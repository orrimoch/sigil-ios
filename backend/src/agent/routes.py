"""
Agent API Routes (REC-279, REC-291)

API endpoints for the trading agent:
- GET /api/v1/agent/context - Aggregated trading context
- GET /api/v1/agent/context/{ticker} - Context for specific ticker
- GET /api/v1/agent/status - Agent status (Phase 3)
- POST /api/v1/agent/pause - Pause agent (Phase 3)
- POST /api/v1/agent/resume - Resume agent (Phase 3)
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from loguru import logger

from .context import ContextAggregator, TradingContext

router = APIRouter(prefix="/api/v1/agent", tags=["agent"])


@router.get("/context")
async def get_trading_context(
    top_n: int = Query(default=20, ge=1, le=50, description="Number of top BUY candidates"),
    include_hold_review: bool = Query(default=True, description="Include holdings with declining scores"),
):
    """
    Get aggregated trading context for agent decision-making.
    
    Returns:
    - Portfolio state (cash, positions, sector exposure)
    - Market state (regime, VIX)
    - Top BUY candidates (not owned)
    - SELL candidates (owned with SELL signal)
    - Data freshness status
    """
    try:
        aggregator = ContextAggregator()
        context = await aggregator.aggregate(
            top_n_candidates=top_n,
            include_hold_review=include_hold_review,
        )
        
        return context.to_dict()
    
    except Exception as e:
        logger.error(f"Failed to aggregate context: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/context/{ticker}")
async def get_ticker_context(ticker: str):
    """
    Get detailed context for a specific ticker.
    
    Useful for debugging or single-stock analysis.
    """
    try:
        aggregator = ContextAggregator()
        context = await aggregator.aggregate_for_ticker(ticker)
        
        if "error" in context:
            raise HTTPException(status_code=404, detail=context["error"])
        
        return context
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get context for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def agent_health():
    """
    Check agent health and data freshness.
    
    Returns whether the agent can safely trade based on data freshness.
    """
    try:
        aggregator = ContextAggregator()
        context = await aggregator.aggregate(top_n_candidates=1)
        
        return {
            "healthy": not context.data_freshness.is_stale,
            "can_trade": not context.data_freshness.is_stale,
            "freshness": {
                "scores_age_hours": context.data_freshness.scores_age_hours,
                "regime_age_hours": context.data_freshness.regime_age_hours,
                "is_stale": context.data_freshness.is_stale,
                "stale_reasons": context.data_freshness.stale_reasons,
            },
            "market": {
                "regime": context.market.regime,
                "vix": context.market.vix,
            }
        }
    
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "healthy": False,
            "can_trade": False,
            "error": str(e),
        }


# Phase 3 endpoints (stubs for now)

@router.get("/status")
async def get_agent_status():
    """Get agent status (Phase 3)."""
    return {
        "status": "not_implemented",
        "message": "Agent status endpoint - Phase 3",
        "active": False,
        "mode": "manual",
        "pending_count": 0,
    }


@router.post("/pause")
async def pause_agent():
    """Pause the agent (Phase 3)."""
    return {
        "status": "not_implemented",
        "message": "Agent pause endpoint - Phase 3",
    }


@router.post("/resume")
async def resume_agent():
    """Resume the agent (Phase 3)."""
    return {
        "status": "not_implemented",
        "message": "Agent resume endpoint - Phase 3",
    }
