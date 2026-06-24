from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from typing import Optional
from app.database import get_database
from app.v1.auth.schema import (
    RegisterRequest, LoginRequest, TokenResponse,
    RefreshTokenRequest, UserResponse,
    ForgotPasswordRequest, VerifyOTPRequest,
    ResetPasswordRequest, ChangePasswordRequest
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
**Purpose:** Create a new user account. Used for creating the initial superadmin.
For org_admin use `POST /organizations/`. For hr_admin use `POST /users/`.

**Access:** Public — no authentication required.

**Request Body:**
| Field | Type | Required | Notes |
|---|---|---|---|
| email | string | ✅ | Must be unique |
| full_name | string | ✅ | |
| role | string | ✅ | `superadmin` / `org_admin` / `hr_admin` / `employee` |
| password | string | ❌ | If omitted, defaults to `Welcome1` |

**Password rules (if provided):** min 8 chars, 1 uppercase, 1 lowercase, 1 digit, 1 special char.

**Response 201:**
```json
{
  "id": "65abc123...",
  "email": "superadmin@hrms.com",
  "full_name": "Super Admin",
  "role": "superadmin",
  "is_active": true,
  "is_verified": false
}
```

**Errors:**
- `400` — Email already registered, or password too weak
- `422` — Missing required fields
""",
)
async def register(data: RegisterRequest, db=Depends(get_database)):
    service = AuthService(db)
    user = await service.register_user(data)
    user = convert_objectid_to_str(user)
    return UserResponse(
        id=user["_id"], email=user["email"], full_name=user["full_name"],
        role=user["role"], is_active=user["is_active"], is_verified=user["is_verified"]
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login",
    description="""
**Purpose:** Authenticate user and receive JWT tokens.

**Access:** Public — no authentication required.

**Request Body:**
```json
{ "email": "user@company.com", "password": "Welcome1" }
```

**Response 200:**
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "requires_password_change": true
}
```

**Tokens are also set as HTTP-only cookies automatically.**
- `access_token` — expires in 30 minutes
- `refresh_token` — expires in 7 days

**`requires_password_change: true`** means the user logged in with the default password `Welcome1`.
Frontend should force a password change screen before proceeding.

**Errors:**
- `401` — Wrong email or password
- `403` — Account is inactive
""",
)
async def login(data: LoginRequest, response: Response, db=Depends(get_database)):
    service = AuthService(db)
    tokens = await service.login_user(data)
    response.set_cookie(key="access_token", value=tokens["access_token"],
                        httponly=True, secure=True, samesite="lax", max_age=1800)
    response.set_cookie(key="refresh_token", value=tokens["refresh_token"],
                        httponly=True, secure=True, samesite="lax", max_age=604800)
    return tokens


@router.post(
    "/refresh",
    summary="Refresh Access Token",
    description="""
**Purpose:** Get a new access token after the current one expires (every 30 min).

**Access:** No login required — reads `refresh_token` cookie automatically.

**Request Body:** None — refresh token is read from cookie.

**Response 200:**
```json
{ "access_token": "eyJ...", "token_type": "bearer" }
```
New `access_token` is also set in cookie.

**Errors:**
- `401` — Refresh token missing, expired, or invalid → user must login again
""",
)
async def refresh_token(request: Request, response: Response, db=Depends(get_database)):
    refresh_token_cookie = request.cookies.get("refresh_token")
    if not refresh_token_cookie:
        raise HTTPException(status_code=401, detail="Refresh token not found. Please login again.")
    service = AuthService(db)
    token = await service.refresh_access_token(refresh_token_cookie)
    response.set_cookie(key="access_token", value=token["access_token"],
                        httponly=True, secure=True, samesite="lax", max_age=1800)
    return token


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="Logout",
    description="""
**Purpose:** Logout the current user and clear all auth cookies.

**Access:** Any authenticated user (all roles).

**Request Body:** None.

**Response 200:**
```json
{ "message": "Logged out successfully" }
```

After logout, all requests return `401` until the user logs in again.

**Errors:**
- `401` — Not authenticated
""",
)
async def logout(response: Response, current_user: dict = Depends(get_current_user)):
    response.delete_cookie(key="access_token")
    response.delete_cookie(key="refresh_token")
    return {"message": "Logged out successfully"}


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get Current User Profile",
    description="""
**Purpose:** Get the profile of the currently logged-in user.

**Access:** Any authenticated user (all roles).

**Request Body:** None — user identity is read from the `access_token` cookie.

**Response 200:**
```json
{
  "id": "65abc123...",
  "email": "rajesh@techsolutions.com",
  "full_name": "Rajesh Kumar",
  "role": "org_admin",
  "is_active": true,
  "is_verified": false
}
```

**Use cases:** Check who is logged in, get role for frontend permission control.

**Errors:**
- `401` — Not authenticated
- `404` — User deleted from DB after token was issued
""",
)
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    user = convert_objectid_to_str(current_user)
    return UserResponse(
        id=user["_id"], email=user["email"], full_name=user["full_name"],
        role=user["role"], is_active=user["is_active"], is_verified=user.get("is_verified", False)
    )


@router.post(
    "/forgot-password",
    status_code=status.HTTP_200_OK,
    summary="Forgot Password — Send OTP",
    description="""
**Purpose:** Send a 6-digit OTP to the user's email to begin password reset.

**Access:** Public — no authentication required.

**Request Body:**
```json
{ "email": "user@company.com" }
```

**Response 200:**
```json
{
  "message": "OTP sent to your email address",
  "email": "user@company.com",
  "expires_in_minutes": 10
}
```

OTP is valid for **10 minutes**. A new request overwrites the previous OTP.

**Errors:**
- `403` — Account is inactive
- `404` — Email not found
""",
)
async def forgot_password(data: ForgotPasswordRequest, db=Depends(get_database)):
    return await AuthService(db).forgot_password(data)


@router.post(
    "/verify-otp",
    status_code=status.HTTP_200_OK,
    summary="Verify OTP (Optional Step)",
    description="""
**Purpose:** Validate the OTP before showing the new password form. Optional step.

**Access:** Public — no authentication required.

**Request Body:**
```json
{ "email": "user@company.com", "otp": "123456" }
```

**Response 200:**
```json
{ "message": "OTP verified successfully", "email": "user@company.com" }
```

This does **not** reset the password. Call `POST /auth/reset-password` next.

**Errors:**
- `400` — OTP invalid, expired, or no OTP was requested
- `404` — User not found
""",
)
async def verify_otp(data: VerifyOTPRequest, db=Depends(get_database)):
    return await AuthService(db).verify_otp(data)


@router.post(
    "/reset-password",
    status_code=status.HTTP_200_OK,
    summary="Reset Password with OTP",
    description="""
**Purpose:** Reset the user's password using the OTP received by email.

**Access:** Public — no authentication required.

**Request Body:**
```json
{
  "email": "user@company.com",
  "otp": "123456",
  "new_password": "NewSecure@123"
}
```

**Password rules:** min 8 chars, 1 uppercase, 1 lowercase, 1 digit, 1 special char.

**Response 200:**
```json
{ "message": "Password reset successfully", "email": "user@company.com" }
```

OTP is invalidated after use. Confirmation email is sent. `requires_password_change` is set to `false`.

**Errors:**
- `400` — OTP invalid, expired, or weak password
- `404` — User not found
""",
)
async def reset_password(data: ResetPasswordRequest, db=Depends(get_database)):
    return await AuthService(db).reset_password(data)


@router.post(
    "/change-password",
    status_code=status.HTTP_200_OK,
    summary="Change Password (Logged-in User)",
    description="""
**Purpose:** Change password while logged in. Used when user knows their current password,
or after first login with `Welcome1` when `requires_password_change: true`.

**Access:** Any authenticated user (all roles).

**Request Body:**
```json
{
  "old_password": "Welcome1",
  "new_password": "NewSecure@456"
}
```

**Password rules:** min 8 chars, 1 uppercase, 1 lowercase, 1 digit, 1 special char. Must differ from current.

**Response 200:**
```json
{ "message": "Password changed successfully", "email": "user@company.com" }
```

**Errors:**
- `400` — Old password incorrect, new password too weak, or same as current
- `401` — Not authenticated
""",
)
async def change_password(
    data: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_database)
):
    return await AuthService(db).change_password(str(current_user["_id"]), data)
