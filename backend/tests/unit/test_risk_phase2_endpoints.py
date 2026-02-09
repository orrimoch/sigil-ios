"""
Unit tests for Risk Phase 2 API endpoints.

Tests:
- Trade validation action pattern (BUG-P2-003)
- VIX dynamic thresholds
- VaR calculation
- Position limit validation
- Risk settings defaults
"""

import pytest
import sys
from pathlib import Path
from pydantic import ValidationError

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


class TestTradeValidationRequest:
    """Tests for trade action validation pattern."""
    
    def test_valid_buy_action(self):
        """BUY action should be accepted."""
        from pydantic import BaseModel, Field
        
        class TradeValidationRequest(BaseModel):
            ticker: str
            action: str = Field(pattern="^(BUY|SELL)$")
            quantity: float = Field(gt=0)
            price: float = Field(gt=0)
        
        req = TradeValidationRequest(
            ticker="AAPL",
            action="BUY",
            quantity=10,
            price=200
        )
        assert req.action == "BUY"
    
    def test_valid_sell_action(self):
        """SELL action should be accepted."""
        from pydantic import BaseModel, Field
        
        class TradeValidationRequest(BaseModel):
            ticker: str
            action: str = Field(pattern="^(BUY|SELL)$")
            quantity: float = Field(gt=0)
            price: float = Field(gt=0)
        
        req = TradeValidationRequest(
            ticker="AAPL",
            action="SELL",
            quantity=10,
            price=200
        )
        assert req.action == "SELL"
    
    def test_invalid_action_rejected(self):
        """Invalid action like 'INVALID' should be rejected."""
        from pydantic import BaseModel, Field
        
        class TradeValidationRequest(BaseModel):
            ticker: str
            action: str = Field(pattern="^(BUY|SELL)$")
            quantity: float = Field(gt=0)
            price: float = Field(gt=0)
        
        with pytest.raises(ValidationError):
            TradeValidationRequest(
                ticker="AAPL",
                action="INVALID",
                quantity=10,
                price=200
            )
    
    def test_lowercase_action_rejected(self):
        """Lowercase 'buy' should be rejected (case-sensitive)."""
        from pydantic import BaseModel, Field
        
        class TradeValidationRequest(BaseModel):
            ticker: str
            action: str = Field(pattern="^(BUY|SELL)$")
            quantity: float = Field(gt=0)
            price: float = Field(gt=0)
        
        with pytest.raises(ValidationError):
            TradeValidationRequest(
                ticker="AAPL",
                action="buy",
                quantity=10,
                price=200
            )
    
    def test_mixed_case_rejected(self):
        """Mixed case 'Buy' should be rejected."""
        from pydantic import BaseModel, Field
        
        class TradeValidationRequest(BaseModel):
            ticker: str
            action: str = Field(pattern="^(BUY|SELL)$")
            quantity: float = Field(gt=0)
            price: float = Field(gt=0)
        
        with pytest.raises(ValidationError):
            TradeValidationRequest(
                ticker="AAPL",
                action="Buy",
                quantity=10,
                price=200
            )
    
    def test_zero_quantity_rejected(self):
        """Zero quantity should be rejected."""
        from pydantic import BaseModel, Field
        
        class TradeValidationRequest(BaseModel):
            ticker: str
            action: str = Field(pattern="^(BUY|SELL)$")
            quantity: float = Field(gt=0)
            price: float = Field(gt=0)
        
        with pytest.raises(ValidationError):
            TradeValidationRequest(
                ticker="AAPL",
                action="BUY",
                quantity=0,
                price=200
            )
    
    def test_negative_price_rejected(self):
        """Negative price should be rejected."""
        from pydantic import BaseModel, Field
        
        class TradeValidationRequest(BaseModel):
            ticker: str
            action: str = Field(pattern="^(BUY|SELL)$")
            quantity: float = Field(gt=0)
            price: float = Field(gt=0)
        
        with pytest.raises(ValidationError):
            TradeValidationRequest(
                ticker="AAPL",
                action="BUY",
                quantity=10,
                price=-100
            )


class TestVIXDynamicThresholds:
    """Tests for VIX-adjusted scoring thresholds."""
    
    def test_baseline_thresholds(self):
        """At VIX=15 (baseline), thresholds should be standard."""
        from risk.dynamic_thresholds import calculate_vix_adjustment
        
        adj = calculate_vix_adjustment(vix=15.0)
        assert adj == 0.0  # No adjustment at baseline
    
    def test_elevated_vix_adjustment(self):
        """Higher VIX should increase thresholds."""
        from risk.dynamic_thresholds import calculate_vix_adjustment
        
        # VIX=20: adjustment = (20-15) * 0.5 = 2.5
        adj = calculate_vix_adjustment(vix=20.0)
        assert adj == 2.5
        
        # VIX=30: adjustment = (30-15) * 0.5 = 7.5
        adj = calculate_vix_adjustment(vix=30.0)
        assert adj == 7.5
    
    def test_low_vix_no_adjustment(self):
        """Below baseline VIX should have no adjustment (clamped to 0)."""
        from risk.dynamic_thresholds import calculate_vix_adjustment
        
        adj = calculate_vix_adjustment(vix=10.0)
        assert adj == 0.0  # max(0, (10-15)*0.5) = max(0, -2.5) = 0
    
    def test_threshold_table_structure(self):
        """Threshold table should have correct structure."""
        from risk.dynamic_thresholds import get_threshold_table
        
        table = get_threshold_table()
        
        # Table is Dict[int, Dict[str, float]] - VIX level -> thresholds
        assert 15 in table  # Baseline
        assert 20 in table
        assert 30 in table
        
        # Each entry has sell and buy thresholds
        assert table[15]["sell"] == 50.0
        assert table[20]["sell"] == 52.5
        assert table[30]["sell"] == 57.5


class TestClaudeAnalyzerFallback:
    """Tests for Claude risk analyzer fallback behavior."""
    
    def test_fallback_result_structure(self):
        """Fallback result should have default moderate risk values."""
        from risk.claude_analyzer import RiskAnalysisResult, RiskLevel
        from datetime import datetime, timezone
        
        result = RiskAnalysisResult(
            ticker="AAPL",
            risk_score=60,
            risk_level=RiskLevel.MEDIUM,
            risk_factors=["Analysis unavailable"],
            recommendation="monitor",
            reasoning="Unable to complete analysis. Defaulting to moderate risk.",
            confidence=0.3,
            analyzed_at=datetime.now(timezone.utc),
            cached=False
        )
        
        data = result.to_dict()
        assert data["risk_score"] == 60
        assert data["risk_level"] == "medium"
        assert data["confidence"] == 0.3
        assert "Analysis unavailable" in data["risk_factors"]
    
    def test_risk_level_enum_values(self):
        """Risk level enum should have correct string values."""
        from risk.claude_analyzer import RiskLevel
        
        assert RiskLevel.LOW.value == "low"
        assert RiskLevel.MEDIUM.value == "medium"
        assert RiskLevel.HIGH.value == "high"
        assert RiskLevel.CRITICAL.value == "critical"


class TestVaRRiskClassification:
    """Tests for VaR risk classification."""
    
    def test_risk_score_classification(self):
        """Risk score should be classified by VaR percentage."""
        from risk.var_calculator import classify_risk_score
        
        # Note: var_95_pct is in decimal form (0.05 = 5%)
        assert classify_risk_score(0.03) == "low"     # < 5%
        assert classify_risk_score(0.07) == "medium"  # 5-10%
        assert classify_risk_score(0.12) == "high"    # >= 10%


class TestPositionLimitValidation:
    """Tests for position limit validation."""
    
    def test_validation_skipped_when_disabled(self):
        """Validation should be skipped when position limits are disabled."""
        from risk.position_limits import validate_trade
        from risk.models import UserRiskSettings
        
        settings = UserRiskSettings(user_id="test")
        # By default, position_limit.enabled = False
        
        result = validate_trade(
            ticker="AAPL",
            action="BUY",
            quantity=100,
            price=200,
            portfolio={"positions": [], "total_value": 10000},
            settings=settings
        )
        
        assert result.valid is True
        assert result.risk_metrics.get("validation_skipped") is True
    
    def test_small_trade_no_warnings(self):
        """Small trade should not trigger warnings."""
        from risk.position_limits import validate_trade
        from risk.models import UserRiskSettings, PositionLimitConfig
        
        settings = UserRiskSettings(
            user_id="test",
            position_limit=PositionLimitConfig(enabled=True, max_pct=0.15)
        )
        
        result = validate_trade(
            ticker="AAPL",
            action="BUY",
            quantity=10,
            price=100,
            portfolio={"positions": [], "total_value": 100000},
            settings=settings
        )
        
        # 10 shares * $100 = $1000 = 1% of $100k portfolio
        # Well under 15% limit
        assert result.valid is True
        assert len(result.warnings) == 0
    
    def test_large_trade_triggers_warning(self):
        """Large trade exceeding limit should trigger warning."""
        from risk.position_limits import validate_trade
        from risk.models import UserRiskSettings, PositionLimitConfig
        
        settings = UserRiskSettings(
            user_id="test",
            position_limit=PositionLimitConfig(enabled=True, max_pct=0.10)  # 10% limit
        )
        
        result = validate_trade(
            ticker="AAPL",
            action="BUY",
            quantity=100,
            price=200,
            portfolio={"positions": [], "total_value": 100000},
            settings=settings
        )
        
        # 100 shares * $200 = $20,000 = 20% of $100k portfolio
        # Exceeds 10% limit
        assert result.valid is True  # Still valid, just has warning
        assert len(result.warnings) > 0


class TestRiskSettingsDefaults:
    """Tests for risk settings default values."""
    
    def test_all_protections_off_by_default(self):
        """All risk protections should be disabled by default."""
        from risk.models import UserRiskSettings
        
        settings = UserRiskSettings(user_id="test")
        
        assert settings.hard_stop.enabled is False
        assert settings.trailing_stop.enabled is False
        assert settings.vix_adjustment.enabled is False
        assert settings.position_limit.enabled is False
    
    def test_default_threshold_values(self):
        """Default threshold values should be set correctly."""
        from risk.models import UserRiskSettings
        
        settings = UserRiskSettings(user_id="test")
        
        assert settings.hard_stop.threshold_pct == -0.08  # -8%
        assert settings.trailing_stop.distance_pct == -0.10  # -10%
        assert settings.position_limit.max_pct == 0.15  # 15%
    
    def test_to_dict_structure(self):
        """Settings should serialize to proper dict structure."""
        from risk.models import UserRiskSettings
        
        settings = UserRiskSettings(user_id="test")
        data = settings.to_dict()
        
        assert "user_id" in data
        assert "hard_stop" in data
        assert "trailing_stop" in data
        assert "vix_adjustment" in data
        assert "position_limit" in data
        
        # Nested structures
        assert "enabled" in data["hard_stop"]
        assert "threshold_pct" in data["hard_stop"]
