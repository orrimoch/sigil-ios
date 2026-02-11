"""
Risk Phase 2 API Routes

REC-225: VIX Data Pipeline - GET /api/v1/market/vix
REC-227: Position Size Limits - POST /api/v1/trade/validate
REC-232: Claude Risk Analyzer - GET /api/v1/risk/analyze/{ticker}
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from auth.middleware import get_required_user, get_optional_user
from auth.database import get_db_session
from db.models import ANONYMOUS_USER_ID

# Import risk modules
from .vix_service import fetch_vix, get_vix_cache_stats, VIXData
from .dynamic_thresholds import get_adjusted_thresholds, get_threshold_table
from .position_limits import validate_trade, get_position_limit_summary, TradeValidationResult
from .var_calculator import calculate_portfolio_var, calculate_position_var
from .claude_analyzer import ClaudeRiskAnalyzer, get_risk_cache_stats, warm_cache_for_tickers
from .service import RiskSettingsService

# Create routers for different prefixes
market_router = APIRouter(prefix="/api/v1/market", tags=["market"])
trade_router = APIRouter(prefix="/api/v1/trade", tags=["trade"])
risk_router = APIRouter(prefix="/api/v1/risk", tags=["risk"])


# ========== Pydantic Models ==========

class VIXResponse(BaseModel):
    """VIX data response."""
    success: bool = True
    data: Dict[str, Any]


class TradeValidationRequest(BaseModel):
    """Trade validation request."""
    ticker: str
    action: str = Field(description="BUY or SELL", pattern="^(BUY|SELL)$")
    quantity: float = Field(gt=0)
    price: float = Field(gt=0)


class TradeValidationResponse(BaseModel):
    """Trade validation response."""
    valid: bool
    warnings: List[Dict[str, Any]]
    risk_metrics: Dict[str, Any]


class RiskAnalysisResponse(BaseModel):
    """Claude risk analysis response."""
    success: bool = True
    data: Dict[str, Any]


class PortfolioRiskResponse(BaseModel):
    """Portfolio-level risk response."""
    success: bool = True
    data: Dict[str, Any]


# ========== VIX Endpoints (REC-225) ==========

@market_router.get("/vix", response_model=VIXResponse)
async def get_vix():
    """
    Get current VIX value and market regime.
    
    Cached for 1 hour. Returns:
    - vix: Current VIX value
    - previous_close: Previous day's close
    - change: Absolute change
    - change_pct: Percentage change
    - regime: Market regime (low/normal/elevated/high/extreme)
    - updated_at: When data was fetched
    """
    try:
        vix_data = await fetch_vix(use_cache=True)
        return {
            "success": True,
            "data": vix_data.to_dict(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch VIX: {e}")


@market_router.get("/vix/thresholds", response_model=VIXResponse)
async def get_vix_thresholds(
    user=Depends(get_optional_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Get VIX-adjusted scoring thresholds.
    
    Returns current BUY/SELL thresholds adjusted for VIX level.
    Respects user's VIX adjustment setting if enabled.
    """
    try:
        # Get user settings if available
        settings = None
        if user:
            user_id = user.id if user else ANONYMOUS_USER_ID
            settings = await RiskSettingsService.get_settings(db, user_id)
        
        # Get adjusted thresholds
        thresholds = get_adjusted_thresholds(settings=settings)
        
        return {
            "success": True,
            "data": thresholds.to_dict(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@market_router.get("/vix/threshold-table")
async def get_vix_threshold_table():
    """
    Get VIX threshold lookup table for reference.
    
    Shows BUY/SELL thresholds at various VIX levels.
    """
    return {
        "success": True,
        "data": {
            "table": get_threshold_table(),
            "formula": "SELL = 50 + max(0, (VIX - 15) × 0.5)",
            "baseline_vix": 15,
        }
    }


@market_router.get("/vix/cache-stats")
async def get_vix_cache_statistics():
    """Get VIX cache statistics (for monitoring)."""
    return {
        "success": True,
        "data": get_vix_cache_stats(),
    }


# ========== Trade Validation Endpoints (REC-227) ==========

@trade_router.post("/validate", response_model=TradeValidationResponse)
async def validate_trade_endpoint(
    request: TradeValidationRequest,
    user=Depends(get_required_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Validate a trade against position size limits.
    
    Returns warnings if the trade would exceed configured limits.
    User can still proceed (warnings are not blocking by default).
    
    Warnings include:
    - position_limit: Trade exceeds max position % setting
    - concentration: Position would be >20% of portfolio
    """
    try:
        user_id = user.id if user else ANONYMOUS_USER_ID
        
        # Get user's risk settings
        settings = await RiskSettingsService.get_settings(db, user_id)
        
        # Get user's portfolio holdings (returns list directly)
        try:
            from trading.user_trading_service import UserTradingService
            holdings = await UserTradingService.get_portfolio_holdings(db, user_id)
            
            # Convert to expected format
            total_value = sum(h.get("market_value", 0) for h in holdings) if holdings else 0
            positions = [
                {
                    "ticker": h.get("ticker"),
                    "quantity": h.get("quantity", h.get("shares", 0)),
                    "current_price": h.get("current_price", 0),
                    "market_value": h.get("market_value", 0),
                }
                for h in holdings
            ] if holdings else []
            portfolio_data = {
                "positions": positions,
                "total_value": total_value,
            }
        except Exception as e:
            logger.warning(f"Failed to get portfolio: {e}")
            portfolio_data = {"positions": [], "total_value": 10000}
        
        # Validate trade
        result = validate_trade(
            ticker=request.ticker,
            action=request.action,
            quantity=request.quantity,
            price=request.price,
            portfolio=portfolio_data,
            settings=settings,
        )
        
        return result.to_dict()
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@trade_router.get("/position-limits", response_model=PortfolioRiskResponse)
async def get_position_limits_summary(
    user=Depends(get_required_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Get summary of current position sizes vs limits.
    
    Returns list of positions with their percentage of portfolio
    and whether they exceed the configured limit.
    """
    try:
        user_id = user.id if user else ANONYMOUS_USER_ID
        
        # Get user's risk settings
        settings = await RiskSettingsService.get_settings(db, user_id)
        
        # Get portfolio holdings (returns list directly)
        try:
            from trading.user_trading_service import UserTradingService
            holdings = await UserTradingService.get_portfolio_holdings(db, user_id)
            total_value = sum(h.get("market_value", 0) for h in holdings) if holdings else 0
            positions = [
                {
                    "ticker": h.get("ticker"),
                    "quantity": h.get("quantity", h.get("shares", 0)),
                    "current_price": h.get("current_price", 0),
                    "market_value": h.get("market_value", 0),
                }
                for h in holdings
            ] if holdings else []
            portfolio_data = {"positions": positions, "total_value": total_value}
        except Exception as e:
            logger.warning(f"Failed to get portfolio: {e}")
            portfolio_data = {"positions": [], "total_value": 0}
        
        summary = get_position_limit_summary(portfolio_data, settings)
        
        return {
            "success": True,
            "data": summary,
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ========== Claude Risk Analysis Endpoints (REC-232) ==========

@risk_router.get("/analyze/{ticker}", response_model=RiskAnalysisResponse)
async def analyze_ticker_risk(
    ticker: str,
    price: Optional[float] = Query(None, description="Current price (fetched if not provided)"),
    entry_price: Optional[float] = Query(None, description="Position entry price"),
    use_cache: bool = Query(True, description="Whether to use cached results"),
    user=Depends(get_optional_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Analyze risk for a specific ticker - FAST response with cached/rule-based data.
    
    Strategy:
    1. Return cached Claude analysis if available (instant)
    2. Otherwise return quick rule-based estimate (instant)
    3. Full Claude analysis runs on cache miss and populates cache for next time
    
    Results are cached for 24 hours.
    """
    from datetime import datetime, timezone
    
    try:
        analyzer = ClaudeRiskAnalyzer()
        
        # 1. Try cache first (instant response)
        if use_cache:
            cached = analyzer.cache.get_any(ticker)
            if cached is not None:
                logger.debug(f"Cache hit for {ticker} - instant response")
                return {"success": True, "data": cached.to_dict()}
        
        # 2. Quick rule-based estimate (instant, no API calls)
        # Calculate simple risk score based on available data
        risk_score = 50  # Default moderate
        risk_factors = []
        
        # Try to get cached price data (fast local file lookup)
        try:
            import json
            from pathlib import Path
            price_file = Path(__file__).parent.parent.parent / "data" / "prices" / f"{ticker}.json"
            if price_file.exists():
                price_data = json.loads(price_file.read_text())
                price = price_data.get('price', 100)
                change_pct = price_data.get('change_percent', 0) or 0
                
                # Simple rule-based scoring
                if abs(change_pct) > 5:
                    risk_score += 15
                    risk_factors.append("High recent volatility")
                if abs(change_pct) > 10:
                    risk_score += 10
                    risk_factors.append("Extreme price movement")
        except Exception:
            pass
        
        # Check VIX from cached file (no async call)
        try:
            vix_file = Path(__file__).parent.parent.parent / "data" / "vix_cache.json"
            if vix_file.exists():
                vix_data = json.loads(vix_file.read_text())
                vix_value = vix_data.get('value', 20)
                if vix_value > 25:
                    risk_score += 10
                    risk_factors.append("Elevated market volatility (VIX)")
                if vix_value > 35:
                    risk_score += 10
                    risk_factors.append("High fear index")
        except Exception:
            pass
        
        # Determine risk level
        risk_score = min(100, max(0, risk_score))
        if risk_score < 30:
            risk_level = "low"
            recommendation = "hold"
        elif risk_score < 50:
            risk_level = "medium"
            recommendation = "monitor"
        elif risk_score < 70:
            risk_level = "medium"
            recommendation = "monitor"
        else:
            risk_level = "high"
            recommendation = "reduce"
        
        if not risk_factors:
            risk_factors = ["Standard market conditions"]
        
        # Return instant rule-based result
        result = {
            "ticker": ticker,
            "risk_score": risk_score,
            "risk_level": risk_level,
            "risk_factors": risk_factors,
            "recommendation": recommendation,
            "reasoning": f"Quick assessment based on market data. Full AI analysis will be cached for future requests.",
            "confidence": 0.5,  # Lower confidence for rule-based
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
            "cached": False,
        }
        
        return {"success": True, "data": result}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Risk analysis error for {ticker}: {e}")
        # Return safe default on error
        return {
            "success": True,
            "data": {
                "ticker": ticker,
                "risk_score": 50,
                "risk_level": "medium",
                "risk_factors": ["Unable to complete full analysis"],
                "recommendation": "monitor",
                "reasoning": "Using default moderate risk assessment.",
                "confidence": 0.3,
                "analyzed_at": datetime.now(timezone.utc).isoformat(),
                "cached": False,
            }
        }


@risk_router.get("/var/{ticker}", response_model=RiskAnalysisResponse)
async def get_position_var(
    ticker: str,
    position_value: float = Query(..., gt=0, description="Position value in dollars"),
    lookback_days: int = Query(252, ge=30, le=504, description="Lookback period for volatility calculation"),
):
    """
    Calculate Value-at-Risk for a single position (REC-228).
    
    Returns:
    - ticker: Stock symbol
    - position_value: Input position value
    - var_95_daily: 95% daily VaR in dollars
    - var_95_pct: 95% daily VaR as percentage
    - volatility: Annualized volatility
    - confidence: Confidence level (0.95)
    """
    try:
        import yfinance as yf
        import numpy as np
        from scipy import stats
        
        # Fetch historical data
        stock = yf.Ticker(ticker.upper())
        hist = stock.history(period="2y")
        
        if len(hist) < 30:
            raise HTTPException(status_code=400, detail=f"Insufficient price history for {ticker}")
        
        # Use requested lookback or max available
        prices = hist['Close'].tail(lookback_days)
        returns = prices.pct_change().dropna()
        
        if len(returns) < 20:
            raise HTTPException(status_code=400, detail=f"Insufficient return data for {ticker}")
        
        # Calculate daily volatility
        daily_vol = float(returns.std())
        
        # Annualized volatility
        annualized_vol = daily_vol * np.sqrt(252)
        
        # 95% VaR (1.645 z-score for one-tailed 95%)
        z_score = stats.norm.ppf(0.95)
        var_95_pct = daily_vol * z_score * 100
        var_95_daily = position_value * daily_vol * z_score
        
        return {
            "success": True,
            "data": {
                "ticker": ticker.upper(),
                "position_value": position_value,
                "var_95_daily": round(var_95_daily, 2),
                "var_95_pct": round(var_95_pct, 4),
                "volatility_daily": round(daily_vol * 100, 4),
                "volatility_annual": round(annualized_vol * 100, 2),
                "lookback_days": len(returns),
                "confidence": 0.95,
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"VaR calculation failed: {e}")


@risk_router.get("/portfolio", response_model=PortfolioRiskResponse)
async def get_portfolio_risk(
    user=Depends(get_required_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Get portfolio-level risk metrics.
    
    Returns:
    - total_value: Portfolio value
    - var_95_daily: 95% VaR in dollars
    - var_95_pct: 95% VaR as percentage
    - risk_score: low/medium/high
    - position_vars: VaR for each position
    """
    try:
        user_id = user.id if user else ANONYMOUS_USER_ID
        
        # Get portfolio holdings (returns list directly)
        try:
            from trading.user_trading_service import UserTradingService
            holdings = await UserTradingService.get_portfolio_holdings(db, user_id)
            # Convert to format expected by calculate_portfolio_var
            positions = [
                {
                    "ticker": h.get("ticker"),
                    "quantity": h.get("quantity", h.get("shares", 0)),
                    "current_price": h.get("current_price", 0),
                    "market_value": h.get("market_value", 0),
                }
                for h in holdings
            ] if holdings else []
        except Exception as e:
            logger.warning(f"Failed to get portfolio holdings: {e}")
            positions = []
        
        if not positions:
            return {
                "success": True,
                "data": {
                    "total_value": 0,
                    "var_95_daily": 0,
                    "var_95_pct": 0,
                    "risk_score": "low",
                    "position_vars": [],
                    "message": "No positions in portfolio",
                }
            }
        
        # Calculate portfolio VaR
        result = calculate_portfolio_var(positions)
        
        return {
            "success": True,
            "data": result.to_dict(),
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@risk_router.get("/cache-stats")
async def get_risk_cache_statistics():
    """Get Claude risk analyzer cache statistics (for monitoring)."""
    return {
        "success": True,
        "data": get_risk_cache_stats(),
    }


@risk_router.post("/warm-cache")
async def warm_portfolio_cache(
    force: bool = Query(False, description="Force re-analyze even if cached"),
    user=Depends(get_required_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Pre-warm risk analysis cache for user's portfolio holdings.
    
    Call this after login to ensure all portfolio positions have
    cached Claude risk analysis for instant display.
    
    Args:
        force: If True, re-run analysis even for cached tickers
        
    Returns:
        Summary of analyzed/cached/failed tickers
    """
    import asyncio
    
    try:
        user_id = user.id if user else ANONYMOUS_USER_ID
        
        # Get portfolio holdings
        try:
            from trading.user_trading_service import UserTradingService
            holdings = await UserTradingService.get_portfolio_holdings(db, user_id)
            tickers = [h.get("ticker") for h in holdings if h.get("ticker")]
        except Exception as e:
            logger.warning(f"Failed to get portfolio holdings: {e}")
            tickers = []
        
        if not tickers:
            return {
                "success": True,
                "data": {
                    "message": "No portfolio holdings to analyze",
                    "requested": 0,
                    "already_cached": 0,
                    "analyzed": 0,
                    "failed": 0,
                }
            }
        
        logger.info(f"Warming cache for {len(tickers)} portfolio holdings: {tickers}")
        
        # Run cache warming in background task (don't block response)
        # But for now, run synchronously so user gets feedback
        result = await warm_cache_for_tickers(tickers, force=force)
        
        return {
            "success": True,
            "data": result,
        }
        
    except Exception as e:
        logger.error(f"Cache warming failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== Combined Risk Overview ==========

@risk_router.get("/overview")
async def get_risk_overview(
    user=Depends(get_required_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Get comprehensive risk overview for the user.
    
    Combines:
    - User's risk settings
    - Current VIX and regime
    - Portfolio VaR
    - Position limit status
    """
    try:
        user_id = user.id if user else ANONYMOUS_USER_ID
        
        # Get risk settings
        settings = await RiskSettingsService.get_settings(db, user_id)
        
        # Get VIX
        try:
            vix_data = await fetch_vix(use_cache=True)
            vix_info = vix_data.to_dict()
        except Exception:
            vix_info = {"vix": None, "regime": "unknown"}
        
        # Get thresholds
        thresholds = get_adjusted_thresholds(settings=settings)
        
        # Get portfolio risk
        try:
            from trading.user_trading_service import UserTradingService
            holdings = await UserTradingService.get_portfolio_holdings(db, user_id)
            positions = [
                {
                    "ticker": h.get("ticker"),
                    "quantity": h.get("quantity", h.get("shares", 0)),
                    "current_price": h.get("current_price", 0),
                    "market_value": h.get("market_value", 0),
                }
                for h in holdings
            ] if holdings else []
            portfolio_var = calculate_portfolio_var(positions) if positions else None
        except Exception as e:
            logger.warning(f"Failed to calculate portfolio VaR: {e}")
            portfolio_var = None
        
        return {
            "success": True,
            "data": {
                "risk_settings": settings.to_dict(),
                "vix": vix_info,
                "thresholds": thresholds.to_dict(),
                "portfolio_var": portfolio_var.to_dict() if portfolio_var else None,
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
