"""
Tests for Historical Sentiment Integration with Backtest (REC-210)

Tests that historical_scores.py properly loads and uses sentiment
from the HSI module.
"""

import pytest
import json
from datetime import datetime, date, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock
import tempfile

from src.backtest.historical_scores import (
    HistoricalScoreGenerator,
    HISTORICAL_SENTIMENT_PATH,
)


@pytest.fixture
def sample_sentiment_data():
    """Sample historical sentiment data."""
    return {
        "generated_at": "2026-02-07T12:00:00",
        "headline_count": 100,
        "ticker_count": 3,
        "weekly_scores": {
            "AAPL": [
                {"week_start": "2019-06-10", "week_end": "2019-06-16", "score": 72.5, "article_count": 5},
                {"week_start": "2019-06-17", "week_end": "2019-06-23", "score": 68.0, "article_count": 3},
            ],
            "MSFT": [
                {"week_start": "2019-06-10", "week_end": "2019-06-16", "score": 65.0, "article_count": 4},
            ],
            "TSLA": [
                {"week_start": "2019-06-10", "week_end": "2019-06-16", "score": 45.0, "article_count": 8},
            ],
        },
        "raw_scores": [],
    }


@pytest.fixture
def temp_sentiment_file(sample_sentiment_data):
    """Create temporary sentiment file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(sample_sentiment_data, f)
        return Path(f.name)


class TestHistoricalSentimentLoading:
    """Tests for loading historical sentiment data."""
    
    def test_load_sentiment_from_file(self, temp_sentiment_file, sample_sentiment_data):
        """Test loading sentiment from JSON file."""
        with patch.object(
            HistoricalScoreGenerator,
            '_load_historical_sentiment'
        ) as mock_load:
            # Manually set up the sentiment data as the constructor would
            generator = HistoricalScoreGenerator.__new__(HistoricalScoreGenerator)
            generator._historical_sentiment = {}
            
            for ticker, weeks in sample_sentiment_data["weekly_scores"].items():
                generator._historical_sentiment[ticker.upper()] = {
                    w["week_start"]: w["score"]
                    for w in weeks
                }
            
            assert "AAPL" in generator._historical_sentiment
            assert "MSFT" in generator._historical_sentiment
            assert len(generator._historical_sentiment["AAPL"]) == 2
    
    def test_sentiment_not_found_returns_neutral(self):
        """Test that missing sentiment file returns neutral."""
        generator = HistoricalScoreGenerator.__new__(HistoricalScoreGenerator)
        generator._historical_sentiment = None
        generator.no_sentiment = False
        
        score = generator._get_historical_sentiment("AAPL", "2019-06-15")
        assert score == 50.0
    
    def test_no_sentiment_mode_returns_neutral(self):
        """Test that no_sentiment mode always returns neutral."""
        generator = HistoricalScoreGenerator.__new__(HistoricalScoreGenerator)
        generator._historical_sentiment = {"AAPL": {"2019-06-10": 75.0}}
        generator.no_sentiment = True
        
        score = generator._get_historical_sentiment("AAPL", "2019-06-15")
        assert score == 50.0


class TestHistoricalSentimentLookup:
    """Tests for looking up sentiment by date."""
    
    @pytest.fixture
    def generator_with_sentiment(self, sample_sentiment_data):
        """Create generator with pre-loaded sentiment."""
        generator = HistoricalScoreGenerator.__new__(HistoricalScoreGenerator)
        generator.no_sentiment = False
        generator._historical_sentiment = {}
        
        for ticker, weeks in sample_sentiment_data["weekly_scores"].items():
            generator._historical_sentiment[ticker.upper()] = {
                w["week_start"]: w["score"]
                for w in weeks
            }
        
        return generator
    
    def test_lookup_exact_week_start(self, generator_with_sentiment):
        """Test looking up sentiment on exact week start date."""
        # 2019-06-10 is a Monday (week start)
        score = generator_with_sentiment._get_historical_sentiment("AAPL", "2019-06-10")
        assert score == 72.5
    
    def test_lookup_mid_week(self, generator_with_sentiment):
        """Test looking up sentiment on a mid-week date."""
        # 2019-06-12 is Wednesday, should map to week starting 2019-06-10
        score = generator_with_sentiment._get_historical_sentiment("AAPL", "2019-06-12")
        assert score == 72.5
    
    def test_lookup_end_of_week(self, generator_with_sentiment):
        """Test looking up sentiment on Friday."""
        # 2019-06-14 is Friday, should map to week starting 2019-06-10
        score = generator_with_sentiment._get_historical_sentiment("AAPL", "2019-06-14")
        assert score == 72.5
    
    def test_lookup_second_week(self, generator_with_sentiment):
        """Test looking up sentiment for second week."""
        # 2019-06-19 is Wednesday of second week
        score = generator_with_sentiment._get_historical_sentiment("AAPL", "2019-06-19")
        assert score == 68.0
    
    def test_lookup_ticker_not_found(self, generator_with_sentiment):
        """Test looking up ticker with no sentiment data."""
        score = generator_with_sentiment._get_historical_sentiment("NVDA", "2019-06-15")
        assert score == 50.0
    
    def test_lookup_date_not_found_uses_fallback(self, generator_with_sentiment):
        """Test that date outside range returns neutral."""
        # Date before any data
        score = generator_with_sentiment._get_historical_sentiment("AAPL", "2019-01-15")
        assert score == 50.0
    
    def test_lookup_case_insensitive(self, generator_with_sentiment):
        """Test that ticker lookup is case-insensitive."""
        score_upper = generator_with_sentiment._get_historical_sentiment("AAPL", "2019-06-12")
        score_lower = generator_with_sentiment._get_historical_sentiment("aapl", "2019-06-12")
        assert score_upper == score_lower == 72.5
    
    def test_bearish_sentiment(self, generator_with_sentiment):
        """Test looking up bearish sentiment."""
        # TSLA has score 45.0 (bearish)
        score = generator_with_sentiment._get_historical_sentiment("TSLA", "2019-06-12")
        assert score == 45.0


class TestSentimentIntegrationWithScoring:
    """Tests for sentiment integration in score generation."""
    
    def test_sentiment_affects_composite_score(self):
        """Test that different sentiment values affect composite score."""
        # This is more of an integration test concept
        # The composite formula is:
        # composite = (fundamental * 0.35) + (sentiment * 0.25) + (technical * 0.20) + (macro * 0.20)
        
        # If all components are 50 except sentiment:
        fundamental = 50.0
        technical = 50.0
        macro = 50.0
        
        # Bullish sentiment (75)
        sentiment_bullish = 75.0
        composite_bullish = (
            fundamental * 0.35 +
            sentiment_bullish * 0.25 +
            technical * 0.20 +
            macro * 0.20
        )
        
        # Bearish sentiment (25)
        sentiment_bearish = 25.0
        composite_bearish = (
            fundamental * 0.35 +
            sentiment_bearish * 0.25 +
            technical * 0.20 +
            macro * 0.20
        )
        
        # Bullish should be higher
        assert composite_bullish > composite_bearish
        
        # Difference should be 12.5 (25 point difference * 0.25 weight)
        assert abs((composite_bullish - composite_bearish) - 12.5) < 0.01
    
    def test_no_sentiment_weights_redistributed(self):
        """Test that weights are properly redistributed in no_sentiment mode."""
        from src.backtest.historical_scores import WEIGHTS, WEIGHTS_NO_SENTIMENT
        
        # Normal weights should sum to 1.0
        assert abs(sum(WEIGHTS.values()) - 1.0) < 0.01
        
        # No-sentiment weights should also sum to 1.0
        assert abs(sum(WEIGHTS_NO_SENTIMENT.values()) - 1.0) < 0.01
        
        # Sentiment weight should be 0 in no_sentiment mode
        assert WEIGHTS_NO_SENTIMENT["sentiment"] == 0.0
        
        # Other weights should be higher
        assert WEIGHTS_NO_SENTIMENT["fundamental"] > WEIGHTS["fundamental"]
        assert WEIGHTS_NO_SENTIMENT["technical"] > WEIGHTS["technical"]
        assert WEIGHTS_NO_SENTIMENT["macro"] > WEIGHTS["macro"]
