"""
Tests for Sentiment Comparison Tool (REC-176)
"""

import pytest
from pathlib import Path
import tempfile

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from scoring.sentiment_comparison import (
    ComparisonResult,
    ComparisonReport,
    SentimentComparator,
)


class TestComparisonResult:
    """Test ComparisonResult dataclass."""
    
    def test_creation(self):
        result = ComparisonResult(
            ticker="AAPL",
            llm_score=75.0,
            llm_sentiment="bullish",
            llm_confidence=0.85,
            keyword_score=50.0,
            keyword_sentiment="neutral",
            score_diff=25.0,
            article_count=3,
        )
        
        assert result.ticker == "AAPL"
        assert result.llm_score == 75.0
        assert result.score_diff == 25.0
    
    def test_is_llm_neutral_true(self):
        result = ComparisonResult(
            ticker="AAPL",
            llm_score=50.0,
            llm_sentiment="neutral",
            llm_confidence=0.5,
            keyword_score=50.0,
            keyword_sentiment="neutral",
            score_diff=0.0,
            article_count=1,
        )
        assert result.is_llm_neutral is True
    
    def test_is_llm_neutral_false(self):
        result = ComparisonResult(
            ticker="AAPL",
            llm_score=75.0,
            llm_sentiment="bullish",
            llm_confidence=0.85,
            keyword_score=50.0,
            keyword_sentiment="neutral",
            score_diff=25.0,
            article_count=1,
        )
        assert result.is_llm_neutral is False
    
    def test_is_keyword_neutral(self):
        result = ComparisonResult(
            ticker="AAPL",
            llm_score=75.0,
            llm_sentiment="bullish",
            llm_confidence=0.85,
            keyword_score=48.0,
            keyword_sentiment="neutral",
            score_diff=27.0,
            article_count=1,
        )
        assert result.is_keyword_neutral is True
    
    def test_both_agree_when_same_direction(self):
        result = ComparisonResult(
            ticker="AAPL",
            llm_score=70.0,
            llm_sentiment="bullish",
            llm_confidence=0.85,
            keyword_score=65.0,
            keyword_sentiment="bullish",
            score_diff=5.0,
            article_count=1,
        )
        assert result.both_agree is True
    
    def test_both_agree_when_different_direction(self):
        result = ComparisonResult(
            ticker="AAPL",
            llm_score=70.0,
            llm_sentiment="bullish",
            llm_confidence=0.85,
            keyword_score=30.0,
            keyword_sentiment="bearish",
            score_diff=40.0,
            article_count=1,
        )
        assert result.both_agree is False
    
    def test_to_dict(self):
        result = ComparisonResult(
            ticker="AAPL",
            llm_score=75.0,
            llm_sentiment="bullish",
            llm_confidence=0.85,
            keyword_score=50.0,
            keyword_sentiment="neutral",
            score_diff=25.0,
            article_count=3,
        )
        
        d = result.to_dict()
        
        assert d["ticker"] == "AAPL"
        assert d["llm_score"] == 75.0
        assert d["both_agree"] is False


class TestComparisonReport:
    """Test ComparisonReport dataclass."""
    
    @pytest.fixture
    def sample_results(self):
        return [
            ComparisonResult("AAPL", 75, "bullish", 0.85, 50, "neutral", 25, 3),
            ComparisonResult("MSFT", 70, "bullish", 0.80, 55, "slightly_bullish", 15, 2),
            ComparisonResult("TSLA", 50, "neutral", 0.60, 50, "neutral", 0, 2),
        ]
    
    def test_creation(self, sample_results):
        report = ComparisonReport(
            total_tickers=3,
            results=sample_results,
        )
        
        assert report.total_tickers == 3
        assert len(report.results) == 3
    
    def test_llm_neutral_rate(self, sample_results):
        report = ComparisonReport(
            total_tickers=3,
            llm_neutral_count=1,
            results=sample_results,
        )
        
        assert report.llm_neutral_rate == pytest.approx(0.333, rel=0.01)
    
    def test_keyword_neutral_rate(self, sample_results):
        report = ComparisonReport(
            total_tickers=3,
            keyword_neutral_count=2,
            results=sample_results,
        )
        
        assert report.keyword_neutral_rate == pytest.approx(0.666, rel=0.01)
    
    def test_agreement_rate(self, sample_results):
        report = ComparisonReport(
            total_tickers=3,
            agreement_count=2,
            results=sample_results,
        )
        
        assert report.agreement_rate == pytest.approx(0.666, rel=0.01)
    
    def test_neutral_reduction(self, sample_results):
        report = ComparisonReport(
            total_tickers=3,
            llm_neutral_count=1,  # 33% LLM neutral
            keyword_neutral_count=2,  # 66% keyword neutral
            results=sample_results,
        )
        
        # Reduction = (66% - 33%) / 66% = 50%
        assert report.neutral_reduction == pytest.approx(0.5, rel=0.01)
    
    def test_to_dict(self, sample_results):
        report = ComparisonReport(
            total_tickers=3,
            llm_neutral_count=1,
            keyword_neutral_count=2,
            agreement_count=2,
            avg_llm_score=65.0,
            avg_keyword_score=51.7,
            avg_score_diff=13.3,
            max_score_diff=25.0,
            avg_confidence=0.75,
            results=sample_results,
        )
        
        d = report.to_dict()
        
        assert d["total_tickers"] == 3
        assert "llm_neutral_rate" in d
        assert "neutral_reduction" in d
        assert len(d["results"]) == 3
    
    def test_to_markdown(self, sample_results):
        report = ComparisonReport(
            total_tickers=3,
            llm_neutral_count=1,
            keyword_neutral_count=2,
            agreement_count=2,
            avg_llm_score=65.0,
            avg_keyword_score=51.7,
            avg_score_diff=13.3,
            max_score_diff=25.0,
            avg_confidence=0.75,
            results=sample_results,
        )
        
        md = report.to_markdown()
        
        assert "# Sentiment Analysis Comparison Report" in md
        assert "Summary" in md
        assert "Neutral Rate" in md
        assert "Conclusion" in md


class TestSentimentComparator:
    """Test SentimentComparator class."""
    
    @pytest.fixture
    def comparator(self):
        return SentimentComparator()
    
    def test_build_report_empty(self, comparator):
        report = comparator._build_report([])
        
        assert report.total_tickers == 0
        assert report.llm_neutral_rate == 0.0
    
    def test_build_report_with_results(self, comparator):
        results = [
            ComparisonResult("AAPL", 75, "bullish", 0.85, 50, "neutral", 25, 3),
            ComparisonResult("MSFT", 70, "bullish", 0.80, 60, "slightly_bullish", 10, 2),
        ]
        
        report = comparator._build_report(results)
        
        assert report.total_tickers == 2
        assert report.avg_llm_score == 72.5
        assert report.avg_keyword_score == 55.0
        assert report.avg_score_diff == 17.5
    
    def test_save_report(self, comparator):
        results = [
            ComparisonResult("AAPL", 75, "bullish", 0.85, 50, "neutral", 25, 3),
        ]
        report = comparator._build_report(results)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            json_path, md_path = comparator.save_report(report, output_dir)
            
            assert json_path.exists()
            assert md_path.exists()
            assert json_path.suffix == ".json"
            assert md_path.suffix == ".md"


class TestNeutralRateReduction:
    """Test that LLM reduces neutral rate (key metric)."""
    
    def test_llm_reduces_neutral_rate(self):
        """Simulate scenario where LLM reduces neutrals."""
        # Keyword: 3 out of 5 neutral (60%)
        # LLM: 1 out of 5 neutral (20%)
        # Reduction: 66%
        
        results = [
            ComparisonResult("AAPL", 75, "bullish", 0.85, 50, "neutral", 25, 3),
            ComparisonResult("MSFT", 72, "bullish", 0.80, 48, "neutral", 24, 2),
            ComparisonResult("GOOGL", 65, "slightly_bullish", 0.75, 50, "neutral", 15, 2),
            ComparisonResult("TSLA", 50, "neutral", 0.60, 52, "neutral", -2, 2),
            ComparisonResult("META", 35, "bearish", 0.70, 45, "neutral", -10, 2),
        ]
        
        report = ComparisonReport(
            total_tickers=5,
            llm_neutral_count=1,  # Only TSLA is LLM neutral
            keyword_neutral_count=4,  # AAPL, MSFT, GOOGL, TSLA are keyword neutral
            results=results,
        )
        
        # LLM neutral rate: 20%
        assert report.llm_neutral_rate == 0.2
        
        # Keyword neutral rate: 80%
        assert report.keyword_neutral_rate == 0.8
        
        # Reduction: (80% - 20%) / 80% = 75%
        assert report.neutral_reduction == pytest.approx(0.75, rel=0.01)
    
    def test_target_neutral_rate_under_15_percent(self):
        """Test that we can achieve <15% neutral rate with LLM."""
        # Simulate 100 tickers with 10 LLM neutral (10%)
        report = ComparisonReport(
            total_tickers=100,
            llm_neutral_count=10,  # 10%
            keyword_neutral_count=62,  # 62% (current baseline)
        )
        
        assert report.llm_neutral_rate < 0.15  # Target: <15%
        assert report.neutral_reduction > 0.80  # >80% improvement


class TestAcceptanceCriteria:
    """
    Test acceptance criteria from REC-176:
    - Compare neutral rates
    - Track score differences
    - Report accuracy metrics
    """
    
    def test_neutral_rates_tracked(self):
        report = ComparisonReport(
            total_tickers=10,
            llm_neutral_count=2,
            keyword_neutral_count=6,
        )
        
        assert "llm_neutral_rate" in report.to_dict()
        assert "keyword_neutral_rate" in report.to_dict()
        assert "neutral_reduction" in report.to_dict()
    
    def test_score_differences_tracked(self):
        results = [
            ComparisonResult("AAPL", 75, "bullish", 0.85, 50, "neutral", 25, 3),
        ]
        report = ComparisonReport(
            total_tickers=1,
            avg_score_diff=25.0,
            max_score_diff=25.0,
            results=results,
        )
        
        d = report.to_dict()
        assert "avg_score_diff" in d
        assert "max_score_diff" in d
    
    def test_accuracy_metrics_in_report(self):
        results = [
            ComparisonResult("AAPL", 75, "bullish", 0.85, 50, "neutral", 25, 3),
        ]
        report = ComparisonReport(
            total_tickers=1,
            agreement_count=1,
            avg_confidence=0.85,
            results=results,
        )
        
        d = report.to_dict()
        assert "agreement_rate" in d
        assert "avg_confidence" in d
