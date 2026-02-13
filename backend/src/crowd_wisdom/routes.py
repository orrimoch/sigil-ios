"""
REC-266: Crowd Wisdom API Endpoints (Reddit-based)

Endpoints:
- GET /api/v1/crowd-wisdom/top-picks - Weekly top 5 trending stocks
- GET /api/v1/crowd-wisdom/trending - All trending tickers (unfiltered)
- GET /api/v1/crowd-wisdom/scores/{ticker} - Score for specific ticker
- POST /api/v1/crowd-wisdom/refresh - Manually trigger data refresh
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from datetime import date, timedelta
from pydantic import BaseModel
import logging

from . import models
from .reddit_scorer import (
    RedditScorer,
    score_to_dict,
    get_weekly_top_picks,
    create_mock_fundamentals,
    create_mock_aggregated_mentions,
    create_mock_sentiment
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/crowd-wisdom", tags=["crowd-wisdom"])


# --- Response Models ---

class TrendingPickResponse(BaseModel):
    """Single trending stock pick (Reddit-based)."""
    rank: int
    ticker: str
    company_name: str
    viral_score: float
    mention_count: int
    total_upvotes: int
    sentiment_label: str
    trending_velocity: float
    current_price: Optional[float] = None
    signal: str = "TRENDING"


class TopPicksResponse(BaseModel):
    """Weekly top 5 trending picks response."""
    success: bool
    week_start: str
    picks: List[TrendingPickResponse]


class TrendingTickerResponse(BaseModel):
    """Trending ticker with full viral score data."""
    ticker: str
    company_name: str
    viral_score: float
    mention_count: int
    total_upvotes: int
    total_comments: int
    unique_posts: int
    subreddits: List[str]
    avg_sentiment: Optional[float]
    sentiment_label: str
    trending_velocity: float
    current_price: Optional[float]
    revenue_ttm: Optional[float]
    eps_latest: Optional[float]
    passes_filters: bool
    filter_reason: Optional[str]
    signal: str


class TrendingListResponse(BaseModel):
    """List of all trending tickers."""
    success: bool
    count: int
    week_start: str
    tickers: List[TrendingTickerResponse]


class TickerScoreResponse(BaseModel):
    """Viral score for a specific ticker."""
    success: bool
    ticker: str
    company_name: str
    viral_score: float
    mention_count: int
    total_upvotes: int
    total_comments: int
    subreddits: List[str]
    sentiment_label: str
    trending_velocity: float
    passes_filters: bool
    filter_reason: Optional[str]
    signal: str
    week_start: str


class RefreshResponse(BaseModel):
    """Response from manual refresh."""
    success: bool
    mentions_fetched: int
    scores_calculated: int
    top_picks_saved: int


# --- Endpoints ---

@router.get("/top-picks", response_model=TopPicksResponse)
async def get_top_picks(week: Optional[str] = None):
    """
    Get weekly top 5 trending Reddit picks.
    
    Args:
        week: Optional week start date (ISO format). Defaults to current week.
    
    Returns:
        Top 5 stocks with highest viral scores that pass quality filters.
    """
    try:
        # Initialize DB if needed
        await models.init_db()
        
        picks = await models.get_top_picks(week)
        
        if not picks:
            # No picks stored - generate live using mock data
            picks = await _generate_live_picks()
        
        # Determine week_start
        if picks:
            week_start = picks[0].get('week_start', _get_current_week_start())
        else:
            week_start = _get_current_week_start()
        
        return TopPicksResponse(
            success=True,
            week_start=week_start,
            picks=[
                TrendingPickResponse(
                    rank=p.get('rank', i+1),
                    ticker=p['ticker'],
                    company_name=p.get('company_name', ''),
                    viral_score=p.get('viral_score', 0),
                    mention_count=p.get('mention_count', 0),
                    total_upvotes=p.get('total_upvotes', 0),
                    sentiment_label=p.get('sentiment_label', 'NEUTRAL'),
                    trending_velocity=p.get('trending_velocity', 1.0),
                    current_price=p.get('current_price'),
                    signal=p.get('signal', 'TRENDING')
                )
                for i, p in enumerate(picks[:5])
            ]
        )
    except Exception as e:
        logger.error(f"Failed to get top picks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trending", response_model=TrendingListResponse)
async def get_trending_tickers(
    week: Optional[str] = None,
    limit: int = Query(default=50, le=100),
    filtered: bool = Query(default=False, description="Only return stocks that pass quality filters")
):
    """
    Get all trending tickers with viral scores.
    
    Args:
        week: Optional week start date
        limit: Maximum results (default 50, max 100)
        filtered: If true, only return stocks passing quality filters
    
    Returns:
        List of all trending tickers sorted by viral score.
    """
    try:
        await models.init_db()
        
        scores = await models.get_viral_scores(
            week_start=week,
            passes_filters_only=filtered,
            limit=limit
        )
        
        if not scores:
            # No scores stored - generate live
            scores = await _generate_live_scores(passes_filters_only=filtered)
        
        week_start = scores[0].get('week_start', _get_current_week_start()) if scores else _get_current_week_start()
        
        return TrendingListResponse(
            success=True,
            count=len(scores),
            week_start=week_start,
            tickers=[
                TrendingTickerResponse(
                    ticker=s['ticker'],
                    company_name=s.get('company_name', ''),
                    viral_score=s.get('viral_score', 0),
                    mention_count=s.get('mention_count', 0),
                    total_upvotes=s.get('total_upvotes', 0),
                    total_comments=s.get('total_comments', 0),
                    unique_posts=s.get('unique_posts', 0),
                    subreddits=s.get('subreddits', []),
                    avg_sentiment=s.get('avg_sentiment'),
                    sentiment_label=s.get('sentiment_label', 'NEUTRAL'),
                    trending_velocity=s.get('trending_velocity', 1.0),
                    current_price=s.get('current_price'),
                    revenue_ttm=s.get('revenue_ttm'),
                    eps_latest=s.get('eps_latest'),
                    passes_filters=bool(s.get('passes_filters')),
                    filter_reason=s.get('filter_reason'),
                    signal=s.get('signal', 'NEUTRAL')
                )
                for s in scores
            ]
        )
    except Exception as e:
        logger.error(f"Failed to get trending tickers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scores/{ticker}", response_model=TickerScoreResponse)
async def get_ticker_score(ticker: str, week: Optional[str] = None):
    """
    Get viral score for a specific stock.
    
    Args:
        ticker: Stock ticker symbol
        week: Optional week start date
    
    Returns:
        Viral score details for the ticker.
    """
    try:
        await models.init_db()
        
        score = await models.get_viral_score_by_ticker(ticker.upper(), week)
        
        if not score:
            # Try generating live
            scores = await _generate_live_scores()
            score = next((s for s in scores if s['ticker'].upper() == ticker.upper()), None)
        
        if not score:
            raise HTTPException(status_code=404, detail=f"No viral score data for {ticker}")
        
        week_start = score.get('week_start', _get_current_week_start())
        
        return TickerScoreResponse(
            success=True,
            ticker=score['ticker'],
            company_name=score.get('company_name', ''),
            viral_score=score.get('viral_score', 0),
            mention_count=score.get('mention_count', 0),
            total_upvotes=score.get('total_upvotes', 0),
            total_comments=score.get('total_comments', 0),
            subreddits=score.get('subreddits', []),
            sentiment_label=score.get('sentiment_label', 'NEUTRAL'),
            trending_velocity=score.get('trending_velocity', 1.0),
            passes_filters=bool(score.get('passes_filters')),
            filter_reason=score.get('filter_reason'),
            signal=score.get('signal', 'NEUTRAL'),
            week_start=week_start
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get score for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/refresh", response_model=RefreshResponse)
async def refresh_data():
    """
    Manually trigger a data refresh.
    
    For now, uses mock data. In production, this would:
    1. Fetch mentions from Reddit using PRAW
    2. Calculate viral scores with fundamentals filtering
    3. Save top picks for the week
    """
    try:
        await models.init_db()
        
        # For now, use mock data
        # In production: fetcher = RedditFetcher(); mentions = fetcher.fetch_mentions()
        mock_mentions = create_mock_aggregated_mentions()
        mock_fundamentals = create_mock_fundamentals()
        mock_sentiment = create_mock_sentiment()
        
        # Calculate scores
        scorer = RedditScorer()
        scorer.set_fundamentals(mock_fundamentals)
        scores = scorer.score_tickers(mock_mentions, mock_sentiment)
        
        # Convert to dicts
        score_dicts = [score_to_dict(s) for s in scores]
        
        week_start = _get_current_week_start()
        
        # Save scores
        await models.save_viral_scores(score_dicts, week_start)
        
        # Get top picks (passing filters)
        top_picks = get_weekly_top_picks(scores, max_picks=5)
        top_pick_dicts = [score_to_dict(s) for s in top_picks]
        
        # Save top picks
        await models.save_top_picks(top_pick_dicts, week_start)
        
        return RefreshResponse(
            success=True,
            mentions_fetched=len(mock_mentions),
            scores_calculated=len(scores),
            top_picks_saved=len(top_pick_dicts)
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


async def _generate_live_picks() -> List[dict]:
    """Generate top picks live using mock data."""
    scores = await _generate_live_scores(passes_filters_only=True)
    
    week_start = _get_current_week_start()
    
    return [
        {
            'rank': i + 1,
            'ticker': s['ticker'],
            'company_name': s.get('company_name', ''),
            'viral_score': s['viral_score'],
            'mention_count': s.get('mention_count', 0),
            'total_upvotes': s.get('total_upvotes', 0),
            'sentiment_label': s.get('sentiment_label', 'NEUTRAL'),
            'trending_velocity': s.get('trending_velocity', 1.0),
            'current_price': s.get('current_price'),
            'signal': s.get('signal', 'TRENDING'),
            'week_start': week_start
        }
        for i, s in enumerate(scores[:5])
    ]


async def _generate_live_scores(passes_filters_only: bool = False) -> List[dict]:
    """Generate viral scores live using mock data."""
    mock_mentions = create_mock_aggregated_mentions()
    mock_fundamentals = create_mock_fundamentals()
    mock_sentiment = create_mock_sentiment()
    
    scorer = RedditScorer()
    scorer.set_fundamentals(mock_fundamentals)
    scores = scorer.score_tickers(mock_mentions, mock_sentiment)
    
    if passes_filters_only:
        scores = [s for s in scores if s.passes_filters]
    
    week_start = _get_current_week_start()
    
    return [
        {**score_to_dict(s), 'week_start': week_start}
        for s in scores
    ]
