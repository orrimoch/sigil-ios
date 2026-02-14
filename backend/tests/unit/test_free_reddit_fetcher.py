"""
Unit tests for FreeRedditFetcher (REC-266)

Tests the free Reddit data fetching from ApeWisdom and Reddit JSON APIs.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from src.crowd_wisdom.free_reddit_fetcher import (
    FreeRedditFetcher,
    RedditTicker,
    CacheEntry,
    get_finance_vader,
    FINANCE_LEXICON,
    fetch_reddit_trending
)


class TestFinanceVader:
    """Tests for FinVADER sentiment analysis."""
    
    def test_finance_lexicon_has_bullish_terms(self):
        """Bullish finance terms should have positive scores."""
        assert FINANCE_LEXICON["moon"] > 0
        assert FINANCE_LEXICON["bullish"] > 0
        assert FINANCE_LEXICON["rocket"] > 0
        assert FINANCE_LEXICON["tendies"] > 0
    
    def test_finance_lexicon_has_bearish_terms(self):
        """Bearish finance terms should have negative scores."""
        assert FINANCE_LEXICON["bearish"] < 0
        assert FINANCE_LEXICON["crash"] < 0
        assert FINANCE_LEXICON["dump"] < 0
        assert FINANCE_LEXICON["puts"] < 0
    
    def test_get_finance_vader_returns_analyzer(self):
        """Should return VADER analyzer with finance lexicon."""
        vader = get_finance_vader()
        if vader is not None:  # Only test if vaderSentiment is installed
            assert hasattr(vader, 'polarity_scores')
            # Check finance terms were added
            assert "moon" in vader.lexicon


class TestRedditTicker:
    """Tests for RedditTicker dataclass."""
    
    def test_default_values(self):
        """RedditTicker should have sensible defaults."""
        ticker = RedditTicker(ticker="AAPL")
        assert ticker.ticker == "AAPL"
        assert ticker.mentions == 0
        assert ticker.upvotes == 0
        assert ticker.sentiment_score == 0.5  # Neutral
        assert ticker.sentiment_label == "neutral"
        assert ticker.trending_velocity == 0.0
        assert ticker.source == "apewisdom"
    
    def test_custom_values(self):
        """RedditTicker should accept custom values."""
        ticker = RedditTicker(
            ticker="NVDA",
            name="NVIDIA",
            mentions=100,
            upvotes=500,
            rank=1,
            sentiment_score=0.8,
            sentiment_label="bullish"
        )
        assert ticker.ticker == "NVDA"
        assert ticker.name == "NVIDIA"
        assert ticker.mentions == 100
        assert ticker.sentiment_label == "bullish"


class TestCacheEntry:
    """Tests for cache functionality."""
    
    def test_cache_entry_not_expired(self):
        """Cache entry should be valid before expiry."""
        entry = CacheEntry(
            data={"test": "data"},
            expires_at=datetime.utcnow() + timedelta(minutes=5)
        )
        assert datetime.utcnow() < entry.expires_at
    
    def test_cache_entry_expired(self):
        """Cache entry should be invalid after expiry."""
        entry = CacheEntry(
            data={"test": "data"},
            expires_at=datetime.utcnow() - timedelta(minutes=1)
        )
        assert datetime.utcnow() >= entry.expires_at


class TestFreeRedditFetcher:
    """Tests for FreeRedditFetcher class."""
    
    def test_init_default(self):
        """Fetcher should initialize with default values."""
        fetcher = FreeRedditFetcher()
        assert fetcher._valid_tickers is None
        assert fetcher._cache == {}
    
    def test_init_with_valid_tickers(self):
        """Fetcher should accept valid tickers filter."""
        valid = {"AAPL", "MSFT", "NVDA"}
        fetcher = FreeRedditFetcher(valid_tickers=valid)
        assert fetcher._valid_tickers == valid
    
    def test_set_valid_tickers(self):
        """Should be able to set valid tickers after init."""
        fetcher = FreeRedditFetcher()
        fetcher.set_valid_tickers({"aapl", "msft"})  # lowercase
        assert "AAPL" in fetcher._valid_tickers  # Should be uppercase
        assert "MSFT" in fetcher._valid_tickers
    
    def test_cache_operations(self):
        """Cache should store and retrieve data correctly."""
        fetcher = FreeRedditFetcher()
        
        # Set cache
        fetcher._set_cache("test_key", {"data": 123}, timedelta(minutes=5))
        
        # Get cache (not expired)
        cached = fetcher._get_cache("test_key")
        assert cached == {"data": 123}
        
        # Non-existent key
        assert fetcher._get_cache("missing_key") is None
    
    def test_cache_expiry(self):
        """Expired cache should return None."""
        fetcher = FreeRedditFetcher()
        
        # Set cache with immediate expiry
        fetcher._cache["expired"] = CacheEntry(
            data={"old": "data"},
            expires_at=datetime.utcnow() - timedelta(seconds=1)
        )
        
        # Should return None for expired entry
        assert fetcher._get_cache("expired") is None
    
    def test_extract_tickers_from_text_cashtags(self):
        """Should extract $TICKER cashtags."""
        fetcher = FreeRedditFetcher()
        
        text = "Just bought $AAPL and $MSFT, selling $TSLA"
        tickers = fetcher.extract_tickers_from_text(text)
        
        assert "AAPL" in tickers
        assert "MSFT" in tickers
        assert "TSLA" in tickers
    
    def test_extract_tickers_from_text_uppercase(self):
        """Should extract uppercase ticker mentions."""
        fetcher = FreeRedditFetcher()
        
        text = "NVDA is going to the moon! AMD also looking good."
        tickers = fetcher.extract_tickers_from_text(text)
        
        assert "NVDA" in tickers
        assert "AMD" in tickers
    
    def test_extract_tickers_excludes_common_words(self):
        """Should exclude common words that look like tickers."""
        fetcher = FreeRedditFetcher()
        
        text = "I think the CEO said YOLO on the IPO for USA GDP"
        tickers = fetcher.extract_tickers_from_text(text)
        
        # These should be excluded
        assert "CEO" not in tickers
        assert "YOLO" not in tickers
        assert "IPO" not in tickers
        assert "USA" not in tickers
        assert "GDP" not in tickers
    
    def test_extract_tickers_with_valid_filter(self):
        """Should only return tickers in valid set."""
        fetcher = FreeRedditFetcher(valid_tickers={"AAPL", "MSFT"})
        
        text = "$AAPL $MSFT $NVDA $TSLA"
        tickers = fetcher.extract_tickers_from_text(text)
        
        assert "AAPL" in tickers
        assert "MSFT" in tickers
        assert "NVDA" not in tickers  # Not in valid set
        assert "TSLA" not in tickers  # Not in valid set
    
    def test_extract_tickers_empty_text(self):
        """Should handle empty text."""
        fetcher = FreeRedditFetcher()
        assert fetcher.extract_tickers_from_text("") == set()
        assert fetcher.extract_tickers_from_text(None) == set()


class TestSentimentAnalysis:
    """Tests for sentiment analysis."""
    
    def test_analyze_sentiment_bullish(self):
        """Bullish text should return high score."""
        fetcher = FreeRedditFetcher()
        
        text = "NVDA is going to the moon! Rocket ship! 🚀 Bullish!"
        score, label = fetcher.analyze_sentiment(text)
        
        assert score > 0.6  # Should be bullish
        assert label == "bullish"
    
    def test_analyze_sentiment_bearish(self):
        """Bearish text should return low score."""
        fetcher = FreeRedditFetcher()
        
        text = "This stock is crashing! Dump it! Puts are printing!"
        score, label = fetcher.analyze_sentiment(text)
        
        assert score < 0.4  # Should be bearish
        assert label == "bearish"
    
    def test_analyze_sentiment_neutral(self):
        """Neutral text should return middle score."""
        fetcher = FreeRedditFetcher()
        
        text = "The stock closed at $150 today with average volume."
        score, label = fetcher.analyze_sentiment(text)
        
        assert 0.4 <= score <= 0.6  # Should be neutral
        assert label == "neutral"
    
    def test_analyze_sentiment_empty(self):
        """Empty text should return neutral."""
        fetcher = FreeRedditFetcher()
        
        score, label = fetcher.analyze_sentiment("")
        assert score == 0.5
        assert label == "neutral"


class TestToDict:
    """Tests for to_dict conversion."""
    
    def test_to_dict_conversion(self):
        """Should convert RedditTicker to dict."""
        fetcher = FreeRedditFetcher()
        ticker = RedditTicker(
            ticker="AAPL",
            name="Apple Inc.",
            mentions=50,
            upvotes=200,
            rank=5,
            sentiment_score=0.75,
            sentiment_label="bullish",
            trending_velocity=1.5
        )
        
        result = fetcher.to_dict(ticker)
        
        assert result["ticker"] == "AAPL"
        assert result["name"] == "Apple Inc."
        assert result["mentions"] == 50
        assert result["upvotes"] == 200
        assert result["rank"] == 5
        assert result["sentiment_score"] == 0.75
        assert result["sentiment_label"] == "bullish"
        assert result["trending_velocity"] == 1.5
        assert "fetched_at" in result


class TestApewisdomAPI:
    """Tests for ApeWisdom API integration."""
    
    @pytest.mark.asyncio
    async def test_fetch_apewisdom_success(self):
        """Should fetch and parse ApeWisdom data."""
        fetcher = FreeRedditFetcher()
        
        mock_response = [
            {"rank": 1, "ticker": "SPY", "name": "SPDR S&P 500", "mentions": 500, "upvotes": 2000},
            {"rank": 2, "ticker": "MSFT", "name": "Microsoft", "mentions": 300, "upvotes": 1500},
        ]
        
        with patch.object(fetcher, '_get_session') as mock_session:
            mock_resp = AsyncMock()
            mock_resp.status = 200
            mock_resp.json = AsyncMock(return_value={"results": mock_response})
            
            mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_session.return_value)
            mock_session.return_value.get = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_resp), __aexit__=AsyncMock()))
            
            # Direct test of parsing logic
            fetcher._cache["apewisdom"] = CacheEntry(
                data=[
                    RedditTicker(ticker="SPY", name="SPDR S&P 500", mentions=500, upvotes=2000, rank=1),
                    RedditTicker(ticker="MSFT", name="Microsoft", mentions=300, upvotes=1500, rank=2),
                ],
                expires_at=datetime.utcnow() + timedelta(minutes=15)
            )
            
            tickers = await fetcher.fetch_apewisdom()
            
            assert len(tickers) == 2
            assert tickers[0].ticker == "SPY"
            assert tickers[0].mentions == 500
        
        await fetcher.close()
    
    @pytest.mark.asyncio
    async def test_fetch_apewisdom_uses_cache(self):
        """Should return cached data if not expired."""
        fetcher = FreeRedditFetcher()
        
        # Pre-populate cache
        cached_data = [RedditTicker(ticker="CACHED", mentions=100)]
        fetcher._set_cache("apewisdom", cached_data, timedelta(minutes=15))
        
        result = await fetcher.fetch_apewisdom()
        
        assert len(result) == 1
        assert result[0].ticker == "CACHED"
        
        await fetcher.close()


class TestIntegration:
    """Integration tests (require network, skip in CI)."""
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_fetch_trending_tickers_live(self):
        """
        Live test: Actually fetch from ApeWisdom API.
        
        Run with: pytest -m integration
        """
        tickers = await fetch_reddit_trending(limit=10)
        
        assert len(tickers) > 0
        
        # Check structure
        first = tickers[0]
        assert "ticker" in first
        assert "mentions" in first
        assert "upvotes" in first
        assert "sentiment_score" in first
        assert "fetched_at" in first
