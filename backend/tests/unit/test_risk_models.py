"""
Unit tests for Risk Module Models

REC-216: Risk Settings API
Tests for UserRiskSettings, StopConfig, TrailingStopConfig, etc.
"""

import pytest
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from risk.models import (
    UserRiskSettings,
    StopConfig,
    TrailingStopConfig,
    VixAdjustmentConfig,
    PositionLimitConfig,
)


class TestStopConfig:
    """Tests for StopConfig (hard stop-loss)."""
    
    def test_defaults(self):
        """Default values should be OFF with -8% threshold."""
        config = StopConfig()
        assert config.enabled is False
        assert config.threshold_pct == -0.08
    
    def test_to_dict(self):
        """Should serialize to dict correctly."""
        config = StopConfig(enabled=True, threshold_pct=-0.10)
        result = config.to_dict()
        assert result == {"enabled": True, "threshold_pct": -0.10}
    
    def test_from_dict(self):
        """Should deserialize from dict correctly."""
        data = {"enabled": True, "threshold_pct": -0.15}
        config = StopConfig.from_dict(data)
        assert config.enabled is True
        assert config.threshold_pct == -0.15
    
    def test_from_dict_missing_fields(self):
        """Should use defaults for missing fields."""
        config = StopConfig.from_dict({})
        assert config.enabled is False
        assert config.threshold_pct == -0.08
    
    def test_validate_valid_range(self):
        """Valid thresholds should pass validation."""
        for pct in [-0.05, -0.08, -0.10, -0.15, -0.20]:
            config = StopConfig(enabled=True, threshold_pct=pct)
            config.validate()  # Should not raise
    
    def test_validate_invalid_range(self):
        """Invalid thresholds should fail validation."""
        for pct in [-0.01, -0.04, -0.25, -0.50]:
            config = StopConfig(enabled=True, threshold_pct=pct)
            with pytest.raises(ValueError):
                config.validate()


class TestTrailingStopConfig:
    """Tests for TrailingStopConfig."""
    
    def test_defaults(self):
        """Default values should be OFF with -10% distance."""
        config = TrailingStopConfig()
        assert config.enabled is False
        assert config.distance_pct == -0.10
    
    def test_validate_valid_range(self):
        """Valid distances should pass validation."""
        for pct in [-0.05, -0.10, -0.15, -0.20, -0.25]:
            config = TrailingStopConfig(enabled=True, distance_pct=pct)
            config.validate()  # Should not raise
    
    def test_validate_invalid_range(self):
        """Invalid distances should fail validation."""
        for pct in [-0.01, -0.04, -0.30, -0.50]:
            config = TrailingStopConfig(enabled=True, distance_pct=pct)
            with pytest.raises(ValueError):
                config.validate()


class TestPositionLimitConfig:
    """Tests for PositionLimitConfig."""
    
    def test_defaults(self):
        """Default values should be OFF with 15% max."""
        config = PositionLimitConfig()
        assert config.enabled is False
        assert config.max_pct == 0.15
    
    def test_validate_valid_range(self):
        """Valid limits should pass validation."""
        for pct in [0.05, 0.10, 0.15, 0.20, 0.30]:
            config = PositionLimitConfig(enabled=True, max_pct=pct)
            config.validate()  # Should not raise
    
    def test_validate_invalid_range(self):
        """Invalid limits should fail validation."""
        for pct in [0.01, 0.04, 0.35, 0.50]:
            config = PositionLimitConfig(enabled=True, max_pct=pct)
            with pytest.raises(ValueError):
                config.validate()


class TestUserRiskSettings:
    """Tests for UserRiskSettings."""
    
    def test_defaults(self):
        """Default settings should have all protections OFF."""
        settings = UserRiskSettings.default("user123")
        
        assert settings.user_id == "user123"
        assert settings.hard_stop.enabled is False
        assert settings.trailing_stop.enabled is False
        assert settings.vix_adjustment.enabled is False
        assert settings.position_limit.enabled is False
    
    def test_to_dict(self):
        """Should serialize to dict correctly."""
        settings = UserRiskSettings.default("user123")
        settings.hard_stop.enabled = True
        
        result = settings.to_dict()
        
        assert result["user_id"] == "user123"
        assert result["hard_stop"]["enabled"] is True
        assert result["trailing_stop"]["enabled"] is False
    
    def test_to_json(self):
        """Should serialize to JSON string correctly."""
        settings = UserRiskSettings.default("user123")
        settings.hard_stop.enabled = True
        settings.hard_stop.threshold_pct = -0.10
        
        json_str = settings.to_json()
        data = json.loads(json_str)
        
        # user_id should NOT be in the JSON (it's the key)
        assert "user_id" not in data
        assert data["hard_stop"]["enabled"] is True
        assert data["hard_stop"]["threshold_pct"] == -0.10
    
    def test_from_json(self):
        """Should deserialize from JSON string correctly."""
        json_str = '{"hard_stop": {"enabled": true, "threshold_pct": -0.12}}'
        settings = UserRiskSettings.from_json("user456", json_str)
        
        assert settings.user_id == "user456"
        assert settings.hard_stop.enabled is True
        assert settings.hard_stop.threshold_pct == -0.12
        assert settings.trailing_stop.enabled is False  # Default
    
    def test_from_json_none(self):
        """Should return defaults when JSON is None."""
        settings = UserRiskSettings.from_json("user789", None)
        
        assert settings.user_id == "user789"
        assert settings.hard_stop.enabled is False
    
    def test_from_dict(self):
        """Should create from dict correctly."""
        data = {
            "hard_stop": {"enabled": True, "threshold_pct": -0.08},
            "trailing_stop": {"enabled": True, "distance_pct": -0.15},
            "vix_adjustment": {"enabled": False},
            "position_limit": {"enabled": True, "max_pct": 0.20},
        }
        settings = UserRiskSettings.from_dict("user001", data)
        
        assert settings.hard_stop.enabled is True
        assert settings.trailing_stop.enabled is True
        assert settings.trailing_stop.distance_pct == -0.15
        assert settings.vix_adjustment.enabled is False
        assert settings.position_limit.enabled is True
        assert settings.position_limit.max_pct == 0.20
    
    def test_has_any_enabled_none(self):
        """Should return False when all protections OFF."""
        settings = UserRiskSettings.default("user")
        assert settings.has_any_enabled() is False
    
    def test_has_any_enabled_one(self):
        """Should return True when any protection ON."""
        settings = UserRiskSettings.default("user")
        settings.hard_stop.enabled = True
        assert settings.has_any_enabled() is True
    
    def test_validate_all_enabled(self):
        """Should validate all enabled settings."""
        settings = UserRiskSettings.default("user")
        settings.hard_stop.enabled = True
        settings.hard_stop.threshold_pct = -0.10
        settings.trailing_stop.enabled = True
        settings.trailing_stop.distance_pct = -0.15
        settings.position_limit.enabled = True
        settings.position_limit.max_pct = 0.20
        
        settings.validate()  # Should not raise
    
    def test_validate_invalid_hard_stop(self):
        """Should fail validation if hard stop threshold invalid."""
        settings = UserRiskSettings.default("user")
        settings.hard_stop.enabled = True
        settings.hard_stop.threshold_pct = -0.50  # Invalid
        
        with pytest.raises(ValueError):
            settings.validate()
