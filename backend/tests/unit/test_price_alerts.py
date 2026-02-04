"""
Tests for REC-158: Server-side Price Alerts.
"""
import json
import os
import tempfile
import pytest
from unittest.mock import patch

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from ibkr import price_alerts


@pytest.fixture(autouse=True)
def temp_alerts_file(tmp_path):
    """Use a temporary file for alerts storage."""
    alerts_file = str(tmp_path / "price_alerts.json")
    with patch.object(price_alerts, 'ALERTS_FILE', alerts_file):
        yield alerts_file


class TestCreatePriceAlert:
    """Tests for create_price_alert function."""

    def test_create_above_alert(self):
        """Creating an ABOVE alert should work."""
        alert = price_alerts.create_price_alert(
            user_id="user1",
            ticker="AAPL",
            condition="ABOVE",
            target_price=200.0
        )
        assert alert.ticker == "AAPL"
        assert alert.condition == "ABOVE"
        assert alert.target_price == 200.0
        assert alert.is_active is True
        assert alert.triggered_at is None

    def test_create_below_alert(self):
        """Creating a BELOW alert should work."""
        alert = price_alerts.create_price_alert(
            user_id="user1",
            ticker="TSLA",
            condition="BELOW",
            target_price=150.0
        )
        assert alert.ticker == "TSLA"
        assert alert.condition == "BELOW"

    def test_invalid_condition(self):
        """Invalid condition should fail."""
        with pytest.raises(ValueError, match="Invalid condition"):
            price_alerts.create_price_alert(
                user_id="user1",
                ticker="AAPL",
                condition="INVALID",
                target_price=200.0
            )

    def test_ticker_uppercased(self):
        """Ticker should be uppercased."""
        alert = price_alerts.create_price_alert(
            user_id="user1",
            ticker="aapl",
            condition="ABOVE",
            target_price=200.0
        )
        assert alert.ticker == "AAPL"


class TestGetUserAlerts:
    """Tests for get_user_alerts function."""

    def test_get_alerts_empty(self):
        """No alerts returns empty list."""
        alerts = price_alerts.get_user_alerts("user1")
        assert alerts == []

    def test_get_alerts_for_user(self):
        """Get alerts returns only user's alerts."""
        price_alerts.create_price_alert("user1", "AAPL", "ABOVE", 200)
        price_alerts.create_price_alert("user2", "TSLA", "BELOW", 100)
        price_alerts.create_price_alert("user1", "GOOG", "ABOVE", 300)

        alerts = price_alerts.get_user_alerts("user1")
        assert len(alerts) == 2
        tickers = {a.ticker for a in alerts}
        assert tickers == {"AAPL", "GOOG"}


class TestDeleteAlert:
    """Tests for delete_alert function."""

    def test_delete_existing_alert(self):
        """Deleting an existing alert should work."""
        alert = price_alerts.create_price_alert("user1", "AAPL", "ABOVE", 200)
        result = price_alerts.delete_alert(alert.id, "user1")
        assert result is True

        alerts = price_alerts.get_user_alerts("user1")
        assert len(alerts) == 0

    def test_delete_nonexistent_alert(self):
        """Deleting nonexistent alert returns False."""
        result = price_alerts.delete_alert("fake_id", "user1")
        assert result is False

    def test_delete_wrong_user(self):
        """Can't delete another user's alert."""
        alert = price_alerts.create_price_alert("user1", "AAPL", "ABOVE", 200)
        result = price_alerts.delete_alert(alert.id, "user2")
        assert result is False


class TestCheckAlerts:
    """Tests for check_alerts_against_price function."""

    def test_trigger_above_alert(self):
        """ABOVE alert triggers when price goes above target."""
        price_alerts.create_price_alert("user1", "AAPL", "ABOVE", 200)
        
        triggered = price_alerts.check_alerts_against_price("AAPL", 205.0)
        assert len(triggered) == 1
        assert triggered[0].condition == "ABOVE"
        assert triggered[0].triggered_at is not None

    def test_trigger_below_alert(self):
        """BELOW alert triggers when price goes below target."""
        price_alerts.create_price_alert("user1", "AAPL", "BELOW", 150)
        
        triggered = price_alerts.check_alerts_against_price("AAPL", 145.0)
        assert len(triggered) == 1
        assert triggered[0].condition == "BELOW"

    def test_no_trigger_above(self):
        """ABOVE alert doesn't trigger when price is below."""
        price_alerts.create_price_alert("user1", "AAPL", "ABOVE", 200)
        
        triggered = price_alerts.check_alerts_against_price("AAPL", 195.0)
        assert len(triggered) == 0

    def test_no_trigger_below(self):
        """BELOW alert doesn't trigger when price is above."""
        price_alerts.create_price_alert("user1", "AAPL", "BELOW", 150)
        
        triggered = price_alerts.check_alerts_against_price("AAPL", 155.0)
        assert len(triggered) == 0

    def test_alert_only_triggers_once(self):
        """Alert should only trigger once."""
        price_alerts.create_price_alert("user1", "AAPL", "ABOVE", 200)
        
        # First check triggers
        triggered1 = price_alerts.check_alerts_against_price("AAPL", 205.0)
        assert len(triggered1) == 1
        
        # Second check doesn't trigger again
        triggered2 = price_alerts.check_alerts_against_price("AAPL", 210.0)
        assert len(triggered2) == 0

    def test_different_ticker_not_triggered(self):
        """Alert for different ticker should not trigger."""
        price_alerts.create_price_alert("user1", "AAPL", "ABOVE", 200)
        
        triggered = price_alerts.check_alerts_against_price("TSLA", 205.0)
        assert len(triggered) == 0
