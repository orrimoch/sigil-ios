"""
Unit tests for F11.1 Authentication System (REC-88)

Tests cover:
- Password hashing and verification
- JWT token creation and decoding
- Token type validation (access vs refresh)
- Token expiration
- AuthService registration (duplicate email, validation)
- AuthService login (bad credentials, disabled accounts)
- AuthService token refresh
- AuthService password reset flow
- Request/response schema validation
"""

import pytest
import asyncio
import sys
import os
import uuid
from pathlib import Path
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock, AsyncMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


# ============ Password Utilities ============

class TestPasswordHashing:
    """Tests for bcrypt password hashing."""

    def test_hash_password_returns_string(self):
        """hash_password should return a bcrypt hash string."""
        from auth.auth_service import hash_password
        hashed = hash_password("testpassword123")
        assert isinstance(hashed, str)
        assert hashed.startswith("$2b$")

    def test_hash_password_different_each_time(self):
        """Same password should produce different hashes (unique salt)."""
        from auth.auth_service import hash_password
        h1 = hash_password("samepassword")
        h2 = hash_password("samepassword")
        assert h1 != h2

    def test_verify_password_correct(self):
        """verify_password should return True for correct password."""
        from auth.auth_service import hash_password, verify_password
        hashed = hash_password("mypassword")
        assert verify_password("mypassword", hashed) is True

    def test_verify_password_incorrect(self):
        """verify_password should return False for wrong password."""
        from auth.auth_service import hash_password, verify_password
        hashed = hash_password("correctpassword")
        assert verify_password("wrongpassword", hashed) is False

    def test_verify_password_empty(self):
        """verify_password should return False for empty password."""
        from auth.auth_service import hash_password, verify_password
        hashed = hash_password("realpassword")
        assert verify_password("", hashed) is False

    def test_hash_password_unicode(self):
        """hash_password should handle unicode characters."""
        from auth.auth_service import hash_password, verify_password
        password = "pässwörd123"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True


# ============ JWT Token Utilities ============

class TestJWTTokens:
    """Tests for JWT token creation and decoding."""

    def test_create_access_token(self):
        """create_access_token should return a valid JWT string."""
        from auth.auth_service import create_access_token
        token = create_access_token("user-123")
        assert isinstance(token, str)
        assert len(token) > 50  # JWTs are always long

    def test_create_refresh_token(self):
        """create_refresh_token should return a valid JWT string."""
        from auth.auth_service import create_refresh_token
        token = create_refresh_token("user-456")
        assert isinstance(token, str)
        assert len(token) > 50

    def test_decode_access_token(self):
        """Decoded access token should contain correct claims."""
        from auth.auth_service import create_access_token, decode_token
        user_id = "user-789"
        token = create_access_token(user_id)
        payload = decode_token(token)

        assert payload["sub"] == user_id
        assert payload["type"] == "access"
        assert "exp" in payload
        assert "iat" in payload

    def test_decode_refresh_token(self):
        """Decoded refresh token should have type=refresh."""
        from auth.auth_service import create_refresh_token, decode_token
        user_id = "user-abc"
        token = create_refresh_token(user_id)
        payload = decode_token(token)

        assert payload["sub"] == user_id
        assert payload["type"] == "refresh"

    def test_access_token_expires_in_1_hour(self):
        """Access token expiry should be ~60 minutes from now."""
        from auth.auth_service import create_access_token, decode_token
        token = create_access_token("user-exp")
        payload = decode_token(token)

        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        iat = datetime.fromtimestamp(payload["iat"], tz=timezone.utc)
        delta = exp - iat

        assert 59 <= delta.total_seconds() / 60 <= 61  # ~60 minutes

    def test_refresh_token_expires_in_30_days(self):
        """Refresh token expiry should be ~30 days from now."""
        from auth.auth_service import create_refresh_token, decode_token
        token = create_refresh_token("user-exp2")
        payload = decode_token(token)

        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        iat = datetime.fromtimestamp(payload["iat"], tz=timezone.utc)
        delta = exp - iat

        assert 29 <= delta.days <= 31  # ~30 days

    def test_decode_invalid_token_raises(self):
        """Decoding garbage should raise an error."""
        from auth.auth_service import decode_token
        import jwt as pyjwt
        with pytest.raises(pyjwt.exceptions.DecodeError):
            decode_token("not.a.valid.token")

    def test_decode_expired_token_raises(self):
        """Decoding an expired token should raise."""
        import jwt as pyjwt
        from auth.auth_service import JWT_SECRET, JWT_ALGORITHM
        expired_payload = {
            "sub": "user-old",
            "type": "access",
            "exp": datetime.now(timezone.utc) - timedelta(hours=2),
            "iat": datetime.now(timezone.utc) - timedelta(hours=3),
        }
        token = pyjwt.encode(expired_payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
        from auth.auth_service import decode_token
        with pytest.raises(pyjwt.exceptions.ExpiredSignatureError):
            decode_token(token)

    def test_decode_wrong_secret_raises(self):
        """Token signed with wrong secret should fail verification."""
        import jwt as pyjwt
        from auth.auth_service import decode_token
        payload = {
            "sub": "user-x",
            "type": "access",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iat": datetime.now(timezone.utc),
        }
        token = pyjwt.encode(payload, "wrong-secret-key", algorithm="HS256")
        with pytest.raises(pyjwt.exceptions.InvalidSignatureError):
            decode_token(token)


# ============ AuthService.verify_token ============

class TestVerifyToken:
    """Tests for AuthService.verify_token."""

    def test_verify_access_token_returns_user_id(self):
        """verify_token should return user_id for valid access token."""
        from auth.auth_service import AuthService, create_access_token
        user_id = "user-verify-1"
        token = create_access_token(user_id)
        result = AuthService.verify_token(token)
        assert result == user_id

    def test_verify_refresh_token_raises(self):
        """verify_token should reject refresh tokens."""
        from auth.auth_service import AuthService, create_refresh_token
        token = create_refresh_token("user-verify-2")
        with pytest.raises(ValueError, match="Not an access token"):
            AuthService.verify_token(token)


# ============ User Model ============

class TestUserModel:
    """Tests for the User SQLAlchemy model."""

    def test_user_to_dict_excludes_password(self):
        """to_dict() should never include password_hash."""
        from auth.models import User
        user = User(
            id="test-id",
            email="test@example.com",
            password_hash="$2b$12$hashedvalue",
            full_name="Test User",
            is_active=True,
        )
        d = user.to_dict()
        assert "password_hash" not in d
        assert "reset_code" not in d
        assert d["email"] == "test@example.com"
        assert d["full_name"] == "Test User"
        assert d["is_active"] is True

    def test_user_to_dict_fields(self):
        """to_dict() should contain expected fields."""
        from auth.models import User
        user = User(
            id="u-1",
            email="a@b.com",
            password_hash="hash",
            full_name="A B",
            is_active=True,
            ibkr_account_id="DU12345",
        )
        d = user.to_dict()
        expected_keys = {"id", "email", "full_name", "created_at", "updated_at",
                         "is_active", "ibkr_account_id", "settings_json"}
        assert set(d.keys()) == expected_keys
        assert d["ibkr_account_id"] == "DU12345"


# ============ Request Schema Validation ============

class TestSchemaValidation:
    """Tests for Pydantic request schemas."""

    def test_register_request_valid(self):
        """Valid registration data should pass."""
        from auth.routes import RegisterRequest
        req = RegisterRequest(
            email="test@example.com",
            password="securepass123",
            full_name="Test User",
        )
        assert req.email == "test@example.com"

    def test_register_request_short_password(self):
        """Password under 8 chars should fail validation."""
        from auth.routes import RegisterRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            RegisterRequest(
                email="test@example.com",
                password="short",
                full_name="Test",
            )

    def test_register_request_empty_name(self):
        """Empty full_name should fail validation."""
        from auth.routes import RegisterRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            RegisterRequest(
                email="test@example.com",
                password="securepass123",
                full_name="",
            )

    def test_login_request_valid(self):
        """Valid login data should pass."""
        from auth.routes import LoginRequest
        req = LoginRequest(email="user@test.com", password="pass1234")
        assert req.email == "user@test.com"

    def test_password_reset_request_valid(self):
        """Password reset request should accept email."""
        from auth.routes import PasswordResetRequest
        req = PasswordResetRequest(email="forgot@test.com")
        assert req.email == "forgot@test.com"

    def test_password_reset_verify_code_length(self):
        """Reset code must be exactly 6 characters."""
        from auth.routes import PasswordResetVerifyRequest
        from pydantic import ValidationError

        # Valid
        req = PasswordResetVerifyRequest(
            email="user@test.com",
            code="123456",
            new_password="newpass1234",
        )
        assert req.code == "123456"

        # Too short
        with pytest.raises(ValidationError):
            PasswordResetVerifyRequest(
                email="user@test.com",
                code="123",
                new_password="newpass1234",
            )

        # Too long
        with pytest.raises(ValidationError):
            PasswordResetVerifyRequest(
                email="user@test.com",
                code="1234567",
                new_password="newpass1234",
            )

    def test_password_reset_verify_short_password(self):
        """New password must be at least 8 chars."""
        from auth.routes import PasswordResetVerifyRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            PasswordResetVerifyRequest(
                email="user@test.com",
                code="123456",
                new_password="short",
            )

    def test_refresh_request_valid(self):
        """Refresh request should accept token string."""
        from auth.routes import RefreshRequest
        req = RefreshRequest(refresh_token="some.jwt.token")
        assert req.refresh_token == "some.jwt.token"

    def test_update_profile_optional_fields(self):
        """UpdateProfileRequest fields should be optional."""
        from auth.routes import UpdateProfileRequest
        req = UpdateProfileRequest()
        assert req.full_name is None
        assert req.settings_json is None

        req2 = UpdateProfileRequest(full_name="New Name")
        assert req2.full_name == "New Name"


# ============ AuthService Async Tests (with real DB) ============

@pytest.fixture
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def db_session(event_loop, tmp_path):
    """Create a temporary in-memory database session for testing."""
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from auth.database import Base
    from auth.models import User  # noqa

    db_path = tmp_path / "test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def setup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    event_loop.run_until_complete(setup())

    session = event_loop.run_until_complete(session_factory().__aenter__())
    yield session

    event_loop.run_until_complete(session.close())
    event_loop.run_until_complete(engine.dispose())


class TestAuthServiceRegister:
    """Tests for AuthService.register."""

    def test_register_success(self, db_session, event_loop):
        """Should create user and return tokens."""
        from auth.auth_service import AuthService
        user, access, refresh = event_loop.run_until_complete(
            AuthService.register(
                db=db_session,
                email="new@example.com",
                password="securepass123",
                full_name="New User",
            )
        )
        assert user.email == "new@example.com"
        assert user.full_name == "New User"
        assert user.is_active is True
        assert isinstance(access, str) and len(access) > 50
        assert isinstance(refresh, str) and len(refresh) > 50

    def test_register_email_normalized(self, db_session, event_loop):
        """Email should be lowercased and stripped."""
        from auth.auth_service import AuthService
        user, _, _ = event_loop.run_until_complete(
            AuthService.register(
                db=db_session,
                email="  UPPER@Email.COM  ",
                password="securepass123",
                full_name="Upper",
            )
        )
        assert user.email == "upper@email.com"

    def test_register_duplicate_email_raises(self, db_session, event_loop):
        """Registering same email twice should raise ValueError."""
        from auth.auth_service import AuthService
        event_loop.run_until_complete(
            AuthService.register(db=db_session, email="dup@test.com",
                                 password="password123", full_name="First")
        )
        with pytest.raises(ValueError, match="already registered"):
            event_loop.run_until_complete(
                AuthService.register(db=db_session, email="dup@test.com",
                                     password="password456", full_name="Second")
            )

    def test_register_short_password_raises(self, db_session, event_loop):
        """Password under 8 chars should raise ValueError."""
        from auth.auth_service import AuthService
        with pytest.raises(ValueError, match="at least 8"):
            event_loop.run_until_complete(
                AuthService.register(db=db_session, email="short@test.com",
                                     password="1234567", full_name="Short")
            )


class TestAuthServiceLogin:
    """Tests for AuthService.login."""

    def _create_user(self, db_session, event_loop, email="login@test.com",
                     password="testpass123", full_name="Login User"):
        from auth.auth_service import AuthService
        return event_loop.run_until_complete(
            AuthService.register(db=db_session, email=email,
                                 password=password, full_name=full_name)
        )

    def test_login_success(self, db_session, event_loop):
        """Valid credentials should return user and tokens."""
        from auth.auth_service import AuthService
        self._create_user(db_session, event_loop)
        user, access, refresh = event_loop.run_until_complete(
            AuthService.login(db=db_session, email="login@test.com", password="testpass123")
        )
        assert user.email == "login@test.com"
        assert isinstance(access, str)

    def test_login_wrong_password(self, db_session, event_loop):
        """Wrong password should raise ValueError."""
        from auth.auth_service import AuthService
        self._create_user(db_session, event_loop, email="wrong@test.com")
        with pytest.raises(ValueError, match="Invalid email or password"):
            event_loop.run_until_complete(
                AuthService.login(db=db_session, email="wrong@test.com", password="badpass123")
            )

    def test_login_nonexistent_email(self, db_session, event_loop):
        """Non-existent email should raise ValueError."""
        from auth.auth_service import AuthService
        with pytest.raises(ValueError, match="Invalid email or password"):
            event_loop.run_until_complete(
                AuthService.login(db=db_session, email="nobody@test.com", password="anything123")
            )

    def test_login_email_case_insensitive(self, db_session, event_loop):
        """Login should work regardless of email case."""
        from auth.auth_service import AuthService
        self._create_user(db_session, event_loop, email="case@test.com")
        user, _, _ = event_loop.run_until_complete(
            AuthService.login(db=db_session, email="CASE@TEST.COM", password="testpass123")
        )
        assert user.email == "case@test.com"

    def test_login_disabled_account(self, db_session, event_loop):
        """Disabled account should raise ValueError."""
        from auth.auth_service import AuthService
        user, _, _ = self._create_user(db_session, event_loop, email="disabled@test.com")
        # Disable the user
        user.is_active = False
        db_session.add(user)
        event_loop.run_until_complete(db_session.commit())

        with pytest.raises(ValueError, match="disabled"):
            event_loop.run_until_complete(
                AuthService.login(db=db_session, email="disabled@test.com",
                                  password="testpass123")
            )


class TestAuthServiceRefresh:
    """Tests for AuthService.refresh_access_token."""

    def test_refresh_returns_new_access_token(self, db_session, event_loop):
        """Valid refresh token should produce a new access token."""
        from auth.auth_service import AuthService
        _, _, refresh = event_loop.run_until_complete(
            AuthService.register(db=db_session, email="refresh@test.com",
                                 password="password123", full_name="Refresh")
        )
        result = event_loop.run_until_complete(
            AuthService.refresh_access_token(db=db_session, refresh_token=refresh)
        )
        # refresh_access_token returns (new_access_token, new_refresh_token) for token rotation
        new_access, new_refresh = result
        assert isinstance(new_access, str) and len(new_access) > 50
        assert isinstance(new_refresh, str) and len(new_refresh) > 50

    def test_refresh_with_access_token_raises(self, db_session, event_loop):
        """Using an access token for refresh should fail."""
        from auth.auth_service import AuthService
        _, access, _ = event_loop.run_until_complete(
            AuthService.register(db=db_session, email="badrefresh@test.com",
                                 password="password123", full_name="Bad")
        )
        with pytest.raises(ValueError, match="Not a refresh token"):
            event_loop.run_until_complete(
                AuthService.refresh_access_token(db=db_session, refresh_token=access)
            )


class TestAuthServicePasswordReset:
    """Tests for password reset flow."""

    def _create_user(self, db_session, event_loop, email="reset@test.com"):
        from auth.auth_service import AuthService
        return event_loop.run_until_complete(
            AuthService.register(db=db_session, email=email,
                                 password="oldpass123", full_name="Reset User")
        )

    def test_request_reset_returns_code(self, db_session, event_loop):
        """Reset request for existing user should return secure token (REC-307)."""
        from auth.auth_service import AuthService
        self._create_user(db_session, event_loop)
        code = event_loop.run_until_complete(
            AuthService.request_password_reset(db=db_session, email="reset@test.com")
        )
        assert code is not None
        # REC-307: Changed from 6-digit to 22-char alphanumeric token
        assert len(code) == 22  # secrets.token_urlsafe(16) produces 22 chars
        assert code.replace('-', '').replace('_', '').isalnum()  # URL-safe chars

    def test_request_reset_nonexistent_returns_none(self, db_session, event_loop):
        """Reset request for non-existent email should return None."""
        from auth.auth_service import AuthService
        code = event_loop.run_until_complete(
            AuthService.request_password_reset(db=db_session, email="nobody@test.com")
        )
        assert code is None

    def test_reset_password_success(self, db_session, event_loop):
        """Valid code + new password should reset and return tokens."""
        from auth.auth_service import AuthService
        self._create_user(db_session, event_loop, email="reset2@test.com")
        code = event_loop.run_until_complete(
            AuthService.request_password_reset(db=db_session, email="reset2@test.com")
        )
        user, access, refresh = event_loop.run_until_complete(
            AuthService.reset_password(
                db=db_session, email="reset2@test.com",
                code=code, new_password="newpass1234"
            )
        )
        assert user.email == "reset2@test.com"
        assert isinstance(access, str)

        # Should be able to login with new password
        user2, _, _ = event_loop.run_until_complete(
            AuthService.login(db=db_session, email="reset2@test.com", password="newpass1234")
        )
        assert user2.email == "reset2@test.com"

    def test_reset_password_wrong_code(self, db_session, event_loop):
        """Wrong reset code should raise ValueError."""
        from auth.auth_service import AuthService
        self._create_user(db_session, event_loop, email="wrongcode@test.com")
        event_loop.run_until_complete(
            AuthService.request_password_reset(db=db_session, email="wrongcode@test.com")
        )
        with pytest.raises(ValueError, match="Invalid"):
            event_loop.run_until_complete(
                AuthService.reset_password(
                    db=db_session, email="wrongcode@test.com",
                    code="000000", new_password="newpass1234"
                )
            )

    def test_reset_password_short_new_password(self, db_session, event_loop):
        """New password under 8 chars should raise ValueError."""
        from auth.auth_service import AuthService
        self._create_user(db_session, event_loop, email="shortpw@test.com")
        code = event_loop.run_until_complete(
            AuthService.request_password_reset(db=db_session, email="shortpw@test.com")
        )
        with pytest.raises(ValueError, match="at least 8"):
            event_loop.run_until_complete(
                AuthService.reset_password(
                    db=db_session, email="shortpw@test.com",
                    code=code, new_password="short"
                )
            )

    def test_reset_clears_code(self, db_session, event_loop):
        """After successful reset, code should be cleared (can't reuse)."""
        from auth.auth_service import AuthService
        self._create_user(db_session, event_loop, email="reuse@test.com")
        code = event_loop.run_until_complete(
            AuthService.request_password_reset(db=db_session, email="reuse@test.com")
        )
        # First reset succeeds
        event_loop.run_until_complete(
            AuthService.reset_password(
                db=db_session, email="reuse@test.com",
                code=code, new_password="newpass1234"
            )
        )
        # Second attempt with same code fails
        with pytest.raises(ValueError):
            event_loop.run_until_complete(
                AuthService.reset_password(
                    db=db_session, email="reuse@test.com",
                    code=code, new_password="anotherpass"
                )
            )
