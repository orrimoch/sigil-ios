"""
Tests for F6.3 IBKR Service — real ib_insync integration (mocked IB Gateway).

Tests connection state management, order creation, position retrieval,
account summary, disconnection cleanup, and error handling.
All IB Gateway interactions are mocked.
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock
from dataclasses import dataclass
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


# ═══════════════════════════════════════════════════════════════════════
# Helpers / Fixtures
# ═══════════════════════════════════════════════════════════════════════

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
    mock_ib.accountSummary.return_value = []
    return mock_ib


def _mock_ib_insync_module():
    """Create a mock ib_insync module."""
    mock_mod = MagicMock()
    mock_mod.Stock.return_value = MagicMock(symbol="AAPL")
    mock_mod.MarketOrder.return_value = MagicMock()
    mock_mod.LimitOrder.return_value = MagicMock()
    return mock_mod


def _make_mock_order_status(status="Filled", avg_price=185.50, filled=10, remaining=0):
    """Create a properly mocked OrderStatus with all required numeric attributes."""
    mock_status = MagicMock()
    mock_status.status = status
    mock_status.avgFillPrice = avg_price
    mock_status.filled = filled  # Must be int, not MagicMock
    mock_status.remaining = remaining  # Must be int, not MagicMock
    return mock_status


def _patch_ibc_connect(service, user_id, mock_ib, account_id="DUP526287"):
    """
    Manually wire a mock _IBConnection into the service to simulate
    a successful connection without hitting a real IB Gateway.
    """
    ibc = MagicMock(spec=_IBConnection)
    ibc.is_connected = True
    ibc.ib = mock_ib
    ibc.connect.return_value = mock_ib.managedAccounts()
    ibc._import_ib_insync = _mock_ib_insync_module
    # run_ib dispatches func(ib) — mock it to call directly with mock_ib
    ibc.run_ib = lambda func: func(mock_ib)

    service._ib_connections[user_id] = ibc
    conn = service.get_connection(user_id)
    conn.state = IBKRConnectionState.CONNECTED
    conn.account_id = account_id
    conn.is_paper = account_id.startswith("DU")
    conn.connected_at = datetime.now().isoformat()
    return ibc


# ═══════════════════════════════════════════════════════════════════════
# Connection Tests
# ═══════════════════════════════════════════════════════════════════════

class TestIBKRConnection:
    """Tests for IBKR connection state management."""

    @pytest.fixture
    def service(self):
        return IBKRService(host="127.0.0.1", port=4002, default_account="DUP526287")

    def test_initial_state_disconnected(self, service):
        """New users should start disconnected."""
        conn = service.get_connection("user1")
        assert conn.state == IBKRConnectionState.DISCONNECTED
        assert conn.account_id is None
        assert conn.is_paper is False

    @patch("ibkr.ibkr_service._IBConnection.connect", return_value=["DUP526287"])
    def test_connect_success(self, mock_connect, service):
        """Successful connection sets state to CONNECTED."""
        conn = service.connect("user1", account_id="DUP526287")

        assert conn.state == IBKRConnectionState.CONNECTED
        assert conn.account_id == "DUP526287"
        assert conn.is_paper is True
        assert conn.connected_at is not None
        assert conn.error_message is None

    @patch("ibkr.ibkr_service._IBConnection.connect", return_value=["DUP526287"])
    def test_connect_default_account(self, mock_connect, service):
        """Connection without explicit account uses default."""
        conn = service.connect("user1")

        assert conn.state == IBKRConnectionState.CONNECTED
        assert conn.account_id == "DUP526287"

    @patch("ibkr.ibkr_service._IBConnection.connect", return_value=["DUP526287"])
    def test_connect_wrong_account(self, mock_connect, service):
        """Connection with non-existent account should fail."""
        conn = service.connect("user1", account_id="NONEXISTENT")

        assert conn.state == IBKRConnectionState.ERROR
        assert "not found" in conn.error_message

    @patch(
        "ibkr.ibkr_service._IBConnection.connect",
        side_effect=ConnectionError("IB Gateway connection failed: Connection refused"),
    )
    def test_connect_gateway_down(self, mock_connect, service):
        """Connection when Gateway is down returns ERROR state (doesn't crash)."""
        conn = service.connect("user1")

        assert conn.state == IBKRConnectionState.ERROR
        assert "Connection refused" in conn.error_message

    @patch("ibkr.ibkr_service._IBConnection.connect", return_value=["DUP526287"])
    def test_connect_paper_detection(self, mock_connect, service):
        """DU-prefixed accounts detected as paper."""
        conn = service.connect("user1", account_id="DUP526287")
        assert conn.is_paper is True

    @patch("ibkr.ibkr_service._IBConnection.connect", return_value=["U1234567"])
    def test_connect_live_detection(self, mock_connect):
        """Non-DU accounts detected as live."""
        svc = IBKRService(default_account="U1234567")
        conn = svc.connect("user1", account_id="U1234567")
        assert conn.is_paper is False

    def test_disconnect(self, service):
        """Disconnection clears all state."""
        mock_ib = _make_mock_ib()
        _patch_ibc_connect(service, "user1", mock_ib)

        conn = service.disconnect("user1")

        assert conn.state == IBKRConnectionState.DISCONNECTED
        assert conn.account_id is None
        assert conn.is_paper is False
        assert conn.connected_at is None
        assert "user1" not in service._ib_connections

    def test_disconnect_already_disconnected(self, service):
        """Disconnecting when already disconnected should not error."""
        conn = service.disconnect("user1")
        assert conn.state == IBKRConnectionState.DISCONNECTED

    def test_get_status_connected(self, service):
        """Status reflects live connection state."""
        mock_ib = _make_mock_ib()
        ibc = _patch_ibc_connect(service, "user1", mock_ib)

        status = service.get_status("user1")
        assert status.state == IBKRConnectionState.CONNECTED

    def test_get_status_connection_lost(self, service):
        """Status detects when IB connection is lost."""
        mock_ib = _make_mock_ib()
        ibc = _patch_ibc_connect(service, "user1", mock_ib)

        # Simulate connection drop
        ibc.is_connected = False

        status = service.get_status("user1")
        assert status.state == IBKRConnectionState.DISCONNECTED
        assert status.error_message == "Connection lost"

    @patch("ibkr.ibkr_service._IBConnection.connect", return_value=["DUP526287"])
    def test_reconnect_disconnects_old(self, mock_connect, service):
        """Reconnecting should disconnect the old connection first."""
        mock_ib = _make_mock_ib()
        old_ibc = _patch_ibc_connect(service, "user1", mock_ib)

        conn = service.connect("user1")
        assert conn.state == IBKRConnectionState.CONNECTED
        old_ibc.disconnect.assert_called_once()

    @patch("ibkr.ibkr_service._IBConnection.connect", return_value=["DUP526287"])
    def test_per_user_isolation(self, mock_connect, service):
        """Different users have independent connections."""
        service.connect("user1")
        conn2 = service.get_connection("user2")

        assert service.get_connection("user1").state == IBKRConnectionState.CONNECTED
        assert conn2.state == IBKRConnectionState.DISCONNECTED

    def test_connection_to_dict(self, service):
        """Connection serialization includes all fields."""
        mock_ib = _make_mock_ib()
        _patch_ibc_connect(service, "user1", mock_ib)

        data = service.get_connection("user1").to_dict()

        assert data["user_id"] == "user1"
        assert data["account_id"] == "DUP526287"
        assert data["state"] == "connected"
        assert data["is_paper"] is True
        assert "connected_at" in data


# ═══════════════════════════════════════════════════════════════════════
# Order Tests
# ═══════════════════════════════════════════════════════════════════════

class TestIBKROrders:
    """Tests for IBKR order submission."""

    @pytest.fixture
    def service(self):
        svc = IBKRService()
        mock_ib = _make_mock_ib()

        # Set up a mock trade response
        mock_order_status = _make_mock_order_status(status="Filled", avg_price=185.50, filled=10, remaining=0)

        mock_order_obj = MagicMock()
        mock_order_obj.orderId = 42

        mock_fill = MagicMock()
        mock_fill.time = datetime(2026, 1, 15, 10, 30, 0)

        mock_trade = MagicMock()
        mock_trade.orderStatus = mock_order_status
        mock_trade.order = mock_order_obj
        mock_trade.fills = [mock_fill]

        mock_ib.placeOrder.return_value = mock_trade

        ibc = _patch_ibc_connect(svc, "user1", mock_ib)
        # Make _import_ib_insync return a proper mock module
        ibc._import_ib_insync = staticmethod(_mock_ib_insync_module)

        svc._mock_ib = mock_ib  # stash for assertions
        return svc

    def test_submit_market_buy(self, service):
        """Market buy should place order and return fill data."""
        with patch("ibkr.ibkr_service._IBConnection._import_ib_insync", return_value=_mock_ib_insync_module()):
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
        assert order.order_type == "MARKET"
        assert order.status == "FILLED"
        assert order.filled_price == 185.50
        assert order.filled_at is not None
        assert order.is_paper is True

    def test_submit_market_sell(self, service):
        """Market sell should work."""
        with patch("ibkr.ibkr_service._IBConnection._import_ib_insync", return_value=_mock_ib_insync_module()):
            order = service.submit_order(
                user_id="user1",
                ticker="TSLA",
                side="SELL",
                quantity=5,
            )

        assert order.side == "SELL"
        assert order.status == "FILLED"

    def test_submit_limit_order(self, service):
        """Limit order should use LimitOrder."""
        mock_mod = _mock_ib_insync_module()
        with patch("ibkr.ibkr_service._IBConnection._import_ib_insync", return_value=mock_mod):
            order = service.submit_order(
                user_id="user1",
                ticker="MSFT",
                side="BUY",
                quantity=20,
                order_type="LIMIT",
                limit_price=350.00,
            )

        assert order.order_type == "LIMIT"
        mock_mod.LimitOrder.assert_called_once_with("BUY", 20, 350.00)

    def test_submit_order_not_connected(self):
        """Order when not connected should fail."""
        svc = IBKRService()
        with pytest.raises(ValueError, match="IBKR not connected"):
            svc.submit_order("user1", "AAPL", "BUY", 10)

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
            service.submit_order("user1", "AAPL", "BUY", 10, order_type="FOOBAR")

    def test_limit_order_requires_price(self, service):
        """Limit order without price should fail."""
        with pytest.raises(ValueError, match="Limit price required"):
            service.submit_order("user1", "AAPL", "BUY", 10, order_type="LIMIT")

    def test_order_to_dict(self, service):
        """Order serialization includes all fields."""
        with patch("ibkr.ibkr_service._IBConnection._import_ib_insync", return_value=_mock_ib_insync_module()):
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
        with patch("ibkr.ibkr_service._IBConnection._import_ib_insync", return_value=_mock_ib_insync_module()):
            order = service.submit_order("user1", "aapl", "BUY", 1)

        assert order.ticker == "AAPL"

    def test_order_pending_status(self):
        """Order that doesn't fill should return PENDING/SUBMITTED."""
        svc = IBKRService()
        mock_ib = _make_mock_ib()

        mock_order_status = _make_mock_order_status(status="Submitted", avg_price=0.0, filled=0, remaining=5)

        mock_order_obj = MagicMock()
        mock_order_obj.orderId = 99

        mock_trade = MagicMock()
        mock_trade.orderStatus = mock_order_status
        mock_trade.order = mock_order_obj
        mock_trade.fills = []

        mock_ib.placeOrder.return_value = mock_trade
        _patch_ibc_connect(svc, "user1", mock_ib)

        with patch("ibkr.ibkr_service._IBConnection._import_ib_insync", return_value=_mock_ib_insync_module()):
            order = svc.submit_order("user1", "AAPL", "BUY", 10)

        assert order.status == "SUBMITTED"
        assert order.filled_price is None

    def test_order_placement_failure(self):
        """Order placement exception should raise ValueError."""
        svc = IBKRService()
        mock_ib = _make_mock_ib()
        mock_ib.placeOrder.side_effect = Exception("Insufficient funds")
        _patch_ibc_connect(svc, "user1", mock_ib)

        with patch("ibkr.ibkr_service._IBConnection._import_ib_insync", return_value=_mock_ib_insync_module()):
            with pytest.raises(ValueError, match="Order placement failed"):
                svc.submit_order("user1", "AAPL", "BUY", 10)


# ═══════════════════════════════════════════════════════════════════════
# Stop Order Tests (REC-138)
# ═══════════════════════════════════════════════════════════════════════

class TestIBKRStopOrders:
    """Tests for IBKR stop order functionality."""

    @pytest.fixture
    def service(self):
        svc = IBKRService()
        mock_ib = _make_mock_ib()

        mock_order_status = _make_mock_order_status(status="Submitted", avg_price=0.0, filled=0, remaining=10)

        mock_order_obj = MagicMock()
        mock_order_obj.orderId = 999

        mock_trade = MagicMock()
        mock_trade.orderStatus = mock_order_status
        mock_trade.order = mock_order_obj
        mock_trade.fills = []

        mock_ib.placeOrder.return_value = mock_trade
        _patch_ibc_connect(svc, "user1", mock_ib)
        svc._mock_ib = mock_ib
        return svc

    def test_submit_stop_order(self, service):
        """Stop order should be accepted with stop price."""
        with patch("ibkr.ibkr_service._IBConnection._import_ib_insync", return_value=_mock_ib_insync_module()):
            order = service.submit_order(
                "user1", "AAPL", "SELL", 10,
                order_type="STP", limit_price=140.0
            )
        assert order.order_type == "STP"
        assert order.side == "SELL"

    def test_submit_stop_order_alternate_name(self, service):
        """'STOP' should normalize to 'STP'."""
        with patch("ibkr.ibkr_service._IBConnection._import_ib_insync", return_value=_mock_ib_insync_module()):
            order = service.submit_order(
                "user1", "AAPL", "SELL", 10,
                order_type="STOP", limit_price=140.0
            )
        assert order.order_type == "STP"

    def test_stop_order_requires_price(self, service):
        """Stop order without price should fail."""
        with pytest.raises(ValueError, match="Stop price required"):
            service.submit_order("user1", "AAPL", "SELL", 10, order_type="STP")

    def test_submit_stop_limit_order(self, service):
        """Stop-limit order should be accepted."""
        with patch("ibkr.ibkr_service._IBConnection._import_ib_insync", return_value=_mock_ib_insync_module()):
            order = service.submit_order(
                "user1", "AAPL", "SELL", 10,
                order_type="STP_LMT", limit_price=140.0
            )
        assert order.order_type == "STP_LMT"

    def test_stop_limit_alternate_name(self, service):
        """'STOP_LIMIT' should normalize to 'STP_LMT'."""
        with patch("ibkr.ibkr_service._IBConnection._import_ib_insync", return_value=_mock_ib_insync_module()):
            order = service.submit_order(
                "user1", "AAPL", "SELL", 10,
                order_type="STOP_LIMIT", limit_price=140.0
            )
        assert order.order_type == "STP_LMT"


# ═══════════════════════════════════════════════════════════════════════
# Trailing Stop Tests (REC-143)
# ═══════════════════════════════════════════════════════════════════════

class TestIBKRTrailingStop:
    """Tests for IBKR trailing stop order functionality."""

    @pytest.fixture
    def service(self):
        svc = IBKRService()
        mock_ib = _make_mock_ib()

        mock_order_status = _make_mock_order_status(status="Submitted", avg_price=0.0, filled=0, remaining=10)

        mock_order_obj = MagicMock()
        mock_order_obj.orderId = 999

        mock_trade = MagicMock()
        mock_trade.orderStatus = mock_order_status
        mock_trade.order = mock_order_obj
        mock_trade.fills = []

        mock_ib.placeOrder.return_value = mock_trade
        _patch_ibc_connect(svc, "user1", mock_ib)
        svc._mock_ib = mock_ib
        return svc

    def test_trailing_stop_with_percent(self, service):
        """Trailing stop with percent should be accepted."""
        with patch("ibkr.ibkr_service._IBConnection._import_ib_insync", return_value=_mock_ib_insync_module()):
            order = service.submit_order(
                "user1", "AAPL", "SELL", 10,
                order_type="TRAIL", trailing_percent=5.0
            )
        assert order.order_type == "TRAIL"

    def test_trailing_stop_with_amount(self, service):
        """Trailing stop with amount should be accepted."""
        with patch("ibkr.ibkr_service._IBConnection._import_ib_insync", return_value=_mock_ib_insync_module()):
            order = service.submit_order(
                "user1", "AAPL", "SELL", 10,
                order_type="TRAIL", trailing_amount=5.0
            )
        assert order.order_type == "TRAIL"

    def test_trailing_stop_requires_trail_value(self, service):
        """Trailing stop without percent or amount should fail."""
        with pytest.raises(ValueError, match="trailing_percent or trailing_amount required"):
            service.submit_order("user1", "AAPL", "SELL", 10, order_type="TRAIL")


# ═══════════════════════════════════════════════════════════════════════
# Extended Hours + TIF Tests (REC-145, REC-146)
# ═══════════════════════════════════════════════════════════════════════

class TestIBKROrderOptions:
    """Tests for extended hours and time-in-force options."""

    @pytest.fixture
    def service(self):
        svc = IBKRService()
        mock_ib = _make_mock_ib()

        mock_order_status = _make_mock_order_status(status="Submitted", avg_price=0.0, filled=0, remaining=10)

        mock_order_obj = MagicMock()
        mock_order_obj.orderId = 999

        mock_trade = MagicMock()
        mock_trade.orderStatus = mock_order_status
        mock_trade.order = mock_order_obj
        mock_trade.fills = []

        mock_ib.placeOrder.return_value = mock_trade
        _patch_ibc_connect(svc, "user1", mock_ib)
        svc._mock_ib = mock_ib
        return svc

    def test_gtc_order(self, service):
        """GTC (Good Till Canceled) order should be accepted."""
        with patch("ibkr.ibkr_service._IBConnection._import_ib_insync", return_value=_mock_ib_insync_module()):
            order = service.submit_order(
                "user1", "AAPL", "BUY", 10,
                order_type="LIMIT", limit_price=150.0, tif="GTC"
            )
        assert order is not None

    def test_gtd_requires_date(self, service):
        """GTD order without date should fail."""
        with pytest.raises(ValueError, match="good_till_date required"):
            service.submit_order(
                "user1", "AAPL", "BUY", 10,
                order_type="LIMIT", limit_price=150.0, tif="GTD"
            )

    def test_gtd_with_date(self, service):
        """GTD order with date should be accepted."""
        with patch("ibkr.ibkr_service._IBConnection._import_ib_insync", return_value=_mock_ib_insync_module()):
            order = service.submit_order(
                "user1", "AAPL", "BUY", 10,
                order_type="LIMIT", limit_price=150.0,
                tif="GTD", good_till_date="20260210 16:00:00"
            )
        assert order is not None

    def test_invalid_tif(self, service):
        """Invalid TIF should fail."""
        with pytest.raises(ValueError, match="Invalid time-in-force"):
            service.submit_order(
                "user1", "AAPL", "BUY", 10,
                order_type="LIMIT", limit_price=150.0, tif="INVALID"
            )

    def test_outside_rth_accepted(self, service):
        """Extended hours order should be accepted."""
        with patch("ibkr.ibkr_service._IBConnection._import_ib_insync", return_value=_mock_ib_insync_module()):
            order = service.submit_order(
                "user1", "AAPL", "BUY", 10,
                order_type="LIMIT", limit_price=150.0, outside_rth=True
            )
        assert order is not None


# ═══════════════════════════════════════════════════════════════════════
# Order Cancellation Tests (REC-139)
# ═══════════════════════════════════════════════════════════════════════

class TestIBKROrderCancellation:
    """Tests for IBKR order cancellation functionality."""

    @pytest.fixture
    def service(self):
        svc = IBKRService()
        mock_ib = _make_mock_ib()
        _patch_ibc_connect(svc, "user1", mock_ib)
        svc._mock_ib = mock_ib
        return svc

    def test_cancel_order_success(self, service):
        """Cancelling an open order should work."""
        mock_order = MagicMock()
        mock_order.orderId = 123
        service._mock_ib.openOrders.return_value = [mock_order]

        result = service.cancel_order("user1", "123")

        assert result["order_id"] == "123"
        assert result["status"] == "CANCEL_REQUESTED"
        service._mock_ib.cancelOrder.assert_called_once_with(mock_order)

    def test_cancel_order_not_found(self, service):
        """Cancelling non-existent order should fail."""
        service._mock_ib.openOrders.return_value = []

        with pytest.raises(ValueError, match="not found"):
            service.cancel_order("user1", "999")

    def test_cancel_order_not_connected(self):
        """Cancelling when not connected should fail."""
        svc = IBKRService()
        with pytest.raises(ValueError, match="IBKR not connected"):
            svc.cancel_order("user1", "123")

    def test_get_open_orders_empty(self, service):
        """No open orders returns empty list."""
        service._mock_ib.openTrades.return_value = []
        orders = service.get_open_orders("user1")
        assert orders == []

    def test_get_open_orders_with_data(self, service):
        """Open orders are returned as IBKROrder objects."""
        mock_contract = MagicMock()
        mock_contract.symbol = "AAPL"

        mock_order = MagicMock()
        mock_order.orderId = 456
        mock_order.action = "BUY"
        mock_order.totalQuantity = 10
        mock_order.orderType = "LMT"

        mock_status = MagicMock()
        mock_status.status = "Submitted"
        mock_status.avgFillPrice = 0.0

        mock_trade = MagicMock()
        mock_trade.contract = mock_contract
        mock_trade.order = mock_order
        mock_trade.orderStatus = mock_status

        service._mock_ib.openTrades.return_value = [mock_trade]

        orders = service.get_open_orders("user1")
        assert len(orders) == 1
        assert orders[0].order_id == "456"
        assert orders[0].ticker == "AAPL"
        assert orders[0].side == "BUY"
        assert orders[0].quantity == 10
        assert orders[0].order_type == "LIMIT"
        assert orders[0].status == "SUBMITTED"

    def test_get_open_orders_not_connected(self):
        """Getting orders when not connected should fail."""
        svc = IBKRService()
        with pytest.raises(ValueError, match="IBKR not connected"):
            svc.get_open_orders("user1")


# ═══════════════════════════════════════════════════════════════════════
# Real-time Quote Tests (REC-140)
# ═══════════════════════════════════════════════════════════════════════

class TestIBKRQuotes:
    """Tests for IBKR real-time quote functionality."""

    @pytest.fixture
    def service(self):
        svc = IBKRService()
        mock_ib = _make_mock_ib()
        _patch_ibc_connect(svc, "user1", mock_ib)
        svc._mock_ib = mock_ib
        return svc

    def test_get_quote_success(self, service):
        """Quote returns price data from IB."""
        mock_ticker = MagicMock()
        mock_ticker.bid = 150.25
        mock_ticker.ask = 150.30
        mock_ticker.last = 150.27
        mock_ticker.close = 149.50
        mock_ticker.high = 152.00
        mock_ticker.low = 148.50
        mock_ticker.volume = 1000000

        service._mock_ib.reqMktData.return_value = mock_ticker
        service._mock_ib.qualifyContracts.return_value = None
        service._mock_ib.cancelMktData.return_value = None

        with patch("ibkr.ibkr_service._IBConnection._import_ib_insync", return_value=_mock_ib_insync_module()):
            quote = service.get_quote("user1", "AAPL")

        assert quote["ticker"] == "AAPL"
        assert quote["bid"] == 150.25
        assert quote["ask"] == 150.30
        assert quote["last"] == 150.27
        assert quote["price"] == 150.27
        assert "mid" in quote
        assert "timestamp" in quote

    def test_get_quote_not_connected(self):
        """Getting quote when not connected should fail."""
        svc = IBKRService()
        with pytest.raises(ValueError, match="IBKR not connected"):
            svc.get_quote("user1", "AAPL")

    def test_get_quote_ticker_uppercase(self, service):
        """Ticker should be uppercased in quote response."""
        mock_ticker = MagicMock()
        mock_ticker.bid = 100.0
        mock_ticker.ask = 100.1
        mock_ticker.last = 100.05
        mock_ticker.close = 99.0
        mock_ticker.high = 101.0
        mock_ticker.low = 98.0
        mock_ticker.volume = 500000

        service._mock_ib.reqMktData.return_value = mock_ticker

        with patch("ibkr.ibkr_service._IBConnection._import_ib_insync", return_value=_mock_ib_insync_module()):
            quote = service.get_quote("user1", "aapl")

        assert quote["ticker"] == "AAPL"


# ═══════════════════════════════════════════════════════════════════════
# Position Tests
# ═══════════════════════════════════════════════════════════════════════

class TestIBKRPositions:
    """Tests for IBKR position retrieval."""

    @pytest.fixture
    def service(self):
        svc = IBKRService()
        mock_ib = _make_mock_ib()
        _patch_ibc_connect(svc, "user1", mock_ib)
        svc._mock_ib = mock_ib
        return svc

    def test_get_positions_empty(self, service):
        """No positions returns empty list."""
        positions = service.get_positions("user1")
        assert isinstance(positions, list)
        assert len(positions) == 0

    def test_get_positions_with_data(self):
        """Positions are converted to IBKRPosition objects."""
        svc = IBKRService()
        mock_ib = _make_mock_ib()

        # Mock a position
        mock_contract = MagicMock()
        mock_contract.symbol = "AAPL"
        mock_pos = MagicMock()
        mock_pos.contract = mock_contract
        mock_pos.position = 100.0
        mock_pos.avgCost = 150.25

        mock_ib.positions.return_value = [mock_pos]
        mock_ib.portfolio.return_value = []

        _patch_ibc_connect(svc, "user1", mock_ib)

        positions = svc.get_positions("user1")
        assert len(positions) == 1
        assert positions[0].ticker == "AAPL"
        assert positions[0].quantity == 100.0
        assert positions[0].avg_cost == 150.25

    def test_get_positions_with_portfolio(self):
        """Portfolio data enriches positions with market value and PnL."""
        svc = IBKRService()
        mock_ib = _make_mock_ib()

        mock_contract = MagicMock()
        mock_contract.symbol = "AAPL"

        mock_pos = MagicMock()
        mock_pos.contract = mock_contract
        mock_pos.position = 50.0
        mock_pos.avgCost = 140.00

        mock_portfolio_item = MagicMock()
        mock_portfolio_item.contract = mock_contract
        mock_portfolio_item.marketValue = 9500.0
        mock_portfolio_item.unrealizedPNL = 2500.0

        mock_ib.positions.return_value = [mock_pos]
        mock_ib.portfolio.return_value = [mock_portfolio_item]

        _patch_ibc_connect(svc, "user1", mock_ib)

        positions = svc.get_positions("user1")
        assert positions[0].market_value == 9500.0
        assert positions[0].unrealized_pnl == 2500.0

    def test_get_positions_not_connected(self):
        """Getting positions when not connected should fail."""
        svc = IBKRService()
        with pytest.raises(ValueError, match="IBKR not connected"):
            svc.get_positions("user1")

    def test_position_to_dict(self):
        """Position serialization includes all fields."""
        pos = IBKRPosition(
            ticker="TSLA",
            quantity=10,
            avg_cost=200.0,
            market_value=2500.0,
            unrealized_pnl=500.0,
        )
        data = pos.to_dict()
        assert data["ticker"] == "TSLA"
        assert data["quantity"] == 10
        assert data["market_value"] == 2500.0


# ═══════════════════════════════════════════════════════════════════════
# Account Summary Tests
# ═══════════════════════════════════════════════════════════════════════

class TestIBKRAccountSummary:
    """Tests for account summary retrieval."""

    def test_get_account_summary(self):
        """Account summary returns parsed financial data."""
        svc = IBKRService()
        mock_ib = _make_mock_ib()

        # Mock account summary items
        def _make_item(tag, value):
            item = MagicMock()
            item.tag = tag
            item.value = value
            return item

        mock_ib.accountSummary.return_value = [
            _make_item("NetLiquidation", "1000000.50"),
            _make_item("TotalCashValue", "500000.25"),
            _make_item("BuyingPower", "2000000.00"),
            _make_item("GrossPositionValue", "500000.25"),
            _make_item("UnrealizedPnL", "12345.67"),
            _make_item("RealizedPnL", "5432.10"),
            _make_item("Currency", "USD"),
        ]

        _patch_ibc_connect(svc, "user1", mock_ib)

        summary = svc.get_account_summary("user1")

        assert summary["account_id"] == "DUP526287"
        assert summary["is_paper"] is True
        assert summary["net_liquidation"] == 1000000.50
        assert summary["total_cash"] == 500000.25
        assert summary["buying_power"] == 2000000.00
        assert summary["unrealized_pnl"] == 12345.67

    def test_get_account_summary_not_connected(self):
        """Account summary when not connected should fail."""
        svc = IBKRService()
        with pytest.raises(ValueError, match="IBKR not connected"):
            svc.get_account_summary("user1")

    def test_get_account_summary_error(self):
        """Account summary API failure is handled gracefully."""
        svc = IBKRService()
        mock_ib = _make_mock_ib()
        mock_ib.accountSummary.side_effect = Exception("Timeout")
        _patch_ibc_connect(svc, "user1", mock_ib)

        with pytest.raises(ValueError, match="Failed to retrieve"):
            svc.get_account_summary("user1")


# ═══════════════════════════════════════════════════════════════════════
# Disconnection Cleanup Tests
# ═══════════════════════════════════════════════════════════════════════

class TestDisconnectionCleanup:
    """Tests that disconnection properly cleans up resources."""

    def test_disconnect_removes_ib_connection(self):
        """Disconnect should remove the _IBConnection from storage."""
        svc = IBKRService()
        mock_ib = _make_mock_ib()
        ibc = _patch_ibc_connect(svc, "user1", mock_ib)

        assert "user1" in svc._ib_connections

        svc.disconnect("user1")

        assert "user1" not in svc._ib_connections

    def test_disconnect_calls_ib_disconnect(self):
        """Disconnect should call disconnect on the IB wrapper."""
        svc = IBKRService()
        mock_ib = _make_mock_ib()
        ibc = _patch_ibc_connect(svc, "user1", mock_ib)

        svc.disconnect("user1")

        ibc.disconnect.assert_called_once()

    def test_operations_after_disconnect_fail(self):
        """Operations after disconnect should fail gracefully."""
        svc = IBKRService()
        mock_ib = _make_mock_ib()
        _patch_ibc_connect(svc, "user1", mock_ib)

        svc.disconnect("user1")

        with pytest.raises(ValueError, match="IBKR not connected"):
            svc.submit_order("user1", "AAPL", "BUY", 10)

        with pytest.raises(ValueError, match="IBKR not connected"):
            svc.get_positions("user1")


# ═══════════════════════════════════════════════════════════════════════
# Error Handling Tests
# ═══════════════════════════════════════════════════════════════════════

class TestIBKRErrorHandling:
    """Tests for error handling edge cases."""

    def test_connection_refused_graceful(self):
        """Connection refused doesn't crash — returns ERROR state."""
        svc = IBKRService(host="127.0.0.1", port=9999)
        with patch.object(
            _IBConnection,
            "connect",
            side_effect=ConnectionError("Connection refused"),
        ):
            conn = svc.connect("user1")

        assert conn.state == IBKRConnectionState.ERROR
        assert "Connection refused" in conn.error_message

    def test_invalid_ticker_handled(self):
        """Order for invalid ticker — IB raises, we wrap in ValueError."""
        svc = IBKRService()
        mock_ib = _make_mock_ib()
        mock_ib.placeOrder.side_effect = Exception("No security definition found")
        _patch_ibc_connect(svc, "user1", mock_ib)

        with patch("ibkr.ibkr_service._IBConnection._import_ib_insync", return_value=_mock_ib_insync_module()):
            with pytest.raises(ValueError, match="Order placement failed"):
                svc.submit_order("user1", "XXXXXX", "BUY", 1)

    def test_service_starts_without_gateway(self):
        """IBKRService should instantiate fine without Gateway running."""
        svc = IBKRService(host="127.0.0.1", port=9999)
        assert svc is not None

        # Status should be disconnected, not an error
        status = svc.get_status("user1")
        assert status.state == IBKRConnectionState.DISCONNECTED


# ═══════════════════════════════════════════════════════════════════════
# _IBConnection Unit Tests
# ═══════════════════════════════════════════════════════════════════════

class TestIBConnectionWrapper:
    """Tests for the low-level _IBConnection wrapper."""

    def test_initial_state(self):
        ibc = _IBConnection("127.0.0.1", 4002, 10)
        assert ibc._connected is False
        assert ibc._ib is None

    def test_connect_failure(self):
        """Connection to non-existent port should raise ConnectionError."""
        ibc = _IBConnection("127.0.0.1", 59999, 10)
        with pytest.raises(ConnectionError):
            ibc.connect()

    def test_disconnect_without_connect(self):
        """Disconnecting without connecting should not error."""
        ibc = _IBConnection("127.0.0.1", 4002, 10)
        ibc.disconnect()  # Should not raise


# ═══════════════════════════════════════════════════════════════════════
# Data Class Tests
# ═══════════════════════════════════════════════════════════════════════

class TestDataClasses:
    """Tests for data class construction and serialization."""

    def test_ibkr_connection_defaults(self):
        conn = IBKRConnection(user_id="u1")
        assert conn.state == IBKRConnectionState.DISCONNECTED
        assert conn.account_id is None

    def test_ibkr_order_to_dict(self):
        order = IBKROrder(
            order_id="42",
            ticker="AAPL",
            side="BUY",
            quantity=10,
            order_type="MARKET",
            status="FILLED",
            filled_price=185.50,
            filled_at="2026-01-15T10:30:00",
            is_paper=True,
        )
        d = order.to_dict()
        assert d["order_id"] == "42"
        assert d["filled_price"] == 185.50

    def test_ibkr_position_to_dict(self):
        pos = IBKRPosition(
            ticker="TSLA",
            quantity=50,
            avg_cost=200.0,
            market_value=12500.0,
            unrealized_pnl=2500.0,
        )
        d = pos.to_dict()
        assert d["ticker"] == "TSLA"
        assert d["unrealized_pnl"] == 2500.0


# ═══════════════════════════════════════════════════════════════════════
# Historical Bars Tests (REC-160)
# ═══════════════════════════════════════════════════════════════════════

class TestIBKRHistoricalBars:
    """Tests for get_historical_bars() (REC-160)."""

    def test_get_historical_bars_success(self):
        """Fetch historical bars from IB."""
        svc = IBKRService()
        mock_ib = _make_mock_ib()
        
        # Mock bar data
        mock_bar = MagicMock()
        mock_bar.date = datetime(2026, 1, 15, 10, 0, 0)
        mock_bar.open = 185.0
        mock_bar.high = 186.5
        mock_bar.low = 184.5
        mock_bar.close = 186.0
        mock_bar.volume = 1000000
        mock_ib.reqHistoricalData.return_value = [mock_bar]
        mock_ib.qualifyContracts.return_value = None

        _patch_ibc_connect(svc, "user1", mock_ib)

        with patch("ibkr.ibkr_service._IBConnection._import_ib_insync", return_value=_mock_ib_insync_module()):
            bars = svc.get_historical_bars("user1", "AAPL", duration="1 D", bar_size="5 mins")

        assert len(bars) == 1
        assert bars[0]["open"] == 185.0
        assert bars[0]["close"] == 186.0
        assert bars[0]["volume"] == 1000000

    def test_get_historical_bars_not_connected(self):
        """Should raise if not connected."""
        svc = IBKRService()
        with pytest.raises(ValueError, match="not connected"):
            svc.get_historical_bars("user1", "AAPL")

    def test_get_historical_bars_parameters(self):
        """Verify parameters are passed correctly to IB."""
        svc = IBKRService()
        mock_ib = _make_mock_ib()
        mock_ib.reqHistoricalData.return_value = []
        mock_ib.qualifyContracts.return_value = None

        _patch_ibc_connect(svc, "user1", mock_ib)

        with patch("ibkr.ibkr_service._IBConnection._import_ib_insync", return_value=_mock_ib_insync_module()):
            svc.get_historical_bars(
                "user1", "AAPL",
                duration="1 W",
                bar_size="1 hour",
                what_to_show="MIDPOINT",
                use_rth=False,
            )

        # Verify reqHistoricalData was called with correct params
        call_args = mock_ib.reqHistoricalData.call_args
        assert call_args.kwargs["durationStr"] == "1 W"
        assert call_args.kwargs["barSizeSetting"] == "1 hour"
        assert call_args.kwargs["whatToShow"] == "MIDPOINT"
        assert call_args.kwargs["useRTH"] is False


# ═══════════════════════════════════════════════════════════════════════
# Bracket Orders Tests (REC-161)
# ═══════════════════════════════════════════════════════════════════════

class TestIBKRBracketOrders:
    """Tests for submit_bracket_order() (REC-161)."""

    def test_bracket_order_success(self):
        """Submit bracket order with entry, TP, and SL."""
        svc = IBKRService()
        mock_ib = _make_mock_ib()

        # Mock bracket order
        mock_trade = MagicMock()
        mock_trade.order.orderId = 100
        mock_trade.order.lmtPrice = 180.0
        mock_trade.order.auxPrice = None
        mock_trade.orderStatus.status = "Submitted"

        mock_ib.bracketOrder.return_value = [MagicMock(), MagicMock(), MagicMock()]
        mock_ib.placeOrder.return_value = mock_trade
        mock_ib.qualifyContracts.return_value = None

        _patch_ibc_connect(svc, "user1", mock_ib)

        with patch("ibkr.ibkr_service._IBConnection._import_ib_insync", return_value=_mock_ib_insync_module()):
            result = svc.submit_bracket_order(
                "user1", "AAPL",
                side="BUY", quantity=100,
                entry_price=180.0,
                take_profit_price=200.0,
                stop_loss_price=170.0,
            )

        assert result["ticker"] == "AAPL"
        assert result["side"] == "BUY"
        assert result["quantity"] == 100
        assert "entry" in result
        assert "take_profit" in result
        assert "stop_loss" in result

    def test_bracket_order_not_connected(self):
        """Should raise if not connected."""
        svc = IBKRService()
        with pytest.raises(ValueError, match="not connected"):
            svc.submit_bracket_order(
                "user1", "AAPL",
                side="BUY", quantity=100,
                entry_price=180.0,
                take_profit_price=200.0,
                stop_loss_price=170.0,
            )

    def test_bracket_order_invalid_buy_prices(self):
        """Buy: TP must be above entry, SL must be below entry."""
        svc = IBKRService()
        mock_ib = _make_mock_ib()
        _patch_ibc_connect(svc, "user1", mock_ib)

        # TP below entry
        with pytest.raises(ValueError, match="Take profit must be above"):
            svc.submit_bracket_order(
                "user1", "AAPL",
                side="BUY", quantity=100,
                entry_price=180.0,
                take_profit_price=170.0,  # Wrong!
                stop_loss_price=160.0,
            )

        # SL above entry
        with pytest.raises(ValueError, match="Stop loss must be below"):
            svc.submit_bracket_order(
                "user1", "AAPL",
                side="BUY", quantity=100,
                entry_price=180.0,
                take_profit_price=200.0,
                stop_loss_price=190.0,  # Wrong!
            )

    def test_bracket_order_invalid_sell_prices(self):
        """Sell: TP must be below entry, SL must be above entry."""
        svc = IBKRService()
        mock_ib = _make_mock_ib()
        _patch_ibc_connect(svc, "user1", mock_ib)

        # TP above entry
        with pytest.raises(ValueError, match="Take profit must be below"):
            svc.submit_bracket_order(
                "user1", "AAPL",
                side="SELL", quantity=100,
                entry_price=180.0,
                take_profit_price=190.0,  # Wrong!
                stop_loss_price=200.0,
            )


# ═══════════════════════════════════════════════════════════════════════
# Market Scanner Tests (REC-157)
# ═══════════════════════════════════════════════════════════════════════

class TestIBKRScanner:
    """Tests for get_scanner_results() (REC-157)."""

    def test_scanner_success(self):
        """Fetch scanner results from IB."""
        svc = IBKRService()
        mock_ib = _make_mock_ib()

        # Mock scanner data
        mock_contract = MagicMock()
        mock_contract.symbol = "NVDA"
        mock_contract.exchange = "SMART"
        mock_contract.conId = 12345

        mock_contract_details = MagicMock()
        mock_contract_details.contract = mock_contract

        mock_scan_item = MagicMock()
        mock_scan_item.rank = 1
        mock_scan_item.contractDetails = mock_contract_details

        mock_scan_data = [mock_scan_item]
        mock_ib.reqScannerSubscription.return_value = mock_scan_data
        mock_ib.cancelScannerSubscription.return_value = None

        _patch_ibc_connect(svc, "user1", mock_ib)

        mock_ibi = _mock_ib_insync_module()
        mock_ibi.ScannerSubscription.return_value = MagicMock()

        with patch("ibkr.ibkr_service._IBConnection._import_ib_insync", return_value=mock_ibi):
            results = svc.get_scanner_results("user1", scan_code="TOP_PERC_GAIN")

        assert len(results) == 1
        assert results[0]["rank"] == 1
        assert results[0]["ticker"] == "NVDA"

    def test_scanner_not_connected(self):
        """Should raise if not connected."""
        svc = IBKRService()
        with pytest.raises(ValueError, match="not connected"):
            svc.get_scanner_results("user1")

    def test_scanner_parameters(self):
        """Verify scanner parameters are set correctly."""
        svc = IBKRService()
        mock_ib = _make_mock_ib()
        mock_ib.reqScannerSubscription.return_value = []
        mock_ib.cancelScannerSubscription.return_value = None

        _patch_ibc_connect(svc, "user1", mock_ib)

        mock_ibi = _mock_ib_insync_module()
        mock_subscription = MagicMock()
        mock_ibi.ScannerSubscription.return_value = mock_subscription

        with patch("ibkr.ibkr_service._IBConnection._import_ib_insync", return_value=mock_ibi):
            svc.get_scanner_results(
                "user1",
                scan_code="MOST_ACTIVE",
                num_rows=30,
                above_price=10.0,
            )

        # Verify ScannerSubscription was called
        mock_ibi.ScannerSubscription.assert_called_once()
        call_kwargs = mock_ibi.ScannerSubscription.call_args.kwargs
        assert call_kwargs["scanCode"] == "MOST_ACTIVE"
        assert call_kwargs["numberOfRows"] == 30
        assert call_kwargs["abovePrice"] == 10.0


# ═══════════════════════════════════════════════════════════════════════
# What-If Order Tests (REC-162)
# ═══════════════════════════════════════════════════════════════════════

class TestIBKRWhatIf:
    """Tests for what_if_order() (REC-162)."""

    def test_what_if_success(self):
        """Simulate order and get margin/commission preview."""
        svc = IBKRService()
        mock_ib = _make_mock_ib()

        # Mock what-if result
        mock_state = MagicMock()
        mock_state.initMarginBefore = "50000"
        mock_state.initMarginAfter = "55000"
        mock_state.initMarginChange = "5000"
        mock_state.maintMarginBefore = "40000"
        mock_state.maintMarginAfter = "44000"
        mock_state.maintMarginChange = "4000"
        mock_state.equityWithLoanBefore = "100000"
        mock_state.equityWithLoanAfter = "95000"
        mock_state.equityWithLoanChange = "-5000"
        mock_state.commission = "1.50"
        mock_state.minCommission = "1.00"
        mock_state.maxCommission = "2.00"
        mock_state.commissionCurrency = "USD"
        mock_state.warningText = ""

        mock_ib.whatIfOrder.return_value = mock_state
        mock_ib.qualifyContracts.return_value = None

        _patch_ibc_connect(svc, "user1", mock_ib)

        with patch("ibkr.ibkr_service._IBConnection._import_ib_insync", return_value=_mock_ib_insync_module()):
            result = svc.what_if_order(
                "user1", "AAPL",
                side="BUY", quantity=100,
                order_type="MARKET",
            )

        assert result["ticker"] == "AAPL"
        assert result["side"] == "BUY"
        assert result["quantity"] == 100
        assert result["init_margin_change"] == 5000.0
        assert result["commission"] == 1.50

    def test_what_if_not_connected(self):
        """Should raise if not connected."""
        svc = IBKRService()
        with pytest.raises(ValueError, match="not connected"):
            svc.what_if_order("user1", "AAPL", side="BUY", quantity=100)

    def test_what_if_limit_order(self):
        """What-if with limit order."""
        svc = IBKRService()
        mock_ib = _make_mock_ib()

        mock_state = MagicMock()
        mock_state.initMarginBefore = "50000"
        mock_state.initMarginAfter = "55000"
        mock_state.initMarginChange = "5000"
        mock_state.maintMarginBefore = "40000"
        mock_state.maintMarginAfter = "44000"
        mock_state.maintMarginChange = "4000"
        mock_state.equityWithLoanBefore = "100000"
        mock_state.equityWithLoanAfter = "95000"
        mock_state.equityWithLoanChange = "-5000"
        mock_state.commission = "1.00"
        mock_state.minCommission = None
        mock_state.maxCommission = None
        mock_state.commissionCurrency = "USD"
        mock_state.warningText = None

        mock_ib.whatIfOrder.return_value = mock_state
        mock_ib.qualifyContracts.return_value = None

        _patch_ibc_connect(svc, "user1", mock_ib)

        with patch("ibkr.ibkr_service._IBConnection._import_ib_insync", return_value=_mock_ib_insync_module()):
            result = svc.what_if_order(
                "user1", "AAPL",
                side="BUY", quantity=50,
                order_type="LIMIT",
                limit_price=180.0,
            )

        assert result["order_type"] == "LIMIT"
        assert result["limit_price"] == 180.0

    def test_what_if_limit_requires_price(self):
        """Limit order requires limit_price."""
        svc = IBKRService()
        mock_ib = _make_mock_ib()
        _patch_ibc_connect(svc, "user1", mock_ib)

        with pytest.raises(ValueError, match="Limit price required"):
            svc.what_if_order(
                "user1", "AAPL",
                side="BUY", quantity=50,
                order_type="LIMIT",
            )

    def test_what_if_invalid_order_type(self):
        """Only MARKET and LIMIT supported for what-if."""
        svc = IBKRService()
        mock_ib = _make_mock_ib()
        _patch_ibc_connect(svc, "user1", mock_ib)

        with pytest.raises(ValueError, match="only supports MARKET and LIMIT"):
            svc.what_if_order(
                "user1", "AAPL",
                side="BUY", quantity=50,
                order_type="STP",
            )


# ═══════════════════════════════════════════════════════════════════════
# Trade History Tests (REC-154)
# ═══════════════════════════════════════════════════════════════════════

class TestIBKRTradeHistory:
    """Tests for get_trade_history() (REC-154)."""

    def test_get_trade_history_success(self):
        """Fetch trade executions from IB."""
        svc = IBKRService()
        mock_ib = _make_mock_ib()

        # Mock fill data
        mock_execution = MagicMock()
        mock_execution.execId = "0001"
        mock_execution.orderId = 100
        mock_execution.side = "BOT"
        mock_execution.shares = 100
        mock_execution.price = 185.50
        mock_execution.avgPrice = 185.50
        mock_execution.time = datetime(2026, 1, 15, 10, 30, 0)
        mock_execution.exchange = "SMART"
        mock_execution.acctNumber = "DUP526287"

        mock_contract = MagicMock()
        mock_contract.symbol = "AAPL"

        mock_commission = MagicMock()
        mock_commission.commission = 1.50
        mock_commission.realizedPNL = 0.0
        mock_commission.currency = "USD"

        mock_fill = MagicMock()
        mock_fill.execution = mock_execution
        mock_fill.contract = mock_contract
        mock_fill.commissionReport = mock_commission

        mock_ib.fills.return_value = [mock_fill]

        _patch_ibc_connect(svc, "user1", mock_ib)

        history = svc.get_trade_history("user1")

        assert len(history) == 1
        assert history[0]["ticker"] == "AAPL"
        assert history[0]["quantity"] == 100
        assert history[0]["price"] == 185.50
        assert history[0]["commission"] == 1.50

    def test_get_trade_history_not_connected(self):
        """Should raise if not connected."""
        svc = IBKRService()
        with pytest.raises(ValueError, match="not connected"):
            svc.get_trade_history("user1")

    def test_get_trade_history_empty(self):
        """Empty fills list returns empty result."""
        svc = IBKRService()
        mock_ib = _make_mock_ib()
        mock_ib.fills.return_value = []

        _patch_ibc_connect(svc, "user1", mock_ib)

        history = svc.get_trade_history("user1")
        assert history == []


# ═══════════════════════════════════════════════════════════════════════
# Daily Loss Limit Tests (REC-152)
# ═══════════════════════════════════════════════════════════════════════

class TestIBKRDailyLossLimit:
    """Tests for daily loss limit functionality (REC-152)."""

    def test_get_daily_pnl(self):
        """Fetch daily PnL from IB."""
        svc = IBKRService()
        mock_ib = _make_mock_ib()

        # Mock account summary with PnL data
        mock_values = [
            MagicMock(tag="RealizedPnL", value="100.00"),
            MagicMock(tag="UnrealizedPnL", value="-50.00"),
            MagicMock(tag="NetLiquidation", value="100000.00"),
        ]
        mock_ib.accountSummary.return_value = mock_values

        _patch_ibc_connect(svc, "user1", mock_ib)

        pnl = svc.get_daily_pnl("user1")

        assert pnl["realized_pnl"] == 100.0
        assert pnl["unrealized_pnl"] == -50.0
        assert pnl["daily_pnl"] == 50.0
        assert pnl["trading_halted"] is False

    def test_trading_halted_on_loss(self):
        """Trading halted when loss exceeds limit."""
        svc = IBKRService()
        mock_ib = _make_mock_ib()

        # Mock large loss (more than 5% of net liquidation)
        mock_values = [
            MagicMock(tag="RealizedPnL", value="-3000.00"),
            MagicMock(tag="UnrealizedPnL", value="-3000.00"),
            MagicMock(tag="NetLiquidation", value="100000.00"),
        ]
        mock_ib.accountSummary.return_value = mock_values

        _patch_ibc_connect(svc, "user1", mock_ib)

        pnl = svc.get_daily_pnl("user1")

        assert pnl["daily_pnl"] == -6000.0
        assert pnl["trading_halted"] is True

    def test_get_daily_pnl_not_connected(self):
        """Should raise if not connected."""
        svc = IBKRService()
        with pytest.raises(ValueError, match="not connected"):
            svc.get_daily_pnl("user1")

    def test_set_daily_loss_limit(self):
        """Set user's daily loss limit."""
        svc = IBKRService()
        mock_ib = _make_mock_ib()
        _patch_ibc_connect(svc, "user1", mock_ib)

        result = svc.set_daily_loss_limit("user1", 3.0)

        assert result["loss_limit_percent"] == 3.0

    def test_set_daily_loss_limit_invalid(self):
        """Invalid loss limit values rejected."""
        svc = IBKRService()
        mock_ib = _make_mock_ib()
        _patch_ibc_connect(svc, "user1", mock_ib)

        with pytest.raises(ValueError, match="between 0 and 100"):
            svc.set_daily_loss_limit("user1", 0)

        with pytest.raises(ValueError, match="between 0 and 100"):
            svc.set_daily_loss_limit("user1", 150)

    def test_is_trading_halted(self):
        """Check trading halt status."""
        svc = IBKRService()
        # Clear any state from other tests
        svc._daily_loss_state.clear()

        # Initially not halted (no state)
        assert svc.is_trading_halted("new_user_123") is False


# ═══════════════════════════════════════════════════════════════════════
# Volume Spike Tests (REC-159)
# ═══════════════════════════════════════════════════════════════════════

class TestIBKRVolumeSpike:
    """Tests for volume spike detection (REC-159)."""

    def test_get_volume_analysis(self):
        """Analyze volume for spike detection."""
        svc = IBKRService()
        mock_ib = _make_mock_ib()

        # Mock historical bars
        mock_bar = MagicMock()
        mock_bar.volume = 1000000
        mock_ib.reqHistoricalData.return_value = [mock_bar] * 20
        mock_ib.qualifyContracts.return_value = None

        # Mock current volume (3x average = spike)
        mock_ticker = MagicMock()
        mock_ticker.volume = 3000000
        mock_ib.reqMktData.return_value = mock_ticker
        mock_ib.cancelMktData.return_value = None

        _patch_ibc_connect(svc, "user1", mock_ib)

        with patch("ibkr.ibkr_service._IBConnection._import_ib_insync", return_value=_mock_ib_insync_module()):
            analysis = svc.get_volume_analysis("user1", "AAPL")

        assert analysis["ticker"] == "AAPL"
        assert analysis["current_volume"] == 3000000
        assert analysis["avg_volume"] == 1000000
        assert analysis["volume_ratio"] == 3.0
        assert analysis["is_spike"] is True
        assert analysis["alert_level"] == "HIGH"

    def test_no_spike_below_threshold(self):
        """Volume below threshold is not a spike."""
        svc = IBKRService()
        mock_ib = _make_mock_ib()

        mock_bar = MagicMock()
        mock_bar.volume = 1000000
        mock_ib.reqHistoricalData.return_value = [mock_bar] * 20
        mock_ib.qualifyContracts.return_value = None

        # Current volume only 1.5x average (below 2.0 threshold)
        mock_ticker = MagicMock()
        mock_ticker.volume = 1500000
        mock_ib.reqMktData.return_value = mock_ticker
        mock_ib.cancelMktData.return_value = None

        _patch_ibc_connect(svc, "user1", mock_ib)

        with patch("ibkr.ibkr_service._IBConnection._import_ib_insync", return_value=_mock_ib_insync_module()):
            analysis = svc.get_volume_analysis("user1", "AAPL")

        assert analysis["is_spike"] is False
        assert analysis["alert_level"] is None

    def test_volume_analysis_not_connected(self):
        """Should raise if not connected."""
        svc = IBKRService()
        with pytest.raises(ValueError, match="not connected"):
            svc.get_volume_analysis("user1", "AAPL")

    def test_check_watchlist_volume_spikes(self):
        """Check multiple tickers for spikes."""
        svc = IBKRService()
        mock_ib = _make_mock_ib()

        # Mock spike detection (will be called per ticker)
        mock_bar = MagicMock()
        mock_bar.volume = 1000000
        mock_ib.reqHistoricalData.return_value = [mock_bar] * 20
        mock_ib.qualifyContracts.return_value = None

        mock_ticker = MagicMock()
        mock_ticker.volume = 3000000  # Spike!
        mock_ib.reqMktData.return_value = mock_ticker
        mock_ib.cancelMktData.return_value = None

        _patch_ibc_connect(svc, "user1", mock_ib)

        with patch("ibkr.ibkr_service._IBConnection._import_ib_insync", return_value=_mock_ib_insync_module()):
            spikes = svc.check_watchlist_volume_spikes("user1", ["AAPL", "NVDA"])

        # Both should be spikes with our mock
        assert len(spikes) == 2


# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
