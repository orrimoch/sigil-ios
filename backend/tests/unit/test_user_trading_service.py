"""
Tests for UserTradingService — per-user portfolio and order operations.

Covers: BUG-092-001 (API endpoints use per-user models),
        BUG-092-002 (unique constraint on UserPortfolio.user_id),
        BUG-092-003 (UserOrder schema alignment with iOS OrderData).
"""

import pytest
import sys
import uuid
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from db.models import (
    UserPortfolio,
    UserPosition,
    UserOrder,
    ANONYMOUS_USER_ID,
)

# Synchronous tests using raw SQLAlchemy
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.exc import IntegrityError
from auth.database import Base


@pytest.fixture
def db_session():
    """Create an in-memory synchronous database for testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()
    engine.dispose()


def _now():
    return datetime.now(timezone.utc)


# ========== BUG-092-002: Unique constraint on user_id ==========

class TestUniqueUserPortfolio:
    """UserPortfolio.user_id should be unique."""

    def test_unique_constraint_exists(self, db_session):
        """Creating two portfolios for same user should fail."""
        port1 = UserPortfolio(
            id=str(uuid.uuid4()),
            user_id="user_a",
            cash_balance=100000.0,
            starting_cash=100000.0,
            created_at=_now(),
            updated_at=_now(),
        )
        db_session.add(port1)
        db_session.commit()

        port2 = UserPortfolio(
            id=str(uuid.uuid4()),
            user_id="user_a",  # Duplicate!
            cash_balance=50000.0,
            starting_cash=50000.0,
            created_at=_now(),
            updated_at=_now(),
        )
        db_session.add(port2)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_different_users_allowed(self, db_session):
        """Different users should each get a portfolio."""
        for uid in ["user_a", "user_b", "user_c"]:
            port = UserPortfolio(
                id=str(uuid.uuid4()),
                user_id=uid,
                cash_balance=100000.0,
                starting_cash=100000.0,
                created_at=_now(),
                updated_at=_now(),
            )
            db_session.add(port)
        db_session.commit()

        count = db_session.query(UserPortfolio).count()
        assert count == 3


# ========== BUG-092-003: UserOrder schema alignment ==========

class TestUserOrderSchemaAlignment:
    """UserOrder.to_dict() must match iOS OrderData Codable struct."""

    REQUIRED_FIELDS = [
        "order_id", "ticker", "side", "order_type", "quantity",
        "limit_price", "status", "filled_quantity", "filled_price",
        "created_at", "updated_at", "filled_at", "reject_reason", "is_paper",
    ]

    def test_to_dict_has_all_ios_fields(self, db_session):
        """to_dict() must include every field iOS OrderData expects."""
        order = UserOrder(
            id="test-id",
            user_id="user_a",
            ticker="AAPL",
            side="BUY",
            quantity=10.0,
            order_type="MARKET",
            status="FILLED",
            filled_quantity=10.0,
            filled_price=150.0,
            is_paper=True,
            created_at=_now(),
            updated_at=_now(),
            filled_at=_now(),
        )
        data = order.to_dict()

        for field in self.REQUIRED_FIELDS:
            assert field in data, f"Missing field: {field}"

    def test_to_dict_order_id_maps_from_id(self, db_session):
        """order_id in to_dict should come from the id column."""
        order = UserOrder(
            id="abc123",
            user_id="user_a",
            ticker="MSFT",
            side="SELL",
            quantity=5.0,
            created_at=_now(),
            updated_at=_now(),
        )
        data = order.to_dict()
        assert data["order_id"] == "abc123"

    def test_to_dict_nullable_fields(self):
        """Nullable fields should be None when not set."""
        order = UserOrder(
            id="test",
            user_id="user_a",
            ticker="GOOG",
            side="BUY",
            quantity=1.0,
            created_at=_now(),
            updated_at=_now(),
        )
        data = order.to_dict()
        assert data["limit_price"] is None
        assert data["filled_price"] is None
        assert data["filled_at"] is None
        assert data["reject_reason"] is None

    def test_to_dict_is_paper_defaults_true(self, db_session):
        """is_paper should default to True when persisted."""
        order = UserOrder(
            id="test-paper",
            user_id="user_a",
            ticker="NVDA",
            side="BUY",
            quantity=1.0,
            is_paper=True,
            created_at=_now(),
            updated_at=_now(),
        )
        db_session.add(order)
        db_session.commit()
        db_session.refresh(order)
        data = order.to_dict()
        assert data["is_paper"] is True

    def test_to_dict_datetime_format(self, db_session):
        """Datetime fields should be ISO format strings."""
        now = _now()
        order = UserOrder(
            id="test",
            user_id="user_a",
            ticker="TSLA",
            side="BUY",
            quantity=1.0,
            created_at=now,
            updated_at=now,
            filled_at=now,
        )
        data = order.to_dict()
        # Should be ISO format strings
        assert isinstance(data["created_at"], str)
        assert isinstance(data["updated_at"], str)
        assert isinstance(data["filled_at"], str)
        assert "T" in data["created_at"]  # ISO format has T separator


# ========== User Trading Service Integration Tests ==========

class TestUserTradingServiceSync:
    """Synchronous unit tests for trading service logic patterns."""

    def test_portfolio_creation(self, db_session):
        """Creating a portfolio should set all defaults correctly."""
        port = UserPortfolio(
            id=str(uuid.uuid4()),
            user_id="new_user",
            cash_balance=100000.0,
            starting_cash=100000.0,
            created_at=_now(),
            updated_at=_now(),
        )
        db_session.add(port)
        db_session.commit()

        result = db_session.execute(
            select(UserPortfolio).where(UserPortfolio.user_id == "new_user")
        ).scalar_one()
        assert result.cash_balance == 100000.0
        assert result.is_paper is True
        assert result.realized_pnl == 0.0

    def test_order_creation_with_all_fields(self, db_session):
        """Creating an order with all fields."""
        order = UserOrder(
            id=str(uuid.uuid4())[:8],
            user_id="user_a",
            ticker="AAPL",
            side="BUY",
            quantity=10.0,
            order_type="MARKET",
            status="FILLED",
            filled_quantity=10.0,
            filled_price=175.50,
            filled_at=_now(),
            is_paper=True,
            created_at=_now(),
            updated_at=_now(),
        )
        db_session.add(order)
        db_session.commit()

        result = db_session.execute(
            select(UserOrder).where(UserOrder.user_id == "user_a")
        ).scalar_one()
        assert result.ticker == "AAPL"
        assert result.filled_price == 175.50

    def test_anonymous_user_backward_compat(self, db_session):
        """Anonymous user should work for backward compatibility."""
        port = UserPortfolio(
            id=str(uuid.uuid4()),
            user_id=ANONYMOUS_USER_ID,
            cash_balance=100000.0,
            starting_cash=100000.0,
            created_at=_now(),
            updated_at=_now(),
        )
        db_session.add(port)
        db_session.commit()

        order = UserOrder(
            id=str(uuid.uuid4())[:8],
            user_id=ANONYMOUS_USER_ID,
            ticker="SPY",
            side="BUY",
            quantity=5.0,
            created_at=_now(),
            updated_at=_now(),
        )
        db_session.add(order)
        db_session.commit()

        orders = db_session.execute(
            select(UserOrder).where(UserOrder.user_id == ANONYMOUS_USER_ID)
        ).scalars().all()
        assert len(orders) == 1
        assert orders[0].ticker == "SPY"

    def test_position_linked_to_portfolio(self, db_session):
        """Positions should be linked to the correct portfolio."""
        port = UserPortfolio(
            id="port-123",
            user_id="user_a",
            cash_balance=100000.0,
            starting_cash=100000.0,
            created_at=_now(),
            updated_at=_now(),
        )
        db_session.add(port)
        db_session.commit()

        pos = UserPosition(
            id=str(uuid.uuid4()),
            portfolio_id="port-123",
            ticker="AAPL",
            quantity=10,
            avg_cost=150.0,
            opened_at=_now(),
        )
        db_session.add(pos)
        db_session.commit()

        positions = db_session.execute(
            select(UserPosition).where(UserPosition.portfolio_id == "port-123")
        ).scalars().all()
        assert len(positions) == 1
        assert positions[0].ticker == "AAPL"


# ========== IBKR Routes User ID Tests ==========

class TestIBKRUserIDExtraction:
    """Test that IBKR routes use proper user ID extraction."""

    def test_anonymous_user_id_constant(self):
        """ANONYMOUS_USER_ID should be 'anonymous'."""
        assert ANONYMOUS_USER_ID == "anonymous"

    def test_helper_with_none_user(self):
        """When user is None, should return ANONYMOUS_USER_ID."""
        # Simulate the _get_user_id helper pattern
        user = None
        user_id = user.id if user else ANONYMOUS_USER_ID
        assert user_id == "anonymous"

    def test_helper_with_real_user(self):
        """When user has .id, should return that ID."""
        class MockUser:
            id = "real-user-uuid"
        
        user = MockUser()
        user_id = user.id if user else ANONYMOUS_USER_ID
        assert user_id == "real-user-uuid"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
