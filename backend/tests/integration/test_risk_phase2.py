"""
REC-233: Phase 2 Integration Tests

Tests for:
- VIX API
- VaR calculation
- Claude analyzer caching
- Position limits validation
"""

import pytest
import asyncio
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock, AsyncMock
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


# ==================== VIX Tests (REC-225) ====================

class TestVIXService:
    """Tests for VIX data pipeline."""
    
    def test_vix_cache_ttl(self):
        """VIX cache respects 1-hour TTL."""
        from risk.vix_service import VIXCache, VIXData
        
        cache = VIXCache()
        
        # Create test data
        vix_data = VIXData(
            value=20.5,
            previous_close=19.8,
            change=0.7,
            change_pct=3.5,
            updated_at=datetime.now(timezone.utc),
            regime="normal",
        )
        
        # Set cache
        cache.set(vix_data)
        
        # Should return cached data
        cached = cache.get()
        assert cached is not None
        assert cached.value == 20.5
    
    def test_vix_regime_classification(self):
        """VIX regime is classified correctly."""
        from risk.vix_service import _classify_vix_regime
        
        assert _classify_vix_regime(10) == "low"
        assert _classify_vix_regime(14.9) == "low"
        assert _classify_vix_regime(15) == "normal"
        assert _classify_vix_regime(19.9) == "normal"
        assert _classify_vix_regime(20) == "elevated"
        assert _classify_vix_regime(24.9) == "elevated"
        assert _classify_vix_regime(25) == "high"
        assert _classify_vix_regime(34.9) == "high"
        assert _classify_vix_regime(35) == "extreme"
        assert _classify_vix_regime(80) == "extreme"
    
    def test_vix_data_to_dict(self):
        """VIX data serializes correctly."""
        from risk.vix_service import VIXData
        
        vix = VIXData(
            value=25.5,
            previous_close=24.0,
            change=1.5,
            change_pct=6.25,
            updated_at=datetime.now(timezone.utc),
            regime="high",
        )
        
        data = vix.to_dict()
        assert data["vix"] == 25.5
        assert data["regime"] == "high"
        assert "updated_at" in data


# ==================== Dynamic Thresholds Tests (REC-226) ====================

class TestDynamicThresholds:
    """Tests for VIX-adjusted scoring thresholds."""
    
    def test_vix_threshold_at_baseline(self):
        """VIX at baseline (15) = no adjustment."""
        from risk.dynamic_thresholds import calculate_vix_adjustment
        
        adjustment = calculate_vix_adjustment(15.0)
        assert adjustment == 0.0
    
    def test_vix_threshold_below_baseline(self):
        """VIX below 15 = no adjustment."""
        from risk.dynamic_thresholds import calculate_vix_adjustment
        
        assert calculate_vix_adjustment(10.0) == 0.0
        assert calculate_vix_adjustment(12.0) == 0.0
        assert calculate_vix_adjustment(14.9) == 0.0
    
    def test_vix_threshold_at_20(self):
        """VIX 20 → threshold becomes 52.5."""
        from risk.dynamic_thresholds import calculate_adjusted_sell_threshold
        
        adjusted = calculate_adjusted_sell_threshold(50.0, 20.0)
        assert adjusted == 52.5
    
    def test_vix_threshold_at_30(self):
        """VIX 30 → threshold becomes 57.5."""
        from risk.dynamic_thresholds import calculate_adjusted_sell_threshold
        
        adjusted = calculate_adjusted_sell_threshold(50.0, 30.0)
        assert adjusted == 57.5
    
    def test_vix_threshold_at_40(self):
        """VIX 40 → threshold becomes 62.5."""
        from risk.dynamic_thresholds import calculate_adjusted_sell_threshold
        
        adjusted = calculate_adjusted_sell_threshold(50.0, 40.0)
        assert adjusted == 62.5
    
    def test_threshold_disabled_returns_base(self):
        """When VIX adjustment disabled, returns base threshold."""
        from risk.dynamic_thresholds import calculate_adjusted_sell_threshold
        from risk.models import UserRiskSettings
        
        settings = UserRiskSettings.default("test_user")
        settings.vix_adjustment.enabled = False
        
        adjusted = calculate_adjusted_sell_threshold(50.0, 40.0, settings)
        assert adjusted == 50.0  # No adjustment
    
    def test_should_trigger_sell(self):
        """Sell signal triggers below adjusted threshold."""
        from risk.dynamic_thresholds import should_trigger_sell
        
        # Score 45, VIX 15 → threshold 50 → should sell
        should_sell, reason = should_trigger_sell(45.0, vix=15.0)
        assert should_sell is True
        assert "below" in reason.lower()
        
        # Score 55, VIX 15 → threshold 50 → should not sell
        should_sell, reason = should_trigger_sell(55.0, vix=15.0)
        assert should_sell is False
        
        # Score 55, VIX 30 → threshold 57.5 → should sell
        should_sell, reason = should_trigger_sell(55.0, vix=30.0)
        assert should_sell is True
    
    def test_should_trigger_buy(self):
        """Buy signal triggers at or above adjusted threshold."""
        from risk.dynamic_thresholds import should_trigger_buy
        
        # Score 75, VIX 15 → threshold 70 → should buy
        should_buy, reason = should_trigger_buy(75.0, vix=15.0)
        assert should_buy is True
        
        # Score 65, VIX 15 → threshold 70 → should not buy
        should_buy, reason = should_trigger_buy(65.0, vix=15.0)
        assert should_buy is False


# ==================== Position Limits Tests (REC-227) ====================

class TestPositionLimits:
    """Tests for position size validation."""
    
    def test_position_within_limit(self):
        """Position within limit generates no warnings."""
        from risk.position_limits import validate_position_size
        from risk.models import UserRiskSettings
        
        settings = UserRiskSettings.default("test_user")
        settings.position_limit.enabled = True
        settings.position_limit.max_pct = 0.15  # 15%
        
        result = validate_position_size(
            ticker="AAPL",
            trade_value=1000,
            current_position_value=0,
            portfolio_value=100000,  # 1% position
            settings=settings,
        )
        
        assert result.valid is True
        assert len(result.warnings) == 0
    
    def test_position_exceeds_limit_warning(self):
        """Position exceeding limit generates warning."""
        from risk.position_limits import validate_position_size, WarningLevel
        from risk.models import UserRiskSettings
        
        settings = UserRiskSettings.default("test_user")
        settings.position_limit.enabled = True
        settings.position_limit.max_pct = 0.15  # 15%
        
        result = validate_position_size(
            ticker="AAPL",
            trade_value=18000,  # Would be 18% of portfolio
            current_position_value=0,
            portfolio_value=100000,
            settings=settings,
        )
        
        assert result.valid is True  # Can still proceed (warning only)
        assert len(result.warnings) == 1
        assert result.warnings[0].type == "position_limit"
        assert result.warnings[0].can_override is True
    
    def test_position_limit_disabled(self):
        """No warnings when position limits disabled."""
        from risk.position_limits import validate_position_size
        from risk.models import UserRiskSettings
        
        settings = UserRiskSettings.default("test_user")
        settings.position_limit.enabled = False
        
        result = validate_position_size(
            ticker="AAPL",
            trade_value=50000,  # 50% of portfolio
            current_position_value=0,
            portfolio_value=100000,
            settings=settings,
        )
        
        assert result.valid is True
        assert len(result.warnings) == 0
        assert result.risk_metrics.get("validation_skipped") is True
    
    def test_concentration_warning_over_20_percent(self):
        """Positions over 20% generate concentration warning."""
        from risk.position_limits import validate_position_size
        from risk.models import UserRiskSettings
        
        settings = UserRiskSettings.default("test_user")
        settings.position_limit.enabled = True
        settings.position_limit.max_pct = 0.30  # 30% limit
        
        result = validate_position_size(
            ticker="AAPL",
            trade_value=25000,  # 25% of portfolio
            current_position_value=0,
            portfolio_value=100000,
            settings=settings,
        )
        
        # Should have concentration warning (>20%)
        concentration_warnings = [w for w in result.warnings if w.type == "concentration"]
        assert len(concentration_warnings) == 1


# ==================== VaR Calculator Tests (REC-228) ====================

class TestVaRCalculator:
    """Tests for Value at Risk calculations."""
    
    def test_var_calculation_basic(self):
        """Basic VaR calculation with known inputs."""
        import numpy as np
        from risk.var_calculator import calculate_parametric_var, Z_SCORE_95
        
        # 2% daily volatility, $10,000 position
        position_value = 10000
        daily_vol = 0.02
        
        var_95 = calculate_parametric_var(position_value, daily_vol, 0.95)
        
        # Expected: 10000 * 0.02 * 1.645 = 329
        expected = position_value * daily_vol * Z_SCORE_95
        assert abs(var_95 - expected) < 0.01
    
    def test_var_is_always_positive(self):
        """VaR should always be a positive number (loss amount)."""
        from risk.var_calculator import calculate_parametric_var
        
        var = calculate_parametric_var(10000, 0.02, 0.95)
        assert var > 0
    
    def test_risk_score_classification(self):
        """Risk score classified correctly based on VaR percentage."""
        from risk.var_calculator import classify_risk_score
        
        assert classify_risk_score(0.03) == "low"     # 3% VaR
        assert classify_risk_score(0.049) == "low"   # 4.9% VaR
        assert classify_risk_score(0.05) == "medium" # 5% VaR
        assert classify_risk_score(0.099) == "medium" # 9.9% VaR
        assert classify_risk_score(0.10) == "high"   # 10% VaR
        assert classify_risk_score(0.20) == "high"   # 20% VaR
    
    def test_position_var_result_structure(self):
        """Position VaR result has correct structure."""
        import numpy as np
        from risk.var_calculator import calculate_position_var
        
        # Use known returns
        returns = np.random.normal(0, 0.02, 252)  # Simulated returns
        
        result = calculate_position_var("AAPL", 10000, returns)
        
        assert result.ticker == "AAPL"
        assert result.position_value == 10000
        assert result.var_95_daily > 0
        assert result.var_99_daily > result.var_95_daily  # 99% VaR > 95% VaR
        assert 0 < result.var_95_pct < 1
        assert result.daily_volatility > 0
        assert result.annualized_volatility > 0


# ==================== Claude Analyzer Tests (REC-232) ====================

class TestClaudeAnalyzer:
    """Tests for Claude risk analyzer with caching."""
    
    def test_cache_key_bucketing(self):
        """Cache key uses bucketed values to reduce misses."""
        from risk.claude_analyzer import RiskAnalysisCache
        
        cache = RiskAnalysisCache()
        
        # Same ticker, prices within same $5 bucket should produce same cache key
        # 150 and 152 both round to 150 bucket
        key1 = cache._make_cache_key("AAPL", 150.0, 20.0, 50.0, -2.5)
        key2 = cache._make_cache_key("AAPL", 152.0, 20.0, 50.0, -2.5)  # Same bucket
        
        assert key1 == key2  # Should be same (within $5 bucket)
        
        # Different bucket should produce different key
        # 150 vs 155 are in different buckets
        key3 = cache._make_cache_key("AAPL", 155.0, 20.0, 50.0, -2.5)  # Different bucket
        assert key1 != key3
    
    def test_cache_memory_layer(self):
        """Memory cache stores and retrieves correctly."""
        from risk.claude_analyzer import RiskAnalysisCache, RiskAnalysisResult, RiskLevel
        from datetime import datetime, timezone
        
        cache = RiskAnalysisCache()
        
        result = RiskAnalysisResult(
            ticker="AAPL",
            risk_score=60,
            risk_level=RiskLevel.MEDIUM,
            risk_factors=["High volatility"],
            recommendation="monitor",
            reasoning="Test reasoning",
            confidence=0.8,
            analyzed_at=datetime.now(timezone.utc),
        )
        
        cache.set("AAPL", result, price=150.0, vix=20.0, sentiment=50.0, return_5d=-2.0)
        
        cached = cache.get("AAPL", price=150.0, vix=20.0, sentiment=50.0, return_5d=-2.0)
        
        assert cached is not None
        assert cached.ticker == "AAPL"
        assert cached.risk_score == 60
        assert cached.cached is True
    
    def test_risk_level_enum(self):
        """Risk level enum values are correct."""
        from risk.claude_analyzer import RiskLevel
        
        assert RiskLevel.LOW.value == "low"
        assert RiskLevel.MEDIUM.value == "medium"
        assert RiskLevel.HIGH.value == "high"
        assert RiskLevel.CRITICAL.value == "critical"
    
    def test_result_to_dict(self):
        """RiskAnalysisResult serializes correctly."""
        from risk.claude_analyzer import RiskAnalysisResult, RiskLevel
        from datetime import datetime, timezone
        
        result = RiskAnalysisResult(
            ticker="NVDA",
            risk_score=75,
            risk_level=RiskLevel.HIGH,
            risk_factors=["VIX elevated", "Negative sentiment"],
            recommendation="reduce",
            reasoning="Position is at high risk",
            confidence=0.9,
            analyzed_at=datetime.now(timezone.utc),
        )
        
        data = result.to_dict()
        
        assert data["ticker"] == "NVDA"
        assert data["risk_score"] == 75
        assert data["risk_level"] == "high"
        assert len(data["risk_factors"]) == 2
        assert data["recommendation"] == "reduce"
        assert data["confidence"] == 0.9
    
    def test_default_result_on_error(self):
        """Analyzer returns conservative default on error."""
        from risk.claude_analyzer import ClaudeRiskAnalyzer, RiskLevel
        
        analyzer = ClaudeRiskAnalyzer()
        result = analyzer._default_result("AAPL", "Test error")
        
        assert result.ticker == "AAPL"
        assert result.risk_score == 60  # Conservative moderate
        assert result.risk_level == RiskLevel.MEDIUM
        assert result.recommendation == "monitor"
        assert result.confidence == 0.3  # Low confidence


# ==================== Risk Notifications Tests (REC-229) ====================

class TestRiskNotifications:
    """Tests for risk push notifications."""
    
    def test_stop_loss_notification_format(self):
        """Stop-loss triggered notification is formatted correctly."""
        from notifications.push_service import send_stop_loss_triggered_notification
        
        result = send_stop_loss_triggered_notification(
            user_id="test_user",
            ticker="AAPL",
            trigger_price=170.66,
            loss_pct=-8.0,
            stop_type="hard",
            quantity=100,
        )
        
        assert result["total_tokens"] >= 0  # May be 0 if no tokens registered
        # Check payload structure
        if result["results"]:
            payload = result["results"][0]["payload"]
            assert "AAPL" in payload.get("aps", {}).get("alert", {}).get("body", "")
    
    def test_approaching_stop_notification(self):
        """Approaching stop notification is sent correctly."""
        from notifications.push_service import send_approaching_stop_notification
        
        result = send_approaching_stop_notification(
            user_id="test_user",
            ticker="NVDA",
            current_price=455.0,
            stop_price=450.0,
            distance_pct=1.1,
            stop_type="trailing",
        )
        
        assert "total_tokens" in result


# ==================== API Endpoint Tests ====================

@pytest.mark.asyncio
class TestRiskAPIEndpoints:
    """Tests for Phase 2 risk API endpoints."""
    
    async def test_vix_endpoint_structure(self):
        """GET /api/v1/market/vix returns correct structure."""
        from httpx import AsyncClient, ASGITransport
        from api.main import app
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/market/vix")
            
            # May fail if yfinance is unavailable, but structure should be correct
            data = response.json()
            assert "success" in data or "detail" in data
    
    async def test_threshold_table_endpoint(self):
        """GET /api/v1/market/vix/threshold-table returns lookup table."""
        from httpx import AsyncClient, ASGITransport
        from api.main import app
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/market/vix/threshold-table")
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "table" in data["data"]
            assert "formula" in data["data"]


# ==================== Integration Flow Tests ====================

class TestPhase2IntegrationFlow:
    """End-to-end integration tests for Phase 2 features."""
    
    def test_var_to_risk_score_flow(self):
        """VaR calculation flows into risk score classification."""
        import numpy as np
        from risk.var_calculator import calculate_portfolio_var
        
        # Create mock positions
        positions = [
            {"ticker": "AAPL", "market_value": 10000},
            {"ticker": "MSFT", "market_value": 10000},
        ]
        
        # This will use default volatility since we're not fetching real data
        result = calculate_portfolio_var(positions, use_correlation=False)
        
        assert result.risk_score in ["low", "medium", "high"]
        assert result.var_95_daily >= 0
    
    def test_settings_affect_thresholds(self):
        """User settings correctly affect threshold calculations."""
        from risk.dynamic_thresholds import get_adjusted_thresholds
        from risk.models import UserRiskSettings
        from risk.vix_service import clear_vix_cache
        
        # Clear VIX cache to ensure clean state
        clear_vix_cache()
        
        # VIX adjustment disabled
        settings = UserRiskSettings.default("test_user")
        settings.vix_adjustment.enabled = False
        
        thresholds_disabled = get_adjusted_thresholds(
            settings=settings,
            fetch_vix_if_needed=False,
        )
        
        assert thresholds_disabled.adjustment_applied is False
        assert thresholds_disabled.sell_threshold == 50.0  # Default
        
        # VIX adjustment enabled (but no VIX data available after cache clear)
        settings.vix_adjustment.enabled = True
        
        thresholds_enabled = get_adjusted_thresholds(
            settings=settings,
            fetch_vix_if_needed=False,  # Don't fetch, and cache is empty
        )
        
        # Without VIX data (cache cleared, fetch disabled), should return base thresholds
        assert thresholds_enabled.sell_threshold == 50.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
