"""
Risk Phase 3 API Routes

REC-243: HMM Regime Detection
REC-244: Regime API Endpoint
REC-245: Sector Limits
REC-247: Portfolio VaR
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime

# Create router
router = APIRouter(prefix="/api/v1", tags=["risk-p3"])


# ========== Pydantic Models ==========

class RegimeResponse(BaseModel):
    """Market regime detection response."""
    success: bool = True
    data: Dict[str, Any]


class SectorExposureResponse(BaseModel):
    """Sector exposure analysis response."""
    success: bool = True
    data: Dict[str, Any]


class PortfolioVaRResponse(BaseModel):
    """Portfolio-level VaR response."""
    success: bool = True
    data: Dict[str, Any]


# ========== Regime Detection Endpoints (REC-243, REC-244) ==========

@router.get("/market/regime", response_model=RegimeResponse)
async def get_market_regime(
    use_cache: bool = Query(True, description="Use cached result if available"),
):
    """
    Get current market volatility regime.
    
    Uses HMM (Hidden Markov Model) trained on SPY/VIX data to detect:
    - LOW_VOL: Calm market, low volatility
    - NORMAL: Average volatility
    - HIGH_VOL: Elevated volatility  
    - CRISIS: Extreme volatility
    
    The regime affects scoring thresholds via `threshold_adjustment`.
    
    Cached for 1 hour by default.
    """
    try:
        from .hmm_regime import detect_current_regime
        
        result = await detect_current_regime(use_cache=use_cache)
        
        return {
            "success": True,
            "data": result.to_dict(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Regime detection failed: {e}")


@router.get("/market/regime/history")
async def get_regime_history(
    days: int = Query(30, ge=1, le=365, description="Days of history"),
):
    """
    Get historical regime detections.
    
    Returns regime for each day in the requested period.
    Useful for backtesting and analysis.
    """
    try:
        import yfinance as yf
        import numpy as np
        from .hmm_regime import get_regime_detector
        from .vix_service import fetch_vix
        
        # Fetch SPY history
        spy = yf.Ticker("SPY")
        hist = spy.history(period=f"{days + 30}d")  # Extra for rolling window
        
        if len(hist) < 30:
            raise HTTPException(status_code=400, detail="Insufficient market data")
        
        returns = hist['Close'].pct_change().dropna()
        dates = returns.index.tolist()
        
        # Fetch VIX history
        vix = yf.Ticker("^VIX")
        vix_hist = vix.history(period=f"{days + 30}d")
        
        detector = get_regime_detector()
        history = []
        
        # Detect regime for each day (using 20-day lookback)
        for i in range(20, min(len(returns), days + 20)):
            day_returns = returns.iloc[i-20:i].values
            date = dates[i]
            
            # Get VIX for that day if available
            try:
                vix_value = float(vix_hist.loc[date, 'Close'])
            except:
                vix_value = None
            
            result = detector.detect(day_returns, vix_value)
            
            history.append({
                "date": date.strftime("%Y-%m-%d"),
                "regime": result.regime.value,
                "confidence": round(result.confidence, 3),
                "vix": round(vix_value, 2) if vix_value else None,
            })
        
        return {
            "success": True,
            "count": len(history),
            "data": history[-days:],  # Return only requested days
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch regime history: {e}")


@router.post("/market/regime/train")
async def train_regime_model(
    start_date: str = Query("2020-01-01", description="Training start date (YYYY-MM-DD)"),
):
    """
    Retrain the HMM regime detection model.
    
    Should be run periodically (e.g., monthly) to update the model
    with recent market data.
    
    Requires significant historical data (2+ years recommended).
    """
    try:
        from .hmm_regime import train_regime_model_from_history
        
        train_regime_model_from_history(start_date=start_date)
        
        return {
            "success": True,
            "message": f"Model retrained from {start_date} to present",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Training failed: {e}")


# ========== Sector Exposure Endpoints (REC-245) ==========

@router.get("/portfolio/sectors/exposure", response_model=SectorExposureResponse)
async def get_sector_exposure(
    warn_threshold: float = Query(0.30, ge=0.1, le=0.5, description="Warning threshold (e.g., 0.30 = 30%)"),
):
    """
    Analyze portfolio sector concentration.
    
    Returns exposure by sector and warnings if any sector exceeds threshold.
    """
    try:
        from .sector_limits import analyze_sector_exposure
        from auth.middleware import get_optional_user
        
        # Get portfolio (simplified - would use actual user portfolio)
        # For now, return sample data
        result = await analyze_sector_exposure(
            positions=[],  # Would fetch from portfolio
            warn_threshold=warn_threshold,
        )
        
        return {
            "success": True,
            "data": result,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sector analysis failed: {e}")


# ========== Portfolio VaR Endpoints (REC-247) ==========

@router.get("/portfolio/var/correlated", response_model=PortfolioVaRResponse)
async def get_correlated_portfolio_var(
    lookback_days: int = Query(252, ge=30, le=504, description="Lookback for correlation"),
):
    """
    Calculate portfolio VaR using correlation matrix.
    
    More accurate than sum of individual VaRs due to diversification benefit.
    Uses historical returns to estimate covariance matrix.
    """
    try:
        from .portfolio_var import calculate_correlated_var
        
        # Get portfolio (simplified)
        result = await calculate_correlated_var(
            positions=[],  # Would fetch from portfolio
            lookback_days=lookback_days,
        )
        
        return {
            "success": True,
            "data": result,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Portfolio VaR calculation failed: {e}")
