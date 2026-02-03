"""
F6.1 & F6.4 Order Management

Create, execute, and track orders.
"""

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, List
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from data.price_fetcher import fetch_latest_price
from trading.portfolio import get_portfolio, Portfolio


# Data directory for persistence
DATA_DIR = Path(__file__).parent.parent.parent / "data"
ORDERS_FILE = DATA_DIR / "orders.json"


class OrderType(str, Enum):
    """Order type."""
    MARKET = "MARKET"
    LIMIT = "LIMIT"


class OrderSide(str, Enum):
    """Buy or sell."""
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(str, Enum):
    """Order status."""
    PENDING = "PENDING"
    FILLED = "FILLED"
    PARTIAL = "PARTIAL"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


@dataclass
class Order:
    """A trading order."""
    order_id: str
    ticker: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    limit_price: Optional[float] = None
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: float = 0.0
    filled_price: Optional[float] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    filled_at: Optional[str] = None
    reject_reason: Optional[str] = None
    is_paper: bool = True
    
    @property
    def is_complete(self) -> bool:
        """Check if order is in a terminal state."""
        return self.status in (
            OrderStatus.FILLED,
            OrderStatus.CANCELLED,
            OrderStatus.REJECTED,
            OrderStatus.EXPIRED
        )
    
    @property
    def remaining_quantity(self) -> float:
        """Quantity still to be filled."""
        return self.quantity - self.filled_quantity
    
    def to_dict(self) -> dict:
        data = asdict(self)
        data["side"] = self.side.value
        data["order_type"] = self.order_type.value
        data["status"] = self.status.value
        return data
    
    @classmethod
    def from_dict(cls, data: dict) -> "Order":
        data = data.copy()
        data["side"] = OrderSide(data["side"])
        data["order_type"] = OrderType(data["order_type"])
        data["status"] = OrderStatus(data["status"])
        return cls(**data)


class OrderManager:
    """
    Manages order creation, execution, and tracking.
    
    For paper trading, orders execute immediately at current price.
    For live trading (future), would connect to IBKR.
    """
    
    def __init__(self, portfolio: Optional[Portfolio] = None):
        self.portfolio = portfolio or get_portfolio()
        self.orders: Dict[str, Order] = {}
        self._load_orders()
    
    def _load_orders(self):
        """Load orders from file."""
        if ORDERS_FILE.exists():
            with open(ORDERS_FILE) as f:
                data = json.load(f)
            for order_data in data.get("orders", []):
                order = Order.from_dict(order_data)
                self.orders[order.order_id] = order
    
    def _save_orders(self):
        """Save orders to file."""
        ORDERS_FILE.parent.mkdir(parents=True, exist_ok=True)
        orders_list = [o.to_dict() for o in self.orders.values()]
        # Keep last 1000 orders
        orders_list = sorted(orders_list, key=lambda x: x["created_at"], reverse=True)[:1000]
        with open(ORDERS_FILE, "w") as f:
            json.dump({"orders": orders_list, "updated_at": datetime.now().isoformat()}, f, indent=2)
    
    def create_order(
        self,
        ticker: str,
        side: OrderSide,
        quantity: float,
        order_type: OrderType = OrderType.MARKET,
        limit_price: Optional[float] = None,
    ) -> Order:
        """
        Create a new order.
        
        For paper trading, market orders execute immediately.
        """
        ticker = ticker.upper()
        
        # Validate
        if quantity <= 0:
            raise ValueError("Quantity must be positive")
        
        if order_type == OrderType.LIMIT and limit_price is None:
            raise ValueError("Limit price required for limit orders")
        
        # Create order
        order = Order(
            order_id=str(uuid.uuid4())[:8],
            ticker=ticker,
            side=side,
            order_type=order_type,
            quantity=quantity,
            limit_price=limit_price,
            is_paper=self.portfolio.is_paper,
        )
        
        # Validate against portfolio
        if side == OrderSide.SELL:
            position = self.portfolio.get_position(ticker)
            if position is None or position.shares < quantity:
                order.status = OrderStatus.REJECTED
                order.reject_reason = f"Insufficient shares to sell"
        elif side == OrderSide.BUY:
            # Estimate cost
            price_data = fetch_latest_price(ticker)
            if price_data is None or price_data.get("price") is None:
                order.status = OrderStatus.REJECTED
                order.reject_reason = f"Unable to get price for {ticker}"
            else:
                estimated_cost = price_data["price"] * quantity
                if estimated_cost > self.portfolio.cash:
                    order.status = OrderStatus.REJECTED
                    order.reject_reason = f"Insufficient cash (need ${estimated_cost:.2f})"
        
        self.orders[order.order_id] = order
        
        # Execute immediately for paper trading market orders
        if (
            order.status == OrderStatus.PENDING
            and order.order_type == OrderType.MARKET
            and self.portfolio.is_paper
        ):
            self._execute_market_order(order)
        
        self._save_orders()
        return order
    
    def _execute_market_order(self, order: Order):
        """Execute a market order immediately."""
        price_data = fetch_latest_price(order.ticker)
        
        if price_data is None or price_data.get("price") is None:
            order.status = OrderStatus.REJECTED
            order.reject_reason = f"Unable to get price for {order.ticker}"
            return
        
        price = price_data["price"]
        
        try:
            if order.side == OrderSide.BUY:
                self.portfolio.add_position(order.ticker, order.quantity, price)
            else:
                self.portfolio.reduce_position(order.ticker, order.quantity, price)
            
            order.status = OrderStatus.FILLED
            order.filled_quantity = order.quantity
            order.filled_price = price
            order.filled_at = datetime.now().isoformat()
            order.updated_at = datetime.now().isoformat()
            
            # Save portfolio
            self.portfolio.save()
            
        except ValueError as e:
            order.status = OrderStatus.REJECTED
            order.reject_reason = str(e)
    
    def cancel_order(self, order_id: str) -> Order:
        """Cancel a pending order."""
        if order_id not in self.orders:
            raise ValueError(f"Order not found: {order_id}")
        
        order = self.orders[order_id]
        
        if order.is_complete:
            raise ValueError(f"Cannot cancel {order.status.value} order")
        
        order.status = OrderStatus.CANCELLED
        order.updated_at = datetime.now().isoformat()
        
        self._save_orders()
        return order
    
    def get_order(self, order_id: str) -> Optional[Order]:
        """Get order by ID."""
        return self.orders.get(order_id)
    
    def get_orders(
        self,
        status: Optional[OrderStatus] = None,
        ticker: Optional[str] = None,
        limit: int = 50
    ) -> List[Order]:
        """Get orders with optional filters."""
        orders = list(self.orders.values())
        
        if status:
            orders = [o for o in orders if o.status == status]
        
        if ticker:
            orders = [o for o in orders if o.ticker == ticker.upper()]
        
        # Sort by created_at descending
        orders.sort(key=lambda o: o.created_at, reverse=True)
        
        return orders[:limit]
    
    def get_pending_orders(self) -> List[Order]:
        """Get all pending orders."""
        return self.get_orders(status=OrderStatus.PENDING)
    
    def get_todays_orders(self) -> List[Order]:
        """Get orders from today."""
        today = datetime.now().date().isoformat()
        return [
            o for o in self.orders.values()
            if o.created_at.startswith(today)
        ]
    
    def clear_orders(self, keep_recent: int = 100):
        """Clear old orders, keeping recent ones."""
        orders = sorted(
            self.orders.values(),
            key=lambda o: o.created_at,
            reverse=True
        )[:keep_recent]
        
        self.orders = {o.order_id: o for o in orders}
        self._save_orders()


# ========== Global Order Manager Instance ==========

_order_manager: Optional[OrderManager] = None


def get_order_manager() -> OrderManager:
    """Get or create the global order manager."""
    global _order_manager
    
    if _order_manager is None:
        _order_manager = OrderManager()
    
    return _order_manager


def reset_order_manager() -> OrderManager:
    """Reset the global order manager."""
    global _order_manager
    
    # Clear orders file
    if ORDERS_FILE.exists():
        ORDERS_FILE.unlink()
    
    _order_manager = OrderManager()
    return _order_manager
