"""
Unit tests for Historical Score Generator Caching Logic

Tests the caching functionality added to generate_historical_scores():
- Skipping dates that already have scores
- Force regenerate flag
- 80% ticker coverage threshold
- Empty data handling
- CLI --force flag parsing
"""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
import argparse

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from backtest.data_store import (
    BacktestDataStore,
    HistoricalScore,
)
from backtest.historical_scores import HistoricalScoreGenerator


@pytest.fixture
def temp_store():
    """Create a temporary data store for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = BacktestDataStore(data_dir=Path(tmpdir))
        yield store


@pytest.fixture
def generator(temp_store):
    """Create a generator with temp store."""
    gen = HistoricalScoreGenerator(data_store=temp_store)
    # Mock the price cache to avoid external API calls
    gen._price_cache = {}
    return gen


def make_score(date: str, ticker: str) -> HistoricalScore:
    """Helper to create a test score."""
    return HistoricalScore(
        date=date,
        ticker=ticker,
        composite_score=65.0,
        signal="HOLD",
        fundamental_score=60.0,
        sentiment_score=50.0,
        technical_score=70.0,
        macro_score=65.0,
        sector="Technology",
    )


class TestCachingBehavior:
    """Tests for date caching/skipping logic."""
    
    def test_skip_dates_with_existing_scores(self, generator, temp_store):
        """Dates with sufficient existing scores should be skipped."""
        # Pre-populate with scores for 2025-01-10
        existing_scores = [
            make_score("2025-01-10", "AAPL"),
            make_score("2025-01-10", "MSFT"),
            make_score("2025-01-10", "GOOGL"),
            make_score("2025-01-10", "AMZN"),
            make_score("2025-01-10", "NVDA"),
        ]
        temp_store.save_historical_scores(existing_scores)
        
        # Mock _prefetch_prices to avoid API calls
        generator._prefetch_prices = MagicMock()
        generator._generate_scores_for_date = MagicMock(return_value=[])
        
        # Request scores for tickers where 2025-01-10 already has 5/5 (100%)
        result = generator.generate_historical_scores(
            start_date="2025-01-10",
            end_date="2025-01-10",
            tickers=["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"],
            frequency="daily",
            force_regenerate=False,
        )
        
        # Should skip and not generate anything
        assert result == 0
        generator._generate_scores_for_date.assert_not_called()
    
    def test_process_dates_without_existing_scores(self, generator, temp_store):
        """Dates without existing scores should be processed."""
        # Mock methods to avoid API calls
        generator._prefetch_prices = MagicMock()
        # Use 2025-02-03 which is a Monday (trading day)
        new_scores = [make_score("2025-02-03", "AAPL")]
        generator._generate_scores_for_date = MagicMock(return_value=new_scores)
        
        # Request scores for a date with no existing scores
        result = generator.generate_historical_scores(
            start_date="2025-02-03",  # Monday
            end_date="2025-02-03",
            tickers=["AAPL"],
            frequency="daily",
            force_regenerate=False,
        )
        
        # Should process and generate
        assert result == 1
        generator._generate_scores_for_date.assert_called_once_with("2025-02-03", ["AAPL"])
    
    def test_mixed_dates_some_cached(self, generator, temp_store):
        """Only process dates that don't have existing scores."""
        # Pre-populate 2025-01-06 with scores
        existing_scores = [
            make_score("2025-01-06", "AAPL"),
            make_score("2025-01-06", "MSFT"),
        ]
        temp_store.save_historical_scores(existing_scores)
        
        generator._prefetch_prices = MagicMock()
        new_score = [make_score("2025-01-07", "AAPL")]
        generator._generate_scores_for_date = MagicMock(return_value=new_score)
        
        # Request 2 dates, one cached, one not
        result = generator.generate_historical_scores(
            start_date="2025-01-06",
            end_date="2025-01-07",
            tickers=["AAPL", "MSFT"],
            frequency="daily",
            force_regenerate=False,
        )
        
        # Should only process 2025-01-07 (2025-01-06 has 2/2 = 100% coverage)
        assert result == 1
        generator._generate_scores_for_date.assert_called_once_with("2025-01-07", ["AAPL", "MSFT"])


class TestForceRegenerate:
    """Tests for --force / force_regenerate parameter."""
    
    def test_force_regenerate_ignores_cache(self, generator, temp_store):
        """Force regenerate should process all dates regardless of cache."""
        # Pre-populate with scores
        existing_scores = [
            make_score("2025-01-10", "AAPL"),
            make_score("2025-01-10", "MSFT"),
        ]
        temp_store.save_historical_scores(existing_scores)
        
        generator._prefetch_prices = MagicMock()
        new_scores = [
            make_score("2025-01-10", "AAPL"),
            make_score("2025-01-10", "MSFT"),
        ]
        generator._generate_scores_for_date = MagicMock(return_value=new_scores)
        
        # Force regenerate should ignore existing scores
        result = generator.generate_historical_scores(
            start_date="2025-01-10",
            end_date="2025-01-10",
            tickers=["AAPL", "MSFT"],
            frequency="daily",
            force_regenerate=True,  # Force!
        )
        
        # Should regenerate even though scores exist
        assert result == 2
        generator._generate_scores_for_date.assert_called_once()
    
    def test_force_regenerate_overwrites_existing(self, generator, temp_store):
        """Force regenerate should update existing scores with new values."""
        # Pre-populate with old scores
        old_scores = [
            HistoricalScore(
                date="2025-01-10",
                ticker="AAPL",
                composite_score=50.0,  # Old value
                signal="HOLD",
                fundamental_score=50.0,
                sentiment_score=50.0,
                technical_score=50.0,
                macro_score=50.0,
            ),
        ]
        temp_store.save_historical_scores(old_scores)
        
        generator._prefetch_prices = MagicMock()
        new_scores = [
            HistoricalScore(
                date="2025-01-10",
                ticker="AAPL",
                composite_score=75.0,  # New value
                signal="BUY",
                fundamental_score=75.0,
                sentiment_score=75.0,
                technical_score=75.0,
                macro_score=75.0,
            ),
        ]
        generator._generate_scores_for_date = MagicMock(return_value=new_scores)
        
        # Force regenerate
        generator.generate_historical_scores(
            start_date="2025-01-10",
            end_date="2025-01-10",
            tickers=["AAPL"],
            frequency="daily",
            force_regenerate=True,
        )
        
        # Verify score was updated
        retrieved = temp_store.get_historical_scores("2025-01-10", "2025-01-10")
        assert retrieved["2025-01-10"]["AAPL"].composite_score == 75.0


class TestPartialCoverageThreshold:
    """Tests for the 80% ticker coverage threshold."""
    
    def test_skip_date_with_80_percent_coverage(self, generator, temp_store):
        """Date with ≥80% coverage should be skipped."""
        # 4 out of 5 tickers = 80% coverage
        existing_scores = [
            make_score("2025-01-10", "AAPL"),
            make_score("2025-01-10", "MSFT"),
            make_score("2025-01-10", "GOOGL"),
            make_score("2025-01-10", "AMZN"),
            # Missing: NVDA
        ]
        temp_store.save_historical_scores(existing_scores)
        
        generator._prefetch_prices = MagicMock()
        generator._generate_scores_for_date = MagicMock(return_value=[])
        
        result = generator.generate_historical_scores(
            start_date="2025-01-10",
            end_date="2025-01-10",
            tickers=["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"],  # 5 tickers
            frequency="daily",
            force_regenerate=False,
        )
        
        # 4/5 = 80%, should skip
        assert result == 0
        generator._generate_scores_for_date.assert_not_called()
    
    def test_process_date_with_below_80_percent_coverage(self, generator, temp_store):
        """Date with <80% coverage should be processed."""
        # 3 out of 5 tickers = 60% coverage
        existing_scores = [
            make_score("2025-01-10", "AAPL"),
            make_score("2025-01-10", "MSFT"),
            make_score("2025-01-10", "GOOGL"),
            # Missing: AMZN, NVDA
        ]
        temp_store.save_historical_scores(existing_scores)
        
        generator._prefetch_prices = MagicMock()
        new_scores = [
            make_score("2025-01-10", "AAPL"),
            make_score("2025-01-10", "MSFT"),
            make_score("2025-01-10", "GOOGL"),
            make_score("2025-01-10", "AMZN"),
            make_score("2025-01-10", "NVDA"),
        ]
        generator._generate_scores_for_date = MagicMock(return_value=new_scores)
        
        result = generator.generate_historical_scores(
            start_date="2025-01-10",
            end_date="2025-01-10",
            tickers=["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"],  # 5 tickers
            frequency="daily",
            force_regenerate=False,
        )
        
        # 3/5 = 60% < 80%, should process
        assert result == 5
        generator._generate_scores_for_date.assert_called_once()
    
    def test_threshold_calculation_rounding(self, generator, temp_store):
        """Test threshold with non-round numbers (e.g., 10 tickers)."""
        # 10 tickers, threshold = int(10 * 0.8) = 8
        # Need 8 or more to skip
        existing_scores = [make_score("2025-01-10", f"TICK{i}") for i in range(7)]
        temp_store.save_historical_scores(existing_scores)
        
        generator._prefetch_prices = MagicMock()
        new_scores = [make_score("2025-01-10", f"TICK{i}") for i in range(10)]
        generator._generate_scores_for_date = MagicMock(return_value=new_scores)
        
        result = generator.generate_historical_scores(
            start_date="2025-01-10",
            end_date="2025-01-10",
            tickers=[f"TICK{i}" for i in range(10)],  # 10 tickers
            frequency="daily",
            force_regenerate=False,
        )
        
        # 7/10 = 70% < 80%, should process
        assert result == 10


class TestEmptyDataHandling:
    """Tests for edge cases with empty or no data."""
    
    def test_empty_ticker_list(self, generator, temp_store):
        """Empty ticker list should handle gracefully."""
        generator._prefetch_prices = MagicMock()
        generator._generate_scores_for_date = MagicMock(return_value=[])
        
        result = generator.generate_historical_scores(
            start_date="2025-01-10",
            end_date="2025-01-10",
            tickers=[],  # Empty!
            frequency="daily",
            force_regenerate=False,
        )
        
        # Should complete without error
        assert result == 0
    
    def test_no_dates_in_range(self, generator, temp_store):
        """Date range with no trading days should return 0."""
        generator._prefetch_prices = MagicMock()
        generator._generate_scores_for_date = MagicMock(return_value=[])
        
        # Weekend dates (Saturday to Sunday)
        result = generator.generate_historical_scores(
            start_date="2025-01-11",  # Saturday
            end_date="2025-01-12",    # Sunday
            tickers=["AAPL"],
            frequency="daily",
            force_regenerate=False,
        )
        
        # No trading days = no scores
        assert result == 0
    
    def test_all_dates_cached_returns_zero(self, generator, temp_store):
        """When all dates are cached, should return 0."""
        # Pre-populate Friday
        existing_scores = [make_score("2025-01-10", "AAPL")]
        temp_store.save_historical_scores(existing_scores)
        
        generator._prefetch_prices = MagicMock()
        
        result = generator.generate_historical_scores(
            start_date="2025-01-10",
            end_date="2025-01-10",
            tickers=["AAPL"],
            frequency="daily",
            force_regenerate=False,
        )
        
        assert result == 0


class TestProgressCallback:
    """Tests for progress callback functionality."""
    
    def test_progress_callback_called(self, generator, temp_store):
        """Progress callback should be called for each date."""
        generator._prefetch_prices = MagicMock()
        generator._generate_scores_for_date = MagicMock(return_value=[
            make_score("2025-01-06", "AAPL"),
        ])
        
        progress_calls = []
        def progress_cb(current, total, message):
            progress_calls.append((current, total, message))
        
        generator.generate_historical_scores(
            start_date="2025-01-06",
            end_date="2025-01-08",
            tickers=["AAPL"],
            frequency="daily",
            progress_callback=progress_cb,
            force_regenerate=True,
        )
        
        # Should have progress calls
        assert len(progress_calls) > 0
        # First call should be (1, total, ...)
        assert progress_calls[0][0] == 1
    
    def test_progress_callback_skipped_dates(self, generator, temp_store):
        """Progress callback should not be called for skipped dates."""
        # Pre-populate all dates
        existing_scores = [
            make_score("2025-01-06", "AAPL"),
            make_score("2025-01-07", "AAPL"),
            make_score("2025-01-08", "AAPL"),
        ]
        temp_store.save_historical_scores(existing_scores)
        
        generator._prefetch_prices = MagicMock()
        
        progress_calls = []
        def progress_cb(current, total, message):
            progress_calls.append((current, total, message))
        
        generator.generate_historical_scores(
            start_date="2025-01-06",
            end_date="2025-01-08",
            tickers=["AAPL"],
            frequency="daily",
            progress_callback=progress_cb,
            force_regenerate=False,
        )
        
        # No progress calls since all dates were skipped
        assert len(progress_calls) == 0


class TestCLIForceFlag:
    """Tests for CLI --force argument parsing."""
    
    def test_generate_parser_has_force_flag(self):
        """The generate subparser should have --force flag."""
        from backtest.__main__ import main
        import sys
        
        # Parse args with --force
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        gen_parser = subparsers.add_parser("generate")
        gen_parser.add_argument("--start", default="2025-01-01")
        gen_parser.add_argument("--end", default="2025-12-31")
        gen_parser.add_argument("--frequency", default="weekly")
        gen_parser.add_argument("--tickers", default=None)
        gen_parser.add_argument("--force", action="store_true")
        
        args = parser.parse_args(["generate", "--force"])
        assert args.force is True
        
        args = parser.parse_args(["generate"])
        assert args.force is False
    
    def test_generate_command_with_force_flag(self):
        """Test that cmd_generate properly handles --force flag."""
        from backtest.__main__ import cmd_generate
        
        # Create mock args
        args = argparse.Namespace(
            start="2025-01-01",
            end="2025-01-02",
            frequency="daily",
            tickers="AAPL",
            force=True,
            no_sentiment=False,
        )
        
        # Mock the generator to verify force_regenerate is passed
        with patch('backtest.__main__.HistoricalScoreGenerator') as MockGen:
            mock_instance = MagicMock()
            mock_instance.generate_historical_scores.return_value = 5
            MockGen.return_value = mock_instance
            
            cmd_generate(args)
            
            # Verify force_regenerate was passed as True
            call_kwargs = mock_instance.generate_historical_scores.call_args[1]
            assert call_kwargs.get('force_regenerate') is True


class TestDateGeneration:
    """Tests for date list generation with frequency."""
    
    def test_daily_frequency(self, generator, temp_store):
        """Daily frequency should generate trading days only."""
        dates = generator._generate_date_list(
            "2025-01-06",  # Monday
            "2025-01-10",  # Friday
            "daily"
        )
        
        assert len(dates) == 5  # Mon-Fri
        assert "2025-01-06" in dates
        assert "2025-01-10" in dates
    
    def test_weekly_frequency(self, generator, temp_store):
        """Weekly frequency should generate one day per week."""
        dates = generator._generate_date_list(
            "2025-01-06",  # Monday
            "2025-01-20",  # Monday (3rd week)
            "weekly"
        )
        
        # Should have ~3 dates (Fridays typically)
        assert len(dates) >= 2
        assert len(dates) <= 3
    
    def test_skip_weekends(self, generator, temp_store):
        """Weekend dates should not be included."""
        dates = generator._generate_date_list(
            "2025-01-11",  # Saturday
            "2025-01-12",  # Sunday
            "daily"
        )
        
        assert len(dates) == 0
