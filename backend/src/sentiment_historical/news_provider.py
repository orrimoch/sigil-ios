"""
News Provider Abstraction Layer (REC-208)

Unified interface for news sources supporting:
- Kaggle (historical 2009-2020)
- Polygon.io (real-time 2020+) [future]

Enables auto-routing by date.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import List, Optional, Dict, Any
from enum import Enum


class NewsSource(str, Enum):
    """Supported news data sources."""
    KAGGLE = "kaggle"
    POLYGON = "polygon"


@dataclass
class NewsArticle:
    """
    Standardized news article representation.
    
    Compatible with live Sigil pipeline article format.
    """
    ticker: str
    headline: str
    published: datetime
    source: str = ""
    summary: str = ""
    url: str = ""
    provider: NewsSource = NewsSource.KAGGLE
    
    # Quality/relevance scores (optional, set by processor)
    quality_score: float = 0.5
    relevance_score: float = 0.5
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict format compatible with live pipeline."""
        return {
            "title": self.headline,
            "summary": self.summary,
            "published": self.published.isoformat(),
            "source": self.source,
            "url": self.url,
            "_ticker": self.ticker,
            "_provider": self.provider.value,
            "_quality_score": self.quality_score,
            "_relevance_score": self.relevance_score,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], ticker: str = "") -> "NewsArticle":
        """Create from dict."""
        published = data.get("published") or data.get("date")
        if isinstance(published, str):
            try:
                published = datetime.fromisoformat(published.replace("Z", "+00:00"))
            except:
                published = datetime.now()
        
        return cls(
            ticker=ticker or data.get("_ticker", ""),
            headline=data.get("title") or data.get("headline", ""),
            published=published,
            source=data.get("source", ""),
            summary=data.get("summary", ""),
            url=data.get("url", ""),
        )


class NewsProvider(ABC):
    """
    Abstract base class for news data providers.
    
    Implementations:
    - KaggleNewsProvider: Historical news from CSV files (2009-2020)
    - PolygonNewsProvider: Real-time news from API (2020+) [future]
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name for logging."""
        pass
    
    @property
    @abstractmethod
    def source_type(self) -> NewsSource:
        """Source type enum."""
        pass
    
    @property
    @abstractmethod
    def date_range(self) -> tuple:
        """(start_date, end_date) coverage."""
        pass
    
    @abstractmethod
    def get_articles(
        self,
        ticker: str,
        start_date: date,
        end_date: date,
    ) -> List[NewsArticle]:
        """
        Get articles for a ticker within date range.
        
        Args:
            ticker: Stock symbol (e.g., "AAPL")
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
        
        Returns:
            List of NewsArticle objects
        """
        pass
    
    @abstractmethod
    def get_all_articles(
        self,
        start_date: date,
        end_date: date,
        tickers: Optional[List[str]] = None,
    ) -> List[NewsArticle]:
        """
        Get all articles within date range, optionally filtered by tickers.
        
        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            tickers: Optional list of tickers to filter (None = all)
        
        Returns:
            List of NewsArticle objects
        """
        pass
    
    @abstractmethod
    def get_coverage_stats(self) -> Dict[str, Any]:
        """Get statistics about data coverage."""
        pass
    
    def supports_date(self, dt: date) -> bool:
        """Check if this provider covers a specific date."""
        start, end = self.date_range
        return start <= dt <= end


class MultiSourceNewsProvider(NewsProvider):
    """
    Aggregates multiple news providers with auto-routing by date.
    
    Routes requests to appropriate provider based on date coverage:
    - Historical dates -> KaggleProvider
    - Recent dates -> PolygonProvider
    """
    
    def __init__(self, providers: List[NewsProvider]):
        """
        Initialize with list of providers.
        
        Args:
            providers: List of NewsProvider instances
        """
        self.providers = providers
        self._build_date_map()
    
    def _build_date_map(self):
        """Build date -> provider mapping for efficient routing."""
        self._date_ranges = [
            (p.date_range[0], p.date_range[1], p)
            for p in self.providers
        ]
        # Sort by start date
        self._date_ranges.sort(key=lambda x: x[0])
    
    def _get_provider_for_date(self, dt: date) -> Optional[NewsProvider]:
        """Get the best provider for a specific date."""
        for start, end, provider in self._date_ranges:
            if start <= dt <= end:
                return provider
        return None
    
    @property
    def name(self) -> str:
        return "multi_source"
    
    @property
    def source_type(self) -> NewsSource:
        return NewsSource.KAGGLE  # Primary
    
    @property
    def date_range(self) -> tuple:
        if not self.providers:
            return (date.min, date.max)
        starts = [p.date_range[0] for p in self.providers]
        ends = [p.date_range[1] for p in self.providers]
        return (min(starts), max(ends))
    
    def get_articles(
        self,
        ticker: str,
        start_date: date,
        end_date: date,
    ) -> List[NewsArticle]:
        """Get articles from all applicable providers."""
        articles = []
        seen_providers = set()
        
        # Find all providers that cover any part of the date range
        for provider in self.providers:
            p_start, p_end = provider.date_range
            
            # Check for overlap
            if p_start <= end_date and p_end >= start_date:
                if provider.name not in seen_providers:
                    # Clip to provider's range
                    q_start = max(start_date, p_start)
                    q_end = min(end_date, p_end)
                    
                    articles.extend(
                        provider.get_articles(ticker, q_start, q_end)
                    )
                    seen_providers.add(provider.name)
        
        # Sort by date
        articles.sort(key=lambda a: a.published, reverse=True)
        return articles
    
    def get_all_articles(
        self,
        start_date: date,
        end_date: date,
        tickers: Optional[List[str]] = None,
    ) -> List[NewsArticle]:
        """Get all articles from all applicable providers."""
        articles = []
        
        for provider in self.providers:
            p_start, p_end = provider.date_range
            
            if p_start <= end_date and p_end >= start_date:
                q_start = max(start_date, p_start)
                q_end = min(end_date, p_end)
                
                articles.extend(
                    provider.get_all_articles(q_start, q_end, tickers)
                )
        
        articles.sort(key=lambda a: a.published, reverse=True)
        return articles
    
    def get_coverage_stats(self) -> Dict[str, Any]:
        """Aggregate coverage stats from all providers."""
        return {
            "providers": [p.name for p in self.providers],
            "combined_range": {
                "start": self.date_range[0].isoformat(),
                "end": self.date_range[1].isoformat(),
            },
            "per_provider": {
                p.name: p.get_coverage_stats()
                for p in self.providers
            }
        }
