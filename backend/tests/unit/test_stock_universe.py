"""
Unit tests for F1.1 Stock Universe Management

Tests cover:
- S&P 500 ticker fetching (Wikipedia)
- NASDAQ screener ticker fetching (NASDAQ API)
- Combined US large-cap ticker list
- Individual stock info lookup
- Full universe build with market cap filtering
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from data.stock_universe import (
    fetch_sp500_tickers,
    fetch_nasdaq_screener_tickers,
    fetch_us_large_cap_tickers,
    get_stock_info,
    build_universe,
    MIN_MARKET_CAP,
)


class TestFetchSP500Tickers:
    """Tests for fetching S&P 500 tickers."""
    
    def test_returns_list(self):
        """Should return a list of tickers."""
        tickers = fetch_sp500_tickers()
        assert isinstance(tickers, list)
    
    def test_returns_around_500_tickers(self):
        """Should return approximately 500 tickers."""
        tickers = fetch_sp500_tickers()
        assert 490 <= len(tickers) <= 510
    
    def test_tickers_are_strings(self):
        """All tickers should be strings."""
        tickers = fetch_sp500_tickers()
        assert all(isinstance(t, str) for t in tickers)
    
    def test_contains_known_tickers(self):
        """Should contain well-known tickers like AAPL, MSFT."""
        tickers = fetch_sp500_tickers()
        assert "AAPL" in tickers
        assert "MSFT" in tickers


class TestFetchNasdaqScreenerTickers:
    """Tests for fetching tickers from NASDAQ screener API."""
    
    def test_returns_list(self):
        """Should return a list of tickers."""
        tickers = fetch_nasdaq_screener_tickers()
        assert isinstance(tickers, list)
    
    def test_returns_substantial_count(self):
        """Should return a large number of tickers (>500)."""
        tickers = fetch_nasdaq_screener_tickers()
        assert len(tickers) > 500
    
    def test_tickers_are_strings(self):
        """All tickers should be strings."""
        tickers = fetch_nasdaq_screener_tickers()
        assert all(isinstance(t, str) for t in tickers)
    
    def test_no_duplicates(self):
        """Should not contain duplicate tickers."""
        tickers = fetch_nasdaq_screener_tickers()
        assert len(tickers) == len(set(tickers))
    
    def test_contains_known_tickers(self):
        """Should contain well-known large-cap tickers."""
        tickers = fetch_nasdaq_screener_tickers()
        # At least some of these should be present
        known = {"AAPL", "MSFT", "NVDA", "JPM", "JNJ"}
        found = known.intersection(set(tickers))
        assert len(found) >= 3, f"Only found {found} out of {known}"
    
    def test_single_exchange(self):
        """Should work for a single exchange."""
        tickers = fetch_nasdaq_screener_tickers(exchanges=['NASDAQ'])
        assert len(tickers) > 100


class TestFetchUSLargeCapTickers:
    """Tests for the combined US large-cap ticker list."""
    
    def test_returns_list(self):
        """Should return a list of tickers."""
        tickers = fetch_us_large_cap_tickers()
        assert isinstance(tickers, list)
    
    def test_returns_broad_coverage(self):
        """Should return more tickers than S&P 500 alone."""
        tickers = fetch_us_large_cap_tickers()
        assert len(tickers) > 600
    
    def test_no_duplicates(self):
        """Should not contain duplicate tickers."""
        tickers = fetch_us_large_cap_tickers()
        assert len(tickers) == len(set(tickers))
    
    def test_contains_sp500_blue_chips(self):
        """Should include major S&P 500 stocks."""
        tickers = fetch_us_large_cap_tickers()
        assert "AAPL" in tickers
        assert "MSFT" in tickers


class TestGetStockInfo:
    """Tests for getting individual stock info."""
    
    def test_returns_dict_for_valid_ticker(self):
        """Should return dict for valid ticker."""
        info = get_stock_info("AAPL")
        assert isinstance(info, dict)
        assert info["ticker"] == "AAPL"
    
    def test_contains_required_fields(self):
        """Should contain all required fields."""
        info = get_stock_info("MSFT")
        required = ["ticker", "name", "sector", "market_cap"]
        for field in required:
            assert field in info
    
    def test_market_cap_is_positive(self):
        """Market cap should be positive for real stock."""
        info = get_stock_info("AAPL")
        assert info["market_cap"] > 0
    
    def test_returns_none_for_invalid_ticker(self):
        """Should return None for invalid ticker."""
        info = get_stock_info("INVALID_TICKER_XYZ123")
        assert info is None


class TestBuildUniverse:
    """Tests for building the stock universe."""
    
    @pytest.mark.slow
    def test_builds_universe_with_broad_coverage(self):
        """Should build universe with ~700-1000 stocks."""
        universe = build_universe()
        assert 500 <= len(universe) <= 1100
    
    @pytest.mark.slow
    def test_all_stocks_above_market_cap_threshold(self):
        """All stocks should be above $10B market cap."""
        universe = build_universe()
        for stock in universe:
            assert stock["market_cap"] >= MIN_MARKET_CAP, \
                f"{stock['ticker']} has market cap ${stock['market_cap']:,}"
    
    @pytest.mark.slow
    def test_universe_sorted_by_market_cap(self):
        """Universe should be sorted by market cap descending."""
        universe = build_universe()
        market_caps = [s["market_cap"] for s in universe]
        assert market_caps == sorted(market_caps, reverse=True)


class TestConstants:
    """Tests for module constants."""
    
    def test_min_market_cap_is_10b(self):
        """Minimum market cap should be $10 billion."""
        assert MIN_MARKET_CAP == 10_000_000_000


# Run with: pytest tests/unit/test_stock_universe.py -v
# Run fast tests only: pytest tests/unit/test_stock_universe.py -v -m "not slow"
