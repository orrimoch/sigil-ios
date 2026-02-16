"""
Sigil Trading Agent Module

Autonomous trading agent that uses Sigil's signals to make trading decisions.

Components:
- context.py: Context aggregator (REC-278)
- routes.py: API endpoints (REC-279)
- memory.py: Memory system (Phase 1)
- position_sizing.py: Risk parity optimizer (Phase 1)
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

__all__ = [
    "ContextAggregator",
    "TradingContext",
    "PortfolioState",
    "MarketState",
    "StockCandidate",
    "Position",
    "DataFreshness",
    "aggregate_context",
]
