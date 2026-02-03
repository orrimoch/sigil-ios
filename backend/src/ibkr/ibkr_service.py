"""
F6.3 IBKR Service — wraps IBKR Client Portal API (mock mode for now).

Manages connection state per user, mock OAuth flow, and order submission.
"""

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, List


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


class IBKRService:
    """
    IBKR Client Portal API wrapper.

    Currently runs in mock mode — simulates OAuth connection and order fills.
    Will be replaced with real IBKR Client Portal REST API calls.
    """

    # Mock account ID for development
    MOCK_ACCOUNT_ID = "DU1234567"

    def __init__(self):
        # Per-user connection state: user_id -> IBKRConnection
        self._connections: Dict[str, IBKRConnection] = {}

    def get_connection(self, user_id: str) -> IBKRConnection:
        """Get connection state for a user."""
        if user_id not in self._connections:
            self._connections[user_id] = IBKRConnection(user_id=user_id)
        return self._connections[user_id]

    def connect(self, user_id: str, account_id: Optional[str] = None) -> IBKRConnection:
        """
        Mock OAuth connection to IBKR.

        In production, this would:
        1. Redirect user to IBKR OAuth page
        2. Handle callback with auth code
        3. Exchange for access token
        4. Store encrypted credentials

        For now, simulates immediate connection success.
        """
        conn = self.get_connection(user_id)

        # Use provided account_id or mock
        resolved_account_id = account_id or self.MOCK_ACCOUNT_ID

        conn.account_id = resolved_account_id
        conn.state = IBKRConnectionState.CONNECTED
        conn.is_paper = resolved_account_id.startswith("DU")  # DU = paper, U = live
        conn.connected_at = datetime.now().isoformat()
        conn.error_message = None

        return conn

    def disconnect(self, user_id: str) -> IBKRConnection:
        """Disconnect from IBKR."""
        conn = self.get_connection(user_id)
        conn.state = IBKRConnectionState.DISCONNECTED
        conn.account_id = None
        conn.is_paper = False
        conn.connected_at = None
        conn.error_message = None
        return conn

    def get_status(self, user_id: str) -> IBKRConnection:
        """Get current IBKR connection status."""
        return self.get_connection(user_id)

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
        Submit an order to IBKR (mock: returns simulated fill).

        In production, would POST to IBKR Client Portal /iserver/account/{id}/orders.
        """
        conn = self.get_connection(user_id)

        if conn.state != IBKRConnectionState.CONNECTED:
            raise ValueError("IBKR not connected. Please connect first.")

        if quantity <= 0:
            raise ValueError("Quantity must be positive")

        if side.upper() not in ("BUY", "SELL"):
            raise ValueError(f"Invalid side: {side}. Must be BUY or SELL.")

        if order_type.upper() not in ("MARKET", "LIMIT"):
            raise ValueError(f"Invalid order type: {order_type}")

        if order_type.upper() == "LIMIT" and limit_price is None:
            raise ValueError("Limit price required for LIMIT orders")

        # Mock fill: simulate immediate execution at a reasonable price
        mock_price = limit_price if limit_price else self._mock_price(ticker)

        order = IBKROrder(
            order_id=f"IBKR-{str(uuid.uuid4())[:8]}",
            ticker=ticker.upper(),
            side=side.upper(),
            quantity=quantity,
            order_type=order_type.upper(),
            status="FILLED",
            filled_price=mock_price,
            filled_at=datetime.now().isoformat(),
            is_paper=conn.is_paper,
        )

        return order

    def get_positions(self, user_id: str) -> List[IBKRPosition]:
        """
        Get IBKR positions (mock: returns empty list).

        In production, would GET from IBKR Client Portal /portfolio/{id}/positions.
        """
        conn = self.get_connection(user_id)

        if conn.state != IBKRConnectionState.CONNECTED:
            raise ValueError("IBKR not connected. Please connect first.")

        # Mock: return empty positions for now
        return []

    def _mock_price(self, ticker: str) -> float:
        """Generate a mock fill price for a ticker."""
        # Simple hash-based mock price for consistency
        hash_val = sum(ord(c) for c in ticker)
        return round(100 + (hash_val % 400) + (hash_val % 100) / 100, 2)


# ========== Global Instance ==========

_ibkr_service: Optional[IBKRService] = None


def get_ibkr_service() -> IBKRService:
    """Get or create the global IBKR service."""
    global _ibkr_service
    if _ibkr_service is None:
        _ibkr_service = IBKRService()
    return _ibkr_service
