"""
REC-147: Position Size Calculator

Calculate optimal position size based on:
- Account size (total portfolio value)
- Risk percentage (max % of account to risk per trade, e.g., 1%)
- Stop distance (difference between entry and stop-loss price)

Formula: Position Size = (Account * Risk%) / (Entry - Stop)
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class PositionSizeResult:
    """Result of position size calculation."""
    shares: int
    position_value: float
    risk_amount: float
    risk_percent: float
    stop_distance: float
    stop_percent: float
    
    def to_dict(self) -> dict:
        return {
            "shares": self.shares,
            "position_value": round(self.position_value, 2),
            "risk_amount": round(self.risk_amount, 2),
            "risk_percent": round(self.risk_percent, 2),
            "stop_distance": round(self.stop_distance, 2),
            "stop_percent": round(self.stop_percent, 4),
        }


def calculate_position_size(
    account_size: float,
    risk_percent: float,
    entry_price: float,
    stop_price: float,
    max_position_percent: float = 25.0,
) -> PositionSizeResult:
    """
    Calculate optimal position size based on risk parameters.
    
    Args:
        account_size: Total account/portfolio value in dollars
        risk_percent: Maximum risk per trade as percentage (e.g., 1.0 = 1%)
        entry_price: Planned entry price
        stop_price: Stop-loss price
        max_position_percent: Maximum single position as % of account (default 25%)
    
    Returns:
        PositionSizeResult with calculated shares and risk metrics
    
    Raises:
        ValueError: If inputs are invalid
    """
    # Validation
    if account_size <= 0:
        raise ValueError("Account size must be positive")
    if risk_percent <= 0 or risk_percent > 100:
        raise ValueError("Risk percent must be between 0 and 100")
    if entry_price <= 0:
        raise ValueError("Entry price must be positive")
    if stop_price <= 0:
        raise ValueError("Stop price must be positive")
    if entry_price == stop_price:
        raise ValueError("Entry and stop price cannot be equal")
    
    # Calculate stop distance (works for both long and short)
    stop_distance = abs(entry_price - stop_price)
    stop_percent = stop_distance / entry_price
    
    # Calculate maximum dollars to risk
    risk_amount = account_size * (risk_percent / 100)
    
    # Calculate shares based on risk
    shares_from_risk = risk_amount / stop_distance
    
    # Calculate maximum shares based on position size limit
    max_position_value = account_size * (max_position_percent / 100)
    shares_from_max_position = max_position_value / entry_price
    
    # Take the smaller of the two (respect both limits)
    shares = int(min(shares_from_risk, shares_from_max_position))
    
    # Ensure at least 1 share if calculation allows
    if shares < 1 and shares_from_risk >= 1:
        shares = 1
    
    # Final position metrics
    position_value = shares * entry_price
    actual_risk = shares * stop_distance
    actual_risk_percent = (actual_risk / account_size) * 100 if account_size > 0 else 0
    
    return PositionSizeResult(
        shares=shares,
        position_value=position_value,
        risk_amount=actual_risk,
        risk_percent=actual_risk_percent,
        stop_distance=stop_distance,
        stop_percent=stop_percent,
    )


def calculate_stop_from_atr(
    entry_price: float,
    atr: float,
    multiplier: float = 2.0,
    is_long: bool = True,
) -> float:
    """
    Calculate stop-loss price based on ATR (Average True Range).
    
    Common multipliers:
    - 1.5x ATR: Tight stop (more stops triggered)
    - 2.0x ATR: Standard stop
    - 3.0x ATR: Wide stop (fewer stops, larger losses)
    
    Args:
        entry_price: Entry price
        atr: Average True Range value
        multiplier: ATR multiplier (default 2.0)
        is_long: True for long position, False for short
    
    Returns:
        Stop-loss price
    """
    stop_distance = atr * multiplier
    if is_long:
        return entry_price - stop_distance
    else:
        return entry_price + stop_distance
