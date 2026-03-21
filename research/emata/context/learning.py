"""
Learning Loop Module (REC-289)

Tracks outcomes of past decisions and generates lessons for future retrieval.

The learning loop:
1. Gets decisions from 1-4 weeks ago
2. Calculates outcomes (P&L %)
3. Uses Claude to reflect and generate lessons
4. Stores lessons in memory for future retrieval

Outcomes are only recorded when:
- Position is closed (sold)
- OR 14+ days have passed (timeout)
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from enum import Enum

from .memory import AgentMemory, Decision, get_agent_memory
from .decision_pairs import get_decision_pair_logger

# LLM import with fallback
try:
    from ..llm.factory import LLMFactory
except ImportError:
    # Stub for testing
    class LLMFactory:
        def create(self, model_name: str):
            return None

logger = logging.getLogger(__name__)


class OutcomeTag(Enum):
    """Tags for categorizing trade outcomes."""
    STRONG_WIN = "strong_win"      # > +10%
    WIN = "win"                     # +5% to +10%
    SMALL_WIN = "small_win"         # +1% to +5%
    NEUTRAL = "neutral"             # -1% to +1%
    LOSS = "loss"                   # -1% to -5%
    STRONG_LOSS = "strong_loss"     # < -5%
    
    @classmethod
    def from_outcome(cls, outcome_pct: float) -> "OutcomeTag":
        if outcome_pct > 10:
            return cls.STRONG_WIN
        elif outcome_pct > 5:
            return cls.WIN
        elif outcome_pct > 1:
            return cls.SMALL_WIN
        elif outcome_pct > -1:
            return cls.NEUTRAL
        elif outcome_pct > -5:
            return cls.LOSS
        else:
            return cls.STRONG_LOSS
    
    @property
    def emoji(self) -> str:
        return {
            OutcomeTag.STRONG_WIN: "🏆",
            OutcomeTag.WIN: "✅",
            OutcomeTag.SMALL_WIN: "✅",
            OutcomeTag.NEUTRAL: "➖",
            OutcomeTag.LOSS: "❌",
            OutcomeTag.STRONG_LOSS: "💀",
        }[self]


@dataclass
class TradeOutcome:
    """Outcome of a completed trade."""
    decision_id: str
    ticker: str
    action: str
    entry_price: float
    exit_price: float
    outcome_pct: float
    outcome_tag: OutcomeTag
    entry_date: datetime
    exit_date: datetime
    holding_days: int
    pnl_dollars: float
    shares: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "ticker": self.ticker,
            "action": self.action,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "outcome_pct": self.outcome_pct,
            "outcome_tag": self.outcome_tag.value,
            "entry_date": self.entry_date.isoformat(),
            "exit_date": self.exit_date.isoformat(),
            "holding_days": self.holding_days,
            "pnl_dollars": self.pnl_dollars,
            "shares": self.shares,
        }


@dataclass
class LessonLearned:
    """A lesson generated from a trade outcome."""
    decision_id: str
    ticker: str
    action: str
    outcome_pct: float
    lesson: str
    context_summary: str
    generated_at: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "ticker": self.ticker,
            "action": self.action,
            "outcome_pct": self.outcome_pct,
            "lesson": self.lesson,
            "context_summary": self.context_summary,
            "generated_at": self.generated_at.isoformat(),
        }


class LearningLoop:
    """
    Tracks outcomes and generates lessons from past decisions.
    
    Runs weekly to:
    1. Find decisions needing outcome updates
    2. Calculate P&L for closed/expired positions
    3. Generate lessons using Claude
    4. Store lessons in memory
    """
    
    # Configuration
    MIN_HOLDING_DAYS = 7       # Minimum days before checking outcome
    MAX_HOLDING_DAYS = 14      # Force outcome after this many days
    OUTCOME_BATCH_SIZE = 10    # Process this many at a time
    
    def __init__(
        self,
        memory: Optional[AgentMemory] = None,
        llm_factory: Optional[LLMFactory] = None,
    ):
        self._memory = memory  # May be None; lazy init via _ensure_memory()
        self.llm_factory = llm_factory or LLMFactory()
        self._lessons_generated: List[LessonLearned] = []
    
    @property
    def memory(self) -> AgentMemory:
        """Get memory instance (for backward compatibility)."""
        return self._memory
    
    async def _ensure_memory(self) -> AgentMemory:
        """Ensure memory is initialized (lazy init)."""
        if self._memory is None:
            self._memory = await get_agent_memory()
        return self._memory
    
    async def run_weekly_update(self) -> Dict[str, Any]:
        """
        Run the weekly learning update.
        
        Called after market close on Friday or Sunday before trading loop.
        
        Returns:
            Summary of updates made
        """
        logger.info("Starting weekly learning update...")
        
        results = {
            "decisions_checked": 0,
            "outcomes_recorded": 0,
            "lessons_generated": 0,
            "errors": [],
        }
        
        try:
            # Get decisions needing outcome updates
            pending = await self._get_pending_outcomes()
            results["decisions_checked"] = len(pending)
            logger.info(f"Found {len(pending)} decisions needing outcome updates")
            
            for decision in pending:
                try:
                    # Calculate outcome
                    outcome = await self._calculate_outcome(decision)
                    
                    if outcome:
                        # Generate lesson
                        lesson = await self._generate_lesson(decision, outcome)
                        
                        # Store in memory
                        await self._store_outcome_and_lesson(decision, outcome, lesson)
                        
                        results["outcomes_recorded"] += 1
                        results["lessons_generated"] += 1
                        
                        logger.info(
                            f"Recorded outcome for {decision.ticker}: "
                            f"{outcome.outcome_pct:+.1f}%"
                        )
                
                except Exception as e:
                    error_msg = f"Error processing {decision.ticker}: {e}"
                    results["errors"].append(error_msg)
                    logger.error(error_msg)
            
            logger.info(
                f"Learning update complete: "
                f"{results['outcomes_recorded']} outcomes, "
                f"{results['lessons_generated']} lessons"
            )
            
        except Exception as e:
            results["errors"].append(f"Fatal error: {e}")
            logger.error(f"Learning update failed: {e}")
        
        return results
    
    async def _get_pending_outcomes(self) -> List[Decision]:
        """Get decisions that need outcome updates."""
        # Get decisions from 7-60 days ago without outcomes
        cutoff_recent = datetime.utcnow() - timedelta(days=self.MIN_HOLDING_DAYS)
        cutoff_old = datetime.utcnow() - timedelta(days=60)
        
        memory = await self._ensure_memory()
        decisions = await memory.get_decisions_without_outcomes(
            after=cutoff_old,
            before=cutoff_recent,
            limit=self.OUTCOME_BATCH_SIZE,
        )
        
        return decisions
    
    async def _calculate_outcome(
        self,
        decision: Decision,
    ) -> Optional[TradeOutcome]:
        """
        Calculate the outcome of a decision.
        
        Returns outcome if position is closed or timeout reached.
        """
        entry_date = decision.timestamp
        entry_price = decision.price
        holding_days = (datetime.utcnow() - entry_date).days
        
        # Check if position is still open
        position_status = await self._get_position_status(
            decision.ticker,
            decision.user_id,
        )
        
        if position_status["is_open"] and holding_days < self.MAX_HOLDING_DAYS:
            # Position still open and not timed out
            return None
        
        # Get exit price
        if position_status["is_open"]:
            # Timeout - use current price as exit
            exit_price = await self._get_current_price(decision.ticker)
            exit_date = datetime.utcnow()
        else:
            # Position closed - use actual exit
            exit_price = position_status.get("exit_price", entry_price)
            exit_date = position_status.get("exit_date", datetime.utcnow())
        
        # Calculate P&L
        if decision.action == "BUY":
            outcome_pct = (exit_price - entry_price) / entry_price * 100
            pnl_dollars = (exit_price - entry_price) * decision.shares
        else:  # SELL
            # For shorts (not implemented yet), flip the calculation
            outcome_pct = (entry_price - exit_price) / entry_price * 100
            pnl_dollars = (entry_price - exit_price) * decision.shares
        
        return TradeOutcome(
            decision_id=decision.id,
            ticker=decision.ticker,
            action=decision.action,
            entry_price=entry_price,
            exit_price=exit_price,
            outcome_pct=outcome_pct,
            outcome_tag=OutcomeTag.from_outcome(outcome_pct),
            entry_date=entry_date,
            exit_date=exit_date,
            holding_days=holding_days,
            pnl_dollars=pnl_dollars,
            shares=decision.shares,
        )
    
    async def _generate_lesson(
        self,
        decision: Decision,
        outcome: TradeOutcome,
    ) -> LessonLearned:
        """
        Generate a lesson from a trade outcome using Claude.
        
        The lesson should be concise (1-2 sentences) and actionable.
        """
        prompt = f"""I made this trading decision:

Action: {decision.action} {decision.ticker}
Score at time: {decision.score:.1f}
Regime at time: {decision.regime}
Rationale: {decision.rationale}
Holding period: {outcome.holding_days} days

Outcome: {outcome.outcome_pct:+.1f}% ({outcome.outcome_tag.emoji} {outcome.outcome_tag.value.replace('_', ' ')})
P&L: ${outcome.pnl_dollars:+,.0f}

What lesson should I remember for similar future situations?
Keep it to 1-2 sentences. Be specific and actionable."""

        try:
            llm = self.llm_factory.create("haiku")
            response = await llm.generate(
                prompt=prompt,
                system="You are an expert trader reflecting on past decisions. Generate concise, actionable lessons.",
                max_tokens=150,
            )
            lesson_text = response.strip()
        except Exception as e:
            logger.warning(f"LLM lesson generation failed: {e}")
            lesson_text = self._generate_fallback_lesson(outcome)
        
        lesson = LessonLearned(
            decision_id=decision.id,
            ticker=decision.ticker,
            action=decision.action,
            outcome_pct=outcome.outcome_pct,
            lesson=lesson_text,
            context_summary=f"Score {decision.score:.0f}, {decision.regime} regime",
            generated_at=datetime.utcnow(),
        )
        
        self._lessons_generated.append(lesson)
        return lesson
    
    def _generate_fallback_lesson(self, outcome: TradeOutcome) -> str:
        """Generate a simple lesson without LLM."""
        tag = outcome.outcome_tag
        
        if tag in (OutcomeTag.STRONG_WIN, OutcomeTag.WIN):
            return f"Trade on {outcome.ticker} worked well (+{outcome.outcome_pct:.1f}%). Consider similar setups."
        elif tag == OutcomeTag.SMALL_WIN:
            return f"Modest gain on {outcome.ticker}. Holding period of {outcome.holding_days} days was reasonable."
        elif tag == OutcomeTag.NEUTRAL:
            return f"Breakeven on {outcome.ticker}. No strong signal either way."
        elif tag == OutcomeTag.LOSS:
            return f"Small loss on {outcome.ticker} ({outcome.outcome_pct:.1f}%). Review entry timing."
        else:  # STRONG_LOSS
            return f"Significant loss on {outcome.ticker} ({outcome.outcome_pct:.1f}%). Need stricter risk management."
    
    async def _store_outcome_and_lesson(
        self,
        decision: Decision,
        outcome: TradeOutcome,
        lesson: LessonLearned,
    ):
        """Store outcome and lesson in memory + decision pairs (REC-298)."""
        memory = await self._ensure_memory()
        await memory.update_outcome(
            decision_id=decision.id,
            outcome_pct=outcome.outcome_pct,
            outcome_date=outcome.exit_date,
        )
        
        await memory.store_lesson(
            decision_id=decision.id,
            lesson=lesson.lesson,
        )
        
        # Also update decision pairs for DPO training (REC-298)
        try:
            pair_logger = get_decision_pair_logger()
            # Find the decision pair record by decision_id
            # Note: decision.id is the memory DB id, we need to correlate
            # For now, we'll log by searching for matching context
            await pair_logger.record_outcome(
                record_id=decision.id,  # This assumes IDs match
                outcome_pct=outcome.outcome_pct,
                lesson=lesson.lesson,
            )
        except Exception as e:
            logger.warning(f"Failed to update decision pair outcome: {e}")
    
    async def _get_position_status(
        self,
        ticker: str,
        user_id: str,
    ) -> Dict[str, Any]:
        """
        Check if position is still open by querying the database (REC-319).
        
        Returns:
            - is_open: True if position has shares > 0
            - exit_price: Fill price of most recent SELL order if closed
            - exit_date: Date of exit if closed
        """
        try:
            from auth.database import async_session_factory
            from db.models import UserPortfolio, UserPosition, UserOrder
            from sqlalchemy import select, and_, desc
            
            async with async_session_factory() as db:
                # Get user's portfolio
                result = await db.execute(
                    select(UserPortfolio).where(UserPortfolio.user_id == user_id)
                )
                portfolio = result.scalars().first()
                
                if not portfolio:
                    # No portfolio = no position
                    return {"is_open": False, "exit_price": None, "exit_date": None}
                
                # Check current position
                result = await db.execute(
                    select(UserPosition).where(
                        and_(
                            UserPosition.portfolio_id == portfolio.id,
                            UserPosition.ticker == ticker.upper()
                        )
                    )
                )
                position = result.scalars().first()
                
                if position and position.quantity > 0:
                    # Position still open
                    return {"is_open": True, "exit_price": None, "exit_date": None}
                
                # Position closed (or never existed) - find most recent SELL order
                result = await db.execute(
                    select(UserOrder).where(
                        and_(
                            UserOrder.user_id == user_id,
                            UserOrder.ticker == ticker.upper(),
                            UserOrder.side == "SELL",
                            UserOrder.status == "FILLED"
                        )
                    ).order_by(desc(UserOrder.filled_at)).limit(1)
                )
                sell_order = result.scalars().first()
                
                if sell_order:
                    return {
                        "is_open": False,
                        "exit_price": sell_order.filled_price,
                        "exit_date": sell_order.filled_at.isoformat() if sell_order.filled_at else None,
                    }
                
                # No position and no sell order found
                return {"is_open": False, "exit_price": None, "exit_date": None}
                
        except Exception as e:
            logger.warning(f"Failed to get position status for {ticker}: {e}")
            # Fallback: assume open to avoid premature outcome calculation
            return {"is_open": True, "exit_price": None, "exit_date": None}
    
    async def _get_current_price(self, ticker: str) -> float:
        """Get current price for timeout calculations."""
        try:
            import yfinance as yf
            stock = yf.Ticker(ticker)
            hist = stock.history(period="1d")
            if not hist.empty:
                return float(hist["Close"].iloc[-1])
        except Exception as e:
            logger.warning(f"Price fetch failed for {ticker}: {e}")
        return 100.0
    
    async def get_recent_lessons(self, limit: int = 20) -> List[LessonLearned]:
        """Get recently generated lessons."""
        return self._lessons_generated[-limit:]
    
    async def get_learning_stats(self) -> Dict[str, Any]:
        """Get statistics about learning outcomes."""
        lessons = self._lessons_generated
        
        if not lessons:
            return {
                "total_lessons": 0,
                "avg_outcome": 0.0,
                "win_rate": 0.0,
                "by_tag": {},
            }
        
        outcomes = [l.outcome_pct for l in lessons]
        wins = sum(1 for o in outcomes if o > 0)
        
        by_tag = {}
        for l in lessons:
            tag = OutcomeTag.from_outcome(l.outcome_pct)
            by_tag[tag.value] = by_tag.get(tag.value, 0) + 1
        
        return {
            "total_lessons": len(lessons),
            "avg_outcome": sum(outcomes) / len(outcomes),
            "win_rate": wins / len(lessons) * 100,
            "by_tag": by_tag,
        }


# Module-level instance
_learning_loop: Optional[LearningLoop] = None


def get_learning_loop() -> LearningLoop:
    """Get or create the global learning loop instance."""
    global _learning_loop
    if _learning_loop is None:
        _learning_loop = LearningLoop()
    return _learning_loop


async def run_learning_update() -> Dict[str, Any]:
    """Convenience function to run learning update."""
    loop = get_learning_loop()
    return await loop.run_weekly_update()
