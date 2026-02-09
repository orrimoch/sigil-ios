"""
Sigil Risk Management Module

Phase 1 (P0) MVP Features:
- Risk Settings API (user preferences)
- Hard Stop-Loss Logic
- Trailing Stop-Loss Logic
- IBKR Stop Order Integration
- High-Water-Mark Tracking
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

__all__ = [
    # Models
    "UserRiskSettings",
    "StopConfig",
    "TrailingStopConfig",
    "VixAdjustmentConfig",
    "PositionLimitConfig",
    # Functions
    "check_hard_stop",
    "check_trailing_stop",
    # Services
    "RiskSettingsService",
]
