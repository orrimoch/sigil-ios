"""
F2.3 Technical Score

Score stocks 0-100 based on price momentum and technical indicators.
Components: Momentum (40%), RSI (30%), Trend (30%)
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from pathlib import Path
import json
from loguru import logger
from dataclasses import dataclass

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from data.price_fetcher import fetch_price_history, load_prices, fetch_all_prices
from data.stock_universe import get_universe


# Cache directory
CACHE_DIR = Path(__file__).parent.parent.parent / "data"
TECHNICAL_CACHE = CACHE_DIR / "technical_scores.json"


@dataclass
class TechnicalScoreResult:
    """Result of technical score calculation."""
    ticker: str
    total_score: float  # 0-100
    momentum_score: float
    rsi_score: float
    trend_score: float
    percentile_rank: float
    details: Dict


def calculate_rsi(prices: pd.Series, period: int = 14) -> float:
    """
    Calculate Relative Strength Index (RSI).
    
    RSI = 100 - (100 / (1 + RS))
    RS = Average Gain / Average Loss
    
    Returns:
        RSI value (0-100)
    """
    if len(prices) < period + 1:
        return 50.0  # Neutral
    
    # Calculate daily returns
    delta = prices.diff()
    
    # Separate gains and losses
    gains = delta.clip(lower=0)
    losses = (-delta).clip(lower=0)
    
    # Calculate average gain/loss
    avg_gain = gains.rolling(window=period).mean()
    avg_loss = losses.rolling(window=period).mean()
    
    # Calculate RS and RSI
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    
    return float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50.0


def calculate_momentum(prices: pd.Series) -> Dict[str, float]:
    """
    Calculate momentum indicators.
    
    Returns:
        Dict with momentum metrics
    """
    if len(prices) < 252:  # Need ~1 year of data
        return {
            "return_1m": 0,
            "return_3m": 0,
            "return_6m": 0,
            "return_12m": 0,
        }
    
    current = prices.iloc[-1]
    
    # Calculate returns over different periods
    def safe_return(days):
        if len(prices) > days:
            old_price = prices.iloc[-days]
            if old_price > 0:
                return (current - old_price) / old_price
        return 0
    
    return {
        "return_1m": safe_return(21),    # ~1 month
        "return_3m": safe_return(63),    # ~3 months
        "return_6m": safe_return(126),   # ~6 months
        "return_12m": safe_return(252),  # ~12 months
    }


def calculate_trend(prices: pd.Series) -> Dict[str, any]:
    """
    Calculate trend indicators (MA crossovers).
    
    Returns:
        Dict with trend metrics
    """
    if len(prices) < 200:
        return {
            "above_sma50": False,
            "above_sma200": False,
            "sma50_above_sma200": False,  # Golden cross
            "price_vs_sma50_pct": 0,
            "price_vs_sma200_pct": 0,
        }
    
    current = prices.iloc[-1]
    sma50 = prices.rolling(50).mean().iloc[-1]
    sma200 = prices.rolling(200).mean().iloc[-1]
    
    return {
        "above_sma50": current > sma50,
        "above_sma200": current > sma200,
        "sma50_above_sma200": sma50 > sma200,
        "price_vs_sma50_pct": (current - sma50) / sma50 if sma50 > 0 else 0,
        "price_vs_sma200_pct": (current - sma200) / sma200 if sma200 > 0 else 0,
    }


def calculate_technical_score_for_ticker(
    ticker: str,
    prices: pd.DataFrame = None
) -> TechnicalScoreResult:
    """
    Calculate technical score for a single stock.
    
    Args:
        ticker: Stock ticker
        prices: Pre-loaded price DataFrame (if None, fetches)
    
    Returns:
        TechnicalScoreResult
    """
    if prices is None:
        prices = load_prices(ticker)
        if prices is None:
            prices = fetch_price_history(ticker, period="5y")
    
    if prices is None or len(prices) < 50:
        return TechnicalScoreResult(
            ticker=ticker,
            total_score=50.0,
            momentum_score=50.0,
            rsi_score=50.0,
            trend_score=50.0,
            percentile_rank=50.0,
            details={"error": "Insufficient price data"}
        )
    
    # Extract close prices
    close = prices['close'] if 'close' in prices.columns else prices.iloc[:, 0]
    
    # Calculate indicators
    rsi = calculate_rsi(close)
    momentum = calculate_momentum(close)
    trend = calculate_trend(close)
    
    # --- RSI Score (30%) ---
    # RSI 30-70 is neutral; < 30 oversold (bullish), > 70 overbought (bearish)
    if rsi < 30:
        rsi_score = 80 + (30 - rsi)  # 80-110, cap at 100
    elif rsi > 70:
        rsi_score = 20 - (rsi - 70)  # -10 to 20, floor at 0
    else:
        # 30-70 maps to 30-70 score
        rsi_score = rsi
    rsi_score = max(0, min(100, rsi_score))
    
    # --- Momentum Score (40%) ---
    # Weight recent performance more, exclude very recent (mean reversion)
    # 1m: 10%, 3m: 30%, 6m: 35%, 12m: 25%
    mom_score = 50  # Start neutral
    
    # Convert returns to scores (10% return = +10 points, -10% = -10 points)
    mom_score += momentum["return_1m"] * 100 * 0.10
    mom_score += momentum["return_3m"] * 100 * 0.30
    mom_score += momentum["return_6m"] * 100 * 0.35
    mom_score += momentum["return_12m"] * 100 * 0.25
    
    mom_score = max(0, min(100, mom_score))
    
    # --- Trend Score (30%) ---
    trend_score = 50
    
    if trend["above_sma50"]:
        trend_score += 10
    else:
        trend_score -= 10
    
    if trend["above_sma200"]:
        trend_score += 15
    else:
        trend_score -= 15
    
    if trend["sma50_above_sma200"]:  # Golden cross
        trend_score += 15
    else:  # Death cross
        trend_score -= 10
    
    # Price vs MA bonus/penalty
    trend_score += trend["price_vs_sma50_pct"] * 20
    
    trend_score = max(0, min(100, trend_score))
    
    # --- Total Score ---
    total_score = (
        mom_score * 0.40 +
        rsi_score * 0.30 +
        trend_score * 0.30
    )
    
    return TechnicalScoreResult(
        ticker=ticker,
        total_score=round(total_score, 2),
        momentum_score=round(mom_score, 2),
        rsi_score=round(rsi_score, 2),
        trend_score=round(trend_score, 2),
        percentile_rank=0,  # Calculated later across universe
        details={
            "rsi": round(rsi, 2),
            "momentum": {k: round(v * 100, 2) for k, v in momentum.items()},
            "trend": {
                "above_sma50": trend["above_sma50"],
                "above_sma200": trend["above_sma200"],
                "golden_cross": trend["sma50_above_sma200"],
            }
        }
    )


def calculate_technical_scores(
    tickers: List[str] = None,
) -> Dict[str, TechnicalScoreResult]:
    """
    Calculate technical scores for all stocks.
    
    Args:
        tickers: List of tickers (if None, uses universe)
    
    Returns:
        Dict mapping ticker to TechnicalScoreResult
    """
    if tickers is None:
        universe = get_universe()
        tickers = [s["ticker"] for s in universe]
    
    logger.info(f"Calculating technical scores for {len(tickers)} stocks...")
    
    results = {}
    for i, ticker in enumerate(tickers):
        result = calculate_technical_score_for_ticker(ticker)
        results[ticker] = result
        
        if (i + 1) % 50 == 0:
            logger.info(f"  Progress: {i + 1}/{len(tickers)}")
    
    # Calculate percentile ranks
    scores = [r.total_score for r in results.values()]
    for ticker, result in results.items():
        rank = sum(1 for s in scores if s <= result.total_score) / len(scores) * 100
        result.percentile_rank = round(rank, 2)
    
    logger.info(f"Calculated technical scores for {len(results)} stocks")
    return results


def get_technical_score(ticker: str) -> Optional[TechnicalScoreResult]:
    """Get technical score for a single stock."""
    return calculate_technical_score_for_ticker(ticker)


def save_technical_scores(scores: Dict[str, TechnicalScoreResult], path: Path = TECHNICAL_CACHE) -> None:
    """Save scores to JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    
    data = {
        "updated_at": datetime.now().isoformat(),
        "count": len(scores),
        "scores": {
            ticker: {
                "ticker": r.ticker,
                "total_score": r.total_score,
                "momentum_score": r.momentum_score,
                "rsi_score": r.rsi_score,
                "trend_score": r.trend_score,
                "percentile_rank": r.percentile_rank,
                "details": r.details,
            }
            for ticker, r in scores.items()
        }
    }
    
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)
    
    logger.info(f"Saved technical scores to {path}")


def load_technical_scores(path: Path = TECHNICAL_CACHE) -> Optional[Dict]:
    """Load scores from JSON."""
    if not path.exists():
        return None
    
    with open(path, 'r') as f:
        return json.load(f)


# CLI for testing
if __name__ == "__main__":
    import sys
    logger.add(sys.stderr, level="INFO")
    
    print("\n=== Technical Score Test ===\n")
    
    # Test single stock
    print("Calculating AAPL technical score...")
    aapl = calculate_technical_score_for_ticker("AAPL")
    print(f"  Total Score: {aapl.total_score:.1f}/100")
    print(f"  Momentum: {aapl.momentum_score:.1f}")
    print(f"  RSI: {aapl.rsi_score:.1f} (raw: {aapl.details.get('rsi', 'N/A')})")
    print(f"  Trend: {aapl.trend_score:.1f}")
    print(f"  Returns: {aapl.details.get('momentum', {})}")
    
    # Test a few more
    print("\nSample stocks:")
    for ticker in ["MSFT", "TSLA", "NVDA", "META"]:
        result = calculate_technical_score_for_ticker(ticker)
        trend = "↑" if result.details.get("trend", {}).get("golden_cross") else "↓"
        print(f"  {ticker}: {result.total_score:.1f} {trend}")
    
    print("\n✅ Technical scoring working!")
