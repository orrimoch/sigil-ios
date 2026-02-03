"""
F4.4 Alerts System

Generates alerts for:
- Score changes > 10 points
- Signal changes (BUY/HOLD/SELL transitions)
- Earnings surprises
"""

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Optional, List, Dict
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

# Data directory
DATA_DIR = Path(__file__).parent.parent.parent / "data"
ALERTS_FILE = DATA_DIR / "alerts.json"


class AlertType(str, Enum):
    """Types of alerts."""
    SCORE_CHANGE = "score_change"
    SIGNAL_CHANGE = "signal_change"
    EARNINGS = "earnings"
    NEWS = "news"


@dataclass
class Alert:
    """An alert notification."""
    id: str
    type: AlertType
    ticker: str
    title: str
    subtitle: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    read: bool = False
    
    def to_dict(self) -> dict:
        data = asdict(self)
        data["type"] = self.type.value
        return data
    
    @classmethod
    def from_dict(cls, data: dict) -> "Alert":
        data = data.copy()
        data["type"] = AlertType(data["type"])
        return cls(**data)


class AlertManager:
    """
    Manages alert generation and storage.
    
    Alerts are generated when:
    - A stock's score changes by > 10 points
    - A stock's signal changes (BUY <-> HOLD <-> SELL)
    - Earnings results are released (future)
    """
    
    MAX_ALERTS = 100  # Keep last N alerts
    
    def __init__(self):
        self.alerts: List[Alert] = []
        self._load()
    
    def _load(self):
        """Load alerts from file."""
        if ALERTS_FILE.exists():
            try:
                with open(ALERTS_FILE) as f:
                    data = json.load(f)
                self.alerts = [Alert.from_dict(a) for a in data.get("alerts", [])]
            except Exception as e:
                print(f"Failed to load alerts: {e}")
                self.alerts = []
    
    def _save(self):
        """Save alerts to file."""
        ALERTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "alerts": [a.to_dict() for a in self.alerts],
            "updated_at": datetime.now().isoformat(),
        }
        with open(ALERTS_FILE, "w") as f:
            json.dump(data, f, indent=2)
    
    def add_alert(
        self,
        alert_type: AlertType,
        ticker: str,
        title: str,
        subtitle: str,
    ) -> Alert:
        """Add a new alert."""
        alert = Alert(
            id=str(uuid.uuid4())[:8],
            type=alert_type,
            ticker=ticker,
            title=title,
            subtitle=subtitle,
        )
        
        self.alerts.insert(0, alert)  # Newest first
        
        # Trim to max
        self.alerts = self.alerts[:self.MAX_ALERTS]
        
        self._save()
        return alert
    
    def check_score_changes(
        self,
        old_scores: Dict[str, dict],
        new_scores: Dict[str, dict],
        threshold: int = 10
    ) -> List[Alert]:
        """
        Compare old and new scores, generate alerts for changes > threshold.
        """
        alerts = []
        
        for ticker, new_data in new_scores.items():
            if ticker not in old_scores:
                continue
            
            old_data = old_scores[ticker]
            old_score = old_data.get("total_score", 0)
            new_score = new_data.get("total_score", 0)
            
            change = new_score - old_score
            
            if abs(change) >= threshold:
                direction = "increased" if change > 0 else "decreased"
                alert = self.add_alert(
                    AlertType.SCORE_CHANGE,
                    ticker,
                    f"Score {direction} {abs(change):+.0f} pts",
                    f"Now rated {new_data.get('signal', 'HOLD')} ({new_score:.0f})",
                )
                alerts.append(alert)
        
        return alerts
    
    def check_signal_changes(
        self,
        old_scores: Dict[str, dict],
        new_scores: Dict[str, dict],
    ) -> List[Alert]:
        """
        Compare old and new signals, generate alerts for changes.
        """
        alerts = []
        
        for ticker, new_data in new_scores.items():
            if ticker not in old_scores:
                continue
            
            old_signal = old_scores[ticker].get("signal", "HOLD")
            new_signal = new_data.get("signal", "HOLD")
            
            if old_signal != new_signal:
                alert = self.add_alert(
                    AlertType.SIGNAL_CHANGE,
                    ticker,
                    "Signal changed",
                    f"{old_signal} → {new_signal}",
                )
                alerts.append(alert)
        
        return alerts
    
    def add_earnings_alert(
        self,
        ticker: str,
        actual_eps: float,
        expected_eps: float,
    ) -> Optional[Alert]:
        """Add an earnings alert."""
        diff = actual_eps - expected_eps
        
        if abs(diff) < 0.01:
            return None  # No significant difference
        
        if diff > 0:
            title = "Earnings beat"
            subtitle = f"EPS ${actual_eps:.2f} vs ${expected_eps:.2f} expected"
        else:
            title = "Earnings miss"
            subtitle = f"EPS ${actual_eps:.2f} vs ${expected_eps:.2f} expected"
        
        return self.add_alert(AlertType.EARNINGS, ticker, title, subtitle)
    
    def get_alerts(
        self,
        limit: int = 20,
        ticker: Optional[str] = None,
        alert_type: Optional[AlertType] = None,
        unread_only: bool = False,
    ) -> List[Alert]:
        """Get alerts with optional filters."""
        alerts = self.alerts
        
        if ticker:
            alerts = [a for a in alerts if a.ticker == ticker.upper()]
        
        if alert_type:
            alerts = [a for a in alerts if a.type == alert_type]
        
        if unread_only:
            alerts = [a for a in alerts if not a.read]
        
        return alerts[:limit]
    
    def get_recent_alerts(self, hours: int = 24) -> List[Alert]:
        """Get alerts from the last N hours."""
        cutoff = datetime.now() - timedelta(hours=hours)
        
        alerts = []
        for alert in self.alerts:
            try:
                ts = datetime.fromisoformat(alert.timestamp.replace("Z", "+00:00"))
                if ts >= cutoff:
                    alerts.append(alert)
            except:
                alerts.append(alert)
        
        return alerts
    
    def mark_read(self, alert_id: str) -> bool:
        """Mark an alert as read."""
        for alert in self.alerts:
            if alert.id == alert_id:
                alert.read = True
                self._save()
                return True
        return False
    
    def mark_all_read(self):
        """Mark all alerts as read."""
        for alert in self.alerts:
            alert.read = True
        self._save()
    
    def clear_alerts(self):
        """Clear all alerts."""
        self.alerts = []
        self._save()


# ========== Global Instance ==========

_alert_manager: Optional[AlertManager] = None


def get_alert_manager() -> AlertManager:
    """Get or create the global alert manager."""
    global _alert_manager
    
    if _alert_manager is None:
        _alert_manager = AlertManager()
    
    return _alert_manager
