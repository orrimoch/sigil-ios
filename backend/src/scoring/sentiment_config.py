"""
Sentiment Analysis Configuration (REC-171)

Manages settings for keyword vs LLM-based sentiment analysis.
Environment variables control the behavior.
"""

import os
from enum import Enum
from dataclasses import dataclass
from typing import Optional
from pathlib import Path
from loguru import logger


class SentimentModel(str, Enum):
    """Available sentiment analysis models."""
    KEYWORD = "keyword"   # Original keyword-based (free, fast, less accurate)
    LLM = "llm"          # Claude-powered (paid, slower, more accurate)
    HYBRID = "hybrid"     # LLM with keyword fallback


@dataclass
class SentimentConfig:
    """Configuration for sentiment analysis."""
    
    # Model selection
    model: SentimentModel = SentimentModel.KEYWORD
    
    # Claude API settings
    anthropic_api_key: Optional[str] = None
    claude_model: str = "claude-3-5-haiku-20241022"  # Default to Haiku for cost efficiency
    claude_model_fallback: str = "claude-3-haiku-20240307"  # Cheaper for simple cases
    
    # Rate limiting
    rate_limit_rpm: int = 50  # Requests per minute
    max_retries: int = 3
    retry_delay_seconds: float = 1.0
    
    # Caching
    cache_ttl_hours: int = 24
    cache_dir: Path = Path(__file__).parent.parent.parent / "data" / "sentiment_cache"
    
    # Analysis settings
    max_articles_per_stock: int = 10
    min_articles_for_llm: int = 1  # Below this, use keyword fallback
    
    # Cost controls
    max_daily_spend_usd: float = 10.0  # Circuit breaker
    
    def __post_init__(self):
        """Validate configuration."""
        if self.model in (SentimentModel.LLM, SentimentModel.HYBRID):
            if not self.anthropic_api_key:
                logger.warning(
                    f"SENTIMENT_MODEL={self.model.value} but ANTHROPIC_API_KEY not set. "
                    "Falling back to keyword model."
                )
                self.model = SentimentModel.KEYWORD
    
    @property
    def is_llm_enabled(self) -> bool:
        """Check if LLM analysis is available."""
        return (
            self.model in (SentimentModel.LLM, SentimentModel.HYBRID) and
            self.anthropic_api_key is not None
        )


def load_sentiment_config() -> SentimentConfig:
    """
    Load sentiment configuration from environment variables.
    
    Environment Variables:
        ANTHROPIC_API_KEY: Claude API key (required for LLM mode)
        SENTIMENT_MODEL: keyword | llm | hybrid (default: keyword)
        SENTIMENT_CLAUDE_MODEL: Claude model to use (default: claude-3-5-haiku-20241022)
        SENTIMENT_CACHE_TTL: Cache TTL in hours (default: 24)
        SENTIMENT_RATE_LIMIT: Requests per minute (default: 50)
        SENTIMENT_MAX_ARTICLES: Max articles per stock (default: 10)
        SENTIMENT_MAX_DAILY_SPEND: Max daily spend in USD (default: 10.0)
    """
    # Get model selection
    model_str = os.environ.get("SENTIMENT_MODEL", "keyword").lower()
    try:
        model = SentimentModel(model_str)
    except ValueError:
        logger.warning(f"Invalid SENTIMENT_MODEL '{model_str}', defaulting to keyword")
        model = SentimentModel.KEYWORD
    
    # Get API key
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    
    # Build config
    config = SentimentConfig(
        model=model,
        anthropic_api_key=api_key,
        claude_model=os.environ.get("SENTIMENT_CLAUDE_MODEL", "claude-3-5-haiku-20241022"),
        cache_ttl_hours=int(os.environ.get("SENTIMENT_CACHE_TTL", "24")),
        rate_limit_rpm=int(os.environ.get("SENTIMENT_RATE_LIMIT", "50")),
        max_articles_per_stock=int(os.environ.get("SENTIMENT_MAX_ARTICLES", "10")),
        max_daily_spend_usd=float(os.environ.get("SENTIMENT_MAX_DAILY_SPEND", "10.0")),
    )
    
    logger.info(
        f"Sentiment config loaded: model={config.model.value}, "
        f"llm_enabled={config.is_llm_enabled}, "
        f"cache_ttl={config.cache_ttl_hours}h"
    )
    
    return config


# Global config instance (lazy-loaded)
_config: Optional[SentimentConfig] = None


def get_sentiment_config() -> SentimentConfig:
    """Get the global sentiment config (lazy-loaded)."""
    global _config
    if _config is None:
        _config = load_sentiment_config()
    return _config


def reload_sentiment_config() -> SentimentConfig:
    """Force reload of sentiment config from environment."""
    global _config
    _config = load_sentiment_config()
    return _config


# CLI for testing
if __name__ == "__main__":
    import sys
    logger.add(sys.stderr, level="DEBUG")
    
    print("\n=== Sentiment Config Test ===\n")
    
    config = load_sentiment_config()
    print(f"Model: {config.model.value}")
    print(f"LLM Enabled: {config.is_llm_enabled}")
    print(f"Claude Model: {config.claude_model}")
    print(f"Cache TTL: {config.cache_ttl_hours}h")
    print(f"Rate Limit: {config.rate_limit_rpm} RPM")
    print(f"Max Articles: {config.max_articles_per_stock}")
    print(f"API Key Set: {config.anthropic_api_key is not None}")
    
    print("\n✅ Config loaded successfully!")
