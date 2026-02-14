"""
REC-266: Crowd Wisdom Module (Reddit-based)

Provides Reddit-based viral stock detection and scoring.
Uses FREE APIs (no Reddit API keys required):
- ApeWisdom: Trending tickers + mentions
- Reddit JSON: Real-time posts for sentiment
- Arctic Shift: Historical data (fallback)
"""

from .routes import router
from .models import init_db
from .reddit_fetcher import RedditFetcher, fetch_reddit_mentions
from .reddit_scorer import RedditScorer, get_weekly_top_picks
from .free_reddit_fetcher import FreeRedditFetcher, fetch_reddit_trending

__all__ = [
    "router",
    "init_db",
    "RedditFetcher",
    "fetch_reddit_mentions",
    "RedditScorer",
    "get_weekly_top_picks",
    "FreeRedditFetcher",
    "fetch_reddit_trending"
]
