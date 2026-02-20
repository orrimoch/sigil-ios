"""
Tests for Historical Sentiment Scorer (REC-209)
"""

import pytest
from datetime import datetime, date, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock
import tempfile
import json

from src.sentiment_historical.sentiment_scorer import (
    HistoricalSentimentScorer,
    ScoredHeadline,
    WeeklySentiment,
    ScoringProgress,
    HISTORICAL_SENTIMENT_PROMPT,
)
from src.sentiment_historical.news_provider import NewsArticle


@pytest.fixture
def mock_client():
    """Create a mock Claude client."""
    client = MagicMock()
    client.is_available = True
    return client


@pytest.fixture
def sample_articles():
    """Create sample articles for testing."""
    return [
        NewsArticle(
            ticker="AAPL",
            headline="Apple beats earnings expectations",
            published=datetime(2019, 6, 15, 10, 30),
        ),
        NewsArticle(
            ticker="AAPL",
            headline="Apple announces new iPhone",
            published=datetime(2019, 6, 18, 14, 0),
        ),
        NewsArticle(
            ticker="MSFT",
            headline="Microsoft cloud revenue surges",
            published=datetime(2019, 6, 20, 9, 0),
        ),
    ]


class TestScoredHeadline:
    """Tests for ScoredHeadline dataclass."""
    
    def test_create_scored_headline(self):
        sh = ScoredHeadline(
            ticker="AAPL",
            headline="Apple beats earnings",
            published=datetime(2019, 6, 15),
            score=75.0,
        )
        
        assert sh.ticker == "AAPL"
        assert sh.score == 75.0
    
    def test_to_dict(self):
        sh = ScoredHeadline(
            ticker="AAPL",
            headline="Apple beats earnings",
            published=datetime(2019, 6, 15, 10, 30),
            score=75.0,
        )
        
        d = sh.to_dict()
        
        assert d["ticker"] == "AAPL"
        assert d["headline"] == "Apple beats earnings"
        assert d["score"] == 75.0
        assert "published" in d


class TestWeeklySentiment:
    """Tests for WeeklySentiment dataclass."""
    
    def test_create_weekly_sentiment(self):
        ws = WeeklySentiment(
            ticker="AAPL",
            week_start=date(2019, 6, 10),
            week_end=date(2019, 6, 16),
            score=72.5,
            article_count=3,
        )
        
        assert ws.ticker == "AAPL"
        assert ws.score == 72.5
        assert ws.article_count == 3
    
    def test_to_dict(self):
        ws = WeeklySentiment(
            ticker="AAPL",
            week_start=date(2019, 6, 10),
            week_end=date(2019, 6, 16),
            score=72.5,
            article_count=3,
        )
        
        d = ws.to_dict()
        
        assert d["score"] == 72.5
        assert d["week_start"] == "2019-06-10"
        assert d["week_end"] == "2019-06-16"


class TestScoringProgress:
    """Tests for ScoringProgress dataclass."""
    
    def test_default_values(self):
        progress = ScoringProgress()
        
        assert progress.total_headlines == 0
        assert progress.scored_headlines == 0
        assert progress.total_cost_usd == 0.0
    
    def test_to_dict(self):
        progress = ScoringProgress(
            total_headlines=100,
            scored_headlines=50,
            total_cost_usd=0.50,
        )
        
        d = progress.to_dict()
        
        assert d["total_headlines"] == 100
        assert d["scored_headlines"] == 50
    
    def test_from_dict(self):
        data = {
            "total_headlines": 100,
            "scored_headlines": 50,
            "failed_headlines": 5,
            "total_cost_usd": 0.50,
            "start_time": "2019-06-15T10:00:00",
            "last_checkpoint": "",
            "last_processed_index": 50,
        }
        
        progress = ScoringProgress.from_dict(data)
        
        assert progress.total_headlines == 100
        assert progress.scored_headlines == 50


class TestHistoricalSentimentScorer:
    """Tests for HistoricalSentimentScorer."""
    
    def test_init(self, mock_client):
        scorer = HistoricalSentimentScorer(client=mock_client)
        
        assert scorer.is_available
        assert scorer.batch_size == 50
    
    def test_estimate_cost(self, mock_client):
        scorer = HistoricalSentimentScorer(client=mock_client)
        
        # 1000 headlines
        cost = scorer.estimate_cost(1000)
        
        # Should be roughly $0.02-0.03 for 1000 headlines
        assert 0.01 < cost < 0.10
    
    def test_estimate_cost_30k_headlines(self, mock_client):
        """Test cost estimate for actual dataset size."""
        scorer = HistoricalSentimentScorer(client=mock_client)
        
        cost = scorer.estimate_cost(30826)  # Actual dataset size
        
        # Should be ~$1.00
        assert 0.5 < cost < 2.0
    
    def test_score_headline_success(self, mock_client):
        """Test successful headline scoring."""
        mock_client.analyze.return_value = {"score": 72}
        
        scorer = HistoricalSentimentScorer(client=mock_client)
        score = scorer.score_headline("AAPL", "Apple beats earnings")
        
        assert score == 72.0
        mock_client.analyze.assert_called_once()
    
    def test_score_headline_with_json_response(self, mock_client):
        """Test scoring when client returns JSON."""
        mock_client.analyze.return_value = {"score": 85}
        
        scorer = HistoricalSentimentScorer(client=mock_client)
        score = scorer.score_headline("AAPL", "Apple beats earnings")
        
        assert score == 85.0
    
    def test_score_headline_failure(self, mock_client):
        """Test handling of scoring failure."""
        mock_client.analyze.return_value = None
        
        scorer = HistoricalSentimentScorer(client=mock_client)
        score = scorer.score_headline("AAPL", "Apple news")
        
        assert score is None
    
    def test_score_headline_extracts_number(self, mock_client):
        """Test extracting number from text response."""
        mock_client.analyze.return_value = "65"
        
        scorer = HistoricalSentimentScorer(client=mock_client)
        score = scorer.score_headline("AAPL", "Apple news")
        
        assert score == 65.0
    
    def test_score_headline_clamps_to_range(self, mock_client):
        """Test that scores are clamped to 0-100."""
        mock_client.analyze.return_value = {"score": 150}
        
        scorer = HistoricalSentimentScorer(client=mock_client)
        score = scorer.score_headline("AAPL", "Apple news")
        
        assert score == 100.0  # Clamped
    
    def test_score_articles(self, mock_client, sample_articles):
        """Test scoring multiple articles using batch API."""
        # score_articles uses score_headlines_batch which expects batch response
        mock_client.analyze.return_value = {"scores": [75, 68, 82]}
        
        with tempfile.TemporaryDirectory() as tmpdir:
            scorer = HistoricalSentimentScorer(
                client=mock_client,
                output_dir=Path(tmpdir),
                checkpoint_interval=10,
            )
            
            scored = scorer.score_articles(sample_articles, resume=False, batch_size=20)
        
        assert len(scored) == 3
        assert scored[0].score == 75.0
        assert scored[1].score == 68.0
        assert scored[2].score == 82.0
    
    def test_aggregate_weekly_single_week(self, mock_client):
        """Test weekly aggregation for single week."""
        scored = [
            ScoredHeadline("AAPL", "H1", datetime(2019, 6, 10), 70.0),
            ScoredHeadline("AAPL", "H2", datetime(2019, 6, 12), 80.0),
            ScoredHeadline("AAPL", "H3", datetime(2019, 6, 14), 75.0),
        ]
        
        scorer = HistoricalSentimentScorer(client=mock_client)
        weekly = scorer.aggregate_weekly(scored)
        
        assert "AAPL" in weekly
        assert len(weekly["AAPL"]) == 1
        
        week = weekly["AAPL"][0]
        assert week.article_count == 3
        # Weighted average should be between min and max
        assert 70.0 <= week.score <= 80.0
    
    def test_aggregate_weekly_multiple_tickers(self, mock_client):
        """Test weekly aggregation for multiple tickers."""
        scored = [
            ScoredHeadline("AAPL", "H1", datetime(2019, 6, 10), 70.0),
            ScoredHeadline("MSFT", "H2", datetime(2019, 6, 12), 65.0),
        ]
        
        scorer = HistoricalSentimentScorer(client=mock_client)
        weekly = scorer.aggregate_weekly(scored)
        
        assert "AAPL" in weekly
        assert "MSFT" in weekly
    
    def test_aggregate_weekly_multiple_weeks(self, mock_client):
        """Test aggregation across multiple weeks."""
        scored = [
            ScoredHeadline("AAPL", "Week 1", datetime(2019, 6, 10), 70.0),  # Week 1
            ScoredHeadline("AAPL", "Week 2", datetime(2019, 6, 17), 80.0),  # Week 2
            ScoredHeadline("AAPL", "Week 3", datetime(2019, 6, 24), 75.0),  # Week 3
        ]
        
        scorer = HistoricalSentimentScorer(client=mock_client)
        weekly = scorer.aggregate_weekly(scored)
        
        assert len(weekly["AAPL"]) == 3
    
    def test_aggregate_weekly_recency_weighting(self, mock_client):
        """Test that newer articles get higher weight within a week."""
        # Two articles in same week - later one should have more weight
        scored = [
            ScoredHeadline("AAPL", "Old", datetime(2019, 6, 10), 50.0),  # Monday (old)
            ScoredHeadline("AAPL", "New", datetime(2019, 6, 15), 90.0),  # Saturday (new)
        ]
        
        scorer = HistoricalSentimentScorer(client=mock_client)
        weekly = scorer.aggregate_weekly(scored)
        
        # Weighted average should be closer to 90 than 50
        week_score = weekly["AAPL"][0].score
        assert week_score > 70.0  # Should be weighted toward newer
    
    def test_save_results(self, mock_client):
        """Test saving results to JSON."""
        scored = [
            ScoredHeadline("AAPL", "H1", datetime(2019, 6, 10), 70.0),
        ]
        weekly = {
            "AAPL": [
                WeeklySentiment("AAPL", date(2019, 6, 10), date(2019, 6, 16), 70.0, 1)
            ]
        }
        
        with tempfile.TemporaryDirectory() as tmpdir:
            scorer = HistoricalSentimentScorer(
                client=mock_client,
                output_dir=Path(tmpdir),
            )
            
            output_path = scorer.save_results(scored, weekly)
            
            assert output_path.exists()
            
            data = json.loads(output_path.read_text())
            assert data["headline_count"] == 1
            assert data["ticker_count"] == 1
            assert "AAPL" in data["weekly_scores"]


class TestHistoricalSentimentScorerCheckpoints:
    """Tests for checkpoint/resume functionality."""
    
    def test_save_and_load_checkpoint(self, mock_client):
        """Test checkpoint save and load."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scorer = HistoricalSentimentScorer(
                client=mock_client,
                output_dir=Path(tmpdir),
            )
            
            progress = ScoringProgress(
                total_headlines=100,
                scored_headlines=50,
                last_processed_index=50,
            )
            scored = [
                ScoredHeadline("AAPL", "H1", datetime(2019, 6, 10), 70.0),
            ]
            
            scorer._save_checkpoint(progress, scored)
            
            # Load checkpoint
            loaded_progress = scorer._load_checkpoint()
            loaded_scored = scorer._load_partial_results()
            
            assert loaded_progress.scored_headlines == 50
            assert len(loaded_scored) == 1
    
    def test_clear_checkpoints(self, mock_client):
        """Test clearing checkpoints."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scorer = HistoricalSentimentScorer(
                client=mock_client,
                output_dir=Path(tmpdir),
            )
            
            # Create checkpoint files
            scorer._checkpoint_path().write_text("{}")
            scorer._partial_results_path().write_text("[]")
            
            scorer.clear_checkpoints()
            
            assert not scorer._checkpoint_path().exists()
            assert not scorer._partial_results_path().exists()


class TestSystemPrompt:
    """Tests for the system prompt."""
    
    def test_prompt_contains_scoring_guide(self):
        assert "0-15" in HISTORICAL_SENTIMENT_PROMPT
        assert "85-100" in HISTORICAL_SENTIMENT_PROMPT
    
    def test_prompt_mentions_scale(self):
        assert "0-100" in HISTORICAL_SENTIMENT_PROMPT
    
    def test_prompt_requests_number_only(self):
        assert "ONLY a number" in HISTORICAL_SENTIMENT_PROMPT
