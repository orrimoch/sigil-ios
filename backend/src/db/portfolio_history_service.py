"""
F7.2 Real Portfolio History Service

Computes actual portfolio history from trade records and historical prices.
No mock data — reconstructs values from real trades.

Optimization: uses portfolio_snapshots table for cached history.
Falls back to live computation only when snapshots are missing.
"""

import asyncio
from datetime import datetime, timedelta, timezone, date
from typing import List, Dict, Optional, Tuple
from collections import defaultdict
import yfinance as yf
from sqlalchemy import select, and_, text
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import UserOrder, UserPortfolio, UserPosition, PortfolioSnapshot, ANONYMOUS_USER_ID


class PortfolioHistoryService:
    """Computes real portfolio history from trade data, with snapshot caching."""

    # ── Public API ──────────────────────────────────────────────

    @staticmethod
    async def get_real_history(
        db: AsyncSession,
        user_id: str,
        days: int = 30,
    ) -> List[Dict]:
        """
        Get portfolio history — checks snapshot cache first, falls back to live.
        
        For "All" period (days=365), always starts from starting_cash.
        """
        # Get portfolio for starting cash
        result = await db.execute(
            select(UserPortfolio).where(UserPortfolio.user_id == user_id)
        )
        portfolio = result.scalar_one_or_none()

        if not portfolio:
            return []

        starting_cash = portfolio.starting_cash
        portfolio_id = portfolio.id

        # Try snapshots first
        snapshots = await PortfolioHistoryService._get_snapshots(
            db, user_id, portfolio_id, days
        )

        if snapshots:
            return snapshots

        # No snapshots — fall back to live computation
        return await PortfolioHistoryService._compute_live_history(
            db, user_id, portfolio, days
        )

    @staticmethod
    async def get_performance(
        db: AsyncSession,
        user_id: str,
        days: int = 30,
    ) -> Dict:
        """
        Calculate performance metrics from real history.
        
        For "All" period, start_value = starting_cash ($100K),
        NOT the first day's computed value.
        """
        # Get portfolio for starting_cash
        result = await db.execute(
            select(UserPortfolio).where(UserPortfolio.user_id == user_id)
        )
        portfolio = result.scalar_one_or_none()
        starting_cash = portfolio.starting_cash if portfolio else 100000.0

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

        # For "All" (365 days or more), use starting_cash as start_value
        # This ensures the chart shows the real all-time return from $100K
        if days >= 365:
            start_value = starting_cash
        else:
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

    @staticmethod
    async def take_snapshot(
        db: AsyncSession,
        user_id: str,
    ) -> Optional[Dict]:
        """
        Take a snapshot of the current portfolio value and store it.
        Called by the daily cron job.
        """
        result = await db.execute(
            select(UserPortfolio).where(UserPortfolio.user_id == user_id)
        )
        portfolio = result.scalar_one_or_none()
        if not portfolio:
            return None

        starting_cash = portfolio.starting_cash
        portfolio_id = portfolio.id

        # Get current positions
        result = await db.execute(
            select(UserPosition).where(UserPosition.portfolio_id == portfolio_id)
        )
        positions = list(result.scalars().all())

        # Fetch current prices for all positions
        tickers = [p.ticker for p in positions if p.quantity > 0]
        current_prices = {}
        if tickers:
            loop = asyncio.get_event_loop()
            current_prices = await loop.run_in_executor(
                None,
                PortfolioHistoryService._fetch_current_prices_sync,
                tickers,
            )

        # Calculate values
        positions_value = sum(
            p.quantity * current_prices.get(p.ticker, p.avg_cost)
            for p in positions
            if p.quantity > 0
        )
        cash = portfolio.cash_balance
        total_value = cash + positions_value
        pnl = total_value - starting_cash
        pnl_pct = (pnl / starting_cash * 100) if starting_cash > 0 else 0

        today = date.today().isoformat()
        now = datetime.now(timezone.utc).isoformat()

        # Upsert snapshot
        await db.execute(
            text(
                "INSERT OR REPLACE INTO portfolio_snapshots "
                "(user_id, portfolio_id, date, total_value, cash, positions_value, "
                "total_pnl, total_pnl_percent, created_at) "
                "VALUES (:user_id, :portfolio_id, :date, :total_value, :cash, "
                ":positions_value, :total_pnl, :total_pnl_percent, :created_at)"
            ),
            {
                "user_id": user_id,
                "portfolio_id": portfolio_id,
                "date": today,
                "total_value": round(total_value, 2),
                "cash": round(cash, 2),
                "positions_value": round(positions_value, 2),
                "total_pnl": round(pnl, 2),
                "total_pnl_percent": round(pnl_pct, 2),
                "created_at": now,
            },
        )
        await db.commit()

        return {
            "date": today,
            "total_value": round(total_value, 2),
            "cash": round(cash, 2),
            "positions_value": round(positions_value, 2),
            "total_pnl": round(pnl, 2),
            "total_pnl_percent": round(pnl_pct, 2),
        }

    # ── Snapshot retrieval ──────────────────────────────────────

    @staticmethod
    async def _get_snapshots(
        db: AsyncSession,
        user_id: str,
        portfolio_id: str,
        days: int,
    ) -> List[Dict]:
        """
        Retrieve cached snapshots from portfolio_snapshots table.
        Returns formatted history list, or empty list if no snapshots.
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=days)

        result = await db.execute(
            text(
                "SELECT date, total_value, cash, positions_value, total_pnl, total_pnl_percent "
                "FROM portfolio_snapshots "
                "WHERE portfolio_id = :portfolio_id AND date >= :start_date "
                "ORDER BY date ASC"
            ),
            {"portfolio_id": portfolio_id, "start_date": start_date.isoformat()},
        )
        rows = result.fetchall()

        if not rows:
            return []

        return [
            {
                "timestamp": datetime.strptime(row[0], "%Y-%m-%d").isoformat() if isinstance(row[0], str) else row[0],
                "total_value": row[1],
                "cash": row[2],
                "positions_value": row[3],
                "total_pnl": row[4],
                "total_pnl_percent": row[5],
            }
            for row in rows
        ]

    # ── Live computation (fallback) ─────────────────────────────

    @staticmethod
    async def _compute_live_history(
        db: AsyncSession,
        user_id: str,
        portfolio: UserPortfolio,
        days: int,
    ) -> List[Dict]:
        """
        Compute portfolio history live from trades + yfinance.
        Uses batch download (all tickers in one call).
        """
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
            return await PortfolioHistoryService._generate_no_trade_history(
                db, user_id, portfolio, days
            )

        # Determine date range
        end_date = datetime.now(timezone.utc).date()
        start_date = end_date - timedelta(days=days)

        first_trade_date = orders[0].filled_at.date() if orders[0].filled_at else start_date
        if first_trade_date > start_date:
            start_date = first_trade_date

        # Collect unique tickers and batch-fetch prices
        tickers = list(set(o.ticker for o in orders))
        historical_prices = await PortfolioHistoryService._fetch_historical_prices_batch(
            tickers, start_date, end_date
        )

        # Reconstruct portfolio state for each day
        history = []
        positions: Dict[str, float] = {}
        cash = starting_cash
        current_date = start_date
        order_idx = 0

        while current_date <= end_date:
            while order_idx < len(orders):
                order = orders[order_idx]
                order_date = order.filled_at.date() if order.filled_at else None

                if order_date and order_date <= current_date:
                    filled_price = order.filled_price or 0
                    trade_value = order.filled_quantity * filled_price

                    if order.side == "BUY":
                        cash -= trade_value
                        positions[order.ticker] = positions.get(order.ticker, 0) + order.filled_quantity
                    else:
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
                if not price:
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
        starting_cash = portfolio.starting_cash
        current_cash = portfolio.cash_balance

        current_date = start_date
        while current_date <= end_date:
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

    # ── Price fetching ──────────────────────────────────────────

    @staticmethod
    async def _fetch_historical_prices_batch(
        tickers: List[str],
        start_date,
        end_date,
    ) -> Dict[str, Dict]:
        """Fetch historical prices using BATCH yfinance download."""
        if not tickers:
            return {}
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            PortfolioHistoryService._fetch_prices_batch_sync,
            tickers,
            start_date,
            end_date,
        )

    @staticmethod
    def _fetch_prices_batch_sync(
        tickers: List[str],
        start_date,
        end_date,
    ) -> Dict[str, Dict]:
        """Synchronous batch price fetching — all tickers in ONE call."""
        import pandas as pd

        result = {}
        fetch_start = start_date - timedelta(days=5)
        fetch_end = end_date + timedelta(days=1)

        try:
            data = yf.download(
                tickers if len(tickers) > 1 else tickers[0],
                start=fetch_start.isoformat(),
                end=fetch_end.isoformat(),
                progress=False,
                auto_adjust=True,
                group_by="ticker" if len(tickers) > 1 else None,
            )

            if data.empty:
                return {t: {} for t in tickers}

            if len(tickers) == 1:
                ticker = tickers[0]
                result[ticker] = {}
                for idx, row in data.iterrows():
                    d = idx.date() if hasattr(idx, 'date') else idx
                    close = row.get('Close', None)
                    if close is not None:
                        if hasattr(close, 'iloc'):
                            close = close.iloc[0]
                        if pd.notna(close):
                            result[ticker][d] = float(close)
            else:
                for ticker in tickers:
                    result[ticker] = {}
                    try:
                        if ticker in data.columns.get_level_values(0):
                            ticker_data = data[ticker]
                            for idx, row in ticker_data.iterrows():
                                d = idx.date() if hasattr(idx, 'date') else idx
                                close = row.get('Close', None)
                                if close is not None and pd.notna(close):
                                    result[ticker][d] = float(close)
                    except Exception as e:
                        print(f"Error processing {ticker}: {e}")

        except Exception as e:
            print(f"Error batch fetching prices: {e}")
            return {t: {} for t in tickers}

        return result

    @staticmethod
    def _fetch_current_prices_sync(tickers: List[str]) -> Dict[str, float]:
        """Fetch current prices for a list of tickers."""
        import pandas as pd
        result = {}
        if not tickers:
            return result
        try:
            data = yf.download(
                tickers if len(tickers) > 1 else tickers[0],
                period="1d",
                progress=False,
                auto_adjust=True,
                group_by="ticker" if len(tickers) > 1 else None,
            )
            if data.empty:
                return result
            if len(tickers) == 1:
                close = data['Close'].iloc[-1]
                if hasattr(close, 'iloc'):
                    close = close.iloc[0]
                if pd.notna(close):
                    result[tickers[0]] = float(close)
            else:
                for ticker in tickers:
                    try:
                        if ticker in data.columns.get_level_values(0):
                            close = data[ticker]['Close'].iloc[-1]
                            if pd.notna(close):
                                result[ticker] = float(close)
                    except Exception:
                        pass
        except Exception as e:
            print(f"Error fetching current prices: {e}")
        return result

    # ── Keep old method names for backward compatibility ────────

    @staticmethod
    async def _fetch_historical_prices(
        tickers: List[str],
        start_date,
        end_date,
    ) -> Dict[str, Dict]:
        """Legacy method — redirects to batch."""
        return await PortfolioHistoryService._fetch_historical_prices_batch(
            tickers, start_date, end_date
        )

    @staticmethod
    def _fetch_prices_sync(
        tickers: List[str],
        start_date,
        end_date,
    ) -> Dict[str, Dict]:
        """Legacy method — redirects to batch."""
        return PortfolioHistoryService._fetch_prices_batch_sync(
            tickers, start_date, end_date
        )

    @staticmethod
    def _get_nearest_price(
        prices: Dict,
        target_date,
    ) -> Optional[float]:
        """Get the nearest available price to a target date."""
        if not prices:
            return None
        for i in range(7):
            check_date = target_date - timedelta(days=i)
            if check_date in prices:
                return prices[check_date]
        if prices:
            return list(prices.values())[-1]
        return None
