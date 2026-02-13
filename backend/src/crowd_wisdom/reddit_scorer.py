"""
REC-266: Reddit Viral Stock Scorer

Calculates viral_score for each ticker based on:
- 30% mention count
- 20% upvote weighted score
- 20% sentiment score
- 15% trending velocity
- 15% fundamentals bonus

Applies quality filters:
- Substantial revenue (real business)
- Strong recent earnings (positive EPS or improving)
"""

import logging
from typing import List, Dict, Optional, Any
from datetime import datetime, date, timedelta
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# Scoring weights (from spec)
WEIGHT_MENTIONS = 0.30
WEIGHT_UPVOTES = 0.20
WEIGHT_SENTIMENT = 0.20
WEIGHT_VELOCITY = 0.15
WEIGHT_FUNDAMENTALS = 0.15

# Quality filter thresholds
MIN_REVENUE_TTM = 50_000_000  # $50M minimum annual revenue
MIN_EPS_OR_IMPROVING = True  # Must have positive EPS or improving trend

# Minimum mentions to be considered trending
MIN_MENTIONS_THRESHOLD = 5


@dataclass
class TickerFundamentals:
    """Fundamental data for quality filtering."""
    ticker: str
    company_name: str
    current_price: Optional[float] = None
    revenue_ttm: Optional[float] = None
    eps_latest: Optional[float] = None
    eps_prev_quarter: Optional[float] = None
    earnings_growth: Optional[float] = None  # YoY EPS growth %


@dataclass
class RedditScore:
    """Calculated viral score for a ticker."""
    ticker: str
    company_name: str
    viral_score: float  # 0-100
    
    # Reddit metrics
    mention_count: int
    total_upvotes: int
    total_comments: int
    unique_posts: int
    subreddits: List[str]
    
    # Sentiment
    avg_sentiment: Optional[float]  # -1.0 to 1.0
    sentiment_label: str  # VERY_BULLISH, BULLISH, NEUTRAL, BEARISH, VERY_BEARISH
    
    # Velocity
    trending_velocity: float  # mentions_recent / mentions_earlier
    
    # Fundamentals
    current_price: Optional[float]
    revenue_ttm: Optional[float]
    eps_latest: Optional[float]
    earnings_growth: Optional[float]
    
    # Filter status
    passes_filters: bool
    filter_reason: Optional[str]
    
    # Signal
    signal: str  # VERY_HOT, HOT, TRENDING, NEUTRAL


class RedditScorer:
    """
    Calculates viral scores for Reddit-mentioned stocks.
    
    Usage:
        scorer = RedditScorer()
        # Load fundamentals from your data source
        scorer.set_fundamentals(fundamentals_data)
        scores = scorer.score_tickers(aggregated_mentions)
    """
    
    def __init__(
        self,
        min_revenue: float = MIN_REVENUE_TTM,
        min_mentions: int = MIN_MENTIONS_THRESHOLD
    ):
        """
        Initialize scorer.
        
        Args:
            min_revenue: Minimum TTM revenue to pass quality filter
            min_mentions: Minimum mentions to be considered trending
        """
        self.min_revenue = min_revenue
        self.min_mentions = min_mentions
        self._fundamentals: Dict[str, TickerFundamentals] = {}
    
    def set_fundamentals(self, fundamentals: Dict[str, TickerFundamentals]):
        """Set fundamentals data for quality filtering."""
        self._fundamentals = {k.upper(): v for k, v in fundamentals.items()}
        logger.info(f"Loaded fundamentals for {len(self._fundamentals)} tickers")
    
    def score_tickers(
        self,
        aggregated_mentions: Dict[str, Dict],
        sentiment_data: Optional[Dict[str, float]] = None
    ) -> List[RedditScore]:
        """
        Calculate viral scores for all tickers.
        
        Args:
            aggregated_mentions: Dict from RedditFetcher.aggregate_by_ticker()
            sentiment_data: Optional dict mapping ticker -> sentiment score (-1 to 1)
            
        Returns:
            List of RedditScore objects sorted by viral_score descending
        """
        if not aggregated_mentions:
            return []
        
        # Find max values for normalization
        max_mentions = max(d["mention_count"] for d in aggregated_mentions.values())
        max_upvotes = max(d["total_upvotes"] for d in aggregated_mentions.values())
        
        scores = []
        for ticker, data in aggregated_mentions.items():
            try:
                score = self._calculate_score(
                    ticker=ticker,
                    data=data,
                    max_mentions=max_mentions,
                    max_upvotes=max_upvotes,
                    sentiment=sentiment_data.get(ticker) if sentiment_data else None
                )
                if score:
                    scores.append(score)
            except Exception as e:
                logger.error(f"Error scoring {ticker}: {e}")
                continue
        
        # Sort by viral_score descending
        scores.sort(key=lambda x: x.viral_score, reverse=True)
        return scores
    
    def _calculate_score(
        self,
        ticker: str,
        data: Dict,
        max_mentions: int,
        max_upvotes: int,
        sentiment: Optional[float] = None
    ) -> Optional[RedditScore]:
        """Calculate viral score for a single ticker."""
        mention_count = data.get("mention_count", 0)
        
        # Skip if below minimum mentions
        if mention_count < self.min_mentions:
            return None
        
        # Get fundamentals
        fundamentals = self._fundamentals.get(ticker.upper())
        
        # --- Calculate component scores (each 0-100) ---
        
        # 1. Mention score (normalized)
        mention_score = (mention_count / max_mentions) * 100 if max_mentions > 0 else 0
        
        # 2. Upvote score (normalized, with recency weighting could be added)
        total_upvotes = data.get("total_upvotes", 0)
        upvote_score = (total_upvotes / max_upvotes) * 100 if max_upvotes > 0 else 0
        
        # 3. Sentiment score (convert from -1,1 to 0-100)
        if sentiment is not None:
            sentiment_score = (sentiment + 1) * 50  # -1 -> 0, 0 -> 50, 1 -> 100
        else:
            sentiment_score = 50  # Neutral if no sentiment data
        
        # 4. Trending velocity
        # For now, use a simple heuristic based on data freshness
        # In a real implementation, compare to previous period
        velocity = data.get("trending_velocity", 1.0)
        velocity_score = min(velocity * 33.3, 100)  # 3x = 100
        
        # 5. Fundamentals bonus
        fundamentals_score = self._calculate_fundamentals_bonus(fundamentals)
        
        # --- Calculate weighted viral score ---
        viral_score = (
            mention_score * WEIGHT_MENTIONS +
            upvote_score * WEIGHT_UPVOTES +
            sentiment_score * WEIGHT_SENTIMENT +
            velocity_score * WEIGHT_VELOCITY +
            fundamentals_score * WEIGHT_FUNDAMENTALS
        )
        
        # --- Apply quality filters ---
        passes_filters, filter_reason = self._apply_quality_filters(fundamentals)
        
        # --- Determine signal ---
        signal = self._determine_signal(viral_score, passes_filters)
        
        # --- Determine sentiment label ---
        sentiment_label = self._sentiment_to_label(sentiment)
        
        return RedditScore(
            ticker=ticker,
            company_name=fundamentals.company_name if fundamentals else ticker,
            viral_score=round(viral_score, 2),
            mention_count=mention_count,
            total_upvotes=total_upvotes,
            total_comments=data.get("total_comments", 0),
            unique_posts=data.get("unique_posts", 0),
            subreddits=data.get("subreddits", []),
            avg_sentiment=sentiment,
            sentiment_label=sentiment_label,
            trending_velocity=velocity,
            current_price=fundamentals.current_price if fundamentals else None,
            revenue_ttm=fundamentals.revenue_ttm if fundamentals else None,
            eps_latest=fundamentals.eps_latest if fundamentals else None,
            earnings_growth=fundamentals.earnings_growth if fundamentals else None,
            passes_filters=passes_filters,
            filter_reason=filter_reason,
            signal=signal
        )
    
    def _calculate_fundamentals_bonus(
        self, fundamentals: Optional[TickerFundamentals]
    ) -> float:
        """
        Calculate fundamentals bonus score (0-100).
        
        Rewards:
        - Strong revenue
        - Positive/improving EPS
        - Earnings growth
        """
        if not fundamentals:
            return 25  # Base score for unknown fundamentals
        
        score = 0
        
        # Revenue score (0-40 points)
        if fundamentals.revenue_ttm:
            if fundamentals.revenue_ttm >= 10_000_000_000:  # $10B+
                score += 40
            elif fundamentals.revenue_ttm >= 1_000_000_000:  # $1B+
                score += 30
            elif fundamentals.revenue_ttm >= 100_000_000:  # $100M+
                score += 20
            elif fundamentals.revenue_ttm >= self.min_revenue:  # $50M+
                score += 10
        
        # EPS score (0-35 points)
        if fundamentals.eps_latest is not None:
            if fundamentals.eps_latest > 0:
                score += 25
                # Extra points for high EPS
                if fundamentals.eps_latest >= 1.0:
                    score += 10
            elif (fundamentals.eps_prev_quarter is not None and 
                  fundamentals.eps_latest > fundamentals.eps_prev_quarter):
                score += 15  # Improving trend
        
        # Earnings growth score (0-25 points)
        if fundamentals.earnings_growth:
            if fundamentals.earnings_growth > 50:
                score += 25
            elif fundamentals.earnings_growth > 25:
                score += 20
            elif fundamentals.earnings_growth > 10:
                score += 15
            elif fundamentals.earnings_growth > 0:
                score += 10
        
        return min(score, 100)
    
    def _apply_quality_filters(
        self, fundamentals: Optional[TickerFundamentals]
    ) -> tuple[bool, Optional[str]]:
        """
        Apply quality filters.
        
        Returns:
            (passes_filters, reason_if_fails)
        """
        if not fundamentals:
            return False, "No fundamental data available"
        
        # Filter 1: Substantial revenue
        if not fundamentals.revenue_ttm or fundamentals.revenue_ttm < self.min_revenue:
            revenue_str = f"${fundamentals.revenue_ttm/1e6:.1f}M" if fundamentals.revenue_ttm else "N/A"
            return False, f"Insufficient revenue: {revenue_str} < ${self.min_revenue/1e6:.0f}M minimum"
        
        # Filter 2: Strong earnings (positive EPS or improving)
        if fundamentals.eps_latest is None:
            return False, "No EPS data available"
        
        if fundamentals.eps_latest <= 0:
            # Check if improving
            if fundamentals.eps_prev_quarter is None or fundamentals.eps_latest <= fundamentals.eps_prev_quarter:
                return False, f"Negative EPS ({fundamentals.eps_latest:.2f}) without improvement trend"
        
        # All filters passed
        return True, None
    
    def _determine_signal(self, viral_score: float, passes_filters: bool) -> str:
        """Determine signal based on viral score and filter status."""
        if not passes_filters:
            return "NEUTRAL"  # Failed quality filters
        
        if viral_score >= 80:
            return "VERY_HOT"
        elif viral_score >= 60:
            return "HOT"
        elif viral_score >= 40:
            return "TRENDING"
        else:
            return "NEUTRAL"
    
    def _sentiment_to_label(self, sentiment: Optional[float]) -> str:
        """Convert sentiment score to label."""
        if sentiment is None:
            return "NEUTRAL"
        
        if sentiment >= 0.6:
            return "VERY_BULLISH"
        elif sentiment >= 0.2:
            return "BULLISH"
        elif sentiment >= -0.2:
            return "NEUTRAL"
        elif sentiment >= -0.6:
            return "BEARISH"
        else:
            return "VERY_BEARISH"


def get_weekly_top_picks(
    scores: List[RedditScore],
    max_picks: int = 5
) -> List[RedditScore]:
    """
    Get top N picks that pass all quality filters.
    
    Args:
        scores: List of RedditScore objects (already sorted by viral_score)
        max_picks: Maximum number of picks to return
        
    Returns:
        List of top picks that pass filters
    """
    filtered_scores = [s for s in scores if s.passes_filters]
    return filtered_scores[:max_picks]


def score_to_dict(score: RedditScore) -> Dict[str, Any]:
    """Convert RedditScore to dictionary for storage/API."""
    return {
        "ticker": score.ticker,
        "company_name": score.company_name,
        "viral_score": score.viral_score,
        "mention_count": score.mention_count,
        "total_upvotes": score.total_upvotes,
        "total_comments": score.total_comments,
        "unique_posts": score.unique_posts,
        "subreddits": score.subreddits,
        "avg_sentiment": score.avg_sentiment,
        "sentiment_label": score.sentiment_label,
        "trending_velocity": score.trending_velocity,
        "current_price": score.current_price,
        "revenue_ttm": score.revenue_ttm,
        "eps_latest": score.eps_latest,
        "earnings_growth": score.earnings_growth,
        "passes_filters": score.passes_filters,
        "filter_reason": score.filter_reason,
        "signal": score.signal
    }


# --- Mock data for development/testing ---

def create_mock_fundamentals() -> Dict[str, TickerFundamentals]:
    """Create mock fundamentals for testing."""
    return {
        "NVDA": TickerFundamentals(
            ticker="NVDA",
            company_name="NVIDIA Corporation",
            current_price=890.00,
            revenue_ttm=60_000_000_000,
            eps_latest=4.93,
            eps_prev_quarter=4.02,
            earnings_growth=265.0
        ),
        "AAPL": TickerFundamentals(
            ticker="AAPL",
            company_name="Apple Inc.",
            current_price=182.50,
            revenue_ttm=383_000_000_000,
            eps_latest=6.16,
            eps_prev_quarter=5.89,
            earnings_growth=2.0
        ),
        "MSFT": TickerFundamentals(
            ticker="MSFT",
            company_name="Microsoft Corporation",
            current_price=415.00,
            revenue_ttm=227_000_000_000,
            eps_latest=11.07,
            eps_prev_quarter=10.65,
            earnings_growth=22.0
        ),
        "AMD": TickerFundamentals(
            ticker="AMD",
            company_name="Advanced Micro Devices, Inc.",
            current_price=165.00,
            revenue_ttm=22_700_000_000,
            eps_latest=0.77,
            eps_prev_quarter=0.69,
            earnings_growth=50.0
        ),
        "PLTR": TickerFundamentals(
            ticker="PLTR",
            company_name="Palantir Technologies Inc.",
            current_price=22.50,
            revenue_ttm=2_200_000_000,
            eps_latest=0.09,
            eps_prev_quarter=0.07,
            earnings_growth=300.0
        ),
        "TSLA": TickerFundamentals(
            ticker="TSLA",
            company_name="Tesla, Inc.",
            current_price=175.00,
            revenue_ttm=96_000_000_000,
            eps_latest=3.12,
            eps_prev_quarter=2.95,
            earnings_growth=-23.0
        ),
        "GME": TickerFundamentals(
            ticker="GME",
            company_name="GameStop Corp.",
            current_price=15.50,
            revenue_ttm=5_300_000_000,
            eps_latest=-0.35,
            eps_prev_quarter=-0.52,
            earnings_growth=None
        ),
        "AMC": TickerFundamentals(
            ticker="AMC",
            company_name="AMC Entertainment Holdings",
            current_price=4.25,
            revenue_ttm=4_800_000_000,
            eps_latest=-0.95,
            eps_prev_quarter=-1.12,
            earnings_growth=None
        ),
    }


def create_mock_aggregated_mentions() -> Dict[str, Dict]:
    """Create mock aggregated mentions for testing."""
    return {
        "NVDA": {
            "ticker": "NVDA",
            "mention_count": 132,
            "total_upvotes": 4500,
            "total_comments": 890,
            "unique_posts": 45,
            "subreddits": ["wallstreetbets", "stocks", "investing"],
            "trending_velocity": 2.1
        },
        "AAPL": {
            "ticker": "AAPL",
            "mention_count": 98,
            "total_upvotes": 2100,
            "total_comments": 450,
            "unique_posts": 32,
            "subreddits": ["wallstreetbets", "stocks"],
            "trending_velocity": 1.3
        },
        "AMD": {
            "ticker": "AMD",
            "mention_count": 85,
            "total_upvotes": 3200,
            "total_comments": 520,
            "unique_posts": 28,
            "subreddits": ["wallstreetbets", "stocks"],
            "trending_velocity": 1.8
        },
        "PLTR": {
            "ticker": "PLTR",
            "mention_count": 76,
            "total_upvotes": 2800,
            "total_comments": 410,
            "unique_posts": 25,
            "subreddits": ["wallstreetbets"],
            "trending_velocity": 2.5
        },
        "MSFT": {
            "ticker": "MSFT",
            "mention_count": 65,
            "total_upvotes": 1800,
            "total_comments": 320,
            "unique_posts": 22,
            "subreddits": ["stocks", "investing"],
            "trending_velocity": 1.1
        },
        "TSLA": {
            "ticker": "TSLA",
            "mention_count": 120,
            "total_upvotes": 5500,
            "total_comments": 980,
            "unique_posts": 48,
            "subreddits": ["wallstreetbets", "stocks"],
            "trending_velocity": 1.5
        },
        "GME": {
            "ticker": "GME",
            "mention_count": 200,
            "total_upvotes": 12000,
            "total_comments": 2500,
            "unique_posts": 80,
            "subreddits": ["wallstreetbets"],
            "trending_velocity": 3.5
        },
        "AMC": {
            "ticker": "AMC",
            "mention_count": 95,
            "total_upvotes": 4800,
            "total_comments": 720,
            "unique_posts": 35,
            "subreddits": ["wallstreetbets"],
            "trending_velocity": 2.2
        },
    }


def create_mock_sentiment() -> Dict[str, float]:
    """Create mock sentiment data for testing."""
    return {
        "NVDA": 0.75,
        "AAPL": 0.45,
        "AMD": 0.62,
        "PLTR": 0.58,
        "MSFT": 0.40,
        "TSLA": 0.25,
        "GME": 0.82,
        "AMC": 0.65,
    }
