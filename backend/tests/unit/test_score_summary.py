"""
Tests for F9.1 Weekly Score Summary

Tests the score summary endpoint, signal counts, and movers detection.
"""

import pytest
import json
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from scoring.composite_score import (
    CompositeScoreResult,
    Signal,
    save_composite_scores,
    load_composite_scores,
    COMPOSITE_CACHE,
)


# ========== Score Summary Logic Tests ==========

class TestScoreSummary:
    """Tests for score summary data extraction."""

    @pytest.fixture
    def mock_scores(self):
        """Create mock composite scores for testing."""
        return {
            "AAPL": CompositeScoreResult(
                ticker="AAPL", sector="Technology",
                total_score=75.0, signal=Signal.BUY,
                rank=1, percentile=95.0,
                fundamental_score=80.0, sentiment_score=70.0,
                technical_score=75.0, macro_score=72.0,
                score_change=5.0, signal_change="HOLD → BUY",
                details={},
            ),
            "MSFT": CompositeScoreResult(
                ticker="MSFT", sector="Technology",
                total_score=72.0, signal=Signal.BUY,
                rank=2, percentile=90.0,
                fundamental_score=75.0, sentiment_score=68.0,
                technical_score=73.0, macro_score=72.0,
                score_change=2.0, signal_change=None,
                details={},
            ),
            "XOM": CompositeScoreResult(
                ticker="XOM", sector="Energy",
                total_score=55.0, signal=Signal.HOLD,
                rank=10, percentile=50.0,
                fundamental_score=60.0, sentiment_score=50.0,
                technical_score=55.0, macro_score=52.0,
                score_change=-3.0, signal_change=None,
                details={},
            ),
            "GE": CompositeScoreResult(
                ticker="GE", sector="Industrials",
                total_score=35.0, signal=Signal.SELL,
                rank=20, percentile=20.0,
                fundamental_score=30.0, sentiment_score=40.0,
                technical_score=35.0, macro_score=32.0,
                score_change=-10.0, signal_change="HOLD → SELL",
                details={},
            ),
        }

    def test_save_and_load_scores(self, mock_scores, tmp_path):
        """Test saving and loading composite scores."""
        path = tmp_path / "scores.json"
        save_composite_scores(mock_scores, path=path)

        loaded = load_composite_scores(path=path)

        assert loaded is not None
        assert loaded["count"] == 4
        assert "AAPL" in loaded["scores"]

    def test_summary_contains_signal_counts(self, mock_scores, tmp_path):
        """Summary should contain BUY/HOLD/SELL counts."""
        path = tmp_path / "scores.json"
        save_composite_scores(mock_scores, path=path)

        loaded = load_composite_scores(path=path)
        summary = loaded["summary"]

        assert summary["buy_count"] == 2  # AAPL, MSFT
        assert summary["hold_count"] == 1  # XOM
        assert summary["sell_count"] == 1  # GE

    def test_movers_detection(self, mock_scores, tmp_path):
        """Should detect stocks with score changes."""
        path = tmp_path / "scores.json"
        save_composite_scores(mock_scores, path=path)

        loaded = load_composite_scores(path=path)
        scores = loaded["scores"]

        # Find movers (non-zero score_change)
        movers = [
            s for s in scores.values()
            if s.get("score_change") is not None and s["score_change"] != 0
        ]

        assert len(movers) == 4  # All have score_change != 0

        # Sort by absolute change
        movers.sort(key=lambda x: abs(x["score_change"]), reverse=True)
        assert movers[0]["ticker"] == "GE"  # -10 is biggest absolute change

    def test_new_buy_signals_detection(self, mock_scores, tmp_path):
        """Should detect stocks that changed to BUY signal."""
        path = tmp_path / "scores.json"
        save_composite_scores(mock_scores, path=path)

        loaded = load_composite_scores(path=path)
        scores = loaded["scores"]

        new_buys = [
            s for s in scores.values()
            if s.get("signal_change") and "BUY" in s["signal_change"].split("→")[-1]
        ]

        assert len(new_buys) == 1
        assert new_buys[0]["ticker"] == "AAPL"

    def test_no_scores_available(self, tmp_path):
        """Should return None when no scores file exists."""
        path = tmp_path / "nonexistent.json"
        loaded = load_composite_scores(path=path)
        assert loaded is None

    def test_score_change_zero(self, tmp_path):
        """Stocks with zero score change should not be movers."""
        scores = {
            "AAPL": CompositeScoreResult(
                ticker="AAPL", sector="Technology",
                total_score=75.0, signal=Signal.BUY,
                rank=1, percentile=95.0,
                fundamental_score=80.0, sentiment_score=70.0,
                technical_score=75.0, macro_score=72.0,
                score_change=0, signal_change=None,
                details={},
            ),
        }

        path = tmp_path / "scores.json"
        save_composite_scores(scores, path=path)
        loaded = load_composite_scores(path=path)

        movers = [
            s for s in loaded["scores"].values()
            if s.get("score_change") is not None and s["score_change"] != 0
        ]
        assert len(movers) == 0

    def test_score_change_none(self, tmp_path):
        """Stocks with None score change should be handled gracefully."""
        scores = {
            "AAPL": CompositeScoreResult(
                ticker="AAPL", sector="Technology",
                total_score=75.0, signal=Signal.BUY,
                rank=1, percentile=95.0,
                fundamental_score=80.0, sentiment_score=70.0,
                technical_score=75.0, macro_score=72.0,
                score_change=None, signal_change=None,
                details={},
            ),
        }

        path = tmp_path / "scores.json"
        save_composite_scores(scores, path=path)
        loaded = load_composite_scores(path=path)

        movers = [
            s for s in loaded["scores"].values()
            if s.get("score_change") is not None and s["score_change"] != 0
        ]
        assert len(movers) == 0

    def test_summary_notification_body_format(self, mock_scores, tmp_path):
        """The notification body can be constructed from summary data."""
        path = tmp_path / "scores.json"
        save_composite_scores(mock_scores, path=path)

        loaded = load_composite_scores(path=path)
        summary = loaded["summary"]

        body = f"New scores available. {summary['buy_count']} BUY signals"
        assert "2 BUY signals" in body

    def test_scores_contain_all_fields(self, mock_scores, tmp_path):
        """Each score should have all required fields for the summary."""
        path = tmp_path / "scores.json"
        save_composite_scores(mock_scores, path=path)

        loaded = load_composite_scores(path=path)

        for ticker, score in loaded["scores"].items():
            assert "ticker" in score
            assert "total_score" in score
            assert "signal" in score
            assert "score_change" in score
            assert "signal_change" in score


# ========== Run Tests ==========

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
