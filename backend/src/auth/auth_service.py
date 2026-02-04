"""
Sigil Auth — Core authentication service.

Handles registration, login, JWT token creation/verification, and password hashing.
"""

import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Tuple

import bcrypt
import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import User

# ── Secret key management ──────────────────────────────────────────────

SECRET_FILE = Path(__file__).parent.parent.parent / "data" / ".jwt_secret"

def _load_or_create_secret() -> str:
    """Load JWT secret from env var first, then disk, or generate + persist (BUG-018 fix)."""
    import os
    # Prefer environment variable
    env_secret = os.environ.get("JWT_SECRET")
    if env_secret:
        return env_secret
    # Fall back to file-based secret
    if SECRET_FILE.exists():
        # Set restrictive file permissions
        SECRET_FILE.chmod(0o600)
        return SECRET_FILE.read_text().strip()
    secret = secrets.token_hex(64)
    SECRET_FILE.parent.mkdir(parents=True, exist_ok=True)
    SECRET_FILE.write_text(secret)
    SECRET_FILE.chmod(0o600)  # Owner read/write only
    return secret

JWT_SECRET = _load_or_create_secret()
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60           # 1 hour
REFRESH_TOKEN_EXPIRE_DAYS = 30             # 30 days


# ── Password utilities ─────────────────────────────────────────────────

def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Check a plaintext password against a bcrypt hash."""
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


# ── JWT utilities ───────────────────────────────────────────────────────

def create_access_token(user_id: str) -> str:
    """Create a short-lived access token."""
    payload = {
        "sub": user_id,
        "type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    """Create a long-lived refresh token."""
    payload = {
        "sub": user_id,
        "type": "refresh",
        "exp": datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and validate a JWT. Raises jwt.PyJWTError on failure."""
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])


# ── AuthService ─────────────────────────────────────────────────────────

class AuthService:
    """High-level authentication operations."""

    @staticmethod
    async def register(
        db: AsyncSession,
        email: str,
        password: str,
        full_name: str,
    ) -> Tuple[User, str, str]:
        """
        Register a new user.

        Returns (user, access_token, refresh_token).
        Raises ValueError on duplicate email or validation failure.
        """
        email = email.lower().strip()

        # Check for existing user
        result = await db.execute(select(User).where(User.email == email))
        if result.scalars().first() is not None:
            raise ValueError("Email already registered")

        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters")

        user = User(
            email=email,
            password_hash=hash_password(password),
            full_name=full_name.strip(),
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

        access_token = create_access_token(user.id)
        refresh_token = create_refresh_token(user.id)
        return user, access_token, refresh_token

    @staticmethod
    async def login(
        db: AsyncSession,
        email: str,
        password: str,
    ) -> Tuple[User, str, str]:
        """
        Authenticate a user.

        Returns (user, access_token, refresh_token).
        Raises ValueError on bad credentials.
        """
        email = email.lower().strip()

        result = await db.execute(select(User).where(User.email == email))
        user = result.scalars().first()

        if user is None or not verify_password(password, user.password_hash):
            raise ValueError("Invalid email or password")

        if not user.is_active:
            raise ValueError("Account is disabled")

        access_token = create_access_token(user.id)
        refresh_token = create_refresh_token(user.id)
        return user, access_token, refresh_token

    @staticmethod
    def verify_token(token: str) -> str:
        """
        Verify an access token.

        Returns user_id (sub claim). Raises on invalid/expired token.
        """
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise ValueError("Not an access token")
        return payload["sub"]

    @staticmethod
    async def refresh_access_token(
        db: AsyncSession,
        refresh_token: str,
    ) -> str:
        """
        Exchange a valid refresh token for a new access token.

        Returns new access_token. Raises on invalid/expired refresh token.
        """
        payload = decode_token(refresh_token)
        if payload.get("type") != "refresh":
            raise ValueError("Not a refresh token")

        user_id = payload["sub"]

        # Ensure user still exists and is active
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalars().first()
        if user is None or not user.is_active:
            raise ValueError("User not found or disabled")

        return create_access_token(user_id)

    @staticmethod
    async def get_user_by_id(db: AsyncSession, user_id: str) -> Optional[User]:
        """Fetch a user by primary key."""
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalars().first()

    @staticmethod
    async def request_password_reset(db: AsyncSession, email: str) -> Optional[str]:
        """
        Generate a 6-digit reset code for the given email.
        Returns the code, or None if user not found (don't reveal this to caller).
        Code expires in 15 minutes.
        """
        import random
        email = email.lower().strip()
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalars().first()

        if user is None or not user.is_active:
            return None

        code = f"{random.randint(0, 999999):06d}"
        user.reset_code = code
        user.reset_code_expires = datetime.now(timezone.utc) + timedelta(minutes=15)
        db.add(user)
        await db.commit()
        return code

    @staticmethod
    async def verify_reset_code(db: AsyncSession, email: str, code: str) -> bool:
        """Check if a reset code is valid and not expired."""
        email = email.lower().strip()
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalars().first()

        if user is None or user.reset_code is None or user.reset_code_expires is None:
            return False

        if user.reset_code != code:
            return False

        expires = user.reset_code_expires
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > expires:
            return False

        return True

    @staticmethod
    async def reset_password(
        db: AsyncSession,
        email: str,
        code: str,
        new_password: str,
    ) -> Tuple[User, str, str]:
        """
        Reset password using a valid code.
        Returns (user, access_token, refresh_token).
        Raises ValueError on invalid code, expired code, or weak password.
        """
        email = email.lower().strip()
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalars().first()

        if user is None:
            raise ValueError("Invalid email or reset code")

        if user.reset_code is None or user.reset_code != code:
            raise ValueError("Invalid email or reset code")

        expires = user.reset_code_expires
        if expires is None:
            raise ValueError("Reset code has expired")
        # Ensure timezone-aware comparison
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > expires:
            raise ValueError("Reset code has expired")

        if len(new_password) < 8:
            raise ValueError("Password must be at least 8 characters")

        user.password_hash = hash_password(new_password)
        user.reset_code = None
        user.reset_code_expires = None
        db.add(user)
        await db.commit()
        await db.refresh(user)

        access_token = create_access_token(user.id)
        refresh_token = create_refresh_token(user.id)
        return user, access_token, refresh_token
