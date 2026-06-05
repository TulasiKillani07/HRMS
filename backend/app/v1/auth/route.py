from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from typing import Optional
from app.database import get_database
from app.v1.auth.schema import (
    RegisterRequest,
    LoginRequest,
    TokenResponse,
    RefreshTokenRequest,
    UserResponse,
    ForgotPasswordRequest,
    VerifyOTPRequest,
    ResetPasswordRequest,
    ChangePasswordRequest
)
from app.v1.auth.service import AuthService
from app.core.dependencies import get_current_user
from app.utils.helpers import convert_objectid_to_str

router = APIRouter()

@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register New User",
    description="""
    **Purpose:** Register a new user account in the HRMS system
    
    **Access:** Public (No authentication required)
    
    **Details:**
    - Creates new user with provided credentials
    - Email must be unique in the system
    - **Password is OPTIONAL - defaults to "Welcome1" if not provided**
    - Supports multiple roles
    
    **Password Field (Optional):**
    - If NOT provided: Uses default password **"Welcome1"**
    - If provided: Must meet security requirements (validated)
    - Default password requires change on first login
    
    **Password Requirements (if custom password provided):**
    - Minimum 8 characters
    - At least one uppercase letter (A-Z)
    - At least one lowercase letter (a-z)
    - At least one digit (0-9)
    - At least one special character (!@#$%^&*...)
    
    **Supported Roles:**
    - `superadmin`: Full system access, can create organizations
    - `org_admin`: Organization administrator (auto-created with org)
    - `hr_admin`: HR department administrator
    - `employee`: Regular employee
    
    **Request Examples:**
    
    **Option 1: Without password (uses "Welcome1")**
    ```json
    {
      "email": "superadmin@hrms.com",
      "full_name": "Super Admin",
      "role": "superadmin"
    }
    ```
    Login with: email + password "Welcome1"
    
    **Option 2: With custom password**
    ```json
    {
      "email": "superadmin@hrms.com",
      "password": "CustomPass@123",
      "full_name": "Super Admin",
      "role": "superadmin"
    }
    ```
    Login with: email + custom password
    
    **Use Cases:**
    - Create initial superadmin account (first time setup)
    - Manual user registration by admin
    - Self-registration (if enabled)
    
    **Important Notes:**
    - For organization admins, use `POST /organizations/` instead
    - That endpoint automatically creates the admin user with "Welcome1"
    - This endpoint is for standalone users or superadmin
    
    **After Registration:**
    - User is created but not verified (`is_verified: false`)
    - Account is active by default (`is_active: true`)
    - User can login immediately
    - If default password used: `requires_password_change: true`
    - If custom password used: `requires_password_change: false`
    """,
    responses={
        201: {
            "description": "User successfully registered",
            "content": {
                "application/json": {
                    "example": {
                        "id": "65abc123...",
                        "email": "superadmin@hrms.com",
                        "full_name": "Super Admin",
                        "role": "superadmin",
                        "is_active": True,
                        "is_verified": False
                    }
                }
            }
        },
        400: {"description": "Email already exists or password doesn't meet requirements (if custom password provided)"},
        422: {"description": "Invalid request data (missing required fields, wrong format)"}
    }
)
async def register(data: RegisterRequest, db=Depends(get_database)):
    service = AuthService(db)
    user = await service.register_user(data)
    user = convert_objectid_to_str(user)
    return UserResponse(
        id=user["_id"],
        email=user["email"],
        full_name=user["full_name"],
        role=user["role"],
        is_active=user["is_active"],
        is_verified=user["is_verified"]
    )

@router.post(
    "/login",
    response_model=TokenResponse,
    summary="User Login",
    description="""
    **Purpose:** Authenticate user and receive JWT tokens in cookies
    
    **Access:** Public (No authentication required)
    
    **Details:**
    - Validates email and password
    - Generates access token (30 min) and refresh token (7 days)
    - **Automatically sets tokens in HTTP-only cookies**
    - Also returns tokens in response body (for API clients)
    - Returns `requires_password_change` flag for first-time login handling
    
    **Cookies Automatically Set:**
    - `access_token`: HTTP-only, Secure, SameSite=Lax (30 min expiry)
    - `refresh_token`: HTTP-only, Secure, SameSite=Lax (7 days expiry)
    
    **Response Body:**
    - access_token: Also available in response (for mobile/API clients)
    - refresh_token: Also available in response (for mobile/API clients)
    - token_type: "bearer"
    - **requires_password_change: Boolean flag indicating if user must change password**
    
    **First-Time Login & Password Change Flow:**
    - When user is created with default password "Welcome1": `requires_password_change: true`
    - Frontend should display password change modal/popup when this flag is `true`
    - User must call `/auth/change-password` endpoint to set new password
    - After password change: `requires_password_change: false`
    
    **Frontend Integration Example:**
    ```javascript
    const response = await login(email, password);
    
    if (response.requires_password_change) {
      // Show password change popup/modal (force user to change password)
      showChangePasswordModal();
    } else {
      // Proceed to dashboard
      redirectToDashboard();
    }
    ```
    
    **After Login:**
    - Browser automatically sends cookies with every request
    - No need to manually add Authorization header
    - Access protected endpoints immediately
    
    **Security Features:**
    - HTTP-only cookies prevent XSS attacks
    - Secure flag ensures HTTPS transmission
    - SameSite prevents CSRF attacks
    - Default passwords require mandatory change on first login
    
    **Usage:**
    - Web: Cookies handled automatically by browser
    - API/Mobile: Use tokens from response body
    """,
    responses={
        200: {
            "description": "Login successful, tokens set in cookies and returned in body",
            "content": {
                "application/json": {
                    "examples": {
                        "first_time_login": {
                            "summary": "First-time login (requires password change)",
                            "value": {
                                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                                "token_type": "bearer",
                                "requires_password_change": True
                            }
                        },
                        "normal_login": {
                            "summary": "Normal login (password already changed)",
                            "value": {
                                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                                "token_type": "bearer",
                                "requires_password_change": False
                            }
                        }
                    }
                }
            }
        },
        401: {"description": "Invalid email or password"},
        403: {"description": "Account is inactive or suspended"}
    }
)
async def login(data: LoginRequest, response: Response, db=Depends(get_database)):
    service = AuthService(db)
    tokens = await service.login_user(data)
    
    # Set access token in HTTP-only cookie (30 minutes)
    response.set_cookie(
        key="access_token",
        value=tokens["access_token"],
        httponly=True,
        secure=True,  # Only send over HTTPS in production
        samesite="lax",
        max_age=1800,  # 30 minutes in seconds
    )
    
    # Set refresh token in HTTP-only cookie (7 days)
    response.set_cookie(
        key="refresh_token",
        value=tokens["refresh_token"],
        httponly=True,
        secure=True,  # Only send over HTTPS in production
        samesite="lax",
        max_age=604800,  # 7 days in seconds
    )
    
    return tokens

@router.post(
    "/refresh",
    response_model=dict,
    summary="Refresh Access Token",
    description="""
    **Purpose:** Get a new access token when it expires
    
    **Access:** Public (Requires valid refresh token in cookie)
    
    **Details:**
    - Called automatically when access token expires (after 30 minutes)
    - **Refresh token is read automatically from cookie**
    - No request body needed
    - Generates new access token (valid for 30 minutes)
    - **Automatically sets new access token in cookie**
    - Refresh token remains valid for 7 days
    
    **How It Works:**
    1. Browser automatically sends `refresh_token` cookie with request
    2. Server validates the refresh token
    3. Server generates new access token
    4. Server sets new `access_token` in cookie
    5. Returns new token in response body
    
    **No Manual Action Required:**
    - Browser handles cookies automatically
    - Just call the endpoint when access token expires
    - New access token is set in cookie
    
    **Response:**
    - New access_token in response body
    - New access_token set in cookie
    
    **Error Cases:**
    - 401: Refresh token cookie not found (user needs to login)
    - 401: Refresh token expired (user needs to login)
    - 401: Refresh token invalid (user needs to login)
    
    **Usage Example:**
    ```javascript
    // Frontend (automatic)
    fetch('/HRMS/auth/refresh', { 
      method: 'POST',
      credentials: 'include'  // Important: sends cookies
    })
    ```
    """,
    responses={
        200: {
            "description": "New access token generated and set in cookie",
            "content": {
                "application/json": {
                    "example": {
                        "access_token": "new_access_token_here",
                        "token_type": "bearer"
                    }
                }
            }
        },
        401: {"description": "Refresh token not found, expired, or invalid. Login required."}
    }
)
async def refresh_token(
    request: Request,
    response: Response,
    db=Depends(get_database)
):
    # Get refresh token from cookie
    refresh_token_cookie = request.cookies.get("refresh_token")
    
    if not refresh_token_cookie:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token not found. Please login again."
        )
    
    service = AuthService(db)
    token = await service.refresh_access_token(refresh_token_cookie)
    
    # Set new access token in HTTP-only cookie
    response.set_cookie(
        key="access_token",
        value=token["access_token"],
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=1800,  # 30 minutes
    )
    
    return token

@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="User Logout",
    description="""
    **Purpose:** Logout user and clear all authentication cookies
    
    **Access:** Authenticated users only (All roles)
    
    **Details:**
    - Clears `access_token` cookie
    - Clears `refresh_token` cookie
    - Invalidates current session
    - User must login again to access protected resources
    
    **What Happens:**
    1. Server removes `access_token` cookie from browser
    2. Server removes `refresh_token` cookie from browser
    3. User session is terminated
    4. Any further requests will require new login
    
    **Automatic Cookie Removal:**
    - Browser automatically removes cookies
    - No manual action needed
    - Secure logout process
    
    **After Logout:**
    - Access to protected endpoints will return 401 Unauthorized
    - User needs to call `/auth/login` to authenticate again
    
    **Usage Example:**
    ```javascript
    // Frontend
    fetch('/HRMS/auth/logout', { 
      method: 'POST',
      credentials: 'include'  // Important: sends cookies
    })
    ```
    """,
    responses={
        200: {
            "description": "Logged out successfully, all cookies cleared",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Logged out successfully"
                    }
                }
            }
        },
        401: {"description": "Not authenticated (no valid access token)"}
    }
)
async def logout(
    response: Response,
    current_user: dict = Depends(get_current_user)
):
    # Clear access token cookie
    response.delete_cookie(key="access_token")
    
    # Clear refresh token cookie
    response.delete_cookie(key="refresh_token")
    
    return {"message": "Logged out successfully"}

@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get Current User Profile",
    description="""
    **Purpose:** Retrieve authenticated user's profile information
    
    **Access:** Authenticated users only (All roles)
    
    **Details:**
    - Returns current user's profile data
    - **Access token is read automatically from cookie**
    - No Authorization header needed (but supported)
    - Use to verify authentication status
    - Get user role and permissions
    
    **Authentication Methods (Automatic):**
    - **Primary:** Cookie with `access_token` (sent by browser automatically)
    - **Fallback:** Authorization header: `Bearer {access_token}` (for API clients)
    
    **How It Works:**
    1. Browser automatically sends `access_token` cookie
    2. Server validates token from cookie
    3. Server fetches user from database
    4. Returns user profile information
    
    **No Manual Action Required:**
    - After login, cookies are set
    - Browser sends cookies automatically
    - Just call this endpoint
    
    **Response:**
    - User ID, email, full name
    - User role (superadmin, org_admin, hr_admin, employee)
    - Account status (active, verified)
    
    **Use Cases:**
    - Verify user is logged in
    - Display user info in UI
    - Check user permissions/role
    - Validate session status
    
    **Usage Example:**
    ```javascript
    // Frontend (automatic)
    fetch('/HRMS/auth/me', { 
      credentials: 'include'  // Important: sends cookies
    })
    ```
    """,
    responses={
        200: {
            "description": "User profile retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "id": "65abc123...",
                        "email": "admin@example.com",
                        "full_name": "John Admin",
                        "role": "org_admin",
                        "is_active": True,
                        "is_verified": False
                    }
                }
            }
        },
        401: {"description": "Not authenticated (no valid access token in cookie or header)"},
        404: {"description": "User not found in database"}
    }
)
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    user = convert_objectid_to_str(current_user)
    return UserResponse(
        id=user["_id"],
        email=user["email"],
        full_name=user["full_name"],
        role=user["role"],
        is_active=user["is_active"],
        is_verified=user.get("is_verified", False)
    )

@router.post(
    "/forgot-password",
    status_code=status.HTTP_200_OK,
    summary="Forgot Password - Request OTP",
    description="""
    **Purpose:** Initiate password reset process by sending OTP to user's email
    
    **Access:** Public (No authentication required)
    
    **Details:**
    - User provides their registered email
    - System generates a 6-digit OTP
    - OTP is sent to user's email
    - OTP is valid for 10 minutes
    - After OTP expires, user must request a new one
    
    **Flow:**
    1. User enters email address
    2. System validates email exists
    3. Generates 6-digit OTP (e.g., "123456")
    4. Sends OTP via email
    5. OTP expires in 10 minutes
    
    **Security Features:**
    - OTP is single-use only
    - Expires after 10 minutes
    - New OTP request overwrites previous OTP
    - Email doesn't reveal if account exists (prevents user enumeration)
    
    **Next Step:**
    - Use `/auth/reset-password` endpoint with OTP and new password
    - Or use `/auth/verify-otp` to verify OTP first (optional)
    
    **Request Example:**
    ```json
    {
      "email": "user@example.com"
    }
    ```
    
    **Response:**
    - Confirmation message
    - Email where OTP was sent
    - OTP expiry time (10 minutes)
    """,
    responses={
        200: {
            "description": "OTP sent successfully to email",
            "content": {
                "application/json": {
                    "example": {
                        "message": "OTP sent to your email address",
                        "email": "user@example.com",
                        "expires_in_minutes": 10
                    }
                }
            }
        },
        403: {"description": "Account is inactive"},
        404: {"description": "If email exists, OTP has been sent (security message)"}
    }
)
async def forgot_password(data: ForgotPasswordRequest, db=Depends(get_database)):
    service = AuthService(db)
    result = await service.forgot_password(data)
    return result

@router.post(
    "/verify-otp",
    status_code=status.HTTP_200_OK,
    summary="Verify OTP (Optional Step)",
    description="""
    **Purpose:** Verify OTP before resetting password (optional validation step)
    
    **Access:** Public (No authentication required)
    
    **Details:**
    - Optional endpoint to verify OTP validity
    - Does NOT reset password
    - Useful for frontend to validate OTP before showing password form
    - Can skip this and directly use `/auth/reset-password`
    
    **Use Cases:**
    - Multi-step password reset UI
    - Verify OTP before showing password input form
    - Provide better UX with validation feedback
    
    **Request Example:**
    ```json
    {
      "email": "user@example.com",
      "otp": "123456"
    }
    ```
    
    **Response:**
    - Confirmation that OTP is valid
    - User can proceed to reset password
    
    **Note:** This is optional. You can directly call `/auth/reset-password` with OTP and new password.
    """,
    responses={
        200: {
            "description": "OTP verified successfully",
            "content": {
                "application/json": {
                    "example": {
                        "message": "OTP verified successfully",
                        "email": "user@example.com"
                    }
                }
            }
        },
        400: {"description": "Invalid OTP, expired OTP, or no OTP requested"},
        404: {"description": "User not found"}
    }
)
async def verify_otp(data: VerifyOTPRequest, db=Depends(get_database)):
    service = AuthService(db)
    result = await service.verify_otp(data)
    return result

@router.post(
    "/reset-password",
    status_code=status.HTTP_200_OK,
    summary="Reset Password with OTP",
    description="""
    **Purpose:** Reset user password using OTP received via email
    
    **Access:** Public (No authentication required)
    
    **Details:**
    - User provides email, OTP, and new password
    - System validates OTP (must be valid and not expired)
    - New password is validated for security requirements
    - Password is updated in database
    - OTP is cleared after successful reset
    - Confirmation email is sent
    
    **Flow:**
    1. User enters email, OTP from email, and new password
    2. System validates OTP is correct and not expired
    3. System validates new password meets requirements
    4. Password is updated
    5. OTP is deleted
    6. Confirmation email sent
    7. User can now login with new password
    
    **Password Requirements:**
    - Minimum 8 characters
    - At least one uppercase letter (A-Z)
    - At least one lowercase letter (a-z)
    - At least one digit (0-9)
    - At least one special character (!@#$%^&*...)
    
    **Request Example:**
    ```json
    {
      "email": "user@example.com",
      "otp": "123456",
      "new_password": "NewSecurePass@123"
    }
    ```
    
    **After Success:**
    - User receives confirmation email
    - OTP is invalidated
    - User can login with new password
    - `requires_password_change` flag is set to false
    """,
    responses={
        200: {
            "description": "Password reset successfully",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Password reset successfully",
                        "email": "user@example.com"
                    }
                }
            }
        },
        400: {"description": "Invalid OTP, expired OTP, or password doesn't meet requirements"},
        404: {"description": "User not found"}
    }
)
async def reset_password(data: ResetPasswordRequest, db=Depends(get_database)):
    service = AuthService(db)
    result = await service.reset_password(data)
    return result

@router.post(
    "/change-password",
    status_code=status.HTTP_200_OK,
    summary="Change Password (Authenticated User)",
    description="""
    **Purpose:** Change password for authenticated user (requires current password)
    
    **Access:** Authenticated users only (All roles)
    
    **Details:**
    - User must be logged in (access token required)
    - User provides current password and new password
    - System verifies current password is correct
    - New password must be different from current password
    - New password is validated for security requirements
    - Password is updated in database
    
    **Difference from Reset Password:**
    - **Change Password:** User is logged in, knows current password
    - **Reset Password:** User forgot password, uses OTP from email
    
    **Flow:**
    1. User is logged in (has valid access token)
    2. User provides current password and new password
    3. System verifies current password
    4. System validates new password requirements
    5. Password is updated
    6. User remains logged in
    
    **Password Requirements:**
    - Minimum 8 characters
    - At least one uppercase letter (A-Z)
    - At least one lowercase letter (a-z)
    - At least one digit (0-9)
    - At least one special character (!@#$%^&*...)
    - Must be different from current password
    
    **Request Example:**
    ```json
    {
      "old_password": "CurrentPass@123",
      "new_password": "NewSecurePass@456"
    }
    ```
    
    **Use Cases:**
    - User wants to change password proactively
    - First login with default password "Welcome1"
    - Security policy requires periodic password changes
    - User suspects password is compromised
    """,
    responses={
        200: {
            "description": "Password changed successfully",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Password changed successfully",
                        "email": "user@example.com"
                    }
                }
            }
        },
        400: {"description": "Current password incorrect, or new password doesn't meet requirements"},
        401: {"description": "Not authenticated"},
        404: {"description": "User not found"}
    }
)
async def change_password(
    data: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_database)
):
    service = AuthService(db)
    user_id = str(current_user["_id"])
    result = await service.change_password(user_id, data)
    return result
