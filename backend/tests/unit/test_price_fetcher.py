"""
Unit tests for F1.2 Price Data Fetcher
"""

import pytest
import sys
from pathlib import Path
import pandas as pd

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from data.price_fetcher import (
    fetch_price_history,
    fetch_latest_price,
    fetch_all_prices,
)


class TestFetchPriceHistory:
    """Tests for fetching historical prices."""
    
    def test_returns_dataframe_for_valid_ticker(self):
        """Should return DataFrame for valid ticker."""
        df = fetch_price_history("AAPL", period="1mo")
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0
    
    def test_contains_required_columns(self):
        """Should contain OHLCV columns."""
        df = fetch_price_history("MSFT", period="1mo")
        required = ["date", "ticker", "open", "high", "low", "close", "volume"]
        for col in required:
            assert col in df.columns, f"Missing column: {col}"
    
    def test_prices_are_positive(self):
        """All prices should be positive."""
        df = fetch_price_history("GOOGL", period="1mo")
        assert (df["close"] > 0).all()
        assert (df["open"] > 0).all()
        assert (df["high"] > 0).all()
        assert (df["low"] > 0).all()
    
    def test_high_greater_than_low(self):
        """High should be >= low for each day."""
        df = fetch_price_history("AAPL", period="1mo")
        assert (df["high"] >= df["low"]).all()
    
    def test_5y_period_returns_substantial_data(self):
        """5-year period should return ~1250 trading days."""
        df = fetch_price_history("AAPL", period="5y")
        # At least 4 years of data (allowing for some missing)
        assert len(df) > 1000, f"Expected >1000 rows, got {len(df)}"
    
    def test_returns_none_for_invalid_ticker(self):
        """Should return None for invalid ticker."""
        df = fetch_price_history("INVALID_XYZ_123")
        assert df is None


class TestFetchLatestPrice:
    """Tests for fetching latest price."""
    
    def test_returns_dict_for_valid_ticker(self):
        """Should return dict for valid ticker."""
        price = fetch_latest_price("AAPL")
        assert isinstance(price, dict)
    
    def test_contains_required_fields(self):
        """Should contain price and change fields."""
        price = fetch_latest_price("MSFT")
        assert "ticker" in price
        assert "price" in price
        assert price["ticker"] == "MSFT"
    
    def test_price_is_positive(self):
        """Price should be positive."""
        price = fetch_latest_price("GOOGL")
        assert price["price"] is None or price["price"] > 0
    
    def test_returns_none_for_invalid_ticker(self):
        """Should return None for invalid ticker."""
        price = fetch_latest_price("INVALID_XYZ_123")
        assert price is None or price.get("price") is None


class TestFetchAllPrices:
    """Tests for batch price fetching."""
    
    def test_fetches_multiple_tickers(self):
        """Should fetch prices for multiple tickers."""
        tickers = ["AAPL", "MSFT", "GOOGL"]
        results = fetch_all_prices(tickers, period="1mo", max_workers=3)
        
        assert len(results) == 3
        for ticker in tickers:
            assert ticker in results
            assert isinstance(results[ticker], pd.DataFrame)
    
    def test_handles_mixed_valid_invalid(self):
        """Should handle mix of valid and invalid tickers."""
        tickers = ["AAPL", "INVALID_XYZ", "MSFT"]
        results = fetch_all_prices(tickers, period="1mo", max_workers=3)
        
        # Should have at least the valid ones
        assert "AAPL" in results
        assert "MSFT" in results


# Run with: pytest tests/unit/test_price_fetcher.py -v
