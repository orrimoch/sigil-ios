"""
REC-266: Free Reddit Data Fetcher (No API Keys Required)

Fetches stock mentions from Reddit using 3 free, no-auth APIs:
1. ApeWisdom (primary) - Pre-aggregated trending tickers
2. Reddit JSON (secondary) - Real-time hot posts  
3. Arctic Shift (fallback) - Historical data

Uses FinVADER (finance-tuned VADER) for sentiment analysis.
"""

import re
import time
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set, Tuple
from dataclasses import dataclass, field
import aiohttp
import asyncio
from functools import lru_cache

logger = logging.getLogger(__name__)

# ============================================================================
# VADER Sentiment (finance-tuned)
# ============================================================================

try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    VADER_AVAILABLE = True
except ImportError:
    VADER_AVAILABLE = False
    logger.warning("vaderSentiment not installed. Run: pip install vaderSentiment")

# Finance-specific sentiment lexicon additions
FINANCE_LEXICON = {
    # Bullish terms
    "moon": 3.0, "mooning": 3.5, "rocket": 2.5, "rocketship": 3.0,
    "tendies": 2.0, "gains": 2.0, "gainz": 2.0, "bullish": 2.5,
    "calls": 1.5, "yolo": 1.0, "diamond": 2.0, "hodl": 1.5,
    "squeeze": 2.0, "breakout": 2.0, "undervalued": 2.0, "buy": 1.5,
    "long": 1.0, "accumulate": 1.5, "strong": 1.5, "growth": 1.5,
    "beat": 2.0, "beats": 2.0, "exceeded": 2.0, "soar": 2.5, "soaring": 2.5,
    "surge": 2.0, "surging": 2.0, "rally": 2.0, "rallying": 2.0,
    
    # Bearish terms
    "puts": -1.5, "bearish": -2.5, "crash": -3.0, "crashing": -3.0,
    "dump": -2.5, "dumping": -2.5, "bag": -1.5, "bagholder": -2.0,
    "loss": -2.0, "losses": -2.0, "red": -1.5, "bleeding": -2.5,
    "sell": -1.5, "short": -1.5, "overvalued": -2.0, "miss": -2.0,
    "missed": -2.0, "tank": -2.5, "tanking": -2.5, "drill": -2.0,
    "drilling": -2.0, "plunge": -2.5, "plunging": -2.5, "sink": -2.0,
    
    # Neutral/uncertain
    "hold": 0.5, "theta": 0.0, "iv": 0.0, "premium": 0.0,
}


def get_finance_vader():
    """Get VADER analyzer with finance-specific lexicon."""
    if not VADER_AVAILABLE:
        return None
    
    analyzer = SentimentIntensityAnalyzer()
    analyzer.lexicon.update(FINANCE_LEXICON)
    return analyzer


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class RedditTicker:
    """Aggregated Reddit data for a single ticker."""
    ticker: str
    name: str = ""
    mentions: int = 0
    upvotes: int = 0
    rank: int = 0
    rank_24h_ago: int = 0
    mentions_24h_ago: int = 0
    sentiment_score: float = 0.5  # 0=bearish, 0.5=neutral, 1=bullish
    sentiment_label: str = "neutral"
    trending_velocity: float = 0.0
    source: str = "apewisdom"
    sample_posts: List[Dict] = field(default_factory=list)
    fetched_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class CacheEntry:
    """Cache entry with TTL."""
    data: any
    expires_at: datetime


# ============================================================================
# Free Reddit Fetcher
# ============================================================================

class FreeRedditFetcher:
    """
    Fetches Reddit stock data using free, no-auth APIs.
    
    Data Sources (in priority order):
    1. ApeWisdom - Pre-aggregated trending tickers (15min cache)
    2. Reddit JSON - Real-time hot posts for sentiment (5min cache)
    3. Arctic Shift - Historical data fallback (1hr cache)
    """
    
    APEWISDOM_URL = "https://apewisdom.io/api/v1.0/filter/all-stocks"
    REDDIT_JSON_URL = "https://www.reddit.com/r/{subreddit}/hot.json"
    ARCTIC_SHIFT_URL = "https://arctic-shift.photon-reddit.com/api/posts"
    
    SUBREDDITS = ["wallstreetbets", "stocks", "investing"]
    
    # Cache TTLs
    APEWISDOM_TTL = timedelta(minutes=15)
    REDDIT_JSON_TTL = timedelta(minutes=5)
    ARCTIC_SHIFT_TTL = timedelta(hours=1)
    
    # Ticker validation pattern
    TICKER_PATTERN = re.compile(r'\$([A-Z]{1,5})\b|\b([A-Z]{2,5})\b')
    TICKER_EXCLUSIONS = {
        "A", "I", "DD", "CEO", "CFO", "IPO", "ETF", "USA", "GDP", "WSB",
        "YOLO", "FOMO", "ATH", "ATL", "IMO", "FYI", "AMA", "EPS", "TLDR",
        "EDIT", "LINK", "POST", "NOW", "GO", "NEW", "TOP", "ALL", "FOR",
        "THE", "AND", "ARE", "WAS", "HAS", "HAD", "NOT", "BUT", "CAN",
        "USD", "EUR", "GBP", "JPY", "PM", "AM", "EST", "PST", "UTC", "UK"
    }
    
    def __init__(self, valid_tickers: Optional[Set[str]] = None):
        """
        Initialize fetcher.
        
        Args:
            valid_tickers: Set of valid ticker symbols to filter against
        """
        self._cache: Dict[str, CacheEntry] = {}
        self._valid_tickers = valid_tickers
        self._vader = get_finance_vader()
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                headers={"User-Agent": "Sigil/1.0 (stock analysis app)"}
            )
        return self._session
    
    async def close(self):
        """Close the session."""
        if self._session and not self._session.closed:
            await self._session.close()
    
    def _get_cache(self, key: str) -> Optional[any]:
        """Get cached data if not expired."""
        entry = self._cache.get(key)
        if entry and datetime.utcnow() < entry.expires_at:
            return entry.data
        return None
    
    def _set_cache(self, key: str, data: any, ttl: timedelta):
        """Set cache entry with TTL."""
        self._cache[key] = CacheEntry(
            data=data,
            expires_at=datetime.utcnow() + ttl
        )
    
    def set_valid_tickers(self, tickers: Set[str]):
        """Set valid tickers for filtering."""
        self._valid_tickers = {t.upper() for t in tickers}
    
    # ========================================================================
    # Source 1: ApeWisdom (Primary)
    # ========================================================================
    
    async def fetch_apewisdom(self) -> List[RedditTicker]:
        """
        Fetch trending tickers from ApeWisdom API.
        
        Returns pre-aggregated mention counts and upvotes.
        15-minute cache.
        """
        cache_key = "apewisdom"
        cached = self._get_cache(cache_key)
        if cached:
            logger.debug("Using cached ApeWisdom data")
            return cached
        
        try:
            session = await self._get_session()
            async with session.get(self.APEWISDOM_URL) as resp:
                if resp.status != 200:
                    logger.warning(f"ApeWisdom API returned {resp.status}")
                    return []
                
                data = await resp.json()
                results = data.get("results", data) if isinstance(data, dict) else data
                
                tickers = []
                for item in results[:100]:  # Top 100
                    ticker = item.get("ticker", "").upper()
                    
                    # Filter invalid tickers
                    if not ticker or ticker in self.TICKER_EXCLUSIONS:
                        continue
                    if self._valid_tickers and ticker not in self._valid_tickers:
                        continue
                    
                    mentions = item.get("mentions", 0) or 0
                    mentions_24h_ago = item.get("mentions_24h_ago") or mentions
                    
                    # Calculate trending velocity (handle None values)
                    if mentions_24h_ago and mentions_24h_ago > 0:
                        velocity = (mentions - mentions_24h_ago) / mentions_24h_ago
                    else:
                        velocity = 1.0 if mentions and mentions > 0 else 0.0
                    
                    tickers.append(RedditTicker(
                        ticker=ticker,
                        name=item.get("name", ""),
                        mentions=mentions,
                        upvotes=item.get("upvotes", 0),
                        rank=item.get("rank", 0),
                        rank_24h_ago=item.get("rank_24h_ago", 0),
                        mentions_24h_ago=mentions_24h_ago,
                        trending_velocity=velocity,
                        source="apewisdom"
                    ))
                
                logger.info(f"Fetched {len(tickers)} tickers from ApeWisdom")
                self._set_cache(cache_key, tickers, self.APEWISDOM_TTL)
                return tickers
                
        except Exception as e:
            logger.error(f"ApeWisdom fetch error: {e}")
            return []
    
    # ========================================================================
    # Source 2: Reddit JSON (Sentiment)
    # ========================================================================
    
    async def fetch_reddit_posts(
        self,
        subreddit: str = "wallstreetbets",
        limit: int = 50
    ) -> List[Dict]:
        """
        Fetch hot posts from a subreddit for sentiment analysis.
        
        Uses Reddit's public JSON API (no auth required).
        5-minute cache per subreddit.
        """
        cache_key = f"reddit_{subreddit}"
        cached = self._get_cache(cache_key)
        if cached:
            logger.debug(f"Using cached Reddit data for r/{subreddit}")
            return cached
        
        try:
            session = await self._get_session()
            url = self.REDDIT_JSON_URL.format(subreddit=subreddit)
            
            async with session.get(f"{url}?limit={limit}") as resp:
                if resp.status != 200:
                    logger.warning(f"Reddit JSON API returned {resp.status} for r/{subreddit}")
                    return []
                
                data = await resp.json()
                children = data.get("data", {}).get("children", [])
                
                posts = []
                for child in children:
                    post = child.get("data", {})
                    posts.append({
                        "id": post.get("id"),
                        "title": post.get("title", ""),
                        "selftext": post.get("selftext", ""),
                        "score": post.get("score", 0),
                        "num_comments": post.get("num_comments", 0),
                        "created_utc": post.get("created_utc", 0),
                        "subreddit": subreddit
                    })
                
                logger.info(f"Fetched {len(posts)} posts from r/{subreddit}")
                self._set_cache(cache_key, posts, self.REDDIT_JSON_TTL)
                return posts
                
        except Exception as e:
            logger.error(f"Reddit JSON fetch error for r/{subreddit}: {e}")
            return []
    
    async def fetch_all_reddit_posts(self) -> List[Dict]:
        """Fetch posts from all configured subreddits with rate limiting."""
        all_posts = []
        
        # MEDIUM FIX CW-002: Add rate limiting (1 req/sec) to avoid Reddit blocks
        for subreddit in self.SUBREDDITS:
            try:
                posts = await self.fetch_reddit_posts(subreddit)
                if posts:
                    all_posts.extend(posts)
                # Rate limit: 1 request per second
                await asyncio.sleep(1.0)
            except Exception as e:
                logger.error(f"Subreddit fetch error for r/{subreddit}: {e}")
        
        return all_posts
    
    # ========================================================================
    # Sentiment Analysis
    # ========================================================================
    
    def analyze_sentiment(self, text: str) -> Tuple[float, str]:
        """
        Analyze sentiment of text using FinVADER.
        
        Returns:
            Tuple of (score 0-1, label)
            - score: 0=bearish, 0.5=neutral, 1=bullish
            - label: "bearish", "neutral", "bullish"
        """
        if not self._vader or not text:
            return 0.5, "neutral"
        
        # VADER returns compound score from -1 to 1
        scores = self._vader.polarity_scores(text)
        compound = scores["compound"]
        
        # Convert to 0-1 scale
        normalized = (compound + 1) / 2
        
        # Classify
        if compound >= 0.05:
            label = "bullish"
        elif compound <= -0.05:
            label = "bearish"
        else:
            label = "neutral"
        
        return normalized, label
    
    def extract_tickers_from_text(self, text: str) -> Set[str]:
        """Extract stock tickers from post text."""
        if not text:
            return set()
        
        matches = self.TICKER_PATTERN.findall(text)
        tickers = set()
        
        for match in matches:
            # Match is tuple (cashtag, word)
            ticker = match[0] or match[1]
            if ticker and ticker not in self.TICKER_EXCLUSIONS:
                if not self._valid_tickers or ticker in self._valid_tickers:
                    tickers.add(ticker)
        
        return tickers
    
    async def enrich_with_sentiment(
        self,
        tickers: List[RedditTicker]
    ) -> List[RedditTicker]:
        """
        Enrich tickers with sentiment from Reddit posts.
        
        Fetches recent posts and analyzes sentiment for each ticker.
        """
        # Fetch all posts
        posts = await self.fetch_all_reddit_posts()
        
        # Build ticker -> posts mapping
        ticker_posts: Dict[str, List[Dict]] = {}
        for post in posts:
            text = f"{post['title']} {post['selftext']}"
            found_tickers = self.extract_tickers_from_text(text)
            
            for ticker in found_tickers:
                if ticker not in ticker_posts:
                    ticker_posts[ticker] = []
                ticker_posts[ticker].append(post)
        
        # Analyze sentiment for each ticker
        for ticker_data in tickers:
            ticker = ticker_data.ticker
            related_posts = ticker_posts.get(ticker, [])
            
            if related_posts:
                # Combine text from all posts, weighted by score
                weighted_texts = []
                for post in related_posts[:10]:  # Top 10 posts
                    weight = max(1, post["score"] // 100)
                    text = f"{post['title']} {post['selftext']}"
                    weighted_texts.extend([text] * weight)
                
                combined_text = " ".join(weighted_texts)
                score, label = self.analyze_sentiment(combined_text)
                
                ticker_data.sentiment_score = score
                ticker_data.sentiment_label = label
                ticker_data.sample_posts = related_posts[:3]
        
        return tickers
    
    # ========================================================================
    # Main Interface
    # ========================================================================
    
    async def fetch_trending_tickers(
        self,
        limit: int = 50,
        enrich_sentiment: bool = True
    ) -> List[RedditTicker]:
        """
        Fetch trending tickers with mentions, upvotes, and sentiment.
        
        Args:
            limit: Maximum tickers to return
            enrich_sentiment: Whether to analyze sentiment from posts
            
        Returns:
            List of RedditTicker objects, sorted by mentions
        """
        # Primary source: ApeWisdom
        tickers = await self.fetch_apewisdom()
        
        if not tickers:
            logger.warning("ApeWisdom returned no data, using fallback")
            # Could add Arctic Shift fallback here
            return []
        
        # Enrich with sentiment
        if enrich_sentiment:
            tickers = await self.enrich_with_sentiment(tickers)
        
        # Sort by mentions and limit
        tickers.sort(key=lambda t: t.mentions, reverse=True)
        return tickers[:limit]
    
    def to_dict(self, ticker: RedditTicker) -> Dict:
        """Convert RedditTicker to dict for API response."""
        return {
            "ticker": ticker.ticker,
            "name": ticker.name,
            "mentions": ticker.mentions,
            "upvotes": ticker.upvotes,
            "rank": ticker.rank,
            "rank_24h_ago": ticker.rank_24h_ago,
            "mentions_24h_ago": ticker.mentions_24h_ago,
            "sentiment_score": round(ticker.sentiment_score, 3),
            "sentiment_label": ticker.sentiment_label,
            "trending_velocity": round(ticker.trending_velocity, 3),
            "source": ticker.source,
            "fetched_at": ticker.fetched_at.isoformat()
        }


# ============================================================================
# Convenience Functions
# ============================================================================

async def fetch_reddit_trending(
    limit: int = 50,
    valid_tickers: Optional[Set[str]] = None
) -> List[Dict]:
    """
    Convenience function to fetch trending Reddit tickers.
    
    Args:
        limit: Maximum tickers to return
        valid_tickers: Set of valid tickers to filter against
        
    Returns:
        List of ticker dicts with mentions, upvotes, sentiment
    """
    fetcher = FreeRedditFetcher(valid_tickers=valid_tickers)
    try:
        tickers = await fetcher.fetch_trending_tickers(limit=limit)
        return [fetcher.to_dict(t) for t in tickers]
    finally:
        await fetcher.close()


# For sync contexts
def fetch_reddit_trending_sync(
    limit: int = 50,
    valid_tickers: Optional[Set[str]] = None
) -> List[Dict]:
    """Synchronous wrapper for fetch_reddit_trending."""
    return asyncio.run(fetch_reddit_trending(limit, valid_tickers))
