"""
F2.2 Sentiment Score

Score stocks 0-100 based on news sentiment.
Method: Keyword-based (MVP), LLM/Agentic (REC-170+)
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

# Import config (REC-171) and agentic analyzer (REC-172)
from .sentiment_config import get_sentiment_config, SentimentModel

# Import article processor (REC-173)
from .article_processor import ArticleProcessor, ProcessedArticle

# Import fallback manager (REC-175)
from .sentiment_fallback import get_fallback_manager

# Lazy import to avoid circular dependency
_agentic_analyzer = None

# Singleton article processor
_article_processor = None

def _get_article_processor() -> ArticleProcessor:
    """Lazy-load the article processor."""
    global _article_processor
    if _article_processor is None:
        config = get_sentiment_config()
        _article_processor = ArticleProcessor(
            max_articles_per_ticker=config.max_articles_per_stock,
            max_content_length=300,
            min_content_length=20,
        )
    return _article_processor

def _get_agentic_analyzer():
    """Lazy-load the agentic sentiment analyzer."""
    global _agentic_analyzer
    if _agentic_analyzer is None:
        from .agentic_sentiment import AgenticSentimentAnalyzer
        _agentic_analyzer = AgenticSentimentAnalyzer()
    return _agentic_analyzer


# Cache directory
CACHE_DIR = Path(__file__).parent.parent.parent / "data"
SENTIMENT_CACHE = CACHE_DIR / "sentiment_scores.json"

# Legacy constant for backward compatibility
SENTIMENT_MODEL = "keyword"  # Actual model read from config at runtime


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
    
    Uses LLM analysis if SENTIMENT_MODEL=llm or hybrid, otherwise keyword-based.
    
    Args:
        ticker: Stock ticker
        articles: Pre-fetched articles (if None, fetches fresh)
        hours: Look back period
    
    Returns:
        SentimentScoreResult
    """
    config = get_sentiment_config()
    
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
            details={"message": "No news found", "model": "none"}
        )
    
    # REC-175: Get fallback manager for tracking
    fallback_mgr = get_fallback_manager()
    
    # Try LLM analysis if configured (REC-174)
    if config.model in (SentimentModel.LLM, SentimentModel.HYBRID):
        try:
            result = _analyze_with_llm(ticker, articles)
            if result is not None:
                # REC-175: Track LLM success (includes cache hits via analyzer)
                fallback_mgr.record_llm_call()
                return result
            # Fall through to keyword if LLM returns None
            if config.model == SentimentModel.LLM:
                logger.warning(f"LLM analysis failed for {ticker}, returning neutral")
                fallback_mgr.record_neutral_fallback()  # REC-175
                return SentimentScoreResult(
                    ticker=ticker,
                    total_score=50.0,
                    raw_sentiment=0.0,
                    article_count=len(articles),
                    positive_count=0,
                    negative_count=0,
                    neutral_count=len(articles),
                    weighted_sentiment=0.0,
                    details={"message": "LLM analysis failed", "model": "llm_failed"}
                )
        except Exception as e:
            logger.warning(f"LLM analysis error for {ticker}: {e}")
            if config.model == SentimentModel.LLM:
                # Pure LLM mode - don't fall back
                fallback_mgr.record_neutral_fallback()  # REC-175
                return SentimentScoreResult(
                    ticker=ticker,
                    total_score=50.0,
                    raw_sentiment=0.0,
                    article_count=len(articles),
                    positive_count=0,
                    negative_count=0,
                    neutral_count=len(articles),
                    weighted_sentiment=0.0,
                    details={"message": f"LLM error: {str(e)}", "model": "llm_error"}
                )
            # Hybrid mode - fall through to keyword
    
    # Keyword-based analysis (original method)
    # REC-175: Track keyword fallback
    if config.model in (SentimentModel.LLM, SentimentModel.HYBRID):
        fallback_mgr.record_keyword_fallback()
    
    return _analyze_with_keywords(ticker, articles, hours)


def _analyze_with_llm(ticker: str, articles: List[Dict]) -> Optional[SentimentScoreResult]:
    """
    Analyze sentiment using Claude LLM (REC-172/174).
    
    Pipeline (REC-173):
    1. Process articles: clean boilerplate, score quality/relevance
    2. Batch top N articles by quality
    3. Send to LLM for analysis
    
    Returns:
        SentimentScoreResult or None if analysis fails
    """
    try:
        analyzer = _get_agentic_analyzer()
        
        if not analyzer.is_available:
            logger.debug(f"LLM not available for {ticker}")
            return None
        
        # REC-173: Process and clean articles before LLM analysis
        processor = _get_article_processor()
        processed = processor.process_articles(ticker, articles)
        
        if not processed:
            logger.debug(f"No articles after processing for {ticker}")
            return None
        
        # Convert ProcessedArticle back to dict format for analyzer
        cleaned_articles = [
            {
                "title": p.headline,
                "summary": p.content,
                "source": p.source,
                "published": p.published,
                "_quality_score": p.quality_score,
                "_relevance_score": p.relevance_score,
            }
            for p in processed
        ]
        
        logger.debug(f"Processed {len(articles)} → {len(cleaned_articles)} articles for {ticker}")
        
        # Run LLM analysis with cleaned articles
        agent_result = analyzer.analyze(ticker, cleaned_articles)
        
        # Convert AgentSentimentResult to SentimentScoreResult
        # Count positive/negative/neutral from article analyses
        positive_count = sum(
            1 for a in agent_result.article_analyses 
            if a.score >= 55
        )
        negative_count = sum(
            1 for a in agent_result.article_analyses 
            if a.score <= 45
        )
        neutral_count = len(agent_result.article_analyses) - positive_count - negative_count
        
        # Convert 0-100 score to -1 to +1 for raw_sentiment
        raw_sentiment = (agent_result.overall_score / 50.0) - 1.0
        
        return SentimentScoreResult(
            ticker=ticker,
            total_score=round(agent_result.overall_score, 2),
            raw_sentiment=round(raw_sentiment, 3),
            article_count=len(articles),
            positive_count=positive_count,
            negative_count=negative_count,
            neutral_count=neutral_count,
            weighted_sentiment=round(raw_sentiment, 3),
            details={
                "model": "llm",
                "llm_model": agent_result.model_used,
                "confidence": agent_result.confidence,
                "rationale": agent_result.rationale,
                "bullish_factors": agent_result.bullish_factors,
                "bearish_factors": agent_result.bearish_factors,
                "sentiment_label": agent_result.overall_sentiment.value,
            }
        )
        
    except Exception as e:
        logger.error(f"LLM analysis failed for {ticker}: {e}")
        return None


def _analyze_with_keywords(ticker: str, articles: List[Dict], hours: int) -> SentimentScoreResult:
    """
    Analyze sentiment using keyword matching (original method).
    """
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
            "model": "keyword",
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
    
    Uses a two-pass approach:
    1. Match articles directly to tickers (ticker symbol + company name)
    2. For stocks with no direct matches, use sector-level sentiment as fallback
    
    Args:
        tickers: List of tickers (if None, uses universe)
        hours: Look back period
    
    Returns:
        Dict mapping ticker to SentimentScoreResult
    """
    universe = get_universe()
    
    if tickers is None:
        tickers = [s["ticker"] for s in universe]
    
    # Build ticker -> sector map
    ticker_sectors = {s["ticker"].upper(): s["sector"] for s in universe}
    
    logger.info(f"Calculating sentiment scores for {len(tickers)} stocks...")
    
    # Fetch all news once
    all_news = fetch_all_news(hours=hours)
    
    # Pass 1: Direct ticker matching
    results = {}
    no_news_tickers = []
    
    for ticker in tickers:
        # Filter news for this ticker (now uses company name matching too)
        ticker_news = [a for a in all_news if _article_mentions_ticker(a, ticker)]
        
        result = calculate_sentiment_score_for_ticker(
            ticker=ticker,
            articles=ticker_news,
            hours=hours
        )
        results[ticker] = result
        
        if result.article_count > 0:
            logger.debug(f"  {ticker}: {result.total_score:.1f} ({result.article_count} articles)")
        else:
            no_news_tickers.append(ticker)
    
    # Pass 2: Sector-level sentiment fallback for stocks without direct news
    if no_news_tickers:
        # Calculate sector sentiments
        sector_sentiments: Dict[str, float] = {}
        sectors_needed = {ticker_sectors.get(t.upper(), "Unknown") for t in no_news_tickers}
        
        for sector in sectors_needed:
            sector_sentiments[sector] = _calculate_sector_sentiment(all_news, sector, universe)
        
        # Apply sector sentiment as fallback
        for ticker in no_news_tickers:
            sector = ticker_sectors.get(ticker.upper(), "Unknown")
            sector_score = sector_sentiments.get(sector, 50.0)
            
            if sector_score != 50.0:
                results[ticker] = SentimentScoreResult(
                    ticker=ticker,
                    total_score=round(sector_score, 2),
                    raw_sentiment=round((sector_score / 50.0) - 1.0, 3),
                    article_count=0,
                    positive_count=0,
                    negative_count=0,
                    neutral_count=0,
                    weighted_sentiment=round((sector_score / 50.0) - 1.0, 3),
                    details={"message": f"Sector-level sentiment ({sector})", "model": SENTIMENT_MODEL}
                )
    
    # Log summary
    with_news = sum(1 for r in results.values() if r.article_count > 0)
    with_sector = sum(1 for r in results.values() if r.article_count == 0 and r.total_score != 50.0)
    at_neutral = sum(1 for r in results.values() if r.total_score == 50.0)
    logger.info(f"Calculated sentiment for {len(results)} stocks "
                f"({with_news} direct, {with_sector} sector-fallback, {at_neutral} neutral)")
    
    return results


def _build_company_name_map() -> Dict[str, List[str]]:
    """
    Build a mapping of ticker -> searchable company name keywords.
    Uses the stock universe data for comprehensive coverage.
    """
    # Static map for top/tricky tickers where company name alone isn't enough
    EXTRA_KEYWORDS = {
        "AAPL": ["apple", "iphone", "ipad", "mac", "app store"],
        "MSFT": ["microsoft", "windows", "azure", "xbox", "office 365"],
        "GOOGL": ["google", "alphabet", "youtube", "android", "waymo"],
        "GOOG": ["google", "alphabet", "youtube", "android"],
        "AMZN": ["amazon", "aws", "prime video", "alexa"],
        "META": ["meta platforms", "facebook", "instagram", "whatsapp", "threads"],
        "TSLA": ["tesla", "elon musk", "cybertruck", "supercharger"],
        "NVDA": ["nvidia", "geforce", "cuda", "gpu"],
        "JPM": ["jpmorgan", "jp morgan", "jamie dimon", "chase"],
        "V": ["visa"],
        "MA": ["mastercard"],
        "BRK-B": ["berkshire", "warren buffett"],
        "JNJ": ["johnson & johnson", "j&j"],
        "WMT": ["walmart"],
        "PG": ["procter & gamble", "procter and gamble"],
        "UNH": ["unitedhealth"],
        "HD": ["home depot"],
        "DIS": ["disney", "marvel", "pixar"],
        "CRM": ["salesforce"],
        "NFLX": ["netflix"],
        "ADBE": ["adobe"],
        "INTC": ["intel"],
        "AMD": ["advanced micro devices"],
        "PYPL": ["paypal"],
        "COST": ["costco"],
        "PEP": ["pepsi", "pepsico"],
        "KO": ["coca-cola", "coca cola", "coke"],
        "MRK": ["merck"],
        "LLY": ["eli lilly", "lilly"],
        "ABBV": ["abbvie"],
        "TMO": ["thermo fisher"],
        "AVGO": ["broadcom"],
        "ORCL": ["oracle"],
        "CSCO": ["cisco"],
        "ACN": ["accenture"],
        "TXN": ["texas instruments"],
        "QCOM": ["qualcomm"],
        "IBM": ["ibm"],
        "NOW": ["servicenow"],
        "GS": ["goldman sachs"],
        "MS": ["morgan stanley"],
        "BA": ["boeing"],
        "GE": ["general electric"],
        "GM": ["general motors"],
        "F": ["ford motor"],
        "CAT": ["caterpillar"],
        "CVX": ["chevron"],
        "XOM": ["exxon", "exxonmobil"],
        "COP": ["conocophillips"],
    }
    
    # Build from universe
    name_map: Dict[str, List[str]] = {}
    try:
        universe = get_universe()
        for stock in universe:
            ticker = stock["ticker"].upper()
            keywords = []
            
            # Add company name (split into meaningful parts)
            name = stock.get("name", "")
            if name:
                # Full name as keyword
                name_lower = name.lower()
                # Remove common suffixes for matching
                for suffix in [" inc.", " inc", " corp.", " corp", " corporation",
                             " co.", " co", " ltd.", " ltd", " plc", " group",
                             " holdings", " enterprises", " technologies",
                             " international", " company", " companies",
                             " & co", " n.v.", " s.a.", " se", " ag"]:
                    name_lower = name_lower.replace(suffix, "")
                name_lower = name_lower.strip()
                if len(name_lower) > 2:  # Skip very short names to avoid false positives
                    keywords.append(name_lower)
            
            # Add extra keywords if available
            if ticker in EXTRA_KEYWORDS:
                keywords.extend(EXTRA_KEYWORDS[ticker])
            
            if keywords:
                name_map[ticker] = keywords
    except Exception as e:
        logger.warning(f"Failed to build company name map from universe: {e}")
    
    # Merge in extras that might not be in universe
    for ticker, kws in EXTRA_KEYWORDS.items():
        if ticker not in name_map:
            name_map[ticker] = kws
        else:
            for kw in kws:
                if kw not in name_map[ticker]:
                    name_map[ticker].append(kw)
    
    return name_map


# Build the map once at module level
_COMPANY_NAME_MAP: Dict[str, List[str]] = {}


def _get_company_name_map() -> Dict[str, List[str]]:
    """Lazy-load the company name map."""
    global _COMPANY_NAME_MAP
    if not _COMPANY_NAME_MAP:
        _COMPANY_NAME_MAP = _build_company_name_map()
    return _COMPANY_NAME_MAP


def _article_mentions_ticker(article: Dict, ticker: str) -> bool:
    """Check if article mentions ticker using ticker symbol + company name matching."""
    ticker_upper = ticker.upper()
    text = (article.get("title", "") + " " + article.get("summary", "")).upper()
    
    # Check ticker symbol (with word boundaries)
    if f" {ticker_upper} " in f" {text} " or f"({ticker_upper})" in text:
        return True
    
    # Check ticker-specific sentiment from Alpha Vantage
    if "ticker_sentiment" in article and ticker_upper in article["ticker_sentiment"]:
        return True
    
    # Check company name keywords
    name_map = _get_company_name_map()
    keywords = name_map.get(ticker_upper, [])
    text_lower = (article.get("title", "") + " " + article.get("summary", "")).lower()
    
    for keyword in keywords:
        if keyword in text_lower:
            return True
    
    return False


def _calculate_sector_sentiment(
    all_news: List[Dict],
    sector: str,
    universe: List[Dict]
) -> float:
    """
    Calculate sector-level sentiment as a fallback for stocks without direct news.
    Aggregates sentiment from all articles matched to stocks in the same sector.
    
    Returns:
        Sentiment score 0-100 (50 = neutral)
    """
    # Get all tickers in this sector
    sector_tickers = {s["ticker"].upper() for s in universe if s.get("sector") == sector}
    
    if not sector_tickers:
        return 50.0
    
    # Find articles that match any ticker in this sector
    sector_articles = []
    for article in all_news:
        for ticker in sector_tickers:
            if _article_mentions_ticker(article, ticker):
                sector_articles.append(article)
                break  # Don't count same article multiple times
    
    if not sector_articles:
        return 50.0
    
    # Analyze sentiment of sector articles
    from data.news_fetcher import analyze_sentiment
    
    scores = []
    for article in sector_articles:
        sentiment = analyze_sentiment(article["title"] + " " + article.get("summary", ""))
        # Use Alpha Vantage sentiment if available
        if "overall_sentiment" in article:
            scores.append(article["overall_sentiment"])
        else:
            scores.append(sentiment["score"])
    
    avg_sentiment = sum(scores) / len(scores)  # -1 to 1
    
    # Convert to 0-100, but dampen the effect (sector sentiment is less specific)
    # Apply a 50% dampening factor
    dampened = avg_sentiment * 0.5
    sector_score = (dampened + 1) * 50
    return max(0, min(100, sector_score))



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
