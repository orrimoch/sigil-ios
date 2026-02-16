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
from scoring.relative_scoring import (
    transform_sentiment_scores,
    transform_fundamental_scores,
    transform_technical_scores,
    transform_macro_scores,
)
from data.stock_universe import get_universe


# Relative scoring configuration
RELATIVE_SCORING_ENABLED = True  # Toggle for A/B testing
PRIOR_STRENGTH = 5  # k value for Bayesian shrinkage


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

# REC-263: Crowd Wisdom Score Boost Configuration
CROWD_WISDOM_CONFIG = {
    "enabled": True,
    "boost_threshold": 70,      # Viral score above this gets boost
    "penalty_threshold": 30,    # Viral score below this gets penalty (if stock is in CW data)
    "max_boost": 10,            # Maximum points to add
    "max_penalty": 3,           # Maximum points to subtract
    "boost_curve": "linear",    # linear | sqrt | log
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


def get_crowd_wisdom_boost(viral_score: float) -> float:
    """
    REC-263: Calculate score boost/penalty based on crowd wisdom viral score.
    
    - viral_score > 70: Boost up to +10 points
    - viral_score < 30: Penalty up to -3 points
    - Otherwise: No adjustment
    
    Returns: Points to add/subtract from composite score
    """
    if not CROWD_WISDOM_CONFIG.get("enabled", False):
        return 0.0
    
    boost_threshold = CROWD_WISDOM_CONFIG["boost_threshold"]
    penalty_threshold = CROWD_WISDOM_CONFIG["penalty_threshold"]
    max_boost = CROWD_WISDOM_CONFIG["max_boost"]
    max_penalty = CROWD_WISDOM_CONFIG["max_penalty"]
    
    if viral_score >= boost_threshold:
        # Calculate boost proportional to how much above threshold
        excess = viral_score - boost_threshold
        max_excess = 100 - boost_threshold  # e.g., 30 points from 70 to 100
        boost = (excess / max_excess) * max_boost
        return min(boost, max_boost)
    
    elif viral_score > 0 and viral_score < penalty_threshold:
        # Calculate penalty proportional to how much below threshold
        # Only apply if stock is actually in crowd wisdom data (viral_score > 0)
        deficit = penalty_threshold - viral_score
        max_deficit = penalty_threshold  # e.g., 30 points from 30 to 0
        penalty = (deficit / max_deficit) * max_penalty
        return -min(penalty, max_penalty)
    
    return 0.0


def load_crowd_wisdom_scores() -> Dict[str, float]:
    """
    REC-263: Load current crowd wisdom viral scores from database.
    
    Returns: Dict mapping ticker -> viral_score
    """
    try:
        import sqlite3
        db_path = CACHE_DIR / "crowd_wisdom.db"
        if not db_path.exists():
            return {}
        
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Get latest scores from this week (from Reddit-based viral scores table)
        cursor.execute("""
            SELECT ticker, viral_score 
            FROM reddit_viral_scores 
            WHERE week_start = (SELECT MAX(week_start) FROM reddit_viral_scores)
            AND passes_filters = 1
        """)
        
        scores = {row[0].upper(): row[1] for row in cursor.fetchall()}
        conn.close()
        
        logger.info(f"Loaded {len(scores)} crowd wisdom scores")
        return scores
    except Exception as e:
        logger.warning(f"Failed to load crowd wisdom scores: {e}")
        return {}


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
    
    # REC-263: Load crowd wisdom scores for boost calculation
    crowd_wisdom_scores = load_crowd_wisdom_scores()
    cw_boost_count = 0
    cw_penalty_count = 0
    
    # Combine into composite scores
    logger.info("\nCombining scores...")
    
    # Apply relative scoring (Bayesian shrinkage + percentile ranking)
    if RELATIVE_SCORING_ENABLED:
        logger.info(f"Applying relative scoring (k={PRIOR_STRENGTH})...")
        
        # Transform each component to relative percentile scores
        f_relative = transform_fundamental_scores(fundamental_scores, k=PRIOR_STRENGTH)
        s_relative = transform_sentiment_scores(sentiment_scores, k=PRIOR_STRENGTH)
        t_relative = transform_technical_scores(technical_scores, k=PRIOR_STRENGTH)
        m_relative = transform_macro_scores(macro_scores, k=PRIOR_STRENGTH)
    else:
        # Fallback: use raw scores with mean imputation (old behavior)
        f_values = [s.total_score for s in fundamental_scores.values() if s and s.total_score is not None]
        s_values = [s.total_score for s in sentiment_scores.values() if s and s.total_score is not None]
        t_values = [s.total_score for s in technical_scores.values() if s and s.total_score is not None]
        m_values = [s.total_score for s in macro_scores.values() if s and s.total_score is not None]
        
        f_mean = np.mean(f_values) if f_values else 50.0
        s_mean = np.mean(s_values) if s_values else 50.0
        t_mean = np.mean(t_values) if t_values else 50.0
        m_mean = np.mean(m_values) if m_values else 50.0
        
        f_relative = {t: (s.total_score if s and s.total_score else f_mean) for t, s in fundamental_scores.items()}
        s_relative = {t: (s.total_score if s and s.total_score else s_mean) for t, s in sentiment_scores.items()}
        t_relative = {t: (s.total_score if s and s.total_score else t_mean) for t, s in technical_scores.items()}
        m_relative = {t: (s.total_score if s and s.total_score else m_mean) for t, s in macro_scores.items()}
    
    results = {}
    
    for ticker in tickers:
        ticker_upper = ticker.upper()
        
        # Get relative (percentile) scores for each component
        f_val = f_relative.get(ticker_upper, 50.0)
        s_val = s_relative.get(ticker_upper, 50.0)
        t_val = t_relative.get(ticker_upper, 50.0)
        m_val = m_relative.get(ticker_upper, 50.0)
        
        # Calculate weighted composite
        total_score = (
            f_val * WEIGHTS["fundamental"] +
            s_val * WEIGHTS["sentiment"] +
            t_val * WEIGHTS["technical"] +
            m_val * WEIGHTS["macro"]
        )
        
        # REC-263: Apply crowd wisdom boost/penalty
        cw_score = crowd_wisdom_scores.get(ticker_upper, 0)
        cw_adjustment = get_crowd_wisdom_boost(cw_score)
        if cw_adjustment > 0:
            cw_boost_count += 1
        elif cw_adjustment < 0:
            cw_penalty_count += 1
        total_score += cw_adjustment
        
        # CRITICAL FIX: Ensure score stays within 0-100 bounds after all adjustments
        total_score = max(0.0, min(100.0, total_score))
        
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
                "fundamental": fundamental_scores.get(ticker_upper, {}).details if fundamental_scores.get(ticker_upper) else {},
                "sentiment": sentiment_scores.get(ticker_upper, {}).details if sentiment_scores.get(ticker_upper) else {},
                "technical": technical_scores.get(ticker_upper, {}).details if technical_scores.get(ticker_upper) else {},
                "macro": macro_scores.get(ticker_upper, {}).details if macro_scores.get(ticker_upper) else {},
                "crowd_wisdom": {
                    "viral_score": cw_score,
                    "adjustment": round(cw_adjustment, 2),
                } if cw_score > 0 else {},
                "relative_scoring": RELATIVE_SCORING_ENABLED,
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
    if CROWD_WISDOM_CONFIG.get("enabled"):
        logger.info(f"Crowd Wisdom: {cw_boost_count} boosted | {cw_penalty_count} penalized")
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
    
    # F4.4: Load previous scores BEFORE overwriting (for alert comparison)
    old_scores = {}
    if path.exists():
        try:
            with open(path, 'r') as f:
                old_data = json.load(f)
                old_scores = old_data.get("scores", {})
        except Exception as e:
            logger.warning(f"Failed to load previous scores for alerts: {e}")
    
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
    
    # F5.5: Record to score history for charting
    try:
        from scoring.score_history import ScoreHistoryService
        recorded = ScoreHistoryService.record_pipeline_run(data.get("scores", {}))
        logger.info(f"Recorded {recorded} scores to history")
    except Exception as e:
        logger.warning(f"Failed to record score history: {e}")
    
    # F4.4: Generate alerts for score/signal changes
    try:
        from alerts import get_alert_manager
        alert_manager = get_alert_manager()
        
        new_scores = data.get("scores", {})
        
        if old_scores:
            # Check for score changes > 10 points
            score_alerts = alert_manager.check_score_changes(old_scores, new_scores, threshold=10)
            # Check for signal changes
            signal_alerts = alert_manager.check_signal_changes(old_scores, new_scores)
            
            total_alerts = len(score_alerts) + len(signal_alerts)
            if total_alerts > 0:
                logger.info(f"Generated {total_alerts} alerts ({len(score_alerts)} score, {len(signal_alerts)} signal)")
        else:
            logger.info("No previous scores to compare - skipping alert generation")
    except Exception as e:
        logger.warning(f"Failed to generate alerts: {e}")


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
