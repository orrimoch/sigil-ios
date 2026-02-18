"""
Trade Executor Module (REC-288)

Executes trades via IBKR in supervised or autonomous mode.

Supervised Mode:
- Creates pending trade record
- Sends push notification to user
- User approves/rejects via app
- If approved, executes via IBKR

Autonomous Mode:
- Executes immediately via IBKR
- Notifies user of action taken
- Attaches stop-loss order
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, List, Dict, Any
from uuid import uuid4

# IBKR import with fallback for standalone testing
try:
    from ..ibkr import IBKRService, get_ibkr_service
except ImportError:
    # Stub for testing without full app context
    IBKRService = None
    def get_ibkr_service():
        return None

# User model import with fallback
try:
    from ..auth.models import User
except ImportError:
    User = None

# Sigil database imports for recording trades
try:
    from ..auth.database import get_db_session
    from ..trading.user_trading_service import UserTradingService
    SIGIL_DB_AVAILABLE = True
except ImportError:
    SIGIL_DB_AVAILABLE = False

logger = logging.getLogger(__name__)


class ExecutionMode(Enum):
    """Trade execution modes."""
    SUPERVISED = "supervised"   # Requires user approval
    AUTONOMOUS = "autonomous"   # Executes immediately


class OrderType(Enum):
    """IBKR order types."""
    MARKET = "MKT"
    LIMIT = "LMT"
    STOP = "STP"
    TRAIL = "TRAIL"


class TradeStatus(Enum):
    """Status of a trade in the execution pipeline."""
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTING = "executing"
    EXECUTED = "executed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class PendingTrade:
    """A trade awaiting user approval."""
    id: str
    user_id: str
    ticker: str
    action: str  # "BUY" or "SELL"
    shares: int
    estimated_price: float
    estimated_value: float
    weight: float
    rationale: str
    decision_id: Optional[str]
    created_at: datetime
    expires_at: datetime
    status: TradeStatus = TradeStatus.PENDING_APPROVAL
    
    @property
    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "ticker": self.ticker,
            "action": self.action,
            "shares": self.shares,
            "estimated_price": self.estimated_price,
            "estimated_value": self.estimated_value,
            "weight": self.weight,
            "rationale": self.rationale,
            "decision_id": self.decision_id,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "status": self.status.value,
            "is_expired": self.is_expired,
        }


@dataclass
class ExecutionResult:
    """Result of a trade execution attempt."""
    success: bool
    ticker: str
    action: str
    shares: int
    order_id: Optional[str] = None
    fill_price: Optional[float] = None
    fill_value: Optional[float] = None
    commission: Optional[float] = None
    stop_order_id: Optional[str] = None
    message: str = ""
    executed_at: Optional[datetime] = None
    # REC-311: Partial fill tracking
    requested_shares: Optional[int] = None  # Original requested quantity
    remaining_shares: Optional[int] = None  # Unfilled quantity
    is_partial_fill: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "ticker": self.ticker,
            "action": self.action,
            "shares": self.shares,
            "order_id": self.order_id,
            "fill_price": self.fill_price,
            "fill_value": self.fill_value,
            "commission": self.commission,
            "stop_order_id": self.stop_order_id,
            "message": self.message,
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
            "requested_shares": self.requested_shares,
            "remaining_shares": self.remaining_shares,
            "is_partial_fill": self.is_partial_fill,
        }


@dataclass
class ExecutorSettings:
    """User settings for trade execution."""
    mode: ExecutionMode = ExecutionMode.SUPERVISED
    stop_loss_type: str = "trailing"  # "trailing", "hard", "none"
    stop_loss_percent: float = 8.0    # Default 8% trailing stop
    approval_timeout_hours: int = 24   # Pending trades expire after 24h
    max_trades_per_week: int = 5
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExecutorSettings":
        return cls(
            mode=ExecutionMode(data.get("mode", "supervised")),
            stop_loss_type=data.get("stop_loss_type", "trailing"),
            stop_loss_percent=data.get("stop_loss_percent", 8.0),
            approval_timeout_hours=data.get("approval_timeout_hours", 24),
            max_trades_per_week=data.get("max_trades_per_week", 5),
        )


class TradeExecutor:
    """
    Executes trades via IBKR.
    
    Supports supervised (user approval) and autonomous (immediate) modes.
    """
    
    def __init__(
        self,
        ibkr_service: Optional[IBKRService] = None,
        notification_service: Optional[Any] = None,
    ):
        self.ibkr = ibkr_service
        self.notifications = notification_service
        
        # In-memory store for pending trades (would be DB in production)
        self._pending_trades: Dict[str, PendingTrade] = {}
        self._execution_history: List[ExecutionResult] = []
    
    async def initialize(self, user_id: str = "anonymous"):
        """Initialize services."""
        if self.ibkr is None:
            self.ibkr = get_ibkr_service()
        
        # Connect to IBKR if not connected
        if self.ibkr is not None and not self.ibkr.is_connected(user_id):
            try:
                await asyncio.to_thread(self.ibkr.connect, user_id)
            except Exception as e:
                logger.warning(f"IBKR connection failed: {e}")
        elif self.ibkr is None:
            logger.warning("IBKR service not available - will simulate trades")
    
    async def execute(
        self,
        ticker: str,
        action: str,
        shares: int,
        rationale: str,
        user_id: str,
        settings: ExecutorSettings,
        decision_id: Optional[str] = None,
        estimated_price: Optional[float] = None,
    ) -> ExecutionResult:
        """
        Execute a trade.
        
        In supervised mode, queues for approval.
        In autonomous mode, executes immediately.
        
        Args:
            ticker: Stock symbol
            action: "BUY" or "SELL"
            shares: Number of shares
            rationale: Why we're making this trade
            user_id: User ID
            settings: Execution settings
            decision_id: ID of the decision that generated this trade
            estimated_price: Current price estimate (optional)
        
        Returns:
            ExecutionResult with success/failure details
        """
        await self.initialize(user_id)
        
        # Get current price if not provided
        if estimated_price is None:
            estimated_price = await self._get_current_price(ticker)
        
        estimated_value = shares * estimated_price
        
        if settings.mode == ExecutionMode.SUPERVISED:
            return await self._supervised_execution(
                ticker=ticker,
                action=action,
                shares=shares,
                rationale=rationale,
                user_id=user_id,
                settings=settings,
                decision_id=decision_id,
                estimated_price=estimated_price,
                estimated_value=estimated_value,
            )
        else:
            return await self._autonomous_execution(
                ticker=ticker,
                action=action,
                shares=shares,
                rationale=rationale,
                user_id=user_id,
                settings=settings,
                decision_id=decision_id,
            )
    
    async def _supervised_execution(
        self,
        ticker: str,
        action: str,
        shares: int,
        rationale: str,
        user_id: str,
        settings: ExecutorSettings,
        decision_id: Optional[str],
        estimated_price: float,
        estimated_value: float,
    ) -> ExecutionResult:
        """Queue trade for user approval."""
        
        # Create pending trade
        pending = PendingTrade(
            id=str(uuid4()),
            user_id=user_id,
            ticker=ticker,
            action=action,
            shares=shares,
            estimated_price=estimated_price,
            estimated_value=estimated_value,
            weight=0.0,  # Will be filled from position sizing
            rationale=rationale,
            decision_id=decision_id,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=settings.approval_timeout_hours),
            status=TradeStatus.PENDING_APPROVAL,
        )
        
        # Store pending trade
        self._pending_trades[pending.id] = pending
        
        # Send push notification
        if self.notifications:
            try:
                await self._send_approval_notification(pending, user_id)
            except Exception as e:
                logger.warning(f"Failed to send notification: {e}")
        
        logger.info(f"Created pending trade {pending.id}: {action} {shares} {ticker}")
        
        return ExecutionResult(
            success=True,
            ticker=ticker,
            action=action,
            shares=shares,
            message=f"Pending approval: {pending.id}",
        )
    
    async def _autonomous_execution(
        self,
        ticker: str,
        action: str,
        shares: int,
        rationale: str,
        user_id: str,
        settings: ExecutorSettings,
        decision_id: Optional[str],
    ) -> ExecutionResult:
        """Execute trade immediately via IBKR."""
        
        try:
            # Place market order
            order_result = await self._place_market_order(ticker, action, shares, user_id)
            
            if not order_result["success"]:
                return ExecutionResult(
                    success=False,
                    ticker=ticker,
                    action=action,
                    shares=shares,
                    message=order_result.get("error", "Order failed"),
                )
            
            fill_price = order_result["fill_price"]
            order_id = order_result["order_id"]
            
            # REC-311: Handle partial fills
            original_shares = shares
            filled_shares = order_result.get("filled_quantity", shares)
            remaining_shares = order_result.get("remaining_quantity", 0)
            is_partial = order_result.get("status") == "PARTIAL" or (filled_shares > 0 and remaining_shares > 0)
            
            if is_partial:
                logger.warning(
                    f"PARTIAL FILL: {ticker} {action} - filled {filled_shares}/{original_shares} shares, "
                    f"{remaining_shares} remaining"
                )
                shares = int(filled_shares)  # Use actual filled quantity
            
            fill_value = fill_price * shares
            
            # Skip further processing if nothing was filled
            if shares == 0:
                return ExecutionResult(
                    success=False,
                    ticker=ticker,
                    action=action,
                    shares=0,
                    order_id=order_id,
                    message=f"Order not filled - {remaining_shares} shares unfilled",
                    requested_shares=original_shares,
                    remaining_shares=int(remaining_shares),
                )
            
            # Attach stop-loss if BUY and configured
            stop_order_id = None
            if action == "BUY" and settings.stop_loss_type != "none":
                stop_result = await self._attach_stop_loss(
                    ticker=ticker,
                    shares=shares,
                    fill_price=fill_price,
                    stop_type=settings.stop_loss_type,
                    stop_percent=settings.stop_loss_percent,
                    user_id=user_id,
                )
                if stop_result["success"]:
                    stop_order_id = stop_result["order_id"]
            
            # Notify user
            if self.notifications:
                try:
                    await self._send_execution_notification(
                        ticker=ticker,
                        action=action,
                        shares=shares,
                        fill_price=fill_price,
                        user_id=user_id,
                    )
                except Exception as e:
                    logger.warning(f"Failed to send notification: {e}")
            
            result = ExecutionResult(
                success=True,
                ticker=ticker,
                action=action,
                shares=shares,
                order_id=order_id,
                fill_price=fill_price,
                fill_value=fill_value,
                stop_order_id=stop_order_id,
                message="Partial fill" if is_partial else "Executed",
                executed_at=datetime.utcnow(),
                # REC-311: Partial fill info
                requested_shares=original_shares if is_partial else None,
                remaining_shares=int(remaining_shares) if is_partial else None,
                is_partial_fill=is_partial,
            )
            
            self._execution_history.append(result)
            logger.info(f"Executed {action} {shares} {ticker} @ ${fill_price:.2f}")
            
            # Record trade in Sigil's portfolio database
            await self._record_trade_in_sigil(
                ticker=ticker,
                action=action,
                shares=shares,
                fill_price=fill_price,
                user_id=user_id,
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Execution failed for {action} {shares} {ticker}: {e}")
            return ExecutionResult(
                success=False,
                ticker=ticker,
                action=action,
                shares=shares,
                message=str(e),
            )
    
    async def approve_pending(
        self,
        pending_id: str,
        user_id: str,
        settings: ExecutorSettings,
    ) -> ExecutionResult:
        """Approve and execute a pending trade."""
        
        pending = self._pending_trades.get(pending_id)
        if not pending:
            return ExecutionResult(
                success=False,
                ticker="",
                action="",
                shares=0,
                message=f"Pending trade {pending_id} not found",
            )
        
        # Verify ownership
        if pending.user_id != user_id:
            return ExecutionResult(
                success=False,
                ticker=pending.ticker,
                action=pending.action,
                shares=pending.shares,
                message="Unauthorized",
            )
        
        # Check expiration
        if pending.is_expired:
            pending.status = TradeStatus.CANCELLED
            return ExecutionResult(
                success=False,
                ticker=pending.ticker,
                action=pending.action,
                shares=pending.shares,
                message="Trade expired",
            )
        
        # Check buying power for BUY trades
        if pending.action == "BUY":
            trade_cost = pending.estimated_value
            available_cash = await self._get_user_buying_power(user_id)
            
            if available_cash is not None and trade_cost > available_cash:
                pending.status = TradeStatus.FAILED
                return ExecutionResult(
                    success=False,
                    ticker=pending.ticker,
                    action=pending.action,
                    shares=pending.shares,
                    message=f"Insufficient buying power: need ${trade_cost:,.2f}, have ${available_cash:,.2f}",
                )
        
        # Update status
        pending.status = TradeStatus.APPROVED
        
        # Execute
        result = await self._autonomous_execution(
            ticker=pending.ticker,
            action=pending.action,
            shares=pending.shares,
            rationale=pending.rationale,
            user_id=user_id,
            settings=settings,
            decision_id=pending.decision_id,
        )
        
        # Update status
        pending.status = TradeStatus.EXECUTED if result.success else TradeStatus.FAILED
        
        return result
    
    async def reject_pending(
        self,
        pending_id: str,
        user_id: str,
        reason: Optional[str] = None,
    ) -> bool:
        """Reject a pending trade."""
        
        pending = self._pending_trades.get(pending_id)
        if not pending:
            return False
        
        if pending.user_id != user_id:
            return False
        
        pending.status = TradeStatus.REJECTED
        logger.info(f"Rejected pending trade {pending_id}: {reason or 'No reason'}")
        
        return True
    
    async def get_pending_trades(self, user_id: str) -> List[PendingTrade]:
        """Get all pending trades for a user."""
        # TODO: Re-enable user filtering after auth is properly integrated
        # For now, return ALL pending trades for demo
        return [
            p for p in self._pending_trades.values()
            if p.status == TradeStatus.PENDING_APPROVAL
        ]
    
    async def get_execution_history(
        self,
        user_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[ExecutionResult]:
        """Get recent execution history."""
        # In production, would filter by user_id from DB
        return self._execution_history[-limit:]
    
    async def _place_market_order(
        self,
        ticker: str,
        action: str,
        shares: int,
        user_id: str = "anonymous",
    ) -> Dict[str, Any]:
        """Place a market order via IBKR."""
        
        if self.ibkr is None or not self.ibkr.is_connected(user_id):
            # Simulate for testing
            logger.warning("IBKR not connected, simulating order")
            price = await self._get_current_price(ticker)
            return {
                "success": True,
                "order_id": f"SIM-{uuid4().hex[:8]}",
                "fill_price": price,
                "simulated": True,
            }
        
        try:
            result = await asyncio.to_thread(
                self.ibkr.submit_order,
                user_id,  # First parameter is user_id
                ticker,
                action,
                shares,
                "MARKET",  # order_type
            )
            # result is an IBKROrder object with: order_id, status, filled_price
            # Status is mapped to: FILLED, PARTIAL, PENDING, CANCELLED, REJECTED
            # REC-311: Include partial fill info
            return {
                "success": result.status in ["FILLED", "PARTIAL"],
                "order_id": str(result.order_id),
                "fill_price": result.filled_price,
                "status": result.status,
                "filled_quantity": result.filled_quantity,
                "remaining_quantity": result.remaining_quantity,
            }
        except Exception as e:
            logger.error(f"IBKR order failed: {e}")
            return {
                "success": False,
                "error": str(e),
            }
    
    async def _attach_stop_loss(
        self,
        ticker: str,
        shares: int,
        fill_price: float,
        stop_type: str,
        stop_percent: float,
        user_id: str = "anonymous",
    ) -> Dict[str, Any]:
        """Attach a stop-loss order to a position."""
        
        if self.ibkr is None or not self.ibkr.is_connected(user_id):
            logger.warning("IBKR not connected, simulating stop order")
            return {
                "success": True,
                "order_id": f"STOP-{uuid4().hex[:8]}",
                "simulated": True,
            }
        
        try:
            if stop_type == "trailing":
                # Submit trailing stop order
                result = await asyncio.to_thread(
                    self.ibkr.submit_order,
                    user_id,
                    ticker,
                    "SELL",
                    shares,
                    "TRAIL",  # order_type
                    None,     # limit_price
                    stop_percent,  # trailing_percent
                )
            else:  # hard stop
                stop_price = fill_price * (1 - stop_percent / 100)
                result = await asyncio.to_thread(
                    self.ibkr.submit_order,
                    user_id,
                    ticker,
                    "SELL",
                    shares,
                    "STP",  # order_type
                    stop_price,  # limit_price (used as stop price)
                )
            # Stop orders won't fill immediately, PENDING is success
            return {
                "success": result.status in ("PENDING", "FILLED"),
                "order_id": str(result.order_id),
            }
        except Exception as e:
            logger.warning(f"Stop-loss order failed: {e}")
            return {
                "success": False,
                "error": str(e),
            }
    
    async def _get_current_price(self, ticker: str) -> float:
        """Get current price for a ticker."""
        try:
            if self.ibkr and self.ibkr.is_connected():
                quote = await asyncio.to_thread(
                    self.ibkr.get_quote,
                    ticker=ticker,
                )
                if quote:
                    return quote.get("last", quote.get("close", 100.0))
            
            # Fallback to yfinance
            import yfinance as yf
            stock = yf.Ticker(ticker)
            hist = stock.history(period="1d")
            if not hist.empty:
                return float(hist["Close"].iloc[-1])
        except Exception as e:
            logger.warning(f"Price fetch failed for {ticker}: {e}")
        
        return 100.0  # Fallback
    
    async def _get_user_buying_power(self, user_id: str) -> Optional[float]:
        """Get available buying power (cash) for a user."""
        try:
            from pathlib import Path
            import aiosqlite
            
            db_path = Path(__file__).parent.parent.parent / "data" / "sigil.db"
            
            async with aiosqlite.connect(db_path) as db:
                # Get user's portfolio cash balance
                cursor = await db.execute(
                    """
                    SELECT cash_balance FROM portfolios 
                    WHERE user_id = ? 
                    ORDER BY created_at DESC LIMIT 1
                    """,
                    (user_id,)
                )
                row = await cursor.fetchone()
                
                if row:
                    return float(row[0])
                
        except Exception as e:
            logger.warning(f"Failed to get buying power for {user_id}: {e}")
        
        return None  # Unknown - allow trade to proceed
    
    async def _record_trade_in_sigil(
        self,
        ticker: str,
        action: str,
        shares: int,
        fill_price: float,
        user_id: str,
    ) -> bool:
        """
        Record the executed trade in Sigil's portfolio database.
        
        This ensures trades executed by the End Game agent appear in the Sigil app.
        Uses HTTP API to avoid SQLite locking when backend is running.
        """
        import httpx
        
        api_url = "http://localhost:8000/api/v1/orders"
        
        payload = {
            "ticker": ticker.upper(),
            "side": "BUY" if action.upper() == "BUY" else "SELL",
            "quantity": float(shares),
            "order_type": "MARKET",
            "is_paper": True,
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Note: For now using anonymous endpoint; in production would add auth header
                response = await client.post(
                    api_url,
                    json=payload,
                    headers={"X-User-Id": user_id},  # Pass user_id in header
                )
                
                if response.status_code in (200, 201):
                    logger.info(f"Recorded trade in Sigil via API: {action} {shares} {ticker}")
                    return True
                else:
                    # API failed (auth required, etc.) — try direct DB
                    logger.warning(f"API returned {response.status_code}, falling back to direct DB")
                    return await self._record_trade_direct_db(ticker, action, shares, fill_price, user_id)
                    
        except httpx.ConnectError:
            logger.warning("Backend not running, trying direct DB access")
            return await self._record_trade_direct_db(ticker, action, shares, fill_price, user_id)
        except Exception as e:
            logger.error(f"Failed to record trade in Sigil: {e}")
            # Try direct DB as last resort
            return await self._record_trade_direct_db(ticker, action, shares, fill_price, user_id)
    
    async def _record_trade_direct_db(
        self,
        ticker: str,
        action: str,
        shares: int,
        fill_price: float,
        user_id: str,
    ) -> bool:
        """Fallback: record trade directly in DB when backend is not running."""
        if not SIGIL_DB_AVAILABLE:
            logger.warning("Sigil DB not available, trade not recorded in app")
            return False
        
        try:
            async for db in get_db_session():
                side = "BUY" if action.upper() == "BUY" else "SELL"
                order = await UserTradingService.create_order(
                    db=db,
                    user_id=user_id,
                    ticker=ticker,
                    side=side,
                    quantity=float(shares),
                    order_type="MARKET",
                    is_paper=True,
                )
                logger.info(f"Recorded trade in Sigil DB: {action} {shares} {ticker} @ ${fill_price:.2f}")
                return True
        except Exception as e:
            logger.error(f"Failed to record trade in Sigil DB: {e}")
            return False
    
    async def _send_approval_notification(
        self,
        pending: PendingTrade,
        user_id: str,
    ):
        """Send push notification for trade approval."""
        await self.notifications.send_push(
            user_id=user_id,
            title=f"🤖 Agent: {pending.action} {pending.ticker}",
            body=f"{pending.shares} shares (${pending.estimated_value:,.0f}) — Tap to review",
            data={
                "type": "pending_trade",
                "pending_id": pending.id,
                "ticker": pending.ticker,
                "action": pending.action,
            },
        )
    
    async def _send_execution_notification(
        self,
        ticker: str,
        action: str,
        shares: int,
        fill_price: float,
        user_id: str,
    ):
        """Send push notification after execution."""
        value = shares * fill_price
        await self.notifications.send_push(
            user_id=user_id,
            title=f"✅ Executed: {action} {ticker}",
            body=f"{shares} shares @ ${fill_price:.2f} (${value:,.0f})",
            data={
                "type": "trade_executed",
                "ticker": ticker,
                "action": action,
            },
        )


# Module-level instance
_executor: Optional[TradeExecutor] = None


def get_executor() -> TradeExecutor:
    """Get or create the global executor instance."""
    global _executor
    if _executor is None:
        _executor = TradeExecutor()
    return _executor


async def execute_trade(
    ticker: str,
    action: str,
    shares: int,
    rationale: str,
    user_id: str,
    mode: str = "supervised",
) -> ExecutionResult:
    """Convenience function to execute a trade."""
    executor = get_executor()
    settings = ExecutorSettings(mode=ExecutionMode(mode))
    return await executor.execute(
        ticker=ticker,
        action=action,
        shares=shares,
        rationale=rationale,
        user_id=user_id,
        settings=settings,
    )
