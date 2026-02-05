"""
F2.5 Composite Score

Combine all scores into final 0-100 score.
Weights: Fundamental 35%, Sentiment 25%, Macro 20%, Technical 20%
Signals: BUY (≥70), HOLD (40-69), SELL (<40)
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from pathlib import Path
import json
from loguru import logger
from dataclasses import dataclass
from enum import Enum

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from scoring.fundamental_score import (
    calculate_fundamental_scores,
    FundamentalScoreResult,
)
from scoring.sentiment_score import (
    calculate_sentiment_scores,
    SentimentScoreResult,
)
from scoring.technical_score import (
    calculate_technical_scores,
    TechnicalScoreResult,
)
from scoring.macro_score import (
    calculate_macro_scores,
    MacroScoreResult,
)
from data.stock_universe import get_universe


# Cache directory
CACHE_DIR = Path(__file__).parent.parent.parent / "data"
COMPOSITE_CACHE = CACHE_DIR / "composite_scores.json"

# Score weights (per PRD)
WEIGHTS = {
    "fundamental": 0.35,
    "sentiment": 0.25,
    "macro": 0.20,
    "technical": 0.20,
}

# Signal thresholds (default: moderate risk)
SIGNAL_THRESHOLDS = {
    "BUY": 70,
    "HOLD_UPPER": 70,
    "HOLD_LOWER": 40,
    "SELL": 40,
}

# REC-126: Risk-adjusted thresholds
# Conservative: Higher bar for BUY, lower bar for SELL (fewer trades, safer)
# Aggressive: Lower bar for BUY, higher bar for SELL (more trades, riskier)
RISK_ADJUSTED_THRESHOLDS = {
    "conservative": {"BUY": 80, "HOLD_UPPER": 80, "HOLD_LOWER": 30, "SELL": 30},
    "moderate": {"BUY": 70, "HOLD_UPPER": 70, "HOLD_LOWER": 40, "SELL": 40},
    "aggressive": {"BUY": 60, "HOLD_UPPER": 60, "HOLD_LOWER": 50, "SELL": 50},
}


def get_thresholds_for_risk(risk_tolerance: str = "moderate") -> Dict[str, int]:
    """Get signal thresholds based on user's risk tolerance (REC-126)."""
    return RISK_ADJUSTED_THRESHOLDS.get(
        risk_tolerance.lower(),
        SIGNAL_THRESHOLDS  # fallback to default
    )


class Signal(str, Enum):
    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"


@dataclass
class CompositeScoreResult:
    """Result of composite score calculation."""
    ticker: str
    sector: str
    total_score: float
    signal: Signal
    rank: int  # 1 = best
    percentile: float  # 0-100
    
    # Component scores
    fundamental_score: float
    sentiment_score: float
    technical_score: float
    macro_score: float
    
    # Week-over-week change (if available)
    score_change: Optional[float]
    signal_change: Optional[str]  # e.g., "HOLD -> BUY"
    
    # Detailed breakdown
    details: Dict


def get_signal(score: float, risk_tolerance: str = "moderate") -> Signal:
    """
    Convert score to trading signal (REC-126).
    
    Thresholds adjust based on risk tolerance:
    - Conservative: BUY ≥80, SELL <30
    - Moderate: BUY ≥70, SELL <40 (default)
    - Aggressive: BUY ≥60, SELL <50
    """
    thresholds = get_thresholds_for_risk(risk_tolerance)
    if score >= thresholds["BUY"]:
        return Signal.BUY
    elif score >= thresholds["SELL"]:
        return Signal.HOLD
    else:
        return Signal.SELL


def calculate_composite_scores(
    tickers: List[str] = None,
    previous_scores: Dict = None,
) -> Dict[str, CompositeScoreResult]:
    """
    Calculate composite scores for all stocks.
    
    Args:
        tickers: List of tickers (if None, uses universe)
        previous_scores: Previous week's scores for change tracking
    
    Returns:
        Dict mapping ticker to CompositeScoreResult
    """
    logger.info("=" * 60)
    logger.info("CALCULATING COMPOSITE SCORES")
    logger.info("=" * 60)
    
    # Get universe
    universe = get_universe()
    if tickers is None:
        tickers = [s["ticker"] for s in universe]
    
    # Build ticker -> sector mapping
    ticker_sectors = {s["ticker"].upper(): s["sector"] for s in universe}
    
    logger.info(f"Scoring {len(tickers)} stocks...")
    logger.info(f"Weights: F={WEIGHTS['fundamental']:.0%} S={WEIGHTS['sentiment']:.0%} "
                f"T={WEIGHTS['technical']:.0%} M={WEIGHTS['macro']:.0%}")
    
    # Calculate all component scores
    logger.info("\n[1/4] Calculating fundamental scores...")
    fundamental_scores = calculate_fundamental_scores()
    
    logger.info("\n[2/4] Calculating sentiment scores...")
    sentiment_scores = calculate_sentiment_scores(tickers)
    
    logger.info("\n[3/4] Calculating technical scores...")
    technical_scores = calculate_technical_scores(tickers)
    
    logger.info("\n[4/4] Calculating macro scores...")
    macro_scores = calculate_macro_scores(tickers)
    
    # Combine into composite scores
    logger.info("\nCombining scores...")
    results = {}
    
    for ticker in tickers:
        ticker_upper = ticker.upper()
        
        # Get component scores (default to 50 if missing)
        f_score = fundamental_scores.get(ticker_upper)
        s_score = sentiment_scores.get(ticker_upper)
        t_score = technical_scores.get(ticker_upper)
        m_score = macro_scores.get(ticker_upper)
        
        f_val = f_score.total_score if f_score else 50.0
        s_val = s_score.total_score if s_score else 50.0
        t_val = t_score.total_score if t_score else 50.0
        m_val = m_score.total_score if m_score else 50.0
        
        # Calculate weighted composite
        total_score = (
            f_val * WEIGHTS["fundamental"] +
            s_val * WEIGHTS["sentiment"] +
            t_val * WEIGHTS["technical"] +
            m_val * WEIGHTS["macro"]
        )
        
        # Get signal
        signal = get_signal(total_score)
        
        # Track week-over-week change
        score_change = None
        signal_change = None
        if previous_scores and ticker_upper in previous_scores:
            prev = previous_scores[ticker_upper]
            score_change = total_score - prev.get("total_score", total_score)
            prev_signal = prev.get("signal", signal.value)
            if prev_signal != signal.value:
                signal_change = f"{prev_signal} -> {signal.value}"
        
        results[ticker_upper] = CompositeScoreResult(
            ticker=ticker_upper,
            sector=ticker_sectors.get(ticker_upper, "Unknown"),
            total_score=round(total_score, 2),
            signal=signal,
            rank=0,  # Calculated below
            percentile=0,  # Calculated below
            fundamental_score=round(f_val, 2),
            sentiment_score=round(s_val, 2),
            technical_score=round(t_val, 2),
            macro_score=round(m_val, 2),
            score_change=round(score_change, 2) if score_change else None,
            signal_change=signal_change,
            details={
                "fundamental": f_score.details if f_score else {},
                "sentiment": s_score.details if s_score else {},
                "technical": t_score.details if t_score else {},
                "macro": m_score.details if m_score else {},
            }
        )
    
    # Normalize scores to use full 0-100 range via z-score normalization
    # This preserves relative ranking while ensuring BUY/SELL signals are generated
    raw_scores = [r.total_score for r in results.values()]
    if len(raw_scores) > 1:
        mean_score = np.mean(raw_scores)
        std_score = np.std(raw_scores)
        if std_score > 0:
            for ticker, result in results.items():
                # Z-score: how many std devs from mean
                z = (result.total_score - mean_score) / std_score
                # Map z-score to 0-100 range (z of ±2.5 maps to 0/100)
                # This gives ~15-20% BUY and ~15-20% SELL with normal distribution
                normalized = 50 + z * 15  # 15 points per std dev
                normalized = max(5, min(95, normalized))  # Cap at 5-95
                result.total_score = round(normalized, 2)
                result.signal = get_signal(result.total_score)
    
    # Calculate ranks and percentiles
    sorted_results = sorted(results.values(), key=lambda x: x.total_score, reverse=True)
    for i, result in enumerate(sorted_results):
        result.rank = i + 1
        result.percentile = round((len(sorted_results) - i) / len(sorted_results) * 100, 2)
    
    # Log summary
    buy_count = sum(1 for r in results.values() if r.signal == Signal.BUY)
    hold_count = sum(1 for r in results.values() if r.signal == Signal.HOLD)
    sell_count = sum(1 for r in results.values() if r.signal == Signal.SELL)
    
    logger.info("\n" + "=" * 60)
    logger.info("SCORING COMPLETE")
    logger.info(f"Total: {len(results)} stocks")
    logger.info(f"Signals: {buy_count} BUY | {hold_count} HOLD | {sell_count} SELL")
    logger.info("=" * 60)
    
    return results


def get_top_stocks(
    scores: Dict[str, CompositeScoreResult] = None,
    n: int = 10,
    signal: Signal = Signal.BUY
) -> List[CompositeScoreResult]:
    """
    Get top N stocks by score, optionally filtered by signal.
    
    Args:
        scores: Pre-calculated scores (if None, calculates fresh)
        n: Number of stocks to return
        signal: Filter by signal (None for all)
    
    Returns:
        List of top CompositeScoreResult
    """
    if scores is None:
        scores = calculate_composite_scores()
    
    filtered = [r for r in scores.values() if signal is None or r.signal == signal]
    sorted_scores = sorted(filtered, key=lambda x: x.total_score, reverse=True)
    
    return sorted_scores[:n]


def get_score(ticker: str) -> Optional[CompositeScoreResult]:
    """Get composite score for a single stock."""
    scores = calculate_composite_scores(tickers=[ticker])
    return scores.get(ticker.upper())


def save_composite_scores(scores: Dict[str, CompositeScoreResult], path: Path = COMPOSITE_CACHE) -> None:
    """Save scores to JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)

    # BUG-026 fix: build ticker→company name map from universe
    from data.stock_universe import load_universe
    _ticker_to_company = {}
    universe = load_universe()
    if universe:
        for stock in universe.get("stocks", []):
            _ticker_to_company[stock["ticker"]] = stock.get("name", stock["ticker"])
    
    data = {
        "updated_at": datetime.now().isoformat(),
        "count": len(scores),
        "weights": WEIGHTS,
        "thresholds": SIGNAL_THRESHOLDS,
        "summary": {
            "buy_count": sum(1 for r in scores.values() if r.signal == Signal.BUY),
            "hold_count": sum(1 for r in scores.values() if r.signal == Signal.HOLD),
            "sell_count": sum(1 for r in scores.values() if r.signal == Signal.SELL),
        },
        "scores": {
            ticker: {
                "ticker": r.ticker,
                "company_name": _ticker_to_company.get(r.ticker),  # BUG-026 fix
                "sector": r.sector,
                "total_score": r.total_score,
                "signal": r.signal.value,
                "rank": r.rank,
                "percentile": r.percentile,
                "fundamental_score": r.fundamental_score,
                "sentiment_score": r.sentiment_score,
                "technical_score": r.technical_score,
                "macro_score": r.macro_score,
                "score_change": r.score_change,
                "signal_change": r.signal_change,
            }
            for ticker, r in scores.items()
        }
    }
    
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)
    
    logger.info(f"Saved composite scores to {path}")


def load_composite_scores(path: Path = COMPOSITE_CACHE) -> Optional[Dict]:
    """Load scores from JSON."""
    if not path.exists():
        return None
    
    with open(path, 'r') as f:
        return json.load(f)


# CLI for testing
if __name__ == "__main__":
    import sys
    logger.add(sys.stderr, level="INFO")
    
    print("\n=== Composite Score Test (Small Sample) ===\n")
    
    # Test with small sample
    test_tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "JPM", "JNJ", "XOM"]
    
    scores = calculate_composite_scores(tickers=test_tickers)
    
    print("\nResults:")
    print("-" * 80)
    print(f"{'Rank':<5} {'Ticker':<8} {'Score':<8} {'Signal':<8} {'F':<8} {'S':<8} {'T':<8} {'M':<8}")
    print("-" * 80)
    
    for result in sorted(scores.values(), key=lambda x: x.total_score, reverse=True):
        print(f"{result.rank:<5} {result.ticker:<8} {result.total_score:<8.1f} {result.signal.value:<8} "
              f"{result.fundamental_score:<8.1f} {result.sentiment_score:<8.1f} "
              f"{result.technical_score:<8.1f} {result.macro_score:<8.1f}")
    
    print("\n✅ Composite scoring working!")
