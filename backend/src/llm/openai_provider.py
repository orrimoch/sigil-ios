"""
OpenAI (GPT) LLM Provider (REC-272)

Implements LLMProvider interface for OpenAI GPT models.
"""

import time
import logging
from typing import Optional, Dict, Any

from .base import LLMProvider, LLMConfig, LLMResponse, TokenUsage, LLMProviderType

logger = logging.getLogger(__name__)

# Check if openai is installed
try:
    import openai
    from openai import AsyncOpenAI, OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("openai package not installed. Run: pip install openai")


# Model pricing (per 1M tokens, as of Feb 2026)
OPENAI_PRICING = {
    "gpt-4o": {"input": 2.50, "output": 10.0},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4-turbo": {"input": 10.0, "output": 30.0},
    "gpt-4": {"input": 30.0, "output": 60.0},
    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
    "o1": {"input": 15.0, "output": 60.0},
    "o1-mini": {"input": 3.0, "output": 12.0},
}

DEFAULT_MODEL = "gpt-4o"
FALLBACK_MODEL = "gpt-4o-mini"


class OpenAIProvider(LLMProvider):
    """
    OpenAI GPT LLM provider.
    
    Supports GPT-4o, GPT-4, GPT-3.5, and o1 models.
    """
    
    def __init__(self, config: LLMConfig):
        super().__init__(config)
        
        if OPENAI_AVAILABLE and config.api_key:
            self._client = OpenAI(api_key=config.api_key)
            self._async_client = AsyncOpenAI(api_key=config.api_key)
        else:
            self._client = None
            self._async_client = None
    
    @property
    def provider_type(self) -> LLMProviderType:
        return LLMProviderType.OPENAI
    
    @property
    def is_available(self) -> bool:
        return OPENAI_AVAILABLE and self._client is not None
    
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
        """Generate response using GPT."""
        if not self.is_available:
            raise RuntimeError("OpenAI provider not available. Check API key and package installation.")
        
        model = model or self.default_model
        max_tokens = max_tokens or self.config.max_tokens
        temperature = temperature if temperature is not None else self.config.temperature
        
        start_time = time.time()
        
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            # o1 models don't support temperature or system messages
            is_o1_model = model.startswith("o1")
            
            create_kwargs = {
                "model": model,
                "messages": messages if not is_o1_model else [m for m in messages if m["role"] != "system"],
                "max_completion_tokens" if is_o1_model else "max_tokens": max_tokens,
            }
            
            if not is_o1_model:
                create_kwargs["temperature"] = temperature
            
            response = await self._async_client.chat.completions.create(**create_kwargs)
            
            latency_ms = (time.time() - start_time) * 1000
            
            text = response.choices[0].message.content if response.choices else ""
            
            usage = TokenUsage(
                input_tokens=response.usage.prompt_tokens if response.usage else 0,
                output_tokens=response.usage.completion_tokens if response.usage else 0,
            )
            
            return LLMResponse(
                text=text or "",
                model=model,
                provider=self.provider_type,
                usage=usage,
                finish_reason=response.choices[0].finish_reason if response.choices else None,
                raw_response=response,
                latency_ms=latency_ms,
            )
            
        except openai.AuthenticationError as e:
            logger.error(f"OpenAI authentication error: {e}")
            raise
        except openai.RateLimitError as e:
            logger.warning(f"OpenAI rate limit: {e}")
            raise
        except openai.APIError as e:
            logger.error(f"OpenAI API error: {e}")
            raise
    
    async def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """Generate JSON response using GPT with JSON mode."""
        model = model or self.default_model
        
        # Add JSON instruction
        json_system = (system_prompt or "") + "\n\nRespond with valid JSON only."
        
        # Use response_format for JSON mode (supported on gpt-4o and newer)
        use_json_mode = model in ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"]
        
        if use_json_mode and not model.startswith("o1"):
            kwargs["response_format"] = {"type": "json_object"}
        
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
        rates = OPENAI_PRICING.get(model, OPENAI_PRICING[DEFAULT_MODEL])
        
        input_cost = (usage.input_tokens / 1_000_000) * rates["input"]
        output_cost = (usage.output_tokens / 1_000_000) * rates["output"]
        
        return input_cost + output_cost
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on OpenAI API."""
        result = {
            "provider": "openai",
            "available": False,
            "api_key_set": self.config.api_key is not None,
            "package_installed": OPENAI_AVAILABLE,
            "model": self.default_model,
        }
        
        if not OPENAI_AVAILABLE:
            result["error"] = "openai package not installed"
            return result
        
        if not self.config.api_key:
            result["error"] = "API key not set"
            return result
        
        try:
            response = self._client.chat.completions.create(
                model=self.default_model,
                max_tokens=10,
                messages=[{"role": "user", "content": "Say 'ok'"}],
            )
            
            content = response.choices[0].message.content if response.choices else ""
            if content and "ok" in content.lower():
                result["available"] = True
            else:
                result["error"] = f"Unexpected response: {content}"
                
        except Exception as e:
            result["error"] = str(e)
        
        return result
