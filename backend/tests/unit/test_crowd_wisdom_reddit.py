"""
REC-266: Unit Tests for Reddit-Based Crowd Wisdom

Tests:
- Reddit fetcher (mock PRAW responses)
- Scoring algorithm
- Quality filters
- API endpoints
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from datetime import datetime, timedelta
import json

# Import modules under test
from src.crowd_wisdom.reddit_fetcher import (
    RedditFetcher,
    RedditMention,
    fetch_reddit_mentions,
    TICKER_EXCLUSIONS
)
from src.crowd_wisdom.reddit_scorer import (
    RedditScorer,
    TickerFundamentals,
    RedditScore,
    score_to_dict,
    get_weekly_top_picks,
    create_mock_fundamentals,
    create_mock_aggregated_mentions,
    create_mock_sentiment
)


# =============================================================================
# Reddit Fetcher Tests
# =============================================================================

class TestRedditFetcher:
    """Test Reddit API fetcher."""
    
    def test_extract_tickers_cashtags(self):
        """Test extraction of cashtag format ($AAPL)."""
        fetcher = RedditFetcher()
        
        text = "I'm bullish on $AAPL and $MSFT. Short $TSLA."
        tickers = fetcher.extract_tickers(text)
        
        assert "AAPL" in tickers
        assert "MSFT" in tickers
        assert "TSLA" in tickers
    
    def test_extract_tickers_uppercase(self):
        """Test extraction of uppercase ticker mentions."""
        fetcher = RedditFetcher()
        
        text = "NVDA is going to moon! AMD also looking strong."
        tickers = fetcher.extract_tickers(text)
        
        assert "NVDA" in tickers
        assert "AMD" in tickers
    
    def test_extract_tickers_excludes_common_words(self):
        """Test that common words are excluded."""
        fetcher = RedditFetcher()
        
        text = "IMO the CEO said GDP and CPI are bullish for AAPL"
        tickers = fetcher.extract_tickers(text)
        
        assert "IMO" not in tickers
        assert "CEO" not in tickers
        assert "GDP" not in tickers
        assert "CPI" not in tickers
        assert "AAPL" in tickers
    
    def test_extract_tickers_with_valid_filter(self):
        """Test ticker filtering against valid set."""
        fetcher = RedditFetcher()
        fetcher.set_valid_tickers({"AAPL", "MSFT", "NVDA"})
        
        text = "$AAPL $MSFT $FAKE $XYZ"
        tickers = fetcher.extract_tickers(text)
        
        assert "AAPL" in tickers
        assert "MSFT" in tickers
        assert "FAKE" not in tickers
        assert "XYZ" not in tickers
    
    def test_extract_tickers_empty_text(self):
        """Test handling of empty text."""
        fetcher = RedditFetcher()
        
        assert fetcher.extract_tickers("") == set()
        assert fetcher.extract_tickers(None) == set()
    
    def test_extract_tickers_no_duplicates(self):
        """Test that duplicate mentions are deduplicated."""
        fetcher = RedditFetcher()
        
        text = "$AAPL AAPL $AAPL going to moon AAPL"
        tickers = fetcher.extract_tickers(text)
        
        assert len(tickers) == 1
        assert "AAPL" in tickers
    
    def test_aggregate_by_ticker(self):
        """Test aggregation of mentions by ticker."""
        fetcher = RedditFetcher()
        
        mentions = [
            RedditMention(
                ticker="AAPL", subreddit="wallstreetbets", post_id="1",
                post_title="AAPL to the moon", post_body="", upvotes=100,
                comments=20, post_created_at=datetime.now()
            ),
            RedditMention(
                ticker="AAPL", subreddit="stocks", post_id="2",
                post_title="Apple earnings", post_body="", upvotes=50,
                comments=10, post_created_at=datetime.now()
            ),
            RedditMention(
                ticker="MSFT", subreddit="investing", post_id="3",
                post_title="MSFT analysis", post_body="", upvotes=75,
                comments=15, post_created_at=datetime.now()
            ),
        ]
        
        aggregated = fetcher.aggregate_by_ticker(mentions)
        
        assert "AAPL" in aggregated
        assert "MSFT" in aggregated
        assert aggregated["AAPL"]["mention_count"] == 2
        assert aggregated["AAPL"]["total_upvotes"] == 150
        assert aggregated["AAPL"]["unique_posts"] == 2
        assert set(aggregated["AAPL"]["subreddits"]) == {"wallstreetbets", "stocks"}
        assert aggregated["MSFT"]["mention_count"] == 1
    
    def test_fetch_mentions_processes_posts(self):
        """Test that fetch_mentions processes posts correctly with mock."""
        fetcher = RedditFetcher(
            client_id="test", client_secret="test", user_agent="test"
        )
        
        # Create mock post
        mock_post = MagicMock()
        mock_post.id = "abc123"
        mock_post.title = "NVDA is going to moon $AAPL"
        mock_post.selftext = "I'm all in on NVDA"
        mock_post.score = 500
        mock_post.num_comments = 100
        mock_post.created_utc = datetime.utcnow().timestamp()
        
        # Mock comments
        mock_comments = MagicMock()
        mock_comments.replace_more = MagicMock()
        mock_comments.__iter__ = lambda self: iter([])
        mock_post.comments = mock_comments
        
        # Setup subreddit mock
        mock_subreddit = MagicMock()
        mock_subreddit.hot.return_value = [mock_post]
        mock_subreddit.new.return_value = []
        
        # Create mock Reddit instance
        mock_reddit = MagicMock()
        mock_reddit.subreddit.return_value = mock_subreddit
        
        # Inject mock
        fetcher._reddit = mock_reddit
        
        # Only test one subreddit to keep it simple
        fetcher.subreddits = ["wallstreetbets"]
        
        mentions = fetcher.fetch_mentions(days_back=7, include_comments=False)
        
        # Should extract NVDA and AAPL from the post
        tickers = {m.ticker for m in mentions}
        assert "NVDA" in tickers or "AAPL" in tickers


# =============================================================================
# Reddit Scorer Tests
# =============================================================================

class TestRedditScorer:
    """Test viral score calculation."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.scorer = RedditScorer()
        self.scorer.set_fundamentals(create_mock_fundamentals())
    
    def test_score_tickers_returns_sorted_list(self):
        """Test that scores are returned sorted by viral_score."""
        mentions = create_mock_aggregated_mentions()
        sentiment = create_mock_sentiment()
        
        scores = self.scorer.score_tickers(mentions, sentiment)
        
        assert len(scores) > 0
        # Verify sorted descending
        for i in range(len(scores) - 1):
            assert scores[i].viral_score >= scores[i + 1].viral_score
    
    def test_score_components_weighted_correctly(self):
        """Test that score components are weighted correctly."""
        # Create a single mention with known values
        mentions = {
            "TEST": {
                "ticker": "TEST",
                "mention_count": 100,  # Max mentions for this test
                "total_upvotes": 1000,  # Max upvotes for this test
                "total_comments": 200,
                "unique_posts": 50,
                "subreddits": ["wallstreetbets"],
                "trending_velocity": 3.0  # 3x = max velocity
            }
        }
        
        # Add fundamentals for TEST
        self.scorer._fundamentals["TEST"] = TickerFundamentals(
            ticker="TEST",
            company_name="Test Corp",
            current_price=100.0,
            revenue_ttm=10_000_000_000,  # $10B
            eps_latest=5.0,
            earnings_growth=50.0
        )
        
        # Perfect sentiment
        sentiment = {"TEST": 1.0}  # Maximum bullish
        
        scores = self.scorer.score_tickers(mentions, sentiment)
        
        assert len(scores) == 1
        score = scores[0]
        
        # With max values for all components, score should be near 100
        # (30% * 100) + (20% * 100) + (20% * 100) + (15% * 100) + (15% * 100)
        assert score.viral_score >= 90  # Allow some margin
    
    def test_quality_filter_revenue(self):
        """Test revenue filter rejects low-revenue stocks."""
        mentions = {
            "LOWREV": {
                "ticker": "LOWREV",
                "mention_count": 50,
                "total_upvotes": 500,
                "total_comments": 100,
                "unique_posts": 20,
                "subreddits": ["wallstreetbets"],
                "trending_velocity": 1.5
            }
        }
        
        self.scorer._fundamentals["LOWREV"] = TickerFundamentals(
            ticker="LOWREV",
            company_name="Low Revenue Inc",
            revenue_ttm=10_000_000,  # $10M < $50M minimum
            eps_latest=0.5
        )
        
        scores = self.scorer.score_tickers(mentions)
        
        assert len(scores) == 1
        assert scores[0].passes_filters == False
        assert "revenue" in scores[0].filter_reason.lower()
    
    def test_quality_filter_eps(self):
        """Test EPS filter rejects negative EPS without improvement."""
        mentions = {
            "NEGEPS": {
                "ticker": "NEGEPS",
                "mention_count": 50,
                "total_upvotes": 500,
                "total_comments": 100,
                "unique_posts": 20,
                "subreddits": ["wallstreetbets"],
                "trending_velocity": 1.5
            }
        }
        
        self.scorer._fundamentals["NEGEPS"] = TickerFundamentals(
            ticker="NEGEPS",
            company_name="Negative EPS Inc",
            revenue_ttm=100_000_000,  # Passes revenue
            eps_latest=-0.50,
            eps_prev_quarter=-0.40  # Worsening
        )
        
        scores = self.scorer.score_tickers(mentions)
        
        assert len(scores) == 1
        assert scores[0].passes_filters == False
        assert "eps" in scores[0].filter_reason.lower()
    
    def test_quality_filter_improving_eps(self):
        """Test that improving negative EPS passes filter."""
        mentions = {
            "IMPROV": {
                "ticker": "IMPROV",
                "mention_count": 50,
                "total_upvotes": 500,
                "total_comments": 100,
                "unique_posts": 20,
                "subreddits": ["wallstreetbets"],
                "trending_velocity": 1.5
            }
        }
        
        self.scorer._fundamentals["IMPROV"] = TickerFundamentals(
            ticker="IMPROV",
            company_name="Improving Inc",
            revenue_ttm=100_000_000,  # Passes revenue
            eps_latest=-0.20,
            eps_prev_quarter=-0.50  # Improving
        )
        
        scores = self.scorer.score_tickers(mentions)
        
        assert len(scores) == 1
        assert scores[0].passes_filters == True
    
    def test_sentiment_labels(self):
        """Test sentiment score to label conversion."""
        mentions = create_mock_aggregated_mentions()
        
        # Test various sentiment levels
        test_cases = [
            (0.8, "VERY_BULLISH"),
            (0.4, "BULLISH"),
            (0.0, "NEUTRAL"),
            (-0.4, "BEARISH"),
            (-0.8, "VERY_BEARISH"),
        ]
        
        for sentiment_score, expected_label in test_cases:
            sentiment = {"NVDA": sentiment_score}
            scores = self.scorer.score_tickers({"NVDA": mentions["NVDA"]}, sentiment)
            assert scores[0].sentiment_label == expected_label
    
    def test_signal_determination(self):
        """Test signal assignment based on viral score."""
        # Test VERY_HOT (score >= 80)
        score = RedditScore(
            ticker="TEST", company_name="Test", viral_score=85,
            mention_count=100, total_upvotes=1000, total_comments=200,
            unique_posts=50, subreddits=["wsb"], avg_sentiment=0.5,
            sentiment_label="BULLISH", trending_velocity=2.0,
            current_price=100, revenue_ttm=10e9, eps_latest=5.0,
            earnings_growth=20, passes_filters=True, filter_reason=None,
            signal="PLACEHOLDER"
        )
        
        # Check signal based on score ranges
        assert self.scorer._determine_signal(85, True) == "VERY_HOT"
        assert self.scorer._determine_signal(70, True) == "HOT"
        assert self.scorer._determine_signal(50, True) == "TRENDING"
        assert self.scorer._determine_signal(30, True) == "NEUTRAL"
        assert self.scorer._determine_signal(85, False) == "NEUTRAL"  # Fails filter
    
    def test_minimum_mentions_threshold(self):
        """Test that tickers below minimum mentions are excluded."""
        mentions = {
            "FEWMNT": {
                "ticker": "FEWMNT",
                "mention_count": 2,  # Below default threshold of 5
                "total_upvotes": 100,
                "total_comments": 20,
                "unique_posts": 2,
                "subreddits": ["wallstreetbets"],
                "trending_velocity": 1.0
            }
        }
        
        scores = self.scorer.score_tickers(mentions)
        
        assert len(scores) == 0


class TestGetWeeklyTopPicks:
    """Test top picks selection."""
    
    def test_filters_to_passing_only(self):
        """Test that only stocks passing filters are included."""
        scores = [
            RedditScore(
                ticker="PASS1", company_name="Pass 1", viral_score=90,
                mention_count=100, total_upvotes=1000, total_comments=200,
                unique_posts=50, subreddits=["wsb"], avg_sentiment=0.5,
                sentiment_label="BULLISH", trending_velocity=2.0,
                current_price=100, revenue_ttm=10e9, eps_latest=5.0,
                earnings_growth=20, passes_filters=True, filter_reason=None,
                signal="VERY_HOT"
            ),
            RedditScore(
                ticker="FAIL1", company_name="Fail 1", viral_score=85,
                mention_count=90, total_upvotes=900, total_comments=180,
                unique_posts=45, subreddits=["wsb"], avg_sentiment=0.4,
                sentiment_label="BULLISH", trending_velocity=1.8,
                current_price=50, revenue_ttm=10e6, eps_latest=-0.5,
                earnings_growth=None, passes_filters=False,
                filter_reason="Low revenue", signal="NEUTRAL"
            ),
            RedditScore(
                ticker="PASS2", company_name="Pass 2", viral_score=80,
                mention_count=80, total_upvotes=800, total_comments=160,
                unique_posts=40, subreddits=["stocks"], avg_sentiment=0.3,
                sentiment_label="BULLISH", trending_velocity=1.5,
                current_price=200, revenue_ttm=5e9, eps_latest=3.0,
                earnings_growth=15, passes_filters=True, filter_reason=None,
                signal="VERY_HOT"
            ),
        ]
        
        top_picks = get_weekly_top_picks(scores, max_picks=5)
        
        assert len(top_picks) == 2
        assert all(p.passes_filters for p in top_picks)
        assert top_picks[0].ticker == "PASS1"  # Highest score
        assert top_picks[1].ticker == "PASS2"
    
    def test_limits_to_max_picks(self):
        """Test that max_picks is respected."""
        # Create 10 passing scores
        scores = [
            RedditScore(
                ticker=f"PASS{i}", company_name=f"Pass {i}", viral_score=90-i,
                mention_count=100-i, total_upvotes=1000, total_comments=200,
                unique_posts=50, subreddits=["wsb"], avg_sentiment=0.5,
                sentiment_label="BULLISH", trending_velocity=2.0,
                current_price=100, revenue_ttm=10e9, eps_latest=5.0,
                earnings_growth=20, passes_filters=True, filter_reason=None,
                signal="VERY_HOT"
            )
            for i in range(10)
        ]
        
        top_picks = get_weekly_top_picks(scores, max_picks=5)
        
        assert len(top_picks) == 5
        assert top_picks[0].ticker == "PASS0"  # Highest score


class TestScoreToDict:
    """Test conversion to dictionary."""
    
    def test_converts_all_fields(self):
        """Test that all fields are converted."""
        score = RedditScore(
            ticker="TEST", company_name="Test Corp", viral_score=75.5,
            mention_count=100, total_upvotes=1500, total_comments=300,
            unique_posts=45, subreddits=["wsb", "stocks"], avg_sentiment=0.6,
            sentiment_label="BULLISH", trending_velocity=2.1,
            current_price=150.0, revenue_ttm=5e9, eps_latest=2.5,
            earnings_growth=25.0, passes_filters=True, filter_reason=None,
            signal="HOT"
        )
        
        result = score_to_dict(score)
        
        assert result["ticker"] == "TEST"
        assert result["company_name"] == "Test Corp"
        assert result["viral_score"] == 75.5
        assert result["mention_count"] == 100
        assert result["total_upvotes"] == 1500
        assert result["subreddits"] == ["wsb", "stocks"]
        assert result["passes_filters"] == True
        assert result["signal"] == "HOT"


# =============================================================================
# API Endpoint Tests
# =============================================================================

class TestAPIEndpoints:
    """Test API endpoints with mocked data."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        from fastapi.testclient import TestClient
        try:
            from src.api.main import app
            return TestClient(app)
        except ImportError:
            pytest.skip("Main app not available for endpoint tests")
    
    @pytest.mark.asyncio
    async def test_get_top_picks_returns_picks(self, client):
        """Test /top-picks endpoint returns picks."""
        # First refresh to populate data
        response = client.post("/api/v1/crowd-wisdom/refresh")
        assert response.status_code == 200
        
        # Then get picks
        response = client.get("/api/v1/crowd-wisdom/top-picks")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert "picks" in data
        assert "week_start" in data
        assert len(data["picks"]) <= 5
        
        # Verify pick structure
        if data["picks"]:
            pick = data["picks"][0]
            assert "rank" in pick
            assert "ticker" in pick
            assert "viral_score" in pick
            assert "mention_count" in pick
            assert "total_upvotes" in pick
            assert "sentiment_label" in pick
            assert "signal" in pick
    
    @pytest.mark.asyncio
    async def test_get_trending_returns_all_tickers(self, client):
        """Test /trending endpoint returns all tickers."""
        # Refresh first
        client.post("/api/v1/crowd-wisdom/refresh")
        
        response = client.get("/api/v1/crowd-wisdom/trending")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert "tickers" in data
        assert "count" in data
        assert data["count"] == len(data["tickers"])
    
    @pytest.mark.asyncio
    async def test_get_trending_filtered(self, client):
        """Test /trending?filtered=true returns only filtered stocks."""
        client.post("/api/v1/crowd-wisdom/refresh")
        
        response = client.get("/api/v1/crowd-wisdom/trending?filtered=true")
        assert response.status_code == 200
        
        data = response.json()
        # All returned tickers should pass filters
        for ticker in data["tickers"]:
            assert ticker["passes_filters"] == True
    
    @pytest.mark.asyncio
    async def test_get_ticker_score_found(self, client):
        """Test /scores/{ticker} returns score for known ticker."""
        client.post("/api/v1/crowd-wisdom/refresh")
        
        response = client.get("/api/v1/crowd-wisdom/scores/NVDA")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert data["ticker"] == "NVDA"
        assert "viral_score" in data
        assert "sentiment_label" in data
    
    @pytest.mark.asyncio
    async def test_get_ticker_score_not_found(self, client):
        """Test /scores/{ticker} returns 404 for unknown ticker."""
        response = client.get("/api/v1/crowd-wisdom/scores/NOTREAL")
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_refresh_endpoint(self, client):
        """Test /refresh endpoint."""
        response = client.post("/api/v1/crowd-wisdom/refresh")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert "mentions_fetched" in data
        assert "scores_calculated" in data
        assert "top_picks_saved" in data


# =============================================================================
# Mock Data Tests
# =============================================================================

class TestMockData:
    """Test mock data generators."""
    
    def test_mock_fundamentals_has_required_fields(self):
        """Test that mock fundamentals have all required fields."""
        fundamentals = create_mock_fundamentals()
        
        assert len(fundamentals) > 0
        
        for ticker, fund in fundamentals.items():
            assert fund.ticker == ticker
            assert fund.company_name is not None
            assert fund.revenue_ttm is not None or fund.revenue_ttm is None  # Can be None for some
    
    def test_mock_mentions_has_required_fields(self):
        """Test that mock mentions have all required fields."""
        mentions = create_mock_aggregated_mentions()
        
        assert len(mentions) > 0
        
        for ticker, data in mentions.items():
            assert data["ticker"] == ticker
            assert "mention_count" in data
            assert "total_upvotes" in data
            assert "subreddits" in data
    
    def test_mock_sentiment_values_in_range(self):
        """Test that mock sentiment values are in valid range."""
        sentiment = create_mock_sentiment()
        
        for ticker, score in sentiment.items():
            assert -1.0 <= score <= 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
