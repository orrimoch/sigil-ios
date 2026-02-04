"""
F6.3 IBKR API Routes

Endpoints for IBKR connection management and live order submission.
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from typing import Optional

from .ibkr_service import get_ibkr_service
from auth.middleware import get_optional_user
from db.models import ANONYMOUS_USER_ID

ibkr_router = APIRouter(prefix="/api/v1/ibkr", tags=["ibkr"])


# ── Request / Response Schemas ──────────────────────────────────────────

class IBKRConnectRequest(BaseModel):
    account_id: Optional[str] = None


class IBKROrderRequest(BaseModel):
    ticker: str
    side: str  # BUY or SELL
    quantity: float
    order_type: str = "MARKET"
    limit_price: Optional[float] = None


# ── Endpoints ───────────────────────────────────────────────────────────

def _get_user_id(user) -> str:
    """Extract user_id from optional user, fallback to ANONYMOUS_USER_ID."""
    return user.id if user else ANONYMOUS_USER_ID


@ibkr_router.post("/connect")
async def connect_ibkr(
    request: IBKRConnectRequest,
    user=Depends(get_optional_user),
):
    """
    Connect to IBKR via mock OAuth flow.

    In production, would initiate OAuth redirect to IBKR.
    For now, simulates immediate connection.
    """
    try:
        service = get_ibkr_service()
        conn = service.connect(
            user_id=_get_user_id(user),
            account_id=request.account_id,
        )

        return {
            "success": True,
            "message": "Connected to IBKR",
            "data": conn.to_dict(),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@ibkr_router.get("/status")
async def get_ibkr_status(user=Depends(get_optional_user)):
    """Get current IBKR connection status."""
    try:
        service = get_ibkr_service()
        conn = service.get_status(user_id=_get_user_id(user))

        return {
            "success": True,
            "data": conn.to_dict(),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@ibkr_router.post("/disconnect")
async def disconnect_ibkr(user=Depends(get_optional_user)):
    """Disconnect from IBKR."""
    try:
        service = get_ibkr_service()
        conn = service.disconnect(user_id=_get_user_id(user))

        return {
            "success": True,
            "message": "Disconnected from IBKR",
            "data": conn.to_dict(),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@ibkr_router.post("/orders")
async def submit_ibkr_order(
    request: IBKROrderRequest,
    user=Depends(get_optional_user),
):
    """
    Submit an order to IBKR.

    Mock mode: returns simulated fill.
    """
    try:
        service = get_ibkr_service()
        order = service.submit_order(
            user_id=_get_user_id(user),
            ticker=request.ticker,
            side=request.side,
            quantity=request.quantity,
            order_type=request.order_type,
            limit_price=request.limit_price,
        )

        return {
            "success": True,
            "data": order.to_dict(),
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@ibkr_router.get("/positions")
async def get_ibkr_positions(user=Depends(get_optional_user)):
    """Get IBKR account positions."""
    try:
        service = get_ibkr_service()
        positions = service.get_positions(user_id=_get_user_id(user))

        return {
            "success": True,
            "count": len(positions),
            "data": [p.to_dict() for p in positions],
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@ibkr_router.get("/account")
async def get_ibkr_account_summary(user=Depends(get_optional_user)):
    """Get IBKR account summary (balances, buying power, PnL)."""
    try:
        service = get_ibkr_service()
        summary = service.get_account_summary(user_id=_get_user_id(user))

        return {
            "success": True,
            "data": summary,
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@ibkr_router.get("/orders/open")
async def get_ibkr_open_orders(user=Depends(get_optional_user)):
    """Get all open (pending) IBKR orders."""
    try:
        service = get_ibkr_service()
        orders = service.get_open_orders(user_id=_get_user_id(user))

        return {
            "success": True,
            "count": len(orders),
            "data": [o.to_dict() for o in orders],
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@ibkr_router.delete("/orders/{order_id}")
async def cancel_ibkr_order(order_id: str, user=Depends(get_optional_user)):
    """Cancel an open IBKR order."""
    try:
        service = get_ibkr_service()
        result = service.cancel_order(
            user_id=_get_user_id(user),
            order_id=order_id,
        )

        return {
            "success": True,
            "message": "Order cancellation requested",
            "data": result,
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
