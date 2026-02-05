"""
Claude API Client for Sentiment Analysis (REC-171)

Provides a robust wrapper around the Anthropic API with:
- Rate limiting
- Retry logic with exponential backoff
- Cost tracking
- Circuit breaker pattern
"""

import os
import time
import json
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime, date
from pathlib import Path
from loguru import logger

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    logger.warning("anthropic package not installed. Run: pip install anthropic")

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from .sentiment_config import get_sentiment_config, SentimentConfig


@dataclass
class TokenUsage:
    """Track token usage for cost estimation."""
    input_tokens: int = 0
    output_tokens: int = 0
    
    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens
    
    def estimated_cost_usd(self, model: str = "claude-sonnet-4-20250514") -> float:
        """Estimate cost based on model pricing."""
        # Pricing as of Feb 2026 (per 1M tokens)
        pricing = {
            "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0},
            "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
            "claude-3-5-sonnet-20241022": {"input": 3.0, "output": 15.0},
        }
        
        rates = pricing.get(model, pricing["claude-sonnet-4-20250514"])
        input_cost = (self.input_tokens / 1_000_000) * rates["input"]
        output_cost = (self.output_tokens / 1_000_000) * rates["output"]
        return input_cost + output_cost


@dataclass
class DailyUsage:
    """Track daily API usage for cost controls."""
    date: date = field(default_factory=date.today)
    total_tokens: int = 0
    total_requests: int = 0
    estimated_cost_usd: float = 0.0
    
    def add_usage(self, tokens: TokenUsage, model: str):
        """Add token usage to daily total."""
        self.total_tokens += tokens.total_tokens
        self.total_requests += 1
        self.estimated_cost_usd += tokens.estimated_cost_usd(model)


class RateLimiter:
    """Simple rate limiter using token bucket algorithm."""
    
    def __init__(self, requests_per_minute: int = 50):
        self.rpm = requests_per_minute
        self.interval = 60.0 / requests_per_minute
        self.last_request_time = 0.0
    
    def wait_if_needed(self):
        """Block until we can make another request."""
        now = time.time()
        elapsed = now - self.last_request_time
        
        if elapsed < self.interval:
            sleep_time = self.interval - elapsed
            logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s")
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()


class CircuitBreaker:
    """Circuit breaker to prevent cascade failures."""
    
    CLOSED = "closed"  # Normal operation
    OPEN = "open"      # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.state = self.CLOSED
        self.failures = 0
        self.last_failure_time: Optional[float] = None
    
    def can_execute(self) -> bool:
        """Check if we can execute a request."""
        if self.state == self.CLOSED:
            return True
        
        if self.state == self.OPEN:
            # Check if recovery timeout passed
            if self.last_failure_time and \
               time.time() - self.last_failure_time >= self.recovery_timeout:
                self.state = self.HALF_OPEN
                return True
            return False
        
        # HALF_OPEN: allow one request to test
        return True
    
    def record_success(self):
        """Record a successful request."""
        self.failures = 0
        self.state = self.CLOSED
    
    def record_failure(self):
        """Record a failed request."""
        self.failures += 1
        self.last_failure_time = time.time()
        
        if self.failures >= self.failure_threshold:
            self.state = self.OPEN
            logger.warning(f"Circuit breaker OPEN after {self.failures} failures")


class ClaudeClient:
    """
    Claude API client for sentiment analysis.
    
    Features:
    - Rate limiting
    - Automatic retries with exponential backoff
    - Circuit breaker for failure protection
    - Cost tracking with daily limits
    """
    
    def __init__(self, config: Optional[SentimentConfig] = None):
        self.config = config or get_sentiment_config()
        
        # Initialize Anthropic client
        self._client: Optional[anthropic.Anthropic] = None
        if ANTHROPIC_AVAILABLE and self.config.anthropic_api_key:
            self._client = anthropic.Anthropic(
                api_key=self.config.anthropic_api_key
            )
        
        # Rate limiting
        self.rate_limiter = RateLimiter(self.config.rate_limit_rpm)
        
        # Circuit breaker
        self.circuit_breaker = CircuitBreaker()
        
        # Usage tracking
        self._daily_usage = DailyUsage()
        self._usage_file = self.config.cache_dir / "usage.json"
        self._load_usage()
    
    @property
    def is_available(self) -> bool:
        """Check if Claude API is available."""
        return self._client is not None and self.circuit_breaker.can_execute()
    
    def _load_usage(self):
        """Load today's usage from disk."""
        if self._usage_file.exists():
            try:
                data = json.loads(self._usage_file.read_text())
                if data.get("date") == str(date.today()):
                    self._daily_usage = DailyUsage(
                        date=date.today(),
                        total_tokens=data.get("total_tokens", 0),
                        total_requests=data.get("total_requests", 0),
                        estimated_cost_usd=data.get("estimated_cost_usd", 0.0),
                    )
            except Exception as e:
                logger.warning(f"Failed to load usage data: {e}")
    
    def _save_usage(self):
        """Persist usage to disk."""
        self._usage_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "date": str(self._daily_usage.date),
            "total_tokens": self._daily_usage.total_tokens,
            "total_requests": self._daily_usage.total_requests,
            "estimated_cost_usd": self._daily_usage.estimated_cost_usd,
        }
        self._usage_file.write_text(json.dumps(data, indent=2))
    
    def _check_daily_limit(self) -> bool:
        """Check if we're within daily spend limit."""
        # Reset if new day
        if self._daily_usage.date != date.today():
            self._daily_usage = DailyUsage()
        
        if self._daily_usage.estimated_cost_usd >= self.config.max_daily_spend_usd:
            logger.warning(
                f"Daily spend limit reached: ${self._daily_usage.estimated_cost_usd:.2f} >= "
                f"${self.config.max_daily_spend_usd:.2f}"
            )
            return False
        return True
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """Get current usage statistics."""
        return {
            "date": str(self._daily_usage.date),
            "total_tokens": self._daily_usage.total_tokens,
            "total_requests": self._daily_usage.total_requests,
            "estimated_cost_usd": round(self._daily_usage.estimated_cost_usd, 4),
            "daily_limit_usd": self.config.max_daily_spend_usd,
            "remaining_usd": round(
                self.config.max_daily_spend_usd - self._daily_usage.estimated_cost_usd, 4
            ),
            "circuit_breaker_state": self.circuit_breaker.state,
        }
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((anthropic.RateLimitError, anthropic.APIConnectionError)),
    )
    def _call_api(
        self,
        system_prompt: str,
        user_message: str,
        model: Optional[str] = None,
        max_tokens: int = 1024,
    ) -> tuple[str, TokenUsage]:
        """
        Make a Claude API call with retries.
        
        Returns:
            Tuple of (response_text, token_usage)
        """
        if not self._client:
            raise RuntimeError("Claude client not initialized. Check ANTHROPIC_API_KEY.")
        
        model = model or self.config.claude_model
        
        # Rate limit
        self.rate_limiter.wait_if_needed()
        
        # Make the call
        response = self._client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        
        # Extract response
        text = response.content[0].text if response.content else ""
        
        # Track usage
        usage = TokenUsage(
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )
        
        return text, usage
    
    def analyze(
        self,
        system_prompt: str,
        user_message: str,
        model: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze text using Claude and return parsed JSON response.
        
        Args:
            system_prompt: System instructions for Claude
            user_message: The content to analyze
            model: Optional model override
        
        Returns:
            Parsed JSON response or None if failed
        """
        if not self.is_available:
            logger.warning("Claude API not available")
            return None
        
        if not self._check_daily_limit():
            logger.warning("Daily spend limit reached, skipping LLM analysis")
            return None
        
        model = model or self.config.claude_model
        
        try:
            response_text, usage = self._call_api(
                system_prompt=system_prompt,
                user_message=user_message,
                model=model,
            )
            
            # Record success
            self.circuit_breaker.record_success()
            
            # Track usage
            self._daily_usage.add_usage(usage, model)
            self._save_usage()
            
            logger.debug(
                f"Claude API call: {usage.input_tokens} in, {usage.output_tokens} out, "
                f"${usage.estimated_cost_usd(model):.4f}"
            )
            
            # Parse JSON response
            try:
                # Handle potential markdown wrapping
                text = response_text.strip()
                if text.startswith("```json"):
                    text = text[7:]
                if text.startswith("```"):
                    text = text[3:]
                if text.endswith("```"):
                    text = text[:-3]
                
                return json.loads(text.strip())
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse Claude response as JSON: {e}")
                logger.debug(f"Raw response: {response_text[:500]}")
                return None
            
        except anthropic.AuthenticationError as e:
            logger.error(f"Claude authentication error: {e}")
            self.circuit_breaker.record_failure()
            return None
        except anthropic.RateLimitError as e:
            logger.warning(f"Claude rate limit hit: {e}")
            self.circuit_breaker.record_failure()
            return None
        except anthropic.APIError as e:
            logger.error(f"Claude API error: {e}")
            self.circuit_breaker.record_failure()
            return None
        except Exception as e:
            logger.error(f"Unexpected error calling Claude: {e}")
            self.circuit_breaker.record_failure()
            return None
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check on the Claude API.
        
        Returns:
            Dict with status and details
        """
        result = {
            "available": False,
            "api_key_set": self.config.anthropic_api_key is not None,
            "package_installed": ANTHROPIC_AVAILABLE,
            "circuit_breaker": self.circuit_breaker.state,
            "model": self.config.claude_model,
            "usage": self.get_usage_stats(),
        }
        
        if not ANTHROPIC_AVAILABLE:
            result["error"] = "anthropic package not installed"
            return result
        
        if not self.config.anthropic_api_key:
            result["error"] = "ANTHROPIC_API_KEY not set"
            return result
        
        if not self.circuit_breaker.can_execute():
            result["error"] = "Circuit breaker open"
            return result
        
        # Try a minimal API call
        try:
            response, usage = self._call_api(
                system_prompt="You are a helpful assistant.",
                user_message="Say 'ok' and nothing else.",
                max_tokens=10,
            )
            
            if "ok" in response.lower():
                result["available"] = True
                result["latency_ms"] = "fast"  # We don't measure precisely
            else:
                result["error"] = f"Unexpected response: {response}"
            
        except Exception as e:
            result["error"] = str(e)
        
        return result


# Global client instance (lazy-loaded)
_client: Optional[ClaudeClient] = None


def get_claude_client() -> ClaudeClient:
    """Get the global Claude client (lazy-loaded)."""
    global _client
    if _client is None:
        _client = ClaudeClient()
    return _client


def reload_claude_client() -> ClaudeClient:
    """Force reload of Claude client."""
    global _client
    _client = ClaudeClient()
    return _client


# CLI for testing
if __name__ == "__main__":
    import sys
    logger.add(sys.stderr, level="DEBUG")
    
    print("\n=== Claude Client Test ===\n")
    
    client = get_claude_client()
    
    print("Health check:")
    health = client.health_check()
    for key, value in health.items():
        print(f"  {key}: {value}")
    
    if health["available"]:
        print("\n✅ Claude API is working!")
    else:
        print(f"\n❌ Claude API not available: {health.get('error', 'Unknown')}")
