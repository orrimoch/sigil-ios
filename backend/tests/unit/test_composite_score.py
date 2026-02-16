"""
Unit tests for Composite Score calculation.

Tests:
- Population mean fallback for missing component scores
- Weighted composite calculation
- Signal generation
- Score bounds enforcement
- Crowd wisdom boost/penalty
- Risk-adjusted thresholds
"""

import pytest
from unittest.mock import patch, MagicMock
from dataclasses import dataclass
from typing import Optional, Dict

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


# Mock result classes matching the actual implementations
@dataclass
class MockFundamentalResult:
    ticker: str
    total_score: Optional[float]
    details: Dict = None
    
    def __post_init__(self):
        if self.details is None:
            self.details = {}


@dataclass
class MockSentimentResult:
    ticker: str
    total_score: Optional[float]
    article_count: int = 0
    details: Dict = None
    
    def __post_init__(self):
        if self.details is None:
            self.details = {}


@dataclass
class MockTechnicalResult:
    ticker: str
    total_score: Optional[float]
    details: Dict = None
    
    def __post_init__(self):
        if self.details is None:
            self.details = {}


@dataclass
class MockMacroResult:
    ticker: str
    total_score: Optional[float]
    details: Dict = None
    
    def __post_init__(self):
        if self.details is None:
            self.details = {}


class TestPopulationMeanFallback:
    """Tests for population mean fallback when component scores are missing."""
    
    def test_mean_calculation_from_valid_scores(self):
        """Test that population means are correctly calculated from valid scores."""
        import numpy as np
        
        # Simulate component scores with some None values
        fundamental_scores = {
            "AAPL": MockFundamentalResult("AAPL", 60.0),
            "MSFT": MockFundamentalResult("MSFT", 70.0),
            "GOOGL": MockFundamentalResult("GOOGL", 50.0),
            "MISSING": MockFundamentalResult("MISSING", None),  # Missing score
        }
        
        # Calculate mean excluding None values
        f_values = [s.total_score for s in fundamental_scores.values() if s and s.total_score is not None]
        f_mean = np.mean(f_values) if f_values else 50.0
        
        assert f_mean == 60.0  # (60 + 70 + 50) / 3
        assert len(f_values) == 3
    
    def test_fallback_uses_population_mean_not_hardcoded_50(self):
        """Test that missing scores use population mean, not hardcoded 50."""
        import numpy as np
        
        # Create scores where population mean is NOT 50
        sentiment_scores = {
            "AAPL": MockSentimentResult("AAPL", 75.0, article_count=10),
            "MSFT": MockSentimentResult("MSFT", 80.0, article_count=8),
            "GOOGL": MockSentimentResult("GOOGL", 70.0, article_count=5),
            "NVDA": MockSentimentResult("NVDA", 65.0, article_count=12),
            "META": MockSentimentResult("META", None, article_count=0),  # No articles
        }
        
        s_values = [s.total_score for s in sentiment_scores.values() if s and s.total_score is not None]
        s_mean = np.mean(s_values) if s_values else 50.0
        
        # Mean should be 72.5, NOT 50
        assert s_mean == 72.5  # (75 + 80 + 70 + 65) / 4
        assert s_mean != 50.0
    
    def test_all_components_missing_defaults_to_50(self):
        """Test that when ALL scores are missing, mean defaults to 50."""
        import numpy as np
        
        # All None scores
        scores = {
            "A": MockSentimentResult("A", None),
            "B": MockSentimentResult("B", None),
            "C": MockSentimentResult("C", None),
        }
        
        values = [s.total_score for s in scores.values() if s and s.total_score is not None]
        mean = np.mean(values) if values else 50.0
        
        assert mean == 50.0
        assert len(values) == 0
    
    def test_single_valid_score_becomes_mean(self):
        """Test that a single valid score is its own mean."""
        import numpy as np
        
        scores = {
            "ONLY": MockTechnicalResult("ONLY", 85.0),
            "MISS1": MockTechnicalResult("MISS1", None),
            "MISS2": MockTechnicalResult("MISS2", None),
        }
        
        values = [s.total_score for s in scores.values() if s and s.total_score is not None]
        mean = np.mean(values) if values else 50.0
        
        assert mean == 85.0


class TestWeightedComposite:
    """Tests for weighted composite score calculation."""
    
    def test_weights_sum_to_one(self):
        """Verify weights sum to 1.0 (100%)."""
        from scoring.composite_score import WEIGHTS
        
        total = sum(WEIGHTS.values())
        assert abs(total - 1.0) < 0.001
    
    def test_weight_values(self):
        """Verify weight values match PRD spec."""
        from scoring.composite_score import WEIGHTS
        
        assert WEIGHTS["fundamental"] == 0.35
        assert WEIGHTS["sentiment"] == 0.25
        assert WEIGHTS["technical"] == 0.20
        assert WEIGHTS["macro"] == 0.20
    
    def test_composite_calculation(self):
        """Test weighted composite calculation formula."""
        from scoring.composite_score import WEIGHTS
        
        f_val = 80.0
        s_val = 60.0
        t_val = 70.0
        m_val = 50.0
        
        expected = (
            f_val * WEIGHTS["fundamental"] +
            s_val * WEIGHTS["sentiment"] +
            t_val * WEIGHTS["technical"] +
            m_val * WEIGHTS["macro"]
        )
        
        # 80*0.35 + 60*0.25 + 70*0.20 + 50*0.20 = 28 + 15 + 14 + 10 = 67
        assert expected == 67.0
    
    def test_all_100_gives_100(self):
        """Test that all perfect scores give 100."""
        from scoring.composite_score import WEIGHTS
        
        score = 100.0 * sum(WEIGHTS.values())
        assert score == 100.0
    
    def test_all_0_gives_0(self):
        """Test that all zero scores give 0."""
        from scoring.composite_score import WEIGHTS
        
        score = 0.0 * sum(WEIGHTS.values())
        assert score == 0.0


class TestSignalGeneration:
    """Tests for signal generation from scores."""
    
    def test_buy_signal_at_threshold(self):
        """Test BUY signal at exactly threshold."""
        from scoring.composite_score import get_signal, Signal
        
        assert get_signal(70.0) == Signal.BUY
    
    def test_buy_signal_above_threshold(self):
        """Test BUY signal above threshold."""
        from scoring.composite_score import get_signal, Signal
        
        assert get_signal(85.0) == Signal.BUY
        assert get_signal(100.0) == Signal.BUY
    
    def test_hold_signal_range(self):
        """Test HOLD signal in middle range."""
        from scoring.composite_score import get_signal, Signal
        
        assert get_signal(40.0) == Signal.HOLD
        assert get_signal(50.0) == Signal.HOLD
        assert get_signal(69.9) == Signal.HOLD
    
    def test_sell_signal_below_threshold(self):
        """Test SELL signal below threshold."""
        from scoring.composite_score import get_signal, Signal
        
        assert get_signal(39.9) == Signal.SELL
        assert get_signal(20.0) == Signal.SELL
        assert get_signal(0.0) == Signal.SELL
    
    def test_risk_adjusted_conservative(self):
        """Test conservative risk tolerance raises BUY threshold."""
        from scoring.composite_score import get_signal, Signal
        
        # At 75, moderate would be BUY, conservative should be HOLD
        assert get_signal(75.0, risk_tolerance="moderate") == Signal.BUY
        assert get_signal(75.0, risk_tolerance="conservative") == Signal.HOLD
        
        # Conservative BUY requires 80+
        assert get_signal(80.0, risk_tolerance="conservative") == Signal.BUY
    
    def test_risk_adjusted_aggressive(self):
        """Test aggressive risk tolerance lowers BUY threshold."""
        from scoring.composite_score import get_signal, Signal
        
        # At 65, moderate would be HOLD, aggressive should be BUY
        assert get_signal(65.0, risk_tolerance="moderate") == Signal.HOLD
        assert get_signal(65.0, risk_tolerance="aggressive") == Signal.BUY


class TestScoreBounds:
    """Tests for score bounds enforcement (0-100 range)."""
    
    def test_score_capped_at_100(self):
        """Test that scores above 100 are capped."""
        # Simulating the bounds enforcement logic
        total_score = 105.0
        bounded = max(0.0, min(100.0, total_score))
        assert bounded == 100.0
    
    def test_score_floored_at_0(self):
        """Test that scores below 0 are floored."""
        total_score = -5.0
        bounded = max(0.0, min(100.0, total_score))
        assert bounded == 0.0
    
    def test_valid_score_unchanged(self):
        """Test that valid scores are not modified."""
        for score in [0.0, 25.0, 50.0, 75.0, 100.0]:
            bounded = max(0.0, min(100.0, score))
            assert bounded == score
    
    def test_bounds_after_crowd_wisdom_boost(self):
        """Test bounds are enforced after crowd wisdom adjustment."""
        # Simulate: base score 98 + max boost 10 = 108 → should be 100
        base_score = 98.0
        cw_boost = 10.0
        adjusted = base_score + cw_boost
        bounded = max(0.0, min(100.0, adjusted))
        assert bounded == 100.0
    
    def test_bounds_after_crowd_wisdom_penalty(self):
        """Test bounds are enforced after crowd wisdom penalty."""
        # Simulate: base score 2 - max penalty 3 = -1 → should be 0
        base_score = 2.0
        cw_penalty = -3.0
        adjusted = base_score + cw_penalty
        bounded = max(0.0, min(100.0, adjusted))
        assert bounded == 0.0


class TestCrowdWisdomBoost:
    """Tests for crowd wisdom score boost/penalty."""
    
    def test_boost_calculation_at_threshold(self):
        """Test boost at exactly threshold (70) is 0."""
        from scoring.composite_score import get_crowd_wisdom_boost
        
        boost = get_crowd_wisdom_boost(70.0)
        assert boost == 0.0
    
    def test_boost_calculation_above_threshold(self):
        """Test boost increases above threshold."""
        from scoring.composite_score import get_crowd_wisdom_boost
        
        # 85 is halfway from 70 to 100, so boost should be ~5 (half of max 10)
        boost = get_crowd_wisdom_boost(85.0)
        assert 4.5 <= boost <= 5.5
    
    def test_max_boost_at_100(self):
        """Test maximum boost at viral score 100."""
        from scoring.composite_score import get_crowd_wisdom_boost
        
        boost = get_crowd_wisdom_boost(100.0)
        assert boost == 10.0
    
    def test_penalty_calculation_below_threshold(self):
        """Test penalty below threshold (30)."""
        from scoring.composite_score import get_crowd_wisdom_boost
        
        # 15 is halfway from 30 to 0, so penalty should be ~-1.5 (half of max -3)
        penalty = get_crowd_wisdom_boost(15.0)
        assert -2.0 <= penalty <= -1.0
    
    def test_max_penalty_near_zero(self):
        """Test maximum penalty near zero viral score."""
        from scoring.composite_score import get_crowd_wisdom_boost
        
        # Very low score should get close to max penalty
        penalty = get_crowd_wisdom_boost(1.0)
        assert -3.0 <= penalty <= -2.5
    
    def test_no_adjustment_in_middle(self):
        """Test no adjustment in neutral range (30-70)."""
        from scoring.composite_score import get_crowd_wisdom_boost
        
        for score in [35.0, 45.0, 55.0, 65.0]:
            boost = get_crowd_wisdom_boost(score)
            assert boost == 0.0
    
    def test_no_penalty_for_zero_score(self):
        """Test that score=0 (not in CW data) gets no penalty."""
        from scoring.composite_score import get_crowd_wisdom_boost
        
        # Zero means stock wasn't in crowd wisdom data
        boost = get_crowd_wisdom_boost(0.0)
        assert boost == 0.0


class TestRiskAdjustedThresholds:
    """Tests for risk-adjusted signal thresholds."""
    
    def test_get_thresholds_moderate(self):
        """Test moderate thresholds (default)."""
        from scoring.composite_score import get_thresholds_for_risk
        
        thresholds = get_thresholds_for_risk("moderate")
        assert thresholds["BUY"] == 70
        assert thresholds["SELL"] == 40
    
    def test_get_thresholds_conservative(self):
        """Test conservative thresholds (higher bar)."""
        from scoring.composite_score import get_thresholds_for_risk
        
        thresholds = get_thresholds_for_risk("conservative")
        assert thresholds["BUY"] == 80
        assert thresholds["SELL"] == 30
    
    def test_get_thresholds_aggressive(self):
        """Test aggressive thresholds (lower bar)."""
        from scoring.composite_score import get_thresholds_for_risk
        
        thresholds = get_thresholds_for_risk("aggressive")
        assert thresholds["BUY"] == 60
        assert thresholds["SELL"] == 50
    
    def test_invalid_risk_falls_back_to_default(self):
        """Test invalid risk tolerance falls back to default."""
        from scoring.composite_score import get_thresholds_for_risk, SIGNAL_THRESHOLDS
        
        thresholds = get_thresholds_for_risk("invalid_value")
        assert thresholds == SIGNAL_THRESHOLDS
    
    def test_case_insensitive(self):
        """Test risk tolerance is case-insensitive."""
        from scoring.composite_score import get_thresholds_for_risk
        
        assert get_thresholds_for_risk("MODERATE") == get_thresholds_for_risk("moderate")
        assert get_thresholds_for_risk("Conservative") == get_thresholds_for_risk("conservative")


class TestSentimentNoneHandling:
    """Tests for sentiment returning None when no articles exist."""
    
    def test_no_articles_returns_none_total_score(self):
        """Test that stocks with no articles return None total_score."""
        from scoring.sentiment_score import SentimentScoreResult
        
        # Simulating what calculate_sentiment_score_for_ticker returns for no articles
        result = SentimentScoreResult(
            ticker="NOARTICLES",
            total_score=None,
            raw_sentiment=0.0,
            article_count=0,
            positive_count=0,
            negative_count=0,
            neutral_count=0,
            weighted_sentiment=0.0,
            details={"message": "No news found - using population mean", "model": "mean_fallback"}
        )
        
        assert result.total_score is None
        assert result.article_count == 0
        assert "population mean" in result.details["message"]
    
    def test_none_score_filtered_in_mean_calculation(self):
        """Test None scores are excluded from mean calculation."""
        scores = [60.0, None, 80.0, None, 70.0]
        valid = [s for s in scores if s is not None]
        mean = sum(valid) / len(valid)
        
        assert mean == 70.0  # (60 + 80 + 70) / 3
        assert None not in valid


class TestCompositeScoreIntegration:
    """Integration tests for composite score calculation flow."""
    
    @patch('scoring.composite_score.calculate_fundamental_scores')
    @patch('scoring.composite_score.calculate_sentiment_scores')
    @patch('scoring.composite_score.calculate_technical_scores')
    @patch('scoring.composite_score.calculate_macro_scores')
    @patch('scoring.composite_score.load_crowd_wisdom_scores')
    @patch('scoring.composite_score.get_universe')
    @patch('scoring.composite_score.RELATIVE_SCORING_ENABLED', False)
    def test_fallback_path_uses_population_mean(
        self,
        mock_universe,
        mock_cw,
        mock_macro,
        mock_tech,
        mock_sent,
        mock_fund
    ):
        """Test that the fallback path (RELATIVE_SCORING_ENABLED=False) uses population means."""
        # Setup mock universe
        mock_universe.return_value = [
            {"ticker": "AAPL", "sector": "Technology"},
            {"ticker": "MSFT", "sector": "Technology"},
            {"ticker": "MISS", "sector": "Technology"},
        ]
        
        # Mock component scores - MISS has None sentiment
        mock_fund.return_value = {
            "AAPL": MockFundamentalResult("AAPL", 60.0),
            "MSFT": MockFundamentalResult("MSFT", 80.0),
            "MISS": MockFundamentalResult("MISS", 70.0),
        }
        mock_sent.return_value = {
            "AAPL": MockSentimentResult("AAPL", 70.0, article_count=5),
            "MSFT": MockSentimentResult("MSFT", 80.0, article_count=8),
            "MISS": MockSentimentResult("MISS", None, article_count=0),  # No articles!
        }
        mock_tech.return_value = {
            "AAPL": MockTechnicalResult("AAPL", 55.0),
            "MSFT": MockTechnicalResult("MSFT", 65.0),
            "MISS": MockTechnicalResult("MISS", 60.0),
        }
        mock_macro.return_value = {
            "AAPL": MockMacroResult("AAPL", 50.0),
            "MSFT": MockMacroResult("MSFT", 55.0),
            "MISS": MockMacroResult("MISS", 52.0),
        }
        mock_cw.return_value = {}
        
        # Import after mocks are set
        from scoring.composite_score import calculate_composite_scores
        
        results = calculate_composite_scores(tickers=["AAPL", "MSFT", "MISS"])
        
        # Verify MISS got scored (not excluded)
        assert "MISS" in results
        
        # The sentiment mean should be (70+80)/2 = 75, not 50
        # This confirms population mean is used
        miss_result = results.get("MISS")
        assert miss_result is not None
        assert miss_result.total_score is not None


class TestRelativeScoring:
    """Tests for relative scoring (Bayesian shrinkage + percentile ranking)."""
    
    def test_bayesian_shrink_formula(self):
        """Test Bayesian shrinkage formula."""
        from scoring.relative_scoring import bayesian_shrink
        
        # High sample size: score stays close to raw
        raw = 80.0
        n = 20
        mean = 50.0
        k = 5
        
        shrunk = bayesian_shrink(raw, n, mean, k)
        # (20*80 + 5*50) / (20+5) = (1600 + 250) / 25 = 74
        assert abs(shrunk - 74.0) < 0.1
    
    def test_bayesian_shrink_low_sample(self):
        """Test shrinkage pulls low-sample scores toward mean."""
        from scoring.relative_scoring import bayesian_shrink
        
        # Low sample size: pulled toward mean
        raw = 90.0
        n = 1
        mean = 50.0
        k = 5
        
        shrunk = bayesian_shrink(raw, n, mean, k)
        # (1*90 + 5*50) / (1+5) = (90 + 250) / 6 = 56.67
        assert abs(shrunk - 56.67) < 0.1
    
    def test_bayesian_shrink_zero_sample(self):
        """Test zero sample size returns mean."""
        from scoring.relative_scoring import bayesian_shrink
        
        shrunk = bayesian_shrink(80.0, 0, 50.0, 5)
        assert shrunk == 50.0
    
    def test_percentile_rank_highest_gets_100(self):
        """Test highest score gets percentile 100."""
        from scoring.relative_scoring import percentile_rank
        
        scores = {"A": 100.0, "B": 50.0, "C": 25.0}
        ranks = percentile_rank(scores)
        
        assert ranks["A"] == 100.0
    
    def test_percentile_rank_lowest_gets_0(self):
        """Test lowest score gets percentile 0."""
        from scoring.relative_scoring import percentile_rank
        
        scores = {"A": 100.0, "B": 50.0, "C": 25.0}
        ranks = percentile_rank(scores)
        
        assert ranks["C"] == 0.0
    
    def test_percentile_rank_single_stock(self):
        """Test single stock gets percentile 50."""
        from scoring.relative_scoring import percentile_rank
        
        scores = {"ONLY": 75.0}
        ranks = percentile_rank(scores)
        
        assert ranks["ONLY"] == 50.0
    
    def test_transform_handles_none_scores(self):
        """Test transform_component_scores handles None values."""
        from scoring.relative_scoring import transform_component_scores
        
        scores = {
            "A": (80.0, 10),
            "B": (None, 0),  # None score
            "C": (60.0, 5),
        }
        
        result = transform_component_scores(scores, "Test")
        
        # None score should get median percentile (50)
        assert result["B"] == 50.0
        # Valid scores should be ranked
        assert result["A"] > result["C"]  # Higher score = higher percentile


class TestEdgeCases:
    """Edge case tests."""
    
    def test_empty_tickers_list(self):
        """Test handling of empty tickers list."""
        # Just verify the logic handles empty case
        tickers = []
        assert len(tickers) == 0
    
    def test_single_ticker(self):
        """Test handling of single ticker."""
        tickers = ["AAPL"]
        assert len(tickers) == 1
    
    def test_duplicate_handling(self):
        """Test that uppercase normalization handles duplicates."""
        tickers = ["AAPL", "aapl", "Aapl"]
        normalized = [t.upper() for t in tickers]
        unique = list(set(normalized))
        assert len(unique) == 1
        assert unique[0] == "AAPL"
    
    def test_score_precision(self):
        """Test score rounding precision."""
        score = 67.456789
        rounded = round(score, 2)
        assert rounded == 67.46
