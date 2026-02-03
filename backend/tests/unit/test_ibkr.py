"""
Tests for F6.3 IBKR Live Trading Integration

Tests connection, disconnection, mock order submission, status checks.
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from ibkr.ibkr_service import (
    IBKRService,
    IBKRConnectionState,
    IBKRConnection,
    IBKROrder,
    IBKRPosition,
)


# ========== Connection Tests ==========

class TestIBKRConnection:
    """Tests for IBKR connection management."""

    @pytest.fixture
    def service(self):
        """Create a fresh IBKR service."""
        return IBKRService()

    def test_initial_state_disconnected(self, service):
        """New users should start disconnected."""
        conn = service.get_connection("user1")
        assert conn.state == IBKRConnectionState.DISCONNECTED
        assert conn.account_id is None
        assert conn.is_paper is False

    def test_connect_with_mock_account(self, service):
        """Connection with default mock account should succeed."""
        conn = service.connect("user1")

        assert conn.state == IBKRConnectionState.CONNECTED
        assert conn.account_id == "DU1234567"
        assert conn.is_paper is True  # DU prefix = paper
        assert conn.connected_at is not None

    def test_connect_with_custom_account(self, service):
        """Connection with a custom account ID."""
        conn = service.connect("user1", account_id="U9876543")

        assert conn.state == IBKRConnectionState.CONNECTED
        assert conn.account_id == "U9876543"
        assert conn.is_paper is False  # U prefix = live

    def test_connect_paper_account_detection(self, service):
        """DU-prefixed accounts should be detected as paper."""
        conn = service.connect("user1", account_id="DU9999999")
        assert conn.is_paper is True

        conn2 = service.connect("user2", account_id="U1111111")
        assert conn2.is_paper is False

    def test_disconnect(self, service):
        """Disconnection should clear all state."""
        service.connect("user1")
        conn = service.disconnect("user1")

        assert conn.state == IBKRConnectionState.DISCONNECTED
        assert conn.account_id is None
        assert conn.is_paper is False
        assert conn.connected_at is None

    def test_disconnect_already_disconnected(self, service):
        """Disconnecting when already disconnected should not error."""
        conn = service.disconnect("user1")
        assert conn.state == IBKRConnectionState.DISCONNECTED

    def test_get_status(self, service):
        """Status should reflect current connection state."""
        status = service.get_status("user1")
        assert status.state == IBKRConnectionState.DISCONNECTED

        service.connect("user1")
        status = service.get_status("user1")
        assert status.state == IBKRConnectionState.CONNECTED

    def test_per_user_isolation(self, service):
        """Different users should have independent connection state."""
        service.connect("user1")
        service.connect("user2", account_id="U5555555")

        conn1 = service.get_connection("user1")
        conn2 = service.get_connection("user2")

        assert conn1.account_id == "DU1234567"
        assert conn2.account_id == "U5555555"
        assert conn1.is_paper is True
        assert conn2.is_paper is False

    def test_connection_to_dict(self, service):
        """Connection serialization should include all fields."""
        service.connect("user1")
        data = service.get_connection("user1").to_dict()

        assert "user_id" in data
        assert "account_id" in data
        assert "state" in data
        assert "is_paper" in data
        assert "connected_at" in data
        assert data["state"] == "connected"

    def test_reconnect_updates_state(self, service):
        """Reconnecting should update the connection state."""
        service.connect("user1", account_id="DU1111111")
        assert service.get_connection("user1").account_id == "DU1111111"

        service.connect("user1", account_id="U2222222")
        assert service.get_connection("user1").account_id == "U2222222"
        assert service.get_connection("user1").is_paper is False


# ========== Order Tests ==========

class TestIBKROrders:
    """Tests for IBKR order submission."""

    @pytest.fixture
    def service(self):
        """Create connected IBKR service."""
        svc = IBKRService()
        svc.connect("user1")
        return svc

    def test_submit_market_buy(self, service):
        """Market buy order should fill immediately."""
        order = service.submit_order(
            user_id="user1",
            ticker="AAPL",
            side="BUY",
            quantity=10,
        )

        assert order.order_id.startswith("IBKR-")
        assert order.ticker == "AAPL"
        assert order.side == "BUY"
        assert order.quantity == 10
        assert order.status == "FILLED"
        assert order.filled_price is not None
        assert order.filled_price > 0
        assert order.filled_at is not None

    def test_submit_market_sell(self, service):
        """Market sell order should fill immediately."""
        order = service.submit_order(
            user_id="user1",
            ticker="TSLA",
            side="SELL",
            quantity=5,
        )

        assert order.side == "SELL"
        assert order.status == "FILLED"

    def test_submit_limit_order(self, service):
        """Limit order should use specified price."""
        order = service.submit_order(
            user_id="user1",
            ticker="MSFT",
            side="BUY",
            quantity=20,
            order_type="LIMIT",
            limit_price=350.00,
        )

        assert order.order_type == "LIMIT"
        assert order.filled_price == 350.00

    def test_submit_order_not_connected(self):
        """Order submission when not connected should fail."""
        service = IBKRService()

        with pytest.raises(ValueError, match="IBKR not connected"):
            service.submit_order(
                user_id="user1",
                ticker="AAPL",
                side="BUY",
                quantity=10,
            )

    def test_submit_order_invalid_quantity(self, service):
        """Zero or negative quantity should fail."""
        with pytest.raises(ValueError, match="Quantity must be positive"):
            service.submit_order(
                user_id="user1",
                ticker="AAPL",
                side="BUY",
                quantity=0,
            )

        with pytest.raises(ValueError, match="Quantity must be positive"):
            service.submit_order(
                user_id="user1",
                ticker="AAPL",
                side="BUY",
                quantity=-5,
            )

    def test_submit_order_invalid_side(self, service):
        """Invalid side should fail."""
        with pytest.raises(ValueError, match="Invalid side"):
            service.submit_order(
                user_id="user1",
                ticker="AAPL",
                side="SHORT",
                quantity=10,
            )

    def test_submit_order_invalid_type(self, service):
        """Invalid order type should fail."""
        with pytest.raises(ValueError, match="Invalid order type"):
            service.submit_order(
                user_id="user1",
                ticker="AAPL",
                side="BUY",
                quantity=10,
                order_type="STOP",
            )

    def test_limit_order_requires_price(self, service):
        """Limit order without price should fail."""
        with pytest.raises(ValueError, match="Limit price required"):
            service.submit_order(
                user_id="user1",
                ticker="AAPL",
                side="BUY",
                quantity=10,
                order_type="LIMIT",
            )

    def test_order_is_paper(self, service):
        """Orders should reflect account paper/live status."""
        order = service.submit_order(
            user_id="user1",
            ticker="AAPL",
            side="BUY",
            quantity=10,
        )
        assert order.is_paper is True  # DU account

    def test_order_to_dict(self, service):
        """Order serialization should include all fields."""
        order = service.submit_order(
            user_id="user1",
            ticker="GOOG",
            side="BUY",
            quantity=3,
        )
        data = order.to_dict()

        assert "order_id" in data
        assert "ticker" in data
        assert "side" in data
        assert "quantity" in data
        assert "status" in data
        assert "filled_price" in data

    def test_ticker_uppercase(self, service):
        """Ticker should be uppercased."""
        order = service.submit_order(
            user_id="user1",
            ticker="aapl",
            side="BUY",
            quantity=1,
        )
        assert order.ticker == "AAPL"


# ========== Positions Tests ==========

class TestIBKRPositions:
    """Tests for IBKR positions retrieval."""

    @pytest.fixture
    def service(self):
        svc = IBKRService()
        svc.connect("user1")
        return svc

    def test_get_positions_empty(self, service):
        """Mock positions should return empty list."""
        positions = service.get_positions("user1")
        assert isinstance(positions, list)
        assert len(positions) == 0

    def test_get_positions_not_connected(self):
        """Getting positions when not connected should fail."""
        service = IBKRService()

        with pytest.raises(ValueError, match="IBKR not connected"):
            service.get_positions("user1")


# ========== Run Tests ==========

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
