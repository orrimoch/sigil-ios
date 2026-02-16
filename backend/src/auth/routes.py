"""
Sigil Auth — API endpoints for authentication.
"""

import json
import time
from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Dict, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_db_session
from .auth_service import AuthService
from .middleware import get_current_user
from .models import User

auth_router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

# AUTH-003: Brute force protection
# Track failed login attempts: email -> (attempts, first_attempt_time)
# HIGH NOTE SEC-004: In-memory tracking doesn't persist across restarts.
# For production with multiple instances, use Redis or database-backed tracking.
# Current implementation is acceptable for single-server deployment.
_failed_logins: Dict[str, Tuple[int, float]] = defaultdict(lambda: (0, 0.0))
_LOCKOUT_THRESHOLD = 5  # Lock after 5 failed attempts
_LOCKOUT_DURATION = 15 * 60  # 15 minutes in seconds


def _check_brute_force(email: str) -> None:
    """Check if account is locked due to too many failed attempts."""
    email = email.lower().strip()
    attempts, first_time = _failed_logins[email]
    
    if attempts >= _LOCKOUT_THRESHOLD:
        elapsed = time.time() - first_time
        if elapsed < _LOCKOUT_DURATION:
            remaining = int(_LOCKOUT_DURATION - elapsed)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Account temporarily locked due to too many failed attempts. Try again in {remaining // 60} minutes."
            )
        else:
            # Lockout expired, reset
            _failed_logins[email] = (0, 0.0)


def _record_failed_login(email: str) -> None:
    """Record a failed login attempt."""
    email = email.lower().strip()
    attempts, first_time = _failed_logins[email]
    
    if attempts == 0:
        # First failed attempt
        _failed_logins[email] = (1, time.time())
    else:
        # Subsequent failed attempt
        _failed_logins[email] = (attempts + 1, first_time)


def _clear_failed_logins(email: str) -> None:
    """Clear failed login attempts on successful login."""
    email = email.lower().strip()
    if email in _failed_logins:
        del _failed_logins[email]


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


# REC-126, REC-127: User Preferences
class UserPreferences(BaseModel):
    """User trading preferences for risk-adjusted scoring and position sizing."""
    risk_tolerance: Optional[str] = Field(
        None,
        description="Risk tolerance level: conservative, moderate, aggressive"
    )
    portfolio_size: Optional[str] = Field(
        None,
        description="Portfolio size tier: small, medium, large"
    )


class PreferencesResponse(BaseModel):
    success: bool = True
    preferences: UserPreferences


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
    # AUTH-003: Check brute force lockout before attempting login
    _check_brute_force(request.email)
    
    try:
        user, access_token, refresh_token = await AuthService.login(
            db=db,
            email=request.email,
            password=request.password,
        )
        # Clear failed attempts on successful login
        _clear_failed_logins(request.email)
    except ValueError as e:
        # Record failed attempt
        _record_failed_login(request.email)
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

    # Never expose reset code in API response (BUG-008 fix).
    # In production: send via email/SMS.
    # HIGH FIX SEC-003: Don't log any part of reset code (even partial logging reduces entropy)
    if code is not None:
        import logging
        logging.getLogger("auth").debug(f"[DEV] Password reset code generated for {request.email}")
    return {"success": True, "message": "If an account exists, a reset code has been sent."}


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


class AuthStatusResponse(BaseModel):
    auth_required: bool
    server_version: str


@auth_router.get("/status", response_model=AuthStatusResponse)
async def get_auth_status():
    """REC-130: Check whether server requires authentication."""
    from api.main import AUTH_REQUIRED

    return {
        "auth_required": AUTH_REQUIRED,
        "server_version": "1.0.0",
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


# ── REC-126, REC-127: User Preferences ──────────────────────────────────


def _parse_preferences(settings_json: Optional[str]) -> UserPreferences:
    """Parse settings_json into UserPreferences with defaults."""
    if not settings_json:
        return UserPreferences(risk_tolerance="moderate", portfolio_size="medium")
    try:
        data = json.loads(settings_json)
        return UserPreferences(
            risk_tolerance=data.get("risk_tolerance", "moderate"),
            portfolio_size=data.get("portfolio_size", "medium"),
        )
    except (json.JSONDecodeError, TypeError):
        return UserPreferences(risk_tolerance="moderate", portfolio_size="medium")


@auth_router.get("/preferences", response_model=PreferencesResponse)
async def get_preferences(
    current_user: User = Depends(get_current_user),
):
    """
    Get user trading preferences (REC-126, REC-127).
    
    Returns risk tolerance and portfolio size settings.
    These affect scoring thresholds and position limits.
    """
    prefs = _parse_preferences(current_user.settings_json)
    return {"success": True, "preferences": prefs}


@auth_router.put("/preferences", response_model=PreferencesResponse)
async def update_preferences(
    request: UserPreferences,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Update user trading preferences (REC-126, REC-127).
    
    - risk_tolerance: conservative | moderate | aggressive
      Affects BUY/SELL signal thresholds in scoring.
    - portfolio_size: small | medium | large
      Affects max position count and sizing limits.
    """
    # Validate risk_tolerance
    valid_risk = {"conservative", "moderate", "aggressive"}
    if request.risk_tolerance and request.risk_tolerance.lower() not in valid_risk:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid risk_tolerance. Must be one of: {', '.join(valid_risk)}"
        )
    
    # Validate portfolio_size
    valid_size = {"small", "medium", "large"}
    if request.portfolio_size and request.portfolio_size.lower() not in valid_size:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid portfolio_size. Must be one of: {', '.join(valid_size)}"
        )
    
    # Merge with existing settings
    existing = _parse_preferences(current_user.settings_json)
    updated = {
        "risk_tolerance": (request.risk_tolerance or existing.risk_tolerance).lower(),
        "portfolio_size": (request.portfolio_size or existing.portfolio_size).lower(),
    }
    
    # Preserve any other settings
    try:
        all_settings = json.loads(current_user.settings_json) if current_user.settings_json else {}
    except (json.JSONDecodeError, TypeError):
        all_settings = {}
    
    all_settings.update(updated)
    current_user.settings_json = json.dumps(all_settings)
    
    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)
    
    return {
        "success": True,
        "preferences": UserPreferences(**updated),
    }
