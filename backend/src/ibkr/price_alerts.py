"""
REC-158: Server-side Price Alerts via IB Gateway.

Manages price alert subscriptions and triggers push notifications
when prices cross thresholds.
"""
import json
import os
import logging
from datetime import datetime, timezone
from typing import Optional, List
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

ALERTS_FILE = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'price_alerts.json')


@dataclass
class PriceAlert:
    """A price alert subscription."""
    id: str
    user_id: str
    ticker: str
    condition: str  # "ABOVE" or "BELOW"
    target_price: float
    created_at: str
    triggered_at: Optional[str] = None
    is_active: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


def _load_alerts() -> dict:
    """Load alerts from JSON file."""
    if os.path.exists(ALERTS_FILE):
        try:
            with open(ALERTS_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return {"alerts": []}


def _save_alerts(data: dict):
    """Save alerts to JSON file."""
    os.makedirs(os.path.dirname(ALERTS_FILE), exist_ok=True)
    with open(ALERTS_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def create_price_alert(
    user_id: str,
    ticker: str,
    condition: str,
    target_price: float,
) -> PriceAlert:
    """
    Create a new price alert.
    
    Args:
        user_id: User creating the alert
        ticker: Stock ticker symbol
        condition: "ABOVE" or "BELOW"
        target_price: Price threshold
    
    Returns:
        Created PriceAlert object
    """
    condition_upper = condition.upper()
    if condition_upper not in ("ABOVE", "BELOW"):
        raise ValueError(f"Invalid condition: {condition}. Must be ABOVE or BELOW.")

    import uuid
    alert = PriceAlert(
        id=str(uuid.uuid4())[:8],
        user_id=user_id,
        ticker=ticker.upper(),
        condition=condition_upper,
        target_price=target_price,
        created_at=datetime.now(timezone.utc).isoformat(),
    )

    data = _load_alerts()
    data["alerts"].append(alert.to_dict())
    _save_alerts(data)

    logger.info("Created price alert: %s %s %s %.2f", ticker, condition, target_price, alert.id)
    return alert


def get_user_alerts(user_id: str, active_only: bool = True) -> List[PriceAlert]:
    """Get all alerts for a user."""
    data = _load_alerts()
    alerts = []
    for a in data["alerts"]:
        if a["user_id"] == user_id:
            if active_only and not a.get("is_active", True):
                continue
            alerts.append(PriceAlert(**a))
    return alerts


def delete_alert(alert_id: str, user_id: str) -> bool:
    """Delete a price alert."""
    data = _load_alerts()
    original_count = len(data["alerts"])
    data["alerts"] = [
        a for a in data["alerts"]
        if not (a["id"] == alert_id and a["user_id"] == user_id)
    ]
    _save_alerts(data)
    return len(data["alerts"]) < original_count


def check_alerts_against_price(ticker: str, current_price: float) -> List[PriceAlert]:
    """
    Check all active alerts for a ticker against current price.
    
    Returns list of triggered alerts.
    """
    data = _load_alerts()
    triggered = []

    for i, a in enumerate(data["alerts"]):
        if a["ticker"] != ticker.upper():
            continue
        if not a.get("is_active", True):
            continue
        if a.get("triggered_at"):
            continue

        should_trigger = False
        if a["condition"] == "ABOVE" and current_price >= a["target_price"]:
            should_trigger = True
        elif a["condition"] == "BELOW" and current_price <= a["target_price"]:
            should_trigger = True

        if should_trigger:
            # Mark as triggered
            data["alerts"][i]["triggered_at"] = datetime.now(timezone.utc).isoformat()
            data["alerts"][i]["is_active"] = False
            triggered.append(PriceAlert(**data["alerts"][i]))
            logger.info("Price alert triggered: %s %s %.2f (current: %.2f)",
                       a["ticker"], a["condition"], a["target_price"], current_price)

    if triggered:
        _save_alerts(data)

    return triggered


def send_alert_notification(alert: PriceAlert, current_price: float):
    """Send push notification for triggered alert."""
    try:
        from notifications.push_service import broadcast_push
        
        direction = "above" if alert.condition == "ABOVE" else "below"
        title = f"🔔 Price Alert: {alert.ticker}"
        body = f"{alert.ticker} is now ${current_price:.2f} ({direction} ${alert.target_price:.2f})"
        
        broadcast_push(
            title=title,
            body=body,
            data={
                "type": "price_alert",
                "ticker": alert.ticker,
                "condition": alert.condition,
                "target_price": alert.target_price,
                "current_price": current_price,
            },
            user_id=alert.user_id
        )
        logger.info("Sent price alert notification to user %s", alert.user_id)
    except Exception as e:
        logger.warning("Failed to send price alert notification: %s", e)
