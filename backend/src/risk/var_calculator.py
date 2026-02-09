"""
Per-Position VaR Calculator - REC-228

Calculates 95% daily Value at Risk (VaR) for each position.
Uses parametric VaR: position_value * volatility * 1.645

VaR represents the maximum expected loss with 95% confidence over 1 day.

Formula: VaR = Position Value × Daily Volatility × Z-score
- Z-score for 95% confidence = 1.645
- Daily volatility = annualized volatility / sqrt(252)
"""

import numpy as np
from scipy import stats
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

import yfinance as yf

logger = logging.getLogger(__name__)

# VaR confidence levels
Z_SCORE_95 = 1.645  # 95% confidence
Z_SCORE_99 = 2.326  # 99% confidence
TRADING_DAYS_PER_YEAR = 252
DEFAULT_LOOKBACK_DAYS = 252  # 1 year of trading data


@dataclass
class VaRResult:
    """Value at Risk calculation result for a single position."""
    ticker: str
    position_value: float
    var_95_daily: float           # 95% VaR in dollars
    var_99_daily: float           # 99% VaR in dollars
    var_95_pct: float             # 95% VaR as percentage
    var_99_pct: float             # 99% VaR as percentage
    daily_volatility: float       # Daily volatility (decimal)
    annualized_volatility: float  # Annualized volatility (decimal)
    calculated_at: datetime
    method: str = "parametric"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "position_value": round(self.position_value, 2),
            "var_95_daily": round(self.var_95_daily, 2),
            "var_99_daily": round(self.var_99_daily, 2),
            "var_95_pct": round(self.var_95_pct, 4),
            "var_99_pct": round(self.var_99_pct, 4),
            "daily_volatility": round(self.daily_volatility, 6),
            "annualized_volatility": round(self.annualized_volatility, 4),
            "calculated_at": self.calculated_at.isoformat(),
            "method": self.method,
        }


@dataclass
class PortfolioVaRResult:
    """VaR result for entire portfolio."""
    total_value: float
    var_95_daily: float
    var_99_daily: float
    var_95_pct: float
    var_99_pct: float
    risk_score: str              # "low", "medium", "high"
    position_vars: List[VaRResult]
    correlation_benefit: float   # Reduction from diversification
    calculated_at: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_value": round(self.total_value, 2),
            "var_95_daily": round(self.var_95_daily, 2),
            "var_99_daily": round(self.var_99_daily, 2),
            "var_95_pct": round(self.var_95_pct, 4),
            "var_99_pct": round(self.var_99_pct, 4),
            "risk_score": self.risk_score,
            "position_vars": [p.to_dict() for p in self.position_vars],
            "correlation_benefit": round(self.correlation_benefit, 4),
            "calculated_at": self.calculated_at.isoformat(),
        }


def fetch_historical_returns(
    ticker: str,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> Optional[np.ndarray]:
    """
    Fetch historical daily returns for a ticker.
    
    Args:
        ticker: Stock symbol
        lookback_days: Number of trading days to fetch
        
    Returns:
        Array of daily returns (log returns) or None if failed
    """
    try:
        # Add buffer days to account for weekends/holidays
        calendar_days = int(lookback_days * 1.5)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=calendar_days)
        
        stock = yf.Ticker(ticker)
        hist = stock.history(start=start_date, end=end_date)
        
        if hist.empty or len(hist) < 30:
            logger.warning(f"Insufficient data for {ticker}: {len(hist)} days")
            return None
        
        # Calculate log returns
        prices = hist['Close'].values
        returns = np.diff(np.log(prices))
        
        # Use the most recent lookback_days of data
        if len(returns) > lookback_days:
            returns = returns[-lookback_days:]
        
        return returns
        
    except Exception as e:
        logger.error(f"Failed to fetch returns for {ticker}: {e}")
        return None


def calculate_volatility(returns: np.ndarray) -> Tuple[float, float]:
    """
    Calculate daily and annualized volatility from returns.
    
    Args:
        returns: Array of daily returns
        
    Returns:
        Tuple of (daily_volatility, annualized_volatility)
    """
    daily_vol = np.std(returns)
    annual_vol = daily_vol * np.sqrt(TRADING_DAYS_PER_YEAR)
    return daily_vol, annual_vol


def calculate_parametric_var(
    position_value: float,
    daily_volatility: float,
    confidence: float = 0.95,
) -> float:
    """
    Calculate parametric VaR assuming normal distribution.
    
    Formula: VaR = Position Value × Daily Volatility × Z-score
    
    Args:
        position_value: Dollar value of position
        daily_volatility: Daily volatility (as decimal)
        confidence: Confidence level (0.95 or 0.99)
        
    Returns:
        VaR in dollars (positive number representing potential loss)
    """
    if confidence == 0.95:
        z_score = Z_SCORE_95
    elif confidence == 0.99:
        z_score = Z_SCORE_99
    else:
        z_score = stats.norm.ppf(confidence)
    
    var = position_value * daily_volatility * z_score
    return abs(var)  # VaR is always positive (it's a loss amount)


def calculate_position_var(
    ticker: str,
    position_value: float,
    returns: Optional[np.ndarray] = None,
) -> VaRResult:
    """
    Calculate VaR for a single position.
    
    Args:
        ticker: Stock symbol
        position_value: Dollar value of position
        returns: Pre-fetched returns (optional, will fetch if not provided)
        
    Returns:
        VaRResult with calculated values
    """
    # Fetch returns if not provided
    if returns is None:
        returns = fetch_historical_returns(ticker)
    
    # If we still don't have returns, use market average volatility
    if returns is None or len(returns) < 30:
        logger.warning(f"Using default volatility for {ticker}")
        daily_vol = 0.02  # ~2% daily vol as fallback (about 32% annual)
        annual_vol = daily_vol * np.sqrt(TRADING_DAYS_PER_YEAR)
    else:
        daily_vol, annual_vol = calculate_volatility(returns)
    
    # Calculate VaR at both confidence levels
    var_95 = calculate_parametric_var(position_value, daily_vol, 0.95)
    var_99 = calculate_parametric_var(position_value, daily_vol, 0.99)
    
    return VaRResult(
        ticker=ticker,
        position_value=position_value,
        var_95_daily=var_95,
        var_99_daily=var_99,
        var_95_pct=var_95 / position_value if position_value > 0 else 0,
        var_99_pct=var_99 / position_value if position_value > 0 else 0,
        daily_volatility=daily_vol,
        annualized_volatility=annual_vol,
        calculated_at=datetime.now(),
        method="parametric",
    )


def classify_risk_score(var_95_pct: float) -> str:
    """
    Classify portfolio risk based on VaR percentage.
    
    - Low: VaR < 5% (green)
    - Medium: 5% <= VaR < 10% (yellow)
    - High: VaR >= 10% (red)
    
    Args:
        var_95_pct: 95% VaR as percentage of portfolio
        
    Returns:
        Risk score: "low", "medium", or "high"
    """
    if var_95_pct < 0.05:
        return "low"
    elif var_95_pct < 0.10:
        return "medium"
    else:
        return "high"


def calculate_portfolio_var(
    positions: List[Dict[str, Any]],
    use_correlation: bool = True,
) -> PortfolioVaRResult:
    """
    Calculate VaR for entire portfolio.
    
    Args:
        positions: List of position dicts with ticker and market_value
        use_correlation: Whether to account for correlation (diversification benefit)
        
    Returns:
        PortfolioVaRResult with aggregated metrics
    """
    if not positions:
        return PortfolioVaRResult(
            total_value=0,
            var_95_daily=0,
            var_99_daily=0,
            var_95_pct=0,
            var_99_pct=0,
            risk_score="low",
            position_vars=[],
            correlation_benefit=0,
            calculated_at=datetime.now(),
        )
    
    # Calculate VaR for each position
    position_vars = []
    total_value = 0
    
    for pos in positions:
        ticker = pos.get("ticker", "")
        market_value = pos.get("market_value", 0)
        
        if market_value <= 0:
            continue
        
        var_result = calculate_position_var(ticker, market_value)
        position_vars.append(var_result)
        total_value += market_value
    
    if total_value <= 0:
        return PortfolioVaRResult(
            total_value=0,
            var_95_daily=0,
            var_99_daily=0,
            var_95_pct=0,
            var_99_pct=0,
            risk_score="low",
            position_vars=[],
            correlation_benefit=0,
            calculated_at=datetime.now(),
        )
    
    # Sum of individual VaRs (undiversified)
    sum_var_95 = sum(p.var_95_daily for p in position_vars)
    sum_var_99 = sum(p.var_99_daily for p in position_vars)
    
    # For simplified portfolio VaR, assume average correlation of 0.3
    # This provides some diversification benefit
    # More accurate would require fetching correlation matrix
    if use_correlation and len(position_vars) > 1:
        avg_correlation = 0.3
        n = len(position_vars)
        
        # Simplified diversification factor
        # Portfolio variance ≈ sum(individual variances) × (1/n + (n-1)/n × correlation)
        diversification_factor = np.sqrt((1/n) + ((n-1)/n) * avg_correlation)
        
        portfolio_var_95 = sum_var_95 * diversification_factor
        portfolio_var_99 = sum_var_99 * diversification_factor
        
        correlation_benefit = 1 - diversification_factor
    else:
        portfolio_var_95 = sum_var_95
        portfolio_var_99 = sum_var_99
        correlation_benefit = 0
    
    # Calculate percentages
    var_95_pct = portfolio_var_95 / total_value
    var_99_pct = portfolio_var_99 / total_value
    
    # Classify risk
    risk_score = classify_risk_score(var_95_pct)
    
    return PortfolioVaRResult(
        total_value=total_value,
        var_95_daily=portfolio_var_95,
        var_99_daily=portfolio_var_99,
        var_95_pct=var_95_pct,
        var_99_pct=var_99_pct,
        risk_score=risk_score,
        position_vars=position_vars,
        correlation_benefit=correlation_benefit,
        calculated_at=datetime.now(),
    )


def add_var_to_positions(
    positions: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Add VaR calculations to each position in the list.
    
    Args:
        positions: List of position dicts
        
    Returns:
        Same list with var_95_daily added to each position
    """
    for pos in positions:
        ticker = pos.get("ticker", "")
        market_value = pos.get("market_value", 0)
        
        if market_value > 0:
            var_result = calculate_position_var(ticker, market_value)
            pos["var_95_daily"] = round(var_result.var_95_daily, 2)
            pos["var_95_pct"] = round(var_result.var_95_pct, 4)
            pos["daily_volatility"] = round(var_result.daily_volatility, 6)
            pos["annualized_volatility"] = round(var_result.annualized_volatility, 4)
        else:
            pos["var_95_daily"] = 0
            pos["var_95_pct"] = 0
            pos["daily_volatility"] = 0
            pos["annualized_volatility"] = 0
    
    return positions


# Cache for VaR calculations (reuse within session)
_var_cache: Dict[str, Tuple[float, VaRResult]] = {}
VAR_CACHE_TTL_SECONDS = 3600  # 1 hour


def calculate_position_var_cached(
    ticker: str,
    position_value: float,
) -> VaRResult:
    """
    Calculate VaR with caching to avoid repeated yfinance calls.
    
    Cache stores volatility by ticker, VaR is recalculated for position value.
    """
    import time
    
    cache_key = ticker
    current_time = time.time()
    
    # Check cache for volatility data
    if cache_key in _var_cache:
        cached_time, cached_result = _var_cache[cache_key]
        if current_time - cached_time < VAR_CACHE_TTL_SECONDS:
            # Use cached volatility, recalculate VaR for current position value
            var_95 = calculate_parametric_var(
                position_value, cached_result.daily_volatility, 0.95
            )
            var_99 = calculate_parametric_var(
                position_value, cached_result.daily_volatility, 0.99
            )
            
            return VaRResult(
                ticker=ticker,
                position_value=position_value,
                var_95_daily=var_95,
                var_99_daily=var_99,
                var_95_pct=var_95 / position_value if position_value > 0 else 0,
                var_99_pct=var_99 / position_value if position_value > 0 else 0,
                daily_volatility=cached_result.daily_volatility,
                annualized_volatility=cached_result.annualized_volatility,
                calculated_at=datetime.now(),
                method="parametric_cached",
            )
    
    # Calculate fresh
    result = calculate_position_var(ticker, position_value)
    
    # Cache the result
    _var_cache[cache_key] = (current_time, result)
    
    return result


def clear_var_cache() -> None:
    """Clear the VaR cache (for testing)."""
    global _var_cache
    _var_cache = {}
