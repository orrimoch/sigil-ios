"""
Anthropic (Claude) LLM Provider (REC-272)

Implements LLMProvider interface for Claude models.
"""

import time
import logging
from typing import Optional, Dict, Any

from .base import LLMProvider, LLMConfig, LLMResponse, TokenUsage, LLMProviderType

logger = logging.getLogger(__name__)

# Check if anthropic is installed
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    logger.warning("anthropic package not installed. Run: pip install anthropic")


# Model pricing (per 1M tokens, as of Feb 2026)
ANTHROPIC_PRICING = {
    "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0},
    "claude-3-5-sonnet-20241022": {"input": 3.0, "output": 15.0},
    "claude-3-5-haiku-20241022": {"input": 1.0, "output": 5.0},
    "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
    "claude-opus-4-20250514": {"input": 15.0, "output": 75.0},
}

DEFAULT_MODEL = "claude-sonnet-4-20250514"
FALLBACK_MODEL = "claude-3-5-haiku-20241022"


class AnthropicProvider(LLMProvider):
    """
    Anthropic Claude LLM provider.
    
    Supports Claude Sonnet, Haiku, and Opus models.
    """
    
    def __init__(self, config: LLMConfig):
        super().__init__(config)
        
        if ANTHROPIC_AVAILABLE and config.api_key:
            self._client = anthropic.Anthropic(api_key=config.api_key)
            self._async_client = anthropic.AsyncAnthropic(api_key=config.api_key)
        else:
            self._client = None
            self._async_client = None
    
    @property
    def provider_type(self) -> LLMProviderType:
        return LLMProviderType.ANTHROPIC
    
    @property
    def is_available(self) -> bool:
        return ANTHROPIC_AVAILABLE and self._client is not None
    
    @property
    def default_model(self) -> str:
        return self.config.model or DEFAULT_MODEL
    
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        **kwargs
    ) -> LLMResponse:
        """Generate response using Claude."""
        if not self.is_available:
            raise RuntimeError("Anthropic provider not available. Check API key and package installation.")
        
        model = model or self.default_model
        max_tokens = max_tokens or self.config.max_tokens
        temperature = temperature if temperature is not None else self.config.temperature
        
        start_time = time.time()
        
        try:
            messages = [{"role": "user", "content": prompt}]
            
            kwargs_filtered = {}
            if system_prompt:
                kwargs_filtered["system"] = system_prompt
            
            response = await self._async_client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=messages,
                **kwargs_filtered
            )
            
            latency_ms = (time.time() - start_time) * 1000
            
            text = response.content[0].text if response.content else ""
            
            usage = TokenUsage(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
            )
            
            return LLMResponse(
                text=text,
                model=model,
                provider=self.provider_type,
                usage=usage,
                finish_reason=response.stop_reason,
                raw_response=response,
                latency_ms=latency_ms,
            )
            
        except anthropic.AuthenticationError as e:
            logger.error(f"Anthropic authentication error: {e}")
            raise
        except anthropic.RateLimitError as e:
            logger.warning(f"Anthropic rate limit: {e}")
            raise
        except anthropic.APIError as e:
            logger.error(f"Anthropic API error: {e}")
            raise
    
    async def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """Generate JSON response using Claude."""
        # Add JSON instruction to system prompt
        json_system = (system_prompt or "") + "\n\nRespond ONLY with valid JSON, no markdown formatting."
        
        response = await self.generate(
            prompt=prompt,
            system_prompt=json_system.strip(),
            model=model,
            **kwargs
        )
        
        return self._parse_json(response.text)
    
    def estimate_cost(self, usage: TokenUsage, model: Optional[str] = None) -> float:
        """Estimate cost for token usage."""
        model = model or self.default_model
        rates = ANTHROPIC_PRICING.get(model, ANTHROPIC_PRICING[DEFAULT_MODEL])
        
        input_cost = (usage.input_tokens / 1_000_000) * rates["input"]
        output_cost = (usage.output_tokens / 1_000_000) * rates["output"]
        
        return input_cost + output_cost
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on Anthropic API."""
        result = {
            "provider": "anthropic",
            "available": False,
            "api_key_set": self.config.api_key is not None,
            "package_installed": ANTHROPIC_AVAILABLE,
            "model": self.default_model,
        }
        
        if not ANTHROPIC_AVAILABLE:
            result["error"] = "anthropic package not installed"
            return result
        
        if not self.config.api_key:
            result["error"] = "API key not set"
            return result
        
        # Try a minimal API call synchronously for health check
        try:
            response = self._client.messages.create(
                model=self.default_model,
                max_tokens=10,
                messages=[{"role": "user", "content": "Say 'ok'"}],
            )
            
            if response.content and "ok" in response.content[0].text.lower():
                result["available"] = True
            else:
                result["error"] = f"Unexpected response: {response.content[0].text if response.content else 'empty'}"
                
        except Exception as e:
            result["error"] = str(e)
        
        return result
