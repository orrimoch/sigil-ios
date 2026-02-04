"""Push notification API routes."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from . import push_service

router = APIRouter(prefix="/notifications", tags=["notifications"])


class DeviceTokenRequest(BaseModel):
    device_token: str
    platform: str = "ios"


class PushNotificationRequest(BaseModel):
    title: str
    body: str
    user_id: Optional[str] = None
    data: Optional[dict] = None
    badge: Optional[int] = None


@router.post("/register-token")
async def register_token(req: DeviceTokenRequest, user_id: str = "anonymous"):
    """Register a device token for push notifications."""
    token = push_service.register_device_token(
        user_id=user_id,
        device_token=req.device_token,
        platform=req.platform
    )
    return {"success": True, "data": token}


@router.delete("/unregister-token")
async def unregister_token(device_token: str):
    """Unregister a device token."""
    removed = push_service.unregister_device_token(device_token)
    if not removed:
        raise HTTPException(status_code=404, detail="Token not found")
    return {"success": True, "message": "Token unregistered"}


@router.post("/send")
async def send_notification(req: PushNotificationRequest):
    """Send a push notification (broadcast or to specific user)."""
    result = push_service.broadcast_push(
        title=req.title,
        body=req.body,
        data=req.data,
        user_id=req.user_id
    )
    return {"success": True, "data": result}


@router.get("/tokens")
async def list_tokens(user_id: Optional[str] = None):
    """List registered device tokens."""
    if user_id:
        tokens = push_service.get_user_tokens(user_id)
    else:
        tokens = push_service.get_all_active_tokens()
    return {"success": True, "count": len(tokens), "data": tokens}
