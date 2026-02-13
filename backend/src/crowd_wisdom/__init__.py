"""
REC-266: Crowd Wisdom Module (Reddit-based)

Provides Reddit-based viral stock detection and scoring.
"""

from .routes import router
from .models import init_db
from .reddit_fetcher import RedditFetcher, fetch_reddit_mentions
from .reddit_scorer import RedditScorer, get_weekly_top_picks

__all__ = [
    "router",
    "init_db",
    "RedditFetcher",
    "fetch_reddit_mentions",
    "RedditScorer",
    "get_weekly_top_picks"
]
