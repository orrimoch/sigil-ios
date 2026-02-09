"""
VIX Dynamic Thresholds - REC-226

Adjusts SELL threshold based on VIX level.
Only applies if user enabled VIX adjustment in settings.

MVP Formula: 50 + max(0, (VIX - 15) * 0.5)
- VIX 15 = baseline (no adjustment) → threshold = 50
- VIX 20 → threshold = 52.5
- VIX 25 → threshold = 55.0
- VIX 30 → threshold = 57.5
- VIX 40 → threshold = 62.5
"""

from typing import Optional, Dict, Any
from dataclasses import dataclass
import logging

from .models import UserRiskSettings
from .vix_service import VIXData, fetch_vix_sync, get_cached_vix

logger = logging.getLogger(__name__)


# Default scoring thresholds (from PRD)
DEFAULT_BUY_THRESHOLD = 70
DEFAULT_SELL_THRESHOLD = 50
DEFAULT_HOLD_MIN = 40

# VIX baseline and adjustment factor
VIX_BASELINE = 15.0
VIX_ADJUSTMENT_FACTOR = 0.5  # Points per VIX above baseline


@dataclass
class AdjustedThresholds:
    """Scoring thresholds after VIX adjustment."""
    buy_threshold: float
    sell_threshold: float
    hold_min: float
    vix_value: Optional[float]
    vix_regime: Optional[str]
    adjustment_applied: bool
    adjustment_reason: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "buy_threshold": self.buy_threshold,
            "sell_threshold": self.sell_threshold,
            "hold_min": self.hold_min,
            "vix_value": self.vix_value,
            "vix_regime": self.vix_regime,
            "adjustment_applied": self.adjustment_applied,
            "adjustment_reason": self.adjustment_reason,
        }


def calculate_vix_adjustment(vix: float) -> float:
    """
    Calculate threshold adjustment based on VIX level.
    
    MVP Formula: max(0, (VIX - 15) * 0.5)
    
    Args:
        vix: Current VIX value
        
    Returns:
        Adjustment to add to thresholds (0 or positive)
    """
    if vix <= VIX_BASELINE:
        return 0.0
    
    adjustment = (vix - VIX_BASELINE) * VIX_ADJUSTMENT_FACTOR
    return round(adjustment, 2)


def calculate_adjusted_sell_threshold(
    base_threshold: float,
    vix: float,
    settings: Optional[UserRiskSettings] = None,
) -> float:
    """
    Calculate VIX-adjusted SELL threshold.
    
    PM Formula (MVP): base + max(0, (VIX - 15) × 0.5)
    
    Args:
        base_threshold: Base SELL threshold (default 50)
        vix: Current VIX value
        settings: User's risk settings (to check if VIX adjustment enabled)
        
    Returns:
        Adjusted threshold (or base if VIX adjustment disabled)
    """
    # Check if VIX adjustment is enabled in user settings
    if settings is not None and not settings.vix_adjustment.enabled:
        return base_threshold
    
    # Calculate adjustment
    adjustment = calculate_vix_adjustment(vix)
    adjusted = base_threshold + adjustment
    
    logger.debug(f"VIX adjustment: {vix:.2f} → +{adjustment:.2f} → threshold {adjusted:.2f}")
    return adjusted


def calculate_adjusted_buy_threshold(
    base_threshold: float,
    vix: float,
    settings: Optional[UserRiskSettings] = None,
) -> float:
    """
    Calculate VIX-adjusted BUY threshold.
    
    During high volatility, we raise the BUY threshold to be more selective.
    Uses same formula but with 0.3x multiplier (less aggressive than SELL).
    
    Args:
        base_threshold: Base BUY threshold (default 70)
        vix: Current VIX value
        settings: User's risk settings (to check if VIX adjustment enabled)
        
    Returns:
        Adjusted threshold (or base if VIX adjustment disabled)
    """
    if settings is not None and not settings.vix_adjustment.enabled:
        return base_threshold
    
    if vix <= VIX_BASELINE:
        return base_threshold
    
    # More conservative BUY threshold in high volatility
    adjustment = (vix - VIX_BASELINE) * 0.3  # Smaller multiplier for BUY
    adjusted = min(base_threshold + adjustment, 85)  # Cap at 85
    
    return round(adjusted, 2)


def get_adjusted_thresholds(
    settings: Optional[UserRiskSettings] = None,
    vix_data: Optional[VIXData] = None,
    fetch_vix_if_needed: bool = True,
) -> AdjustedThresholds:
    """
    Get all scoring thresholds adjusted for current VIX level.
    
    Args:
        settings: User's risk settings
        vix_data: Pre-fetched VIX data (optional)
        fetch_vix_if_needed: Whether to fetch VIX if not provided
        
    Returns:
        AdjustedThresholds with current values
    """
    # Check if VIX adjustment is enabled
    vix_enabled = settings is None or settings.vix_adjustment.enabled
    
    if not vix_enabled:
        return AdjustedThresholds(
            buy_threshold=DEFAULT_BUY_THRESHOLD,
            sell_threshold=DEFAULT_SELL_THRESHOLD,
            hold_min=DEFAULT_HOLD_MIN,
            vix_value=None,
            vix_regime=None,
            adjustment_applied=False,
            adjustment_reason="VIX adjustment disabled in settings",
        )
    
    # Get VIX data
    if vix_data is None:
        if fetch_vix_if_needed:
            try:
                vix_data = fetch_vix_sync(use_cache=True)
            except Exception as e:
                logger.warning(f"Failed to fetch VIX for threshold adjustment: {e}")
                return AdjustedThresholds(
                    buy_threshold=DEFAULT_BUY_THRESHOLD,
                    sell_threshold=DEFAULT_SELL_THRESHOLD,
                    hold_min=DEFAULT_HOLD_MIN,
                    vix_value=None,
                    vix_regime=None,
                    adjustment_applied=False,
                    adjustment_reason=f"VIX unavailable: {e}",
                )
        else:
            # Try cache only
            vix_data = get_cached_vix()
            if vix_data is None:
                return AdjustedThresholds(
                    buy_threshold=DEFAULT_BUY_THRESHOLD,
                    sell_threshold=DEFAULT_SELL_THRESHOLD,
                    hold_min=DEFAULT_HOLD_MIN,
                    vix_value=None,
                    vix_regime=None,
                    adjustment_applied=False,
                    adjustment_reason="VIX not cached and fetch disabled",
                )
    
    # Calculate adjusted thresholds
    vix = vix_data.value
    adjustment = calculate_vix_adjustment(vix)
    
    buy_threshold = calculate_adjusted_buy_threshold(DEFAULT_BUY_THRESHOLD, vix, settings)
    sell_threshold = calculate_adjusted_sell_threshold(DEFAULT_SELL_THRESHOLD, vix, settings)
    
    # HOLD minimum threshold also adjusts slightly
    hold_min = DEFAULT_HOLD_MIN + (adjustment * 0.5)
    
    # Determine adjustment reason
    if adjustment > 0:
        reason = f"VIX at {vix:.2f} (above baseline {VIX_BASELINE}): +{adjustment:.2f} to thresholds"
    else:
        reason = f"VIX at {vix:.2f} (at or below baseline {VIX_BASELINE}): no adjustment"
    
    return AdjustedThresholds(
        buy_threshold=buy_threshold,
        sell_threshold=sell_threshold,
        hold_min=hold_min,
        vix_value=vix,
        vix_regime=vix_data.regime,
        adjustment_applied=adjustment > 0,
        adjustment_reason=reason,
    )


def should_trigger_sell(
    score: float,
    settings: Optional[UserRiskSettings] = None,
    vix: Optional[float] = None,
) -> tuple[bool, str]:
    """
    Check if a score should trigger a SELL signal.
    
    Args:
        score: Current composite score (0-100)
        settings: User's risk settings
        vix: Current VIX value (fetched if not provided)
        
    Returns:
        Tuple of (should_sell: bool, reason: str)
    """
    # Get VIX if not provided
    if vix is None:
        try:
            vix_data = fetch_vix_sync(use_cache=True)
            vix = vix_data.value
        except Exception:
            vix = VIX_BASELINE  # Use baseline if unavailable
    
    # Calculate adjusted threshold
    threshold = calculate_adjusted_sell_threshold(DEFAULT_SELL_THRESHOLD, vix, settings)
    
    if score < threshold:
        return True, f"Score {score:.1f} below SELL threshold {threshold:.1f} (VIX: {vix:.1f})"
    
    return False, f"Score {score:.1f} above SELL threshold {threshold:.1f}"


def should_trigger_buy(
    score: float,
    settings: Optional[UserRiskSettings] = None,
    vix: Optional[float] = None,
) -> tuple[bool, str]:
    """
    Check if a score should trigger a BUY signal.
    
    Args:
        score: Current composite score (0-100)
        settings: User's risk settings
        vix: Current VIX value (fetched if not provided)
        
    Returns:
        Tuple of (should_buy: bool, reason: str)
    """
    if vix is None:
        try:
            vix_data = fetch_vix_sync(use_cache=True)
            vix = vix_data.value
        except Exception:
            vix = VIX_BASELINE
    
    threshold = calculate_adjusted_buy_threshold(DEFAULT_BUY_THRESHOLD, vix, settings)
    
    if score >= threshold:
        return True, f"Score {score:.1f} meets BUY threshold {threshold:.1f} (VIX: {vix:.1f})"
    
    return False, f"Score {score:.1f} below BUY threshold {threshold:.1f}"


# VIX threshold lookup table for reference
VIX_THRESHOLD_TABLE = {
    10: {"sell": 50.0, "buy": 70.0},
    12: {"sell": 50.0, "buy": 70.0},
    15: {"sell": 50.0, "buy": 70.0},  # Baseline
    18: {"sell": 51.5, "buy": 70.9},
    20: {"sell": 52.5, "buy": 71.5},
    22: {"sell": 53.5, "buy": 72.1},
    25: {"sell": 55.0, "buy": 73.0},
    28: {"sell": 56.5, "buy": 73.9},
    30: {"sell": 57.5, "buy": 74.5},
    35: {"sell": 60.0, "buy": 76.0},
    40: {"sell": 62.5, "buy": 77.5},
    50: {"sell": 67.5, "buy": 80.5},
}


def get_threshold_table() -> Dict[int, Dict[str, float]]:
    """Get the VIX threshold lookup table for documentation."""
    return VIX_THRESHOLD_TABLE
