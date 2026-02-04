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
