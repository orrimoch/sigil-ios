"""
Sigil Auth Package — User authentication and authorization.
"""

from .routes import auth_router
from .middleware import get_current_user, get_optional_user, get_required_user
from .auth_service import AuthService
from .database import init_db, get_db_session

__all__ = [
    "auth_router",
    "get_current_user",
    "get_optional_user",
    "get_required_user",
    "AuthService",
    "init_db",
    "get_db_session",
]
