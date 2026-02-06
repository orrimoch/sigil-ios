"""
F7.2 Real Portfolio History Service

Computes actual portfolio history from trade records and historical prices.
No mock data — reconstructs values from real trades.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Tuple
from collections import defaultdict
import yfinance as yf
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import UserOrder, UserPortfolio, UserPosition, ANONYMOUS_USER_ID


class PortfolioHistoryService:
    """Computes real portfolio history from trade data."""

    @staticmethod
    async def get_real_history(
        db: AsyncSession,
        user_id: str,
        days: int = 30,
    ) -> List[Dict]:
        """
        Compute actual portfolio history from trades.
        
        Reconstructs portfolio value for each day by:
        1. Getting all filled orders
        2. Building position snapshots at each point in time
        3. Fetching historical prices to value positions
        """
        # Get portfolio for starting cash
        result = await db.execute(
            select(UserPortfolio).where(UserPortfolio.user_id == user_id)
        )
        portfolio = result.scalar_one_or_none()
        
        if not portfolio:
            return []
        
        starting_cash = portfolio.starting_cash
        
        # Get all filled orders sorted by date
        result = await db.execute(
            select(UserOrder)
            .where(
                and_(
                    UserOrder.user_id == user_id,
                    UserOrder.status == "FILLED",
                )
            )
            .order_by(UserOrder.filled_at.asc())
        )
        orders = list(result.scalars().all())
        
        if not orders:
            # No trades yet — return current portfolio value as flat line
            return await PortfolioHistoryService._generate_no_trade_history(
                db, user_id, portfolio, days
            )
        
        # Determine date range
        end_date = datetime.now(timezone.utc).date()
        start_date = end_date - timedelta(days=days)
        
        # Find first trade date
        first_trade_date = orders[0].filled_at.date() if orders[0].filled_at else start_date
        if first_trade_date > start_date:
            start_date = first_trade_date
        
        # Build daily position snapshots
        tickers = set(o.ticker for o in orders)
        
        # Fetch historical prices for all tickers
        historical_prices = await PortfolioHistoryService._fetch_historical_prices(
            list(tickers), start_date, end_date
        )
        
        # Reconstruct portfolio state for each day
        history = []
        positions: Dict[str, float] = {}  # ticker -> shares
        cash = starting_cash
        
        current_date = start_date
        order_idx = 0
        
        while current_date <= end_date:
            # Apply any orders that occurred on this date
            while order_idx < len(orders):
                order = orders[order_idx]
                order_date = order.filled_at.date() if order.filled_at else None
                
                if order_date and order_date <= current_date:
                    # Apply this trade
                    filled_price = order.filled_price or 0
                    trade_value = order.filled_quantity * filled_price
                    
                    if order.side == "BUY":
                        cash -= trade_value
                        positions[order.ticker] = positions.get(order.ticker, 0) + order.filled_quantity
                    else:  # SELL
                        cash += trade_value
                        positions[order.ticker] = positions.get(order.ticker, 0) - order.filled_quantity
                        if positions[order.ticker] <= 0:
                            del positions[order.ticker]
                    
                    order_idx += 1
                else:
                    break
            
            # Calculate portfolio value for this day
            positions_value = 0.0
            for ticker, shares in positions.items():
                price = historical_prices.get(ticker, {}).get(current_date)
                if price:
                    positions_value += shares * price
                else:
                    # Fallback: use most recent available price
                    price = PortfolioHistoryService._get_nearest_price(
                        historical_prices.get(ticker, {}), current_date
                    )
                    if price:
                        positions_value += shares * price
            
            total_value = cash + positions_value
            pnl = total_value - starting_cash
            pnl_percent = (pnl / starting_cash * 100) if starting_cash > 0 else 0
            
            history.append({
                "timestamp": datetime.combine(current_date, datetime.min.time()).isoformat(),
                "total_value": round(total_value, 2),
                "cash": round(cash, 2),
                "positions_value": round(positions_value, 2),
                "total_pnl": round(pnl, 2),
                "total_pnl_percent": round(pnl_percent, 2),
            })
            
            current_date += timedelta(days=1)
        
        return history

    @staticmethod
    async def _generate_no_trade_history(
        db: AsyncSession,
        user_id: str,
        portfolio: UserPortfolio,
        days: int,
    ) -> List[Dict]:
        """Generate history when no trades exist — just the starting cash."""
        history = []
        end_date = datetime.now(timezone.utc).date()
        start_date = end_date - timedelta(days=days)
        
        current_date = start_date
        starting_cash = portfolio.starting_cash
        current_cash = portfolio.cash_balance
        
        while current_date <= end_date:
            # Before today: starting cash
            # Today: current cash (in case it was modified)
            if current_date == end_date:
                cash = current_cash
            else:
                cash = starting_cash
            
            history.append({
                "timestamp": datetime.combine(current_date, datetime.min.time()).isoformat(),
                "total_value": round(cash, 2),
                "cash": round(cash, 2),
                "positions_value": 0.0,
                "total_pnl": round(cash - starting_cash, 2),
                "total_pnl_percent": round((cash - starting_cash) / starting_cash * 100, 2) if starting_cash > 0 else 0,
            })
            current_date += timedelta(days=1)
        
        return history

    @staticmethod
    async def _fetch_historical_prices(
        tickers: List[str],
        start_date,
        end_date,
    ) -> Dict[str, Dict]:
        """Fetch historical closing prices for tickers."""
        if not tickers:
            return {}
        
        # Run yfinance in thread pool
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            PortfolioHistoryService._fetch_prices_sync,
            tickers,
            start_date,
            end_date,
        )

    @staticmethod
    def _fetch_prices_sync(
        tickers: List[str],
        start_date,
        end_date,
    ) -> Dict[str, Dict]:
        """Synchronous price fetching."""
        result = {}
        
        # Add buffer day for yfinance
        fetch_start = start_date - timedelta(days=5)
        fetch_end = end_date + timedelta(days=1)
        
        for ticker in tickers:
            try:
                data = yf.download(
                    ticker,
                    start=fetch_start.isoformat(),
                    end=fetch_end.isoformat(),
                    progress=False,
                    auto_adjust=True,
                )
                
                if not data.empty:
                    prices = {}
                    for idx, row in data.iterrows():
                        date = idx.date() if hasattr(idx, 'date') else idx
                        close = row['Close']
                        # Handle both scalar and Series
                        if hasattr(close, 'iloc'):
                            close = close.iloc[0]
                        prices[date] = float(close)
                    result[ticker] = prices
            except Exception as e:
                print(f"Error fetching prices for {ticker}: {e}")
                result[ticker] = {}
        
        return result

    @staticmethod
    def _get_nearest_price(
        prices: Dict,
        target_date,
    ) -> Optional[float]:
        """Get the nearest available price to a target date."""
        if not prices:
            return None
        
        # Look backwards for nearest price (weekends, holidays)
        for i in range(7):
            check_date = target_date - timedelta(days=i)
            if check_date in prices:
                return prices[check_date]
        
        # Fallback: return any price
        if prices:
            return list(prices.values())[-1]
        
        return None

    @staticmethod
    async def get_performance(
        db: AsyncSession,
        user_id: str,
        days: int = 30,
    ) -> Dict:
        """Calculate performance metrics from real history."""
        history = await PortfolioHistoryService.get_real_history(db, user_id, days)
        
        if len(history) < 2:
            return {
                "period_days": days,
                "start_value": None,
                "end_value": None,
                "change": None,
                "change_percent": None,
                "data_points": len(history),
            }
        
        start_value = history[0]["total_value"]
        end_value = history[-1]["total_value"]
        change = end_value - start_value
        change_percent = (change / start_value * 100) if start_value > 0 else 0
        
        return {
            "period_days": days,
            "start_value": round(start_value, 2),
            "end_value": round(end_value, 2),
            "change": round(change, 2),
            "change_percent": round(change_percent, 2),
            "data_points": len(history),
        }
