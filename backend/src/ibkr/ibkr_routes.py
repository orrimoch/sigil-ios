"""
F6.3 IBKR API Routes

Endpoints for IBKR connection management and live order submission.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

from .ibkr_service import get_ibkr_service

ibkr_router = APIRouter(prefix="/api/v1/ibkr", tags=["ibkr"])

# Default user ID when auth is not required
ANONYMOUS_USER_ID = "anonymous"


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

@ibkr_router.post("/connect")
async def connect_ibkr(request: IBKRConnectRequest):
    """
    Connect to IBKR via mock OAuth flow.

    In production, would initiate OAuth redirect to IBKR.
    For now, simulates immediate connection.
    """
    try:
        service = get_ibkr_service()
        conn = service.connect(
            user_id=ANONYMOUS_USER_ID,
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
async def get_ibkr_status():
    """Get current IBKR connection status."""
    try:
        service = get_ibkr_service()
        conn = service.get_status(user_id=ANONYMOUS_USER_ID)

        return {
            "success": True,
            "data": conn.to_dict(),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@ibkr_router.post("/disconnect")
async def disconnect_ibkr():
    """Disconnect from IBKR."""
    try:
        service = get_ibkr_service()
        conn = service.disconnect(user_id=ANONYMOUS_USER_ID)

        return {
            "success": True,
            "message": "Disconnected from IBKR",
            "data": conn.to_dict(),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@ibkr_router.post("/orders")
async def submit_ibkr_order(request: IBKROrderRequest):
    """
    Submit an order to IBKR.

    Mock mode: returns simulated fill.
    """
    try:
        service = get_ibkr_service()
        order = service.submit_order(
            user_id=ANONYMOUS_USER_ID,
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
async def get_ibkr_positions():
    """Get IBKR account positions."""
    try:
        service = get_ibkr_service()
        positions = service.get_positions(user_id=ANONYMOUS_USER_ID)

        return {
            "success": True,
            "count": len(positions),
            "data": [p.to_dict() for p in positions],
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
