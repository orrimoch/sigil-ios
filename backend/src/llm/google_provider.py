"""
Google (Gemini) LLM Provider (REC-272)

Implements LLMProvider interface for Google Gemini models.
"""

import time
import logging
from typing import Optional, Dict, Any

from .base import LLMProvider, LLMConfig, LLMResponse, TokenUsage, LLMProviderType

logger = logging.getLogger(__name__)

# Check if google-generativeai is installed
try:
    import google.generativeai as genai
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False
    logger.warning("google-generativeai package not installed. Run: pip install google-generativeai")


# Model pricing (per 1M tokens, as of Feb 2026)
GOOGLE_PRICING = {
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
    "gemini-1.5-flash-8b": {"input": 0.0375, "output": 0.15},
    "gemini-1.5-pro": {"input": 1.25, "output": 5.0},
    "gemini-2.0-flash-thinking": {"input": 0.70, "output": 2.80},
}

DEFAULT_MODEL = "gemini-2.0-flash"
FALLBACK_MODEL = "gemini-1.5-flash"


class GoogleProvider(LLMProvider):
    """
    Google Gemini LLM provider.
    
    Supports Gemini 2.0 and 1.5 models.
    """
    
    def __init__(self, config: LLMConfig):
        super().__init__(config)
        
        if GOOGLE_AVAILABLE and config.api_key:
            genai.configure(api_key=config.api_key)
            self._configured = True
        else:
            self._configured = False
    
    @property
    def provider_type(self) -> LLMProviderType:
        return LLMProviderType.GOOGLE
    
    @property
    def is_available(self) -> bool:
        return GOOGLE_AVAILABLE and self._configured
    
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
        """Generate response using Gemini."""
        if not self.is_available:
            raise RuntimeError("Google provider not available. Check API key and package installation.")
        
        model_name = model or self.default_model
        max_tokens = max_tokens or self.config.max_tokens
        temperature = temperature if temperature is not None else self.config.temperature
        
        start_time = time.time()
        
        try:
            # Configure generation settings
            generation_config = genai.GenerationConfig(
                max_output_tokens=max_tokens,
                temperature=temperature,
            )
            
            # Create model with system instruction if provided
            model_kwargs = {"model_name": model_name, "generation_config": generation_config}
            if system_prompt:
                model_kwargs["system_instruction"] = system_prompt
            
            gemini_model = genai.GenerativeModel(**model_kwargs)
            
            # Generate content (async)
            response = await gemini_model.generate_content_async(prompt)
            
            latency_ms = (time.time() - start_time) * 1000
            
            text = response.text if hasattr(response, 'text') else ""
            
            # Extract usage metadata
            usage_metadata = getattr(response, 'usage_metadata', None)
            usage = TokenUsage(
                input_tokens=getattr(usage_metadata, 'prompt_token_count', 0) if usage_metadata else 0,
                output_tokens=getattr(usage_metadata, 'candidates_token_count', 0) if usage_metadata else 0,
            )
            
            # Determine finish reason
            finish_reason = None
            if hasattr(response, 'candidates') and response.candidates:
                finish_reason = str(response.candidates[0].finish_reason)
            
            return LLMResponse(
                text=text,
                model=model_name,
                provider=self.provider_type,
                usage=usage,
                finish_reason=finish_reason,
                raw_response=response,
                latency_ms=latency_ms,
            )
            
        except Exception as e:
            logger.error(f"Google API error: {e}")
            raise
    
    async def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """Generate JSON response using Gemini."""
        model_name = model or self.default_model
        
        # Add JSON instruction
        json_system = (system_prompt or "") + "\n\nRespond with valid JSON only, no markdown formatting."
        
        # Try to use JSON mode if supported
        try:
            generation_config = genai.GenerationConfig(
                max_output_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                response_mime_type="application/json",
            )
            
            model_kwargs = {"model_name": model_name, "generation_config": generation_config}
            if json_system:
                model_kwargs["system_instruction"] = json_system.strip()
            
            gemini_model = genai.GenerativeModel(**model_kwargs)
            response = await gemini_model.generate_content_async(prompt)
            
            return self._parse_json(response.text if hasattr(response, 'text') else "")
            
        except Exception as e:
            # Fallback to standard generation
            logger.warning(f"JSON mode failed, falling back: {e}")
            response = await self.generate(
                prompt=prompt,
                system_prompt=json_system.strip(),
                model=model_name,
                **kwargs
            )
            return self._parse_json(response.text)
    
    def estimate_cost(self, usage: TokenUsage, model: Optional[str] = None) -> float:
        """Estimate cost for token usage."""
        model = model or self.default_model
        rates = GOOGLE_PRICING.get(model, GOOGLE_PRICING[DEFAULT_MODEL])
        
        input_cost = (usage.input_tokens / 1_000_000) * rates["input"]
        output_cost = (usage.output_tokens / 1_000_000) * rates["output"]
        
        return input_cost + output_cost
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on Google Gemini API."""
        result = {
            "provider": "google",
            "available": False,
            "api_key_set": self.config.api_key is not None,
            "package_installed": GOOGLE_AVAILABLE,
            "model": self.default_model,
        }
        
        if not GOOGLE_AVAILABLE:
            result["error"] = "google-generativeai package not installed"
            return result
        
        if not self.config.api_key:
            result["error"] = "API key not set"
            return result
        
        try:
            model = genai.GenerativeModel(model_name=self.default_model)
            response = model.generate_content("Say 'ok'")
            
            if hasattr(response, 'text') and "ok" in response.text.lower():
                result["available"] = True
            else:
                result["error"] = f"Unexpected response: {getattr(response, 'text', 'empty')}"
                
        except Exception as e:
            result["error"] = str(e)
        
        return result
