"""
REC-155: Trading Performance Statistics
REC-156: Execution Quality Analysis

Calculate trading metrics from order history:
- Win rate, average winner/loser
- Profit factor, expectancy
- Sharpe ratio (if daily returns available)
- Slippage tracking
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime, timezone
import statistics


@dataclass
class TradeStats:
    """Statistics for a single trade or aggregated metrics."""
    ticker: str
    side: str  # BUY or SELL
    quantity: float
    entry_price: float
    exit_price: Optional[float] = None
    pnl: Optional[float] = None
    pnl_percent: Optional[float] = None
    is_winner: Optional[bool] = None
    hold_time_hours: Optional[float] = None
    
    # REC-156: Execution quality
    expected_price: Optional[float] = None
    slippage: Optional[float] = None  # actual - expected
    slippage_percent: Optional[float] = None


@dataclass
class PerformanceMetrics:
    """Aggregated trading performance metrics."""
    # Basic counts
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    
    # Win rate
    win_rate: float = 0.0  # percentage
    
    # P&L metrics
    total_pnl: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    
    # Risk metrics
    profit_factor: float = 0.0  # gross profit / gross loss
    expectancy: float = 0.0  # avg profit per trade
    avg_risk_reward: float = 0.0  # avg win / avg loss
    
    # REC-156: Execution quality
    avg_slippage: float = 0.0
    avg_slippage_percent: float = 0.0
    total_slippage_cost: float = 0.0
    
    # Holding period
    avg_hold_time_hours: float = 0.0
    
    # Time range
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": round(self.win_rate, 2),
            "total_pnl": round(self.total_pnl, 2),
            "avg_win": round(self.avg_win, 2),
            "avg_loss": round(self.avg_loss, 2),
            "largest_win": round(self.largest_win, 2),
            "largest_loss": round(self.largest_loss, 2),
            "profit_factor": round(self.profit_factor, 2),
            "expectancy": round(self.expectancy, 2),
            "avg_risk_reward": round(self.avg_risk_reward, 2),
            "avg_slippage": round(self.avg_slippage, 4),
            "avg_slippage_percent": round(self.avg_slippage_percent, 4),
            "total_slippage_cost": round(self.total_slippage_cost, 2),
            "avg_hold_time_hours": round(self.avg_hold_time_hours, 2),
            "period_start": self.period_start,
            "period_end": self.period_end,
        }


def calculate_performance_metrics(orders: List[dict]) -> PerformanceMetrics:
    """
    Calculate performance metrics from a list of filled orders.
    
    Args:
        orders: List of order dicts with keys:
            - ticker, side, quantity, status
            - fill_price, limit_price (for slippage)
            - created_at, filled_at
    
    Returns:
        PerformanceMetrics with calculated stats
    """
    metrics = PerformanceMetrics()
    
    # Filter to filled orders only
    filled = [o for o in orders if o.get("status") == "FILLED"]
    if not filled:
        return metrics
    
    metrics.total_trades = len(filled)
    
    # Calculate P&L for closed positions
    # For simplicity, assume each sell closes a prior buy at that ticker
    wins = []
    losses = []
    slippages = []
    hold_times = []
    
    # Group by ticker
    buys_by_ticker: Dict[str, List[dict]] = {}
    
    for order in sorted(filled, key=lambda x: x.get("created_at", "")):
        ticker = order.get("ticker", "")
        side = order.get("side", "").upper()
        fill_price = order.get("fill_price") or order.get("filled_price", 0)
        limit_price = order.get("limit_price")
        quantity = order.get("quantity", 0)
        
        # REC-156: Calculate slippage for limit orders
        if limit_price and fill_price:
            slippage = abs(fill_price - limit_price)
            slippage_pct = slippage / limit_price * 100 if limit_price else 0
            slippages.append({
                "amount": slippage * quantity,
                "percent": slippage_pct,
            })
        
        if side == "BUY":
            if ticker not in buys_by_ticker:
                buys_by_ticker[ticker] = []
            buys_by_ticker[ticker].append(order)
        
        elif side == "SELL" and ticker in buys_by_ticker and buys_by_ticker[ticker]:
            # Match with earliest buy (FIFO)
            buy = buys_by_ticker[ticker].pop(0)
            buy_price = buy.get("fill_price") or buy.get("filled_price", 0)
            
            if buy_price and fill_price:
                pnl = (fill_price - buy_price) * quantity
                
                if pnl >= 0:
                    wins.append(pnl)
                else:
                    losses.append(pnl)
                
                # Hold time
                buy_time = buy.get("filled_at") or buy.get("created_at")
                sell_time = order.get("filled_at") or order.get("created_at")
                if buy_time and sell_time:
                    try:
                        bt = datetime.fromisoformat(buy_time.replace("Z", "+00:00"))
                        st = datetime.fromisoformat(sell_time.replace("Z", "+00:00"))
                        hold_hours = (st - bt).total_seconds() / 3600
                        hold_times.append(hold_hours)
                    except:
                        pass
    
    # Calculate metrics
    metrics.winning_trades = len(wins)
    metrics.losing_trades = len(losses)
    
    if metrics.total_trades > 0:
        metrics.win_rate = (metrics.winning_trades / metrics.total_trades) * 100
    
    metrics.total_pnl = sum(wins) + sum(losses)
    
    if wins:
        metrics.avg_win = statistics.mean(wins)
        metrics.largest_win = max(wins)
    
    if losses:
        metrics.avg_loss = statistics.mean(losses)
        metrics.largest_loss = min(losses)
    
    # Profit factor
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    if gross_loss > 0:
        metrics.profit_factor = gross_profit / gross_loss
    
    # Expectancy (avg profit per trade)
    all_pnl = wins + losses
    if all_pnl:
        metrics.expectancy = statistics.mean(all_pnl)
    
    # Risk/Reward ratio
    if metrics.avg_loss != 0:
        metrics.avg_risk_reward = abs(metrics.avg_win / metrics.avg_loss)
    
    # REC-156: Slippage metrics
    if slippages:
        metrics.avg_slippage = statistics.mean([s["amount"] for s in slippages])
        metrics.avg_slippage_percent = statistics.mean([s["percent"] for s in slippages])
        metrics.total_slippage_cost = sum([s["amount"] for s in slippages])
    
    # Hold time
    if hold_times:
        metrics.avg_hold_time_hours = statistics.mean(hold_times)
    
    # Period
    if filled:
        dates = [o.get("created_at", "") for o in filled if o.get("created_at")]
        if dates:
            metrics.period_start = min(dates)
            metrics.period_end = max(dates)
    
    return metrics


def analyze_slippage(orders: List[dict]) -> List[dict]:
    """
    REC-156: Analyze slippage for each filled order.
    
    Returns list of slippage records for orders with limit prices.
    """
    results = []
    
    for order in orders:
        if order.get("status") != "FILLED":
            continue
        
        fill_price = order.get("fill_price") or order.get("filled_price")
        limit_price = order.get("limit_price")
        
        if not (fill_price and limit_price):
            continue
        
        slippage = fill_price - limit_price
        slippage_pct = (slippage / limit_price) * 100 if limit_price else 0
        quantity = order.get("quantity", 0)
        
        # Positive slippage = worse fill for buyer, better for seller
        side = order.get("side", "").upper()
        cost_impact = slippage * quantity
        if side == "SELL":
            cost_impact = -cost_impact  # Negative slippage helps seller
        
        results.append({
            "order_id": order.get("id") or order.get("order_id"),
            "ticker": order.get("ticker"),
            "side": side,
            "quantity": quantity,
            "limit_price": round(limit_price, 2),
            "fill_price": round(fill_price, 2),
            "slippage": round(slippage, 4),
            "slippage_percent": round(slippage_pct, 4),
            "cost_impact": round(cost_impact, 2),
            "filled_at": order.get("filled_at"),
        })
    
    return results
