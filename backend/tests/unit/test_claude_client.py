"""
Tests for Claude API client (REC-171)
"""

import os
import json
import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from pathlib import Path
from datetime import date
import tempfile

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from scoring.claude_client import (
    DailyUsage,
    RateLimiter,
    CircuitBreaker,
    ClaudeClient,
    get_claude_client,
    reload_claude_client,
)

# REC-272: Import TokenUsage from LLM base module
try:
    from llm.base import TokenUsage
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False
    from dataclasses import dataclass
    @dataclass
    class TokenUsage:
        input_tokens: int = 0
        output_tokens: int = 0
        @property
        def total_tokens(self):
            return self.input_tokens + self.output_tokens

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

from scoring.sentiment_config import SentimentConfig, SentimentModel


class TestTokenUsage:
    """Test TokenUsage dataclass."""
    
    def test_total_tokens(self):
        usage = TokenUsage(input_tokens=100, output_tokens=50)
        assert usage.total_tokens == 150
    
    @pytest.mark.skipif(not LLM_AVAILABLE, reason="LLM module not available")
    def test_estimated_cost_via_provider(self):
        """Test cost estimation via provider (REC-272)."""
        from llm.anthropic_provider import AnthropicProvider
        from llm.base import LLMConfig, LLMProviderType
        
        config = LLMConfig(provider=LLMProviderType.ANTHROPIC)
        provider = AnthropicProvider(config)
        
        usage = TokenUsage(input_tokens=1_000_000, output_tokens=100_000)
        cost = provider.estimate_cost(usage)
        
        # Default is Haiku: $1/M input + $5/M output = 1.0 + 0.5 = $1.50
        expected = 1.5
        assert abs(cost - expected) < 0.01
    
    def test_zero_tokens(self):
        usage = TokenUsage()
        assert usage.total_tokens == 0


class TestDailyUsage:
    """Test DailyUsage tracking."""
    
    def test_default_values(self):
        usage = DailyUsage()
        assert usage.date == date.today()
        assert usage.total_tokens == 0
        assert usage.total_requests == 0
        assert usage.estimated_cost_usd == 0.0
    
    def test_add_usage(self):
        daily = DailyUsage()
        tokens = TokenUsage(input_tokens=2300, output_tokens=400)
        
        # REC-272: Updated interface - cost is now pre-calculated
        daily.add_usage(tokens, cost=0.01)
        
        assert daily.total_tokens == 2700
        assert daily.total_requests == 1
        assert daily.estimated_cost_usd > 0
    
    def test_add_multiple_usages(self):
        daily = DailyUsage()
        
        tokens1 = TokenUsage(input_tokens=1000, output_tokens=100)
        tokens2 = TokenUsage(input_tokens=2000, output_tokens=200)
        
        # REC-272: Updated interface - cost is now pre-calculated
        daily.add_usage(tokens1, cost=0.005)
        daily.add_usage(tokens2, cost=0.008)
        
        assert daily.total_tokens == 3300
        assert daily.total_requests == 2


class TestRateLimiter:
    """Test RateLimiter."""
    
    def test_default_rpm(self):
        limiter = RateLimiter()
        assert limiter.rpm == 50
    
    def test_custom_rpm(self):
        limiter = RateLimiter(requests_per_minute=100)
        assert limiter.rpm == 100
    
    def test_first_request_no_wait(self):
        limiter = RateLimiter(requests_per_minute=60)
        import time
        start = time.time()
        limiter.wait_if_needed()
        elapsed = time.time() - start
        assert elapsed < 0.1  # Should be nearly instant


class TestCircuitBreaker:
    """Test CircuitBreaker pattern."""
    
    def test_starts_closed(self):
        cb = CircuitBreaker()
        assert cb.state == CircuitBreaker.CLOSED
        assert cb.can_execute()
    
    def test_opens_after_failures(self):
        cb = CircuitBreaker(failure_threshold=3)
        
        cb.record_failure()
        assert cb.can_execute()
        
        cb.record_failure()
        assert cb.can_execute()
        
        cb.record_failure()  # 3rd failure
        assert cb.state == CircuitBreaker.OPEN
        assert not cb.can_execute()
    
    def test_success_resets_failures(self):
        cb = CircuitBreaker(failure_threshold=3)
        
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        
        assert cb.failures == 0
        assert cb.state == CircuitBreaker.CLOSED
    
    def test_recovers_after_timeout(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        
        cb.record_failure()
        assert not cb.can_execute()
        
        import time
        time.sleep(0.15)
        
        assert cb.can_execute()
        assert cb.state == CircuitBreaker.HALF_OPEN


class TestClaudeClient:
    """Test ClaudeClient."""
    
    def test_not_available_without_api_key(self):
        # Clear environment variables for this test
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "", "OPENAI_API_KEY": "", "GOOGLE_API_KEY": ""}, clear=False):
            config = SentimentConfig(model=SentimentModel.KEYWORD, anthropic_api_key=None)
            client = ClaudeClient(config)
            # Without API key, not available
            assert not client.config.anthropic_api_key
    
    def test_get_usage_stats(self):
        config = SentimentConfig()
        with tempfile.TemporaryDirectory() as tmpdir:
            config.cache_dir = Path(tmpdir)
            client = ClaudeClient(config)
            
            stats = client.get_usage_stats()
            
            assert "date" in stats
            assert "total_tokens" in stats
            assert "total_requests" in stats
            assert "estimated_cost_usd" in stats
            assert "daily_limit_usd" in stats
            assert "remaining_usd" in stats
            assert "circuit_breaker_state" in stats
    
    def test_health_check_structure(self):
        """Test health check returns expected structure."""
        config = SentimentConfig(model=SentimentModel.KEYWORD)
        with tempfile.TemporaryDirectory() as tmpdir:
            config.cache_dir = Path(tmpdir)
            client = ClaudeClient(config)
            
            health = client.health_check()
            
            # Should have standard health check fields
            assert "provider" in health
            assert "usage" in health
    
    @pytest.mark.skipif(not ANTHROPIC_AVAILABLE, reason="anthropic not installed")
    def test_health_check_with_mock_api_key(self):
        config = SentimentConfig(
            model=SentimentModel.LLM,
            anthropic_api_key="sk-test-invalid"
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            config.cache_dir = Path(tmpdir)
            client = ClaudeClient(config)
            
            health = client.health_check()
            
            # Will fail auth but structure should be correct
            assert health["api_key_set"]
            assert "error" in health or not health["available"]


class TestClaudeClientMocked:
    """Test ClaudeClient with mocked Anthropic API."""
    
    @pytest.fixture
    def mock_anthropic(self):
        """Create a mock Anthropic client."""
        with patch("scoring.claude_client.anthropic") as mock:
            mock_client = MagicMock()
            mock.Anthropic.return_value = mock_client
            
            # Mock successful response
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text='{"sentiment": "positive", "score": 75}')]
            mock_response.usage.input_tokens = 100
            mock_response.usage.output_tokens = 50
            mock_client.messages.create.return_value = mock_response
            
            yield mock, mock_client
    
    @pytest.mark.asyncio
    async def test_analyze_returns_parsed_json(self, mock_anthropic):
        mock, mock_client = mock_anthropic
        
        config = SentimentConfig(
            model=SentimentModel.LLM,
            anthropic_api_key="sk-test"
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            config.cache_dir = Path(tmpdir)
            
            # Need to patch the global ANTHROPIC_AVAILABLE and disable LLM provider
            with patch("scoring.claude_client.ANTHROPIC_AVAILABLE", True), \
                 patch("scoring.claude_client.LLM_ABSTRACTION_AVAILABLE", False):
                client = ClaudeClient(config)
                client._anthropic_client = mock_client
                client._provider = None  # Force fallback
                
                result = await client.analyze(
                    system_prompt="Test prompt",
                    user_message="Test message"
                )
                
                assert result == {"sentiment": "positive", "score": 75}
    
    @pytest.mark.asyncio
    async def test_analyze_handles_markdown_wrapped_json(self, mock_anthropic):
        mock, mock_client = mock_anthropic
        
        # Response wrapped in markdown
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='```json\n{"score": 80}\n```')]
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50
        mock_client.messages.create.return_value = mock_response
        
        config = SentimentConfig(
            model=SentimentModel.LLM,
            anthropic_api_key="sk-test"
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            config.cache_dir = Path(tmpdir)
            
            with patch("scoring.claude_client.ANTHROPIC_AVAILABLE", True), \
                 patch("scoring.claude_client.LLM_ABSTRACTION_AVAILABLE", False):
                client = ClaudeClient(config)
                client._anthropic_client = mock_client
                client._provider = None  # Force fallback
                
                result = await client.analyze(
                    system_prompt="Test",
                    user_message="Test"
                )
                
                assert result == {"score": 80}
    
    @pytest.mark.asyncio
    async def test_daily_limit_blocks_requests(self, mock_anthropic):
        mock, mock_client = mock_anthropic
        
        config = SentimentConfig(
            model=SentimentModel.LLM,
            anthropic_api_key="sk-test",
            max_daily_spend_usd=0.001  # Very low limit
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            config.cache_dir = Path(tmpdir)
            
            with patch("scoring.claude_client.ANTHROPIC_AVAILABLE", True), \
                 patch("scoring.claude_client.LLM_ABSTRACTION_AVAILABLE", False):
                client = ClaudeClient(config)
                client._anthropic_client = mock_client
                client._provider = None  # Force fallback
                
                # Simulate hitting the limit
                client._daily_usage.estimated_cost_usd = 0.002
                
                result = await client.analyze(
                    system_prompt="Test",
                    user_message="Test"
                )
                
                # Should return None due to daily limit
                assert result is None


class TestGlobalClient:
    """Test global client getters."""
    
    def test_get_client_returns_instance(self):
        client = get_claude_client()
        assert isinstance(client, ClaudeClient)
    
    def test_reload_creates_new_instance(self):
        client1 = get_claude_client()
        client2 = reload_claude_client()
        # After reload, global should point to new instance
        assert get_claude_client() is client2
