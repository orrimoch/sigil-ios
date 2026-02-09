"""
Stop-Loss Logic

REC-217: Hard Stop-Loss Logic
REC-218: Trailing Stop-Loss Logic

Pure functions for calculating stop-loss triggers.
"""

from typing import Tuple, Optional
from dataclasses import dataclass


@dataclass
class StopCheckResult:
    """Result of a stop-loss check."""
    triggered: bool
    stop_type: str  # "hard" or "trailing"
    trigger_price: float
    current_loss_pct: float
    reason: Optional[str] = None


def check_hard_stop(
    entry_price: float,
    current_price: float,
    threshold_pct: float = -0.08,
) -> bool:
    """
    Check if hard stop-loss is triggered.
    
    REC-217: Hard Stop-Loss Logic
    Default -8%, range -5% to -20%
    
    Args:
        entry_price: Price at which position was opened
        current_price: Current market price
        threshold_pct: Stop-loss threshold as negative percentage (e.g., -0.08 for -8%)
        
    Returns:
        True if stop-loss triggered, False otherwise
        
    Examples:
        >>> check_hard_stop(100.0, 92.0, -0.08)  # Down 8%
        True
        >>> check_hard_stop(100.0, 93.0, -0.08)  # Down 7%
        False
        >>> check_hard_stop(100.0, 91.0, -0.08)  # Down 9%
        True
    """
    if entry_price <= 0:
        raise ValueError("Entry price must be positive")
    if current_price < 0:
        raise ValueError("Current price cannot be negative")
    
    # Ensure threshold is negative (loss)
    if threshold_pct > 0:
        threshold_pct = -threshold_pct
    
    # Calculate current P&L percentage
    pnl_pct = (current_price - entry_price) / entry_price
    
    # Trigger if loss exceeds threshold (more negative than threshold)
    return pnl_pct <= threshold_pct


def check_trailing_stop(
    current_price: float,
    high_water_mark: float,
    distance_pct: float = -0.10,
) -> bool:
    """
    Check if trailing stop-loss is triggered.
    
    REC-218: Trailing Stop-Loss Logic
    Default -10%, range -5% to -25%
    
    The trailing stop follows the price up but never moves down.
    It triggers when price drops distance_pct below the high-water-mark.
    
    Args:
        current_price: Current market price
        high_water_mark: Highest price reached since position opened
        distance_pct: Trailing distance as negative percentage (e.g., -0.10 for -10%)
        
    Returns:
        True if trailing stop triggered, False otherwise
        
    Examples:
        >>> check_trailing_stop(90.0, 100.0, -0.10)  # Down 10% from peak
        True
        >>> check_trailing_stop(91.0, 100.0, -0.10)  # Down 9% from peak
        False
        >>> check_trailing_stop(89.0, 100.0, -0.10)  # Down 11% from peak
        True
    """
    if high_water_mark <= 0:
        raise ValueError("High-water-mark must be positive")
    if current_price < 0:
        raise ValueError("Current price cannot be negative")
    
    # Ensure distance is negative (loss from peak)
    if distance_pct > 0:
        distance_pct = -distance_pct
    
    # Calculate drawdown from peak
    drawdown = (current_price - high_water_mark) / high_water_mark
    
    # Trigger if drawdown exceeds distance (more negative than distance)
    return drawdown <= distance_pct


def calculate_stop_price(
    entry_price: float,
    threshold_pct: float = -0.08,
) -> float:
    """
    Calculate the hard stop trigger price.
    
    Args:
        entry_price: Price at which position was opened
        threshold_pct: Stop-loss threshold as negative percentage
        
    Returns:
        Price at which stop would trigger
        
    Examples:
        >>> calculate_stop_price(100.0, -0.08)
        92.0
        >>> calculate_stop_price(200.0, -0.10)
        180.0
    """
    if entry_price <= 0:
        raise ValueError("Entry price must be positive")
    
    if threshold_pct > 0:
        threshold_pct = -threshold_pct
        
    return entry_price * (1 + threshold_pct)


def calculate_trailing_stop_price(
    high_water_mark: float,
    distance_pct: float = -0.10,
) -> float:
    """
    Calculate the trailing stop trigger price.
    
    Args:
        high_water_mark: Highest price reached since position opened
        distance_pct: Trailing distance as negative percentage
        
    Returns:
        Price at which trailing stop would trigger
        
    Examples:
        >>> calculate_trailing_stop_price(100.0, -0.10)
        90.0
        >>> calculate_trailing_stop_price(150.0, -0.15)
        127.5
    """
    if high_water_mark <= 0:
        raise ValueError("High-water-mark must be positive")
    
    if distance_pct > 0:
        distance_pct = -distance_pct
        
    return high_water_mark * (1 + distance_pct)


def check_stop_with_details(
    entry_price: float,
    current_price: float,
    high_water_mark: float,
    hard_stop_pct: Optional[float] = None,
    trailing_stop_pct: Optional[float] = None,
) -> Optional[StopCheckResult]:
    """
    Check both hard and trailing stops, returning details if triggered.
    
    Args:
        entry_price: Price at which position was opened
        current_price: Current market price
        high_water_mark: Highest price reached since position opened
        hard_stop_pct: Hard stop threshold (None = disabled)
        trailing_stop_pct: Trailing stop distance (None = disabled)
        
    Returns:
        StopCheckResult if any stop triggered, None otherwise
    """
    # Check hard stop first (takes priority)
    if hard_stop_pct is not None:
        if check_hard_stop(entry_price, current_price, hard_stop_pct):
            pnl_pct = (current_price - entry_price) / entry_price
            trigger_price = calculate_stop_price(entry_price, hard_stop_pct)
            return StopCheckResult(
                triggered=True,
                stop_type="hard",
                trigger_price=trigger_price,
                current_loss_pct=pnl_pct,
                reason=f"Hard stop-loss triggered at {pnl_pct*100:.1f}% loss (threshold: {hard_stop_pct*100:.1f}%)",
            )
    
    # Check trailing stop
    if trailing_stop_pct is not None:
        if check_trailing_stop(current_price, high_water_mark, trailing_stop_pct):
            drawdown = (current_price - high_water_mark) / high_water_mark
            trigger_price = calculate_trailing_stop_price(high_water_mark, trailing_stop_pct)
            return StopCheckResult(
                triggered=True,
                stop_type="trailing",
                trigger_price=trigger_price,
                current_loss_pct=drawdown,
                reason=f"Trailing stop triggered at {drawdown*100:.1f}% from peak (distance: {trailing_stop_pct*100:.1f}%)",
            )
    
    return None


def update_high_water_mark(
    current_price: float,
    current_hwm: Optional[float] = None,
) -> float:
    """
    Update high-water-mark if current price is higher.
    
    REC-220: High-Water-Mark Tracking
    
    Args:
        current_price: Current market price
        current_hwm: Current high-water-mark (None for new positions)
        
    Returns:
        Updated high-water-mark (max of current and previous)
    """
    if current_price < 0:
        raise ValueError("Current price cannot be negative")
    
    if current_hwm is None:
        return current_price
    
    return max(current_price, current_hwm)
