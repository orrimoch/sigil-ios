"""
Tests for F4.4 Alerts Module
"""

import pytest
from pathlib import Path
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from alerts.alerts import Alert, AlertType, AlertManager


class TestAlert:
    """Tests for Alert class."""
    
    def test_alert_creation(self):
        """Test basic alert creation."""
        alert = Alert(
            id="test123",
            type=AlertType.SCORE_CHANGE,
            ticker="AAPL",
            title="Score increased +15 pts",
            subtitle="Now rated BUY (85)",
        )
        
        assert alert.id == "test123"
        assert alert.type == AlertType.SCORE_CHANGE
        assert alert.ticker == "AAPL"
        assert alert.read is False
    
    def test_alert_serialization(self):
        """Test alert to/from dict."""
        alert = Alert(
            id="test123",
            type=AlertType.SIGNAL_CHANGE,
            ticker="MSFT",
            title="Signal changed",
            subtitle="HOLD → BUY",
        )
        
        data = alert.to_dict()
        restored = Alert.from_dict(data)
        
        assert restored.id == alert.id
        assert restored.type == AlertType.SIGNAL_CHANGE
        assert restored.ticker == "MSFT"


class TestAlertManager:
    """Tests for AlertManager class.
    
    Note: We mock _save() and _load() to prevent tests from polluting production data.
    """
    """Tests for AlertManager class."""
    
    @pytest.fixture
    def manager(self):
        """Create fresh manager (in memory, no file I/O)."""
        with patch.object(AlertManager, '_save'), patch.object(AlertManager, '_load'):
            m = AlertManager()
            m.alerts = []  # Start with empty alerts
            yield m
    
    def test_add_alert(self, manager):
        """Test adding an alert."""
        alert = manager.add_alert(
            AlertType.SCORE_CHANGE,
            "AAPL",
            "Score increased",
            "Now rated BUY (85)",
        )
        
        assert len(manager.alerts) == 1
        assert alert.ticker == "AAPL"
    
    def test_alerts_newest_first(self, manager):
        """Test alerts are ordered newest first."""
        manager.add_alert(AlertType.SCORE_CHANGE, "AAPL", "First", "")
        manager.add_alert(AlertType.SCORE_CHANGE, "MSFT", "Second", "")
        
        assert manager.alerts[0].ticker == "MSFT"
        assert manager.alerts[1].ticker == "AAPL"
    
    def test_check_score_changes(self, manager):
        """Test score change detection."""
        old_scores = {
            "AAPL": {"total_score": 60, "signal": "HOLD"},
            "MSFT": {"total_score": 50, "signal": "HOLD"},
        }
        new_scores = {
            "AAPL": {"total_score": 75, "signal": "BUY"},  # +15
            "MSFT": {"total_score": 52, "signal": "HOLD"},  # +2 (no alert)
        }
        
        alerts = manager.check_score_changes(old_scores, new_scores, threshold=10)
        
        assert len(alerts) == 1
        assert alerts[0].ticker == "AAPL"
    
    def test_check_signal_changes(self, manager):
        """Test signal change detection."""
        old_scores = {
            "AAPL": {"signal": "HOLD"},
            "MSFT": {"signal": "SELL"},
        }
        new_scores = {
            "AAPL": {"signal": "BUY"},  # Changed
            "MSFT": {"signal": "SELL"},  # Same
        }
        
        alerts = manager.check_signal_changes(old_scores, new_scores)
        
        assert len(alerts) == 1
        assert alerts[0].ticker == "AAPL"
        assert "HOLD → BUY" in alerts[0].subtitle
    
    def test_get_alerts_filtered(self, manager):
        """Test getting filtered alerts."""
        manager.add_alert(AlertType.SCORE_CHANGE, "AAPL", "Title", "")
        manager.add_alert(AlertType.SIGNAL_CHANGE, "MSFT", "Title", "")
        manager.add_alert(AlertType.SCORE_CHANGE, "AAPL", "Title2", "")
        
        # Filter by ticker
        aapl_alerts = manager.get_alerts(ticker="AAPL")
        assert len(aapl_alerts) == 2
        
        # Filter by type
        score_alerts = manager.get_alerts(alert_type=AlertType.SCORE_CHANGE)
        assert len(score_alerts) == 2
    
    def test_mark_read(self, manager):
        """Test marking alert as read."""
        alert = manager.add_alert(AlertType.SCORE_CHANGE, "AAPL", "Title", "")
        
        assert alert.read is False
        
        manager.mark_read(alert.id)
        
        assert manager.alerts[0].read is True
    
    def test_add_earnings_alert(self, manager):
        """Test earnings alert."""
        alert = manager.add_earnings_alert("AAPL", 2.18, 2.10)
        
        assert alert is not None
        assert alert.type == AlertType.EARNINGS
        assert "beat" in alert.title
    
    def test_max_alerts(self, manager):
        """Test max alerts limit."""
        manager.MAX_ALERTS = 5
        
        for i in range(10):
            manager.add_alert(AlertType.SCORE_CHANGE, f"TICK{i}", "Title", "")
        
        assert len(manager.alerts) == 5


# ========== Run Tests ==========

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
