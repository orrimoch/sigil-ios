"""
Risk Settings API Routes

REC-216: Risk Settings API
GET/PUT /api/v1/user/risk-settings
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from auth.middleware import get_required_user
from auth.database import get_db_session
from db.models import ANONYMOUS_USER_ID
from .models import UserRiskSettings
from .service import RiskSettingsService

router = APIRouter(prefix="/api/v1/user", tags=["risk"])


# ========== Pydantic Models for API ==========

class StopConfigRequest(BaseModel):
    """Hard stop configuration in API request."""
    enabled: bool = False
    threshold_pct: float = Field(default=-0.08, ge=-0.20, le=-0.05)


class TrailingStopConfigRequest(BaseModel):
    """Trailing stop configuration in API request."""
    enabled: bool = False
    distance_pct: float = Field(default=-0.10, ge=-0.25, le=-0.05)


class VixAdjustmentConfigRequest(BaseModel):
    """VIX adjustment configuration in API request."""
    enabled: bool = False


class PositionLimitConfigRequest(BaseModel):
    """Position limit configuration in API request."""
    enabled: bool = False
    max_pct: float = Field(default=0.15, ge=0.05, le=0.30)


class RiskSettingsRequest(BaseModel):
    """Full risk settings update request."""
    hard_stop: Optional[StopConfigRequest] = None
    trailing_stop: Optional[TrailingStopConfigRequest] = None
    vix_adjustment: Optional[VixAdjustmentConfigRequest] = None
    position_limit: Optional[PositionLimitConfigRequest] = None


class RiskSettingsResponse(BaseModel):
    """Risk settings API response."""
    success: bool = True
    data: Dict[str, Any]


# ========== Endpoints ==========

@router.get("/risk-settings", response_model=RiskSettingsResponse)
async def get_risk_settings(
    user=Depends(get_required_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Get user's risk management settings.
    
    Returns current settings with defaults for any unset values.
    All protections default to OFF (minimum restriction).
    """
    try:
        user_id = user.id if user else ANONYMOUS_USER_ID
        settings = await RiskSettingsService.get_settings(db, user_id)
        
        return {
            "success": True,
            "data": settings.to_dict(),
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/risk-settings", response_model=RiskSettingsResponse)
async def update_risk_settings(
    request: RiskSettingsRequest,
    user=Depends(get_required_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Update user's risk management settings.
    
    Partial updates are supported - only include fields you want to change.
    When settings change, IBKR stop orders are automatically synced.
    
    Side Effects:
    - If hard_stop.enabled changes → place/cancel IBKR STP orders
    - If trailing_stop.enabled changes → place/cancel IBKR TRAIL orders
    """
    try:
        user_id = user.id if user else ANONYMOUS_USER_ID
        
        # Build updates dict from request
        updates = {}
        if request.hard_stop is not None:
            updates["hard_stop"] = request.hard_stop.model_dump()
        if request.trailing_stop is not None:
            updates["trailing_stop"] = request.trailing_stop.model_dump()
        if request.vix_adjustment is not None:
            updates["vix_adjustment"] = request.vix_adjustment.model_dump()
        if request.position_limit is not None:
            updates["position_limit"] = request.position_limit.model_dump()
        
        if not updates:
            # No updates, just return current settings
            settings = await RiskSettingsService.get_settings(db, user_id)
        else:
            # Apply updates
            settings = await RiskSettingsService.update_settings(db, user_id, updates)
        
        return {
            "success": True,
            "data": settings.to_dict(),
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/risk-settings/reset", response_model=RiskSettingsResponse)
async def reset_risk_settings(
    user=Depends(get_required_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Reset risk settings to defaults (all OFF).
    
    This will cancel any existing IBKR stop orders.
    """
    try:
        user_id = user.id if user else ANONYMOUS_USER_ID
        settings = await RiskSettingsService.reset_to_defaults(db, user_id)
        
        return {
            "success": True,
            "data": settings.to_dict(),
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/risk-settings/defaults", response_model=RiskSettingsResponse)
async def get_risk_settings_defaults():
    """
    Get default risk settings (all OFF).
    
    This endpoint does not require authentication.
    Useful for initializing the settings UI.
    """
    defaults = UserRiskSettings.default("defaults")
    return {
        "success": True,
        "data": defaults.to_dict(),
    }
