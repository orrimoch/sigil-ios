"""
Abstract Base Class for LLM Providers (REC-272)

Defines the common interface for all LLM providers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class LLMProviderType(str, Enum):
    """Supported LLM provider types."""
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GOOGLE = "google"


@dataclass
class LLMConfig:
    """Configuration for LLM provider."""
    provider: LLMProviderType
    api_key: Optional[str] = None
    model: Optional[str] = None
    fallback_model: Optional[str] = None
    max_tokens: int = 1024
    temperature: float = 0.0
    rate_limit_rpm: int = 50
    max_retries: int = 3
    retry_delay_seconds: float = 1.0
    max_daily_spend_usd: float = 10.0
    
    # Provider-specific settings
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TokenUsage:
    """Track token usage for cost estimation."""
    input_tokens: int = 0
    output_tokens: int = 0
    
    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class LLMResponse:
    """Standard response from any LLM provider."""
    text: str
    model: str
    provider: LLMProviderType
    usage: TokenUsage
    finish_reason: Optional[str] = None
    raw_response: Optional[Any] = None
    latency_ms: Optional[float] = None
    cached: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "model": self.model,
            "provider": self.provider.value,
            "usage": {
                "input_tokens": self.usage.input_tokens,
                "output_tokens": self.usage.output_tokens,
                "total_tokens": self.usage.total_tokens,
            },
            "finish_reason": self.finish_reason,
            "latency_ms": self.latency_ms,
            "cached": self.cached,
        }


class LLMProvider(ABC):
    """
    Abstract base class for LLM providers.
    
    All LLM providers must implement this interface to ensure
    consistent behavior across Anthropic, OpenAI, and Google.
    """
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self._client = None
    
    @property
    @abstractmethod
    def provider_type(self) -> LLMProviderType:
        """Return the provider type."""
        pass
    
    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Check if the provider is available (API key set, package installed)."""
        pass
    
    @property
    @abstractmethod
    def default_model(self) -> str:
        """Return the default model for this provider."""
        pass
    
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Generate a response from the LLM.
        
        Args:
            prompt: The user prompt
            system_prompt: Optional system instructions
            model: Optional model override
            max_tokens: Optional max tokens override
            temperature: Optional temperature override
            **kwargs: Provider-specific options
            
        Returns:
            LLMResponse with the generated text and metadata
        """
        pass
    
    @abstractmethod
    async def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """
        Generate a JSON response from the LLM.
        
        Args:
            prompt: The user prompt
            system_prompt: Optional system instructions
            model: Optional model override
            **kwargs: Provider-specific options
            
        Returns:
            Parsed JSON dict or None if parsing fails
        """
        pass
    
    @abstractmethod
    def estimate_cost(self, usage: TokenUsage, model: Optional[str] = None) -> float:
        """
        Estimate cost in USD for token usage.
        
        Args:
            usage: TokenUsage object
            model: Optional model (uses default if not specified)
            
        Returns:
            Estimated cost in USD
        """
        pass
    
    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check on the provider.
        
        Returns:
            Dict with status and details
        """
        pass
    
    def _parse_json(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Parse JSON from LLM response, handling markdown code blocks.
        
        Args:
            text: Raw response text
            
        Returns:
            Parsed JSON dict or None
        """
        import json
        
        text = text.strip()
        
        # Remove markdown code blocks
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON: {e}")
            logger.debug(f"Raw text: {text[:500]}")
            return None
