"""
Historical Sentiment Integration (HSI) Module

Provides historical sentiment scoring for backtesting using:
1. Kaggle Dataset (2009-2020) - Historical news
2. Polygon.io API (2020+) - Real-time news (future)

Uses same Claude Haiku agentic scoring as live Sigil pipeline.
"""

from .news_provider import NewsProvider, NewsArticle
from .kaggle_provider import KaggleNewsProvider
from .sentiment_scorer import HistoricalSentimentScorer

__all__ = [
    "NewsProvider",
    "NewsArticle", 
    "KaggleNewsProvider",
    "HistoricalSentimentScorer",
]
