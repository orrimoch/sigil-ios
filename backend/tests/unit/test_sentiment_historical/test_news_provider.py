"""
Tests for News Provider Abstraction Layer (REC-208)
"""

import pytest
from datetime import datetime, date
from pathlib import Path

from src.sentiment_historical.news_provider import (
    NewsProvider,
    NewsArticle,
    NewsSource,
    MultiSourceNewsProvider,
)


class TestNewsArticle:
    """Tests for NewsArticle dataclass."""
    
    def test_create_article(self):
        """Test creating a basic article."""
        article = NewsArticle(
            ticker="AAPL",
            headline="Apple beats earnings",
            published=datetime(2019, 10, 15, 14, 30),
            source="Reuters",
        )
        
        assert article.ticker == "AAPL"
        assert article.headline == "Apple beats earnings"
        assert article.source == "Reuters"
        assert article.provider == NewsSource.KAGGLE
    
    def test_article_to_dict(self):
        """Test converting article to dict."""
        article = NewsArticle(
            ticker="MSFT",
            headline="Microsoft cloud grows",
            published=datetime(2019, 9, 1, 10, 0),
            source="Bloomberg",
            summary="Azure revenue up 50%",
        )
        
        d = article.to_dict()
        
        assert d["title"] == "Microsoft cloud grows"
        assert d["summary"] == "Azure revenue up 50%"
        assert d["source"] == "Bloomberg"
        assert "_ticker" in d
        assert d["_ticker"] == "MSFT"
    
    def test_article_from_dict(self):
        """Test creating article from dict."""
        data = {
            "title": "Tesla delivers 500k cars",
            "summary": "Record deliveries",
            "published": "2019-10-01T12:00:00",
            "source": "CNBC",
        }
        
        article = NewsArticle.from_dict(data, ticker="TSLA")
        
        assert article.ticker == "TSLA"
        assert article.headline == "Tesla delivers 500k cars"
        assert article.summary == "Record deliveries"
    
    def test_article_default_quality_scores(self):
        """Test default quality/relevance scores."""
        article = NewsArticle(
            ticker="GOOG",
            headline="Google announces AI",
            published=datetime.now(),
        )
        
        assert article.quality_score == 0.5
        assert article.relevance_score == 0.5


class TestNewsSource:
    """Tests for NewsSource enum."""
    
    def test_kaggle_source(self):
        assert NewsSource.KAGGLE.value == "kaggle"
    
    def test_polygon_source(self):
        assert NewsSource.POLYGON.value == "polygon"


class MockNewsProvider(NewsProvider):
    """Mock provider for testing."""
    
    def __init__(self, articles: list = None, start: date = None, end: date = None):
        self._articles = articles or []
        self._start = start or date(2019, 1, 1)
        self._end = end or date(2019, 12, 31)
    
    @property
    def name(self) -> str:
        return "mock"
    
    @property
    def source_type(self) -> NewsSource:
        return NewsSource.KAGGLE
    
    @property
    def date_range(self) -> tuple:
        return (self._start, self._end)
    
    def get_articles(self, ticker, start_date, end_date):
        return [
            a for a in self._articles
            if a.ticker == ticker
            and start_date <= a.published.date() <= end_date
        ]
    
    def get_all_articles(self, start_date, end_date, tickers=None):
        filtered = [
            a for a in self._articles
            if start_date <= a.published.date() <= end_date
        ]
        if tickers:
            tickers_upper = {t.upper() for t in tickers}
            filtered = [a for a in filtered if a.ticker in tickers_upper]
        return filtered
    
    def get_coverage_stats(self):
        return {"total": len(self._articles)}


class TestMultiSourceNewsProvider:
    """Tests for MultiSourceNewsProvider."""
    
    def test_empty_providers(self):
        """Test with no providers."""
        multi = MultiSourceNewsProvider([])
        
        assert multi.name == "multi_source"
        articles = multi.get_all_articles(date(2019, 1, 1), date(2019, 12, 31))
        assert articles == []
    
    def test_single_provider(self):
        """Test with single provider."""
        articles = [
            NewsArticle("AAPL", "Apple news", datetime(2019, 6, 15)),
            NewsArticle("MSFT", "Microsoft news", datetime(2019, 7, 20)),
        ]
        
        mock = MockNewsProvider(articles)
        multi = MultiSourceNewsProvider([mock])
        
        result = multi.get_all_articles(date(2019, 6, 1), date(2019, 6, 30))
        assert len(result) == 1
        assert result[0].ticker == "AAPL"
    
    def test_multiple_providers_date_routing(self):
        """Test routing to correct provider by date."""
        articles_2019 = [
            NewsArticle("AAPL", "Apple 2019", datetime(2019, 6, 15)),
        ]
        articles_2020 = [
            NewsArticle("AAPL", "Apple 2020", datetime(2020, 6, 15)),
        ]
        
        provider_2019 = MockNewsProvider(
            articles_2019,
            start=date(2019, 1, 1),
            end=date(2019, 12, 31),
        )
        provider_2020 = MockNewsProvider(
            articles_2020,
            start=date(2020, 1, 1),
            end=date(2020, 12, 31),
        )
        
        multi = MultiSourceNewsProvider([provider_2019, provider_2020])
        
        # Query 2019
        result_2019 = multi.get_all_articles(date(2019, 1, 1), date(2019, 12, 31))
        assert len(result_2019) == 1
        assert "2019" in result_2019[0].headline
        
        # Query 2020
        result_2020 = multi.get_all_articles(date(2020, 1, 1), date(2020, 12, 31))
        assert len(result_2020) == 1
        assert "2020" in result_2020[0].headline
        
        # Query spanning both
        result_all = multi.get_all_articles(date(2019, 1, 1), date(2020, 12, 31))
        assert len(result_all) == 2
    
    def test_ticker_filter(self):
        """Test filtering by tickers."""
        articles = [
            NewsArticle("AAPL", "Apple news", datetime(2019, 6, 15)),
            NewsArticle("MSFT", "Microsoft news", datetime(2019, 6, 20)),
            NewsArticle("GOOG", "Google news", datetime(2019, 6, 25)),
        ]
        
        mock = MockNewsProvider(articles)
        multi = MultiSourceNewsProvider([mock])
        
        result = multi.get_all_articles(
            date(2019, 6, 1),
            date(2019, 6, 30),
            tickers=["AAPL", "GOOG"],
        )
        
        assert len(result) == 2
        tickers = {a.ticker for a in result}
        assert "AAPL" in tickers
        assert "GOOG" in tickers
        assert "MSFT" not in tickers
    
    def test_get_articles_single_ticker(self):
        """Test getting articles for single ticker."""
        articles = [
            NewsArticle("AAPL", "Apple news 1", datetime(2019, 6, 15)),
            NewsArticle("AAPL", "Apple news 2", datetime(2019, 6, 20)),
            NewsArticle("MSFT", "Microsoft news", datetime(2019, 6, 25)),
        ]
        
        mock = MockNewsProvider(articles)
        multi = MultiSourceNewsProvider([mock])
        
        result = multi.get_articles("AAPL", date(2019, 6, 1), date(2019, 6, 30))
        
        assert len(result) == 2
        assert all(a.ticker == "AAPL" for a in result)
    
    def test_coverage_stats(self):
        """Test aggregated coverage stats."""
        mock1 = MockNewsProvider([], start=date(2019, 1, 1), end=date(2019, 12, 31))
        mock2 = MockNewsProvider([], start=date(2020, 1, 1), end=date(2020, 12, 31))
        
        multi = MultiSourceNewsProvider([mock1, mock2])
        stats = multi.get_coverage_stats()
        
        assert "providers" in stats
        assert len(stats["providers"]) == 2
        assert "combined_range" in stats
    
    def test_supports_date(self):
        """Test date support checking."""
        mock = MockNewsProvider([], start=date(2019, 1, 1), end=date(2019, 12, 31))
        multi = MultiSourceNewsProvider([mock])
        
        assert multi.supports_date(date(2019, 6, 15))
        assert not multi.supports_date(date(2020, 6, 15))
