"""
REC-254: Crowd Wisdom API Endpoints

Endpoints:
- GET /api/v1/crowd-wisdom/top-picks - Weekly top 5 smart money picks
- GET /api/v1/crowd-wisdom/scores - All crowd wisdom scores
- GET /api/v1/crowd-wisdom/scores/{ticker} - Score for specific ticker
- POST /api/v1/crowd-wisdom/refresh - Manually trigger data refresh
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from datetime import date, datetime, timedelta
from pydantic import BaseModel
import asyncio
import logging

from .insider_fetcher import InsiderFetcher
from .insider_scorer import InsiderScorer, calculate_weekly_scores
from . import models

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/crowd-wisdom", tags=["crowd-wisdom"])


# --- Response Models ---

class InsiderEvent(BaseModel):
    """Notable insider event."""
    event: str


class TopPickResponse(BaseModel):
    """Single top pick stock."""
    rank: int
    ticker: str
    company_name: str
    insider_score: float
    insider_buy_count: int
    insider_buy_value: float
    notable_events: List[str]
    current_price: Optional[float] = None
    signal: str = "STRONG_BUY"


class TopPicksResponse(BaseModel):
    """Weekly top 5 picks response."""
    success: bool
    week_start: str
    picks: List[TopPickResponse]


class CrowdWisdomScoreResponse(BaseModel):
    """Crowd wisdom score for a stock."""
    ticker: str
    company_name: str
    sector: str
    current_price: Optional[float]
    insider_score: float
    insider_buy_count: int
    insider_buy_value: float
    insider_cluster: bool
    executive_buys: int
    notable_events: List[str]
    discovery_reason: str
    signal: str


class ScoresListResponse(BaseModel):
    """List of all crowd wisdom scores."""
    success: bool
    count: int
    week_start: str
    scores: List[CrowdWisdomScoreResponse]


class RefreshResponse(BaseModel):
    """Response from manual refresh."""
    success: bool
    transactions_fetched: int
    scores_calculated: int
    top_picks_saved: int


# --- Endpoints ---

@router.get("/top-picks", response_model=TopPicksResponse)
async def get_top_picks(week: Optional[str] = None):
    """
    Get weekly top 5 smart money picks.
    
    Args:
        week: Optional week start date (ISO format). Defaults to current week.
    
    Returns:
        Top 5 stocks with strongest insider buying signals.
    """
    try:
        # Initialize DB if needed
        await models.init_db()
        
        picks = await models.get_top_picks(week)
        
        if not picks:
            # No picks stored - run a live fetch
            picks = await _fetch_live_top_picks()
        
        # Determine week_start
        if picks:
            week_start = picks[0].get('week_start', _get_current_week_start())
        else:
            week_start = _get_current_week_start()
        
        return TopPicksResponse(
            success=True,
            week_start=week_start,
            picks=[
                TopPickResponse(
                    rank=p.get('rank', i+1),
                    ticker=p['ticker'],
                    company_name=p.get('company_name', ''),
                    insider_score=p.get('insider_score', 0),
                    insider_buy_count=p.get('insider_buy_count', 0),
                    insider_buy_value=p.get('insider_buy_value', 0),
                    notable_events=p.get('notable_events', []),
                    current_price=p.get('current_price'),
                    signal=p.get('signal', 'STRONG_BUY')
                )
                for i, p in enumerate(picks[:5])
            ]
        )
    except Exception as e:
        logger.error(f"Failed to get top picks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scores", response_model=ScoresListResponse)
async def get_all_scores(week: Optional[str] = None, limit: int = 50):
    """
    Get all crowd wisdom scores.
    
    Args:
        week: Optional week start date
        limit: Maximum results (default 50)
    
    Returns:
        List of all scored stocks sorted by insider_score.
    """
    try:
        await models.init_db()
        
        scores = await models.get_all_scores(week)
        
        if not scores:
            # No scores stored - calculate live
            scores = await _calculate_live_scores()
        
        week_start = scores[0].get('week_start', _get_current_week_start()) if scores else _get_current_week_start()
        
        return ScoresListResponse(
            success=True,
            count=len(scores[:limit]),
            week_start=week_start,
            scores=[
                CrowdWisdomScoreResponse(
                    ticker=s['ticker'],
                    company_name=s.get('company_name', ''),
                    sector=s.get('sector', 'Technology'),
                    current_price=s.get('current_price'),
                    insider_score=s.get('insider_score', 0),
                    insider_buy_count=s.get('insider_buy_count', 0),
                    insider_buy_value=s.get('insider_buy_value', 0),
                    insider_cluster=bool(s.get('insider_cluster')),
                    executive_buys=s.get('executive_buys', 0),
                    notable_events=s.get('notable_events', []),
                    discovery_reason=s.get('discovery_reason', ''),
                    signal=s.get('signal', 'NEUTRAL')
                )
                for s in scores[:limit]
            ]
        )
    except Exception as e:
        logger.error(f"Failed to get scores: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scores/{ticker}", response_model=CrowdWisdomScoreResponse)
async def get_score_by_ticker(ticker: str):
    """
    Get crowd wisdom score for a specific stock.
    
    Args:
        ticker: Stock ticker symbol
    
    Returns:
        Crowd wisdom score details.
    """
    try:
        await models.init_db()
        
        scores = await models.get_all_scores()
        
        # Find the ticker
        ticker_upper = ticker.upper()
        for s in scores:
            if s['ticker'].upper() == ticker_upper:
                return CrowdWisdomScoreResponse(
                    ticker=s['ticker'],
                    company_name=s.get('company_name', ''),
                    sector=s.get('sector', 'Technology'),
                    current_price=s.get('current_price'),
                    insider_score=s.get('insider_score', 0),
                    insider_buy_count=s.get('insider_buy_count', 0),
                    insider_buy_value=s.get('insider_buy_value', 0),
                    insider_cluster=bool(s.get('insider_cluster')),
                    executive_buys=s.get('executive_buys', 0),
                    notable_events=s.get('notable_events', []),
                    discovery_reason=s.get('discovery_reason', ''),
                    signal=s.get('signal', 'NEUTRAL')
                )
        
        raise HTTPException(status_code=404, detail=f"No crowd wisdom data for {ticker}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get score for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/refresh", response_model=RefreshResponse)
async def refresh_data():
    """
    Manually trigger a data refresh.
    Fetches latest insider data, calculates scores, saves top picks.
    """
    try:
        await models.init_db()
        
        # Fetch transactions
        fetcher = InsiderFetcher(max_price=30, days_back=7)
        transactions = fetcher.fetch_insider_buys(tech_only=False)
        
        # Convert to dicts for storage
        txn_dicts = [
            {
                'ticker': t.ticker,
                'company_name': t.company_name,
                'insider_name': t.insider_name,
                'insider_title': t.insider_title,
                'trade_type': t.trade_type,
                'price': t.price,
                'quantity': t.quantity,
                'shares_owned': t.shares_owned,
                'ownership_change_pct': t.ownership_change_pct,
                'value': t.value,
                'trade_date': t.trade_date.isoformat(),
                'filing_date': t.filing_date.isoformat()
            }
            for t in transactions
        ]
        
        # Save transactions
        await models.save_transactions(txn_dicts)
        
        # Calculate scores
        scores = calculate_weekly_scores(transactions)
        week_start = _get_current_week_start()
        
        # Save scores
        await models.save_weekly_scores(scores, week_start)
        
        # Save top 5 picks
        await models.save_top_picks(scores[:5], week_start)
        
        return RefreshResponse(
            success=True,
            transactions_fetched=len(transactions),
            scores_calculated=len(scores),
            top_picks_saved=min(5, len(scores))
        )
        
    except Exception as e:
        logger.error(f"Failed to refresh data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- Helper Functions ---

def _get_current_week_start() -> str:
    """Get Monday of current week as ISO string."""
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    return monday.isoformat()


async def _fetch_live_top_picks() -> List[dict]:
    """Fetch and calculate top picks live (no DB)."""
    fetcher = InsiderFetcher(max_price=30, days_back=7)
    transactions = fetcher.fetch_insider_buys(tech_only=False)
    
    if not transactions:
        return []
    
    scorer = InsiderScorer()
    scores = scorer.score_transactions(transactions)
    
    week_start = _get_current_week_start()
    
    return [
        {
            'rank': i + 1,
            'ticker': s.ticker,
            'company_name': s.company_name,
            'insider_score': s.insider_score,
            'insider_buy_count': s.insider_buy_count,
            'insider_buy_value': s.insider_buy_value,
            'notable_events': s.notable_events,
            'signal': s.signal,
            'week_start': week_start
        }
        for i, s in enumerate(scores[:5])
    ]


async def _calculate_live_scores() -> List[dict]:
    """Calculate scores live (no DB)."""
    fetcher = InsiderFetcher(max_price=30, days_back=7)
    transactions = fetcher.fetch_insider_buys(tech_only=False)
    
    if not transactions:
        return []
    
    scores = calculate_weekly_scores(transactions)
    week_start = _get_current_week_start()
    
    for s in scores:
        s['week_start'] = week_start
    
    return scores
