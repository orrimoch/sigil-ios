"""
Sigil Auth — FastAPI dependencies for authentication.
"""

from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_db_session
from .auth_service import AuthService
from .models import User

security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db_session),
) -> User:
    """
    FastAPI dependency — extracts and validates Bearer token.
    Returns the authenticated User or raises 401.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = AuthService.verify_token(credentials.credentials)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await AuthService.get_user_by_id(db, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or disabled",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db_session),
) -> Optional[User]:
    """
    Same as get_current_user but returns None instead of raising 401
    when no credentials are provided. Useful for endpoints that work
    both authenticated and unauthenticated.
    """
    if credentials is None:
        return None

    try:
        user_id = AuthService.verify_token(credentials.credentials)
    except Exception:
        return None

    return await AuthService.get_user_by_id(db, user_id)


async def get_required_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db_session),
) -> Optional[User]:
    """
    Auth-gate dependency (REC-130).

    When AUTH_REQUIRED=True: requires valid Bearer token, returns 401 if missing/invalid.
    When AUTH_REQUIRED=False: falls back to get_optional_user behavior (returns None).
    """
    from api.main import AUTH_REQUIRED

    if AUTH_REQUIRED:
        return await get_current_user(credentials, db)
    else:
        return await get_optional_user(credentials, db)
