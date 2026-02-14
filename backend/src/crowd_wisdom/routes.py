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
    create_mock_sentiment
)
from .free_reddit_fetcher import FreeRedditFetcher, fetch_reddit_trending
from .fundamentals_fetcher import fetch_fundamentals_batch

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
    Manually trigger a data refresh using REAL Reddit data.
    
    Fetches live data from:
    1. ApeWisdom API (trending tickers + mentions)
    2. Reddit JSON API (sentiment analysis)
    
    No API keys required - all sources are free and public.
    """
    try:
        await models.init_db()
        
        # Fetch REAL data from free Reddit APIs
        fetcher = FreeRedditFetcher()
        try:
            trending = await fetcher.fetch_trending_tickers(limit=50, enrich_sentiment=True)
            logger.info(f"Refreshed: fetched {len(trending)} tickers from Reddit APIs")
        finally:
            await fetcher.close()
        
        if not trending:
            raise HTTPException(status_code=503, detail="Reddit APIs unavailable")
        
        # Convert to aggregated format
        aggregated_mentions = {}
        sentiment_data = {}
        
        for ticker_data in trending:
            ticker = ticker_data.ticker
            aggregated_mentions[ticker] = {
                "ticker": ticker,
                "mention_count": ticker_data.mentions,
                "total_upvotes": ticker_data.upvotes,
                "total_comments": 0,
                "unique_posts": ticker_data.mentions // 3,
                "subreddits": ["wallstreetbets", "stocks", "investing"],
                "trending_velocity": ticker_data.trending_velocity
            }
            sentiment_data[ticker] = ticker_data.sentiment_score
        
        # Fetch REAL fundamentals from Yahoo Finance
        ticker_list = list(aggregated_mentions.keys())
        real_fundamentals = fetch_fundamentals_batch(ticker_list, max_workers=5)
        logger.info(f"Refresh: fetched real fundamentals for {len(real_fundamentals)}/{len(ticker_list)} tickers")
        
        # Calculate scores with real fundamentals filtering
        scorer = RedditScorer()
        scorer.set_fundamentals(real_fundamentals)
        scores = scorer.score_tickers(aggregated_mentions, sentiment_data)
        
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
            mentions_fetched=len(aggregated_mentions),
            scores_calculated=len(scores),
            top_picks_saved=len(top_pick_dicts)
        )
        
    except HTTPException:
        raise
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
    """Generate top picks live using real Reddit data from free APIs."""
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
    """
    Generate viral scores live using REAL Reddit data from free APIs.
    
    Data sources (no API keys needed):
    - ApeWisdom: Pre-aggregated trending tickers
    - Reddit JSON: Real-time posts for sentiment
    """
    try:
        # Fetch real data from ApeWisdom + Reddit JSON APIs
        fetcher = FreeRedditFetcher()
        try:
            trending = await fetcher.fetch_trending_tickers(limit=50, enrich_sentiment=True)
            logger.info(f"Fetched {len(trending)} trending tickers from Reddit APIs")
        finally:
            await fetcher.close()
        
        if not trending:
            logger.warning("No Reddit data available, using minimal fallback")
            return []
        
        # Convert to aggregated format for scorer
        aggregated_mentions = {}
        sentiment_data = {}
        
        for ticker_data in trending:
            ticker = ticker_data.ticker
            aggregated_mentions[ticker] = {
                "ticker": ticker,
                "mention_count": ticker_data.mentions,
                "total_upvotes": ticker_data.upvotes,
                "total_comments": 0,  # Not available from ApeWisdom
                "unique_posts": ticker_data.mentions // 3,  # Estimate
                "subreddits": ["wallstreetbets", "stocks", "investing"],
                "trending_velocity": ticker_data.trending_velocity
            }
            sentiment_data[ticker] = ticker_data.sentiment_score
        
        # Fetch REAL fundamentals from Yahoo Finance
        ticker_list = list(aggregated_mentions.keys())
        real_fundamentals = fetch_fundamentals_batch(ticker_list, max_workers=5)
        logger.info(f"Fetched real fundamentals for {len(real_fundamentals)}/{len(ticker_list)} tickers")
        
        # Score tickers
        scorer = RedditScorer()
        scorer.set_fundamentals(real_fundamentals)
        scores = scorer.score_tickers(aggregated_mentions, sentiment_data)
        
        if passes_filters_only:
            scores = [s for s in scores if s.passes_filters]
        
        week_start = _get_current_week_start()
        
        return [
            {**score_to_dict(s), 'week_start': week_start}
            for s in scores
        ]
        
    except Exception as e:
        logger.error(f"Failed to fetch live Reddit data: {e}")
        # Return empty list on error (graceful degradation)
        return []


# --- REC-264: Stock Discovery Endpoints ---

class DiscoveryCandidateResponse(BaseModel):
    """Stock discovered outside universe."""
    ticker: str
    company_name: str
    sector: str
    current_price: float
    market_cap: float
    viral_score: float
    mention_count: int
    total_upvotes: int
    sentiment_label: str
    discovered_at: str
    passes_filters: bool
    filter_reasons: list


class DiscoveryResponse(BaseModel):
    """Discovery candidates response."""
    success: bool
    count: int
    quarterly_additions: int
    max_quarterly: int
    candidates: List[DiscoveryCandidateResponse]


@router.get("/discovery", response_model=DiscoveryResponse)
async def get_discovery_candidates():
    """
    REC-264: Get stock discovery candidates.
    
    Returns stocks trending on Reddit that are not in our universe
    but meet quality criteria (Tech sector, price < $30, market cap $500M-$50B).
    """
    try:
        from .stock_discovery import load_discovery_candidates, DISCOVERY_FILTERS, get_quarterly_additions
        
        candidates = load_discovery_candidates()
        
        return {
            "success": True,
            "count": len(candidates),
            "quarterly_additions": get_quarterly_additions(),
            "max_quarterly": DISCOVERY_FILTERS["max_quarterly_additions"],
            "candidates": candidates,
        }
    except Exception as e:
        logger.error(f"Failed to load discovery candidates: {e}")
        return {
            "success": False,
            "count": 0,
            "quarterly_additions": 0,
            "max_quarterly": 10,
            "candidates": [],
        }


@router.post("/discovery/refresh")
async def refresh_discovery_candidates():
    """
    REC-264: Refresh stock discovery candidates.
    
    Fetches current Reddit trending data and identifies new discovery candidates.
    """
    try:
        from .stock_discovery import discover_stocks, save_discovery_candidates
        
        # Fetch trending data
        fetcher = FreeRedditFetcher()
        try:
            trending = await fetcher.fetch_trending_tickers(limit=100, enrich_sentiment=True)
        finally:
            await fetcher.close()
        
        if not trending:
            return {"success": False, "message": "No trending data available"}
        
        # Convert to expected format
        class TrendingData:
            def __init__(self, data):
                self.ticker = data.ticker
                self.viral_score = data.mentions * 2 + data.upvotes / 100  # Rough score
                self.mention_count = data.mentions
                self.total_upvotes = data.upvotes
                self.sentiment_label = (
                    "VERY_BULLISH" if data.sentiment_score > 0.5 else
                    "BULLISH" if data.sentiment_score > 0.2 else
                    "NEUTRAL" if data.sentiment_score > -0.2 else
                    "BEARISH" if data.sentiment_score > -0.5 else
                    "VERY_BEARISH"
                )
        
        trending_data = [TrendingData(t) for t in trending]
        
        # Discover and save
        candidates = await discover_stocks(trending_data)
        save_discovery_candidates(candidates)
        
        return {
            "success": True,
            "message": f"Found {len(candidates)} discovery candidates",
            "count": len(candidates),
        }
    except Exception as e:
        logger.error(f"Failed to refresh discovery candidates: {e}")
        raise HTTPException(status_code=500, detail=str(e))
