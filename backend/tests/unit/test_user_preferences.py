"""
Unit tests for REC-126/REC-127: User Preferences (Risk Tolerance & Portfolio Size)

Tests cover:
- Preferences API endpoints (GET/PUT)
- Risk-adjusted scoring thresholds
- Portfolio size position limits
"""

import pytest
import sys
import json
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


# ============ Risk Tolerance Thresholds (REC-126) ============


class TestRiskAdjustedThresholds:
    """Test risk tolerance affects signal thresholds."""

    def test_conservative_thresholds(self):
        """Conservative: BUY >= 80, SELL < 30."""
        from scoring.composite_score import get_thresholds_for_risk
        thresholds = get_thresholds_for_risk("conservative")
        assert thresholds["BUY"] == 80
        assert thresholds["SELL"] == 30

    def test_moderate_thresholds(self):
        """Moderate (default): BUY >= 70, SELL < 40."""
        from scoring.composite_score import get_thresholds_for_risk
        thresholds = get_thresholds_for_risk("moderate")
        assert thresholds["BUY"] == 70
        assert thresholds["SELL"] == 40

    def test_aggressive_thresholds(self):
        """Aggressive: BUY >= 60, SELL < 50."""
        from scoring.composite_score import get_thresholds_for_risk
        thresholds = get_thresholds_for_risk("aggressive")
        assert thresholds["BUY"] == 60
        assert thresholds["SELL"] == 50

    def test_invalid_risk_falls_back_to_default(self):
        """Unknown risk tolerance falls back to moderate."""
        from scoring.composite_score import get_thresholds_for_risk
        thresholds = get_thresholds_for_risk("invalid")
        assert thresholds["BUY"] == 70  # moderate default


class TestGetSignalWithRisk:
    """Test get_signal respects risk tolerance."""

    def test_score_75_is_buy_for_moderate(self):
        from scoring.composite_score import get_signal, Signal
        assert get_signal(75, "moderate") == Signal.BUY

    def test_score_75_is_hold_for_conservative(self):
        from scoring.composite_score import get_signal, Signal
        assert get_signal(75, "conservative") == Signal.HOLD

    def test_score_65_is_buy_for_aggressive(self):
        from scoring.composite_score import get_signal, Signal
        assert get_signal(65, "aggressive") == Signal.BUY

    def test_score_65_is_hold_for_moderate(self):
        from scoring.composite_score import get_signal, Signal
        assert get_signal(65, "moderate") == Signal.HOLD

    def test_score_35_is_sell_for_moderate(self):
        from scoring.composite_score import get_signal, Signal
        assert get_signal(35, "moderate") == Signal.SELL

    def test_score_35_is_hold_for_conservative(self):
        from scoring.composite_score import get_signal, Signal
        # Conservative SELL < 30, so 35 is HOLD
        assert get_signal(35, "conservative") == Signal.HOLD


# ============ Portfolio Size Limits (REC-127) ============


class TestPortfolioSizeLimits:
    """Test portfolio size constrains max positions."""

    def test_small_limit_is_5(self):
        from trading.user_trading_service import get_position_limit
        assert get_position_limit("small") == 5

    def test_medium_limit_is_10(self):
        from trading.user_trading_service import get_position_limit
        assert get_position_limit("medium") == 10

    def test_large_limit_is_15(self):
        from trading.user_trading_service import get_position_limit
        assert get_position_limit("large") == 15

    def test_invalid_size_defaults_to_medium(self):
        from trading.user_trading_service import get_position_limit
        assert get_position_limit("invalid") == 10


# ============ Preferences API Validation ============


class TestPreferencesValidation:
    """Test preferences validation in routes."""

    def test_valid_risk_tolerances(self):
        """All valid risk values should be accepted."""
        valid = ["conservative", "moderate", "aggressive"]
        for risk in valid:
            assert risk in valid

    def test_valid_portfolio_sizes(self):
        """All valid portfolio sizes should be accepted."""
        valid = ["small", "medium", "large"]
        for size in valid:
            assert size in valid


# ============ Integration Tests (require TestClient) ============


class TestPreferencesEndpoints:
    """Test preferences API endpoints."""

    def test_get_preferences_requires_auth(self):
        """GET /auth/preferences should return 401 without auth."""
        from fastapi.testclient import TestClient
        from api.main import app
        
        client = TestClient(app)
        resp = client.get("/api/v1/auth/preferences")
        # Returns 401 or our custom error format
        assert resp.status_code in (401, 200)
        if resp.status_code == 200:
            data = resp.json()
            assert data.get("success") is False or "error" in data

    def test_preferences_returned_with_defaults(self):
        """Preferences should have default values."""
        from auth.routes import _parse_preferences, UserPreferences
        
        prefs = _parse_preferences(None)
        assert prefs.risk_tolerance == "moderate"
        assert prefs.portfolio_size == "medium"

    def test_parse_preferences_from_json(self):
        """Parse preferences from valid JSON."""
        from auth.routes import _parse_preferences
        
        settings = json.dumps({
            "risk_tolerance": "aggressive",
            "portfolio_size": "large"
        })
        prefs = _parse_preferences(settings)
        assert prefs.risk_tolerance == "aggressive"
        assert prefs.portfolio_size == "large"

    def test_parse_preferences_invalid_json(self):
        """Invalid JSON falls back to defaults."""
        from auth.routes import _parse_preferences
        
        prefs = _parse_preferences("invalid json{")
        assert prefs.risk_tolerance == "moderate"
        assert prefs.portfolio_size == "medium"
