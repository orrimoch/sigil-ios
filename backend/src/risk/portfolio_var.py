"""
Portfolio VaR (Multi-Stock Correlated) - REC-247

Calculate portfolio-level VaR using covariance matrix.
More accurate than sum of individual VaRs due to diversification benefit.

Uses historical returns to estimate covariance matrix.
"""

import numpy as np
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from scipy import stats
import logging

logger = logging.getLogger(__name__)


@dataclass
class CorrelatedVaRResult:
    """Result of portfolio-level VaR calculation."""
    portfolio_value: float
    var_95_daily: float           # 95% VaR in dollars
    var_99_daily: float           # 99% VaR in dollars
    var_95_pct: float             # 95% VaR as percentage
    var_99_pct: float             # 99% VaR as percentage
    diversification_benefit: float  # Reduction from correlation
    sum_individual_vars: float    # Sum of individual VaRs (worst case)
    portfolio_volatility: float   # Annual portfolio volatility
    correlation_matrix: Optional[Dict[str, Dict[str, float]]]
    calculated_at: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "portfolio_value": round(self.portfolio_value, 2),
            "var_95_daily": round(self.var_95_daily, 2),
            "var_99_daily": round(self.var_99_daily, 2),
            "var_95_pct": round(self.var_95_pct * 100, 4),
            "var_99_pct": round(self.var_99_pct * 100, 4),
            "diversification_benefit": round(self.diversification_benefit, 2),
            "diversification_benefit_pct": round(
                (self.diversification_benefit / self.sum_individual_vars * 100) 
                if self.sum_individual_vars > 0 else 0, 2
            ),
            "sum_individual_vars": round(self.sum_individual_vars, 2),
            "portfolio_volatility_annual": round(self.portfolio_volatility * 100, 2),
            "correlation_matrix": self.correlation_matrix,
            "calculated_at": self.calculated_at.isoformat(),
        }


def fetch_returns_matrix(
    tickers: List[str],
    lookback_days: int = 252,
) -> Tuple[np.ndarray, List[str]]:
    """
    Fetch historical returns for multiple tickers.
    
    Returns:
        returns_matrix: Shape (n_days, n_tickers)
        valid_tickers: Tickers that had sufficient data
    """
    import yfinance as yf
    
    if not tickers:
        return np.array([]).reshape(0, 0), []
    
    # Download data for all tickers at once
    data = yf.download(
        tickers,
        period=f"{lookback_days + 30}d",
        progress=False,
        threads=True,
    )
    
    if data.empty:
        return np.array([]).reshape(0, 0), []
    
    # Handle single ticker case (different structure)
    if len(tickers) == 1:
        prices = data['Close']
        returns = prices.pct_change().dropna()
        if len(returns) < 20:
            return np.array([]).reshape(0, 0), []
        return returns.values.reshape(-1, 1), tickers
    
    # Multi-ticker case
    prices = data['Close']
    returns = prices.pct_change().dropna()
    
    # Remove tickers with insufficient data
    valid_tickers = []
    valid_returns = []
    
    for ticker in tickers:
        if ticker in returns.columns:
            col_returns = returns[ticker].dropna()
            if len(col_returns) >= 20:
                valid_tickers.append(ticker)
                valid_returns.append(col_returns.values[-lookback_days:])
    
    if not valid_tickers:
        return np.array([]).reshape(0, 0), []
    
    # Align lengths (take minimum)
    min_len = min(len(r) for r in valid_returns)
    aligned_returns = np.column_stack([r[-min_len:] for r in valid_returns])
    
    return aligned_returns, valid_tickers


def calculate_covariance_matrix(returns: np.ndarray) -> np.ndarray:
    """Calculate covariance matrix from returns."""
    return np.cov(returns, rowvar=False)


def calculate_correlation_matrix(returns: np.ndarray) -> np.ndarray:
    """Calculate correlation matrix from returns."""
    return np.corrcoef(returns, rowvar=False)


def calculate_portfolio_variance(
    weights: np.ndarray,
    cov_matrix: np.ndarray,
) -> float:
    """Calculate portfolio variance from weights and covariance matrix."""
    return float(weights.T @ cov_matrix @ weights)


async def calculate_correlated_var(
    positions: List[Dict[str, Any]],
    lookback_days: int = 252,
    confidence_levels: List[float] = [0.95, 0.99],
) -> Dict[str, Any]:
    """
    Calculate portfolio VaR using correlation matrix.
    
    Args:
        positions: List of positions with ticker, market_value
        lookback_days: Days of history for correlation estimation
        confidence_levels: VaR confidence levels
        
    Returns:
        VaR result with diversification benefit
    """
    if not positions:
        return {
            "portfolio_value": 0,
            "var_95_daily": 0,
            "var_99_daily": 0,
            "var_95_pct": 0,
            "var_99_pct": 0,
            "diversification_benefit": 0,
            "sum_individual_vars": 0,
            "portfolio_volatility_annual": 0,
            "correlation_matrix": None,
            "message": "No positions in portfolio",
        }
    
    # Extract tickers and values
    tickers = [p.get("ticker", "") for p in positions]
    values = np.array([p.get("market_value", 0) for p in positions])
    portfolio_value = float(values.sum())
    
    if portfolio_value == 0:
        return {
            "portfolio_value": 0,
            "var_95_daily": 0,
            "var_99_daily": 0,
            "var_95_pct": 0,
            "var_99_pct": 0,
            "diversification_benefit": 0,
            "sum_individual_vars": 0,
            "portfolio_volatility_annual": 0,
            "correlation_matrix": None,
            "message": "Portfolio has no value",
        }
    
    # Fetch returns
    returns, valid_tickers = fetch_returns_matrix(tickers, lookback_days)
    
    if len(valid_tickers) == 0:
        return {
            "portfolio_value": portfolio_value,
            "var_95_daily": 0,
            "var_99_daily": 0,
            "var_95_pct": 0,
            "var_99_pct": 0,
            "diversification_benefit": 0,
            "sum_individual_vars": 0,
            "portfolio_volatility_annual": 0,
            "correlation_matrix": None,
            "message": "Could not fetch historical data for positions",
        }
    
    # Filter to valid tickers
    valid_indices = [i for i, t in enumerate(tickers) if t in valid_tickers]
    valid_values = values[valid_indices]
    
    # Calculate weights
    weights = valid_values / valid_values.sum()
    
    # Calculate covariance and correlation matrices
    cov_matrix = calculate_covariance_matrix(returns)
    corr_matrix = calculate_correlation_matrix(returns)
    
    # Handle single asset case
    if len(valid_tickers) == 1:
        cov_matrix = np.array([[cov_matrix]])
        corr_matrix = np.array([[1.0]])
    
    # Calculate portfolio volatility (daily)
    portfolio_variance = calculate_portfolio_variance(weights, cov_matrix)
    portfolio_vol_daily = np.sqrt(portfolio_variance)
    portfolio_vol_annual = portfolio_vol_daily * np.sqrt(252)
    
    # Calculate VaR at different confidence levels
    z_95 = stats.norm.ppf(0.95)
    z_99 = stats.norm.ppf(0.99)
    
    var_95_pct = portfolio_vol_daily * z_95
    var_99_pct = portfolio_vol_daily * z_99
    var_95_daily = portfolio_value * var_95_pct
    var_99_daily = portfolio_value * var_99_pct
    
    # Calculate sum of individual VaRs (no diversification)
    individual_vols = np.sqrt(np.diag(cov_matrix))
    individual_vars_95 = (valid_values * individual_vols * z_95).sum()
    
    # Diversification benefit
    diversification_benefit = individual_vars_95 - var_95_daily
    
    # Build correlation matrix dict
    corr_dict: Dict[str, Dict[str, float]] = {}
    for i, t1 in enumerate(valid_tickers):
        corr_dict[t1] = {}
        for j, t2 in enumerate(valid_tickers):
            if len(valid_tickers) > 1:
                corr_dict[t1][t2] = round(float(corr_matrix[i, j]), 3)
            else:
                corr_dict[t1][t2] = 1.0
    
    result = CorrelatedVaRResult(
        portfolio_value=portfolio_value,
        var_95_daily=var_95_daily,
        var_99_daily=var_99_daily,
        var_95_pct=var_95_pct,
        var_99_pct=var_99_pct,
        diversification_benefit=diversification_benefit,
        sum_individual_vars=individual_vars_95,
        portfolio_volatility=portfolio_vol_annual,
        correlation_matrix=corr_dict,
        calculated_at=datetime.now(timezone.utc),
    )
    
    return result.to_dict()


def estimate_correlation_impact(
    ticker1: str,
    ticker2: str,
    lookback_days: int = 252,
) -> Dict[str, Any]:
    """
    Estimate correlation between two stocks.
    
    Useful for understanding diversification benefit of adding a stock.
    """
    import yfinance as yf
    
    data = yf.download(
        [ticker1, ticker2],
        period=f"{lookback_days + 30}d",
        progress=False,
    )
    
    if data.empty:
        return {"error": "Could not fetch data"}
    
    prices = data['Close']
    returns = prices.pct_change().dropna()
    
    if len(returns) < 20:
        return {"error": "Insufficient data"}
    
    correlation = float(returns[ticker1].corr(returns[ticker2]))
    
    return {
        "ticker1": ticker1,
        "ticker2": ticker2,
        "correlation": round(correlation, 3),
        "interpretation": _interpret_correlation(correlation),
        "lookback_days": len(returns),
    }


def _interpret_correlation(corr: float) -> str:
    """Interpret correlation coefficient."""
    if corr >= 0.8:
        return "Very high positive - minimal diversification benefit"
    elif corr >= 0.5:
        return "Moderate positive - some diversification benefit"
    elif corr >= 0.2:
        return "Weak positive - good diversification benefit"
    elif corr >= -0.2:
        return "Near zero - excellent diversification benefit"
    elif corr >= -0.5:
        return "Weak negative - great diversification (hedge)"
    else:
        return "Strong negative - excellent hedge"
