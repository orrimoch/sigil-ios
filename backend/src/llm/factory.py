"""
LLM Provider Factory (REC-272)

Factory for creating LLM providers based on configuration.
Environment-based selection via LLM_PROVIDER env var.
"""

import os
import logging
from typing import Optional, Dict, Any
from enum import Enum

from .base import LLMProvider, LLMConfig, LLMProviderType
from .anthropic_provider import AnthropicProvider
from .openai_provider import OpenAIProvider
from .google_provider import GoogleProvider

logger = logging.getLogger(__name__)


# Re-export for convenience
class LLMProviderType(str, Enum):
    """Supported LLM provider types."""
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GOOGLE = "google"


# Default models per provider
DEFAULT_MODELS = {
    LLMProviderType.ANTHROPIC: "claude-3-5-haiku-20241022",
    LLMProviderType.OPENAI: "gpt-4o",
    LLMProviderType.GOOGLE: "gemini-2.0-flash",
}

FALLBACK_MODELS = {
    LLMProviderType.ANTHROPIC: "claude-3-5-haiku-20241022",
    LLMProviderType.OPENAI: "gpt-4o-mini",
    LLMProviderType.GOOGLE: "gemini-1.5-flash",
}

# API key env var names
API_KEY_ENV_VARS = {
    LLMProviderType.ANTHROPIC: "ANTHROPIC_API_KEY",
    LLMProviderType.OPENAI: "OPENAI_API_KEY",
    LLMProviderType.GOOGLE: "GOOGLE_API_KEY",
}


def get_provider_config(
    provider: Optional[LLMProviderType] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
) -> LLMConfig:
    """
    Get configuration for an LLM provider.
    
    Args:
        provider: Provider type (defaults to LLM_PROVIDER env var or anthropic)
        model: Model name (defaults to provider's default model)
        api_key: API key (defaults to provider's env var)
        
    Returns:
        LLMConfig for the specified provider
    """
    # Determine provider
    if provider is None:
        provider_str = os.environ.get("LLM_PROVIDER", "anthropic").lower()
        try:
            provider = LLMProviderType(provider_str)
        except ValueError:
            logger.warning(f"Invalid LLM_PROVIDER '{provider_str}', defaulting to anthropic")
            provider = LLMProviderType.ANTHROPIC
    
    # Get API key
    if api_key is None:
        env_var = API_KEY_ENV_VARS.get(provider, "")
        api_key = os.environ.get(env_var)
    
    # Get model
    if model is None:
        model = os.environ.get("LLM_MODEL", DEFAULT_MODELS.get(provider))
    
    fallback_model = FALLBACK_MODELS.get(provider)
    
    # Get other config from env
    config = LLMConfig(
        provider=provider,
        api_key=api_key,
        model=model,
        fallback_model=fallback_model,
        max_tokens=int(os.environ.get("LLM_MAX_TOKENS", "1024")),
        temperature=float(os.environ.get("LLM_TEMPERATURE", "0.0")),
        rate_limit_rpm=int(os.environ.get("LLM_RATE_LIMIT", "50")),
        max_retries=int(os.environ.get("LLM_MAX_RETRIES", "3")),
        max_daily_spend_usd=float(os.environ.get("LLM_MAX_DAILY_SPEND", "10.0")),
    )
    
    logger.info(
        f"LLM config: provider={provider.value}, model={model}, "
        f"api_key_set={api_key is not None}"
    )
    
    return config


def create_provider(config: LLMConfig) -> LLMProvider:
    """
    Create an LLM provider instance from config.
    
    Args:
        config: LLMConfig with provider settings
        
    Returns:
        LLMProvider instance
    """
    providers = {
        LLMProviderType.ANTHROPIC: AnthropicProvider,
        LLMProviderType.OPENAI: OpenAIProvider,
        LLMProviderType.GOOGLE: GoogleProvider,
    }
    
    provider_class = providers.get(config.provider)
    if provider_class is None:
        raise ValueError(f"Unknown provider: {config.provider}")
    
    return provider_class(config)


# Global provider instance (lazy-loaded)
_provider: Optional[LLMProvider] = None


def get_llm_provider(
    provider: Optional[LLMProviderType] = None,
    force_reload: bool = False,
) -> LLMProvider:
    """
    Get the global LLM provider instance (lazy-loaded).
    
    Args:
        provider: Optional provider override
        force_reload: Force recreation of provider
        
    Returns:
        LLMProvider instance
    """
    global _provider
    
    if _provider is None or force_reload or provider is not None:
        config = get_provider_config(provider=provider)
        _provider = create_provider(config)
    
    return _provider


def reload_llm_provider() -> LLMProvider:
    """Force reload of the global LLM provider."""
    return get_llm_provider(force_reload=True)


def health_check_all_providers() -> Dict[str, Any]:
    """
    Run health checks on all configured providers.
    
    Returns:
        Dict with health status for each provider
    """
    results = {}
    
    for provider_type in LLMProviderType:
        try:
            config = get_provider_config(provider=provider_type)
            provider = create_provider(config)
            results[provider_type.value] = provider.health_check()
        except Exception as e:
            results[provider_type.value] = {
                "provider": provider_type.value,
                "available": False,
                "error": str(e),
            }
    
    return results


# CLI for testing
if __name__ == "__main__":
    import sys
    import asyncio
    
    logging.basicConfig(level=logging.DEBUG)
    
    print("\n=== LLM Provider Factory Test ===\n")
    
    # Test current provider
    provider = get_llm_provider()
    print(f"Current provider: {provider.provider_type.value}")
    print(f"Model: {provider.default_model}")
    print(f"Available: {provider.is_available}")
    
    # Health check
    print("\nHealth check:")
    health = provider.health_check()
    for key, value in health.items():
        print(f"  {key}: {value}")
    
    # Health check all providers
    print("\n--- All Providers ---")
    all_health = health_check_all_providers()
    for provider_name, status in all_health.items():
        available = status.get("available", False)
        error = status.get("error", "")
        print(f"  {provider_name}: {'✅' if available else '❌'} {error}")
