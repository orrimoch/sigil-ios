"""
Unit tests for F1.5 Macro Data Fetcher
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from data.macro_fetcher import (
    fetch_fred_series,
    fetch_all_macro_data,
    get_latest_macro_value,
    calculate_macro_score,
    get_sector_macro_sensitivity,
    FRED_SERIES,
)


class TestFetchFredSeries:
    """Tests for fetching FRED series data."""
    
    def test_returns_dataframe_for_valid_series(self):
        """Should return DataFrame for valid series."""
        df = fetch_fred_series("VIXCLS", periods=30)
        assert df is not None
        assert len(df) > 0
    
    def test_contains_required_columns(self):
        """Should have date, value, and series_id columns."""
        df = fetch_fred_series("FEDFUNDS", periods=30)
        assert "date" in df.columns
        assert "value" in df.columns
        assert "series_id" in df.columns
    
    def test_values_are_numeric(self):
        """Values should be numeric."""
        df = fetch_fred_series("UNRATE", periods=30)
        assert df["value"].dtype in ["float64", "int64"]
    
    def test_returns_none_for_invalid_series(self):
        """Should return None for invalid series ID."""
        df = fetch_fred_series("INVALID_XYZ_123", periods=30)
        # May return empty df or None
        assert df is None or len(df) == 0


class TestGetLatestMacroValue:
    """Tests for getting latest indicator values."""
    
    def test_returns_dict_for_valid_indicator(self):
        """Should return dict for valid indicator name."""
        result = get_latest_macro_value("vix")
        assert isinstance(result, dict)
    
    def test_contains_required_fields(self):
        """Should contain indicator, value, and date."""
        result = get_latest_macro_value("fed_funds_rate")
        assert "indicator" in result
        assert "value" in result
        assert "date" in result
    
    def test_returns_none_for_invalid_indicator(self):
        """Should return None for unknown indicator."""
        result = get_latest_macro_value("fake_indicator")
        assert result is None
    
    def test_vix_is_positive(self):
        """VIX should always be positive."""
        result = get_latest_macro_value("vix")
        if result:
            assert result["value"] > 0


class TestFetchAllMacroData:
    """Tests for fetching all macro indicators."""
    
    @pytest.mark.slow
    def test_returns_dict(self):
        """Should return a dict of indicators."""
        data = fetch_all_macro_data(periods=30)
        assert isinstance(data, dict)
    
    @pytest.mark.slow
    def test_fetches_multiple_indicators(self):
        """Should fetch at least some indicators."""
        data = fetch_all_macro_data(periods=30)
        # Should have at least half the indicators
        assert len(data) >= len(FRED_SERIES) // 2
    
    @pytest.mark.slow
    def test_indicators_have_required_fields(self):
        """Each indicator should have value and date."""
        data = fetch_all_macro_data(periods=30)
        for name, indicator in data.items():
            assert "value" in indicator, f"{name} missing value"
            assert "date" in indicator, f"{name} missing date"


class TestCalculateMacroScore:
    """Tests for macro score calculation."""
    
    def test_returns_dict(self):
        """Should return a dict with score."""
        result = calculate_macro_score()
        assert isinstance(result, dict)
    
    def test_contains_score(self):
        """Should contain numeric score."""
        result = calculate_macro_score()
        assert "score" in result
        assert isinstance(result["score"], (int, float))
    
    def test_score_in_range(self):
        """Score should be 0-100."""
        result = calculate_macro_score()
        assert 0 <= result["score"] <= 100
    
    def test_contains_regime(self):
        """Should contain regime classification."""
        result = calculate_macro_score()
        assert "regime" in result
        assert result["regime"] in ["bullish", "neutral", "cautious", "bearish"]
    
    def test_contains_details(self):
        """Should contain component details."""
        result = calculate_macro_score()
        assert "details" in result


class TestSectorMacroSensitivity:
    """Tests for sector sensitivity data."""
    
    def test_returns_dict(self):
        """Should return a dict of sectors."""
        result = get_sector_macro_sensitivity()
        assert isinstance(result, dict)
    
    def test_contains_major_sectors(self):
        """Should contain major GICS sectors."""
        result = get_sector_macro_sensitivity()
        expected_sectors = [
            "Technology", "Financials", "Healthcare",
            "Consumer Discretionary", "Energy"
        ]
        for sector in expected_sectors:
            assert sector in result, f"Missing sector: {sector}"
    
    def test_sectors_have_sensitivity_scores(self):
        """Each sector should have sensitivity scores."""
        result = get_sector_macro_sensitivity()
        for sector, data in result.items():
            assert "rate_sensitivity" in data
            assert "gdp_sensitivity" in data
            assert "vix_sensitivity" in data
    
    def test_sensitivity_in_range(self):
        """Sensitivity scores should be -1 to 1."""
        result = get_sector_macro_sensitivity()
        for sector, data in result.items():
            for key, value in data.items():
                assert -1 <= value <= 1, f"{sector}.{key} = {value} out of range"


class TestFredSeriesConstants:
    """Tests for FRED series configuration."""
    
    def test_has_key_indicators(self):
        """Should have key economic indicators defined."""
        required = ["fed_funds_rate", "unemployment_rate", "vix", "gdp"]
        for indicator in required:
            assert indicator in FRED_SERIES, f"Missing indicator: {indicator}"
    
    def test_series_ids_are_strings(self):
        """All series IDs should be strings."""
        for name, series_id in FRED_SERIES.items():
            assert isinstance(series_id, str), f"{name} has non-string ID"


# Run with: pytest tests/unit/test_macro_fetcher.py -v -m "not slow"
