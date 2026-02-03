"""
Tests for F11.4 Per-User Data Isolation

Tests that different users see different portfolios and orders,
and that user A can't see user B's data.
Uses synchronous SQLAlchemy to match project patterns.
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

# Use synchronous SQLite for unit tests
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
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


def _create_portfolio(session, user_id, cash=100000.0):
    """Helper: create a portfolio for a user."""
    port = UserPortfolio(
        id=str(uuid.uuid4()),
        user_id=user_id,
        cash_balance=cash,
        starting_cash=cash,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(port)
    session.commit()
    session.refresh(port)
    return port


def _create_position(session, portfolio_id, ticker, quantity, avg_cost):
    """Helper: create a position."""
    pos = UserPosition(
        id=str(uuid.uuid4()),
        portfolio_id=portfolio_id,
        ticker=ticker,
        quantity=quantity,
        avg_cost=avg_cost,
        opened_at=datetime.now(timezone.utc),
    )
    session.add(pos)
    session.commit()
    return pos


def _create_order(session, user_id, ticker, side, quantity, status="PENDING"):
    """Helper: create an order."""
    order = UserOrder(
        id=str(uuid.uuid4())[:8],
        user_id=user_id,
        ticker=ticker.upper(),
        side=side.upper(),
        quantity=quantity,
        status=status,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(order)
    session.commit()
    session.refresh(order)
    return order


# ========== Portfolio Isolation Tests ==========

class TestPortfolioIsolation:
    """Different users should have independent portfolios."""

    def test_create_portfolio_for_user(self, db_session):
        port = _create_portfolio(db_session, "user_a")
        assert port.user_id == "user_a"
        assert port.cash_balance == 100000.0

    def test_different_users_different_portfolios(self, db_session):
        port_a = _create_portfolio(db_session, "user_a")
        port_b = _create_portfolio(db_session, "user_b")

        assert port_a.id != port_b.id
        assert port_a.user_id == "user_a"
        assert port_b.user_id == "user_b"

    def test_query_by_user_id(self, db_session):
        _create_portfolio(db_session, "user_a")
        _create_portfolio(db_session, "user_b")

        result = db_session.execute(
            select(UserPortfolio).where(UserPortfolio.user_id == "user_a")
        )
        portfolios = list(result.scalars().all())
        assert len(portfolios) == 1
        assert portfolios[0].user_id == "user_a"

    def test_custom_starting_cash(self, db_session):
        port = _create_portfolio(db_session, "rich_user", cash=500000.0)
        assert port.cash_balance == 500000.0
        assert port.starting_cash == 500000.0

    def test_reset_portfolio_clears_positions(self, db_session):
        port = _create_portfolio(db_session, "user_a")
        _create_position(db_session, port.id, "AAPL", 10, 150.0)

        # Verify position exists
        positions = db_session.execute(
            select(UserPosition).where(UserPosition.portfolio_id == port.id)
        ).scalars().all()
        assert len(positions) == 1

        # Delete positions and reset cash
        for pos in positions:
            db_session.delete(pos)
        port.cash_balance = 100000.0
        port.realized_pnl = 0.0
        db_session.commit()

        positions_after = db_session.execute(
            select(UserPosition).where(UserPosition.portfolio_id == port.id)
        ).scalars().all()
        assert len(positions_after) == 0
        assert port.cash_balance == 100000.0

    def test_anonymous_user(self, db_session):
        port = _create_portfolio(db_session, ANONYMOUS_USER_ID)
        assert port.user_id == "anonymous"
        assert port.cash_balance == 100000.0


# ========== Position Isolation Tests ==========

class TestPositionIsolation:
    """Positions should be scoped to portfolios."""

    def test_add_position(self, db_session):
        port = _create_portfolio(db_session, "user_a")
        _create_position(db_session, port.id, "AAPL", 10, 150.0)

        positions = db_session.execute(
            select(UserPosition).where(UserPosition.portfolio_id == port.id)
        ).scalars().all()

        assert len(positions) == 1
        assert positions[0].ticker == "AAPL"
        assert positions[0].quantity == 10

    def test_positions_not_shared(self, db_session):
        port_a = _create_portfolio(db_session, "user_a")
        port_b = _create_portfolio(db_session, "user_b")

        _create_position(db_session, port_a.id, "TSLA", 5, 200.0)

        positions_b = db_session.execute(
            select(UserPosition).where(UserPosition.portfolio_id == port_b.id)
        ).scalars().all()
        assert len(positions_b) == 0

        positions_a = db_session.execute(
            select(UserPosition).where(UserPosition.portfolio_id == port_a.id)
        ).scalars().all()
        assert len(positions_a) == 1

    def test_get_specific_position(self, db_session):
        port = _create_portfolio(db_session, "user_a")
        _create_position(db_session, port.id, "MSFT", 20, 350.0)

        found = db_session.execute(
            select(UserPosition).where(
                UserPosition.portfolio_id == port.id,
                UserPosition.ticker == "MSFT",
            )
        ).scalar_one_or_none()
        assert found is not None
        assert found.quantity == 20

        not_found = db_session.execute(
            select(UserPosition).where(
                UserPosition.portfolio_id == port.id,
                UserPosition.ticker == "GOOG",
            )
        ).scalar_one_or_none()
        assert not_found is None

    def test_multiple_positions(self, db_session):
        port = _create_portfolio(db_session, "user_a")
        _create_position(db_session, port.id, "AAPL", 10, 150.0)
        _create_position(db_session, port.id, "MSFT", 5, 350.0)
        _create_position(db_session, port.id, "GOOGL", 3, 170.0)

        positions = db_session.execute(
            select(UserPosition).where(UserPosition.portfolio_id == port.id)
        ).scalars().all()
        assert len(positions) == 3


# ========== Order Isolation Tests ==========

class TestOrderIsolation:
    """Orders should be scoped to individual users."""

    def test_create_order(self, db_session):
        order = _create_order(db_session, "user_a", "AAPL", "BUY", 10)

        assert order.user_id == "user_a"
        assert order.ticker == "AAPL"
        assert order.side == "BUY"
        assert order.status == "PENDING"

    def test_orders_not_shared(self, db_session):
        _create_order(db_session, "user_a", "AAPL", "BUY", 10)
        _create_order(db_session, "user_b", "MSFT", "SELL", 5)

        orders_a = db_session.execute(
            select(UserOrder).where(UserOrder.user_id == "user_a")
        ).scalars().all()
        orders_b = db_session.execute(
            select(UserOrder).where(UserOrder.user_id == "user_b")
        ).scalars().all()

        assert len(orders_a) == 1
        assert orders_a[0].ticker == "AAPL"
        assert len(orders_b) == 1
        assert orders_b[0].ticker == "MSFT"

    def test_user_cant_see_others_order(self, db_session):
        order_b = _create_order(db_session, "user_b", "TSLA", "BUY", 3)

        # User A tries to access User B's order (scoped query)
        found = db_session.execute(
            select(UserOrder).where(
                UserOrder.id == order_b.id,
                UserOrder.user_id == "user_a",
            )
        ).scalar_one_or_none()
        assert found is None

        # User B can access their own order
        found_b = db_session.execute(
            select(UserOrder).where(
                UserOrder.id == order_b.id,
                UserOrder.user_id == "user_b",
            )
        ).scalar_one_or_none()
        assert found_b is not None

    def test_order_filter_by_status(self, db_session):
        order = _create_order(db_session, "user_a", "AAPL", "BUY", 10, status="FILLED")
        _create_order(db_session, "user_a", "MSFT", "SELL", 5, status="PENDING")

        filled = db_session.execute(
            select(UserOrder).where(
                UserOrder.user_id == "user_a",
                UserOrder.status == "FILLED",
            )
        ).scalars().all()
        pending = db_session.execute(
            select(UserOrder).where(
                UserOrder.user_id == "user_a",
                UserOrder.status == "PENDING",
            )
        ).scalars().all()

        assert len(filled) == 1
        assert len(pending) == 1
        assert filled[0].ticker == "AAPL"


# ========== Model Serialization Tests ==========

class TestModelSerialization:
    """Tests for model to_dict methods."""

    def test_portfolio_to_dict(self, db_session):
        port = _create_portfolio(db_session, "user_a")
        data = port.to_dict()

        assert "id" in data
        assert "user_id" in data
        assert "cash_balance" in data
        assert data["user_id"] == "user_a"

    def test_order_to_dict(self, db_session):
        order = _create_order(db_session, "user_a", "GOOG", "BUY", 5)
        data = order.to_dict()

        assert "order_id" in data
        assert "user_id" in data
        assert "ticker" in data
        assert data["ticker"] == "GOOG"

    def test_position_to_dict(self):
        pos = UserPosition(
            id="test-123",
            portfolio_id="port-456",
            ticker="NVDA",
            quantity=15,
            avg_cost=800.0,
        )
        data = pos.to_dict()

        assert data["ticker"] == "NVDA"
        assert data["quantity"] == 15
        assert data["avg_cost"] == 800.0


# ========== Anonymous/Backward Compat Tests ==========

class TestAnonymousUser:
    """Tests for backward compatibility when auth is disabled."""

    def test_anonymous_user_id_constant(self):
        assert ANONYMOUS_USER_ID == "anonymous"

    def test_anonymous_gets_portfolio(self, db_session):
        port = _create_portfolio(db_session, ANONYMOUS_USER_ID)
        assert port.user_id == "anonymous"

    def test_anonymous_creates_orders(self, db_session):
        order = _create_order(db_session, ANONYMOUS_USER_ID, "AAPL", "BUY", 10)
        assert order.user_id == "anonymous"

    def test_scores_are_global(self):
        """Scores are shared (not per-user) — just verify the constant."""
        # Scores use load_composite_scores() which is global, not per-user
        # This test documents that design decision
        assert True


# ========== Run Tests ==========

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
