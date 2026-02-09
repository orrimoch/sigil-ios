"""
Integration tests for Risk Phase 3 features.

REC-250: Phase 3 Integration Tests
Tests that verify Phase 3 features work end-to-end.
"""

import pytest
import sys
import os
from pathlib import Path
from httpx import AsyncClient, ASGITransport

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

# Disable auth for testing
os.environ["AUTH_REQUIRED"] = "false"


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    """Create async test client."""
    os.environ["AUTH_REQUIRED"] = "false"
    
    from api.main import app
    import api.main
    api.main.AUTH_REQUIRED = False
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


class TestRegimeEndpoints:
    """Tests for regime detection endpoints."""
    
    @pytest.mark.anyio
    async def test_get_market_regime(self, client):
        """GET /api/v1/market/regime should return regime data."""
        response = await client.get("/api/v1/market/regime")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "regime" in data["data"]
        assert "confidence" in data["data"]
        assert "threshold_adjustment" in data["data"]
        assert data["data"]["regime"] in ["low_vol", "normal", "high_vol", "crisis"]
    
    @pytest.mark.anyio
    async def test_regime_cached(self, client):
        """Regime detection should be cached."""
        # First call
        response1 = await client.get("/api/v1/market/regime")
        # Second call (should be faster due to cache)
        response2 = await client.get("/api/v1/market/regime")
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        
        # Both should return same regime
        data1 = response1.json()["data"]
        data2 = response2.json()["data"]
        assert data1["regime"] == data2["regime"]


class TestPatternMemoryEndpoints:
    """Tests for pattern memory endpoints."""
    
    @pytest.mark.anyio
    async def test_get_pattern_stats(self, client):
        """GET /api/v1/risk/patterns/stats should return stats."""
        response = await client.get("/api/v1/risk/patterns/stats")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "total_events" in data["data"]
        assert "total_trades" in data["data"]
    
    @pytest.mark.anyio
    async def test_get_events_empty(self, client):
        """GET /api/v1/risk/patterns/events should work with empty data."""
        response = await client.get("/api/v1/risk/patterns/events")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "count" in data
        assert "data" in data
    
    @pytest.mark.anyio
    async def test_get_events_with_filter(self, client):
        """GET /api/v1/risk/patterns/events with filters."""
        response = await client.get(
            "/api/v1/risk/patterns/events",
            params={"ticker": "AAPL", "limit": 10}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
    
    @pytest.mark.anyio
    async def test_get_trades_empty(self, client):
        """GET /api/v1/risk/patterns/trades should work with empty data."""
        response = await client.get("/api/v1/risk/patterns/trades")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "count" in data
    
    @pytest.mark.anyio
    async def test_stop_analysis(self, client):
        """GET /api/v1/risk/patterns/analysis/stops should return analysis."""
        response = await client.get("/api/v1/risk/patterns/analysis/stops")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
    
    @pytest.mark.anyio
    async def test_regime_performance_analysis(self, client):
        """GET /api/v1/risk/patterns/analysis/regimes should return analysis."""
        response = await client.get("/api/v1/risk/patterns/analysis/regimes")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
    
    @pytest.mark.anyio
    async def test_similar_situations(self, client):
        """GET /api/v1/risk/patterns/similar/{ticker} should work."""
        response = await client.get(
            "/api/v1/risk/patterns/similar/AAPL",
            params={"regime": "normal", "vix_min": 15, "vix_max": 25}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "count" in data


class TestSectorExposureEndpoints:
    """Tests for sector exposure endpoints."""
    
    @pytest.mark.anyio
    async def test_get_sector_exposure(self, client):
        """GET /api/v1/portfolio/sectors/exposure should return exposure."""
        response = await client.get("/api/v1/portfolio/sectors/exposure")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "exposures" in data["data"]
        assert "diversification_score" in data["data"]
    
    @pytest.mark.anyio
    async def test_sector_exposure_custom_threshold(self, client):
        """Sector exposure with custom threshold."""
        response = await client.get(
            "/api/v1/portfolio/sectors/exposure",
            params={"warn_threshold": 0.25}
        )
        
        assert response.status_code == 200


class TestPortfolioVaREndpoints:
    """Tests for correlated portfolio VaR endpoints."""
    
    @pytest.mark.anyio
    async def test_get_correlated_var(self, client):
        """GET /api/v1/portfolio/var/correlated should return VaR."""
        response = await client.get("/api/v1/portfolio/var/correlated")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        # Empty portfolio case
        assert "portfolio_value" in data["data"]
    
    @pytest.mark.anyio
    async def test_correlated_var_custom_lookback(self, client):
        """Correlated VaR with custom lookback."""
        response = await client.get(
            "/api/v1/portfolio/var/correlated",
            params={"lookback_days": 60}
        )
        
        assert response.status_code == 200


class TestEndToEndFlows:
    """End-to-end integration tests."""
    
    @pytest.mark.anyio
    async def test_regime_affects_thresholds(self, client):
        """Regime detection should affect threshold adjustment."""
        response = await client.get("/api/v1/market/regime")
        
        assert response.status_code == 200
        data = response.json()["data"]
        
        regime = data["regime"]
        adjustment = data["threshold_adjustment"]
        
        # Verify adjustment matches regime
        expected_adjustments = {
            "low_vol": -2.0,
            "normal": 0.0,
            "high_vol": 3.0,
            "crisis": 7.0,
        }
        
        assert adjustment == expected_adjustments.get(regime, 0.0)
    
    @pytest.mark.anyio
    async def test_combined_risk_overview(self, client):
        """Multiple risk endpoints should work together."""
        # Get regime
        regime_response = await client.get("/api/v1/market/regime")
        assert regime_response.status_code == 200
        
        # Get pattern stats
        stats_response = await client.get("/api/v1/risk/patterns/stats")
        assert stats_response.status_code == 200
        
        # Get sector exposure
        sector_response = await client.get("/api/v1/portfolio/sectors/exposure")
        assert sector_response.status_code == 200
        
        # All should succeed
        assert regime_response.json()["success"] is True
        assert stats_response.json()["success"] is True
        assert sector_response.json()["success"] is True


class TestBacktestRiskIntegration:
    """Tests for backtest risk integration module."""
    
    def test_risk_integration_creation(self):
        """Should create risk integration with defaults."""
        from backtest.risk_integration import create_risk_integration
        
        integration = create_risk_integration()
        
        assert integration.enable_regime_adjustment is True
        assert integration.enable_sector_limits is True
        assert integration.sector_limit_pct == 0.30
    
    def test_threshold_adjustment_by_regime(self):
        """Should adjust thresholds based on regime."""
        from backtest.risk_integration import BacktestRiskIntegration
        
        integration = BacktestRiskIntegration()
        
        # Set cached regime
        integration._regime_cache["2024-01-01"] = "crisis"
        
        buy, sell = integration.adjust_thresholds("2024-01-01", 70.0, 50.0)
        
        # Crisis adjustment is +7
        assert buy == 77.0
        assert sell == 57.0
    
    def test_threshold_no_adjustment_when_disabled(self):
        """Should not adjust when disabled."""
        from backtest.risk_integration import BacktestRiskIntegration
        
        integration = BacktestRiskIntegration(enable_regime_adjustment=False)
        integration._regime_cache["2024-01-01"] = "crisis"
        
        buy, sell = integration.adjust_thresholds("2024-01-01", 70.0, 50.0)
        
        # No adjustment
        assert buy == 70.0
        assert sell == 50.0
    
    def test_sector_limit_check(self):
        """Should check sector limits correctly."""
        from backtest.risk_integration import BacktestRiskIntegration
        
        integration = BacktestRiskIntegration(sector_limit_pct=0.30)
        integration._sector_cache = {
            "AAPL": "Technology",
            "MSFT": "Technology",
            "JPM": "Financials",
        }
        
        # Current portfolio: AAPL $25k (25%)
        positions = {
            "AAPL": {"current_value": 25000},
        }
        
        # Try to add MSFT $10k - would make tech 35% (exceeds 30%)
        allowed, warning = integration.check_sector_limit(
            "MSFT",
            10000,
            positions,
            100000,
        )
        
        assert allowed is False
        assert "Technology" in warning
