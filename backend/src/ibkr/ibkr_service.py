"""
F6.3 IBKR Service — real IB Gateway integration via ib_insync.

Manages IB Gateway connections per user, live order submission,
position retrieval, and account summary.
"""

import logging
import os
import threading
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)

# ── Patch asyncio early (before any event loop starts) ──────────────────
try:
    import nest_asyncio
    nest_asyncio.apply()
except ImportError:
    pass

# ── Configuration (env-overridable) ─────────────────────────────────────

IB_GATEWAY_HOST = os.environ.get("IB_GATEWAY_HOST", "127.0.0.1")
IB_GATEWAY_PORT = int(os.environ.get("IB_GATEWAY_PORT", "4002"))
IB_ACCOUNT_ID = os.environ.get("IB_ACCOUNT_ID", "DUP526287")

# Base clientId — each user connection gets base + offset
_IB_CLIENT_ID_BASE = 10
_client_id_counter = 0
_client_id_lock = threading.Lock()


def _next_client_id() -> int:
    """Thread-safe incrementing clientId allocator."""
    global _client_id_counter
    with _client_id_lock:
        _client_id_counter += 1
        return _IB_CLIENT_ID_BASE + _client_id_counter


# ── Data Classes (interface unchanged) ──────────────────────────────────

class IBKRConnectionState(str, Enum):
    """IBKR connection status."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


@dataclass
class IBKRConnection:
    """Per-user IBKR connection state."""
    user_id: str
    account_id: Optional[str] = None
    state: IBKRConnectionState = IBKRConnectionState.DISCONNECTED
    is_paper: bool = False
    connected_at: Optional[str] = None
    error_message: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "account_id": self.account_id,
            "state": self.state.value,
            "is_paper": self.is_paper,
            "connected_at": self.connected_at,
            "error_message": self.error_message,
        }


@dataclass
class IBKROrder:
    """An IBKR order result."""
    order_id: str
    ticker: str
    side: str
    quantity: float
    order_type: str
    status: str
    filled_price: Optional[float] = None
    filled_at: Optional[str] = None
    is_paper: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class IBKRPosition:
    """An IBKR position."""
    ticker: str
    quantity: float
    avg_cost: float
    market_value: float
    unrealized_pnl: float

    def to_dict(self) -> dict:
        return asdict(self)


# ── IB Connection Wrapper (thread-safe) ─────────────────────────────────

class _IBConnection:
    """
    Wraps an ib_insync.IB instance running in a single persistent worker thread.

    ALL IB operations are dispatched to this thread via a queue, ensuring
    the IB object is only ever accessed from one thread/event-loop.
    """

    def __init__(self, host: str, port: int, client_id: int):
        self.host = host
        self.port = port
        self.client_id = client_id
        self._ib = None
        self._connected = False
        import queue
        self._queue = queue.Queue()
        self._thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._thread.start()

    @staticmethod
    def _import_ib_insync():
        """Import ib_insync (nest_asyncio already applied at module level)."""
        import ib_insync as _ibi
        return _ibi

    def _worker_loop(self):
        """Persistent worker thread — processes all IB operations sequentially."""
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            import nest_asyncio
            nest_asyncio.apply(loop)
        except ImportError:
            pass

        while True:
            item = self._queue.get()
            if item is None:
                break
            func, result_holder = item
            try:
                result_holder["result"] = func()
            except Exception as exc:
                result_holder["error"] = exc
            finally:
                result_holder["event"].set()

    def _dispatch(self, func, timeout=30):
        """Submit func to worker thread and wait for result."""
        import queue
        holder = {"result": None, "error": None, "event": threading.Event()}
        self._queue.put((func, holder))
        holder["event"].wait(timeout=timeout)
        if holder["error"] is not None:
            raise holder["error"]
        return holder["result"]

    def connect(self) -> List[str]:
        """Connect to IB Gateway. Returns list of managed accounts."""
        def _do():
            ibi = self._import_ib_insync()
            if self._ib is not None and self._ib.isConnected():
                return list(self._ib.managedAccounts())
            self._ib = ibi.IB()
            try:
                self._ib.connect(
                    self.host, self.port,
                    clientId=self.client_id, timeout=10, readonly=False,
                )
                accounts = list(self._ib.managedAccounts())
                self._connected = True
                logger.info("IB Gateway connected (clientId=%d, accounts=%s)", self.client_id, accounts)
                return accounts
            except Exception as exc:
                self._ib = None
                self._connected = False
                logger.error("IB Gateway connection failed: %s", exc)
                raise ConnectionError(f"IB Gateway connection failed: {exc}") from exc
        return self._dispatch(_do)

    def disconnect(self):
        def _do():
            if self._ib is not None:
                try:
                    self._ib.disconnect()
                except Exception:
                    pass
                self._ib = None
                self._connected = False
                logger.info("IB Gateway disconnected (clientId=%d)", self.client_id)
        self._dispatch(_do, timeout=10)

    @property
    def is_connected(self) -> bool:
        if not self._connected:
            return False
        try:
            def _check():
                return self._ib is not None and self._ib.isConnected()
            return self._dispatch(_check, timeout=5)
        except Exception:
            return False

    def run_ib(self, func):
        """Run func(ib) in the worker thread where the IB object lives."""
        def _do():
            return func(self._ib)
        return self._dispatch(_do)


# ── Service ─────────────────────────────────────────────────────────────

class IBKRService:
    """
    IBKR IB Gateway wrapper using ib_insync.

    Connects to a locally-running IB Gateway / TWS instance,
    manages per-user connections, submits real orders, and
    retrieves live positions and account data.
    """

    def __init__(
        self,
        host: str = IB_GATEWAY_HOST,
        port: int = IB_GATEWAY_PORT,
        default_account: str = IB_ACCOUNT_ID,
    ):
        self._host = host
        self._port = port
        self._default_account = default_account

        # Per-user state
        self._connections: Dict[str, IBKRConnection] = {}
        self._ib_connections: Dict[str, _IBConnection] = {}

    # -- helpers -----------------------------------------------------------

    def get_connection(self, user_id: str) -> IBKRConnection:
        """Get connection state for a user (creates default if absent)."""
        if user_id not in self._connections:
            self._connections[user_id] = IBKRConnection(user_id=user_id)
        return self._connections[user_id]

    def _get_ib(self, user_id: str) -> _IBConnection:
        """Get the live IB wrapper for a user. Raises ValueError if not connected."""
        ibc = self._ib_connections.get(user_id)
        if ibc is None or not ibc.is_connected:
            raise ValueError("IBKR not connected. Please connect first.")
        return ibc

    # -- connect / disconnect / status ------------------------------------

    def connect(self, user_id: str, account_id: Optional[str] = None) -> IBKRConnection:
        """
        Connect to IB Gateway for the given user.

        Creates a new ib_insync.IB() instance, connects to the Gateway,
        and verifies the account_id is among managed accounts.
        """
        conn = self.get_connection(user_id)
        resolved_account = account_id or self._default_account

        conn.state = IBKRConnectionState.CONNECTING
        conn.error_message = None

        # Disconnect any existing connection for this user first
        old_ibc = self._ib_connections.pop(user_id, None)
        if old_ibc is not None:
            old_ibc.disconnect()

        client_id = _next_client_id()
        ibc = _IBConnection(self._host, self._port, client_id)

        try:
            managed = ibc.connect()
        except ConnectionError as exc:
            conn.state = IBKRConnectionState.ERROR
            conn.error_message = str(exc)
            return conn

        # Verify account
        if resolved_account not in managed:
            ibc.disconnect()
            conn.state = IBKRConnectionState.ERROR
            conn.error_message = (
                f"Account {resolved_account} not found in managed accounts: {managed}"
            )
            return conn

        # Store
        self._ib_connections[user_id] = ibc
        conn.account_id = resolved_account
        conn.state = IBKRConnectionState.CONNECTED
        conn.is_paper = resolved_account.startswith("DU")
        conn.connected_at = datetime.now().isoformat()
        conn.error_message = None

        logger.info("User %s connected to IBKR account %s", user_id, resolved_account)
        return conn

    def disconnect(self, user_id: str) -> IBKRConnection:
        """Disconnect from IB Gateway."""
        conn = self.get_connection(user_id)

        ibc = self._ib_connections.pop(user_id, None)
        if ibc is not None:
            ibc.disconnect()

        conn.state = IBKRConnectionState.DISCONNECTED
        conn.account_id = None
        conn.is_paper = False
        conn.connected_at = None
        conn.error_message = None

        logger.info("User %s disconnected from IBKR", user_id)
        return conn

    def get_status(self, user_id: str) -> IBKRConnection:
        """Get current IBKR connection status (checks live state)."""
        conn = self.get_connection(user_id)

        # Reconcile: if we think we're connected but IB dropped, update
        ibc = self._ib_connections.get(user_id)
        if conn.state == IBKRConnectionState.CONNECTED:
            if ibc is None or not ibc.is_connected:
                conn.state = IBKRConnectionState.DISCONNECTED
                conn.error_message = "Connection lost"

        return conn

    # -- orders -----------------------------------------------------------

    def submit_order(
        self,
        user_id: str,
        ticker: str,
        side: str,
        quantity: float,
        order_type: str = "MARKET",
        limit_price: Optional[float] = None,
    ) -> IBKROrder:
        """
        Submit a real order to IB Gateway.

        Creates a Stock contract on SMART/USD, builds a Market or Limit order,
        places it, and waits briefly for a fill.
        """
        # Validate inputs
        conn = self.get_connection(user_id)
        if conn.state != IBKRConnectionState.CONNECTED:
            raise ValueError("IBKR not connected. Please connect first.")

        if quantity <= 0:
            raise ValueError("Quantity must be positive")

        side_upper = side.upper()
        if side_upper not in ("BUY", "SELL"):
            raise ValueError(f"Invalid side: {side}. Must be BUY or SELL.")

        order_type_upper = order_type.upper()
        if order_type_upper not in ("MARKET", "LIMIT"):
            raise ValueError(f"Invalid order type: {order_type}")

        if order_type_upper == "LIMIT" and limit_price is None:
            raise ValueError("Limit price required for LIMIT orders")

        ibc = self._get_ib(user_id)
        ibi = _IBConnection._import_ib_insync()
        _ticker = ticker.upper()

        def _place(ib):
            contract = ibi.Stock(_ticker, "SMART", "USD")

            if order_type_upper == "MARKET":
                ib_order = ibi.MarketOrder(side_upper, quantity)
            else:
                ib_order = ibi.LimitOrder(side_upper, quantity, limit_price)

            trade = ib.placeOrder(contract, ib_order)
            logger.info(
                "Order placed: %s %s x%.0f %s (orderId=%s)",
                side_upper, _ticker, quantity, order_type_upper,
                trade.order.orderId,
            )

            for _ in range(4):
                ib.sleep(0.5)
                if trade.orderStatus.status in ("Filled", "Cancelled", "Inactive"):
                    break

            return trade

        try:
            trade = ibc.run_ib(_place)
        except Exception as exc:
            logger.error("Order placement failed: %s", exc)
            raise ValueError(f"Order placement failed: {exc}") from exc

        # Map status
        ib_status = trade.orderStatus.status
        status_map = {
            "Filled": "FILLED",
            "Submitted": "SUBMITTED",
            "PreSubmitted": "SUBMITTED",
            "Cancelled": "CANCELLED",
            "Inactive": "REJECTED",
        }
        mapped_status = status_map.get(ib_status, "PENDING")

        filled_price = None
        filled_at = None
        if mapped_status == "FILLED":
            filled_price = trade.orderStatus.avgFillPrice
            if trade.fills:
                filled_at = trade.fills[-1].time.isoformat() if trade.fills[-1].time else None
            if not filled_at:
                filled_at = datetime.now().isoformat()

        order = IBKROrder(
            order_id=str(trade.order.orderId),
            ticker=ticker.upper(),
            side=side_upper,
            quantity=quantity,
            order_type=order_type_upper,
            status=mapped_status,
            filled_price=filled_price,
            filled_at=filled_at,
            is_paper=conn.is_paper,
        )

        logger.info(
            "Order result: %s %s status=%s fill=%.2f",
            order.side, order.ticker, order.status, order.filled_price or 0.0,
        )
        return order

    # -- positions --------------------------------------------------------

    def get_positions(self, user_id: str) -> List[IBKRPosition]:
        """
        Get real positions from IB Gateway.

        Returns a list of IBKRPosition with live data.
        """
        conn = self.get_connection(user_id)
        if conn.state != IBKRConnectionState.CONNECTED:
            raise ValueError("IBKR not connected. Please connect first.")

        ibc = self._get_ib(user_id)

        def _fetch_positions(ib):
            ib.sleep(0.5)
            raw_positions = ib.positions()
            portfolio_items = []
            try:
                ib.sleep(0.2)
                portfolio_items = ib.portfolio()
            except Exception:
                pass
            return raw_positions, portfolio_items

        raw_positions, portfolio_items = ibc.run_ib(_fetch_positions)

        # Build portfolio lookup
        pf_map = {}
        for item in portfolio_items:
            pf_map[item.contract.symbol] = item

        positions: List[IBKRPosition] = []
        for pos in raw_positions:
            ticker = pos.contract.symbol
            qty = float(pos.position)
            avg = float(pos.avgCost)
            market_value = qty * avg
            unrealized_pnl = 0.0

            if ticker in pf_map:
                market_value = float(pf_map[ticker].marketValue)
                unrealized_pnl = float(pf_map[ticker].unrealizedPNL)

            positions.append(IBKRPosition(
                ticker=ticker,
                quantity=qty,
                avg_cost=avg,
                market_value=market_value,
                unrealized_pnl=unrealized_pnl,
            ))

        return positions

    # -- account summary --------------------------------------------------

    def get_account_summary(self, user_id: str) -> dict:
        """
        Get account summary from IB Gateway.

        Returns dict with keys like NetLiquidation, TotalCashValue,
        BuyingPower, GrossPositionValue, etc.
        """
        conn = self.get_connection(user_id)
        if conn.state != IBKRConnectionState.CONNECTED:
            raise ValueError("IBKR not connected. Please connect first.")

        ibc = self._get_ib(user_id)
        account_id = conn.account_id

        def _fetch_summary(ib):
            ib.sleep(0.5)
            return ib.accountSummary(account=account_id)

        try:
            summary_items = ibc.run_ib(_fetch_summary)
        except Exception as exc:
            logger.error("Account summary failed: %s", exc)
            raise ValueError(f"Failed to retrieve account summary: {exc}") from exc

        # Group by tag
        result: Dict[str, str] = {}
        for item in summary_items:
            result[item.tag] = item.value

        return {
            "account_id": conn.account_id,
            "is_paper": conn.is_paper,
            "net_liquidation": float(result.get("NetLiquidation", 0)),
            "total_cash": float(result.get("TotalCashValue", 0)),
            "buying_power": float(result.get("BuyingPower", 0)),
            "gross_position_value": float(result.get("GrossPositionValue", 0)),
            "unrealized_pnl": float(result.get("UnrealizedPnL", 0)),
            "realized_pnl": float(result.get("RealizedPnL", 0)),
            "currency": result.get("Currency", "USD"),
            "raw": result,
        }


# ========== Global Instance ==========

_ibkr_service: Optional[IBKRService] = None


def get_ibkr_service() -> IBKRService:
    """Get or create the global IBKR service."""
    global _ibkr_service
    if _ibkr_service is None:
        _ibkr_service = IBKRService()
    return _ibkr_service
