"""
Tests for F5.5 Score History Service.
"""

import pytest
import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock
import tempfile
import shutil

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


class TestScoreHistoryService:
    """Tests for score history storage and retrieval."""

    @pytest.fixture
    def temp_data_dir(self):
        """Create a temporary data directory."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def mock_history_file(self, temp_data_dir):
        """Patch the history file location."""
        with patch('scoring.score_history.SCORE_HISTORY_FILE', temp_data_dir / "score_history.json"):
            with patch('scoring.score_history.DATA_DIR', temp_data_dir):
                yield temp_data_dir / "score_history.json"

    def test_load_history_empty(self, mock_history_file):
        """Test loading when no history file exists."""
        from scoring.score_history import ScoreHistoryService
        
        history = ScoreHistoryService.load_history()
        assert history == {}

    def test_save_and_load_history(self, mock_history_file):
        """Test saving and loading history."""
        from scoring.score_history import ScoreHistoryService
        
        test_data = {
            "AAPL": [
                {"date": "2026-02-01", "total_score": 75.0, "signal": "BUY"}
            ]
        }
        
        ScoreHistoryService.save_history(test_data)
        loaded = ScoreHistoryService.load_history()
        
        assert loaded == test_data

    def test_record_pipeline_run(self, mock_history_file):
        """Test recording scores from a pipeline run."""
        from scoring.score_history import ScoreHistoryService
        
        scores = {
            "AAPL": {
                "total_score": 75.5,
                "signal": "BUY",
                "fundamental_score": 60,
                "sentiment_score": 70,
                "technical_score": 80,
                "macro_score": 90,
            },
            "GOOGL": {
                "total_score": 45.0,
                "signal": "HOLD",
                "fundamental_score": 40,
                "sentiment_score": 50,
                "technical_score": 45,
                "macro_score": 45,
            }
        }
        
        recorded = ScoreHistoryService.record_pipeline_run(scores)
        
        assert recorded == 2
        
        # Verify data was saved
        history = ScoreHistoryService.load_history()
        assert "AAPL" in history
        assert len(history["AAPL"]) == 1
        assert history["AAPL"][0]["total_score"] == 75.5
        assert history["AAPL"][0]["signal"] == "BUY"

    def test_record_pipeline_run_updates_same_day(self, mock_history_file):
        """Test that recording on same day updates existing entry."""
        from scoring.score_history import ScoreHistoryService
        
        # First run
        ScoreHistoryService.record_pipeline_run({
            "AAPL": {"total_score": 70.0, "signal": "BUY"}
        })
        
        # Second run same day
        ScoreHistoryService.record_pipeline_run({
            "AAPL": {"total_score": 75.0, "signal": "BUY"}
        })
        
        history = ScoreHistoryService.load_history()
        
        # Should still have only 1 entry (updated)
        assert len(history["AAPL"]) == 1
        assert history["AAPL"][0]["total_score"] == 75.0

    def test_get_ticker_history(self, mock_history_file):
        """Test retrieving history for a specific ticker."""
        from scoring.score_history import ScoreHistoryService
        
        today = datetime.now().strftime("%Y-%m-%d")
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        
        test_data = {
            "AAPL": [
                {"date": today, "total_score": 75.0, "signal": "BUY"},
                {"date": yesterday, "total_score": 72.0, "signal": "BUY"},
            ]
        }
        ScoreHistoryService.save_history(test_data)
        
        history = ScoreHistoryService.get_ticker_history("AAPL", days=7)
        
        assert len(history) == 2
        # Should be sorted oldest first
        assert history[0]["date"] == yesterday
        assert history[1]["date"] == today

    def test_get_ticker_history_case_insensitive(self, mock_history_file):
        """Test that ticker lookup is case insensitive."""
        from scoring.score_history import ScoreHistoryService
        
        today = datetime.now().strftime("%Y-%m-%d")
        ScoreHistoryService.save_history({
            "AAPL": [{"date": today, "total_score": 75.0, "signal": "BUY"}]
        })
        
        # Query with lowercase
        history = ScoreHistoryService.get_ticker_history("aapl", days=7)
        assert len(history) == 1

    def test_get_signal_changes(self, mock_history_file):
        """Test detecting signal changes."""
        from scoring.score_history import ScoreHistoryService
        
        d1 = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
        d2 = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
        d3 = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        
        test_data = {
            "AAPL": [
                {"date": d3, "total_score": 75.0, "signal": "BUY"},
                {"date": d2, "total_score": 65.0, "signal": "HOLD"},  # Changed from HOLD to BUY
                {"date": d1, "total_score": 55.0, "signal": "HOLD"},
            ]
        }
        ScoreHistoryService.save_history(test_data)
        
        changes = ScoreHistoryService.get_signal_changes("AAPL", days=7)
        
        assert len(changes) == 1
        assert changes[0]["from_signal"] == "HOLD"
        assert changes[0]["to_signal"] == "BUY"
        assert changes[0]["date"] == d3

    def test_get_signal_changes_no_changes(self, mock_history_file):
        """Test when there are no signal changes."""
        from scoring.score_history import ScoreHistoryService
        
        d1 = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
        d2 = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        
        test_data = {
            "AAPL": [
                {"date": d2, "total_score": 75.0, "signal": "BUY"},
                {"date": d1, "total_score": 72.0, "signal": "BUY"},
            ]
        }
        ScoreHistoryService.save_history(test_data)
        
        changes = ScoreHistoryService.get_signal_changes("AAPL", days=7)
        
        assert len(changes) == 0

    def test_backfill_from_current(self, mock_history_file):
        """Test backfilling history from current scores."""
        from scoring.score_history import ScoreHistoryService
        
        current_scores = {
            "AAPL": {
                "total_score": 75.0,
                "signal": "BUY",
                "fundamental_score": 60,
                "sentiment_score": 70,
                "technical_score": 80,
                "macro_score": 90,
            }
        }
        
        recorded = ScoreHistoryService.backfill_from_current(current_scores, days=7)
        
        # Should have recorded entries for past 7 days
        assert recorded == 7
        
        history = ScoreHistoryService.get_ticker_history("AAPL", days=14)
        assert len(history) == 7
        
        # All scores should be close to 75 (with small variance)
        for entry in history:
            assert 70 <= entry["total_score"] <= 80

    def test_history_limit_90_days(self, mock_history_file):
        """Test that history is limited to 90 days per ticker."""
        from scoring.score_history import ScoreHistoryService
        
        # Create 100 days of history
        history = {
            "AAPL": [
                {"date": (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d"), 
                 "total_score": 50.0, "signal": "HOLD"}
                for i in range(100)
            ]
        }
        ScoreHistoryService.save_history(history)
        
        # Add one more via record
        ScoreHistoryService.record_pipeline_run({
            "AAPL": {"total_score": 55.0, "signal": "HOLD"}
        })
        
        final = ScoreHistoryService.load_history()
        
        # Should be capped at 90
        assert len(final["AAPL"]) == 90


class TestScoreHistoryAPI:
    """Integration tests for score history API endpoint."""

    def test_score_history_response_format(self):
        """Test API response has correct format."""
        # This would be an integration test with the actual API
        pass
