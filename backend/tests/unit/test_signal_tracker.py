"""
Tests for F9.3 Signal Tracker

Tests detection of signal changes: HOLD→BUY, BUY→SELL, no change, etc.
"""

import pytest
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from scoring.signal_tracker import (
    detect_signal_changes,
    save_previous_scores,
    load_previous_scores,
)


# ========== Signal Change Detection Tests ==========

class TestSignalChangeDetection:
    """Tests for detecting signal changes between scoring runs."""

    def test_hold_to_buy(self):
        """Detect HOLD → BUY transition."""
        previous = {
            "scores": {
                "AAPL": {"ticker": "AAPL", "total_score": 55.0, "signal": "HOLD"},
            }
        }
        current = {
            "AAPL": {"ticker": "AAPL", "total_score": 75.0, "signal": "BUY"},
        }

        changes = detect_signal_changes(current, previous)

        assert len(changes) == 1
        assert changes[0]["ticker"] == "AAPL"
        assert changes[0]["old_signal"] == "HOLD"
        assert changes[0]["new_signal"] == "BUY"
        assert changes[0]["score_change"] == 20.0

    def test_buy_to_sell(self):
        """Detect BUY → SELL transition."""
        previous = {
            "scores": {
                "TSLA": {"ticker": "TSLA", "total_score": 72.0, "signal": "BUY"},
            }
        }
        current = {
            "TSLA": {"ticker": "TSLA", "total_score": 35.0, "signal": "SELL"},
        }

        changes = detect_signal_changes(current, previous)

        assert len(changes) == 1
        assert changes[0]["old_signal"] == "BUY"
        assert changes[0]["new_signal"] == "SELL"
        assert changes[0]["score_change"] == -37.0

    def test_sell_to_hold(self):
        """Detect SELL → HOLD transition."""
        previous = {
            "scores": {
                "GE": {"ticker": "GE", "total_score": 30.0, "signal": "SELL"},
            }
        }
        current = {
            "GE": {"ticker": "GE", "total_score": 50.0, "signal": "HOLD"},
        }

        changes = detect_signal_changes(current, previous)

        assert len(changes) == 1
        assert changes[0]["old_signal"] == "SELL"
        assert changes[0]["new_signal"] == "HOLD"

    def test_no_change(self):
        """No change when signals remain the same."""
        previous = {
            "scores": {
                "AAPL": {"ticker": "AAPL", "total_score": 75.0, "signal": "BUY"},
            }
        }
        current = {
            "AAPL": {"ticker": "AAPL", "total_score": 78.0, "signal": "BUY"},
        }

        changes = detect_signal_changes(current, previous)
        assert len(changes) == 0

    def test_multiple_changes(self):
        """Detect changes across multiple stocks."""
        previous = {
            "scores": {
                "AAPL": {"ticker": "AAPL", "total_score": 55.0, "signal": "HOLD"},
                "MSFT": {"ticker": "MSFT", "total_score": 72.0, "signal": "BUY"},
                "GE": {"ticker": "GE", "total_score": 45.0, "signal": "HOLD"},
                "XOM": {"ticker": "XOM", "total_score": 60.0, "signal": "HOLD"},
            }
        }
        current = {
            "AAPL": {"ticker": "AAPL", "total_score": 75.0, "signal": "BUY"},
            "MSFT": {"ticker": "MSFT", "total_score": 35.0, "signal": "SELL"},
            "GE": {"ticker": "GE", "total_score": 48.0, "signal": "HOLD"},
            "XOM": {"ticker": "XOM", "total_score": 65.0, "signal": "HOLD"},
        }

        changes = detect_signal_changes(current, previous)

        assert len(changes) == 2  # AAPL and MSFT changed
        tickers = [c["ticker"] for c in changes]
        assert "AAPL" in tickers
        assert "MSFT" in tickers
        assert "GE" not in tickers  # No signal change

    def test_new_stock_no_previous(self):
        """New stocks without previous data should not be flagged."""
        previous = {
            "scores": {}
        }
        current = {
            "AAPL": {"ticker": "AAPL", "total_score": 75.0, "signal": "BUY"},
        }

        changes = detect_signal_changes(current, previous)
        assert len(changes) == 0

    def test_no_previous_data(self):
        """Should return empty list when no previous data exists."""
        current = {
            "AAPL": {"ticker": "AAPL", "total_score": 75.0, "signal": "BUY"},
        }

        changes = detect_signal_changes(current, None)
        assert len(changes) == 0

    def test_sorted_by_score_change(self):
        """Changes should be sorted by absolute score change."""
        previous = {
            "scores": {
                "AAPL": {"ticker": "AAPL", "total_score": 55.0, "signal": "HOLD"},
                "TSLA": {"ticker": "TSLA", "total_score": 72.0, "signal": "BUY"},
            }
        }
        current = {
            "AAPL": {"ticker": "AAPL", "total_score": 75.0, "signal": "BUY"},  # +20
            "TSLA": {"ticker": "TSLA", "total_score": 35.0, "signal": "SELL"},  # -37
        }

        changes = detect_signal_changes(current, previous)

        assert changes[0]["ticker"] == "TSLA"  # Biggest absolute change first

    def test_score_change_calculation(self):
        """Score change should be correctly calculated."""
        previous = {
            "scores": {
                "AAPL": {"ticker": "AAPL", "total_score": 50.0, "signal": "HOLD"},
            }
        }
        current = {
            "AAPL": {"ticker": "AAPL", "total_score": 72.5, "signal": "BUY"},
        }

        changes = detect_signal_changes(current, previous)

        assert changes[0]["score_change"] == 22.5
        assert changes[0]["old_score"] == 50.0
        assert changes[0]["new_score"] == 72.5


# ========== Persistence Tests ==========

class TestSignalTrackerPersistence:
    """Tests for saving/loading previous scores."""

    def test_save_and_load(self, tmp_path, monkeypatch):
        """Save and load previous scores."""
        import scoring.signal_tracker as st
        monkeypatch.setattr(st, "PREVIOUS_SCORES_FILE", tmp_path / "prev.json")

        scores = {
            "AAPL": {"total_score": 75.0, "signal": "BUY"},
            "MSFT": {"total_score": 55.0, "signal": "HOLD"},
        }

        save_previous_scores(scores)
        loaded = load_previous_scores()

        assert loaded is not None
        assert "AAPL" in loaded["scores"]
        assert loaded["scores"]["AAPL"]["signal"] == "BUY"
        assert loaded["scores"]["MSFT"]["total_score"] == 55.0

    def test_load_nonexistent(self, tmp_path, monkeypatch):
        """Loading from nonexistent file returns None."""
        import scoring.signal_tracker as st
        monkeypatch.setattr(st, "PREVIOUS_SCORES_FILE", tmp_path / "nonexistent.json")

        result = load_previous_scores()
        assert result is None

    def test_save_includes_timestamp(self, tmp_path, monkeypatch):
        """Saved data should include a timestamp."""
        import scoring.signal_tracker as st
        monkeypatch.setattr(st, "PREVIOUS_SCORES_FILE", tmp_path / "prev.json")

        save_previous_scores({"AAPL": {"total_score": 75.0, "signal": "BUY"}})
        loaded = load_previous_scores()

        assert "saved_at" in loaded


# ========== Run Tests ==========

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
