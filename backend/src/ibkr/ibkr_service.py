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

# Import push notification service for fill notifications (REC-141)
try:
    from notifications.push_service import send_order_fill_notification
    PUSH_AVAILABLE = True
except ImportError:
    PUSH_AVAILABLE = False
    logger.warning("Push notifications not available for order fills")

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
        trailing_percent: Optional[float] = None,
        trailing_amount: Optional[float] = None,
        outside_rth: bool = False,
        tif: str = "DAY",
        good_till_date: Optional[str] = None,
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
        valid_types = ("MARKET", "LIMIT", "STP", "STOP", "STP_LMT", "STOP_LIMIT", "TRAIL", "TRAILING")
        if order_type_upper not in valid_types:
            raise ValueError(f"Invalid order type: {order_type}")

        # Normalize order types
        if order_type_upper in ("STOP", "STP"):
            order_type_upper = "STP"
        elif order_type_upper in ("STOP_LIMIT", "STP_LMT"):
            order_type_upper = "STP_LMT"
        elif order_type_upper in ("TRAIL", "TRAILING"):
            order_type_upper = "TRAIL"

        # Validate TIF
        tif_upper = tif.upper()
        valid_tif = ("DAY", "GTC", "GTD", "IOC", "FOK")
        if tif_upper not in valid_tif:
            raise ValueError(f"Invalid time-in-force: {tif}. Valid: {valid_tif}")

        if tif_upper == "GTD" and not good_till_date:
            raise ValueError("good_till_date required for GTD orders (format: YYYYMMDD HH:MM:SS)")

        if order_type_upper == "LIMIT" and limit_price is None:
            raise ValueError("Limit price required for LIMIT orders")
        if order_type_upper in ("STP", "STP_LMT") and limit_price is None:
            raise ValueError("Stop price required for STOP orders")
        if order_type_upper == "TRAIL" and trailing_percent is None and trailing_amount is None:
            raise ValueError("trailing_percent or trailing_amount required for TRAIL orders")

        ibc = self._get_ib(user_id)
        ibi = _IBConnection._import_ib_insync()
        _ticker = ticker.upper()

        def _place(ib):
            contract = ibi.Stock(_ticker, "SMART", "USD")

            if order_type_upper == "MARKET":
                ib_order = ibi.MarketOrder(side_upper, quantity)
            elif order_type_upper == "LIMIT":
                ib_order = ibi.LimitOrder(side_upper, quantity, limit_price)
            elif order_type_upper == "STP":
                ib_order = ibi.StopOrder(side_upper, quantity, limit_price)
            elif order_type_upper == "STP_LMT":
                ib_order = ibi.StopLimitOrder(side_upper, quantity, limit_price, limit_price)
            elif order_type_upper == "TRAIL":
                # Trailing stop order
                ib_order = ibi.Order()
                ib_order.action = side_upper
                ib_order.totalQuantity = quantity
                ib_order.orderType = "TRAIL"
                if trailing_percent:
                    ib_order.trailingPercent = trailing_percent
                elif trailing_amount:
                    ib_order.auxPrice = trailing_amount
            else:
                ib_order = ibi.MarketOrder(side_upper, quantity)

            # Apply time-in-force (REC-146)
            ib_order.tif = tif_upper
            if tif_upper == "GTD" and good_till_date:
                ib_order.goodTillDate = good_till_date

            # Apply extended hours (REC-145)
            if outside_rth:
                ib_order.outsideRth = True

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

        # REC-141: Send push notification on order fill
        if mapped_status == "FILLED" and filled_price and PUSH_AVAILABLE:
            try:
                send_order_fill_notification(
                    user_id=user_id,
                    ticker=ticker.upper(),
                    side=side_upper,
                    quantity=quantity,
                    fill_price=filled_price,
                    order_type=order_type_upper,
                    is_paper=conn.is_paper,
                )
                logger.info("Fill notification sent for order %s", order.order_id)
            except Exception as e:
                logger.warning("Failed to send fill notification: %s", e)

        return order

    def cancel_order(self, user_id: str, order_id: str) -> dict:
        """
        Cancel an open order via IB Gateway.

        Returns dict with cancellation status.
        """
        conn = self.get_connection(user_id)
        if conn.state != IBKRConnectionState.CONNECTED:
            raise ValueError("IBKR not connected. Please connect first.")

        ibc = self._get_ib(user_id)

        def _cancel(ib):
            # Find the order by orderId
            open_orders = ib.openOrders()
            target_order = None
            for order in open_orders:
                if str(order.orderId) == str(order_id):
                    target_order = order
                    break

            if target_order is None:
                raise ValueError(f"Order {order_id} not found or already filled/cancelled")

            # Cancel it
            ib.cancelOrder(target_order)
            ib.sleep(0.5)

            return {"order_id": str(order_id), "status": "CANCEL_REQUESTED"}

        try:
            result = ibc.run_ib(_cancel)
            logger.info("Order %s cancellation requested", order_id)
            return result
        except Exception as exc:
            logger.error("Order cancellation failed: %s", exc)
            raise ValueError(f"Order cancellation failed: {exc}") from exc

    def get_open_orders(self, user_id: str) -> List[IBKROrder]:
        """
        Get all open (pending) orders from IB Gateway.

        Returns list of IBKROrder for orders not yet filled.
        """
        conn = self.get_connection(user_id)
        if conn.state != IBKRConnectionState.CONNECTED:
            raise ValueError("IBKR not connected. Please connect first.")

        ibc = self._get_ib(user_id)

        def _fetch_orders(ib):
            ib.sleep(0.3)
            trades = ib.openTrades()
            return trades

        try:
            trades = ibc.run_ib(_fetch_orders)
        except Exception as exc:
            logger.error("Failed to fetch open orders: %s", exc)
            raise ValueError(f"Failed to fetch open orders: {exc}") from exc

        orders: List[IBKROrder] = []
        for trade in trades:
            order = trade.order
            contract = trade.contract
            status = trade.orderStatus

            # Map order type
            order_type_map = {
                "MKT": "MARKET",
                "LMT": "LIMIT",
                "STP": "STP",
                "STP LMT": "STP_LMT",
            }
            order_type = order_type_map.get(order.orderType, order.orderType)

            # Map status
            status_map = {
                "Filled": "FILLED",
                "Submitted": "SUBMITTED",
                "PreSubmitted": "SUBMITTED",
                "Cancelled": "CANCELLED",
                "Inactive": "REJECTED",
            }
            mapped_status = status_map.get(status.status, "PENDING")

            orders.append(IBKROrder(
                order_id=str(order.orderId),
                ticker=contract.symbol,
                side=order.action,
                quantity=float(order.totalQuantity),
                order_type=order_type,
                status=mapped_status,
                filled_price=float(status.avgFillPrice) if status.avgFillPrice else None,
                filled_at=None,
                is_paper=conn.is_paper,
            ))

        return orders

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

    # -- real-time quotes (REC-140) --------------------------------------

    def get_quote(self, user_id: str, ticker: str) -> dict:
        """
        Get real-time quote from IB Gateway.

        Returns current bid, ask, last price, volume, etc.
        Much faster and more reliable than Yahoo Finance polling.
        """
        conn = self.get_connection(user_id)
        if conn.state != IBKRConnectionState.CONNECTED:
            raise ValueError("IBKR not connected. Please connect first.")

        ibc = self._get_ib(user_id)
        ibi = _IBConnection._import_ib_insync()
        _ticker = ticker.upper()

        def _get_quote(ib):
            contract = ibi.Stock(_ticker, "SMART", "USD")
            ib.qualifyContracts(contract)

            # Request market data snapshot
            ticker_data = ib.reqMktData(contract, snapshot=True)
            ib.sleep(1.5)  # Wait for data to arrive

            # Extract the data
            result = {
                "ticker": _ticker,
                "bid": ticker_data.bid if ticker_data.bid and ticker_data.bid > 0 else None,
                "ask": ticker_data.ask if ticker_data.ask and ticker_data.ask > 0 else None,
                "last": ticker_data.last if ticker_data.last and ticker_data.last > 0 else None,
                "close": ticker_data.close if ticker_data.close and ticker_data.close > 0 else None,
                "high": ticker_data.high if ticker_data.high and ticker_data.high > 0 else None,
                "low": ticker_data.low if ticker_data.low and ticker_data.low > 0 else None,
                "volume": int(ticker_data.volume) if ticker_data.volume and ticker_data.volume > 0 else None,
                "timestamp": datetime.now().isoformat(),
            }

            # Calculate mid price
            if result["bid"] and result["ask"]:
                result["mid"] = (result["bid"] + result["ask"]) / 2

            # Use last price or close as the "price" field
            result["price"] = result["last"] or result["close"]

            # Cancel the market data subscription
            ib.cancelMktData(contract)

            return result

        try:
            quote = ibc.run_ib(_get_quote)
            logger.info("Quote for %s: price=%.2f", _ticker, quote.get("price") or 0)
            return quote
        except Exception as exc:
            logger.error("Failed to get quote for %s: %s", _ticker, exc)
            raise ValueError(f"Failed to get quote for {_ticker}: {exc}") from exc

    # -- historical bars (REC-160) ---------------------------------------

    def get_historical_bars(
        self,
        user_id: str,
        ticker: str,
        duration: str = "1 D",
        bar_size: str = "5 mins",
        what_to_show: str = "TRADES",
        use_rth: bool = True,
    ) -> List[dict]:
        """
        Get historical OHLCV bars from IB Gateway (REC-160).

        Better data quality than Yahoo Finance, real-time during market hours.

        Args:
            ticker: Stock symbol
            duration: Time span (e.g., '1 D', '1 W', '1 M', '1 Y')
            bar_size: Bar period ('1 min', '5 mins', '15 mins', '1 hour', '1 day')
            what_to_show: Data type ('TRADES', 'MIDPOINT', 'BID', 'ASK')
            use_rth: If True, only regular trading hours data

        Returns:
            List of bar dicts with date, open, high, low, close, volume
        """
        conn = self.get_connection(user_id)
        if conn.state != IBKRConnectionState.CONNECTED:
            raise ValueError("IBKR not connected. Please connect first.")

        ibc = self._get_ib(user_id)
        ibi = _IBConnection._import_ib_insync()
        _ticker = ticker.upper()

        def _fetch_bars(ib):
            contract = ibi.Stock(_ticker, "SMART", "USD")
            ib.qualifyContracts(contract)

            bars = ib.reqHistoricalData(
                contract,
                endDateTime="",  # Current time
                durationStr=duration,
                barSizeSetting=bar_size,
                whatToShow=what_to_show,
                useRTH=use_rth,
                formatDate=2,  # UTC datetime
            )

            return bars

        try:
            bars = ibc.run_ib(_fetch_bars)
        except Exception as exc:
            logger.error("Failed to fetch historical bars for %s: %s", _ticker, exc)
            raise ValueError(f"Failed to fetch historical bars: {exc}") from exc

        # Convert to list of dicts
        result = []
        for bar in bars:
            result.append({
                "date": bar.date.isoformat() if hasattr(bar.date, 'isoformat') else str(bar.date),
                "open": float(bar.open),
                "high": float(bar.high),
                "low": float(bar.low),
                "close": float(bar.close),
                "volume": int(bar.volume),
            })

        logger.info("Fetched %d bars for %s (%s, %s)", len(result), _ticker, duration, bar_size)
        return result

    # -- bracket orders (REC-161) -----------------------------------------

    def submit_bracket_order(
        self,
        user_id: str,
        ticker: str,
        side: str,
        quantity: float,
        entry_price: float,
        take_profit_price: float,
        stop_loss_price: float,
        outside_rth: bool = False,
    ) -> dict:
        """
        Submit a bracket order (entry + take-profit + stop-loss) to IB Gateway (REC-161).

        All three orders are linked - if one fills/cancels, the others adjust.

        Args:
            ticker: Stock symbol
            side: BUY or SELL
            quantity: Number of shares
            entry_price: Limit price for entry order
            take_profit_price: Limit price for profit target
            stop_loss_price: Stop price for loss protection

        Returns:
            Dict with entry, take_profit, and stop_loss order details
        """
        conn = self.get_connection(user_id)
        if conn.state != IBKRConnectionState.CONNECTED:
            raise ValueError("IBKR not connected. Please connect first.")

        if quantity <= 0:
            raise ValueError("Quantity must be positive")

        side_upper = side.upper()
        if side_upper not in ("BUY", "SELL"):
            raise ValueError(f"Invalid side: {side}. Must be BUY or SELL.")

        # Validate prices make sense
        if side_upper == "BUY":
            if take_profit_price <= entry_price:
                raise ValueError("Take profit must be above entry price for BUY")
            if stop_loss_price >= entry_price:
                raise ValueError("Stop loss must be below entry price for BUY")
        else:
            if take_profit_price >= entry_price:
                raise ValueError("Take profit must be below entry price for SELL")
            if stop_loss_price <= entry_price:
                raise ValueError("Stop loss must be above entry price for SELL")

        ibc = self._get_ib(user_id)
        ibi = _IBConnection._import_ib_insync()
        _ticker = ticker.upper()

        def _place_bracket(ib):
            contract = ibi.Stock(_ticker, "SMART", "USD")
            ib.qualifyContracts(contract)

            # Create bracket order using IB's helper
            bracket = ib.bracketOrder(
                action=side_upper,
                quantity=quantity,
                limitPrice=entry_price,
                takeProfitPrice=take_profit_price,
                stopLossPrice=stop_loss_price,
            )

            # Apply extended hours if requested
            if outside_rth:
                for order in bracket:
                    order.outsideRth = True

            # Place all three orders
            trades = []
            for order in bracket:
                trade = ib.placeOrder(contract, order)
                trades.append(trade)
                ib.sleep(0.2)

            # Wait briefly for status updates
            ib.sleep(1.0)

            return trades

        try:
            trades = ibc.run_ib(_place_bracket)
        except Exception as exc:
            logger.error("Bracket order failed: %s", exc)
            raise ValueError(f"Bracket order failed: {exc}") from exc

        # Build result with all three orders
        def trade_to_dict(trade, order_type):
            return {
                "order_id": str(trade.order.orderId),
                "order_type": order_type,
                "status": trade.orderStatus.status,
                "limit_price": getattr(trade.order, 'lmtPrice', None),
                "stop_price": getattr(trade.order, 'auxPrice', None),
            }

        result = {
            "ticker": _ticker,
            "side": side_upper,
            "quantity": quantity,
            "entry": trade_to_dict(trades[0], "ENTRY"),
            "take_profit": trade_to_dict(trades[1], "TAKE_PROFIT"),
            "stop_loss": trade_to_dict(trades[2], "STOP_LOSS"),
            "is_paper": conn.is_paper,
        }

        logger.info(
            "Bracket order placed: %s %s x%.0f entry=%.2f tp=%.2f sl=%.2f",
            side_upper, _ticker, quantity, entry_price, take_profit_price, stop_loss_price
        )

        return result

    # -- market scanner (REC-157) -----------------------------------------

    def get_scanner_results(
        self,
        user_id: str,
        scan_code: str = "TOP_PERC_GAIN",
        instrument: str = "STK",
        location: str = "STK.US.MAJOR",
        num_rows: int = 20,
        above_price: float = 5.0,
        below_price: float = 10000.0,
        above_volume: int = 100000,
        market_cap_above: float = 1e9,
    ) -> List[dict]:
        """
        Get market scanner results from IB Gateway (REC-157).

        Scan codes: TOP_PERC_GAIN, TOP_PERC_LOSE, MOST_ACTIVE, HOT_BY_VOLUME,
                    HIGH_VS_13W_HL, LOW_VS_13W_HL, HIGH_VS_52W_HL, LOW_VS_52W_HL

        Args:
            scan_code: Type of scan (default: TOP_PERC_GAIN)
            instrument: Instrument type (STK, FUT, etc.)
            location: Market location (STK.US.MAJOR, STK.NASDAQ, etc.)
            num_rows: Number of results (max 50)
            above_price: Minimum price filter
            below_price: Maximum price filter
            above_volume: Minimum volume filter
            market_cap_above: Minimum market cap filter

        Returns:
            List of scanner results with ticker, price, change, volume
        """
        conn = self.get_connection(user_id)
        if conn.state != IBKRConnectionState.CONNECTED:
            raise ValueError("IBKR not connected. Please connect first.")

        ibc = self._get_ib(user_id)
        ibi = _IBConnection._import_ib_insync()

        def _run_scanner(ib):
            subscription = ibi.ScannerSubscription(
                numberOfRows=min(num_rows, 50),
                instrument=instrument,
                locationCode=location,
                scanCode=scan_code,
                abovePrice=above_price,
                belowPrice=below_price,
                aboveVolume=above_volume,
                marketCapAbove=market_cap_above,
            )

            results = ib.reqScannerSubscription(subscription)
            ib.sleep(2.0)  # Wait for data

            # Cancel subscription after getting results
            ib.cancelScannerSubscription(results)

            return results

        try:
            scan_data = ibc.run_ib(_run_scanner)
        except Exception as exc:
            logger.error("Scanner failed: %s", exc)
            raise ValueError(f"Scanner failed: {exc}") from exc

        # Convert to list of dicts
        result = []
        for item in scan_data:
            contract = item.contractDetails.contract if item.contractDetails else None
            result.append({
                "rank": item.rank,
                "ticker": contract.symbol if contract else "N/A",
                "exchange": contract.exchange if contract else "N/A",
                "contract_id": contract.conId if contract else None,
                "distance": getattr(item, 'distance', None),
                "benchmark": getattr(item, 'benchmark', None),
                "projection": getattr(item, 'projection', None),
                "legs_str": getattr(item, 'legsStr', None),
            })

        logger.info("Scanner %s returned %d results", scan_code, len(result))
        return result

    # -- what-if order simulation (REC-162) -------------------------------

    def what_if_order(
        self,
        user_id: str,
        ticker: str,
        side: str,
        quantity: float,
        order_type: str = "MARKET",
        limit_price: Optional[float] = None,
    ) -> dict:
        """
        Simulate an order to preview margin impact without placing it (REC-162).

        Shows initial margin, maintenance margin, commission estimate.

        Args:
            ticker: Stock symbol
            side: BUY or SELL
            quantity: Number of shares
            order_type: MARKET or LIMIT
            limit_price: Required for LIMIT orders

        Returns:
            Dict with margin impact and commission estimate
        """
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
            raise ValueError("What-if only supports MARKET and LIMIT orders")

        if order_type_upper == "LIMIT" and limit_price is None:
            raise ValueError("Limit price required for LIMIT orders")

        ibc = self._get_ib(user_id)
        ibi = _IBConnection._import_ib_insync()
        _ticker = ticker.upper()

        def _simulate(ib):
            contract = ibi.Stock(_ticker, "SMART", "USD")
            ib.qualifyContracts(contract)

            if order_type_upper == "MARKET":
                order = ibi.MarketOrder(side_upper, quantity)
            else:
                order = ibi.LimitOrder(side_upper, quantity, limit_price)

            # Run what-if simulation
            order_state = ib.whatIfOrder(contract, order)
            return order_state

        try:
            state = ibc.run_ib(_simulate)
        except Exception as exc:
            logger.error("What-if simulation failed: %s", exc)
            raise ValueError(f"What-if simulation failed: {exc}") from exc

        # Parse the order state
        def safe_float(val):
            try:
                return float(val) if val else 0.0
            except (ValueError, TypeError):
                return 0.0

        result = {
            "ticker": _ticker,
            "side": side_upper,
            "quantity": quantity,
            "order_type": order_type_upper,
            "limit_price": limit_price,
            # Margin info
            "init_margin_before": safe_float(state.initMarginBefore),
            "init_margin_after": safe_float(state.initMarginAfter),
            "init_margin_change": safe_float(state.initMarginChange),
            "maint_margin_before": safe_float(state.maintMarginBefore),
            "maint_margin_after": safe_float(state.maintMarginAfter),
            "maint_margin_change": safe_float(state.maintMarginChange),
            "equity_with_loan_before": safe_float(state.equityWithLoanBefore),
            "equity_with_loan_after": safe_float(state.equityWithLoanAfter),
            "equity_with_loan_change": safe_float(state.equityWithLoanChange),
            # Commission
            "commission": safe_float(state.commission),
            "min_commission": safe_float(state.minCommission),
            "max_commission": safe_float(state.maxCommission),
            "commission_currency": state.commissionCurrency or "USD",
            # Warning messages
            "warning_text": state.warningText or None,
        }

        logger.info(
            "What-if: %s %s x%.0f - margin change: %.2f, commission: %.2f",
            side_upper, _ticker, quantity,
            result["init_margin_change"], result["commission"]
        )

        return result

    # -- trade history (REC-154) -----------------------------------------

    def get_trade_history(self, user_id: str) -> List[dict]:
        """
        Get trade execution history from IB Gateway (REC-154).

        Returns actual fills with timestamps, prices, commissions.
        More accurate than local order history.

        Returns:
            List of execution dicts with orderId, ticker, side, quantity,
            price, time, commission, etc.
        """
        conn = self.get_connection(user_id)
        if conn.state != IBKRConnectionState.CONNECTED:
            raise ValueError("IBKR not connected. Please connect first.")

        ibc = self._get_ib(user_id)

        def _fetch_history(ib):
            ib.sleep(0.3)
            fills = ib.fills()
            return fills

        try:
            fills = ibc.run_ib(_fetch_history)
        except Exception as exc:
            logger.error("Failed to fetch trade history: %s", exc)
            raise ValueError(f"Failed to fetch trade history: {exc}") from exc

        result = []
        for fill in fills:
            execution = fill.execution
            contract = fill.contract
            commission_report = fill.commissionReport

            result.append({
                "exec_id": execution.execId,
                "order_id": str(execution.orderId),
                "ticker": contract.symbol,
                "side": execution.side,
                "quantity": float(execution.shares),
                "price": float(execution.price),
                "avg_price": float(execution.avgPrice),
                "time": execution.time.isoformat() if execution.time else None,
                "exchange": execution.exchange,
                "commission": float(commission_report.commission) if commission_report else None,
                "realized_pnl": float(commission_report.realizedPNL) if commission_report and commission_report.realizedPNL else None,
                "currency": commission_report.currency if commission_report else "USD",
                "account": execution.acctNumber,
            })

        logger.info("Fetched %d trade executions", len(result))
        return result

    # -- daily loss limit (REC-152) ---------------------------------------

    # Per-user daily loss tracking
    _daily_loss_state: Dict[str, dict] = {}

    def get_daily_pnl(self, user_id: str) -> dict:
        """
        Get today's realized + unrealized PnL from IB Gateway (REC-152).

        Returns:
            Dict with daily_pnl, realized_pnl, unrealized_pnl, and trading_halted status.
        """
        conn = self.get_connection(user_id)
        if conn.state != IBKRConnectionState.CONNECTED:
            raise ValueError("IBKR not connected. Please connect first.")

        ibc = self._get_ib(user_id)
        account_id = conn.account_id

        def _fetch_pnl(ib):
            ib.sleep(0.3)
            # Get account values for PnL
            account_values = ib.accountSummary(account=account_id)
            return account_values

        try:
            values = ibc.run_ib(_fetch_pnl)
        except Exception as exc:
            logger.error("Failed to fetch daily PnL: %s", exc)
            raise ValueError(f"Failed to fetch daily PnL: {exc}") from exc

        # Parse account values
        pnl_data = {}
        for item in values:
            pnl_data[item.tag] = item.value

        realized = float(pnl_data.get("RealizedPnL", 0))
        unrealized = float(pnl_data.get("UnrealizedPnL", 0))
        net_liq = float(pnl_data.get("NetLiquidation", 0))

        # Get user's loss limit setting (default 5%)
        loss_limit_percent = self._get_user_loss_limit(user_id)
        loss_limit_amount = net_liq * (loss_limit_percent / 100)

        daily_pnl = realized + unrealized
        pnl_percent = (daily_pnl / net_liq * 100) if net_liq > 0 else 0

        # Check if trading should be halted
        trading_halted = daily_pnl < -loss_limit_amount

        # Store state for order blocking
        today = datetime.now().strftime("%Y-%m-%d")
        self._daily_loss_state[user_id] = {
            "date": today,
            "daily_pnl": daily_pnl,
            "trading_halted": trading_halted,
        }

        return {
            "daily_pnl": daily_pnl,
            "daily_pnl_percent": round(pnl_percent, 2),
            "realized_pnl": realized,
            "unrealized_pnl": unrealized,
            "net_liquidation": net_liq,
            "loss_limit_percent": loss_limit_percent,
            "loss_limit_amount": loss_limit_amount,
            "trading_halted": trading_halted,
            "is_paper": conn.is_paper,
        }

    def _get_user_loss_limit(self, user_id: str) -> float:
        """Get user's daily loss limit percentage (default 5%)."""
        # TODO: Load from user preferences in database
        # For now, use environment variable or default
        return float(os.environ.get("DAILY_LOSS_LIMIT_PERCENT", "5.0"))

    def set_daily_loss_limit(self, user_id: str, limit_percent: float) -> dict:
        """
        Set user's daily loss limit percentage (REC-152).

        Args:
            limit_percent: Maximum daily loss as percentage (e.g., 5.0 for 5%)

        Returns:
            Updated loss limit settings.
        """
        if limit_percent <= 0 or limit_percent > 100:
            raise ValueError("Loss limit must be between 0 and 100 percent")

        # TODO: Store in database per user
        # For now, just validate and return
        logger.info("User %s set daily loss limit to %.1f%%", user_id, limit_percent)

        return {
            "user_id": user_id,
            "loss_limit_percent": limit_percent,
            "message": f"Daily loss limit set to {limit_percent}%",
        }

    def is_trading_halted(self, user_id: str) -> bool:
        """Check if trading is halted due to daily loss limit."""
        state = self._daily_loss_state.get(user_id)
        if not state:
            return False

        today = datetime.now().strftime("%Y-%m-%d")
        if state.get("date") != today:
            # New day, reset
            return False

        return state.get("trading_halted", False)

    # -- volume spike detection (REC-159) ---------------------------------

    def get_volume_analysis(
        self,
        user_id: str,
        ticker: str,
        lookback_days: int = 20,
        spike_threshold: float = 2.0,
    ) -> dict:
        """
        Analyze volume for unusual activity (REC-159).

        Compares current volume to historical average to detect spikes.

        Args:
            ticker: Stock symbol
            lookback_days: Days of history for average (default 20)
            spike_threshold: Multiple of average to trigger spike (default 2.0x)

        Returns:
            Dict with current volume, average, ratio, and spike detection.
        """
        conn = self.get_connection(user_id)
        if conn.state != IBKRConnectionState.CONNECTED:
            raise ValueError("IBKR not connected. Please connect first.")

        ibc = self._get_ib(user_id)
        ibi = _IBConnection._import_ib_insync()
        _ticker = ticker.upper()

        def _analyze(ib):
            contract = ibi.Stock(_ticker, "SMART", "USD")
            ib.qualifyContracts(contract)

            # Get historical daily bars for volume average
            bars = ib.reqHistoricalData(
                contract,
                endDateTime="",
                durationStr=f"{lookback_days} D",
                barSizeSetting="1 day",
                whatToShow="TRADES",
                useRTH=True,
                formatDate=2,
            )

            # Get current quote for today's volume
            ticker_data = ib.reqMktData(contract, snapshot=True)
            ib.sleep(1.0)
            current_volume = int(ticker_data.volume) if ticker_data.volume else 0
            ib.cancelMktData(contract)

            return bars, current_volume

        try:
            bars, current_volume = ibc.run_ib(_analyze)
        except Exception as exc:
            logger.error("Volume analysis failed for %s: %s", _ticker, exc)
            raise ValueError(f"Volume analysis failed: {exc}") from exc

        # Calculate average volume
        if not bars:
            raise ValueError(f"No historical data for {_ticker}")

        volumes = [int(bar.volume) for bar in bars if bar.volume]
        avg_volume = sum(volumes) / len(volumes) if volumes else 0

        # Calculate ratio
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 0
        is_spike = volume_ratio >= spike_threshold

        result = {
            "ticker": _ticker,
            "current_volume": current_volume,
            "avg_volume": int(avg_volume),
            "volume_ratio": round(volume_ratio, 2),
            "lookback_days": lookback_days,
            "spike_threshold": spike_threshold,
            "is_spike": is_spike,
            "alert_level": "HIGH" if volume_ratio >= 3.0 else ("MEDIUM" if is_spike else None),
        }

        if is_spike:
            logger.info(
                "Volume spike detected: %s at %.1fx average",
                _ticker, volume_ratio
            )

        return result

    def check_watchlist_volume_spikes(
        self,
        user_id: str,
        tickers: List[str],
        spike_threshold: float = 2.0,
    ) -> List[dict]:
        """
        Check multiple tickers for volume spikes (REC-159).

        Args:
            tickers: List of stock symbols
            spike_threshold: Multiple of average to trigger spike

        Returns:
            List of tickers with spike data (only those with spikes).
        """
        spikes = []
        for ticker in tickers:
            try:
                analysis = self.get_volume_analysis(
                    user_id, ticker,
                    lookback_days=20,
                    spike_threshold=spike_threshold,
                )
                if analysis.get("is_spike"):
                    spikes.append(analysis)
            except Exception as e:
                logger.warning("Volume check failed for %s: %s", ticker, e)
                continue

        return spikes

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
