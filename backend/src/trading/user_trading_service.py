"""
F11.4 User Trading Service

High-level service that wraps UserPortfolio/UserPosition/UserOrder operations
for use by API endpoints. Handles order execution (fills market orders, updates
portfolio cash/positions) scoped to a specific user.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import UserPortfolio, UserPosition, UserOrder, ANONYMOUS_USER_ID
from data.price_fetcher import get_price_summary


# REC-127: Portfolio size limits (max distinct positions)
PORTFOLIO_SIZE_LIMITS = {
    "small": {"min": 3, "max": 5},      # Conservative, fewer positions
    "medium": {"min": 5, "max": 10},    # Balanced diversification
    "large": {"min": 10, "max": 15},    # Maximum diversification
}


def get_position_limit(portfolio_size: str = "medium") -> int:
    """Get max position count for portfolio size (REC-127)."""
    limits = PORTFOLIO_SIZE_LIMITS.get(portfolio_size.lower(), PORTFOLIO_SIZE_LIMITS["medium"])
    return limits["max"]


class UserTradingService:
    """Per-user trading operations — portfolio, positions, and orders."""

    # ── Portfolio ────────────────────────────────────────────────────

    @staticmethod
    async def get_or_create_portfolio(
        db: AsyncSession,
        user_id: str,
        starting_cash: float = 100000.0,
    ) -> UserPortfolio:
        """Get existing portfolio or create a new one for the user."""
        result = await db.execute(
            select(UserPortfolio).where(UserPortfolio.user_id == user_id)
        )
        portfolio = result.scalar_one_or_none()

        if portfolio is None:
            portfolio = UserPortfolio(
                id=str(uuid.uuid4()),
                user_id=user_id,
                cash_balance=starting_cash,
                starting_cash=starting_cash,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            db.add(portfolio)
            await db.commit()
            await db.refresh(portfolio)

        return portfolio

    @staticmethod
    async def get_positions(
        db: AsyncSession,
        portfolio_id: str,
    ) -> List[UserPosition]:
        """Get all positions for a portfolio."""
        result = await db.execute(
            select(UserPosition).where(UserPosition.portfolio_id == portfolio_id)
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_portfolio_data(
        db: AsyncSession,
        user_id: str,
    ) -> dict:
        """Get full portfolio data (summary + holdings) for a user."""
        portfolio = await UserTradingService.get_or_create_portfolio(db, user_id)
        positions = await UserTradingService.get_positions(db, portfolio.id)

        holdings = []
        total_market_value = 0.0
        for pos in positions:
            holding = pos.to_dict()
            # Try to get current price
            try:
                price_data = get_price_summary(pos.ticker)
                if price_data and price_data.get("price"):
                    current_price = price_data["price"]
                    market_value = pos.quantity * current_price
                    cost_basis = pos.quantity * pos.avg_cost
                    unrealized_pnl = (current_price - pos.avg_cost) * pos.quantity
                    unrealized_pnl_pct = ((current_price - pos.avg_cost) / pos.avg_cost * 100) if pos.avg_cost else 0
                    holding["current_price"] = current_price
                    holding["market_value"] = round(market_value, 2)
                    holding["cost_basis"] = round(cost_basis, 2)  # BUG-010
                    holding["unrealized_pnl"] = round(unrealized_pnl, 2)
                    holding["unrealized_pnl_percent"] = round(unrealized_pnl_pct, 2)  # BUG-010
                    total_market_value += market_value
            except Exception:
                # Use avg_cost as fallback so iOS decode doesn't break
                holding["current_price"] = pos.avg_cost
                holding["market_value"] = round(pos.quantity * pos.avg_cost, 2)
                holding["cost_basis"] = round(pos.quantity * pos.avg_cost, 2)
                holding["unrealized_pnl"] = 0.0
                holding["unrealized_pnl_percent"] = 0.0
                total_market_value += pos.quantity * pos.avg_cost
            holdings.append(holding)

        total_value = portfolio.cash_balance + total_market_value
        total_pnl = total_value - portfolio.starting_cash

        summary = {
            "total_value": round(total_value, 2),
            "cash": round(portfolio.cash_balance, 2),
            "invested": round(total_market_value, 2),
            "positions_value": round(total_market_value, 2),  # BUG-009: iOS expects this field
            "total_pnl": round(total_pnl, 2),
            "total_pnl_percent": round(
                (total_pnl / portfolio.starting_cash * 100) if portfolio.starting_cash else 0, 2
            ),
            "daily_pnl": 0.0,  # BUG-009: iOS expects this (no intraday tracking yet)
            "daily_pnl_percent": 0.0,  # BUG-009: iOS expects this
            "starting_cash": portfolio.starting_cash,
            "position_count": len(positions),
            "positions_count": len(positions),  # BUG-009: iOS expects this field name
        }

        return {
            "summary": summary,
            "holdings": holdings,
            "is_paper": portfolio.is_paper,
            "realized_pnl": round(portfolio.realized_pnl, 2),
        }

    @staticmethod
    async def reset_portfolio(
        db: AsyncSession,
        user_id: str,
        starting_cash: float = 100000.0,
    ) -> UserPortfolio:
        """Reset a user's portfolio — clear positions, reset cash."""
        result = await db.execute(
            select(UserPortfolio).where(UserPortfolio.user_id == user_id)
        )
        portfolio = result.scalar_one_or_none()

        if portfolio:
            # Delete all positions
            positions_result = await db.execute(
                select(UserPosition).where(UserPosition.portfolio_id == portfolio.id)
            )
            for pos in positions_result.scalars().all():
                await db.delete(pos)

            # Delete all orders
            orders_result = await db.execute(
                select(UserOrder).where(UserOrder.user_id == user_id)
            )
            for order in orders_result.scalars().all():
                await db.delete(order)

            portfolio.cash_balance = starting_cash
            portfolio.starting_cash = starting_cash
            portfolio.realized_pnl = 0.0
            portfolio.updated_at = datetime.now(timezone.utc)
        else:
            portfolio = UserPortfolio(
                id=str(uuid.uuid4()),
                user_id=user_id,
                cash_balance=starting_cash,
                starting_cash=starting_cash,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            db.add(portfolio)

        await db.commit()
        await db.refresh(portfolio)
        return portfolio

    # ── Orders ───────────────────────────────────────────────────────

    @staticmethod
    async def create_order(
        db: AsyncSession,
        user_id: str,
        ticker: str,
        side: str,
        quantity: float,
        order_type: str = "MARKET",
        limit_price: Optional[float] = None,
        is_paper: bool = True,
        portfolio_size: str = "medium",  # REC-127
    ) -> UserOrder:
        """Create and execute an order for a user.
        
        Market orders are filled immediately at current price.
        Limit orders are stored as PENDING.
        
        REC-127: portfolio_size limits max positions (small=5, medium=10, large=15).
        """
        ticker = ticker.upper()
        side = side.upper()
        order_type = order_type.upper()

        if side not in ("BUY", "SELL"):
            raise ValueError(f"Invalid side: {side}")
        if order_type not in ("MARKET", "LIMIT"):
            raise ValueError(f"Invalid order type: {order_type}")
        if quantity <= 0:
            raise ValueError("Quantity must be positive")
        if order_type == "LIMIT" and limit_price is None:
            raise ValueError("Limit price required for LIMIT orders")

        # Validate ticker against stock universe
        from src.data.stock_universe import load_universe
        universe = load_universe()
        if universe:
            valid_tickers = {s["ticker"] for s in universe.get("stocks", [])}
            if ticker.upper() not in valid_tickers:
                raise ValueError(f"Unknown ticker: {ticker}. Not in stock universe.")

        # Get portfolio
        portfolio = await UserTradingService.get_or_create_portfolio(db, user_id)
        
        # REC-127: Check position limit for BUY orders (new positions only)
        if side == "BUY":
            # Check if user already has a position in this ticker
            existing_pos = await db.execute(
                select(UserPosition).where(
                    and_(
                        UserPosition.portfolio_id == portfolio.id,
                        UserPosition.ticker == ticker,
                    )
                )
            )
            has_existing = existing_pos.scalar_one_or_none() is not None
            
            if not has_existing:
                # New position — check against limit
                pos_count_result = await db.execute(
                    select(func.count(UserPosition.id)).where(
                        UserPosition.portfolio_id == portfolio.id
                    )
                )
                current_count = pos_count_result.scalar() or 0
                max_positions = get_position_limit(portfolio_size)
                
                if current_count >= max_positions:
                    raise ValueError(
                        f"Position limit reached ({current_count}/{max_positions}). "
                        f"Portfolio size '{portfolio_size}' allows max {max_positions} positions. "
                        f"Sell an existing position first or upgrade your portfolio size."
                    )

        # Determine fill price for market orders
        fill_price = None
        status = "PENDING"
        filled_quantity = 0.0
        filled_at = None

        if order_type == "MARKET":
            # Get current price — reject if unavailable
            try:
                price_data = get_price_summary(ticker)
                if price_data and price_data.get("price"):
                    fill_price = price_data["price"]
                else:
                    raise ValueError(f"Cannot get price for {ticker}. Market may be closed or ticker is invalid.")
            except ValueError:
                raise
            except Exception as e:
                raise ValueError(f"Price lookup failed for {ticker}: {e}")

            # Execute immediately
            total_cost = fill_price * quantity

            if side == "BUY":
                if portfolio.cash_balance < total_cost:
                    raise ValueError(
                        f"Insufficient cash. Need ${total_cost:.2f}, have ${portfolio.cash_balance:.2f}"
                    )
                portfolio.cash_balance -= total_cost

                # Update or create position
                pos_result = await db.execute(
                    select(UserPosition).where(
                        and_(
                            UserPosition.portfolio_id == portfolio.id,
                            UserPosition.ticker == ticker,
                        )
                    )
                )
                position = pos_result.scalar_one_or_none()

                if position:
                    # Average up/down
                    total_qty = position.quantity + quantity
                    position.avg_cost = (
                        (position.avg_cost * position.quantity + fill_price * quantity)
                        / total_qty
                    )
                    position.quantity = total_qty
                else:
                    position = UserPosition(
                        id=str(uuid.uuid4()),
                        portfolio_id=portfolio.id,
                        ticker=ticker,
                        quantity=quantity,
                        avg_cost=fill_price,
                        opened_at=datetime.now(timezone.utc),
                    )
                    db.add(position)

            elif side == "SELL":
                # Find position to sell
                pos_result = await db.execute(
                    select(UserPosition).where(
                        and_(
                            UserPosition.portfolio_id == portfolio.id,
                            UserPosition.ticker == ticker,
                        )
                    )
                )
                position = pos_result.scalar_one_or_none()

                if position is None or position.quantity < quantity:
                    available = position.quantity if position else 0
                    raise ValueError(
                        f"Insufficient shares. Have {available}, trying to sell {quantity}"
                    )

                # Realize P&L
                realized = (fill_price - position.avg_cost) * quantity
                portfolio.realized_pnl += realized
                portfolio.cash_balance += total_cost

                position.quantity -= quantity
                if position.quantity <= 0:
                    await db.delete(position)

            status = "FILLED"
            filled_quantity = quantity
            filled_at = datetime.now(timezone.utc)
            portfolio.updated_at = datetime.now(timezone.utc)

        elif order_type == "LIMIT":
            fill_price = limit_price

        # Create order record
        order = UserOrder(
            id=str(uuid.uuid4())[:8],
            user_id=user_id,
            ticker=ticker,
            side=side,
            quantity=quantity,
            order_type=order_type,
            limit_price=limit_price,
            status=status,
            filled_quantity=filled_quantity,
            filled_price=fill_price if status == "FILLED" else None,
            filled_at=filled_at,
            is_paper=is_paper,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(order)
        await db.commit()
        await db.refresh(order)

        return order

    @staticmethod
    async def get_orders(
        db: AsyncSession,
        user_id: str,
        status: Optional[str] = None,
        ticker: Optional[str] = None,
        limit: int = 50,
    ) -> List[UserOrder]:
        """Get orders for a user, optionally filtered."""
        query = select(UserOrder).where(UserOrder.user_id == user_id)

        if status:
            query = query.where(UserOrder.status == status.upper())
        if ticker:
            query = query.where(UserOrder.ticker == ticker.upper())

        query = query.order_by(UserOrder.created_at.desc()).limit(limit)

        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_todays_orders(
        db: AsyncSession,
        user_id: str,
    ) -> List[UserOrder]:
        """Get today's orders for a user."""
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        query = (
            select(UserOrder)
            .where(
                and_(
                    UserOrder.user_id == user_id,
                    UserOrder.created_at >= today_start,
                )
            )
            .order_by(UserOrder.created_at.desc())
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_portfolio_summary(
        db: AsyncSession,
        user_id: str,
    ) -> dict:
        """Get portfolio summary (total value, P&L) for a user."""
        data = await UserTradingService.get_portfolio_data(db, user_id)
        summary = data["summary"]
        summary["is_paper"] = data["is_paper"]
        return summary

    @staticmethod
    async def get_portfolio_holdings(
        db: AsyncSession,
        user_id: str,
    ) -> list:
        """Get portfolio holdings for a user."""
        data = await UserTradingService.get_portfolio_data(db, user_id)
        return data["holdings"]

    @staticmethod
    async def get_portfolio_sectors(
        db: AsyncSession,
        user_id: str,
    ) -> list:
        """Get sector allocation for a user's portfolio."""
        from data.stock_universe import get_universe

        portfolio = await UserTradingService.get_or_create_portfolio(db, user_id)
        positions = await UserTradingService.get_positions(db, portfolio.id)

        if not positions:
            return []

        # Build sector map from universe
        universe = get_universe()
        ticker_sector = {s["ticker"]: s.get("sector", "Unknown") for s in universe}

        sector_totals: dict[str, float] = {}
        total_invested = 0.0

        for pos in positions:
            try:
                price_data = get_price_summary(pos.ticker)
                price = price_data["price"] if price_data and price_data.get("price") else pos.avg_cost
            except Exception:
                price = pos.avg_cost
            market_value = pos.quantity * price
            sector = ticker_sector.get(pos.ticker, "Unknown")
            sector_totals[sector] = sector_totals.get(sector, 0.0) + market_value
            total_invested += market_value

        if total_invested == 0:
            return []

        return [
            {
                "sector": sector,
                "value": round(value, 2),
                "percentage": round(value / total_invested * 100, 2),
            }
            for sector, value in sorted(sector_totals.items(), key=lambda x: -x[1])
        ]

    @staticmethod
    async def get_pending_orders(
        db: AsyncSession,
        user_id: str,
    ) -> List[UserOrder]:
        """Get pending orders for a user."""
        result = await db.execute(
            select(UserOrder).where(
                and_(
                    UserOrder.user_id == user_id,
                    UserOrder.status == "PENDING",
                )
            ).order_by(UserOrder.created_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_order_by_id(
        db: AsyncSession,
        user_id: str,
        order_id: str,
    ) -> Optional[UserOrder]:
        """Get a specific order by ID for a user."""
        result = await db.execute(
            select(UserOrder).where(
                and_(
                    UserOrder.id == order_id,
                    UserOrder.user_id == user_id,
                )
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def cancel_order(
        db: AsyncSession,
        user_id: str,
        order_id: str,
    ) -> UserOrder:
        """Cancel a pending order."""
        result = await db.execute(
            select(UserOrder).where(
                and_(
                    UserOrder.id == order_id,
                    UserOrder.user_id == user_id,
                )
            )
        )
        order = result.scalar_one_or_none()

        if order is None:
            raise ValueError(f"Order not found: {order_id}")
        if order.status != "PENDING":
            raise ValueError(f"Cannot cancel order with status: {order.status}")

        order.status = "CANCELLED"
        order.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(order)

        return order
