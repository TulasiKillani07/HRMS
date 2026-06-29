from datetime import datetime, timedelta
from fastapi import HTTPException, status
from bson import ObjectId
from app.database import get_database
from app.models.user import UserModel
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    decode_token
)
from app.utils.validators import validate_password_strength
from app.utils.notifications import send_password_reset_otp, send_password_reset_success
from app.utils.logger import logger
from app.v1.auth.schema import (
    RegisterRequest,
    LoginRequest,
    ForgotPasswordRequest,
    VerifyOTPRequest,
    ResetPasswordRequest,
    ChangePasswordRequest
)
import random
import string

class AuthService:
    def __init__(self, db=None):
        self.db = db if db is not None else get_database()
    
    async def register_user(self, data: RegisterRequest):
        """Register a new user"""
        # Check if user already exists
        existing_user = await self.db.users.find_one({"email": data.email})
        if existing_user:
            logger.warning(f"Registration failed: Email already exists - {data.email}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Use default password "Welcome1" if not provided
        password = data.password if data.password else "Welcome1"
        
        # Validate password strength only if custom password is provided
        if data.password:
            is_valid, error_msg = validate_password_strength(password)
            if not is_valid:
                logger.warning(f"Registration failed: Weak password for {data.email}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=error_msg
                )
        
        # Create user using UserModel
        user_model = UserModel(
            email=data.email,
            hashed_password=get_password_hash(password),
            full_name=data.full_name,
            role=data.role,
            is_active=True,
            is_verified=False,
            requires_password_change=not data.password,  # Require change if default password used
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        result = await self.db.users.insert_one(user_model.model_dump())
        user_dict = user_model.model_dump()
        user_dict["_id"] = str(result.inserted_id)
        
        logger.info(f"User registered successfully: {data.email} (role: {data.role})")
        return user_dict
    
    async def login_user(self, data: LoginRequest):
        """Login user and return tokens"""
        # Find user
        user = await self.db.users.find_one({"email": data.email})
        if not user:
            logger.warning(f"Login failed: Invalid email - {data.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        
        # Verify password
        if not verify_password(data.password, user["hashed_password"]):
            logger.warning(f"Login failed: Invalid password for {data.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        
        # Check if user is active
        if not user.get("is_active", True):
            logger.warning(f"Login failed: Account inactive - {data.email}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is inactive"
            )
        
        # Check if user needs to change password (only on first login)
        requires_password_change = user.get("requires_password_change", False)
        
        # If this is first login (flag is true), set it to false for future logins
        if requires_password_change:
            await self.db.users.update_one(
                {"_id": user["_id"]},
                {
                    "$set": {
                        "requires_password_change": False,
                        "last_login": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    }
                }
            )
        else:
            await self.db.users.update_one(
                {"_id": user["_id"]},
                {"$set": {"last_login": datetime.utcnow(), "updated_at": datetime.utcnow()}}
            )
        
        # Create tokens
        access_token = create_access_token({"sub": str(user["_id"])})
        refresh_token = create_refresh_token({"sub": str(user["_id"])})
        
        logger.info(f"User logged in successfully: {data.email} (role: {user['role']})")

        # Activity log
        from app.v1.activity_logs.service import ActivityLogService
        await ActivityLogService(self.db).log(
            user=user, action="login", module="auth",
            description=f"{user.get('full_name', data.email)} logged in",
            target_id=str(user["_id"]), target_name=user.get("full_name", data.email), target_type="user"
        )
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "requires_password_change": requires_password_change
        }
    
    async def refresh_access_token(self, refresh_token: str):
        """Refresh access token using refresh token"""
        payload = decode_token(refresh_token)
        
        if payload is None or payload.get("type") != "refresh":
            logger.warning("Token refresh failed: Invalid refresh token")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )
        
        user_id = payload.get("sub")
        user = await self.db.users.find_one({"_id": user_id})
        
        if not user:
            logger.warning(f"Token refresh failed: User not found - {user_id}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        
        # Create new access token
        access_token = create_access_token({"sub": str(user["_id"])})
        
        logger.info(f"Access token refreshed for user: {user['email']}")
        
        return {
            "access_token": access_token,
            "token_type": "bearer"
        }
    
    def _generate_otp(self) -> str:
        """Generate a 6-digit OTP"""
        return ''.join(random.choices(string.digits, k=6))
    
    async def forgot_password(self, data: ForgotPasswordRequest):
        """
        Initiate forgot password process by sending OTP to user's email
        """
        # Find user by email
        user = await self.db.users.find_one({"email": data.email})
        
        if not user:
            # Don't reveal if email exists or not (security best practice)
            logger.warning(f"Forgot password request for non-existent email: {data.email}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="If this email exists, an OTP has been sent"
            )
        
        # Check if user is active
        if not user.get("is_active", True):
            logger.warning(f"Forgot password request for inactive account: {data.email}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is inactive. Please contact support."
            )
        
        # Generate OTP
        otp = self._generate_otp()
        
        # Set OTP expiry to 10 minutes from now
        otp_expires_at = datetime.utcnow() + timedelta(minutes=10)
        
        # Update user with OTP and expiry
        await self.db.users.update_one(
            {"_id": user["_id"]},
            {
                "$set": {
                    "password_reset_otp": otp,
                    "password_reset_otp_expires_at": otp_expires_at,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        # Send OTP via email
        await send_password_reset_otp(
            email=user["email"],
            full_name=user["full_name"],
            otp=otp
        )
        
        logger.info(f"Password reset OTP sent to: {data.email}")
        
        return {
            "message": "OTP sent to your email address",
            "email": user["email"],
            "expires_in_minutes": 10
        }
    
    async def verify_otp(self, data: VerifyOTPRequest):
        """
        Verify OTP without resetting password (optional verification step)
        """
        # Find user by email
        user = await self.db.users.find_one({"email": data.email})
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Check if OTP exists
        if not user.get("password_reset_otp"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No OTP requested. Please use forgot password first."
            )
        
        # Check if OTP is expired
        if user.get("password_reset_otp_expires_at") and \
           user["password_reset_otp_expires_at"] < datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OTP has expired. Please request a new one."
            )
        
        # Verify OTP
        if user["password_reset_otp"] != data.otp:
            logger.warning(f"OTP verification failed for: {data.email}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid OTP"
            )
        
        logger.info(f"OTP verified successfully for: {data.email}")
        return {
            "message": "OTP verified successfully",
            "email": user["email"]
        }
    
    async def reset_password(self, data: ResetPasswordRequest):
        """
        Reset password using OTP
        """
        # Find user by email
        user = await self.db.users.find_one({"email": data.email})
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Check if OTP exists
        if not user.get("password_reset_otp"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No OTP requested. Please use forgot password first."
            )
        
        # Check if OTP is expired
        if user.get("password_reset_otp_expires_at") and \
           user["password_reset_otp_expires_at"] < datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OTP has expired. Please request a new one."
            )
        
        # Verify OTP
        if user["password_reset_otp"] != data.otp:
            logger.warning(f"Password reset failed: Invalid OTP for {data.email}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid OTP"
            )
        
        # Validate new password strength
        is_valid, error_msg = validate_password_strength(data.new_password)
        if not is_valid:
            logger.warning(f"Password reset failed: Weak password for {data.email}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )
        
        # Hash new password
        hashed_password = get_password_hash(data.new_password)
        
        # Update password and clear OTP
        await self.db.users.update_one(
            {"_id": user["_id"]},
            {
                "$set": {
                    "hashed_password": hashed_password,
                    "requires_password_change": False,
                    "updated_at": datetime.utcnow()
                },
                "$unset": {
                    "password_reset_otp": "",
                    "password_reset_otp_expires_at": ""
                }
            }
        )
        
        # Send confirmation email
        await send_password_reset_success(
            email=user["email"],
            full_name=user["full_name"]
        )
        
        logger.info(f"Password reset successfully for: {data.email}")
        
        return {
            "message": "Password reset successfully",
            "email": user["email"]
        }
    
    async def change_password(self, user_id: str, data: ChangePasswordRequest):
        """
        Change password for authenticated user
        """
        # Find user
        user = await self.db.users.find_one({"_id": ObjectId(user_id)})
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Verify old password
        if not verify_password(data.old_password, user["hashed_password"]):
            logger.warning(f"Password change failed: Incorrect old password for user {user_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect"
            )
        
        # Validate new password strength
        is_valid, error_msg = validate_password_strength(data.new_password)
        if not is_valid:
            logger.warning(f"Password change failed: Weak password for user {user_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )
        
        # Check if new password is same as old password
        if verify_password(data.new_password, user["hashed_password"]):
            logger.warning(f"Password change failed: New password same as old for user {user_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New password must be different from current password"
            )
        
        # Hash new password
        hashed_password = get_password_hash(data.new_password)
        
        # Update password
        await self.db.users.update_one(
            {"_id": user["_id"]},
            {
                "$set": {
                    "hashed_password": hashed_password,
                    "requires_password_change": False,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        logger.info(f"Password changed successfully for user: {user['email']}")
        
        return {
            "message": "Password changed successfully",
            "email": user["email"]
        }
