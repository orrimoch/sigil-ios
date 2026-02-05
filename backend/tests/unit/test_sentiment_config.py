"""
Tests for sentiment configuration (REC-171)
"""

import os
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from scoring.sentiment_config import (
    SentimentConfig,
    SentimentModel,
    load_sentiment_config,
    get_sentiment_config,
    reload_sentiment_config,
)


class TestSentimentModel:
    """Test SentimentModel enum."""
    
    def test_keyword_model(self):
        assert SentimentModel.KEYWORD.value == "keyword"
    
    def test_llm_model(self):
        assert SentimentModel.LLM.value == "llm"
    
    def test_hybrid_model(self):
        assert SentimentModel.HYBRID.value == "hybrid"


class TestSentimentConfig:
    """Test SentimentConfig dataclass."""
    
    def test_default_config(self):
        config = SentimentConfig()
        assert config.model == SentimentModel.KEYWORD
        assert config.anthropic_api_key is None
        assert config.claude_model == "claude-sonnet-4-20250514"
        assert config.cache_ttl_hours == 24
        assert config.rate_limit_rpm == 50
    
    def test_llm_without_api_key_falls_back(self):
        """LLM model without API key should fall back to keyword."""
        config = SentimentConfig(model=SentimentModel.LLM, anthropic_api_key=None)
        assert config.model == SentimentModel.KEYWORD
    
    def test_llm_with_api_key_works(self):
        """LLM model with API key should stay as LLM."""
        config = SentimentConfig(model=SentimentModel.LLM, anthropic_api_key="sk-test")
        assert config.model == SentimentModel.LLM
    
    def test_is_llm_enabled_keyword(self):
        config = SentimentConfig(model=SentimentModel.KEYWORD)
        assert not config.is_llm_enabled
    
    def test_is_llm_enabled_llm_with_key(self):
        config = SentimentConfig(model=SentimentModel.LLM, anthropic_api_key="sk-test")
        assert config.is_llm_enabled
    
    def test_is_llm_enabled_hybrid_with_key(self):
        config = SentimentConfig(model=SentimentModel.HYBRID, anthropic_api_key="sk-test")
        assert config.is_llm_enabled


class TestLoadSentimentConfig:
    """Test loading config from environment."""
    
    def test_default_loads_keyword(self):
        with patch.dict(os.environ, {}, clear=True):
            config = load_sentiment_config()
            assert config.model == SentimentModel.KEYWORD
    
    def test_env_sentiment_model_llm(self):
        with patch.dict(os.environ, {
            "SENTIMENT_MODEL": "llm",
            "ANTHROPIC_API_KEY": "sk-test-key"
        }, clear=True):
            config = load_sentiment_config()
            assert config.model == SentimentModel.LLM
            assert config.anthropic_api_key == "sk-test-key"
    
    def test_env_sentiment_model_hybrid(self):
        with patch.dict(os.environ, {
            "SENTIMENT_MODEL": "hybrid",
            "ANTHROPIC_API_KEY": "sk-test"
        }, clear=True):
            config = load_sentiment_config()
            assert config.model == SentimentModel.HYBRID
    
    def test_invalid_model_defaults_to_keyword(self):
        with patch.dict(os.environ, {"SENTIMENT_MODEL": "invalid"}, clear=True):
            config = load_sentiment_config()
            assert config.model == SentimentModel.KEYWORD
    
    def test_env_cache_ttl(self):
        with patch.dict(os.environ, {"SENTIMENT_CACHE_TTL": "48"}, clear=True):
            config = load_sentiment_config()
            assert config.cache_ttl_hours == 48
    
    def test_env_rate_limit(self):
        with patch.dict(os.environ, {"SENTIMENT_RATE_LIMIT": "100"}, clear=True):
            config = load_sentiment_config()
            assert config.rate_limit_rpm == 100
    
    def test_env_max_articles(self):
        with patch.dict(os.environ, {"SENTIMENT_MAX_ARTICLES": "20"}, clear=True):
            config = load_sentiment_config()
            assert config.max_articles_per_stock == 20
    
    def test_env_max_daily_spend(self):
        with patch.dict(os.environ, {"SENTIMENT_MAX_DAILY_SPEND": "25.0"}, clear=True):
            config = load_sentiment_config()
            assert config.max_daily_spend_usd == 25.0
    
    def test_env_claude_model(self):
        with patch.dict(os.environ, {
            "SENTIMENT_CLAUDE_MODEL": "claude-3-haiku-20240307"
        }, clear=True):
            config = load_sentiment_config()
            assert config.claude_model == "claude-3-haiku-20240307"


class TestGetSentimentConfig:
    """Test global config getter."""
    
    def test_returns_config(self):
        config = get_sentiment_config()
        assert isinstance(config, SentimentConfig)
    
    def test_reload_picks_up_changes(self):
        # First load
        with patch.dict(os.environ, {"SENTIMENT_MODEL": "keyword"}, clear=True):
            reload_sentiment_config()
            config1 = get_sentiment_config()
            assert config1.model == SentimentModel.KEYWORD
        
        # Reload with new env
        with patch.dict(os.environ, {
            "SENTIMENT_MODEL": "llm",
            "ANTHROPIC_API_KEY": "sk-new"
        }, clear=True):
            config2 = reload_sentiment_config()
            assert config2.model == SentimentModel.LLM
