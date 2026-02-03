"""
F2.1 Fundamental Score

Score stocks 0-100 based on fundamentals.
Components: Value (25%), Quality (35%), Growth (40%)
Uses percentile ranking across universe for fair comparison.
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

from data.fundamental_fetcher import fetch_fundamentals, fetch_all_fundamentals, load_fundamentals
from data.stock_universe import get_universe


# Cache directory
CACHE_DIR = Path(__file__).parent.parent.parent / "data"
SCORES_CACHE = CACHE_DIR / "fundamental_scores.json"


@dataclass
class FundamentalScoreResult:
    """Result of fundamental score calculation."""
    ticker: str
    total_score: float
    value_score: float
    quality_score: float
    growth_score: float
    percentile_rank: float  # 0-100, where 100 is best
    details: Dict
    

def percentile_rank(values: pd.Series, ascending: bool = True) -> pd.Series:
    """
    Calculate percentile rank for a series (0-100).
    
    Args:
        values: Series of values to rank
        ascending: If True, lower values get higher rank (good for P/E)
                  If False, higher values get higher rank (good for ROE)
    """
    if ascending:
        return values.rank(pct=True, ascending=True) * 100
    else:
        return values.rank(pct=True, ascending=False) * 100


def calculate_value_score(fundamentals_df: pd.DataFrame) -> pd.Series:
    """
    Calculate value score (0-100) based on valuation metrics.
    Lower P/E, P/B, P/S = higher score (undervalued).
    
    Components:
    - P/E Ratio: 35%
    - P/B Ratio: 25%
    - P/S Ratio: 20%
    - PEG Ratio: 20%
    """
    scores = pd.DataFrame(index=fundamentals_df.index)
    
    # P/E (lower is better, but exclude negative/extreme)
    pe = fundamentals_df['pe_ratio'].clip(0, 100)
    scores['pe_score'] = percentile_rank(pe, ascending=True)  # Low P/E = high score
    
    # P/B (lower is better)
    pb = fundamentals_df['pb_ratio'].clip(0, 20)
    scores['pb_score'] = percentile_rank(pb, ascending=True)
    
    # P/S (lower is better)
    ps = fundamentals_df['ps_ratio'].clip(0, 30)
    scores['ps_score'] = percentile_rank(ps, ascending=True)
    
    # PEG (lower is better, ideally < 1)
    peg = fundamentals_df['peg_ratio'].clip(0, 5)
    scores['peg_score'] = percentile_rank(peg, ascending=True)
    
    # Weighted average
    value_score = (
        scores['pe_score'] * 0.35 +
        scores['pb_score'] * 0.25 +
        scores['ps_score'] * 0.20 +
        scores['peg_score'] * 0.20
    )
    
    return value_score.fillna(50)  # Default to neutral


def calculate_quality_score(fundamentals_df: pd.DataFrame) -> pd.Series:
    """
    Calculate quality score (0-100) based on profitability and health.
    Higher margins, ROE, lower debt = higher score.
    
    Components:
    - ROE: 30%
    - Profit Margin: 25%
    - Operating Margin: 20%
    - Debt/Equity (inverse): 15%
    - Current Ratio: 10%
    """
    scores = pd.DataFrame(index=fundamentals_df.index)
    
    # ROE (higher is better)
    roe = fundamentals_df['roe'].clip(-0.5, 1.0)
    scores['roe_score'] = percentile_rank(roe, ascending=False)
    
    # Profit Margin (higher is better)
    profit = fundamentals_df['profit_margin'].clip(-0.5, 0.5)
    scores['profit_score'] = percentile_rank(profit, ascending=False)
    
    # Operating Margin (higher is better)
    operating = fundamentals_df['operating_margin'].clip(-0.5, 0.5)
    scores['operating_score'] = percentile_rank(operating, ascending=False)
    
    # Debt/Equity (lower is better)
    de = fundamentals_df['debt_to_equity'].clip(0, 500)
    scores['de_score'] = percentile_rank(de, ascending=True)
    
    # Current Ratio (higher is better, but not too high)
    current = fundamentals_df['current_ratio'].clip(0, 5)
    scores['current_score'] = percentile_rank(current, ascending=False)
    
    # Weighted average
    quality_score = (
        scores['roe_score'] * 0.30 +
        scores['profit_score'] * 0.25 +
        scores['operating_score'] * 0.20 +
        scores['de_score'] * 0.15 +
        scores['current_score'] * 0.10
    )
    
    return quality_score.fillna(50)


def calculate_growth_score(fundamentals_df: pd.DataFrame) -> pd.Series:
    """
    Calculate growth score (0-100) based on growth metrics.
    Higher revenue/earnings growth = higher score.
    
    Components:
    - Revenue Growth: 40%
    - Earnings Growth: 40%
    - EPS Forward vs TTM: 20%
    """
    scores = pd.DataFrame(index=fundamentals_df.index)
    
    # Revenue Growth (higher is better)
    rev_growth = fundamentals_df['revenue_growth'].clip(-0.5, 1.0)
    scores['rev_score'] = percentile_rank(rev_growth, ascending=False)
    
    # Earnings Growth (higher is better)
    earn_growth = fundamentals_df['earnings_growth'].clip(-0.5, 1.0)
    scores['earn_score'] = percentile_rank(earn_growth, ascending=False)
    
    # EPS Forward vs TTM (forward momentum)
    eps_ttm = fundamentals_df['eps_ttm']
    eps_fwd = fundamentals_df['eps_forward']
    eps_growth = ((eps_fwd - eps_ttm) / eps_ttm.abs().clip(lower=0.01)).clip(-1, 1)
    scores['eps_score'] = percentile_rank(eps_growth, ascending=False)
    
    # Weighted average
    growth_score = (
        scores['rev_score'] * 0.40 +
        scores['earn_score'] * 0.40 +
        scores['eps_score'] * 0.20
    )
    
    return growth_score.fillna(50)


def calculate_fundamental_scores(fundamentals: Dict[str, Dict] = None) -> Dict[str, FundamentalScoreResult]:
    """
    Calculate fundamental scores for all stocks.
    
    Args:
        fundamentals: Dict of fundamental data (if None, loads from cache)
    
    Returns:
        Dict mapping ticker to FundamentalScoreResult
    """
    # Load fundamentals
    if fundamentals is None:
        cached = load_fundamentals()
        if cached is None:
            logger.warning("No cached fundamentals, fetching fresh data...")
            fundamentals = fetch_all_fundamentals()
        else:
            fundamentals = cached.get("stocks", {})
    
    if not fundamentals:
        logger.error("No fundamental data available")
        return {}
    
    logger.info(f"Calculating fundamental scores for {len(fundamentals)} stocks...")
    
    # Convert to DataFrame for vectorized operations
    df = pd.DataFrame.from_dict(fundamentals, orient='index')
    
    # Calculate component scores
    value_scores = calculate_value_score(df)
    quality_scores = calculate_quality_score(df)
    growth_scores = calculate_growth_score(df)
    
    # Composite fundamental score (weighted)
    # Value: 25%, Quality: 35%, Growth: 40%
    total_scores = (
        value_scores * 0.25 +
        quality_scores * 0.35 +
        growth_scores * 0.40
    )
    
    # Calculate percentile rank of total score
    percentile_ranks = percentile_rank(total_scores, ascending=False)
    
    # Build results
    results = {}
    for ticker in df.index:
        try:
            results[ticker] = FundamentalScoreResult(
                ticker=ticker,
                total_score=round(float(total_scores.loc[ticker]), 2),
                value_score=round(float(value_scores.loc[ticker]), 2),
                quality_score=round(float(quality_scores.loc[ticker]), 2),
                growth_score=round(float(growth_scores.loc[ticker]), 2),
                percentile_rank=round(float(percentile_ranks.loc[ticker]), 2),
                details={
                    "pe_ratio": fundamentals[ticker].get("pe_ratio"),
                    "pb_ratio": fundamentals[ticker].get("pb_ratio"),
                    "roe": fundamentals[ticker].get("roe"),
                    "profit_margin": fundamentals[ticker].get("profit_margin"),
                    "revenue_growth": fundamentals[ticker].get("revenue_growth"),
                    "debt_to_equity": fundamentals[ticker].get("debt_to_equity"),
                }
            )
        except Exception as e:
            logger.warning(f"Error calculating score for {ticker}: {e}")
    
    logger.info(f"Calculated scores for {len(results)} stocks")
    return results


def get_fundamental_score(ticker: str) -> Optional[FundamentalScoreResult]:
    """
    Get fundamental score for a single stock.
    """
    scores = calculate_fundamental_scores()
    return scores.get(ticker.upper())


def save_fundamental_scores(scores: Dict[str, FundamentalScoreResult], path: Path = SCORES_CACHE) -> None:
    """Save scores to JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    
    data = {
        "updated_at": datetime.now().isoformat(),
        "count": len(scores),
        "scores": {
            ticker: {
                "ticker": r.ticker,
                "total_score": r.total_score,
                "value_score": r.value_score,
                "quality_score": r.quality_score,
                "growth_score": r.growth_score,
                "percentile_rank": r.percentile_rank,
                "details": r.details,
            }
            for ticker, r in scores.items()
        }
    }
    
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)
    
    logger.info(f"Saved fundamental scores to {path}")


def load_fundamental_scores(path: Path = SCORES_CACHE) -> Optional[Dict]:
    """Load scores from JSON."""
    if not path.exists():
        return None
    
    with open(path, 'r') as f:
        return json.load(f)


def get_top_fundamental_stocks(n: int = 10) -> List[Tuple[str, float]]:
    """
    Get top N stocks by fundamental score.
    
    Returns:
        List of (ticker, score) tuples
    """
    scores = calculate_fundamental_scores()
    sorted_scores = sorted(
        scores.items(),
        key=lambda x: x[1].total_score,
        reverse=True
    )
    return [(t, s.total_score) for t, s in sorted_scores[:n]]


# CLI for testing
if __name__ == "__main__":
    import sys
    logger.add(sys.stderr, level="INFO")
    
    print("\n=== Fundamental Score Test ===\n")
    
    # Calculate scores
    scores = calculate_fundamental_scores()
    
    # Top 10
    print("Top 10 by Fundamental Score:")
    top = get_top_fundamental_stocks(10)
    for i, (ticker, score) in enumerate(top, 1):
        result = scores[ticker]
        print(f"  {i}. {ticker}: {score:.1f} (V:{result.value_score:.0f} Q:{result.quality_score:.0f} G:{result.growth_score:.0f})")
    
    # Bottom 5
    print("\nBottom 5:")
    bottom = sorted(scores.items(), key=lambda x: x[1].total_score)[:5]
    for ticker, result in bottom:
        print(f"  {ticker}: {result.total_score:.1f}")
    
    # Save
    save_fundamental_scores(scores)
    
    print("\n✅ Fundamental scoring working!")
