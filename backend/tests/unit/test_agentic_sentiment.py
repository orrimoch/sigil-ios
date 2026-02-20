"""
Tests for Agentic Sentiment Analyzer (REC-172)
"""

import os
import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from pathlib import Path
from datetime import datetime, timedelta
import tempfile

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from scoring.agentic_sentiment import (
    SentimentLabel,
    ArticleAnalysis,
    AgentSentimentResult,
    SentimentCache,
    AgenticSentimentAnalyzer,
    get_agentic_analyzer,
    SENTIMENT_AGENT_SYSTEM_PROMPT,
)
from scoring.sentiment_config import SentimentConfig, SentimentModel


class TestSentimentLabel:
    """Test SentimentLabel enum."""
    
    def test_all_labels_exist(self):
        labels = [
            SentimentLabel.VERY_BULLISH,
            SentimentLabel.BULLISH,
            SentimentLabel.SLIGHTLY_BULLISH,
            SentimentLabel.NEUTRAL,
            SentimentLabel.SLIGHTLY_BEARISH,
            SentimentLabel.BEARISH,
            SentimentLabel.VERY_BEARISH,
        ]
        assert len(labels) == 7
    
    def test_from_score_very_bullish(self):
        assert SentimentLabel.from_score(90) == SentimentLabel.VERY_BULLISH
        assert SentimentLabel.from_score(85) == SentimentLabel.VERY_BULLISH
        assert SentimentLabel.from_score(100) == SentimentLabel.VERY_BULLISH
    
    def test_from_score_bullish(self):
        assert SentimentLabel.from_score(75) == SentimentLabel.BULLISH
        assert SentimentLabel.from_score(70) == SentimentLabel.BULLISH
        assert SentimentLabel.from_score(84) == SentimentLabel.BULLISH
    
    def test_from_score_slightly_bullish(self):
        assert SentimentLabel.from_score(60) == SentimentLabel.SLIGHTLY_BULLISH
        assert SentimentLabel.from_score(55) == SentimentLabel.SLIGHTLY_BULLISH
        assert SentimentLabel.from_score(69) == SentimentLabel.SLIGHTLY_BULLISH
    
    def test_from_score_neutral(self):
        assert SentimentLabel.from_score(50) == SentimentLabel.NEUTRAL
        assert SentimentLabel.from_score(45) == SentimentLabel.NEUTRAL
        assert SentimentLabel.from_score(54) == SentimentLabel.NEUTRAL
    
    def test_from_score_slightly_bearish(self):
        assert SentimentLabel.from_score(40) == SentimentLabel.SLIGHTLY_BEARISH
        assert SentimentLabel.from_score(31) == SentimentLabel.SLIGHTLY_BEARISH
        assert SentimentLabel.from_score(44) == SentimentLabel.SLIGHTLY_BEARISH
    
    def test_from_score_bearish(self):
        assert SentimentLabel.from_score(25) == SentimentLabel.BEARISH
        assert SentimentLabel.from_score(16) == SentimentLabel.BEARISH
        assert SentimentLabel.from_score(30) == SentimentLabel.BEARISH
    
    def test_from_score_very_bearish(self):
        assert SentimentLabel.from_score(10) == SentimentLabel.VERY_BEARISH
        assert SentimentLabel.from_score(0) == SentimentLabel.VERY_BEARISH
        assert SentimentLabel.from_score(15) == SentimentLabel.VERY_BEARISH


class TestArticleAnalysis:
    """Test ArticleAnalysis dataclass."""
    
    def test_creation(self):
        analysis = ArticleAnalysis(
            headline="Test Headline",
            sentiment=SentimentLabel.BULLISH,
            score=75.0,
            key_factors=["Strong earnings", "Growth"],
            relevance=0.8
        )
        
        assert analysis.headline == "Test Headline"
        assert analysis.sentiment == SentimentLabel.BULLISH
        assert analysis.score == 75.0
        assert len(analysis.key_factors) == 2
        assert analysis.relevance == 0.8
    
    def test_default_values(self):
        analysis = ArticleAnalysis(
            headline="Test",
            sentiment=SentimentLabel.NEUTRAL,
            score=50.0
        )
        
        assert analysis.key_factors == []
        assert analysis.relevance == 0.5


class TestAgentSentimentResult:
    """Test AgentSentimentResult dataclass."""
    
    def test_creation(self):
        result = AgentSentimentResult(
            ticker="AAPL",
            overall_score=72.5,
            overall_sentiment=SentimentLabel.BULLISH,
            confidence=0.85,
            rationale="Strong earnings and positive outlook.",
            bullish_factors=["Revenue beat", "iPhone growth"],
            bearish_factors=["Regulatory concerns"],
        )
        
        assert result.ticker == "AAPL"
        assert result.overall_score == 72.5
        assert result.overall_sentiment == SentimentLabel.BULLISH
        assert result.confidence == 0.85
        assert len(result.bullish_factors) == 2
        assert len(result.bearish_factors) == 1
        assert result.analyzed_at  # Auto-set
    
    def test_to_dict(self):
        result = AgentSentimentResult(
            ticker="AAPL",
            overall_score=72.5,
            overall_sentiment=SentimentLabel.BULLISH,
            confidence=0.85,
            rationale="Test",
        )
        
        d = result.to_dict()
        
        assert d["ticker"] == "AAPL"
        assert d["overall_score"] == 72.5
        assert d["overall_sentiment"] == "bullish"
        assert d["confidence"] == 0.85
        assert "analyzed_at" in d
    
    def test_from_dict(self):
        data = {
            "ticker": "MSFT",
            "overall_score": 65.0,
            "overall_sentiment": "slightly_bullish",
            "confidence": 0.7,
            "rationale": "Mixed signals",
            "article_analyses": [
                {
                    "headline": "Test",
                    "sentiment": "neutral",
                    "score": 50,
                    "key_factors": [],
                    "relevance": 0.5
                }
            ],
            "bullish_factors": ["Growth"],
            "bearish_factors": ["Competition"],
            "analyzed_at": "2026-02-05T10:00:00",
        }
        
        result = AgentSentimentResult.from_dict(data)
        
        assert result.ticker == "MSFT"
        assert result.overall_score == 65.0
        assert result.overall_sentiment == SentimentLabel.SLIGHTLY_BULLISH
        assert len(result.article_analyses) == 1
    
    def test_round_trip(self):
        """Test to_dict -> from_dict preserves data."""
        original = AgentSentimentResult(
            ticker="NVDA",
            overall_score=88.0,
            overall_sentiment=SentimentLabel.VERY_BULLISH,
            confidence=0.9,
            rationale="AI boom",
            article_analyses=[
                ArticleAnalysis(
                    headline="NVDA Surges",
                    sentiment=SentimentLabel.VERY_BULLISH,
                    score=92,
                    key_factors=["AI demand"],
                    relevance=0.95
                )
            ],
            bullish_factors=["AI", "Data centers"],
            bearish_factors=[],
        )
        
        restored = AgentSentimentResult.from_dict(original.to_dict())
        
        assert restored.ticker == original.ticker
        assert restored.overall_score == original.overall_score
        assert restored.overall_sentiment == original.overall_sentiment
        assert len(restored.article_analyses) == 1
        assert restored.article_analyses[0].headline == "NVDA Surges"


class TestSentimentCache:
    """Test SentimentCache."""
    
    @pytest.fixture
    def cache(self):
        """Create a temporary cache."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield SentimentCache(Path(tmpdir), ttl_hours=24)
    
    def test_get_miss(self, cache):
        result = cache.get("AAPL")
        assert result is None
    
    def test_set_and_get(self, cache):
        result = AgentSentimentResult(
            ticker="AAPL",
            overall_score=75.0,
            overall_sentiment=SentimentLabel.BULLISH,
            confidence=0.8,
            rationale="Test",
        )
        
        cache.set(result)
        loaded = cache.get("AAPL")
        
        assert loaded is not None
        assert loaded.ticker == "AAPL"
        assert loaded.overall_score == 75.0
    
    def test_case_insensitive(self, cache):
        result = AgentSentimentResult(
            ticker="AAPL",
            overall_score=75.0,
            overall_sentiment=SentimentLabel.BULLISH,
            confidence=0.8,
            rationale="Test",
        )
        
        cache.set(result)
        
        # Should find with different case
        assert cache.get("aapl") is not None
        assert cache.get("Aapl") is not None
    
    def test_expired_cache(self, cache):
        """Expired entries should return None."""
        result = AgentSentimentResult(
            ticker="AAPL",
            overall_score=75.0,
            overall_sentiment=SentimentLabel.BULLISH,
            confidence=0.8,
            rationale="Test",
            analyzed_at=(datetime.now() - timedelta(hours=48)).isoformat()
        )
        
        cache.set(result)
        loaded = cache.get("AAPL")
        
        # Should be None because it's older than TTL
        assert loaded is None
    
    def test_invalidate(self, cache):
        result = AgentSentimentResult(
            ticker="AAPL",
            overall_score=75.0,
            overall_sentiment=SentimentLabel.BULLISH,
            confidence=0.8,
            rationale="Test",
        )
        
        cache.set(result)
        assert cache.get("AAPL") is not None
        
        removed = cache.invalidate("AAPL")
        assert removed is True
        assert cache.get("AAPL") is None
    
    def test_invalidate_nonexistent(self, cache):
        removed = cache.invalidate("NONEXISTENT")
        assert removed is False
    
    def test_invalidate_all(self, cache):
        for ticker in ["AAPL", "MSFT", "GOOGL"]:
            result = AgentSentimentResult(
                ticker=ticker,
                overall_score=50.0,
                overall_sentiment=SentimentLabel.NEUTRAL,
                confidence=0.5,
                rationale="Test",
            )
            cache.set(result)
        
        count = cache.invalidate_all()
        assert count == 3
        
        assert cache.get("AAPL") is None
        assert cache.get("MSFT") is None
        assert cache.get("GOOGL") is None
    
    def test_stats(self, cache):
        result = AgentSentimentResult(
            ticker="AAPL",
            overall_score=75.0,
            overall_sentiment=SentimentLabel.BULLISH,
            confidence=0.8,
            rationale="Test",
        )
        cache.set(result)
        
        stats = cache.stats()
        
        assert stats["total"] == 1
        assert stats["fresh"] == 1
        assert stats["stale"] == 0
        assert stats["ttl_hours"] == 24


class TestAgenticSentimentAnalyzer:
    """Test AgenticSentimentAnalyzer."""
    
    @pytest.fixture
    def mock_client(self):
        """Create a mock Claude client."""
        client = MagicMock()
        client.is_available = True
        # analyze() must be AsyncMock since the code awaits it
        client.analyze = AsyncMock()
        return client
    
    @pytest.fixture
    def analyzer(self, mock_client):
        """Create an analyzer with mocked client."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("scoring.agentic_sentiment.get_sentiment_config") as mock_config:
                config = SentimentConfig()
                config.cache_dir = Path(tmpdir)
                mock_config.return_value = config
                
                analyzer = AgenticSentimentAnalyzer(client=mock_client)
                yield analyzer
    
    def test_is_available(self, analyzer, mock_client):
        assert analyzer.is_available is True
        
        mock_client.is_available = False
        assert analyzer.is_available is False
    
    def test_analyze_returns_result(self, analyzer, mock_client):
        """Test successful analysis."""
        mock_client.analyze.return_value = {
            "ticker": "AAPL",
            "overall_score": 72,
            "overall_sentiment": "bullish",
            "confidence": 0.85,
            "rationale": "Strong earnings report",
            "article_analyses": [
                {
                    "headline": "Apple beats earnings",
                    "sentiment": "bullish",
                    "score": 75,
                    "key_factors": ["Revenue beat"],
                    "relevance": 0.9
                }
            ],
            "bullish_factors": ["Earnings beat"],
            "bearish_factors": []
        }
        
        articles = [{"title": "Apple beats earnings", "summary": "Good", "source": "Reuters"}]
        result = analyzer.analyze("AAPL", articles, use_cache=False)
        
        assert result.ticker == "AAPL"
        assert result.overall_score == 72
        assert result.overall_sentiment == SentimentLabel.BULLISH
        assert result.confidence == 0.85
        assert len(result.article_analyses) == 1
    
    def test_analyze_empty_articles(self, analyzer, mock_client):
        """Empty articles should return neutral."""
        result = analyzer.analyze("AAPL", [], use_cache=False)
        
        assert result.overall_score == 50.0
        assert result.overall_sentiment == SentimentLabel.NEUTRAL
        assert "No news" in result.rationale
    
    def test_analyze_uses_cache(self, analyzer, mock_client):
        """Second call should hit cache."""
        mock_client.analyze.return_value = {
            "ticker": "AAPL",
            "overall_score": 72,
            "overall_sentiment": "bullish",
            "confidence": 0.85,
            "rationale": "Strong",
            "article_analyses": []
        }
        
        articles = [{"title": "Test", "summary": "Test"}]
        
        # First call - should hit LLM
        result1 = analyzer.analyze("AAPL", articles, use_cache=True)
        assert mock_client.analyze.call_count == 1
        
        # Second call - should hit cache
        result2 = analyzer.analyze("AAPL", articles, use_cache=True)
        assert mock_client.analyze.call_count == 1  # No additional call
        
        assert result1.overall_score == result2.overall_score
    
    def test_analyze_cache_bypass(self, analyzer, mock_client):
        """use_cache=False should always call LLM."""
        mock_client.analyze.return_value = {
            "ticker": "AAPL",
            "overall_score": 72,
            "overall_sentiment": "bullish",
            "confidence": 0.85,
            "rationale": "Strong",
            "article_analyses": []
        }
        
        articles = [{"title": "Test", "summary": "Test"}]
        
        analyzer.analyze("AAPL", articles, use_cache=False)
        analyzer.analyze("AAPL", articles, use_cache=False)
        
        assert mock_client.analyze.call_count == 2
    
    def test_analyze_llm_unavailable_raises(self, analyzer, mock_client):
        """Should raise when LLM unavailable and no cache."""
        mock_client.is_available = False
        
        articles = [{"title": "Test", "summary": "Test"}]
        
        with pytest.raises(RuntimeError, match="LLM unavailable"):
            analyzer.analyze("AAPL", articles, use_cache=True)
    
    def test_analyze_handles_llm_none_response(self, analyzer, mock_client):
        """Should raise when LLM returns None."""
        mock_client.analyze.return_value = None
        
        articles = [{"title": "Test", "summary": "Test"}]
        
        with pytest.raises(RuntimeError, match="no response"):
            analyzer.analyze("AAPL", articles, use_cache=False)
    
    def test_format_articles_truncates(self, analyzer, mock_client):
        """Long summaries should be truncated."""
        prompt = analyzer._build_prompt("AAPL", [
            {
                "title": "Test",
                "summary": "A" * 500,  # Long summary
                "source": "Test",
                "published": "2026-02-05"
            }
        ])
        
        # Should truncate summary
        assert "A" * 500 not in prompt
        assert "..." in prompt
    
    def test_parse_response_handles_variations(self, analyzer, mock_client):
        """Parser should handle sentiment label variations."""
        data = {
            "ticker": "AAPL",
            "overall_score": 72,
            "overall_sentiment": "BULLISH",  # Uppercase
            "confidence": 0.85,
            "rationale": "Strong",
            "article_analyses": [
                {
                    "headline": "Test",
                    "sentiment": "slightly-bullish",  # Hyphenated
                    "score": 60
                }
            ]
        }
        
        result = analyzer._parse_response(data, "AAPL")
        
        assert result.overall_sentiment == SentimentLabel.BULLISH
        assert result.article_analyses[0].sentiment == SentimentLabel.SLIGHTLY_BULLISH
    
    def test_get_cache_stats(self, analyzer):
        stats = analyzer.get_cache_stats()
        
        assert "total" in stats
        assert "fresh" in stats
        assert "stale" in stats
    
    def test_clear_cache(self, analyzer, mock_client):
        """Should clear all cached results."""
        mock_client.analyze.return_value = {
            "ticker": "AAPL",
            "overall_score": 72,
            "overall_sentiment": "bullish",
            "confidence": 0.85,
            "rationale": "Strong",
            "article_analyses": []
        }
        
        articles = [{"title": "Test", "summary": "Test"}]
        analyzer.analyze("AAPL", articles, use_cache=True)
        
        count = analyzer.clear_cache()
        assert count >= 1


class TestSystemPrompt:
    """Test the system prompt."""
    
    def test_prompt_contains_key_elements(self):
        assert "financial sentiment analyst" in SENTIMENT_AGENT_SYSTEM_PROMPT.lower()
        assert "very_bullish" in SENTIMENT_AGENT_SYSTEM_PROMPT.lower()
        assert "very_bearish" in SENTIMENT_AGENT_SYSTEM_PROMPT.lower()
        assert "confidence" in SENTIMENT_AGENT_SYSTEM_PROMPT.lower()
        assert "json" in SENTIMENT_AGENT_SYSTEM_PROMPT.lower()
    
    def test_prompt_has_scoring_guidelines(self):
        assert "85-100" in SENTIMENT_AGENT_SYSTEM_PROMPT
        assert "0-15" in SENTIMENT_AGENT_SYSTEM_PROMPT
