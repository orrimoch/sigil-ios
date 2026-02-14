"""
Configuration API Routes (REC-272)

Endpoints for managing app configuration:
- LLM provider settings
- IBKR account configuration
- Database info
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import os
import logging

from auth.middleware import get_optional_user, get_required_user
from db.models import ANONYMOUS_USER_ID

logger = logging.getLogger(__name__)

config_router = APIRouter(prefix="/api/v1/config", tags=["config"])


# ── Request / Response Schemas ──────────────────────────────────────────

class LLMProviderInfo(BaseModel):
    """LLM provider information."""
    provider: str
    model: str
    available: bool
    error: Optional[str] = None


class IBKRAccountConfigRequest(BaseModel):
    """IBKR account configuration request."""
    account_id: str
    gateway_host: Optional[str] = "127.0.0.1"
    gateway_port: Optional[int] = 4002
    is_paper: bool = True


class IBKRAccountConfigResponse(BaseModel):
    """IBKR account configuration response."""
    account_id: Optional[str]
    gateway_host: str
    gateway_port: int
    is_configured: bool
    is_paper: Optional[bool] = None


# In-memory storage for user IBKR configs (in production, use database)
_user_ibkr_configs: Dict[str, dict] = {}


# ── Helper Functions ────────────────────────────────────────────────────

def _get_user_id(user) -> str:
    """Extract user_id from optional user, fallback to ANONYMOUS_USER_ID."""
    return user.id if user else ANONYMOUS_USER_ID


# ── LLM Provider Endpoints ──────────────────────────────────────────────

@config_router.get("/llm")
async def get_llm_config():
    """
    Get current LLM provider configuration.
    
    Returns the active provider, model, and availability status.
    """
    try:
        # Try to import and use the LLM abstraction layer
        try:
            from llm import get_llm_provider
            provider = get_llm_provider()
            
            return {
                "success": True,
                "data": {
                    "provider": provider.provider_type.value,
                    "model": provider.default_model,
                    "available": provider.is_available,
                    "fallback_model": provider.config.fallback_model,
                },
            }
        except ImportError:
            # Fallback to checking environment
            provider = os.environ.get("LLM_PROVIDER", "anthropic")
            
            return {
                "success": True,
                "data": {
                    "provider": provider,
                    "model": os.environ.get("LLM_MODEL", "claude-sonnet-4-20250514"),
                    "available": os.environ.get("ANTHROPIC_API_KEY") is not None,
                    "note": "LLM abstraction layer not loaded",
                },
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@config_router.get("/llm/providers")
async def get_available_providers():
    """
    Get list of available LLM providers and their status.
    """
    try:
        providers = []
        
        # Check Anthropic
        anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
        providers.append({
            "provider": "anthropic",
            "name": "Anthropic (Claude)",
            "models": ["claude-sonnet-4-20250514", "claude-3-5-haiku-20241022", "claude-opus-4-20250514"],
            "default_model": "claude-sonnet-4-20250514",
            "configured": anthropic_key is not None,
            "env_var": "ANTHROPIC_API_KEY",
        })
        
        # Check OpenAI
        openai_key = os.environ.get("OPENAI_API_KEY")
        providers.append({
            "provider": "openai",
            "name": "OpenAI (GPT)",
            "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "o1", "o1-mini"],
            "default_model": "gpt-4o",
            "configured": openai_key is not None,
            "env_var": "OPENAI_API_KEY",
        })
        
        # Check Google
        google_key = os.environ.get("GOOGLE_API_KEY")
        providers.append({
            "provider": "google",
            "name": "Google (Gemini)",
            "models": ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"],
            "default_model": "gemini-2.0-flash",
            "configured": google_key is not None,
            "env_var": "GOOGLE_API_KEY",
        })
        
        # Get current provider
        current = os.environ.get("LLM_PROVIDER", "anthropic")
        
        return {
            "success": True,
            "data": {
                "current_provider": current,
                "providers": providers,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@config_router.get("/llm/health")
async def llm_health_check():
    """
    Perform health check on the current LLM provider.
    """
    try:
        from llm import get_llm_provider
        provider = get_llm_provider()
        health = provider.health_check()
        
        return {
            "success": True,
            "data": health,
        }
    except ImportError:
        return {
            "success": False,
            "error": "LLM abstraction layer not available",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── IBKR Account Configuration Endpoints ────────────────────────────────

@config_router.get("/ibkr")
async def get_ibkr_config(user=Depends(get_optional_user)):
    """
    Get current IBKR account configuration for the user.
    """
    user_id = _get_user_id(user)
    
    # Check user-specific config first
    if user_id in _user_ibkr_configs:
        config = _user_ibkr_configs[user_id]
        return {
            "success": True,
            "data": {
                "account_id": config.get("account_id"),
                "gateway_host": config.get("gateway_host", "127.0.0.1"),
                "gateway_port": config.get("gateway_port", 4002),
                "is_configured": True,
                "is_paper": config.get("is_paper", True),
                "source": "user_config",
            },
        }
    
    # Fall back to environment configuration
    env_account = os.environ.get("IB_ACCOUNT_ID")
    
    return {
        "success": True,
        "data": {
            "account_id": env_account,
            "gateway_host": os.environ.get("IB_GATEWAY_HOST", "127.0.0.1"),
            "gateway_port": int(os.environ.get("IB_GATEWAY_PORT", "4002")),
            "is_configured": env_account is not None,
            "is_paper": env_account.startswith("DU") if env_account else None,
            "source": "environment" if env_account else "none",
        },
    }


@config_router.post("/ibkr")
async def set_ibkr_config(
    request: IBKRAccountConfigRequest,
    user=Depends(get_required_user),
):
    """
    Configure IBKR account for the current user.
    
    This stores the configuration per-user. In production,
    this should be stored encrypted in the database.
    """
    user_id = _get_user_id(user)
    
    # Validate account ID format
    if not request.account_id:
        raise HTTPException(status_code=400, detail="Account ID is required")
    
    # Basic validation: IB account IDs are typically 8 characters
    if len(request.account_id) < 6 or len(request.account_id) > 12:
        raise HTTPException(status_code=400, detail="Invalid account ID format")
    
    # Store configuration
    _user_ibkr_configs[user_id] = {
        "account_id": request.account_id,
        "gateway_host": request.gateway_host or "127.0.0.1",
        "gateway_port": request.gateway_port or 4002,
        "is_paper": request.is_paper,
    }
    
    logger.info(f"IBKR config updated for user {user_id}: account={request.account_id}")
    
    return {
        "success": True,
        "message": "IBKR configuration saved",
        "data": {
            "account_id": request.account_id,
            "gateway_host": request.gateway_host,
            "gateway_port": request.gateway_port,
            "is_paper": request.is_paper,
        },
    }


@config_router.delete("/ibkr")
async def clear_ibkr_config(user=Depends(get_required_user)):
    """
    Clear IBKR account configuration for the current user.
    """
    user_id = _get_user_id(user)
    
    if user_id in _user_ibkr_configs:
        del _user_ibkr_configs[user_id]
        logger.info(f"IBKR config cleared for user {user_id}")
    
    return {
        "success": True,
        "message": "IBKR configuration cleared",
    }


# ── Database Info Endpoint ──────────────────────────────────────────────

@config_router.get("/database")
async def get_database_info():
    """
    Get current database configuration (for diagnostics).
    """
    try:
        from auth.database import get_database_info
        info = get_database_info()
        
        return {
            "success": True,
            "data": info,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── System Info Endpoint ────────────────────────────────────────────────

@config_router.get("/system")
async def get_system_info():
    """
    Get system configuration overview.
    """
    try:
        # LLM info
        llm_provider = os.environ.get("LLM_PROVIDER", "anthropic")
        llm_configured = any([
            os.environ.get("ANTHROPIC_API_KEY"),
            os.environ.get("OPENAI_API_KEY"),
            os.environ.get("GOOGLE_API_KEY"),
        ])
        
        # Database info
        db_type = "postgresql" if os.environ.get("DATABASE_URL") else "sqlite"
        
        # IBKR info
        ibkr_configured = os.environ.get("IB_ACCOUNT_ID") is not None
        
        return {
            "success": True,
            "data": {
                "llm": {
                    "provider": llm_provider,
                    "configured": llm_configured,
                },
                "database": {
                    "type": db_type,
                },
                "ibkr": {
                    "configured": ibkr_configured,
                    "gateway_host": os.environ.get("IB_GATEWAY_HOST", "127.0.0.1"),
                    "gateway_port": int(os.environ.get("IB_GATEWAY_PORT", "4002")),
                },
                "environment": os.environ.get("ENVIRONMENT", "development"),
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
