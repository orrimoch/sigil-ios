"""
Push Notification Service — manages device tokens and sends push notifications.
APNs sending is stubbed (requires Apple Developer certificate).
Infrastructure is complete for when certificates are available.
"""
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

TOKENS_FILE = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'device_tokens.json')


def _load_tokens() -> dict:
    if os.path.exists(TOKENS_FILE):
        with open(TOKENS_FILE, 'r') as f:
            return json.load(f)
    return {"tokens": []}


def _save_tokens(data: dict):
    os.makedirs(os.path.dirname(TOKENS_FILE), exist_ok=True)
    with open(TOKENS_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def register_device_token(user_id: str, device_token: str, platform: str = "ios") -> dict:
    """Register or update a device token for push notifications."""
    data = _load_tokens()

    # Remove existing token for this device (update scenario)
    data["tokens"] = [t for t in data["tokens"] if t["device_token"] != device_token]

    token_entry = {
        "id": str(uuid.uuid4())[:8],
        "user_id": user_id,
        "device_token": device_token,
        "platform": platform,
        "registered_at": datetime.now(timezone.utc).isoformat(),
        "last_used_at": datetime.now(timezone.utc).isoformat(),
        "is_active": True
    }

    data["tokens"].append(token_entry)
    _save_tokens(data)
    return token_entry


def unregister_device_token(device_token: str) -> bool:
    """Remove a device token (user logged out or uninstalled)."""
    data = _load_tokens()
    original_count = len(data["tokens"])
    data["tokens"] = [t for t in data["tokens"] if t["device_token"] != device_token]
    _save_tokens(data)
    return len(data["tokens"]) < original_count


def get_user_tokens(user_id: str) -> list:
    """Get all active device tokens for a user."""
    data = _load_tokens()
    return [t for t in data["tokens"] if t["user_id"] == user_id and t["is_active"]]


def get_all_active_tokens() -> list:
    """Get all active device tokens (for broadcast)."""
    data = _load_tokens()
    return [t for t in data["tokens"] if t["is_active"]]


def send_push_notification(
    device_token: str,
    title: str,
    body: str,
    data: Optional[dict] = None,
    badge: Optional[int] = None,
    sound: str = "default"
) -> dict:
    """
    Send a push notification via APNs.

    STUB: Actual APNs integration requires:
    - Apple Developer Program membership
    - Push notification certificate (.p8 key)
    - APNs provider (e.g., PyAPNs2)

    Returns simulated success response.
    """
    notification_id = str(uuid.uuid4())[:8]

    payload = {
        "aps": {
            "alert": {"title": title, "body": body},
            "sound": sound,
        }
    }
    if badge is not None:
        payload["aps"]["badge"] = badge
    if data:
        payload.update(data)

    # Log the notification (would be sent to APNs in production)
    result = {
        "notification_id": notification_id,
        "device_token": device_token[:16] + "...",
        "status": "queued",  # Would be "sent" with real APNs
        "payload": payload,
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "note": "APNs stub — install PyAPNs2 and configure .p8 key for real delivery"
    }

    return result


def broadcast_push(
    title: str,
    body: str,
    data: Optional[dict] = None,
    user_id: Optional[str] = None
) -> dict:
    """Send push to all tokens (or all tokens for a specific user)."""
    if user_id:
        tokens = get_user_tokens(user_id)
    else:
        tokens = get_all_active_tokens()

    results = []
    for token in tokens:
        result = send_push_notification(
            device_token=token["device_token"],
            title=title,
            body=body,
            data=data
        )
        results.append(result)

    return {
        "total_tokens": len(tokens),
        "sent": len(results),
        "results": results
    }


def send_order_fill_notification(
    user_id: str,
    ticker: str,
    side: str,
    quantity: float,
    fill_price: float,
    order_type: str = "MARKET",
    is_paper: bool = True
) -> dict:
    """
    Send push notification when an order fills (REC-141).
    
    Args:
        user_id: User who placed the order
        ticker: Stock ticker symbol
        side: BUY or SELL
        quantity: Number of shares
        fill_price: Price at which the order filled
        order_type: MARKET, LIMIT, STP, etc.
        is_paper: Whether this is a paper trade
    
    Returns:
        Notification result dict
    """
    # Calculate total
    total = quantity * fill_price
    
    # Format the notification
    mode_prefix = "📝 Paper " if is_paper else "💰 "
    side_emoji = "🟢" if side == "BUY" else "🔴"
    
    title = f"{mode_prefix}Order Filled"
    body = f"{side_emoji} {side} {int(quantity)} {ticker} @ ${fill_price:.2f} (${total:,.2f})"
    
    # Notification data payload for deep linking
    data = {
        "type": "order_fill",
        "ticker": ticker,
        "side": side,
        "quantity": quantity,
        "fill_price": fill_price,
        "total": total,
        "is_paper": is_paper,
        "order_type": order_type
    }
    
    # Send to user's devices
    return broadcast_push(
        title=title,
        body=body,
        data=data,
        user_id=user_id
    )


# ==================== REC-229: Risk Push Notifications ====================

def send_stop_loss_triggered_notification(
    user_id: str,
    ticker: str,
    trigger_price: float,
    loss_pct: float,
    stop_type: str = "hard",
    quantity: Optional[float] = None,
) -> dict:
    """
    Send push notification when a stop-loss is triggered (REC-229).
    
    Args:
        user_id: User ID
        ticker: Stock symbol
        trigger_price: Price at which stop triggered
        loss_pct: Percentage loss (negative number)
        stop_type: "hard" or "trailing"
        quantity: Number of shares (optional)
        
    Returns:
        Notification result dict
    """
    stop_emoji = "🛑" if stop_type == "hard" else "📉"
    stop_label = "Stop-loss" if stop_type == "hard" else "Trailing stop"
    
    title = f"⚠️ {stop_label} Triggered"
    body = f"{stop_emoji} {ticker} hit {stop_label.lower()} at ${trigger_price:.2f} ({loss_pct:.1f}%)"
    
    if quantity:
        body += f" — {int(quantity)} shares sold"
    
    data = {
        "type": "stop_loss_triggered",
        "ticker": ticker,
        "trigger_price": trigger_price,
        "loss_pct": loss_pct,
        "stop_type": stop_type,
        "quantity": quantity,
    }
    
    return broadcast_push(
        title=title,
        body=body,
        data=data,
        user_id=user_id
    )


def send_approaching_stop_notification(
    user_id: str,
    ticker: str,
    current_price: float,
    stop_price: float,
    distance_pct: float,
    stop_type: str = "hard",
) -> dict:
    """
    Send push notification when price approaches stop-loss (within 2%).
    
    Args:
        user_id: User ID
        ticker: Stock symbol
        current_price: Current market price
        stop_price: Stop-loss price
        distance_pct: Distance from stop as percentage (e.g., 1.5 = 1.5% away)
        stop_type: "hard" or "trailing"
        
    Returns:
        Notification result dict
    """
    # Choose emoji based on urgency
    if distance_pct <= 1.0:
        urgency_emoji = "🔴"
        urgency_text = "very close to"
    elif distance_pct <= 2.0:
        urgency_emoji = "🟡"
        urgency_text = "approaching"
    else:
        urgency_emoji = "🟢"
        urgency_text = "near"
    
    stop_label = "stop-loss" if stop_type == "hard" else "trailing stop"
    
    title = f"📉 {ticker} {urgency_text.title()} Stop"
    body = f"{urgency_emoji} {ticker} at ${current_price:.2f} — {distance_pct:.1f}% from {stop_label} (${stop_price:.2f})"
    
    data = {
        "type": "approaching_stop",
        "ticker": ticker,
        "current_price": current_price,
        "stop_price": stop_price,
        "distance_pct": distance_pct,
        "stop_type": stop_type,
    }
    
    return broadcast_push(
        title=title,
        body=body,
        data=data,
        user_id=user_id
    )


def send_risk_alert_notification(
    user_id: str,
    ticker: str,
    risk_score: int,
    risk_level: str,
    reason: str,
) -> dict:
    """
    Send push notification for elevated risk detected by Claude analyzer.
    
    Args:
        user_id: User ID
        ticker: Stock symbol
        risk_score: Risk score 0-100
        risk_level: "low", "medium", "high", "critical"
        reason: Brief explanation
        
    Returns:
        Notification result dict
    """
    # Choose emoji based on risk level
    level_emojis = {
        "low": "🟢",
        "medium": "🟡",
        "high": "🟠",
        "critical": "🔴",
    }
    emoji = level_emojis.get(risk_level, "⚠️")
    
    title = f"{emoji} Risk Alert: {ticker}"
    body = f"Risk score: {risk_score}/100 ({risk_level}). {reason}"
    
    data = {
        "type": "risk_alert",
        "ticker": ticker,
        "risk_score": risk_score,
        "risk_level": risk_level,
        "reason": reason,
    }
    
    return broadcast_push(
        title=title,
        body=body,
        data=data,
        user_id=user_id
    )


def send_vix_alert_notification(
    user_id: str,
    vix_value: float,
    vix_regime: str,
    change_pct: float,
) -> dict:
    """
    Send push notification for significant VIX changes.
    
    Args:
        user_id: User ID
        vix_value: Current VIX value
        vix_regime: "low", "normal", "elevated", "high", "extreme"
        change_pct: Percentage change from previous
        
    Returns:
        Notification result dict
    """
    # Choose emoji based on regime
    regime_emojis = {
        "low": "🟢",
        "normal": "🔵",
        "elevated": "🟡",
        "high": "🟠",
        "extreme": "🔴",
    }
    emoji = regime_emojis.get(vix_regime, "📊")
    
    direction = "↑" if change_pct > 0 else "↓"
    
    title = f"{emoji} VIX Alert: {vix_regime.title()} Volatility"
    body = f"VIX at {vix_value:.1f} ({direction}{abs(change_pct):.1f}%). Thresholds may be adjusted."
    
    data = {
        "type": "vix_alert",
        "vix_value": vix_value,
        "vix_regime": vix_regime,
        "change_pct": change_pct,
    }
    
    return broadcast_push(
        title=title,
        body=body,
        data=data,
        user_id=user_id
    )
