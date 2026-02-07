"""
Tests for Kaggle News Provider (REC-207)
"""

import pytest
import pandas as pd
from datetime import datetime, date
from pathlib import Path
from unittest.mock import patch, MagicMock
import tempfile
import json

from src.sentiment_historical.kaggle_provider import (
    KaggleNewsProvider,
    TICKER_ALIASES,
    create_kaggle_provider,
)
from src.sentiment_historical.news_provider import NewsSource


@pytest.fixture
def sample_csv_data():
    """Sample CSV data for testing."""
    return pd.DataFrame({
        "Unnamed: 0": [0, 1, 2, 3, 4],
        "title": [
            "Apple beats earnings expectations",
            "Microsoft cloud revenue grows 50%",
            "Apple announces new iPhone",
            "Google faces antitrust probe",
            "Tesla delivers record cars",
        ],
        "date": [
            "2019-06-15 10:30:00-04:00",
            "2019-07-20 14:00:00-04:00",
            "2019-09-10 09:00:00-04:00",
            "2019-10-05 11:30:00-04:00",
            "2019-11-15 16:00:00-04:00",
        ],
        "stock": ["AAPL", "MSFT", "AAPL", "GOOGL", "TSLA"],
    })


@pytest.fixture
def temp_data_dir(sample_csv_data):
    """Create temporary data directory with sample CSV."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        
        # Write sample CSV
        csv_path = data_dir / "analyst_ratings_processed.csv"
        sample_csv_data.to_csv(csv_path, index=False)
        
        # Write sample universe
        universe_path = data_dir / "fundamentals.json"
        universe_path.write_text(json.dumps({
            "stocks": {
                "AAPL": {},
                "MSFT": {},
                "GOOGL": {},
                "TSLA": {},
                "AMZN": {},
            }
        }))
        
        yield data_dir, universe_path


class TestTickerAliases:
    """Tests for ticker normalization."""
    
    def test_brk_aliases(self):
        assert TICKER_ALIASES["BRK.B"] == "BRK-B"
        assert TICKER_ALIASES["BRK.A"] == "BRK-A"
    
    def test_bf_aliases(self):
        assert TICKER_ALIASES["BF.B"] == "BF-B"


class TestKaggleNewsProvider:
    """Tests for KaggleNewsProvider."""
    
    def test_init_lazy_load(self, temp_data_dir):
        """Test lazy loading initialization."""
        data_dir, universe_path = temp_data_dir
        
        provider = KaggleNewsProvider(
            data_dir=data_dir,
            universe_path=universe_path,
            lazy_load=True,
        )
        
        assert provider._df is None  # Not loaded yet
        assert provider.name == "kaggle"
        assert provider.source_type == NewsSource.KAGGLE
    
    def test_init_immediate_load(self, temp_data_dir):
        """Test immediate loading initialization."""
        data_dir, universe_path = temp_data_dir
        
        provider = KaggleNewsProvider(
            data_dir=data_dir,
            universe_path=universe_path,
            lazy_load=False,
        )
        
        assert provider._df is not None
    
    def test_date_range(self, temp_data_dir):
        """Test date range property."""
        data_dir, universe_path = temp_data_dir
        provider = KaggleNewsProvider(data_dir, universe_path)
        
        start, end = provider.date_range
        
        assert start == date(2019, 6, 15)
        assert end == date(2019, 11, 15)
    
    def test_get_articles_single_ticker(self, temp_data_dir):
        """Test getting articles for single ticker."""
        data_dir, universe_path = temp_data_dir
        provider = KaggleNewsProvider(data_dir, universe_path)
        
        articles = provider.get_articles(
            "AAPL",
            date(2019, 6, 1),
            date(2019, 12, 31),
        )
        
        assert len(articles) == 2
        assert all(a.ticker == "AAPL" for a in articles)
    
    def test_get_articles_date_filter(self, temp_data_dir):
        """Test date filtering."""
        data_dir, universe_path = temp_data_dir
        provider = KaggleNewsProvider(data_dir, universe_path)
        
        # Only June
        articles = provider.get_articles(
            "AAPL",
            date(2019, 6, 1),
            date(2019, 6, 30),
        )
        
        assert len(articles) == 1
        assert articles[0].published.month == 6
    
    def test_get_articles_ticker_not_found(self, temp_data_dir):
        """Test when ticker has no articles."""
        data_dir, universe_path = temp_data_dir
        provider = KaggleNewsProvider(data_dir, universe_path)
        
        articles = provider.get_articles(
            "AMZN",  # In universe but no articles
            date(2019, 6, 1),
            date(2019, 12, 31),
        )
        
        assert len(articles) == 0
    
    def test_get_all_articles(self, temp_data_dir):
        """Test getting all articles."""
        data_dir, universe_path = temp_data_dir
        provider = KaggleNewsProvider(data_dir, universe_path)
        
        articles = provider.get_all_articles(
            date(2019, 6, 1),
            date(2019, 12, 31),
        )
        
        assert len(articles) == 5
    
    def test_get_all_articles_with_ticker_filter(self, temp_data_dir):
        """Test filtering all articles by tickers."""
        data_dir, universe_path = temp_data_dir
        provider = KaggleNewsProvider(data_dir, universe_path)
        
        articles = provider.get_all_articles(
            date(2019, 6, 1),
            date(2019, 12, 31),
            tickers=["AAPL", "MSFT"],
        )
        
        assert len(articles) == 3
        tickers = {a.ticker for a in articles}
        assert tickers == {"AAPL", "MSFT"}
    
    def test_get_articles_for_universe(self, temp_data_dir):
        """Test filtering to universe tickers."""
        data_dir, universe_path = temp_data_dir
        provider = KaggleNewsProvider(data_dir, universe_path)
        
        articles = provider.get_articles_for_universe(
            date(2019, 6, 1),
            date(2019, 12, 31),
        )
        
        # All 5 articles match universe tickers
        assert len(articles) == 5
    
    def test_get_coverage_stats(self, temp_data_dir):
        """Test coverage statistics."""
        data_dir, universe_path = temp_data_dir
        provider = KaggleNewsProvider(data_dir, universe_path)
        
        stats = provider.get_coverage_stats()
        
        assert stats["total_articles"] == 5
        assert stats["unique_tickers"] == 4  # AAPL, MSFT, GOOGL, TSLA
        assert "date_range" in stats
        assert stats["universe_overlap"]["matched"] == 4
        assert stats["universe_overlap"]["universe_size"] == 5
    
    def test_get_ticker_article_counts(self, temp_data_dir):
        """Test article counts per ticker."""
        data_dir, universe_path = temp_data_dir
        provider = KaggleNewsProvider(data_dir, universe_path)
        
        counts = provider.get_ticker_article_counts(
            date(2019, 6, 1),
            date(2019, 12, 31),
        )
        
        assert counts["AAPL"] == 2
        assert counts["MSFT"] == 1
        assert counts["GOOGL"] == 1
        assert counts["TSLA"] == 1
    
    def test_ticker_normalization(self, temp_data_dir):
        """Test ticker normalization (uppercase)."""
        data_dir, universe_path = temp_data_dir
        provider = KaggleNewsProvider(data_dir, universe_path)
        
        # Should work with lowercase
        articles = provider.get_articles(
            "aapl",  # lowercase
            date(2019, 6, 1),
            date(2019, 12, 31),
        )
        
        assert len(articles) == 2
    
    def test_article_has_correct_properties(self, temp_data_dir):
        """Test that articles have correct properties."""
        data_dir, universe_path = temp_data_dir
        provider = KaggleNewsProvider(data_dir, universe_path)
        
        articles = provider.get_articles(
            "AAPL",
            date(2019, 6, 1),
            date(2019, 6, 30),
        )
        
        assert len(articles) == 1
        article = articles[0]
        
        assert article.ticker == "AAPL"
        assert article.headline == "Apple beats earnings expectations"
        assert article.source == "kaggle"
        assert article.provider == NewsSource.KAGGLE
        assert isinstance(article.published, datetime)


class TestKaggleProviderEdgeCases:
    """Edge case tests for KaggleNewsProvider."""
    
    def test_missing_csv_raises_error(self):
        """Test that missing CSV raises FileNotFoundError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            provider = KaggleNewsProvider(
                data_dir=Path(tmpdir),
                lazy_load=True,
            )
            
            with pytest.raises(FileNotFoundError):
                _ = provider.df
    
    def test_empty_date_range_returns_empty(self, temp_data_dir):
        """Test querying outside data range returns empty."""
        data_dir, universe_path = temp_data_dir
        provider = KaggleNewsProvider(data_dir, universe_path)
        
        articles = provider.get_articles(
            "AAPL",
            date(2020, 1, 1),  # After data range
            date(2020, 12, 31),
        )
        
        assert len(articles) == 0
    
    def test_no_universe_file(self, sample_csv_data):
        """Test behavior when universe file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            
            # Write CSV only, no universe
            csv_path = data_dir / "analyst_ratings_processed.csv"
            sample_csv_data.to_csv(csv_path, index=False)
            
            provider = KaggleNewsProvider(
                data_dir=data_dir,
                universe_path=data_dir / "nonexistent.json",
            )
            
            # Should still work, just no universe filtering
            stats = provider.get_coverage_stats()
            assert stats["universe_overlap"]["universe_size"] == 0


class TestCreateKaggleProvider:
    """Tests for create_kaggle_provider convenience function."""
    
    def test_create_with_explicit_root(self, temp_data_dir):
        """Test creating with explicit project root."""
        data_dir, universe_path = temp_data_dir
        
        # Create expected structure
        kaggle_dir = data_dir.parent / "kaggle_sentiment"
        kaggle_dir.mkdir(exist_ok=True)
        
        backend_dir = data_dir.parent / "backend" / "data"
        backend_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy files
        import shutil
        shutil.copy(
            data_dir / "analyst_ratings_processed.csv",
            kaggle_dir / "analyst_ratings_processed.csv",
        )
        shutil.copy(
            data_dir / "fundamentals.json",
            backend_dir / "fundamentals.json",
        )
        
        provider = create_kaggle_provider(data_dir.parent)
        
        assert provider is not None
        assert provider.name == "kaggle"
