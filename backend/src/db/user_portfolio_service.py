"""
F11.4 Per-User Portfolio Service

Manages portfolios, positions, and orders per-user in SQLite.
Falls back to anonymous user when AUTH_REQUIRED=False.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import UserPortfolio, UserPosition, UserOrder, ANONYMOUS_USER_ID


class UserPortfolioService:
    """Per-user portfolio operations using SQLAlchemy async sessions."""

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
    async def get_position(
        db: AsyncSession,
        portfolio_id: str,
        ticker: str,
    ) -> Optional[UserPosition]:
        """Get a specific position."""
        result = await db.execute(
            select(UserPosition).where(
                and_(
                    UserPosition.portfolio_id == portfolio_id,
                    UserPosition.ticker == ticker.upper(),
                )
            )
        )
        return result.scalar_one_or_none()

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
            positions = await UserPortfolioService.get_positions(db, portfolio.id)
            for pos in positions:
                await db.delete(pos)

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
            )
            db.add(portfolio)

        await db.commit()
        await db.refresh(portfolio)
        return portfolio

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
    ) -> UserOrder:
        """Create a new order for a user."""
        order = UserOrder(
            id=str(uuid.uuid4())[:8],
            user_id=user_id,
            ticker=ticker.upper(),
            side=side.upper(),
            quantity=quantity,
            order_type=order_type.upper(),
            limit_price=limit_price,
            is_paper=is_paper,
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
        limit: int = 50,
    ) -> List[UserOrder]:
        """Get orders for a user, optionally filtered by status."""
        query = select(UserOrder).where(UserOrder.user_id == user_id)

        if status:
            query = query.where(UserOrder.status == status.upper())

        query = query.order_by(UserOrder.created_at.desc()).limit(limit)

        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_order(
        db: AsyncSession,
        user_id: str,
        order_id: str,
    ) -> Optional[UserOrder]:
        """Get a specific order (scoped to user)."""
        result = await db.execute(
            select(UserOrder).where(
                and_(
                    UserOrder.id == order_id,
                    UserOrder.user_id == user_id,
                )
            )
        )
        return result.scalar_one_or_none()
