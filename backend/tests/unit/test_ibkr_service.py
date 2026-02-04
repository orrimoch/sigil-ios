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

    @patch.object(_IBConnection, "connect", return_value=["DUP526287"])
    def test_connect_success(self, mock_connect, service):
        """Successful connection sets state to CONNECTED."""
        conn = service.connect("user1", account_id="DUP526287")

        assert conn.state == IBKRConnectionState.CONNECTED
        assert conn.account_id == "DUP526287"
        assert conn.is_paper is True
        assert conn.connected_at is not None
        assert conn.error_message is None

    @patch.object(_IBConnection, "connect", return_value=["DUP526287"])
    def test_connect_default_account(self, mock_connect, service):
        """Connection without explicit account uses default."""
        conn = service.connect("user1")

        assert conn.state == IBKRConnectionState.CONNECTED
        assert conn.account_id == "DUP526287"

    @patch.object(_IBConnection, "connect", return_value=["DUP526287"])
    def test_connect_wrong_account(self, mock_connect, service):
        """Connection with non-existent account should fail."""
        conn = service.connect("user1", account_id="NONEXISTENT")

        assert conn.state == IBKRConnectionState.ERROR
        assert "not found" in conn.error_message

    @patch.object(
        _IBConnection, "connect",
        side_effect=ConnectionError("IB Gateway connection failed: Connection refused"),
    )
    def test_connect_gateway_down(self, mock_connect, service):
        """Connection when Gateway is down returns ERROR state (doesn't crash)."""
        conn = service.connect("user1")

        assert conn.state == IBKRConnectionState.ERROR
        assert "Connection refused" in conn.error_message

    @patch.object(_IBConnection, "connect", return_value=["DUP526287"])
    def test_connect_paper_detection(self, mock_connect, service):
        """DU-prefixed accounts detected as paper."""
        conn = service.connect("user1", account_id="DUP526287")
        assert conn.is_paper is True

    @patch.object(_IBConnection, "connect", return_value=["U1234567"])
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

    @patch.object(_IBConnection, "connect", return_value=["DUP526287"])
    def test_reconnect_disconnects_old(self, mock_connect, service):
        """Reconnecting should disconnect the old connection first."""
        mock_ib = _make_mock_ib()
        old_ibc = _patch_ibc_connect(service, "user1", mock_ib)

        conn = service.connect("user1")
        assert conn.state == IBKRConnectionState.CONNECTED
        old_ibc.disconnect.assert_called_once()

    @patch.object(_IBConnection, "connect", return_value=["DUP526287"])
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

        mock_ib.placeOrder.return_value = mock_trade

        ibc = _patch_ibc_connect(svc, "user1", mock_ib)
        # Make _import_ib_insync return a proper mock module
        ibc._import_ib_insync = staticmethod(_mock_ib_insync_module)

        svc._mock_ib = mock_ib  # stash for assertions
        return svc

    def test_submit_market_buy(self, service):
        """Market buy should place order and return fill data."""
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
        assert order.order_type == "MARKET"
        assert order.status == "FILLED"
        assert order.filled_price == 185.50
        assert order.filled_at is not None
        assert order.is_paper is True

    def test_submit_market_sell(self, service):
        """Market sell should work."""
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
        """Limit order should use LimitOrder."""
        mock_mod = _mock_ib_insync_module()
        with patch.object(_IBConnection, "_import_ib_insync", return_value=mock_mod):
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
            service.submit_order("user1", "AAPL", "BUY", 10, order_type="STOP")

    def test_limit_order_requires_price(self, service):
        """Limit order without price should fail."""
        with pytest.raises(ValueError, match="Limit price required"):
            service.submit_order("user1", "AAPL", "BUY", 10, order_type="LIMIT")

    def test_order_to_dict(self, service):
        """Order serialization includes all fields."""
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

    def test_order_pending_status(self):
        """Order that doesn't fill should return PENDING/SUBMITTED."""
        svc = IBKRService()
        mock_ib = _make_mock_ib()

        mock_order_status = MagicMock()
        mock_order_status.status = "Submitted"
        mock_order_status.avgFillPrice = 0.0

        mock_order_obj = MagicMock()
        mock_order_obj.orderId = 99

        mock_trade = MagicMock()
        mock_trade.orderStatus = mock_order_status
        mock_trade.order = mock_order_obj
        mock_trade.fills = []

        mock_ib.placeOrder.return_value = mock_trade
        _patch_ibc_connect(svc, "user1", mock_ib)

        with patch.object(_IBConnection, "_import_ib_insync", return_value=_mock_ib_insync_module()):
            order = svc.submit_order("user1", "AAPL", "BUY", 10)

        assert order.status == "SUBMITTED"
        assert order.filled_price is None

    def test_order_placement_failure(self):
        """Order placement exception should raise ValueError."""
        svc = IBKRService()
        mock_ib = _make_mock_ib()
        mock_ib.placeOrder.side_effect = Exception("Insufficient funds")
        _patch_ibc_connect(svc, "user1", mock_ib)

        with patch.object(_IBConnection, "_import_ib_insync", return_value=_mock_ib_insync_module()):
            with pytest.raises(ValueError, match="Order placement failed"):
                svc.submit_order("user1", "AAPL", "BUY", 10)


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

        with patch.object(_IBConnection, "_import_ib_insync", return_value=_mock_ib_insync_module()):
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

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
