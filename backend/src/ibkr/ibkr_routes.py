"""
F6.3 IBKR API Routes

Endpoints for IBKR connection management and live order submission.
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from typing import Optional

from .ibkr_service import get_ibkr_service
from .price_alerts import (
    create_price_alert, get_user_alerts, delete_alert,
    check_alerts_against_price, send_alert_notification
)
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
    # REC-143: Trailing stop
    trailing_percent: Optional[float] = None
    trailing_amount: Optional[float] = None
    # REC-145: Extended hours
    outside_rth: bool = False
    # REC-146: Good-till-date
    tif: str = "DAY"  # DAY, GTC, GTD, IOC, FOK
    good_till_date: Optional[str] = None  # Format: YYYYMMDD HH:MM:SS
    # REC-151: Auto stop-loss
    auto_stop_loss_percent: Optional[float] = None  # e.g., 5.0 for 5% below entry


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
            trailing_percent=request.trailing_percent,
            trailing_amount=request.trailing_amount,
            outside_rth=request.outside_rth,
            tif=request.tif,
            good_till_date=request.good_till_date,
        )

        # REC-151: Auto stop-loss - submit protective stop when order fills
        stop_order = None
        if (request.auto_stop_loss_percent and 
            order.status == "FILLED" and 
            order.filled_price and
            request.side.upper() == "BUY"):
            
            stop_price = order.filled_price * (1 - request.auto_stop_loss_percent / 100)
            try:
                stop_order = service.submit_order(
                    user_id=_get_user_id(user),
                    ticker=request.ticker,
                    side="SELL",
                    quantity=request.quantity,
                    order_type="STP",
                    limit_price=round(stop_price, 2),
                    tif="GTC",  # Stop-loss should persist
                )
            except Exception as e:
                # Log but don't fail the main order
                import logging
                logging.warning(f"Auto stop-loss failed: {e}")

        result = {
            "success": True,
            "data": order.to_dict(),
        }
        if stop_order:
            result["stop_order"] = stop_order.to_dict()

        return result

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


@ibkr_router.get("/margin")
async def get_ibkr_margin(user=Depends(get_optional_user)):
    """
    Get margin status from IB Gateway (REC-153).
    
    Returns margin utilization, buying power, and alerts if approaching limits.
    """
    try:
        service = get_ibkr_service()
        summary = service.get_account_summary(user_id=_get_user_id(user))
        
        # Calculate margin utilization
        net_liq = summary.get("net_liquidation", 0)
        buying_power = summary.get("buying_power", 0)
        gross_position = summary.get("gross_position_value", 0)
        
        # Margin utilization = positions / net liquidation
        margin_used = gross_position / net_liq if net_liq > 0 else 0
        margin_available = 1 - margin_used
        
        # Alert thresholds
        alert_level = None
        if margin_used >= 0.9:
            alert_level = "CRITICAL"
        elif margin_used >= 0.75:
            alert_level = "WARNING"
        elif margin_used >= 0.5:
            alert_level = "ELEVATED"
        
        return {
            "success": True,
            "data": {
                "net_liquidation": net_liq,
                "buying_power": buying_power,
                "gross_position_value": gross_position,
                "margin_used_percent": round(margin_used * 100, 2),
                "margin_available_percent": round(margin_available * 100, 2),
                "alert_level": alert_level,
                "is_paper": summary.get("is_paper", True),
            }
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@ibkr_router.get("/quote/{ticker}")
async def get_ibkr_quote(ticker: str, user=Depends(get_optional_user)):
    """
    Get real-time quote from IB Gateway (REC-140).
    
    Returns bid, ask, last, volume, etc. directly from IB.
    Much faster than Yahoo Finance polling.
    """
    try:
        service = get_ibkr_service()
        quote = service.get_quote(user_id=_get_user_id(user), ticker=ticker)

        return {
            "success": True,
            "data": quote,
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


# ═══════════════════════════════════════════════════════════════════════
# Price Alerts (REC-158)
# ═══════════════════════════════════════════════════════════════════════

class PriceAlertRequest(BaseModel):
    ticker: str
    condition: str  # "ABOVE" or "BELOW"
    target_price: float


@ibkr_router.post("/alerts")
async def create_ibkr_price_alert(
    request: PriceAlertRequest,
    user=Depends(get_optional_user),
):
    """Create a server-side price alert (REC-158)."""
    try:
        alert = create_price_alert(
            user_id=_get_user_id(user),
            ticker=request.ticker,
            condition=request.condition,
            target_price=request.target_price,
        )

        return {
            "success": True,
            "message": f"Alert created: {request.ticker} {request.condition} ${request.target_price}",
            "data": alert.to_dict(),
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@ibkr_router.get("/alerts")
async def get_ibkr_price_alerts(user=Depends(get_optional_user)):
    """Get all price alerts for the current user."""
    try:
        alerts = get_user_alerts(user_id=_get_user_id(user))

        return {
            "success": True,
            "count": len(alerts),
            "data": [a.to_dict() for a in alerts],
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@ibkr_router.delete("/alerts/{alert_id}")
async def delete_ibkr_price_alert(alert_id: str, user=Depends(get_optional_user)):
    """Delete a price alert."""
    try:
        deleted = delete_alert(alert_id=alert_id, user_id=_get_user_id(user))

        if not deleted:
            raise HTTPException(status_code=404, detail="Alert not found")

        return {
            "success": True,
            "message": "Alert deleted",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@ibkr_router.post("/alerts/check/{ticker}")
async def check_price_alerts(ticker: str, user=Depends(get_optional_user)):
    """
    Check and trigger price alerts for a ticker.
    
    Fetches current price from IB and triggers any matching alerts.
    Typically called periodically by a background job.
    """
    try:
        service = get_ibkr_service()
        quote = service.get_quote(user_id=_get_user_id(user), ticker=ticker)
        
        current_price = quote.get("price") or quote.get("last") or quote.get("close")
        if not current_price:
            raise ValueError(f"Could not get price for {ticker}")

        triggered = check_alerts_against_price(ticker, current_price)
        
        # Send notifications for triggered alerts
        for alert in triggered:
            send_alert_notification(alert, current_price)

        return {
            "success": True,
            "ticker": ticker.upper(),
            "current_price": current_price,
            "triggered_count": len(triggered),
            "triggered": [a.to_dict() for a in triggered],
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
