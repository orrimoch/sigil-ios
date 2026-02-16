"""
Sigil Trading Agent Module

Autonomous trading agent that uses Sigil's signals to make trading decisions.

Components:
- context.py: Context aggregator (REC-278)
- routes.py: API endpoints (REC-279)
- memory.py: Memory system (REC-281, REC-282)
- position_sizing.py: Risk parity optimizer (REC-283)
- decision_engine.py: Claude integration (Phase 2)
- risk_validator.py: Risk checks (Phase 2)
- executor.py: Trade execution (Phase 3)
- learning.py: Outcome tracking (Phase 3)
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
]
