"""
Risk Management Models

PM Requirement: ALL defaults = OFF (minimum restriction)
User must explicitly opt-in to any protection.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any
import json


@dataclass
class StopConfig:
    """Hard stop-loss configuration.
    
    Default: OFF with -8% threshold.
    Range: -5% to -20%
    """
    enabled: bool = False  # PM: Default OFF
    threshold_pct: float = -0.08  # -8%

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "threshold_pct": self.threshold_pct,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StopConfig":
        return cls(
            enabled=data.get("enabled", False),
            threshold_pct=data.get("threshold_pct", -0.08),
        )

    def validate(self) -> None:
        """Validate configuration values."""
        if not (-0.20 <= self.threshold_pct <= -0.05):
            raise ValueError(f"Hard stop threshold must be between -5% and -20%, got {self.threshold_pct*100:.1f}%")


@dataclass
class TrailingStopConfig:
    """Trailing stop-loss configuration.
    
    Default: OFF with -10% distance.
    Range: -5% to -25%
    """
    enabled: bool = False  # PM: Default OFF
    distance_pct: float = -0.10  # -10%

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "distance_pct": self.distance_pct,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TrailingStopConfig":
        return cls(
            enabled=data.get("enabled", False),
            distance_pct=data.get("distance_pct", -0.10),
        )

    def validate(self) -> None:
        """Validate configuration values."""
        if not (-0.25 <= self.distance_pct <= -0.05):
            raise ValueError(f"Trailing stop distance must be between -5% and -25%, got {self.distance_pct*100:.1f}%")


@dataclass
class VixAdjustmentConfig:
    """VIX-based threshold adjustment.
    
    Default: OFF
    When enabled, adjusts SELL threshold based on VIX level.
    Formula: 50 + max(0, (VIX - 15) × 0.5)
    """
    enabled: bool = False  # PM: Default OFF

    def to_dict(self) -> Dict[str, Any]:
        return {"enabled": self.enabled}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VixAdjustmentConfig":
        return cls(enabled=data.get("enabled", False))


@dataclass
class PositionLimitConfig:
    """Position size limits.
    
    Default: OFF with 15% max.
    Range: 5% to 30%
    """
    enabled: bool = False  # PM: Default OFF
    max_pct: float = 0.15  # 15%

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "max_pct": self.max_pct,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PositionLimitConfig":
        return cls(
            enabled=data.get("enabled", False),
            max_pct=data.get("max_pct", 0.15),
        )

    def validate(self) -> None:
        """Validate configuration values."""
        if not (0.05 <= self.max_pct <= 0.30):
            raise ValueError(f"Position limit must be between 5% and 30%, got {self.max_pct*100:.1f}%")


@dataclass
class UserRiskSettings:
    """
    User's risk management preferences.
    
    PM Requirement: ALL defaults = OFF (minimum restriction)
    User must explicitly opt-in to any protection.
    
    Stored as JSON in the user's settings_json column or in a dedicated table.
    """
    user_id: str
    hard_stop: StopConfig = field(default_factory=StopConfig)
    trailing_stop: TrailingStopConfig = field(default_factory=TrailingStopConfig)
    vix_adjustment: VixAdjustmentConfig = field(default_factory=VixAdjustmentConfig)
    position_limit: PositionLimitConfig = field(default_factory=PositionLimitConfig)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict for API response."""
        return {
            "user_id": self.user_id,
            "hard_stop": self.hard_stop.to_dict(),
            "trailing_stop": self.trailing_stop.to_dict(),
            "vix_adjustment": self.vix_adjustment.to_dict(),
            "position_limit": self.position_limit.to_dict(),
        }

    def to_json(self) -> str:
        """Serialize to JSON string for database storage."""
        # Exclude user_id from storage (it's the key)
        data = {
            "hard_stop": self.hard_stop.to_dict(),
            "trailing_stop": self.trailing_stop.to_dict(),
            "vix_adjustment": self.vix_adjustment.to_dict(),
            "position_limit": self.position_limit.to_dict(),
        }
        return json.dumps(data)

    @classmethod
    def from_dict(cls, user_id: str, data: Dict[str, Any]) -> "UserRiskSettings":
        """Create from dictionary (e.g., API request or database)."""
        return cls(
            user_id=user_id,
            hard_stop=StopConfig.from_dict(data.get("hard_stop", {})),
            trailing_stop=TrailingStopConfig.from_dict(data.get("trailing_stop", {})),
            vix_adjustment=VixAdjustmentConfig.from_dict(data.get("vix_adjustment", {})),
            position_limit=PositionLimitConfig.from_dict(data.get("position_limit", {})),
        )

    @classmethod
    def from_json(cls, user_id: str, json_str: Optional[str]) -> "UserRiskSettings":
        """Create from JSON string (database storage)."""
        if not json_str:
            return cls(user_id=user_id)  # All defaults
        data = json.loads(json_str)
        return cls.from_dict(user_id, data)

    @classmethod
    def default(cls, user_id: str) -> "UserRiskSettings":
        """Create default settings (all OFF)."""
        return cls(user_id=user_id)

    def validate(self) -> None:
        """Validate all settings. Raises ValueError if invalid."""
        if self.hard_stop.enabled:
            self.hard_stop.validate()
        if self.trailing_stop.enabled:
            self.trailing_stop.validate()
        if self.position_limit.enabled:
            self.position_limit.validate()

    def has_any_enabled(self) -> bool:
        """Check if any risk protection is enabled."""
        return (
            self.hard_stop.enabled or
            self.trailing_stop.enabled or
            self.vix_adjustment.enabled or
            self.position_limit.enabled
        )
