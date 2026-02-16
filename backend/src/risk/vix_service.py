"""
VIX Data Pipeline - REC-225

Fetches daily VIX from Yahoo Finance (^VIX) using yfinance.
Caches data for 1 hour to minimize API calls.

API Endpoint: GET /api/v1/market/vix
"""

import yfinance as yf
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class VIXData:
    """VIX market data."""
    value: float                    # Current VIX value
    previous_close: float           # Previous day close
    change: float                   # Absolute change
    change_pct: float               # Percentage change
    updated_at: datetime            # When data was fetched
    regime: str                     # Market regime (low/normal/elevated/high/extreme)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "vix": self.value,
            "previous_close": self.previous_close,
            "change": self.change,
            "change_pct": self.change_pct,
            "updated_at": self.updated_at.isoformat(),
            "regime": self.regime,
        }


class VIXCache:
    """In-memory cache for VIX data with 1-hour TTL."""
    
    TTL_SECONDS = 3600  # 1 hour
    
    def __init__(self):
        self._data: Optional[VIXData] = None
        self._cached_at: Optional[datetime] = None
    
    def get(self) -> Optional[VIXData]:
        """Get cached VIX data if valid."""
        if self._data is None or self._cached_at is None:
            return None
        
        # Check if cache is still valid
        age = (datetime.now(timezone.utc) - self._cached_at).total_seconds()
        if age > self.TTL_SECONDS:
            logger.debug(f"VIX cache expired (age: {age:.0f}s)")
            return None
        
        return self._data
    
    def set(self, data: VIXData) -> None:
        """Store VIX data in cache."""
        self._data = data
        self._cached_at = datetime.now(timezone.utc)
        logger.debug(f"VIX cached: {data.value:.2f}")
    
    def clear(self) -> None:
        """Clear the cache."""
        self._data = None
        self._cached_at = None
    
    def get_cache_age_seconds(self) -> Optional[float]:
        """Get age of cached data in seconds."""
        if self._cached_at is None:
            return None
        return (datetime.now(timezone.utc) - self._cached_at).total_seconds()


# Global cache instance
_vix_cache = VIXCache()


def _classify_vix_regime(vix: float) -> str:
    """
    Classify market regime based on VIX level.
    
    Thresholds based on historical VIX distribution:
    - < 15: Low volatility
    - 15-20: Normal
    - 20-25: Elevated
    - 25-35: High
    - > 35: Extreme
    """
    if vix < 15:
        return "low"
    elif vix < 20:
        return "normal"
    elif vix < 25:
        return "elevated"
    elif vix < 35:
        return "high"
    else:
        return "extreme"


async def fetch_vix(use_cache: bool = True) -> VIXData:
    """
    Fetch current VIX value from Yahoo Finance.
    
    Args:
        use_cache: Whether to use cached data if available (default True)
        
    Returns:
        VIXData with current VIX information
        
    Raises:
        ValueError: If VIX data cannot be fetched
    """
    # Check cache first
    if use_cache:
        cached = _vix_cache.get()
        if cached is not None:
            logger.debug(f"Returning cached VIX: {cached.value:.2f}")
            return cached
    
    try:
        # Fetch VIX data from Yahoo Finance
        vix_ticker = yf.Ticker("^VIX")
        
        # Get current/latest data
        hist = vix_ticker.history(period="5d")
        
        if hist.empty:
            raise ValueError("No VIX data available from Yahoo Finance")
        
        # Get the latest close price
        current_value = float(hist['Close'].iloc[-1])
        
        # Get previous close for change calculation
        if len(hist) >= 2:
            previous_close = float(hist['Close'].iloc[-2])
        else:
            previous_close = current_value
        
        # Calculate change
        change = current_value - previous_close
        change_pct = (change / previous_close * 100) if previous_close > 0 else 0.0
        
        # Classify regime
        regime = _classify_vix_regime(current_value)
        
        # Create VIX data object
        vix_data = VIXData(
            value=round(current_value, 2),
            previous_close=round(previous_close, 2),
            change=round(change, 2),
            change_pct=round(change_pct, 2),
            updated_at=datetime.now(timezone.utc),
            regime=regime,
        )
        
        # Cache the result
        _vix_cache.set(vix_data)
        
        logger.info(f"Fetched VIX: {current_value:.2f} (regime: {regime})")
        return vix_data
        
    except Exception as e:
        logger.error(f"Failed to fetch VIX: {e}")
        
        # If we have stale cache data, return it as fallback
        if _vix_cache._data is not None:
            logger.warning("Using stale VIX cache as fallback")
            return _vix_cache._data
        
        # MEDIUM FIX RK-003: Return default VIX instead of raising (15 = historical average)
        logger.warning("No VIX data available, using default value (20)")
        return VIXData(
            value=20.0,  # Slightly above baseline as conservative default
            previous_close=20.0,
            change=0.0,
            change_pct=0.0,
            updated_at=datetime.now(timezone.utc),
            regime="normal",
        )


def get_cached_vix() -> Optional[VIXData]:
    """
    Get VIX data from cache without fetching.
    
    Returns:
        Cached VIXData or None if not cached/expired
    """
    return _vix_cache.get()


def clear_vix_cache() -> None:
    """Clear the VIX cache (for testing)."""
    _vix_cache.clear()


def get_vix_cache_stats() -> Dict[str, Any]:
    """Get cache statistics."""
    cached = _vix_cache.get()
    return {
        "has_cached_data": cached is not None,
        "cache_age_seconds": _vix_cache.get_cache_age_seconds(),
        "ttl_seconds": VIXCache.TTL_SECONDS,
        "cached_value": cached.value if cached else None,
    }


# Synchronous wrapper for non-async contexts
def fetch_vix_sync(use_cache: bool = True) -> VIXData:
    """
    Synchronous version of fetch_vix.
    
    Uses the same logic but without async/await.
    """
    import asyncio
    
    # Try to get existing event loop, create new one if needed
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # We're in an async context, can't use run_until_complete
            # Fall back to synchronous implementation
            return _fetch_vix_sync_impl(use_cache)
        return loop.run_until_complete(fetch_vix(use_cache))
    except RuntimeError:
        # No event loop, create one
        return asyncio.run(fetch_vix(use_cache))


def _fetch_vix_sync_impl(use_cache: bool = True) -> VIXData:
    """Pure synchronous implementation of VIX fetch."""
    # Check cache first
    if use_cache:
        cached = _vix_cache.get()
        if cached is not None:
            return cached
    
    try:
        vix_ticker = yf.Ticker("^VIX")
        hist = vix_ticker.history(period="5d")
        
        if hist.empty:
            raise ValueError("No VIX data available")
        
        current_value = float(hist['Close'].iloc[-1])
        previous_close = float(hist['Close'].iloc[-2]) if len(hist) >= 2 else current_value
        
        change = current_value - previous_close
        change_pct = (change / previous_close * 100) if previous_close > 0 else 0.0
        regime = _classify_vix_regime(current_value)
        
        vix_data = VIXData(
            value=round(current_value, 2),
            previous_close=round(previous_close, 2),
            change=round(change, 2),
            change_pct=round(change_pct, 2),
            updated_at=datetime.now(timezone.utc),
            regime=regime,
        )
        
        _vix_cache.set(vix_data)
        return vix_data
        
    except Exception as e:
        if _vix_cache._data is not None:
            return _vix_cache._data
        raise ValueError(f"Failed to fetch VIX: {e}")


# Convenience function for agent context aggregator (REC-278)
async def get_current_vix() -> Dict[str, Any]:
    """
    Get current VIX data for agent context.
    
    Returns dict with vix, change, regime for TradingContext.
    """
    try:
        vix_data = await fetch_vix(use_cache=True)
        return {
            "vix": vix_data.value,
            "change": vix_data.change,
            "change_pct": vix_data.change_pct,
            "regime": vix_data.regime,
        }
    except Exception as e:
        logger.warning(f"get_current_vix failed: {e}, using defaults")
        return {
            "vix": 20.0,
            "change": 0.0,
            "change_pct": 0.0,
            "regime": "normal",
        }
