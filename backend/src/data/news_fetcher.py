"""
F1.4 News Fetcher

Fetches news headlines from multiple sources for sentiment analysis.

Sources (FREE):
- RSS Feeds: Yahoo Finance, Reuters, MarketWatch, SEC
- Alpha Vantage News API (requires free API key)
- Finnhub News API (requires free API key)
"""

import feedparser
import requests
import os
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from pathlib import Path
import json
import re
from loguru import logger
from concurrent.futures import ThreadPoolExecutor, as_completed
import time


# Cache directory
CACHE_DIR = Path(__file__).parent.parent.parent / "data"
NEWS_CACHE = CACHE_DIR / "news.json"

# API Keys (get free keys from alphavantage.co and finnhub.io)
ALPHA_VANTAGE_API_KEY = os.environ.get("ALPHA_VANTAGE_API_KEY", "")
FINNHUB_API_KEY = os.environ.get("FINNHUB_API_KEY", "")

# RSS Feed URLs (always free, no API key needed)
# Note: Reuters RSS and SEC EDGAR feeds removed (deprecated/broken as of Feb 2026)
NEWS_FEEDS = {
    "yahoo_finance": "https://finance.yahoo.com/news/rssindex",
    "marketwatch": "https://feeds.content.dowjones.io/public/rss/mw_topstories",
}

# User agent for requests
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
}

# Source tiers for weighting (per PRD)
SOURCE_TIERS = {
    # Tier 1 (3x weight) - Premium sources
    "wsj": 3, "ft": 3, "economist": 3,
    # Tier 2 (2x weight) - Quality sources
    "bloomberg": 2, "finnhub": 2, "alpha_vantage": 2,
    # Tier 3 (1x weight) - General sources
    "yahoo_finance": 1, "marketwatch": 1,
}


def parse_date(date_str: str) -> Optional[datetime]:
    """Parse date from various RSS formats."""
    formats = [
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S",
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except:
            continue
    
    return None


def fetch_feed(source: str, url: str, hours: int = 168) -> List[Dict]:
    """
    Fetch and parse a single RSS feed.
    
    Args:
        source: Source name
        url: RSS feed URL
        hours: Only return articles from last N hours (default 7 days)
    
    Returns:
        List of article dicts
    """
    try:
        # Fetch feed with custom headers
        response = requests.get(url, headers=HEADERS, timeout=10)
        feed = feedparser.parse(response.content)
        
        if feed.bozo and not feed.entries:
            logger.warning(f"Failed to parse {source}: {feed.bozo_exception}")
            return []
        
        cutoff = datetime.now() - timedelta(hours=hours)
        articles = []
        
        for entry in feed.entries:
            # Parse publish date
            pub_date = None
            for date_field in ["published", "updated", "created"]:
                if hasattr(entry, date_field) and getattr(entry, date_field):
                    pub_date = parse_date(getattr(entry, date_field))
                    if pub_date:
                        break
            
            # Skip old articles
            if pub_date and pub_date.replace(tzinfo=None) < cutoff:
                continue
            
            # Extract article data
            article = {
                "source": source,
                "title": entry.get("title", "").strip(),
                "summary": entry.get("summary", "")[:500].strip(),
                "link": entry.get("link", ""),
                "published": pub_date.isoformat() if pub_date else None,
                "fetched_at": datetime.now().isoformat(),
            }
            
            if article["title"]:
                articles.append(article)
        
        logger.debug(f"Fetched {len(articles)} articles from {source}")
        return articles
        
    except Exception as e:
        logger.error(f"Failed to fetch {source}: {e}")
        return []


def fetch_finnhub_news(ticker: str = None, hours: int = 168) -> List[Dict]:
    """
    Fetch news from Finnhub API.
    
    Args:
        ticker: Optional ticker to filter news (None = general market news)
        hours: Look back period
    
    Returns:
        List of article dicts
    
    Docs: https://finnhub.io/docs/api/market-news
    """
    if not FINNHUB_API_KEY:
        logger.debug("Finnhub API key not set, skipping")
        return []
    
    try:
        cutoff = datetime.now() - timedelta(hours=hours)
        
        if ticker:
            # Company-specific news
            url = f"https://finnhub.io/api/v1/company-news"
            params = {
                "symbol": ticker.upper(),
                "from": cutoff.strftime("%Y-%m-%d"),
                "to": datetime.now().strftime("%Y-%m-%d"),
                "token": FINNHUB_API_KEY,
            }
        else:
            # General market news
            url = "https://finnhub.io/api/v1/news"
            params = {
                "category": "general",
                "token": FINNHUB_API_KEY,
            }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        articles = []
        for item in data:
            # Parse timestamp (Unix epoch)
            pub_date = datetime.fromtimestamp(item.get("datetime", 0))
            
            if pub_date < cutoff:
                continue
            
            article = {
                "source": f"finnhub_{item.get('source', 'unknown')}",
                "title": item.get("headline", "").strip(),
                "summary": item.get("summary", "")[:500].strip(),
                "link": item.get("url", ""),
                "published": pub_date.isoformat(),
                "fetched_at": datetime.now().isoformat(),
                "ticker": ticker,
                "tier": 2,  # Tier 2 source
            }
            
            if article["title"]:
                articles.append(article)
        
        logger.info(f"Finnhub: {len(articles)} articles" + (f" for {ticker}" if ticker else ""))
        return articles
        
    except Exception as e:
        logger.error(f"Failed to fetch Finnhub news: {e}")
        return []


def fetch_alpha_vantage_news(tickers: List[str] = None, hours: int = 168) -> List[Dict]:
    """
    Fetch news from Alpha Vantage News API.
    
    Args:
        tickers: List of tickers to get news for (max 50 per call)
        hours: Look back period
    
    Returns:
        List of article dicts
    
    Docs: https://www.alphavantage.co/documentation/#news-sentiment
    """
    if not ALPHA_VANTAGE_API_KEY:
        logger.debug("Alpha Vantage API key not set, skipping")
        return []
    
    try:
        cutoff = datetime.now() - timedelta(hours=hours)
        
        url = "https://www.alphavantage.co/query"
        params = {
            "function": "NEWS_SENTIMENT",
            "apikey": ALPHA_VANTAGE_API_KEY,
            "limit": 200,  # Max per call
            "sort": "LATEST",
        }
        
        if tickers:
            # Limit to 50 tickers per API constraint
            params["tickers"] = ",".join(tickers[:50])
        
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        if "feed" not in data:
            logger.warning(f"Alpha Vantage unexpected response: {data.get('Note', data.get('Information', 'Unknown'))}")
            return []
        
        articles = []
        for item in data["feed"]:
            # Parse date (format: 20231215T120000)
            time_str = item.get("time_published", "")
            try:
                pub_date = datetime.strptime(time_str, "%Y%m%dT%H%M%S")
            except:
                pub_date = datetime.now()
            
            if pub_date < cutoff:
                continue
            
            # Extract ticker relevance
            ticker_sentiment = {}
            for ts in item.get("ticker_sentiment", []):
                ticker_sentiment[ts["ticker"]] = {
                    "relevance": float(ts.get("relevance_score", 0)),
                    "sentiment": float(ts.get("ticker_sentiment_score", 0)),
                }
            
            article = {
                "source": f"alphavantage_{item.get('source', 'unknown')}",
                "title": item.get("title", "").strip(),
                "summary": item.get("summary", "")[:500].strip(),
                "link": item.get("url", ""),
                "published": pub_date.isoformat(),
                "fetched_at": datetime.now().isoformat(),
                "overall_sentiment": float(item.get("overall_sentiment_score", 0)),
                "ticker_sentiment": ticker_sentiment,
                "tier": 2,  # Tier 2 source
            }
            
            if article["title"]:
                articles.append(article)
        
        logger.info(f"Alpha Vantage: {len(articles)} articles")
        return articles
        
    except Exception as e:
        logger.error(f"Failed to fetch Alpha Vantage news: {e}")
        return []


def fetch_all_news(hours: int = 168, tickers: List[str] = None, timeout: int = 60) -> List[Dict]:
    """
    Fetch news from all sources (RSS + APIs) with circuit breaker protection.
    
    Args:
        hours: Only return articles from last N hours (default 7 days)
        tickers: Optional list of tickers for API sources
        timeout: Overall timeout in seconds (default 60s) - circuit breaker
    
    Returns:
        List of all articles, sorted by date
    """
    sources_count = len(NEWS_FEEDS)
    if FINNHUB_API_KEY:
        sources_count += 1
    if ALPHA_VANTAGE_API_KEY:
        sources_count += 1
    
    logger.info(f"Fetching news from {sources_count} sources (last {hours}h, timeout {timeout}s)...")
    
    all_articles = []
    failed_count = 0
    start_time = time.time()
    
    # Circuit breaker: stop if too many failures or timeout exceeded
    MAX_FAILURES = 3
    
    # Fetch RSS feeds in parallel with timeout
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_source = {
            executor.submit(fetch_feed, source, url, hours): source
            for source, url in NEWS_FEEDS.items()
        }
        
        for future in as_completed(future_to_source, timeout=timeout):
            # Check circuit breaker conditions
            if failed_count >= MAX_FAILURES:
                logger.warning(f"Circuit breaker: stopping after {MAX_FAILURES} failures")
                break
            if time.time() - start_time > timeout:
                logger.warning(f"Circuit breaker: overall timeout ({timeout}s) exceeded")
                break
                
            source = future_to_source[future]
            try:
                articles = future.result(timeout=15)  # 15s per-source timeout
                all_articles.extend(articles)
                logger.info(f"  {source}: {len(articles)} articles")
            except Exception as e:
                failed_count += 1
                logger.error(f"  {source}: ERROR - {e}")
    
    # Fetch from Finnhub (if API key set)
    if FINNHUB_API_KEY:
        finnhub_articles = fetch_finnhub_news(ticker=None, hours=hours)
        all_articles.extend(finnhub_articles)
    
    # Fetch from Alpha Vantage (if API key set)
    if ALPHA_VANTAGE_API_KEY:
        av_articles = fetch_alpha_vantage_news(tickers=tickers, hours=hours)
        all_articles.extend(av_articles)
    
    # Sort by date (newest first)
    all_articles.sort(
        key=lambda x: x["published"] or "1970-01-01",
        reverse=True
    )
    
    logger.info(f"Total: {len(all_articles)} articles")
    return all_articles


def filter_by_ticker(articles: List[Dict], ticker: str) -> List[Dict]:
    """
    Filter articles that mention a specific ticker.
    
    Searches in title and summary for:
    - Exact ticker match (e.g., "AAPL")
    - Company name patterns
    """
    ticker_upper = ticker.upper()
    
    # Company name mappings — only use distinctive names (BUG-015 fix)
    # Avoid ambiguous words like "apple", "meta" that match non-financial context
    COMPANY_NAMES = {
        "AAPL": ["apple inc", "iphone", "ipad", "macbook", "app store"],
        "MSFT": ["microsoft", "azure", "xbox", "windows 11"],
        "GOOGL": ["alphabet inc", "google cloud", "youtube"],
        "GOOG": ["alphabet inc", "google cloud", "youtube"],
        "AMZN": ["amazon.com", "amazon web services", "aws"],
        "META": ["meta platforms", "facebook", "instagram", "whatsapp"],
        "TSLA": ["tesla inc", "tesla motors", "cybertruck"],
        "NVDA": ["nvidia", "geforce", "cuda"],
        "JPM": ["jpmorgan", "jp morgan", "jamie dimon"],
        "V": ["visa inc", "visa network"],
        "MA": ["mastercard"],
    }
    
    # Financial context words — article must mention at least one to qualify via keyword match
    FINANCIAL_CONTEXT = {"stock", "share", "revenue", "earnings", "profit", "market", "investor",
                         "analyst", "quarterly", "dividend", "ipo", "valuation", "ceo", "cfo",
                         "trading", "nasdaq", "nyse", "s&p", "wall street", "sec filing"}
    
    keywords = [ticker_upper]
    if ticker_upper in COMPANY_NAMES:
        keywords.extend(COMPANY_NAMES[ticker_upper])
    
    filtered = []
    for article in articles:
        text = (article["title"] + " " + article["summary"]).lower()
        
        # Check for ticker (with word boundaries) — always trust exact ticker matches
        if re.search(rf'\b{ticker_upper}\b', article["title"] + " " + article["summary"], re.IGNORECASE):
            filtered.append(article)
            continue
        
        # Check for company keywords — require financial context to reduce false positives
        has_financial_context = any(ctx in text for ctx in FINANCIAL_CONTEXT)
        if has_financial_context:
            for keyword in keywords[1:]:  # Skip ticker itself
                if keyword.lower() in text:
                    filtered.append(article)
                    break
    
    return filtered


def fetch_news_for_ticker(ticker: str, hours: int = 168) -> List[Dict]:
    """
    Fetch news mentioning a specific stock.
    
    Uses:
    - RSS feeds (filtered by ticker mention)
    - Finnhub company news (if API key set)
    - Alpha Vantage news (if API key set)
    
    Args:
        ticker: Stock ticker symbol
        hours: Look back period in hours
    
    Returns:
        List of relevant articles, deduplicated
    """
    all_articles = []
    
    # Get RSS news and filter
    rss_news = fetch_all_news(hours=hours, tickers=[ticker])
    rss_filtered = filter_by_ticker(rss_news, ticker)
    all_articles.extend(rss_filtered)
    
    # Get Finnhub company-specific news (if available)
    if FINNHUB_API_KEY:
        finnhub_news = fetch_finnhub_news(ticker=ticker, hours=hours)
        all_articles.extend(finnhub_news)
    
    # Deduplicate by title similarity
    seen_titles = set()
    unique_articles = []
    for article in all_articles:
        # Normalize title for comparison
        title_key = article["title"].lower()[:50]
        if title_key not in seen_titles:
            seen_titles.add(title_key)
            unique_articles.append(article)
    
    # Sort by date
    unique_articles.sort(
        key=lambda x: x["published"] or "1970-01-01",
        reverse=True
    )
    
    return unique_articles


def save_news(articles: List[Dict], path: Path = NEWS_CACHE) -> None:
    """Save news to JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    
    data = {
        "updated_at": datetime.now().isoformat(),
        "count": len(articles),
        "articles": articles
    }
    
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)
    
    logger.info(f"Saved {len(articles)} articles to {path}")


def load_news(path: Path = NEWS_CACHE) -> Optional[Dict]:
    """Load news from JSON file."""
    if not path.exists():
        return None
    
    with open(path, 'r') as f:
        return json.load(f)


def get_news_summary(ticker: str = None) -> Dict:
    """
    Get news summary, optionally filtered by ticker.
    """
    cached = load_news()
    
    if cached is None:
        articles = fetch_all_news()
        save_news(articles)
    else:
        articles = cached["articles"]
    
    if ticker:
        articles = filter_by_ticker(articles, ticker)
    
    return {
        "count": len(articles),
        "articles": articles[:50],  # Limit response size
    }


# Simple keyword-based sentiment (MVP)
POSITIVE_WORDS = [
    "surge", "soar", "jump", "gain", "rise", "beat", "exceed", "profit",
    "growth", "record", "strong", "bullish", "upgrade", "buy", "outperform",
    "positive", "boost", "rally", "breakthrough", "success", "wins"
]

NEGATIVE_WORDS = [
    "fall", "drop", "plunge", "crash", "decline", "miss", "loss", "weak",
    "bearish", "downgrade", "sell", "underperform", "negative", "cut",
    "layoff", "lawsuit", "investigation", "fraud", "warning", "concern"
]


def analyze_sentiment(text: str) -> Dict:
    """
    Simple keyword-based sentiment analysis.
    
    Returns:
        Dict with sentiment score (-1 to 1), label, and word counts
    """
    text_lower = text.lower()
    
    positive_count = sum(1 for word in POSITIVE_WORDS if word in text_lower)
    negative_count = sum(1 for word in NEGATIVE_WORDS if word in text_lower)
    
    total = positive_count + negative_count
    
    if total == 0:
        score = 0.0
        label = "neutral"
    else:
        score = (positive_count - negative_count) / total
        if score > 0.2:
            label = "positive"
        elif score < -0.2:
            label = "negative"
        else:
            label = "neutral"
    
    return {
        "score": round(score, 3),
        "label": label,
        "positive_words": positive_count,
        "negative_words": negative_count,
    }


def analyze_news_sentiment(articles: List[Dict]) -> Dict:
    """
    Analyze sentiment for a list of articles.
    
    Returns:
        Aggregated sentiment metrics
    """
    if not articles:
        return {
            "score": 0,
            "label": "neutral",
            "article_count": 0,
            "positive_count": 0,
            "negative_count": 0,
            "neutral_count": 0,
        }
    
    sentiments = [analyze_sentiment(a["title"] + " " + a["summary"]) for a in articles]
    
    avg_score = sum(s["score"] for s in sentiments) / len(sentiments)
    
    positive_count = sum(1 for s in sentiments if s["label"] == "positive")
    negative_count = sum(1 for s in sentiments if s["label"] == "negative")
    neutral_count = sum(1 for s in sentiments if s["label"] == "neutral")
    
    if avg_score > 0.1:
        label = "positive"
    elif avg_score < -0.1:
        label = "negative"
    else:
        label = "neutral"
    
    return {
        "score": round(avg_score, 3),
        "label": label,
        "article_count": len(articles),
        "positive_count": positive_count,
        "negative_count": negative_count,
        "neutral_count": neutral_count,
    }


# CLI for testing
if __name__ == "__main__":
    import sys
    logger.add(sys.stderr, level="INFO")
    
    print("\n=== News Fetcher Test ===\n")
    
    # Fetch all news
    print("Fetching news from all sources...")
    articles = fetch_all_news(hours=72)  # Last 3 days
    
    print(f"\nTotal articles: {len(articles)}")
    print("\nLatest 5 headlines:")
    for a in articles[:5]:
        print(f"  [{a['source']}] {a['title'][:70]}...")
    
    # Filter for AAPL
    print("\n--- AAPL News ---")
    aapl_news = filter_by_ticker(articles, "AAPL")
    print(f"Found {len(aapl_news)} articles about AAPL")
    for a in aapl_news[:3]:
        print(f"  {a['title'][:70]}...")
    
    # Sentiment analysis
    if aapl_news:
        sentiment = analyze_news_sentiment(aapl_news)
        print(f"\nAAPL Sentiment: {sentiment['label']} ({sentiment['score']:.2f})")
    
    print("\n✅ News fetcher working!")
