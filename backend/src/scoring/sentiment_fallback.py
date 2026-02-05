"""
Sentiment Fallback Manager (REC-175)

Provides graceful degradation for sentiment analysis:
1. LLM (Claude) - Primary, most accurate
2. Cache (24h) - Fast, free
3. Keyword - Fallback, always available
4. Neutral (50) - Last resort

Also provides cost tracking and budget management.
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime, date
from pathlib import Path
import json
from loguru import logger

from .sentiment_config import get_sentiment_config, SentimentModel
from .sentiment_score import SentimentScoreResult


@dataclass
class FallbackStats:
    """Track fallback usage statistics."""
    date: date = field(default_factory=date.today)
    llm_calls: int = 0
    cache_hits: int = 0
    keyword_fallbacks: int = 0
    neutral_fallbacks: int = 0
    total_requests: int = 0
    
    @property
    def cache_hit_rate(self) -> float:
        """Calculate cache hit rate."""
        if self.total_requests == 0:
            return 0.0
        return self.cache_hits / self.total_requests
    
    @property
    def llm_rate(self) -> float:
        """Calculate LLM usage rate."""
        if self.total_requests == 0:
            return 0.0
        return self.llm_calls / self.total_requests
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "date": str(self.date),
            "llm_calls": self.llm_calls,
            "cache_hits": self.cache_hits,
            "keyword_fallbacks": self.keyword_fallbacks,
            "neutral_fallbacks": self.neutral_fallbacks,
            "total_requests": self.total_requests,
            "cache_hit_rate": round(self.cache_hit_rate, 3),
            "llm_rate": round(self.llm_rate, 3),
        }


class FallbackManager:
    """
    Manages sentiment analysis fallback chain.
    
    Priority:
    1. Check cache first (free, fast)
    2. Try LLM analysis (paid, accurate)
    3. Fall back to keyword (free, less accurate)
    4. Return neutral if all fail (always works)
    
    Also tracks usage statistics and manages budget.
    """
    
    def __init__(self, stats_file: Optional[Path] = None):
        self.config = get_sentiment_config()
        self.stats_file = stats_file or (self.config.cache_dir / "fallback_stats.json")
        self._stats = self._load_stats()
    
    def _load_stats(self) -> FallbackStats:
        """Load today's stats from disk."""
        if self.stats_file.exists():
            try:
                data = json.loads(self.stats_file.read_text())
                if data.get("date") == str(date.today()):
                    return FallbackStats(
                        date=date.today(),
                        llm_calls=data.get("llm_calls", 0),
                        cache_hits=data.get("cache_hits", 0),
                        keyword_fallbacks=data.get("keyword_fallbacks", 0),
                        neutral_fallbacks=data.get("neutral_fallbacks", 0),
                        total_requests=data.get("total_requests", 0),
                    )
            except Exception as e:
                logger.warning(f"Failed to load fallback stats: {e}")
        
        return FallbackStats()
    
    def _save_stats(self):
        """Persist stats to disk."""
        self.stats_file.parent.mkdir(parents=True, exist_ok=True)
        self.stats_file.write_text(json.dumps(self._stats.to_dict(), indent=2))
    
    def record_llm_call(self):
        """Record an LLM API call."""
        self._ensure_today()
        self._stats.llm_calls += 1
        self._stats.total_requests += 1
        self._save_stats()
    
    def record_cache_hit(self):
        """Record a cache hit."""
        self._ensure_today()
        self._stats.cache_hits += 1
        self._stats.total_requests += 1
        self._save_stats()
    
    def record_keyword_fallback(self):
        """Record a keyword fallback."""
        self._ensure_today()
        self._stats.keyword_fallbacks += 1
        self._stats.total_requests += 1
        self._save_stats()
    
    def record_neutral_fallback(self):
        """Record a neutral fallback."""
        self._ensure_today()
        self._stats.neutral_fallbacks += 1
        self._stats.total_requests += 1
        self._save_stats()
    
    def _ensure_today(self):
        """Reset stats if it's a new day."""
        if self._stats.date != date.today():
            self._stats = FallbackStats()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current fallback statistics."""
        self._ensure_today()
        return self._stats.to_dict()
    
    def get_recommendation(self) -> str:
        """
        Get a recommendation based on current stats.
        
        Returns:
            String recommendation for optimization
        """
        stats = self._stats
        
        if stats.total_requests < 10:
            return "Not enough data yet. Run more analyses."
        
        recommendations = []
        
        # Check cache hit rate
        if stats.cache_hit_rate < 0.3:
            recommendations.append(
                f"Cache hit rate is low ({stats.cache_hit_rate:.0%}). "
                "Consider running batch analysis to pre-populate cache."
            )
        elif stats.cache_hit_rate > 0.7:
            recommendations.append(
                f"Cache hit rate is good ({stats.cache_hit_rate:.0%}). "
                "Cost optimization working well."
            )
        
        # Check keyword fallbacks
        if stats.keyword_fallbacks > stats.total_requests * 0.2:
            recommendations.append(
                f"High keyword fallback rate ({stats.keyword_fallbacks}/{stats.total_requests}). "
                "Check API key and rate limits."
            )
        
        # Check neutral fallbacks
        if stats.neutral_fallbacks > 0:
            recommendations.append(
                f"Had {stats.neutral_fallbacks} neutral fallbacks. "
                "Some analyses completely failed."
            )
        
        return " ".join(recommendations) if recommendations else "System operating normally."


# Global manager instance
_manager: Optional[FallbackManager] = None


def get_fallback_manager() -> FallbackManager:
    """Get the global fallback manager."""
    global _manager
    if _manager is None:
        _manager = FallbackManager()
    return _manager


def get_fallback_stats() -> Dict[str, Any]:
    """Get current fallback statistics."""
    return get_fallback_manager().get_stats()


def check_system_health() -> Dict[str, Any]:
    """
    Check overall sentiment system health.
    
    Returns:
        Dict with health status and metrics
    """
    from .sentiment_config import get_sentiment_config
    from .claude_client import get_claude_client
    from .agentic_sentiment import get_agentic_analyzer
    
    config = get_sentiment_config()
    client = get_claude_client()
    analyzer = get_agentic_analyzer()
    fallback = get_fallback_manager()
    
    health = {
        "status": "healthy",
        "issues": [],
        "config": {
            "model": config.model.value,
            "llm_enabled": config.is_llm_enabled,
            "cache_ttl_hours": config.cache_ttl_hours,
        },
        "api": {
            "available": client.is_available,
            "circuit_breaker": client.circuit_breaker.state,
            "usage": client.get_usage_stats(),
        },
        "cache": analyzer.get_cache_stats(),
        "fallback": fallback.get_stats(),
    }
    
    # Check for issues
    if not client.is_available:
        health["status"] = "degraded"
        health["issues"].append("LLM API not available")
    
    if client.circuit_breaker.state != "closed":
        health["status"] = "degraded"
        health["issues"].append(f"Circuit breaker is {client.circuit_breaker.state}")
    
    usage = client.get_usage_stats()
    if usage["remaining_usd"] < 1.0:
        health["status"] = "warning"
        health["issues"].append(f"Low API budget: ${usage['remaining_usd']:.2f} remaining")
    
    return health


# CLI for testing
if __name__ == "__main__":
    import sys
    logger.add(sys.stderr, level="DEBUG")
    
    print("\n=== Sentiment Fallback Manager Test ===\n")
    
    manager = get_fallback_manager()
    
    # Simulate some usage
    manager.record_cache_hit()
    manager.record_cache_hit()
    manager.record_llm_call()
    manager.record_keyword_fallback()
    
    print("Stats:", json.dumps(manager.get_stats(), indent=2))
    print("\nRecommendation:", manager.get_recommendation())
    
    print("\n--- System Health ---")
    from dotenv import load_dotenv
    load_dotenv()
    
    health = check_system_health()
    print(json.dumps(health, indent=2))
