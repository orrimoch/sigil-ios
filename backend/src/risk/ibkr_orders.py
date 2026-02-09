"""
IBKR Stop Order Integration

REC-219: IBKR Stop Order Integration

Manages stop-loss orders via IBKR Gateway using ib_insync.
Uses native IBKR order types (STP, TRAIL) for server-side execution.

PM Requirement: Use IBKR native orders for execution.
Do NOT poll prices ourselves — IBKR monitors server-side.
"""

import logging
from typing import Optional, Dict, List, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class StopOrderInfo:
    """Information about a placed stop order."""
    order_id: int
    ticker: str
    order_type: str  # "STP" or "TRAIL"
    quantity: int
    stop_price: Optional[float] = None
    trailing_pct: Optional[float] = None
    status: str = "PENDING"


class IBKRStopOrderManager:
    """
    Manages stop-loss orders via IBKR Gateway.
    
    PM Requirement: Use IBKR native orders for execution.
    Do NOT poll prices ourselves — IBKR monitors server-side.
    
    Uses:
    - OrderType.STP for hard stop-loss
    - OrderType.TRAIL for trailing stop-loss
    """
    
    def __init__(self, ibkr_service: Any):
        """
        Initialize with IBKR service.
        
        Args:
            ibkr_service: IBKRService instance (connected to IB Gateway)
        """
        self.ibkr = ibkr_service
        self._order_map: Dict[str, int] = {}  # ticker -> order_id
        self._order_info: Dict[str, StopOrderInfo] = {}  # ticker -> order info

    def place_hard_stop(
        self,
        ticker: str,
        quantity: int,
        stop_price: float,
        limit_buffer_pct: float = 0.005,  # 0.5% buffer for STP_LMT
    ) -> Optional[int]:
        """
        Place hard stop-loss order via IBKR.
        
        Args:
            ticker: Stock symbol
            quantity: Number of shares to sell
            stop_price: Price at which stop triggers
            limit_buffer_pct: Buffer below stop for limit price (slippage protection)
            
        Returns:
            Order ID if successful, None otherwise
        """
        try:
            # Import ib_insync components
            from ib_insync import Contract, Order
            
            contract = Contract(
                symbol=ticker,
                secType='STK',
                exchange='SMART',
                currency='USD'
            )
            
            # Calculate limit price (slightly below stop for slippage protection)
            limit_price = stop_price * (1 - limit_buffer_pct)
            
            order = Order()
            order.action = 'SELL'
            order.orderType = 'STP LMT'  # Stop-limit for slippage protection
            order.totalQuantity = quantity
            order.auxPrice = stop_price  # Stop trigger price
            order.lmtPrice = limit_price  # Limit price
            
            # Place order via IBKR service
            result = self.ibkr.place_order(ticker, order)
            
            if result and result.get("order_id"):
                order_id = result["order_id"]
                self._order_map[ticker] = order_id
                self._order_info[ticker] = StopOrderInfo(
                    order_id=order_id,
                    ticker=ticker,
                    order_type="STP",
                    quantity=quantity,
                    stop_price=stop_price,
                    status="PENDING",
                )
                logger.info(f"Placed hard stop for {ticker}: stop=${stop_price:.2f}, limit=${limit_price:.2f}")
                return order_id
            
            return None
            
        except ImportError:
            logger.error("ib_insync not available")
            return None
        except Exception as e:
            logger.error(f"Failed to place hard stop for {ticker}: {e}")
            return None

    def place_trailing_stop(
        self,
        ticker: str,
        quantity: int,
        trailing_pct: float,  # e.g., 0.10 for 10%
    ) -> Optional[int]:
        """
        Place trailing stop order via IBKR.
        
        IBKR tracks high-water-mark server-side.
        
        Args:
            ticker: Stock symbol
            quantity: Number of shares to sell
            trailing_pct: Trailing percentage (e.g., 0.10 for 10%)
            
        Returns:
            Order ID if successful, None otherwise
        """
        try:
            from ib_insync import Contract, Order
            
            contract = Contract(
                symbol=ticker,
                secType='STK',
                exchange='SMART',
                currency='USD'
            )
            
            order = Order()
            order.action = 'SELL'
            order.orderType = 'TRAIL'
            order.totalQuantity = quantity
            # IBKR expects percentage as whole number (10 for 10%)
            order.trailingPercent = abs(trailing_pct) * 100
            
            # Place order via IBKR service
            result = self.ibkr.place_order(ticker, order)
            
            if result and result.get("order_id"):
                order_id = result["order_id"]
                self._order_map[ticker] = order_id
                self._order_info[ticker] = StopOrderInfo(
                    order_id=order_id,
                    ticker=ticker,
                    order_type="TRAIL",
                    quantity=quantity,
                    trailing_pct=trailing_pct,
                    status="PENDING",
                )
                logger.info(f"Placed trailing stop for {ticker}: trailing={abs(trailing_pct)*100:.1f}%")
                return order_id
            
            return None
            
        except ImportError:
            logger.error("ib_insync not available")
            return None
        except Exception as e:
            logger.error(f"Failed to place trailing stop for {ticker}: {e}")
            return None

    def cancel_stop(self, ticker: str) -> bool:
        """
        Cancel existing stop order for ticker.
        
        Args:
            ticker: Stock symbol
            
        Returns:
            True if cancelled, False otherwise
        """
        if ticker not in self._order_map:
            logger.debug(f"No stop order found for {ticker}")
            return False
        
        try:
            order_id = self._order_map[ticker]
            
            # Cancel via IBKR service
            result = self.ibkr.cancel_order(order_id)
            
            if result:
                del self._order_map[ticker]
                if ticker in self._order_info:
                    del self._order_info[ticker]
                logger.info(f"Cancelled stop order for {ticker}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to cancel stop for {ticker}: {e}")
            return False

    async def sync_stops_with_settings(
        self,
        positions: List[Dict[str, Any]],
        settings: "UserRiskSettings",
    ) -> None:
        """
        Sync IBKR stop orders with user's current risk settings.
        
        Called when:
        - User changes settings in iOS app
        - New position opened
        - App startup
        
        Args:
            positions: List of user's positions
            settings: User's risk settings
        """
        from .stop_loss import calculate_stop_price
        
        for position in positions:
            ticker = position.get("ticker")
            quantity = int(position.get("quantity", 0) or position.get("shares", 0))
            entry_price = position.get("avg_cost", 0)
            
            if not ticker or quantity <= 0 or entry_price <= 0:
                continue
            
            # Cancel existing stops first
            self.cancel_stop(ticker)
            
            # Place new stops based on settings
            if settings.hard_stop.enabled:
                stop_price = calculate_stop_price(entry_price, settings.hard_stop.threshold_pct)
                self.place_hard_stop(ticker, quantity, stop_price)
            
            if settings.trailing_stop.enabled:
                self.place_trailing_stop(ticker, quantity, abs(settings.trailing_stop.distance_pct))
        
        logger.info(f"Synced stop orders for {len(positions)} positions")

    def get_active_stops(self) -> Dict[str, StopOrderInfo]:
        """Get all active stop orders."""
        return self._order_info.copy()

    def has_stop(self, ticker: str) -> bool:
        """Check if ticker has an active stop order."""
        return ticker in self._order_map


class MockIBKRStopOrderManager(IBKRStopOrderManager):
    """
    Mock IBKR stop order manager for paper trading.
    
    Simulates stop order placement without actual IBKR connection.
    Used when IBKR is not connected or for testing.
    """
    
    def __init__(self):
        """Initialize mock manager (no IBKR service needed)."""
        self._order_map: Dict[str, int] = {}
        self._order_info: Dict[str, StopOrderInfo] = {}
        self._next_order_id = 1000

    def place_hard_stop(
        self,
        ticker: str,
        quantity: int,
        stop_price: float,
        limit_buffer_pct: float = 0.005,
    ) -> Optional[int]:
        """Simulate placing hard stop order."""
        order_id = self._next_order_id
        self._next_order_id += 1
        
        self._order_map[ticker] = order_id
        self._order_info[ticker] = StopOrderInfo(
            order_id=order_id,
            ticker=ticker,
            order_type="STP",
            quantity=quantity,
            stop_price=stop_price,
            status="SIMULATED",
        )
        
        logger.info(f"[MOCK] Placed hard stop for {ticker}: stop=${stop_price:.2f}")
        return order_id

    def place_trailing_stop(
        self,
        ticker: str,
        quantity: int,
        trailing_pct: float,
    ) -> Optional[int]:
        """Simulate placing trailing stop order."""
        order_id = self._next_order_id
        self._next_order_id += 1
        
        self._order_map[ticker] = order_id
        self._order_info[ticker] = StopOrderInfo(
            order_id=order_id,
            ticker=ticker,
            order_type="TRAIL",
            quantity=quantity,
            trailing_pct=trailing_pct,
            status="SIMULATED",
        )
        
        logger.info(f"[MOCK] Placed trailing stop for {ticker}: trailing={abs(trailing_pct)*100:.1f}%")
        return order_id

    def cancel_stop(self, ticker: str) -> bool:
        """Simulate cancelling stop order."""
        if ticker not in self._order_map:
            return False
        
        del self._order_map[ticker]
        if ticker in self._order_info:
            del self._order_info[ticker]
        
        logger.info(f"[MOCK] Cancelled stop order for {ticker}")
        return True

    async def sync_stops_with_settings(
        self,
        positions: List[Dict[str, Any]],
        settings: "UserRiskSettings",
    ) -> None:
        """Simulate syncing stop orders."""
        from .stop_loss import calculate_stop_price
        
        for position in positions:
            ticker = position.get("ticker")
            quantity = int(position.get("quantity", 0) or position.get("shares", 0))
            entry_price = position.get("avg_cost", 0)
            
            if not ticker or quantity <= 0 or entry_price <= 0:
                continue
            
            # Cancel existing stops first
            self.cancel_stop(ticker)
            
            # Place new stops based on settings
            if settings.hard_stop.enabled:
                stop_price = calculate_stop_price(entry_price, settings.hard_stop.threshold_pct)
                self.place_hard_stop(ticker, quantity, stop_price)
            
            if settings.trailing_stop.enabled:
                self.place_trailing_stop(ticker, quantity, abs(settings.trailing_stop.distance_pct))
        
        logger.info(f"[MOCK] Synced stop orders for {len(positions)} positions")
