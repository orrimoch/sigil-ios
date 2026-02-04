"""
Tests for F6.3 IBKR Live Trading Integration

Tests connection, disconnection, order submission, status checks.
All IB Gateway interactions are mocked so tests run without a live Gateway.
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from ibkr.ibkr_service import (
    IBKRService,
    IBKRConnectionState,
    IBKRConnection,
    IBKROrder,
    IBKRPosition,
    _IBConnection,
)


# ── Helpers ─────────────────────────────────────────────────────────────

def _make_mock_ib(managed_accounts=None):
    """Create a mock ib_insync.IB() instance."""
    mock_ib = MagicMock()
    mock_ib.isConnected.return_value = True
    mock_ib.managedAccounts.return_value = managed_accounts or ["DUP526287"]
    mock_ib.connect.return_value = None
    mock_ib.disconnect.return_value = None
    mock_ib.sleep.return_value = None
    mock_ib.positions.return_value = []
    mock_ib.portfolio.return_value = []
    return mock_ib


def _mock_ib_insync_module():
    """Create a mock ib_insync module."""
    mock_mod = MagicMock()
    mock_mod.Stock.return_value = MagicMock(symbol="AAPL")
    mock_mod.MarketOrder.return_value = MagicMock()
    mock_mod.LimitOrder.return_value = MagicMock()
    return mock_mod


def _patch_ibc_connect(service, user_id, mock_ib, account_id="DUP526287"):
    """Wire a mock _IBConnection into the service."""
    ibc = MagicMock(spec=_IBConnection)
    ibc.is_connected = True
    ibc.ib = mock_ib
    ibc.connect.return_value = mock_ib.managedAccounts()
    ibc._import_ib_insync = _mock_ib_insync_module
    ibc.run_ib = lambda func: func(mock_ib)

    service._ib_connections[user_id] = ibc
    conn = service.get_connection(user_id)
    conn.state = IBKRConnectionState.CONNECTED
    conn.account_id = account_id
    conn.is_paper = account_id.startswith("DU")
    conn.connected_at = datetime.now().isoformat()
    return ibc


def _make_filled_trade():
    """Create a mock trade that fills immediately."""
    mock_order_status = MagicMock()
    mock_order_status.status = "Filled"
    mock_order_status.avgFillPrice = 185.50

    mock_order_obj = MagicMock()
    mock_order_obj.orderId = 42

    mock_fill = MagicMock()
    mock_fill.time = datetime(2026, 1, 15, 10, 30, 0)

    mock_trade = MagicMock()
    mock_trade.orderStatus = mock_order_status
    mock_trade.order = mock_order_obj
    mock_trade.fills = [mock_fill]
    return mock_trade


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

    @patch.object(_IBConnection, "connect", return_value=["DUP526287"])
    def test_connect_with_default_account(self, mock_connect, service):
        """Connection with default account should succeed."""
        conn = service.connect("user1")

        assert conn.state == IBKRConnectionState.CONNECTED
        assert conn.account_id == "DUP526287"
        assert conn.is_paper is True  # DU prefix = paper
        assert conn.connected_at is not None

    @patch.object(_IBConnection, "connect", return_value=["U9876543"])
    def test_connect_with_custom_account(self, mock_connect):
        """Connection with a custom account ID."""
        svc = IBKRService(default_account="U9876543")
        conn = svc.connect("user1", account_id="U9876543")

        assert conn.state == IBKRConnectionState.CONNECTED
        assert conn.account_id == "U9876543"
        assert conn.is_paper is False  # U prefix = live

    @patch.object(_IBConnection, "connect", return_value=["DU9999999"])
    def test_connect_paper_account_detection(self, mock_connect):
        """DU-prefixed accounts should be detected as paper."""
        svc = IBKRService(default_account="DU9999999")
        conn = svc.connect("user1", account_id="DU9999999")
        assert conn.is_paper is True

    @patch.object(_IBConnection, "connect", return_value=["U1111111"])
    def test_connect_live_account_detection(self, mock_connect):
        svc = IBKRService(default_account="U1111111")
        conn = svc.connect("user1", account_id="U1111111")
        assert conn.is_paper is False

    def test_disconnect(self, service):
        """Disconnection should clear all state."""
        mock_ib = _make_mock_ib()
        _patch_ibc_connect(service, "user1", mock_ib)
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

        mock_ib = _make_mock_ib()
        _patch_ibc_connect(service, "user1", mock_ib)
        status = service.get_status("user1")
        assert status.state == IBKRConnectionState.CONNECTED

    @patch.object(_IBConnection, "connect", return_value=["DUP526287"])
    def test_per_user_isolation(self, mock_connect, service):
        """Different users should have independent connection state."""
        service.connect("user1")

        conn1 = service.get_connection("user1")
        conn2 = service.get_connection("user2")

        assert conn1.state == IBKRConnectionState.CONNECTED
        assert conn2.state == IBKRConnectionState.DISCONNECTED

    def test_connection_to_dict(self, service):
        """Connection serialization should include all fields."""
        mock_ib = _make_mock_ib()
        _patch_ibc_connect(service, "user1", mock_ib)
        data = service.get_connection("user1").to_dict()

        assert "user_id" in data
        assert "account_id" in data
        assert "state" in data
        assert "is_paper" in data
        assert "connected_at" in data
        assert data["state"] == "connected"

    @patch.object(_IBConnection, "connect", return_value=["DUP526287"])
    def test_reconnect_updates_state(self, mock_connect, service):
        """Reconnecting should update the connection state."""
        service.connect("user1")
        assert service.get_connection("user1").account_id == "DUP526287"


# ========== Order Tests ==========

class TestIBKROrders:
    """Tests for IBKR order submission."""

    @pytest.fixture
    def service(self):
        """Create connected IBKR service with mock trades."""
        svc = IBKRService()
        mock_ib = _make_mock_ib()
        mock_ib.placeOrder.return_value = _make_filled_trade()
        _patch_ibc_connect(svc, "user1", mock_ib)
        return svc

    def test_submit_market_buy(self, service):
        """Market buy order should fill."""
        with patch.object(_IBConnection, "_import_ib_insync", return_value=_mock_ib_insync_module()):
            order = service.submit_order(
                user_id="user1",
                ticker="AAPL",
                side="BUY",
                quantity=10,
            )

        assert order.order_id == "42"
        assert order.ticker == "AAPL"
        assert order.side == "BUY"
        assert order.quantity == 10
        assert order.status == "FILLED"
        assert order.filled_price is not None
        assert order.filled_price > 0
        assert order.filled_at is not None

    def test_submit_market_sell(self, service):
        """Market sell order should fill."""
        with patch.object(_IBConnection, "_import_ib_insync", return_value=_mock_ib_insync_module()):
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
        with patch.object(_IBConnection, "_import_ib_insync", return_value=_mock_ib_insync_module()):
            order = service.submit_order(
                user_id="user1",
                ticker="MSFT",
                side="BUY",
                quantity=20,
                order_type="LIMIT",
                limit_price=350.00,
            )

        assert order.order_type == "LIMIT"

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
            service.submit_order("user1", "AAPL", "BUY", 0)

        with pytest.raises(ValueError, match="Quantity must be positive"):
            service.submit_order("user1", "AAPL", "BUY", -5)

    def test_submit_order_invalid_side(self, service):
        """Invalid side should fail."""
        with pytest.raises(ValueError, match="Invalid side"):
            service.submit_order("user1", "AAPL", "SHORT", 10)

    def test_submit_order_invalid_type(self, service):
        """Invalid order type should fail."""
        with pytest.raises(ValueError, match="Invalid order type"):
            service.submit_order("user1", "AAPL", "BUY", 10, order_type="STOP")

    def test_limit_order_requires_price(self, service):
        """Limit order without price should fail."""
        with pytest.raises(ValueError, match="Limit price required"):
            service.submit_order("user1", "AAPL", "BUY", 10, order_type="LIMIT")

    def test_order_is_paper(self, service):
        """Orders should reflect account paper/live status."""
        with patch.object(_IBConnection, "_import_ib_insync", return_value=_mock_ib_insync_module()):
            order = service.submit_order("user1", "AAPL", "BUY", 10)
        assert order.is_paper is True  # DU account

    def test_order_to_dict(self, service):
        """Order serialization should include all fields."""
        with patch.object(_IBConnection, "_import_ib_insync", return_value=_mock_ib_insync_module()):
            order = service.submit_order("user1", "GOOG", "BUY", 3)
        data = order.to_dict()

        assert "order_id" in data
        assert "ticker" in data
        assert "side" in data
        assert "quantity" in data
        assert "status" in data
        assert "filled_price" in data

    def test_ticker_uppercase(self, service):
        """Ticker should be uppercased."""
        with patch.object(_IBConnection, "_import_ib_insync", return_value=_mock_ib_insync_module()):
            order = service.submit_order("user1", "aapl", "BUY", 1)
        assert order.ticker == "AAPL"


# ========== Positions Tests ==========

class TestIBKRPositions:
    """Tests for IBKR positions retrieval."""

    @pytest.fixture
    def service(self):
        svc = IBKRService()
        mock_ib = _make_mock_ib()
        _patch_ibc_connect(svc, "user1", mock_ib)
        return svc

    def test_get_positions_empty(self, service):
        """Empty positions should return empty list."""
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
