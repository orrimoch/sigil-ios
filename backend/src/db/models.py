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
    # REC-220: High-Water-Mark Tracking for trailing stop-loss
    high_water_mark = Column(Float, nullable=True)  # Highest price since position opened

    portfolio = relationship("UserPortfolio", back_populates="positions")

    def to_dict(self):
        return {
            "id": self.id,
            "portfolio_id": self.portfolio_id,
            "ticker": self.ticker,
            "quantity": self.quantity,
            "shares": self.quantity,  # BUG-010: iOS expects "shares"
            "avg_cost": self.avg_cost,
            "cost_basis": round(self.quantity * self.avg_cost, 2),  # BUG-010: iOS expects this
            "opened_at": self.opened_at.isoformat() if self.opened_at else None,
            "high_water_mark": self.high_water_mark,  # REC-220
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


class PortfolioSnapshot(Base):
    """Daily portfolio value snapshot for fast history retrieval."""
    __tablename__ = "portfolio_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), nullable=False, index=True)
    portfolio_id = Column(String(36), nullable=False)
    date = Column(String(10), nullable=False)  # YYYY-MM-DD
    total_value = Column(Float, nullable=False)
    cash = Column(Float, nullable=False)
    positions_value = Column(Float, nullable=False)
    total_pnl = Column(Float, nullable=False)
    total_pnl_percent = Column(Float, nullable=False)
    created_at = Column(String(30), nullable=False, default=lambda: datetime.now(timezone.utc).isoformat())

    __table_args__ = (
        # Unique constraint on portfolio_id + date
        {"sqlite_autoincrement": True},
    )


# Default anonymous user ID for when auth is disabled
ANONYMOUS_USER_ID = "anonymous"
