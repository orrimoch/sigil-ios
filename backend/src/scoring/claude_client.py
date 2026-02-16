"""
LLM Client for Sentiment Analysis (REC-171, REC-272)

Provides a robust wrapper around the LLM abstraction layer with:
- Multi-provider support (Anthropic, OpenAI, Google)
- Rate limiting
- Retry logic with exponential backoff
- Cost tracking
- Circuit breaker pattern

Provider selection is environment-based via LLM_PROVIDER env var.
"""

import os
import time
import json
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime, date
from pathlib import Path
from loguru import logger

# Import the LLM abstraction layer
try:
    from llm import get_llm_provider, LLMProvider, LLMProviderType, LLMResponse
    from llm.base import TokenUsage
    LLM_ABSTRACTION_AVAILABLE = True
except ImportError:
    LLM_ABSTRACTION_AVAILABLE = False
    logger.warning("LLM abstraction layer not available")

# Fallback to direct anthropic import for backward compatibility
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from .sentiment_config import get_sentiment_config, SentimentConfig


@dataclass
class DailyUsage:
    """Track daily API usage for cost controls."""
    date: date = field(default_factory=date.today)
    total_tokens: int = 0
    total_requests: int = 0
    estimated_cost_usd: float = 0.0
    
    def add_usage(self, tokens: TokenUsage, cost: float):
        """Add token usage to daily total."""
        self.total_tokens += tokens.total_tokens
        self.total_requests += 1
        self.estimated_cost_usd += cost


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
            if self.last_failure_time and \
               time.time() - self.last_failure_time >= self.recovery_timeout:
                self.state = self.HALF_OPEN
                return True
            return False
        
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
    LLM API client for sentiment analysis.
    
    Now supports multiple providers via LLM abstraction layer (REC-272):
    - Anthropic (Claude)
    - OpenAI (GPT)
    - Google (Gemini)
    
    Features:
    - Rate limiting
    - Automatic retries with exponential backoff
    - Circuit breaker for failure protection
    - Cost tracking with daily limits
    """
    
    def __init__(self, config: Optional[SentimentConfig] = None):
        self.config = config or get_sentiment_config()
        
        # Initialize LLM provider using abstraction layer
        self._provider: Optional[LLMProvider] = None
        if LLM_ABSTRACTION_AVAILABLE:
            try:
                self._provider = get_llm_provider()
                logger.info(f"Using LLM provider: {self._provider.provider_type.value}")
            except Exception as e:
                logger.warning(f"Failed to initialize LLM provider: {e}")
        
        # Fallback to direct Anthropic if abstraction not available
        self._anthropic_client = None
        if self._provider is None and ANTHROPIC_AVAILABLE and self.config.anthropic_api_key:
            self._anthropic_client = anthropic.Anthropic(api_key=self.config.anthropic_api_key)
            logger.info("Using fallback Anthropic client")
        
        # Rate limiting
        self.rate_limiter = RateLimiter(self.config.rate_limit_rpm)
        
        # Circuit breaker
        self.circuit_breaker = CircuitBreaker()
        
        # Usage tracking
        self._daily_usage = DailyUsage()
        self._usage_file = self.config.cache_dir / "usage.json"
        self._load_usage()
    
    @property
    def provider_name(self) -> str:
        """Get the current provider name."""
        if self._provider:
            return self._provider.provider_type.value
        return "anthropic-fallback"
    
    @property
    def is_available(self) -> bool:
        """Check if LLM API is available."""
        if self._provider:
            return self._provider.is_available and self.circuit_breaker.can_execute()
        return self._anthropic_client is not None and self.circuit_breaker.can_execute()
    
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
            "provider": self.provider_name,
            "total_tokens": self._daily_usage.total_tokens,
            "total_requests": self._daily_usage.total_requests,
            "estimated_cost_usd": round(self._daily_usage.estimated_cost_usd, 4),
            "daily_limit_usd": self.config.max_daily_spend_usd,
            "remaining_usd": round(
                self.config.max_daily_spend_usd - self._daily_usage.estimated_cost_usd, 4
            ),
            "circuit_breaker_state": self.circuit_breaker.state,
        }
    
    async def _call_api_via_provider(
        self,
        system_prompt: str,
        user_message: str,
        model: Optional[str] = None,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        """Call API using the LLM abstraction layer."""
        return await self._provider.generate(
            prompt=user_message,
            system_prompt=system_prompt,
            model=model,
            max_tokens=max_tokens,
        )
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    def _call_api_anthropic_fallback(
        self,
        system_prompt: str,
        user_message: str,
        model: Optional[str] = None,
        max_tokens: int = 1024,
    ) -> tuple[str, TokenUsage]:
        """Fallback: Direct Anthropic API call."""
        if not self._anthropic_client:
            raise RuntimeError("Anthropic client not initialized. Check ANTHROPIC_API_KEY.")
        
        model = model or self.config.claude_model
        
        self.rate_limiter.wait_if_needed()
        
        response = self._anthropic_client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        
        text = response.content[0].text if response.content else ""
        usage = TokenUsage(
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )
        
        return text, usage
    
    async def analyze(
        self,
        system_prompt: str,
        user_message: str,
        model: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze text using LLM and return parsed JSON response.
        
        Args:
            system_prompt: System instructions
            user_message: The content to analyze
            model: Optional model override
        
        Returns:
            Parsed JSON response or None if failed
        """
        if not self.is_available:
            logger.warning("LLM API not available")
            return None
        
        if not self._check_daily_limit():
            logger.warning("Daily spend limit reached, skipping LLM analysis")
            return None
        
        try:
            self.rate_limiter.wait_if_needed()
            
            if self._provider:
                # Use LLM abstraction layer
                response = await self._call_api_via_provider(
                    system_prompt=system_prompt,
                    user_message=user_message,
                    model=model,
                )
                
                self.circuit_breaker.record_success()
                
                # Track usage
                cost = self._provider.estimate_cost(response.usage)
                self._daily_usage.add_usage(response.usage, cost)
                self._save_usage()
                
                logger.debug(
                    f"LLM API call ({self.provider_name}): {response.usage.input_tokens} in, "
                    f"{response.usage.output_tokens} out, ${cost:.4f}"
                )
                
                # Parse JSON response
                return self._parse_json(response.text)
            else:
                # Fallback to direct Anthropic call
                model = model or self.config.claude_model
                response_text, usage = self._call_api_anthropic_fallback(
                    system_prompt=system_prompt,
                    user_message=user_message,
                    model=model,
                )
                
                self.circuit_breaker.record_success()
                
                # Estimate cost (Sonnet pricing)
                cost = (usage.input_tokens / 1_000_000) * 3.0 + (usage.output_tokens / 1_000_000) * 15.0
                self._daily_usage.add_usage(usage, cost)
                self._save_usage()
                
                logger.debug(
                    f"Anthropic API call: {usage.input_tokens} in, {usage.output_tokens} out, ${cost:.4f}"
                )
                
                return self._parse_json(response_text)
            
        except Exception as e:
            logger.error(f"LLM API error: {e}")
            self.circuit_breaker.record_failure()
            # MEDIUM FIX SE-003: Persist usage before returning on failure
            self._save_usage()
            return None
    
    def _parse_json(self, text: str) -> Optional[Dict[str, Any]]:
        """Parse JSON from LLM response."""
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM response as JSON: {e}")
            logger.debug(f"Raw response: {text[:500]}")
            return None
    
    def health_check(self) -> Dict[str, Any]:
        """Perform a health check on the LLM API."""
        result = {
            "available": False,
            "provider": self.provider_name,
            "circuit_breaker": self.circuit_breaker.state,
            "usage": self.get_usage_stats(),
        }
        
        if self._provider:
            health = self._provider.health_check()
            result.update(health)
        elif self._anthropic_client:
            result["api_key_set"] = True
            result["package_installed"] = ANTHROPIC_AVAILABLE
            result["model"] = self.config.claude_model
            
            try:
                response = self._anthropic_client.messages.create(
                    model=self.config.claude_model,
                    max_tokens=10,
                    messages=[{"role": "user", "content": "Say 'ok'"}],
                )
                if response.content and "ok" in response.content[0].text.lower():
                    result["available"] = True
            except Exception as e:
                result["error"] = str(e)
        else:
            result["error"] = "No LLM provider configured"
        
        return result


# Global client instance (lazy-loaded)
_client: Optional[ClaudeClient] = None


def get_claude_client() -> ClaudeClient:
    """Get the global LLM client (lazy-loaded)."""
    global _client
    if _client is None:
        _client = ClaudeClient()
    return _client


def reload_claude_client() -> ClaudeClient:
    """Force reload of LLM client."""
    global _client
    _client = ClaudeClient()
    return _client


# CLI for testing
if __name__ == "__main__":
    import sys
    logger.add(sys.stderr, level="DEBUG")
    
    print("\n=== LLM Client Test ===\n")
    
    client = get_claude_client()
    
    print(f"Provider: {client.provider_name}")
    print("Health check:")
    health = client.health_check()
    for key, value in health.items():
        print(f"  {key}: {value}")
    
    if health.get("available"):
        print(f"\n✅ LLM API is working ({client.provider_name})!")
    else:
        print(f"\n❌ LLM API not available: {health.get('error', 'Unknown')}")
