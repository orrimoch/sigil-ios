"""
Unit tests for LLM Provider Abstraction (REC-272)

Tests the multi-provider LLM support including:
- Provider factory
- Provider configuration
- Provider switching
"""

import pytest
import os
from unittest.mock import patch, MagicMock, AsyncMock


class TestLLMProviderFactory:
    """Tests for the LLM provider factory."""
    
    def test_get_provider_config_defaults_to_anthropic(self):
        """Default provider should be anthropic."""
        with patch.dict(os.environ, {}, clear=True):
            from llm.factory import get_provider_config
            config = get_provider_config()
            assert config.provider.value == "anthropic"
    
    def test_get_provider_config_respects_env_var(self):
        """LLM_PROVIDER env var should change provider."""
        with patch.dict(os.environ, {"LLM_PROVIDER": "openai"}, clear=False):
            from llm.factory import get_provider_config, LLMProviderType
            config = get_provider_config(provider=LLMProviderType.OPENAI)
            assert config.provider.value == "openai"
    
    def test_get_provider_config_with_api_key(self):
        """API key should be loaded from environment."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}, clear=False):
            from llm.factory import get_provider_config, LLMProviderType
            config = get_provider_config(provider=LLMProviderType.ANTHROPIC)
            assert config.api_key == "test-key"
    
    def test_create_anthropic_provider(self):
        """Should create Anthropic provider correctly."""
        from llm.factory import create_provider, get_provider_config, LLMProviderType
        
        config = get_provider_config(provider=LLMProviderType.ANTHROPIC)
        provider = create_provider(config)
        
        assert provider.provider_type == LLMProviderType.ANTHROPIC
        assert "claude" in provider.default_model.lower()
    
    def test_create_openai_provider(self):
        """Should create OpenAI provider correctly."""
        from llm.factory import create_provider, get_provider_config, LLMProviderType
        
        config = get_provider_config(provider=LLMProviderType.OPENAI)
        provider = create_provider(config)
        
        assert provider.provider_type == LLMProviderType.OPENAI
        assert "gpt" in provider.default_model.lower()
    
    def test_create_google_provider(self):
        """Should create Google provider correctly."""
        from llm.factory import create_provider, get_provider_config, LLMProviderType
        
        config = get_provider_config(provider=LLMProviderType.GOOGLE)
        provider = create_provider(config)
        
        assert provider.provider_type == LLMProviderType.GOOGLE
        assert "gemini" in provider.default_model.lower()


class TestTokenUsage:
    """Tests for token usage tracking."""
    
    def test_token_usage_total(self):
        """Total tokens should be sum of input and output."""
        from llm.base import TokenUsage
        
        usage = TokenUsage(input_tokens=100, output_tokens=50)
        assert usage.total_tokens == 150
    
    def test_token_usage_zero(self):
        """Zero usage should work."""
        from llm.base import TokenUsage
        
        usage = TokenUsage()
        assert usage.total_tokens == 0


class TestLLMResponse:
    """Tests for LLM response model."""
    
    def test_response_to_dict(self):
        """Response should serialize to dict correctly."""
        from llm.base import LLMResponse, TokenUsage, LLMProviderType
        
        response = LLMResponse(
            text="Hello world",
            model="test-model",
            provider=LLMProviderType.ANTHROPIC,
            usage=TokenUsage(input_tokens=10, output_tokens=20),
        )
        
        result = response.to_dict()
        
        assert result["text"] == "Hello world"
        assert result["model"] == "test-model"
        assert result["provider"] == "anthropic"
        assert result["usage"]["total_tokens"] == 30


class TestAnthropicProvider:
    """Tests for Anthropic provider."""
    
    def test_default_model(self):
        """Default model should be Claude Sonnet."""
        from llm.anthropic_provider import AnthropicProvider
        from llm.base import LLMConfig, LLMProviderType
        
        config = LLMConfig(provider=LLMProviderType.ANTHROPIC)
        provider = AnthropicProvider(config)
        
        assert "sonnet" in provider.default_model.lower()
    
    def test_estimate_cost(self):
        """Cost estimation should work correctly."""
        from llm.anthropic_provider import AnthropicProvider
        from llm.base import LLMConfig, LLMProviderType, TokenUsage
        
        config = LLMConfig(provider=LLMProviderType.ANTHROPIC)
        provider = AnthropicProvider(config)
        
        # 1M input tokens + 1M output tokens on Sonnet
        usage = TokenUsage(input_tokens=1_000_000, output_tokens=1_000_000)
        cost = provider.estimate_cost(usage)
        
        # Sonnet: $3/1M input + $15/1M output = $18
        assert cost == pytest.approx(18.0, rel=0.1)
    
    def test_is_available_without_key(self):
        """Provider should not be available without API key."""
        from llm.anthropic_provider import AnthropicProvider
        from llm.base import LLMConfig, LLMProviderType
        
        config = LLMConfig(provider=LLMProviderType.ANTHROPIC, api_key=None)
        provider = AnthropicProvider(config)
        
        assert not provider.is_available


class TestOpenAIProvider:
    """Tests for OpenAI provider."""
    
    def test_default_model(self):
        """Default model should be GPT-4o."""
        from llm.openai_provider import OpenAIProvider
        from llm.base import LLMConfig, LLMProviderType
        
        config = LLMConfig(provider=LLMProviderType.OPENAI)
        provider = OpenAIProvider(config)
        
        assert "gpt-4o" in provider.default_model.lower()
    
    def test_estimate_cost(self):
        """Cost estimation should work correctly."""
        from llm.openai_provider import OpenAIProvider
        from llm.base import LLMConfig, LLMProviderType, TokenUsage
        
        config = LLMConfig(provider=LLMProviderType.OPENAI)
        provider = OpenAIProvider(config)
        
        # 1M input tokens + 1M output tokens on GPT-4o
        usage = TokenUsage(input_tokens=1_000_000, output_tokens=1_000_000)
        cost = provider.estimate_cost(usage)
        
        # GPT-4o: $2.50/1M input + $10/1M output = $12.50
        assert cost == pytest.approx(12.5, rel=0.1)


class TestGoogleProvider:
    """Tests for Google provider."""
    
    def test_default_model(self):
        """Default model should be Gemini Flash."""
        from llm.google_provider import GoogleProvider
        from llm.base import LLMConfig, LLMProviderType
        
        config = LLMConfig(provider=LLMProviderType.GOOGLE)
        provider = GoogleProvider(config)
        
        assert "gemini" in provider.default_model.lower()
    
    def test_estimate_cost(self):
        """Cost estimation should work correctly."""
        from llm.google_provider import GoogleProvider
        from llm.base import LLMConfig, LLMProviderType, TokenUsage
        
        config = LLMConfig(provider=LLMProviderType.GOOGLE)
        provider = GoogleProvider(config)
        
        # 1M input tokens + 1M output tokens on Gemini Flash
        usage = TokenUsage(input_tokens=1_000_000, output_tokens=1_000_000)
        cost = provider.estimate_cost(usage)
        
        # Gemini 2.0 Flash: $0.10/1M input + $0.40/1M output = $0.50
        assert cost == pytest.approx(0.5, rel=0.1)


class TestJSONParsing:
    """Tests for JSON response parsing."""
    
    def test_parse_clean_json(self):
        """Should parse clean JSON."""
        from llm.base import LLMProvider, LLMConfig, LLMProviderType
        from llm.anthropic_provider import AnthropicProvider
        
        config = LLMConfig(provider=LLMProviderType.ANTHROPIC)
        provider = AnthropicProvider(config)
        
        result = provider._parse_json('{"key": "value"}')
        assert result == {"key": "value"}
    
    def test_parse_json_with_markdown(self):
        """Should parse JSON wrapped in markdown code blocks."""
        from llm.anthropic_provider import AnthropicProvider
        from llm.base import LLMConfig, LLMProviderType
        
        config = LLMConfig(provider=LLMProviderType.ANTHROPIC)
        provider = AnthropicProvider(config)
        
        text = '```json\n{"key": "value"}\n```'
        result = provider._parse_json(text)
        assert result == {"key": "value"}
    
    def test_parse_invalid_json(self):
        """Should return None for invalid JSON."""
        from llm.anthropic_provider import AnthropicProvider
        from llm.base import LLMConfig, LLMProviderType
        
        config = LLMConfig(provider=LLMProviderType.ANTHROPIC)
        provider = AnthropicProvider(config)
        
        result = provider._parse_json('not valid json')
        assert result is None


class TestProviderHealthCheck:
    """Tests for provider health checks."""
    
    def test_health_check_no_api_key(self):
        """Health check should indicate missing API key."""
        from llm.anthropic_provider import AnthropicProvider
        from llm.base import LLMConfig, LLMProviderType
        
        config = LLMConfig(provider=LLMProviderType.ANTHROPIC, api_key=None)
        provider = AnthropicProvider(config)
        
        health = provider.health_check()
        
        assert health["provider"] == "anthropic"
        assert not health["available"]
        assert "api key" in health.get("error", "").lower() or not health["api_key_set"]
