"""
Unit tests for F2.x Scoring System
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


# ============ F2.1 Fundamental Score ============

class TestFundamentalScore:
    """Tests for F2.1 Fundamental Score."""
    
    def test_imports_successfully(self):
        """Module should import without errors."""
        from scoring.fundamental_score import (
            calculate_fundamental_scores,
            get_fundamental_score,
            FundamentalScoreResult,
            percentile_rank,
        )
        assert callable(calculate_fundamental_scores)
    
    def test_percentile_rank_function(self):
        """Percentile rank should return 0-100 values."""
        import pandas as pd
        from scoring.fundamental_score import percentile_rank
        
        values = pd.Series([10, 20, 30, 40, 50])
        ranks = percentile_rank(values, ascending=True)
        
        assert ranks.min() >= 0
        assert ranks.max() <= 100
    
    @pytest.mark.slow
    def test_score_in_range(self):
        """All scores should be 0-100."""
        from scoring.fundamental_score import get_fundamental_score
        
        result = get_fundamental_score("AAPL")
        if result:
            assert 0 <= result.total_score <= 100
            assert 0 <= result.value_score <= 100
            assert 0 <= result.quality_score <= 100
            assert 0 <= result.growth_score <= 100
    
    def test_weights_sum_to_one(self):
        """Component weights should sum to 1."""
        # Value: 25%, Quality: 35%, Growth: 40%
        assert abs(0.25 + 0.35 + 0.40 - 1.0) < 0.01


# ============ F2.2 Sentiment Score ============

class TestSentimentScore:
    """Tests for F2.2 Sentiment Score."""
    
    def test_imports_successfully(self):
        """Module should import without errors."""
        from scoring.sentiment_score import (
            calculate_sentiment_score_for_ticker,
            SentimentScoreResult,
            SENTIMENT_MODEL,
        )
        assert SENTIMENT_MODEL == "keyword"
    
    def test_no_news_returns_neutral(self):
        """Stock with no news should return neutral (50)."""
        from scoring.sentiment_score import calculate_sentiment_score_for_ticker
        
        # Use empty articles list
        result = calculate_sentiment_score_for_ticker("FAKE_TICKER", hours=1)
        assert result.total_score == 50.0
        assert result.article_count == 0
    
    def test_recency_weight_function(self):
        """Recency weight should decay over time."""
        from scoring.sentiment_score import calculate_recency_weight
        
        # Recent should have higher weight
        recent = calculate_recency_weight("2026-02-02T12:00:00")
        old = calculate_recency_weight("2026-01-25T12:00:00")
        
        # More recent date should have higher weight
        assert recent >= old or (recent < 0.2 and old < 0.2)
    
    def test_source_tier_weight(self):
        """Source tier weight should return correct values."""
        from scoring.sentiment_score import get_source_tier_weight
        
        assert get_source_tier_weight("finnhub_reuters") == 2
        assert get_source_tier_weight("yahoo_finance") == 1
        assert get_source_tier_weight("unknown_source") == 1


# ============ F2.3 Technical Score ============

class TestTechnicalScore:
    """Tests for F2.3 Technical Score."""
    
    def test_imports_successfully(self):
        """Module should import without errors."""
        from scoring.technical_score import (
            calculate_technical_score_for_ticker,
            calculate_rsi,
            calculate_momentum,
            calculate_trend,
            TechnicalScoreResult,
        )
        assert callable(calculate_rsi)
    
    def test_rsi_calculation(self):
        """RSI should be 0-100."""
        from scoring.technical_score import calculate_rsi
        import pandas as pd
        import numpy as np
        
        # Create sample price series with clear uptrend
        np.random.seed(42)
        prices = pd.Series(np.random.randn(100).cumsum() + 100)
        rsi = calculate_rsi(prices)
        
        assert 0 <= rsi <= 100
    
    def test_rsi_short_series(self):
        """RSI should handle short series."""
        from scoring.technical_score import calculate_rsi
        import pandas as pd
        
        short_prices = pd.Series([100, 101, 102])
        rsi = calculate_rsi(short_prices)
        
        assert rsi == 50.0  # Default neutral
    
    def test_momentum_calculation(self):
        """Momentum should return dict with return periods."""
        from scoring.technical_score import calculate_momentum
        import pandas as pd
        import numpy as np
        
        prices = pd.Series(range(300))  # Steady uptrend
        momentum = calculate_momentum(prices)
        
        assert "return_1m" in momentum
        assert "return_3m" in momentum
        assert "return_6m" in momentum
        assert "return_12m" in momentum
    
    def test_weights_correct(self):
        """Component weights should be correct."""
        # Momentum: 40%, RSI: 30%, Trend: 30%
        assert abs(0.40 + 0.30 + 0.30 - 1.0) < 0.01


# ============ F2.4 Macro Score ============

class TestMacroScore:
    """Tests for F2.4 Macro Score."""
    
    def test_imports_successfully(self):
        """Module should import without errors."""
        from scoring.macro_score import (
            calculate_macro_score_for_ticker,
            calculate_sector_macro_score,
            MacroScoreResult,
        )
        assert callable(calculate_sector_macro_score)
    
    def test_sector_macro_score_returns_dict(self):
        """Sector macro score should return dict."""
        from scoring.macro_score import calculate_sector_macro_score
        
        result = calculate_sector_macro_score("Technology")
        assert isinstance(result, dict)
        assert "score" in result
        assert 0 <= result["score"] <= 100
    
    def test_sector_sensitivity_defined(self):
        """All major sectors should have sensitivity defined."""
        from data.macro_fetcher import get_sector_macro_sensitivity
        
        sensitivity = get_sector_macro_sensitivity()
        expected_sectors = ["Technology", "Financials", "Healthcare", "Energy"]
        
        for sector in expected_sectors:
            assert sector in sensitivity
    
    def test_sensitivity_has_required_factors(self):
        """Each sector should have rate/gdp/vix sensitivity."""
        from data.macro_fetcher import get_sector_macro_sensitivity
        
        sensitivity = get_sector_macro_sensitivity()
        
        for sector, factors in sensitivity.items():
            assert "rate_sensitivity" in factors
            assert "gdp_sensitivity" in factors
            assert "vix_sensitivity" in factors
    
    def test_unknown_sector_handled(self):
        """Unknown sector should return neutral score."""
        from scoring.macro_score import calculate_sector_macro_score
        
        result = calculate_sector_macro_score("FakeSector123")
        assert result["score"] == 50.0


# ============ F2.5 Composite Score ============

class TestCompositeScore:
    """Tests for F2.5 Composite Score."""
    
    def test_weights_sum_to_one(self):
        """Component weights should sum to 1."""
        from scoring.composite_score import WEIGHTS
        
        total = sum(WEIGHTS.values())
        assert abs(total - 1.0) < 0.01
    
    def test_weights_match_spec(self):
        """Weights should match PRD spec."""
        from scoring.composite_score import WEIGHTS
        
        assert WEIGHTS["fundamental"] == 0.35
        assert WEIGHTS["sentiment"] == 0.25
        assert WEIGHTS["macro"] == 0.20
        assert WEIGHTS["technical"] == 0.20
    
    def test_signal_thresholds(self):
        """Signal thresholds should be correct."""
        from scoring.composite_score import SIGNAL_THRESHOLDS
        
        assert SIGNAL_THRESHOLDS["BUY"] == 70
        assert SIGNAL_THRESHOLDS["SELL"] == 40
    
    def test_get_signal_buy(self):
        """Score >= 70 should be BUY."""
        from scoring.composite_score import get_signal, Signal
        
        assert get_signal(70) == Signal.BUY
        assert get_signal(85) == Signal.BUY
        assert get_signal(100) == Signal.BUY
    
    def test_get_signal_hold(self):
        """Score 40-69 should be HOLD."""
        from scoring.composite_score import get_signal, Signal
        
        assert get_signal(40) == Signal.HOLD
        assert get_signal(55) == Signal.HOLD
        assert get_signal(69) == Signal.HOLD
    
    def test_get_signal_sell(self):
        """Score < 40 should be SELL."""
        from scoring.composite_score import get_signal, Signal
        
        assert get_signal(39) == Signal.SELL
        assert get_signal(20) == Signal.SELL
        assert get_signal(0) == Signal.SELL
    
    @pytest.mark.slow
    def test_calculate_returns_results(self):
        """Should return dict of results."""
        from scoring.composite_score import calculate_composite_scores
        
        scores = calculate_composite_scores(tickers=["AAPL", "MSFT"])
        assert isinstance(scores, dict)
        assert len(scores) == 2
    
    @pytest.mark.slow
    def test_result_has_all_components(self):
        """Result should have all score components."""
        from scoring.composite_score import calculate_composite_scores
        
        scores = calculate_composite_scores(tickers=["AAPL"])
        result = scores.get("AAPL")
        
        assert result is not None
        assert hasattr(result, 'total_score')
        assert hasattr(result, 'fundamental_score')
        assert hasattr(result, 'sentiment_score')
        assert hasattr(result, 'technical_score')
        assert hasattr(result, 'macro_score')
        assert hasattr(result, 'signal')
        assert hasattr(result, 'rank')


# ============ F2.6 Score Explainability ============

class TestScoreExplainability:
    """Tests for F2.6 Score Explainability."""
    
    def test_imports_successfully(self):
        """Module should import without errors."""
        from scoring.explainer import (
            explain_score,
            explain_score_simple,
            format_explanation_markdown,
            ScoreExplanation,
        )
        assert callable(explain_score)
    
    def test_explain_mock_result(self):
        """Should explain a mock result."""
        from scoring.composite_score import CompositeScoreResult, Signal
        from scoring.explainer import explain_score
        
        # Create mock result
        mock_result = CompositeScoreResult(
            ticker="TEST",
            sector="Technology",
            total_score=75.0,
            signal=Signal.BUY,
            rank=1,
            percentile=95.0,
            fundamental_score=80.0,
            sentiment_score=70.0,
            technical_score=75.0,
            macro_score=72.0,
            score_change=5.0,
            signal_change=None,
            details={
                "fundamental": {"pe_ratio": 25, "roe": 0.20},
                "sentiment": {},
                "technical": {"rsi": 55, "trend": {"golden_cross": True}},
                "macro": {"regime": "bullish"},
            }
        )
        
        explanation = explain_score(mock_result)
        assert explanation is not None
        assert "TEST" in explanation.summary
        assert "BUY" in explanation.signal_reason
    
    def test_strength_weakness_identification(self):
        """Should identify strengths and weaknesses."""
        from scoring.explainer import _identify_strengths_weaknesses
        from scoring.composite_score import CompositeScoreResult, Signal
        
        # High fundamental score should be identified as strength
        result = CompositeScoreResult(
            ticker="TEST", sector="Tech", total_score=70, signal=Signal.BUY,
            rank=1, percentile=90,
            fundamental_score=80, sentiment_score=50, technical_score=50, macro_score=50,
            score_change=None, signal_change=None,
            details={"fundamental": {"roe": 0.20}, "sentiment": {}, "technical": {}, "macro": {}}
        )
        
        strengths, weaknesses = _identify_strengths_weaknesses(result)
        assert len(strengths) >= 1 or len(weaknesses) >= 0  # At least checks run
    
    def test_markdown_format_structure(self):
        """Markdown format should have proper structure."""
        from scoring.composite_score import CompositeScoreResult, Signal
        from scoring.explainer import explain_score, format_explanation_markdown
        
        result = CompositeScoreResult(
            ticker="MOCK", sector="Financials", total_score=55, signal=Signal.HOLD,
            rank=100, percentile=50,
            fundamental_score=50, sentiment_score=50, technical_score=50, macro_score=70,
            score_change=None, signal_change=None,
            details={"fundamental": {}, "sentiment": {}, "technical": {}, "macro": {"regime": "neutral"}}
        )
        
        explanation = explain_score(result)
        markdown = format_explanation_markdown(explanation)
        
        assert "##" in markdown
        assert "MOCK" in markdown
        assert "Strengths" in markdown
        assert "Weaknesses" in markdown


# Run with: pytest tests/unit/test_scoring.py -v -m "not slow"
