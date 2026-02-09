"""
Sigil Risk Management Module

Phase 1 (P0) MVP Features:
- Risk Settings API (user preferences)
- Hard Stop-Loss Logic
- Trailing Stop-Loss Logic
- IBKR Stop Order Integration
- High-Water-Mark Tracking

Phase 2 (P1) Enhanced Protection:
- VIX Data Pipeline (REC-225)
- VIX Dynamic Thresholds (REC-226)
- Position Size Limits (REC-227)
- Per-Position VaR Calculator (REC-228)
- Risk Push Notifications (REC-229)
- Claude Risk Analyzer (REC-232)
"""

from .models import (
    UserRiskSettings,
    StopConfig,
    TrailingStopConfig,
    VixAdjustmentConfig,
    PositionLimitConfig,
)
from .stop_loss import check_hard_stop, check_trailing_stop
from .service import RiskSettingsService

# Phase 2 imports
from .vix_service import (
    VIXData,
    fetch_vix,
    fetch_vix_sync,
    get_cached_vix,
    clear_vix_cache,
    get_vix_cache_stats,
)
from .dynamic_thresholds import (
    AdjustedThresholds,
    calculate_vix_adjustment,
    calculate_adjusted_sell_threshold,
    calculate_adjusted_buy_threshold,
    get_adjusted_thresholds,
    should_trigger_sell,
    should_trigger_buy,
)
from .position_limits import (
    WarningLevel,
    PositionWarning,
    TradeValidationResult,
    validate_position_size,
    validate_trade,
    get_position_limit_summary,
    calculate_max_trade_size,
)
from .var_calculator import (
    VaRResult,
    PortfolioVaRResult,
    calculate_position_var,
    calculate_portfolio_var,
    classify_risk_score,
    add_var_to_positions,
)
from .claude_analyzer import (
    RiskLevel,
    RiskAnalysisResult,
    ClaudeRiskAnalyzer,
    analyze_risk_sync,
    get_risk_cache_stats,
    clear_risk_cache,
)

__all__ = [
    # Models
    "UserRiskSettings",
    "StopConfig",
    "TrailingStopConfig",
    "VixAdjustmentConfig",
    "PositionLimitConfig",
    # Phase 1 Functions
    "check_hard_stop",
    "check_trailing_stop",
    # Services
    "RiskSettingsService",
    # Phase 2 - VIX
    "VIXData",
    "fetch_vix",
    "fetch_vix_sync",
    "get_cached_vix",
    "clear_vix_cache",
    "get_vix_cache_stats",
    # Phase 2 - Dynamic Thresholds
    "AdjustedThresholds",
    "calculate_vix_adjustment",
    "calculate_adjusted_sell_threshold",
    "calculate_adjusted_buy_threshold",
    "get_adjusted_thresholds",
    "should_trigger_sell",
    "should_trigger_buy",
    # Phase 2 - Position Limits
    "WarningLevel",
    "PositionWarning",
    "TradeValidationResult",
    "validate_position_size",
    "validate_trade",
    "get_position_limit_summary",
    "calculate_max_trade_size",
    # Phase 2 - VaR
    "VaRResult",
    "PortfolioVaRResult",
    "calculate_position_var",
    "calculate_portfolio_var",
    "classify_risk_score",
    "add_var_to_positions",
    # Phase 2 - Claude Analyzer
    "RiskLevel",
    "RiskAnalysisResult",
    "ClaudeRiskAnalyzer",
    "analyze_risk_sync",
    "get_risk_cache_stats",
    "clear_risk_cache",
]
