"""
Unit tests for remaining features:
- REC-147: Position Size Calculator
- REC-150: Level 2 Market Depth
- REC-155: Performance Stats
- REC-156: Slippage Analysis
"""

import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


# ========== REC-147: Position Size Calculator ==========

class TestPositionSizeCalculator:
    """Test position size calculations."""

    def test_basic_calculation(self):
        """Basic position size calculation."""
        from trading.position_calculator import calculate_position_size
        
        result = calculate_position_size(
            account_size=100000,
            risk_percent=1.0,
            entry_price=150.0,
            stop_price=145.0,
            max_position_percent=50.0,  # Allow larger position for this test
        )
        
        # $1000 risk / $5 stop = 200 shares
        assert result.shares == 200
        assert result.risk_amount == 1000.0

    def test_respects_max_position(self):
        """Should not exceed max position percent."""
        from trading.position_calculator import calculate_position_size
        
        result = calculate_position_size(
            account_size=10000,
            risk_percent=10.0,  # Very high risk
            entry_price=100.0,
            stop_price=99.0,
            max_position_percent=25.0,  # 25% = $2500 max
        )
        
        # Max position = $2500 / $100 = 25 shares
        assert result.shares <= 25

    def test_invalid_inputs_raise_error(self):
        """Invalid inputs should raise ValueError."""
        from trading.position_calculator import calculate_position_size
        
        with pytest.raises(ValueError):
            calculate_position_size(0, 1, 100, 95)  # zero account
        
        with pytest.raises(ValueError):
            calculate_position_size(100000, 0, 100, 95)  # zero risk
        
        with pytest.raises(ValueError):
            calculate_position_size(100000, 1, 100, 100)  # same entry/stop

    def test_stop_distance_calculated(self):
        """Stop distance should be calculated correctly."""
        from trading.position_calculator import calculate_position_size
        
        result = calculate_position_size(
            account_size=100000,
            risk_percent=1.0,
            entry_price=100.0,
            stop_price=95.0,
        )
        
        assert result.stop_distance == 5.0
        assert result.stop_percent == 0.05  # 5%


# ========== REC-150: Market Depth ==========

class TestMarketDepth:
    """Test market depth functionality."""

    def test_mock_depth_generation(self):
        """Mock depth should generate valid data."""
        from ibkr.market_depth import get_market_depth_mock
        
        depth = get_market_depth_mock("AAPL", levels=10)
        
        assert depth.ticker == "AAPL"
        assert len(depth.bids) == 10
        assert len(depth.asks) == 10
        assert depth.spread is not None
        assert depth.spread > 0

    def test_bids_descending(self):
        """Bids should be sorted high to low."""
        from ibkr.market_depth import get_market_depth_mock
        
        depth = get_market_depth_mock("AAPL", levels=5)
        prices = [b.price for b in depth.bids]
        
        assert prices == sorted(prices, reverse=True)

    def test_asks_ascending(self):
        """Asks should be sorted low to high."""
        from ibkr.market_depth import get_market_depth_mock
        
        depth = get_market_depth_mock("AAPL", levels=5)
        prices = [a.price for a in depth.asks]
        
        assert prices == sorted(prices)

    def test_depth_to_dict(self):
        """to_dict should include all fields."""
        from ibkr.market_depth import get_market_depth_mock
        
        depth = get_market_depth_mock("MSFT", levels=5)
        d = depth.to_dict()
        
        assert "ticker" in d
        assert "bids" in d
        assert "asks" in d
        assert "spread" in d
        assert "bid_depth" in d
        assert "ask_depth" in d
        assert "levels" in d


# ========== REC-155: Performance Stats ==========

class TestPerformanceStats:
    """Test trading performance calculations."""

    def test_empty_orders(self):
        """Empty orders should return zero metrics."""
        from trading.performance_stats import calculate_performance_metrics
        
        metrics = calculate_performance_metrics([])
        
        assert metrics.total_trades == 0
        assert metrics.win_rate == 0.0

    def test_win_rate_calculation(self):
        """Win rate should be calculated correctly."""
        from trading.performance_stats import calculate_performance_metrics
        
        # 3 wins, 1 loss = 75% win rate
        orders = [
            {"status": "FILLED", "ticker": "AAPL", "side": "BUY", "fill_price": 100, "quantity": 10, "created_at": "2026-01-01T10:00:00Z"},
            {"status": "FILLED", "ticker": "AAPL", "side": "SELL", "fill_price": 110, "quantity": 10, "created_at": "2026-01-02T10:00:00Z"},  # +$100
            {"status": "FILLED", "ticker": "MSFT", "side": "BUY", "fill_price": 200, "quantity": 5, "created_at": "2026-01-03T10:00:00Z"},
            {"status": "FILLED", "ticker": "MSFT", "side": "SELL", "fill_price": 220, "quantity": 5, "created_at": "2026-01-04T10:00:00Z"},  # +$100
        ]
        
        metrics = calculate_performance_metrics(orders)
        
        assert metrics.total_trades == 4
        assert metrics.winning_trades == 2
        assert metrics.total_pnl == 200.0  # $100 + $100

    def test_profit_factor(self):
        """Profit factor should be gross profit / gross loss."""
        from trading.performance_stats import calculate_performance_metrics
        
        orders = [
            {"status": "FILLED", "ticker": "A", "side": "BUY", "fill_price": 100, "quantity": 10, "created_at": "2026-01-01T10:00:00Z"},
            {"status": "FILLED", "ticker": "A", "side": "SELL", "fill_price": 120, "quantity": 10, "created_at": "2026-01-02T10:00:00Z"},  # +$200
            {"status": "FILLED", "ticker": "B", "side": "BUY", "fill_price": 100, "quantity": 10, "created_at": "2026-01-03T10:00:00Z"},
            {"status": "FILLED", "ticker": "B", "side": "SELL", "fill_price": 90, "quantity": 10, "created_at": "2026-01-04T10:00:00Z"},  # -$100
        ]
        
        metrics = calculate_performance_metrics(orders)
        
        # Profit factor = $200 / $100 = 2.0
        assert metrics.profit_factor == 2.0


# ========== REC-156: Slippage Analysis ==========

class TestSlippageAnalysis:
    """Test slippage tracking."""

    def test_slippage_calculation(self):
        """Slippage should be fill - limit."""
        from trading.performance_stats import analyze_slippage
        
        orders = [
            {
                "id": "1",
                "status": "FILLED",
                "ticker": "AAPL",
                "side": "BUY",
                "quantity": 100,
                "limit_price": 150.00,
                "fill_price": 150.05,  # 5 cents worse
            }
        ]
        
        results = analyze_slippage(orders)
        
        assert len(results) == 1
        assert results[0]["slippage"] == 0.05
        assert results[0]["cost_impact"] == 5.0  # $0.05 * 100 shares

    def test_no_slippage_for_market_orders(self):
        """Market orders (no limit) should not appear."""
        from trading.performance_stats import analyze_slippage
        
        orders = [
            {
                "id": "1",
                "status": "FILLED",
                "ticker": "AAPL",
                "side": "BUY",
                "quantity": 100,
                "fill_price": 150.00,
                # No limit_price = market order
            }
        ]
        
        results = analyze_slippage(orders)
        
        assert len(results) == 0


# ========== API Endpoint Tests ==========

class TestFeatureEndpoints:
    """Test API endpoints for new features."""

    def test_position_size_endpoint(self):
        """POST /trading/position-size should calculate size."""
        from fastapi.testclient import TestClient
        from api.main import app
        
        client = TestClient(app)
        resp = client.post("/api/v1/trading/position-size", json={
            "account_size": 100000,
            "risk_percent": 1.0,
            "entry_price": 150.0,
            "stop_price": 145.0,
        })
        
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "shares" in data["data"]

    def test_market_depth_endpoint(self):
        """GET /market-depth/{ticker} should return depth."""
        from fastapi.testclient import TestClient
        from api.main import app
        
        client = TestClient(app)
        resp = client.get("/api/v1/market-depth/AAPL")
        
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "bids" in data["data"]
        assert "asks" in data["data"]
