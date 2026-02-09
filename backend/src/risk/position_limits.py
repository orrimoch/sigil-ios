"""
Position Size Limits - REC-227

Validates trades against position size limits.
Warns if exceeding max % of portfolio (default 15%).
User can override with confirmation.

API Endpoint: POST /api/v1/trade/validate
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum
import logging

from .models import UserRiskSettings

logger = logging.getLogger(__name__)


class WarningLevel(str, Enum):
    """Warning severity levels."""
    NONE = "none"
    LOW = "low"           # Informational
    MEDIUM = "medium"     # Should pay attention
    HIGH = "high"         # Strong warning


@dataclass
class PositionWarning:
    """Warning about a position size issue."""
    type: str              # e.g., "position_limit", "concentration", "liquidity"
    level: WarningLevel
    message: str
    can_override: bool
    current_value: Optional[float] = None
    threshold_value: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "level": self.level.value,
            "message": self.message,
            "can_override": self.can_override,
            "current_value": self.current_value,
            "threshold_value": self.threshold_value,
        }


@dataclass
class TradeValidationResult:
    """Result of trade validation."""
    valid: bool
    warnings: List[PositionWarning]
    risk_metrics: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "warnings": [w.to_dict() for w in self.warnings],
            "risk_metrics": self.risk_metrics,
        }
    
    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0
    
    @property
    def has_blocking_warnings(self) -> bool:
        return any(not w.can_override for w in self.warnings)
    
    @property
    def highest_warning_level(self) -> WarningLevel:
        if not self.warnings:
            return WarningLevel.NONE
        
        level_order = [WarningLevel.NONE, WarningLevel.LOW, WarningLevel.MEDIUM, WarningLevel.HIGH]
        max_level = WarningLevel.NONE
        
        for warning in self.warnings:
            if level_order.index(warning.level) > level_order.index(max_level):
                max_level = warning.level
        
        return max_level


def calculate_position_pct(
    position_value: float,
    portfolio_value: float,
) -> float:
    """
    Calculate position as percentage of portfolio.
    
    Args:
        position_value: Dollar value of position
        portfolio_value: Total portfolio value
        
    Returns:
        Position percentage (0.0 to 1.0)
    """
    if portfolio_value <= 0:
        return 0.0
    return position_value / portfolio_value


def validate_position_size(
    ticker: str,
    trade_value: float,
    current_position_value: float,
    portfolio_value: float,
    settings: Optional[UserRiskSettings] = None,
    action: str = "BUY",
) -> TradeValidationResult:
    """
    Validate a trade against position size limits.
    
    Args:
        ticker: Stock symbol
        trade_value: Dollar value of the trade
        current_position_value: Current position value (0 if new position)
        portfolio_value: Total portfolio value including cash
        settings: User's risk settings
        action: BUY or SELL
        
    Returns:
        TradeValidationResult with warnings if applicable
    """
    warnings = []
    
    # If position limits disabled or settings not provided, skip validation
    if settings is None or not settings.position_limit.enabled:
        return TradeValidationResult(
            valid=True,
            warnings=[],
            risk_metrics={
                "validation_skipped": True,
                "reason": "Position limits not enabled",
            }
        )
    
    # For SELL actions, no position limit warnings needed
    if action.upper() == "SELL":
        return TradeValidationResult(
            valid=True,
            warnings=[],
            risk_metrics={
                "action": "SELL",
                "position_limit_check": "not_applicable",
            }
        )
    
    # Calculate post-trade position value
    new_position_value = current_position_value + trade_value
    
    # Calculate percentages
    current_pct = calculate_position_pct(current_position_value, portfolio_value)
    new_pct = calculate_position_pct(new_position_value, portfolio_value)
    max_pct = settings.position_limit.max_pct
    
    # Check against limit
    if new_pct > max_pct:
        # Calculate how much exceeds the limit
        excess_pct = new_pct - max_pct
        
        if excess_pct > 0.10:  # More than 10% over limit
            level = WarningLevel.HIGH
        elif excess_pct > 0.05:  # 5-10% over limit
            level = WarningLevel.MEDIUM
        else:
            level = WarningLevel.LOW
        
        warnings.append(PositionWarning(
            type="position_limit",
            level=level,
            message=f"This trade would make {ticker} {new_pct*100:.1f}% of your portfolio (limit: {max_pct*100:.0f}%)",
            can_override=True,
            current_value=new_pct,
            threshold_value=max_pct,
        ))
    
    # Additional warning if this would be the largest position
    if new_pct > 0.20:  # More than 20% of portfolio
        warnings.append(PositionWarning(
            type="concentration",
            level=WarningLevel.MEDIUM,
            message=f"{ticker} would be over 20% of your portfolio. Consider diversifying.",
            can_override=True,
            current_value=new_pct,
            threshold_value=0.20,
        ))
    
    # Prepare risk metrics
    risk_metrics = {
        "ticker": ticker,
        "action": action,
        "trade_value": trade_value,
        "current_position_value": current_position_value,
        "post_trade_position_value": new_position_value,
        "portfolio_value": portfolio_value,
        "current_position_pct": round(current_pct, 4),
        "post_trade_position_pct": round(new_pct, 4),
        "max_position_pct": max_pct,
        "exceeds_limit": new_pct > max_pct,
    }
    
    return TradeValidationResult(
        valid=True,  # Position limits don't block trades, just warn
        warnings=warnings,
        risk_metrics=risk_metrics,
    )


def validate_trade(
    ticker: str,
    action: str,
    quantity: float,
    price: float,
    portfolio: Dict[str, Any],
    settings: Optional[UserRiskSettings] = None,
) -> TradeValidationResult:
    """
    Full trade validation including position limits.
    
    Args:
        ticker: Stock symbol
        action: BUY or SELL
        quantity: Number of shares
        price: Price per share
        portfolio: Portfolio data with positions and total value
        settings: User's risk settings
        
    Returns:
        TradeValidationResult
    """
    trade_value = quantity * price
    
    # Find current position for this ticker
    positions = portfolio.get("positions", [])
    current_position = next(
        (p for p in positions if p.get("ticker") == ticker),
        None
    )
    
    current_position_value = 0.0
    if current_position:
        current_position_value = current_position.get("market_value", 0.0)
    
    portfolio_value = portfolio.get("total_value", 0.0)
    
    # Run position size validation
    result = validate_position_size(
        ticker=ticker,
        trade_value=trade_value,
        current_position_value=current_position_value,
        portfolio_value=portfolio_value,
        settings=settings,
        action=action,
    )
    
    # Add trade details to risk metrics
    result.risk_metrics["quantity"] = quantity
    result.risk_metrics["price"] = price
    
    return result


def get_position_limit_summary(
    portfolio: Dict[str, Any],
    settings: Optional[UserRiskSettings] = None,
) -> Dict[str, Any]:
    """
    Get summary of position sizes vs limits.
    
    Args:
        portfolio: Portfolio data with positions
        settings: User's risk settings
        
    Returns:
        Summary dict with position info
    """
    if settings is None or not settings.position_limit.enabled:
        return {
            "enabled": False,
            "max_pct": None,
            "positions": [],
        }
    
    max_pct = settings.position_limit.max_pct
    portfolio_value = portfolio.get("total_value", 0.0)
    positions = portfolio.get("positions", [])
    
    position_summary = []
    for pos in positions:
        ticker = pos.get("ticker", "")
        market_value = pos.get("market_value", 0.0)
        pct = calculate_position_pct(market_value, portfolio_value)
        
        position_summary.append({
            "ticker": ticker,
            "market_value": market_value,
            "pct": round(pct, 4),
            "exceeds_limit": pct > max_pct,
            "distance_to_limit": round(max_pct - pct, 4),
        })
    
    # Sort by percentage descending
    position_summary.sort(key=lambda x: x["pct"], reverse=True)
    
    return {
        "enabled": True,
        "max_pct": max_pct,
        "portfolio_value": portfolio_value,
        "positions": position_summary,
        "positions_over_limit": sum(1 for p in position_summary if p["exceeds_limit"]),
    }


def calculate_max_trade_size(
    ticker: str,
    current_position_value: float,
    portfolio_value: float,
    settings: Optional[UserRiskSettings] = None,
) -> Dict[str, Any]:
    """
    Calculate maximum trade size without exceeding position limit.
    
    Args:
        ticker: Stock symbol
        current_position_value: Current position value
        portfolio_value: Total portfolio value
        settings: User's risk settings
        
    Returns:
        Dict with max trade info
    """
    if settings is None or not settings.position_limit.enabled:
        return {
            "ticker": ticker,
            "max_trade_value": None,
            "reason": "Position limits not enabled",
        }
    
    max_pct = settings.position_limit.max_pct
    max_position_value = portfolio_value * max_pct
    available_for_trade = max_position_value - current_position_value
    
    return {
        "ticker": ticker,
        "current_position_value": current_position_value,
        "current_position_pct": calculate_position_pct(current_position_value, portfolio_value),
        "max_position_pct": max_pct,
        "max_position_value": max_position_value,
        "max_trade_value": max(0, available_for_trade),
        "at_limit": current_position_value >= max_position_value,
    }
