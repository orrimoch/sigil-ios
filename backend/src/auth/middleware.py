"""
Sigil Auth — FastAPI dependencies for authentication.
"""

from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

import os
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


async def get_agent_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db_session),
) -> User:
    """
    Get current user for agent operations.
    
    When authenticated: returns the authenticated user.
    When not authenticated: returns the default agent user from AGENT_DEFAULT_USER_ID.
    """
    from api.main import AUTH_REQUIRED
    
    # Try authenticated user first
    if credentials:
        try:
            user = await get_current_user(credentials, db)
            if user:
                return user
        except HTTPException:
            pass  # Fall through to default user
    
    # When auth not required, use default agent user
    if not AUTH_REQUIRED:
        default_user_id = os.getenv("AGENT_DEFAULT_USER_ID")
        if default_user_id:
            user = await AuthService.get_user_by_id(db, default_user_id)
            if user:
                return user
    
    # Final fallback - raise 401
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required for agent operations",
        headers={"WWW-Authenticate": "Bearer"},
    )
