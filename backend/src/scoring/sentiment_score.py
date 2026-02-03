"""
F2.2 Sentiment Score

Score stocks 0-100 based on news sentiment.
Method: Keyword-based (MVP), FinBERT (Phase 6)
Weighted by recency and source tier.
"""

import numpy as np
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from pathlib import Path
import json
import math
from loguru import logger
from dataclasses import dataclass

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from data.news_fetcher import (
    fetch_all_news, 
    fetch_news_for_ticker, 
    analyze_sentiment,
    load_news,
    SOURCE_TIERS
)
from data.stock_universe import get_universe


# Cache directory
CACHE_DIR = Path(__file__).parent.parent.parent / "data"
SENTIMENT_CACHE = CACHE_DIR / "sentiment_scores.json"

# Config flag for sentiment model (change to "finbert" in Phase 6)
SENTIMENT_MODEL = "keyword"


@dataclass
class SentimentScoreResult:
    """Result of sentiment score calculation."""
    ticker: str
    total_score: float  # 0-100
    raw_sentiment: float  # -1 to 1
    article_count: int
    positive_count: int
    negative_count: int
    neutral_count: int
    weighted_sentiment: float  # After recency/tier weighting
    details: Dict


def calculate_recency_weight(published_date: str, max_days: int = 7) -> float:
    """
    Calculate recency weight (0-1) where newer = higher weight.
    
    Decay function: weight = exp(-days / half_life)
    Half-life of ~2 days means 2-day-old news has ~50% weight.
    """
    if not published_date:
        return 0.5
    
    try:
        pub_dt = datetime.fromisoformat(published_date.replace('Z', '+00:00'))
        if pub_dt.tzinfo:
            pub_dt = pub_dt.replace(tzinfo=None)
        
        age_days = (datetime.now() - pub_dt).total_seconds() / 86400
        
        # Exponential decay with half-life of 2 days
        half_life = 2.0
        weight = math.exp(-age_days * math.log(2) / half_life)
        
        return max(0.1, min(1.0, weight))
        
    except Exception:
        return 0.5


def get_source_tier_weight(source: str) -> float:
    """
    Get tier weight for a source (1-3).
    """
    # Extract base source name (e.g., "finnhub_reuters" -> "finnhub")
    source_lower = source.lower()
    
    for tier_source, weight in SOURCE_TIERS.items():
        if tier_source in source_lower:
            return weight
    
    return 1  # Default tier 3


def calculate_sentiment_score_for_ticker(
    ticker: str,
    articles: List[Dict] = None,
    hours: int = 168
) -> SentimentScoreResult:
    """
    Calculate sentiment score for a single stock.
    
    Args:
        ticker: Stock ticker
        articles: Pre-fetched articles (if None, fetches fresh)
        hours: Look back period
    
    Returns:
        SentimentScoreResult
    """
    if articles is None:
        articles = fetch_news_for_ticker(ticker, hours=hours)
    
    if not articles:
        return SentimentScoreResult(
            ticker=ticker,
            total_score=50.0,  # Neutral when no news
            raw_sentiment=0.0,
            article_count=0,
            positive_count=0,
            negative_count=0,
            neutral_count=0,
            weighted_sentiment=0.0,
            details={"message": "No news found"}
        )
    
    # Analyze each article
    weighted_scores = []
    total_weight = 0
    positive_count = 0
    negative_count = 0
    neutral_count = 0
    
    article_details = []
    
    for article in articles:
        # Get sentiment
        sentiment = analyze_sentiment(article["title"] + " " + article.get("summary", ""))
        
        # Apply Alpha Vantage sentiment if available (more accurate)
        if "overall_sentiment" in article:
            sentiment["score"] = article["overall_sentiment"]
            sentiment["label"] = "positive" if sentiment["score"] > 0.1 else ("negative" if sentiment["score"] < -0.1 else "neutral")
        
        # Calculate weights
        recency_weight = calculate_recency_weight(article.get("published"))
        tier_weight = get_source_tier_weight(article.get("source", ""))
        combined_weight = recency_weight * tier_weight
        
        # Add to weighted sum
        weighted_scores.append(sentiment["score"] * combined_weight)
        total_weight += combined_weight
        
        # Count by label
        if sentiment["label"] == "positive":
            positive_count += 1
        elif sentiment["label"] == "negative":
            negative_count += 1
        else:
            neutral_count += 1
        
        article_details.append({
            "title": article["title"][:100],
            "source": article.get("source"),
            "sentiment": sentiment["label"],
            "score": sentiment["score"],
            "weight": round(combined_weight, 2),
        })
    
    # Calculate weighted average sentiment (-1 to 1)
    if total_weight > 0:
        weighted_sentiment = sum(weighted_scores) / total_weight
    else:
        weighted_sentiment = 0.0
    
    # Raw (unweighted) average
    raw_sentiment = sum(analyze_sentiment(a["title"])["score"] for a in articles) / len(articles)
    
    # Convert to 0-100 score
    # -1 -> 0, 0 -> 50, 1 -> 100
    total_score = (weighted_sentiment + 1) * 50
    total_score = max(0, min(100, total_score))
    
    return SentimentScoreResult(
        ticker=ticker,
        total_score=round(total_score, 2),
        raw_sentiment=round(raw_sentiment, 3),
        article_count=len(articles),
        positive_count=positive_count,
        negative_count=negative_count,
        neutral_count=neutral_count,
        weighted_sentiment=round(weighted_sentiment, 3),
        details={
            "model": SENTIMENT_MODEL,
            "hours_lookback": hours,
            "top_articles": article_details[:5],
        }
    )


def calculate_sentiment_scores(
    tickers: List[str] = None,
    hours: int = 168
) -> Dict[str, SentimentScoreResult]:
    """
    Calculate sentiment scores for all stocks.
    
    Args:
        tickers: List of tickers (if None, uses universe)
        hours: Look back period
    
    Returns:
        Dict mapping ticker to SentimentScoreResult
    """
    if tickers is None:
        universe = get_universe()
        tickers = [s["ticker"] for s in universe]
    
    logger.info(f"Calculating sentiment scores for {len(tickers)} stocks...")
    
    # Fetch all news once
    all_news = fetch_all_news(hours=hours)
    
    results = {}
    for ticker in tickers:
        # Filter news for this ticker
        ticker_news = [a for a in all_news if _article_mentions_ticker(a, ticker)]
        
        result = calculate_sentiment_score_for_ticker(
            ticker=ticker,
            articles=ticker_news,
            hours=hours
        )
        results[ticker] = result
        
        if result.article_count > 0:
            logger.debug(f"  {ticker}: {result.total_score:.1f} ({result.article_count} articles)")
    
    # Log summary
    with_news = sum(1 for r in results.values() if r.article_count > 0)
    logger.info(f"Calculated sentiment for {len(results)} stocks ({with_news} with news)")
    
    return results


def _article_mentions_ticker(article: Dict, ticker: str) -> bool:
    """Check if article mentions ticker (simple heuristic)."""
    ticker_upper = ticker.upper()
    text = (article.get("title", "") + " " + article.get("summary", "")).upper()
    
    # Check ticker
    if f" {ticker_upper} " in f" {text} " or f"({ticker_upper})" in text:
        return True
    
    # Check ticker-specific sentiment from Alpha Vantage
    if "ticker_sentiment" in article and ticker_upper in article["ticker_sentiment"]:
        return True
    
    return False


def get_sentiment_score(ticker: str) -> Optional[SentimentScoreResult]:
    """Get sentiment score for a single stock."""
    return calculate_sentiment_score_for_ticker(ticker)


def save_sentiment_scores(scores: Dict[str, SentimentScoreResult], path: Path = SENTIMENT_CACHE) -> None:
    """Save scores to JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    
    data = {
        "updated_at": datetime.now().isoformat(),
        "count": len(scores),
        "model": SENTIMENT_MODEL,
        "scores": {
            ticker: {
                "ticker": r.ticker,
                "total_score": r.total_score,
                "raw_sentiment": r.raw_sentiment,
                "article_count": r.article_count,
                "positive_count": r.positive_count,
                "negative_count": r.negative_count,
                "neutral_count": r.neutral_count,
                "weighted_sentiment": r.weighted_sentiment,
            }
            for ticker, r in scores.items()
        }
    }
    
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)
    
    logger.info(f"Saved sentiment scores to {path}")


def load_sentiment_scores(path: Path = SENTIMENT_CACHE) -> Optional[Dict]:
    """Load scores from JSON."""
    if not path.exists():
        return None
    
    with open(path, 'r') as f:
        return json.load(f)


# CLI for testing
if __name__ == "__main__":
    import sys
    logger.add(sys.stderr, level="INFO")
    
    print("\n=== Sentiment Score Test ===\n")
    
    # Test single stock
    print("Calculating AAPL sentiment...")
    aapl = calculate_sentiment_score_for_ticker("AAPL")
    print(f"  Score: {aapl.total_score:.1f}/100")
    print(f"  Articles: {aapl.article_count}")
    print(f"  Breakdown: +{aapl.positive_count} / {aapl.neutral_count} / -{aapl.negative_count}")
    print(f"  Weighted sentiment: {aapl.weighted_sentiment:.3f}")
    
    # Test a few more
    print("\nSample stocks:")
    for ticker in ["MSFT", "TSLA", "NVDA"]:
        result = calculate_sentiment_score_for_ticker(ticker)
        print(f"  {ticker}: {result.total_score:.1f} ({result.article_count} articles)")
    
    print("\n✅ Sentiment scoring working!")
