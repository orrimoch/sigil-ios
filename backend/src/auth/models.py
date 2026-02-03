"""
Sigil Auth — User SQLAlchemy model.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, DateTime, Text
from .database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    ibkr_account_id = Column(String(255), nullable=True)
    settings_json = Column(Text, nullable=True)
    reset_code = Column(String(6), nullable=True)
    reset_code_expires = Column(DateTime(timezone=True), nullable=True)

    def to_dict(self):
        """Return a JSON-safe dict (excludes password_hash)."""
        return {
            "id": self.id,
            "email": self.email,
            "full_name": self.full_name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "is_active": self.is_active,
            "ibkr_account_id": self.ibkr_account_id,
            "settings_json": self.settings_json,
        }
