"""
Weekly Trading Loop Module (REC-290)

Main orchestrator that runs the complete trading cycle.

Runs every Sunday at 01:00 AM (after pipeline completes):
1. Aggregate context (portfolio, market, candidates)
2. Retrieve similar past situations from memory
3. Use Claude to make trading decisions
4. Size positions using risk parity
5. Validate against risk limits
6. Execute trades (supervised or autonomous)
7. Store decisions for future learning
8. Update outcomes for past decisions

Can also be triggered on-demand via API.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum

from .context import ContextAggregator, TradingContext, aggregate_context
from .memory import AgentMemory, get_agent_memory
from .position_sizing import PositionSizer, SizedPosition, size_positions
from .decision_engine import DecisionEngine, DecisionResult, make_decisions
from .risk_validator import RiskValidator, RiskValidation, validate_trades
from .executor import (
    TradeExecutor,
    ExecutorSettings,
    ExecutionMode,
    ExecutionResult,
    get_executor,
)
from .learning import LearningLoop, run_learning_update
from .decision_pairs import (
    DecisionPairLogger,
    DecisionContext,
    get_decision_pair_logger,
)

logger = logging.getLogger(__name__)


class AgentStatus(Enum):
    """Agent operational status."""
    ACTIVE = "active"
    PAUSED = "paused"
    RUNNING = "running"
    ERROR = "error"


@dataclass
class TradingLoopResult:
    """Result of a trading loop execution."""
    success: bool
    run_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    
    # Pipeline stages
    context_aggregated: bool = False
    memories_retrieved: int = 0
    decisions_made: int = 0
    positions_sized: int = 0
    validations_passed: int = 0
    executions_attempted: int = 0
    executions_succeeded: int = 0
    
    # Details
    decisions: List[Dict[str, Any]] = field(default_factory=list)
    executions: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    # Learning
    learning_outcomes_recorded: int = 0
    
    @property
    def duration_seconds(self) -> float:
        if self.completed_at and self.started_at:
            return (self.completed_at - self.started_at).total_seconds()
        return 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "run_id": self.run_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds,
            "context_aggregated": self.context_aggregated,
            "memories_retrieved": self.memories_retrieved,
            "decisions_made": self.decisions_made,
            "positions_sized": self.positions_sized,
            "validations_passed": self.validations_passed,
            "executions_attempted": self.executions_attempted,
            "executions_succeeded": self.executions_succeeded,
            "decisions": self.decisions,
            "executions": self.executions,
            "errors": self.errors,
            "warnings": self.warnings,
            "learning_outcomes_recorded": self.learning_outcomes_recorded,
        }


@dataclass
class AgentSettings:
    """Agent configuration settings."""
    mode: ExecutionMode = ExecutionMode.SUPERVISED
    max_trades_per_week: int = 5
    min_score_for_buy: float = 75.0
    max_score_for_sell: float = 40.0
    risk_profile: str = "moderate"  # conservative, moderate, aggressive
    stop_loss_enabled: bool = True
    stop_loss_percent: float = 8.0
    auto_run_enabled: bool = True
    auto_run_day: str = "sunday"
    auto_run_hour: int = 1
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentSettings":
        return cls(
            mode=ExecutionMode(data.get("mode", "supervised")),
            max_trades_per_week=data.get("max_trades_per_week", 5),
            min_score_for_buy=data.get("min_score_for_buy", 75.0),
            max_score_for_sell=data.get("max_score_for_sell", 40.0),
            risk_profile=data.get("risk_profile", "moderate"),
            stop_loss_enabled=data.get("stop_loss_enabled", True),
            stop_loss_percent=data.get("stop_loss_percent", 8.0),
            auto_run_enabled=data.get("auto_run_enabled", True),
            auto_run_day=data.get("auto_run_day", "sunday"),
            auto_run_hour=data.get("auto_run_hour", 1),
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode.value,
            "max_trades_per_week": self.max_trades_per_week,
            "min_score_for_buy": self.min_score_for_buy,
            "max_score_for_sell": self.max_score_for_sell,
            "risk_profile": self.risk_profile,
            "stop_loss_enabled": self.stop_loss_enabled,
            "stop_loss_percent": self.stop_loss_percent,
            "auto_run_enabled": self.auto_run_enabled,
            "auto_run_day": self.auto_run_day,
            "auto_run_hour": self.auto_run_hour,
        }


class TradingLoop:
    """
    Main trading loop orchestrator.
    
    Coordinates all agent components to execute the weekly trading cycle.
    """
    
    def __init__(
        self,
        memory: Optional[AgentMemory] = None,
        executor: Optional[TradeExecutor] = None,
    ):
        self.memory = memory  # Will be initialized in initialize() if None
        self.executor = executor or get_executor()
        
        # Components (initialized on first run)
        self._context_aggregator: Optional[ContextAggregator] = None
        self._position_sizer: Optional[PositionSizer] = None
        self._decision_engine: Optional[DecisionEngine] = None
        self._risk_validator: Optional[RiskValidator] = None
        self._learning_loop: Optional[LearningLoop] = None
        
        # State
        self._status: AgentStatus = AgentStatus.PAUSED
        self._settings: AgentSettings = AgentSettings()
        self._last_run: Optional[TradingLoopResult] = None
        self._run_history: List[TradingLoopResult] = []
    
    @property
    def status(self) -> AgentStatus:
        return self._status
    
    @property
    def settings(self) -> AgentSettings:
        return self._settings
    
    @property
    def last_run(self) -> Optional[TradingLoopResult]:
        return self._last_run
    
    async def initialize(self):
        """Initialize all components."""
        from .context import ContextAggregator
        from .position_sizing import PositionSizer
        from .decision_engine import DecisionEngine
        from .risk_validator import RiskValidator
        from .learning import LearningLoop
        
        # Initialize memory if not provided
        if self.memory is None:
            self.memory = await get_agent_memory()
        
        self._context_aggregator = ContextAggregator()
        self._position_sizer = PositionSizer()
        self._decision_engine = DecisionEngine()
        self._risk_validator = RiskValidator()
        self._learning_loop = LearningLoop(memory=self.memory)
        
        await self.executor.initialize()
    
    def update_settings(self, settings: AgentSettings):
        """Update agent settings."""
        self._settings = settings
        logger.info(f"Agent settings updated: {settings.to_dict()}")
    
    def pause(self):
        """Pause the agent."""
        self._status = AgentStatus.PAUSED
        logger.info("Agent paused")
    
    def resume(self):
        """Resume the agent."""
        self._status = AgentStatus.ACTIVE
        logger.info("Agent resumed")
    
    async def run(
        self,
        user_id: str,
        dry_run: bool = False,
    ) -> TradingLoopResult:
        """
        Execute the complete trading loop.
        
        Args:
            user_id: User ID to execute trades for
            dry_run: If True, don't actually execute trades
        
        Returns:
            TradingLoopResult with details of the run
        """
        run_id = f"run_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        result = TradingLoopResult(
            success=False,
            run_id=run_id,
            started_at=datetime.utcnow(),
        )
        
        logger.info(f"Starting trading loop {run_id} for user {user_id}")
        self._status = AgentStatus.RUNNING
        
        try:
            # Initialize if needed
            if self._context_aggregator is None:
                await self.initialize()
            
            # STEP 1: Context Aggregation
            logger.info("Step 1: Aggregating context...")
            context = await self._aggregate_context(user_id)
            result.context_aggregated = True
            
            # STEP 1.5: Data Freshness Check (HALT if stale)
            if context.data_freshness.is_stale:
                stale_reasons = context.data_freshness.stale_reasons
                error_msg = f"HALT: Data is stale - {'; '.join(stale_reasons)}"
                logger.error(error_msg)
                result.errors.append(error_msg)
                result.success = False
                result.completed_at = datetime.utcnow()
                self._status = AgentStatus.ERROR
                return result
            
            # Log data freshness info
            df = context.data_freshness
            logger.info(f"Data freshness OK - Scores: {df.scores_age_hours:.1f}h, Regime: {df.regime_age_hours or 0:.1f}h")
            
            # STEP 2: Memory Retrieval
            logger.info("Step 2: Retrieving similar situations...")
            memories = await self._retrieve_memories(context)
            result.memories_retrieved = len(memories)
            
            # STEP 3: Decision Making
            logger.info("Step 3: Making decisions...")
            decisions = await self._make_decisions(context, memories)
            result.decisions_made = len(decisions)
            result.decisions = [d.to_dict() if hasattr(d, 'to_dict') else vars(d) for d in decisions]
            
            if not decisions:
                logger.info("No trading decisions made")
                result.success = True
                result.completed_at = datetime.utcnow()
                return result
            
            # STEP 4: Position Sizing
            logger.info("Step 4: Sizing positions...")
            sized_positions = await self._size_positions(decisions, context)
            result.positions_sized = len(sized_positions)
            
            # STEP 5: Risk Validation
            logger.info("Step 5: Validating risk...")
            validated_trades = await self._validate_risk(sized_positions, context)
            result.validations_passed = len(validated_trades)
            
            if not validated_trades:
                result.warnings.append("All trades blocked by risk validation")
                result.success = True
                result.completed_at = datetime.utcnow()
                return result
            
            # STEP 6: Execution
            logger.info("Step 6: Executing trades...")
            if not dry_run:
                execution_results = await self._execute_trades(
                    validated_trades,
                    user_id,
                )
                result.executions_attempted = len(execution_results)
                result.executions_succeeded = sum(
                    1 for r in execution_results if r.success
                )
                result.executions = [r.to_dict() for r in execution_results]
            else:
                result.warnings.append("Dry run - no trades executed")
            
            # STEP 7: Store Decisions
            logger.info("Step 7: Storing decisions...")
            await self._store_decisions(decisions, context, user_id)
            
            # STEP 8: Learning Update
            logger.info("Step 8: Running learning update...")
            learning_result = await run_learning_update()
            result.learning_outcomes_recorded = learning_result.get(
                "outcomes_recorded", 0
            )
            
            result.success = True
            logger.info(f"Trading loop {run_id} completed successfully")
            
        except Exception as e:
            result.errors.append(str(e))
            logger.error(f"Trading loop {run_id} failed: {e}")
            self._status = AgentStatus.ERROR
        
        finally:
            result.completed_at = datetime.utcnow()
            self._last_run = result
            self._run_history.append(result)
            
            if self._status == AgentStatus.RUNNING:
                self._status = AgentStatus.ACTIVE
        
        return result
    
    async def _aggregate_context(self, user_id: str) -> TradingContext:
        """Aggregate all trading context."""
        # TODO: Pass user_id once context supports per-user portfolios
        return await aggregate_context()
    
    async def _retrieve_memories(
        self,
        context: TradingContext,
    ) -> List[Any]:
        """Retrieve similar past situations."""
        return await self.memory.retrieve_similar(context, k=10)
    
    async def _make_decisions(
        self,
        context: TradingContext,
        memories: List[Any],
    ) -> List[Any]:  # List of TradeDecision
        """Make trading decisions using Claude."""
        result = await make_decisions(context, memories)
        
        # Extract decisions from result
        decisions = result.decisions if hasattr(result, 'decisions') else []
        
        # Filter by settings
        filtered = []
        for d in decisions:
            if d.action == "BUY" and d.score >= self._settings.min_score_for_buy:
                filtered.append(d)
            elif d.action == "SELL" and d.score <= self._settings.max_score_for_sell:
                filtered.append(d)
        
        # Limit to max trades per week
        return filtered[:self._settings.max_trades_per_week]
    
    async def _size_positions(
        self,
        decisions: List[DecisionResult],
        context: TradingContext,
    ) -> List[SizedPosition]:
        """Size positions using risk parity."""
        return await size_positions(decisions, context)
    
    async def _validate_risk(
        self,
        positions: List[SizedPosition],
        context: TradingContext,
    ) -> List[SizedPosition]:
        """Validate trades against risk limits."""
        validated = []
        
        for position in positions:
            results = await validate_trades([position], context)
            if results:
                # validate_trades returns List[Tuple[SizedPosition, RiskValidation]]
                pos, risk_validation = results[0]
                if risk_validation.passed:
                    # Use adjusted shares if reduced
                    if risk_validation.adjusted_shares != position.shares:
                        position.shares = risk_validation.adjusted_shares
                        position.dollars = position.shares * position.price
                    validated.append(position)
        
        return validated
    
    async def _execute_trades(
        self,
        positions: List[SizedPosition],
        user_id: str,
    ) -> List[ExecutionResult]:
        """Execute trades via IBKR."""
        executor_settings = ExecutorSettings(
            mode=self._settings.mode,
            stop_loss_type="trailing" if self._settings.stop_loss_enabled else "none",
            stop_loss_percent=self._settings.stop_loss_percent,
        )
        
        results = []
        for position in positions:
            result = await self.executor.execute(
                ticker=position.ticker,
                action=position.action,
                shares=position.shares,
                rationale=position.rationale,
                user_id=user_id,
                settings=executor_settings,
            )
            results.append(result)
        
        return results
    
    async def _store_decisions(
        self,
        decisions: List[DecisionResult],
        context: TradingContext,
        user_id: str,
    ):
        """Store decisions in memory for future learning and DPO training."""
        pair_logger = get_decision_pair_logger()
        
        for decision in decisions:
            # Store in memory system
            await self.memory.store_decision(decision, context, user_id)
            
            # Log for DPO training (REC-298)
            try:
                decision_context = self._build_decision_context(decision, context)
                await pair_logger.log_decision(
                    user_id=user_id,
                    context=decision_context,
                    action=decision.action,
                    shares=decision.shares if hasattr(decision, 'shares') else 0,
                    rationale=decision.rationale,
                    confidence=decision.confidence,
                )
            except Exception as e:
                logger.warning(f"Failed to log decision pair: {e}")
    
    def _build_decision_context(
        self,
        decision: DecisionResult,
        context: TradingContext,
    ) -> DecisionContext:
        """Build DecisionContext for DPO logging from TradingContext."""
        # Find the candidate info for this decision
        ticker_info = {}
        for candidate in context.buy_candidates + context.sell_candidates:
            if candidate.ticker == decision.ticker:
                ticker_info = {
                    "ticker_score": candidate.score,
                    "ticker_sector": candidate.sector,
                    "ticker_price": candidate.price,
                    "ticker_market_cap": getattr(candidate, 'market_cap', 0),
                    "ticker_sentiment": getattr(candidate, 'sentiment_score', 50),
                    "ticker_technical": getattr(candidate, 'technical_score', 50),
                    "ticker_fundamental": getattr(candidate, 'fundamental_score', 50),
                }
                break
        
        # Build top candidates list
        top_candidates = [
            {"ticker": c.ticker, "score": c.score}
            for c in context.buy_candidates[:5]
        ]
        
        return DecisionContext(
            timestamp=datetime.utcnow().isoformat(),
            regime=context.market.regime,
            vix_level=context.market.vix,
            portfolio_value=context.portfolio.total_value,
            cash_available=context.portfolio.cash,
            positions_count=context.portfolio.position_count,
            sector_exposure=context.portfolio.sector_exposure,
            ticker=decision.ticker,
            ticker_score=ticker_info.get("ticker_score", decision.score),
            ticker_sector=ticker_info.get("ticker_sector", "Unknown"),
            ticker_price=ticker_info.get("ticker_price", 0),
            ticker_market_cap=ticker_info.get("ticker_market_cap", 0),
            ticker_sentiment=ticker_info.get("ticker_sentiment", 50),
            ticker_technical=ticker_info.get("ticker_technical", 50),
            ticker_fundamental=ticker_info.get("ticker_fundamental", 50),
            top_candidates=top_candidates,
            recent_trades=[],  # TODO: Add recent trades from history
            recent_outcomes=[],  # TODO: Add recent outcomes from learning
        )
    
    def get_status(self) -> Dict[str, Any]:
        """Get current agent status."""
        return {
            "status": self._status.value,
            "settings": self._settings.to_dict(),
            "last_run": self._last_run.to_dict() if self._last_run else None,
            "total_runs": len(self._run_history),
        }
    
    def get_run_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent run history."""
        return [r.to_dict() for r in self._run_history[-limit:]]


# Module-level instance
_trading_loop: Optional[TradingLoop] = None


def get_trading_loop() -> TradingLoop:
    """Get or create the global trading loop instance."""
    global _trading_loop
    if _trading_loop is None:
        _trading_loop = TradingLoop()
    return _trading_loop


async def run_trading_loop(
    user_id: str,
    dry_run: bool = False,
) -> TradingLoopResult:
    """Convenience function to run trading loop."""
    loop = get_trading_loop()
    return await loop.run(user_id=user_id, dry_run=dry_run)
