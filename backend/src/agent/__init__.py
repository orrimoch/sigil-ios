"""
Sigil Trading Agent Module

Autonomous trading agent that uses Sigil's signals to make trading decisions.

Components:
- context.py: Context aggregator (REC-278)
- routes.py: Context API endpoints (REC-279)
- memory.py: Memory system (REC-281, REC-282)
- position_sizing.py: Risk parity optimizer (REC-283)
- decision_engine.py: Claude integration (REC-285)
- risk_validator.py: Risk checks (REC-286)
- executor.py: Trade execution (REC-288)
- learning.py: Outcome tracking (REC-289)
- trading_loop.py: Main orchestrator (REC-290)
- routes_agent.py: Agent API endpoints (REC-291)
"""

from .context import (
    ContextAggregator,
    TradingContext,
    PortfolioState,
    MarketState,
    StockCandidate,
    Position,
    DataFreshness,
    aggregate_context,
)

from .memory import (
    AgentMemory,
    Decision,
    Memory,
    get_agent_memory,
)

from .position_sizing import (
    PositionSizer,
    SizedPosition,
    TradeDecision,
    size_positions,
)

from .decision_engine import (
    DecisionEngine,
    DecisionResult,
    make_decisions,
)

from .risk_validator import (
    RiskValidator,
    RiskValidation,
    validate_trades,
)

from .executor import (
    TradeExecutor,
    ExecutorSettings,
    ExecutionMode,
    ExecutionResult,
    PendingTrade,
    get_executor,
    execute_trade,
)

from .learning import (
    LearningLoop,
    OutcomeTag,
    TradeOutcome,
    LessonLearned,
    get_learning_loop,
    run_learning_update,
)

from .trading_loop import (
    TradingLoop,
    TradingLoopResult,
    AgentSettings,
    AgentStatus,
    get_trading_loop,
    run_trading_loop,
)

__all__ = [
    # Context
    "ContextAggregator",
    "TradingContext",
    "PortfolioState",
    "MarketState",
    "StockCandidate",
    "Position",
    "DataFreshness",
    "aggregate_context",
    # Memory
    "AgentMemory",
    "Decision",
    "Memory",
    "get_agent_memory",
    # Position Sizing
    "PositionSizer",
    "SizedPosition",
    "TradeDecision",
    "size_positions",
    # Decision Engine
    "DecisionEngine",
    "DecisionResult",
    "make_decisions",
    # Risk Validator
    "RiskValidator",
    "RiskValidation",
    "validate_trades",
    # Executor (Phase 3)
    "TradeExecutor",
    "ExecutorSettings",
    "ExecutionMode",
    "ExecutionResult",
    "PendingTrade",
    "get_executor",
    "execute_trade",
    # Learning (Phase 3)
    "LearningLoop",
    "OutcomeTag",
    "TradeOutcome",
    "LessonLearned",
    "get_learning_loop",
    "run_learning_update",
    # Trading Loop (Phase 3)
    "TradingLoop",
    "TradingLoopResult",
    "AgentSettings",
    "AgentStatus",
    "get_trading_loop",
    "run_trading_loop",
]
