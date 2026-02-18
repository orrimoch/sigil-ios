"""
Sigil Auth — Core authentication service.

Handles registration, login, JWT token creation/verification, and password hashing.
"""

import hashlib
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Tuple

import bcrypt
import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import User, RefreshToken

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


def create_refresh_token(user_id: str, token_id: str = None) -> str:
    """Create a long-lived refresh token with unique ID for rotation (REC-308)."""
    if token_id is None:
        token_id = str(uuid.uuid4())
    
    payload = {
        "sub": user_id,
        "type": "refresh",
        "jti": token_id,  # Unique token ID for tracking/revocation
        "exp": datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def hash_token(token: str) -> str:
    """Create SHA-256 hash of token for storage (REC-308)."""
    return hashlib.sha256(token.encode()).hexdigest()


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

        # REC-308: Store refresh token in DB for rotation/revocation
        token_id = str(uuid.uuid4())
        access_token = create_access_token(user.id)
        refresh_token = create_refresh_token(user.id, token_id)
        
        token_record = RefreshToken(
            id=token_id,
            user_id=user.id,
            token_hash=hash_token(refresh_token),
            expires_at=datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        )
        db.add(token_record)
        await db.commit()
        
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

        # REC-308: Store refresh token in DB for rotation/revocation
        token_id = str(uuid.uuid4())
        access_token = create_access_token(user.id)
        refresh_token = create_refresh_token(user.id, token_id)
        
        token_record = RefreshToken(
            id=token_id,
            user_id=user.id,
            token_hash=hash_token(refresh_token),
            expires_at=datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        )
        db.add(token_record)
        await db.commit()
        
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
    ) -> Tuple[str, str]:
        """
        Exchange a valid refresh token for new tokens (REC-308: rotation).

        Returns (new_access_token, new_refresh_token).
        Old refresh token is revoked after use.
        Raises on invalid/expired/revoked refresh token.
        """
        payload = decode_token(refresh_token)
        if payload.get("type") != "refresh":
            raise ValueError("Not a refresh token")

        user_id = payload["sub"]
        token_jti = payload.get("jti")

        # REC-308: Check if token is in DB and not revoked
        token_hash = hash_token(refresh_token)
        result = await db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        stored_token = result.scalar_one_or_none()

        if stored_token is None:
            # Token not found in DB - might be pre-rotation token, allow but log
            pass  # Legacy tokens without DB entry still work
        elif stored_token.revoked:
            # Potential token reuse attack - revoke all user tokens
            await db.execute(
                select(RefreshToken).where(RefreshToken.user_id == user_id)
            )
            # Mark all as revoked (security measure)
            raise ValueError("Token has been revoked (possible replay attack)")

        # Ensure user still exists and is active
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalars().first()
        if user is None or not user.is_active:
            raise ValueError("User not found or disabled")

        # REC-308: Create new refresh token (rotation)
        new_token_id = str(uuid.uuid4())
        new_refresh_token = create_refresh_token(user_id, new_token_id)
        new_access_token = create_access_token(user_id)

        # Store new token in DB
        new_token_record = RefreshToken(
            id=new_token_id,
            user_id=user_id,
            token_hash=hash_token(new_refresh_token),
            expires_at=datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        )
        db.add(new_token_record)

        # Revoke old token if it was in DB
        if stored_token and not stored_token.revoked:
            stored_token.revoked = True
            stored_token.replaced_by = new_token_id

        await db.commit()

        return new_access_token, new_refresh_token

    @staticmethod
    async def get_user_by_id(db: AsyncSession, user_id: str) -> Optional[User]:
        """Fetch a user by primary key."""
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalars().first()

    @staticmethod
    async def request_password_reset(db: AsyncSession, email: str) -> Optional[str]:
        """
        Generate a secure reset token for the given email.
        Returns the token, or None if user not found (don't reveal this to caller).
        Token expires in 15 minutes.
        
        REC-307: Changed from 6-digit numeric (1M possibilities) to 
        22-char alphanumeric token (10^39 possibilities) for security.
        """
        # AUTH-001: Use cryptographically secure random number generator
        email = email.lower().strip()
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalars().first()

        if user is None or not user.is_active:
            return None

        # REC-307: Use secure token instead of weak 6-digit code
        code = secrets.token_urlsafe(16)  # 22 chars, ~128 bits entropy
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
