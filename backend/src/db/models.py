"""
F11.4 Per-User Data Isolation — SQLAlchemy models for portfolio, positions, and orders.

Replaces flat JSON files with per-user SQLite tables.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship

from auth.database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class UserPortfolio(Base):
    """Per-user portfolio with cash balance."""
    __tablename__ = "portfolios"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), nullable=False, unique=True, index=True)
    cash_balance = Column(Float, default=100000.0, nullable=False)
    starting_cash = Column(Float, default=100000.0, nullable=False)
    realized_pnl = Column(Float, default=0.0, nullable=False)
    is_paper = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False)

    positions = relationship("UserPosition", back_populates="portfolio", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "cash_balance": self.cash_balance,
            "starting_cash": self.starting_cash,
            "realized_pnl": self.realized_pnl,
            "is_paper": self.is_paper,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class UserPosition(Base):
    """A position within a user's portfolio."""
    __tablename__ = "positions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    portfolio_id = Column(String(36), ForeignKey("portfolios.id"), nullable=False, index=True)
    ticker = Column(String(10), nullable=False)
    quantity = Column(Float, nullable=False, default=0.0)
    avg_cost = Column(Float, nullable=False, default=0.0)
    opened_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    portfolio = relationship("UserPortfolio", back_populates="positions")

    def to_dict(self):
        return {
            "id": self.id,
            "portfolio_id": self.portfolio_id,
            "ticker": self.ticker,
            "quantity": self.quantity,
            "avg_cost": self.avg_cost,
            "opened_at": self.opened_at.isoformat() if self.opened_at else None,
        }


class UserOrder(Base):
    """A trading order belonging to a user."""
    __tablename__ = "user_orders"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), nullable=False, index=True)
    ticker = Column(String(10), nullable=False)
    side = Column(String(4), nullable=False)  # BUY or SELL
    quantity = Column(Float, nullable=False)
    order_type = Column(String(10), nullable=False, default="MARKET")
    limit_price = Column(Float, nullable=True)
    status = Column(String(20), nullable=False, default="PENDING")
    filled_quantity = Column(Float, default=0.0, nullable=False)
    filled_price = Column(Float, nullable=True)
    reject_reason = Column(Text, nullable=True)
    is_paper = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False)
    filled_at = Column(DateTime(timezone=True), nullable=True)

    def to_dict(self):
        return {
            "order_id": self.id,
            "user_id": self.user_id,
            "ticker": self.ticker,
            "side": self.side,
            "order_type": self.order_type,
            "quantity": self.quantity,
            "limit_price": self.limit_price,
            "status": self.status,
            "filled_quantity": self.filled_quantity,
            "filled_price": self.filled_price,
            "reject_reason": self.reject_reason,
            "is_paper": self.is_paper,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "filled_at": self.filled_at.isoformat() if self.filled_at else None,
        }


# Default anonymous user ID for when auth is disabled
ANONYMOUS_USER_ID = "anonymous"
