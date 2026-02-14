"""
LLM Provider Abstraction Layer (REC-272)

Supports multiple LLM providers:
- Anthropic (Claude)
- OpenAI (GPT)
- Google (Gemini)

Provider selection is environment-based via LLM_PROVIDER env var.
"""

from .base import LLMProvider, LLMResponse, LLMConfig
from .factory import get_llm_provider, get_provider_config, LLMProviderType
from .anthropic_provider import AnthropicProvider
from .openai_provider import OpenAIProvider
from .google_provider import GoogleProvider

__all__ = [
    "LLMProvider",
    "LLMResponse",
    "LLMConfig",
    "LLMProviderType",
    "get_llm_provider",
    "get_provider_config",
    "AnthropicProvider",
    "OpenAIProvider",
    "GoogleProvider",
]
