"""
Unit tests for F1.3 Fundamental Data Fetcher
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from data.fundamental_fetcher import (
    fetch_fundamentals,
    calculate_quality_score,
    calculate_value_score,
    calculate_growth_score,
)


class TestFetchFundamentals:
    """Tests for fetching fundamental data."""
    
    def test_returns_dict_for_valid_ticker(self):
        """Should return dict for valid ticker."""
        fund = fetch_fundamentals("AAPL")
        assert isinstance(fund, dict)
    
    def test_contains_valuation_metrics(self):
        """Should contain P/E, P/B, and market cap."""
        fund = fetch_fundamentals("MSFT")
        assert "pe_ratio" in fund
        assert "pb_ratio" in fund
        assert "market_cap" in fund
    
    def test_contains_profitability_metrics(self):
        """Should contain margin and ROE data."""
        fund = fetch_fundamentals("GOOGL")
        assert "profit_margin" in fund
        assert "roe" in fund
        assert "operating_margin" in fund
    
    def test_contains_growth_metrics(self):
        """Should contain revenue and earnings growth."""
        fund = fetch_fundamentals("AAPL")
        assert "revenue_growth" in fund
        assert "earnings_growth" in fund
        assert "eps_ttm" in fund
    
    def test_contains_financial_health_metrics(self):
        """Should contain debt and cash flow data."""
        fund = fetch_fundamentals("MSFT")
        assert "debt_to_equity" in fund
        assert "current_ratio" in fund
        assert "free_cash_flow" in fund
    
    def test_returns_none_for_invalid_ticker(self):
        """Should return None for invalid ticker."""
        fund = fetch_fundamentals("INVALID_XYZ_123")
        assert fund is None


class TestQualityScore:
    """Tests for quality score calculation."""
    
    def test_returns_float(self):
        """Should return a float score."""
        fund = fetch_fundamentals("AAPL")
        score = calculate_quality_score(fund)
        assert isinstance(score, (int, float))
    
    def test_score_in_range(self):
        """Score should be between 0 and 100."""
        fund = fetch_fundamentals("MSFT")
        score = calculate_quality_score(fund)
        assert 0 <= score <= 100
    
    def test_high_quality_stock_scores_well(self):
        """High quality stock (MSFT) should score above 50."""
        fund = fetch_fundamentals("MSFT")
        score = calculate_quality_score(fund)
        assert score >= 50, f"MSFT quality score {score} should be >= 50"


class TestValueScore:
    """Tests for value score calculation."""
    
    def test_returns_float(self):
        """Should return a float score."""
        fund = fetch_fundamentals("AAPL")
        score = calculate_value_score(fund)
        assert isinstance(score, (int, float))
    
    def test_score_in_range(self):
        """Score should be between 0 and 100."""
        fund = fetch_fundamentals("GOOGL")
        score = calculate_value_score(fund)
        assert 0 <= score <= 100


class TestGrowthScore:
    """Tests for growth score calculation."""
    
    def test_returns_float(self):
        """Should return a float score."""
        fund = fetch_fundamentals("NVDA")
        score = calculate_growth_score(fund)
        assert isinstance(score, (int, float))
    
    def test_score_in_range(self):
        """Score should be between 0 and 100."""
        fund = fetch_fundamentals("AAPL")
        score = calculate_growth_score(fund)
        assert 0 <= score <= 100


class TestScoreConsistency:
    """Tests for score consistency."""
    
    def test_all_scores_computed(self):
        """All three scores should be computable."""
        fund = fetch_fundamentals("AAPL")
        
        quality = calculate_quality_score(fund)
        value = calculate_value_score(fund)
        growth = calculate_growth_score(fund)
        
        assert quality is not None
        assert value is not None
        assert growth is not None
        
        # All should be valid scores
        assert 0 <= quality <= 100
        assert 0 <= value <= 100
        assert 0 <= growth <= 100


# Run with: pytest tests/unit/test_fundamental_fetcher.py -v
