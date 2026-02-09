"""
REC-233: Phase 2 Unit Tests

Unit tests for Phase 2 risk features:
- VIX service
- Dynamic thresholds
- Position limits
- VaR calculator
- Claude analyzer
"""

import pytest
import numpy as np
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


# ==================== VIX Service Unit Tests ====================

class TestVIXServiceUnit:
    """Unit tests for VIX service."""
    
    def test_vix_data_creation(self):
        """VIXData dataclass creates correctly."""
        from risk.vix_service import VIXData
        
        now = datetime.now(timezone.utc)
        vix = VIXData(
            value=22.5,
            previous_close=21.0,
            change=1.5,
            change_pct=7.14,
            updated_at=now,
            regime="elevated",
        )
        
        assert vix.value == 22.5
        assert vix.previous_close == 21.0
        assert vix.change == 1.5
        assert vix.regime == "elevated"
    
    def test_vix_cache_clear(self):
        """Cache clear works correctly."""
        from risk.vix_service import VIXCache, VIXData
        
        cache = VIXCache()
        vix = VIXData(
            value=20.0,
            previous_close=19.0,
            change=1.0,
            change_pct=5.26,
            updated_at=datetime.now(timezone.utc),
            regime="normal",
        )
        
        cache.set(vix)
        assert cache.get() is not None
        
        cache.clear()
        assert cache.get() is None
    
    def test_vix_regime_boundaries(self):
        """VIX regime classification handles exact boundaries."""
        from risk.vix_service import _classify_vix_regime
        
        # Test exact boundaries
        assert _classify_vix_regime(14.999) == "low"
        assert _classify_vix_regime(15.0) == "normal"
        assert _classify_vix_regime(19.999) == "normal"
        assert _classify_vix_regime(20.0) == "elevated"
        assert _classify_vix_regime(24.999) == "elevated"
        assert _classify_vix_regime(25.0) == "high"
        assert _classify_vix_regime(34.999) == "high"
        assert _classify_vix_regime(35.0) == "extreme"


# ==================== Dynamic Thresholds Unit Tests ====================

class TestDynamicThresholdsUnit:
    """Unit tests for dynamic thresholds."""
    
    def test_adjustment_calculation_formula(self):
        """Adjustment formula is correct: max(0, (VIX - 15) * 0.5)."""
        from risk.dynamic_thresholds import calculate_vix_adjustment
        
        # VIX = 20: (20 - 15) * 0.5 = 2.5
        assert calculate_vix_adjustment(20.0) == 2.5
        
        # VIX = 25: (25 - 15) * 0.5 = 5.0
        assert calculate_vix_adjustment(25.0) == 5.0
        
        # VIX = 10: max(0, (10 - 15) * 0.5) = max(0, -2.5) = 0
        assert calculate_vix_adjustment(10.0) == 0.0
    
    def test_adjusted_thresholds_dataclass(self):
        """AdjustedThresholds has correct structure."""
        from risk.dynamic_thresholds import AdjustedThresholds
        
        thresholds = AdjustedThresholds(
            buy_threshold=72.5,
            sell_threshold=52.5,
            hold_min=42.5,
            vix_value=20.0,
            vix_regime="normal",
            adjustment_applied=True,
            adjustment_reason="Test reason",
        )
        
        data = thresholds.to_dict()
        assert data["buy_threshold"] == 72.5
        assert data["sell_threshold"] == 52.5
        assert data["adjustment_applied"] is True
    
    def test_threshold_table_values(self):
        """Threshold lookup table has correct values."""
        from risk.dynamic_thresholds import VIX_THRESHOLD_TABLE
        
        assert VIX_THRESHOLD_TABLE[15]["sell"] == 50.0
        assert VIX_THRESHOLD_TABLE[20]["sell"] == 52.5
        assert VIX_THRESHOLD_TABLE[30]["sell"] == 57.5


# ==================== Position Limits Unit Tests ====================

class TestPositionLimitsUnit:
    """Unit tests for position limits."""
    
    def test_position_pct_calculation(self):
        """Position percentage calculated correctly."""
        from risk.position_limits import calculate_position_pct
        
        # $10,000 position in $100,000 portfolio = 10%
        pct = calculate_position_pct(10000, 100000)
        assert pct == 0.10
        
        # Zero portfolio value returns 0
        pct = calculate_position_pct(10000, 0)
        assert pct == 0.0
    
    def test_warning_level_enum(self):
        """Warning level enum has correct values."""
        from risk.position_limits import WarningLevel
        
        assert WarningLevel.NONE.value == "none"
        assert WarningLevel.LOW.value == "low"
        assert WarningLevel.MEDIUM.value == "medium"
        assert WarningLevel.HIGH.value == "high"
    
    def test_position_warning_to_dict(self):
        """PositionWarning serializes correctly."""
        from risk.position_limits import PositionWarning, WarningLevel
        
        warning = PositionWarning(
            type="position_limit",
            level=WarningLevel.MEDIUM,
            message="Test warning",
            can_override=True,
            current_value=0.18,
            threshold_value=0.15,
        )
        
        data = warning.to_dict()
        assert data["type"] == "position_limit"
        assert data["level"] == "medium"
        assert data["can_override"] is True
    
    def test_validation_result_properties(self):
        """TradeValidationResult computed properties work."""
        from risk.position_limits import TradeValidationResult, PositionWarning, WarningLevel
        
        # No warnings
        result = TradeValidationResult(
            valid=True,
            warnings=[],
            risk_metrics={},
        )
        assert result.has_warnings is False
        assert result.highest_warning_level == WarningLevel.NONE
        
        # With warnings
        result_with_warning = TradeValidationResult(
            valid=True,
            warnings=[
                PositionWarning("test", WarningLevel.HIGH, "msg", True)
            ],
            risk_metrics={},
        )
        assert result_with_warning.has_warnings is True
        assert result_with_warning.highest_warning_level == WarningLevel.HIGH


# ==================== VaR Calculator Unit Tests ====================

class TestVaRCalculatorUnit:
    """Unit tests for VaR calculator."""
    
    def test_z_scores_correct(self):
        """Z-scores for confidence levels are correct."""
        from risk.var_calculator import Z_SCORE_95, Z_SCORE_99
        
        assert abs(Z_SCORE_95 - 1.645) < 0.01
        assert abs(Z_SCORE_99 - 2.326) < 0.01
    
    def test_volatility_calculation(self):
        """Volatility calculated correctly from returns."""
        from risk.var_calculator import calculate_volatility
        
        # Known returns with known volatility
        returns = np.array([0.01, -0.01, 0.02, -0.02, 0.01])
        daily_vol, annual_vol = calculate_volatility(returns)
        
        # Daily vol should be around 0.0141 (std of returns)
        expected_daily = np.std(returns)
        assert abs(daily_vol - expected_daily) < 0.001
        
        # Annual vol = daily * sqrt(252)
        expected_annual = expected_daily * np.sqrt(252)
        assert abs(annual_vol - expected_annual) < 0.01
    
    def test_var_result_structure(self):
        """VaRResult has correct structure."""
        from risk.var_calculator import VaRResult
        from datetime import datetime
        
        result = VaRResult(
            ticker="AAPL",
            position_value=10000,
            var_95_daily=329,
            var_99_daily=465,
            var_95_pct=0.0329,
            var_99_pct=0.0465,
            daily_volatility=0.02,
            annualized_volatility=0.317,
            calculated_at=datetime.now(),
        )
        
        data = result.to_dict()
        assert data["ticker"] == "AAPL"
        assert "var_95_daily" in data
        assert "var_99_daily" in data
    
    def test_portfolio_var_result_structure(self):
        """PortfolioVaRResult has correct structure."""
        from risk.var_calculator import PortfolioVaRResult
        from datetime import datetime
        
        result = PortfolioVaRResult(
            total_value=100000,
            var_95_daily=2000,
            var_99_daily=2800,
            var_95_pct=0.02,
            var_99_pct=0.028,
            risk_score="low",
            position_vars=[],
            correlation_benefit=0.15,
            calculated_at=datetime.now(),
        )
        
        data = result.to_dict()
        assert data["risk_score"] == "low"
        assert data["correlation_benefit"] == 0.15


# ==================== Claude Analyzer Unit Tests ====================

class TestClaudeAnalyzerUnit:
    """Unit tests for Claude risk analyzer."""
    
    def test_risk_level_from_value(self):
        """RiskLevel enum can be created from string."""
        from risk.claude_analyzer import RiskLevel
        
        assert RiskLevel("low") == RiskLevel.LOW
        assert RiskLevel("medium") == RiskLevel.MEDIUM
        assert RiskLevel("high") == RiskLevel.HIGH
        assert RiskLevel("critical") == RiskLevel.CRITICAL
    
    def test_result_from_dict(self):
        """RiskAnalysisResult can be created from dict."""
        from risk.claude_analyzer import RiskAnalysisResult, RiskLevel
        
        data = {
            "ticker": "AAPL",
            "risk_score": 65,
            "risk_level": "medium",
            "risk_factors": ["High VIX"],
            "recommendation": "monitor",
            "reasoning": "Test",
            "confidence": 0.8,
            "analyzed_at": "2024-01-01T00:00:00+00:00",
        }
        
        result = RiskAnalysisResult.from_dict(data)
        assert result.ticker == "AAPL"
        assert result.risk_score == 65
        assert result.risk_level == RiskLevel.MEDIUM
    
    def test_cache_stats_structure(self):
        """Cache stats have correct structure."""
        from risk.claude_analyzer import RiskAnalysisCache
        
        cache = RiskAnalysisCache()
        stats = cache.get_stats()
        
        assert "memory_entries" in stats
        assert "sqlite_entries" in stats
        assert "hits" in stats
        assert "misses" in stats
        assert "hit_rate" in stats
    
    def test_analyzer_default_model(self):
        """Analyzer uses Haiku model by default."""
        from risk.claude_analyzer import ClaudeRiskAnalyzer, CLAUDE_MODEL
        
        analyzer = ClaudeRiskAnalyzer()
        assert analyzer.model == CLAUDE_MODEL
        assert "haiku" in analyzer.model.lower()


# ==================== Edge Cases ====================

class TestEdgeCases:
    """Edge case tests for robustness."""
    
    def test_zero_portfolio_value(self):
        """Position limits handle zero portfolio value."""
        from risk.position_limits import validate_position_size
        from risk.models import UserRiskSettings
        
        settings = UserRiskSettings.default("test")
        settings.position_limit.enabled = True
        
        result = validate_position_size(
            ticker="AAPL",
            trade_value=1000,
            current_position_value=0,
            portfolio_value=0,  # Zero portfolio
            settings=settings,
        )
        
        # Should not crash
        assert result.valid is True
    
    def test_negative_returns_var(self):
        """VaR handles array with all negative returns."""
        from risk.var_calculator import calculate_volatility
        
        returns = np.array([-0.01, -0.02, -0.01, -0.015, -0.02])
        daily_vol, annual_vol = calculate_volatility(returns)
        
        # Should still calculate valid volatility
        assert daily_vol > 0
        assert annual_vol > 0
    
    def test_extreme_vix_values(self):
        """Dynamic thresholds handle extreme VIX values."""
        from risk.dynamic_thresholds import calculate_adjusted_sell_threshold
        
        # Very high VIX
        threshold = calculate_adjusted_sell_threshold(50.0, 80.0)
        assert threshold > 50.0
        assert threshold < 100.0  # Should be reasonable
        
        # Zero VIX
        threshold = calculate_adjusted_sell_threshold(50.0, 0.0)
        assert threshold == 50.0  # No adjustment


# ==================== Model Serialization Tests ====================

class TestModelSerialization:
    """Tests for model serialization/deserialization."""
    
    def test_vix_data_round_trip(self):
        """VIXData survives JSON round trip."""
        import json
        from risk.vix_service import VIXData
        
        original = VIXData(
            value=25.5,
            previous_close=24.0,
            change=1.5,
            change_pct=6.25,
            updated_at=datetime.now(timezone.utc),
            regime="high",
        )
        
        # Serialize and deserialize
        json_str = json.dumps(original.to_dict())
        data = json.loads(json_str)
        
        assert data["vix"] == 25.5
        assert data["regime"] == "high"
    
    def test_validation_result_json(self):
        """TradeValidationResult serializes to valid JSON."""
        import json
        from risk.position_limits import TradeValidationResult, PositionWarning, WarningLevel
        
        result = TradeValidationResult(
            valid=True,
            warnings=[
                PositionWarning("test", WarningLevel.MEDIUM, "msg", True, 0.18, 0.15)
            ],
            risk_metrics={"test": 123},
        )
        
        # Should not throw
        json_str = json.dumps(result.to_dict())
        assert json_str is not None
        
        # Should round-trip
        parsed = json.loads(json_str)
        assert parsed["valid"] is True
        assert len(parsed["warnings"]) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
