"""
Sigil Auth — API endpoints for authentication.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_db_session
from .auth_service import AuthService
from .middleware import get_current_user
from .models import User

auth_router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


# ── Request / Response schemas ──────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: str = Field(..., description="User email")
    password: str = Field(..., min_length=8, description="Password (min 8 chars)")
    full_name: str = Field(..., min_length=1, description="Full name")


class LoginRequest(BaseModel):
    email: str = Field(..., description="User email")
    password: str = Field(..., description="Password")


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., description="Refresh token")


class UpdateProfileRequest(BaseModel):
    full_name: Optional[str] = None
    settings_json: Optional[str] = None


class PasswordResetRequest(BaseModel):
    email: str = Field(..., description="Account email")


class PasswordResetVerifyRequest(BaseModel):
    email: str = Field(..., description="Account email")
    code: str = Field(..., min_length=6, max_length=6, description="6-digit reset code")
    new_password: str = Field(..., min_length=8, description="New password (min 8 chars)")


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    is_active: bool
    ibkr_account_id: Optional[str] = None
    settings_json: Optional[str] = None


class AuthResponse(BaseModel):
    success: bool = True
    user: UserResponse
    tokens: dict


class TokenResponse(BaseModel):
    success: bool = True
    access_token: str


class ProfileResponse(BaseModel):
    success: bool = True
    user: UserResponse


# ── Endpoints ───────────────────────────────────────────────────────────

@auth_router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """Register a new user account."""
    try:
        user, access_token, refresh_token = await AuthService.register(
            db=db,
            email=request.email,
            password=request.password,
            full_name=request.full_name,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return {
        "success": True,
        "user": user.to_dict(),
        "tokens": {
            "access_token": access_token,
            "refresh_token": refresh_token,
        },
    }


@auth_router.post("/login", response_model=AuthResponse)
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """Log in with email and password."""
    try:
        user, access_token, refresh_token = await AuthService.login(
            db=db,
            email=request.email,
            password=request.password,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    return {
        "success": True,
        "user": user.to_dict(),
        "tokens": {
            "access_token": access_token,
            "refresh_token": refresh_token,
        },
    }


@auth_router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: RefreshRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """Exchange a refresh token for a new access token."""
    try:
        access_token = await AuthService.refresh_access_token(
            db=db,
            refresh_token=request.refresh_token,
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    return {
        "success": True,
        "access_token": access_token,
    }


@auth_router.post("/password-reset/request")
async def request_password_reset(
    request: PasswordResetRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Request a password reset code.
    Always returns success (don't reveal whether email exists).
    In production, the code would be sent via email.
    """
    code = await AuthService.request_password_reset(db=db, email=request.email)

    # For MVP/development: return the code directly.
    # In production: send via email, return only success.
    response = {"success": True, "message": "If an account exists, a reset code has been sent."}
    if code is not None:
        response["code"] = code  # DEV ONLY — remove in production
    return response


@auth_router.post("/password-reset/confirm", response_model=AuthResponse)
async def confirm_password_reset(
    request: PasswordResetVerifyRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """Reset the password using a valid 6-digit code. Returns tokens on success."""
    try:
        user, access_token, refresh_token = await AuthService.reset_password(
            db=db,
            email=request.email,
            code=request.code,
            new_password=request.new_password,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return {
        "success": True,
        "user": user.to_dict(),
        "tokens": {
            "access_token": access_token,
            "refresh_token": refresh_token,
        },
    }


@auth_router.get("/me", response_model=ProfileResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
):
    """Get current user profile (requires auth)."""
    return {
        "success": True,
        "user": current_user.to_dict(),
    }


@auth_router.put("/me", response_model=ProfileResponse)
async def update_me(
    request: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Update current user profile (requires auth)."""
    if request.full_name is not None:
        current_user.full_name = request.full_name.strip()
    if request.settings_json is not None:
        current_user.settings_json = request.settings_json

    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)

    return {
        "success": True,
        "user": current_user.to_dict(),
    }
