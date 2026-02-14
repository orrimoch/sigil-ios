"""
LLM Risk Analyzer - REC-232, REC-272

Uses LLM (Claude/GPT/Gemini) to estimate risk from multiple metrics.
Provider selection is environment-based via LLM_PROVIDER env var.

Inputs: VIX, returns, sentiment, events
Outputs: risk_score 0-100, risk_level, risk_factors, recommendation, reasoning

Multi-layer cache:
- Memory cache: 1h TTL
- SQLite cache: 24h TTL

Cache key includes: ticker, price_bucket, vix_bucket, sentiment_bucket, return_bucket, date

API Endpoint: GET /api/v1/risk/analyze/{ticker}
"""

import json
import hashlib
import sqlite3
import os
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import logging
from enum import Enum
from pathlib import Path

# Load .env file (override=True to prefer .env over system env)
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=True)
except ImportError:
    pass

logger = logging.getLogger(__name__)

# Import LLM abstraction layer (REC-272)
try:
    from llm import get_llm_provider, LLMProvider, LLMProviderType
    LLM_ABSTRACTION_AVAILABLE = True
except ImportError:
    LLM_ABSTRACTION_AVAILABLE = False
    logger.warning("LLM abstraction layer not available, using direct Anthropic")

# Fallback model for direct Anthropic (backward compatibility)
CLAUDE_MODEL = "claude-3-5-haiku-20241022"

# Cache configuration
MEMORY_CACHE_TTL_SECONDS = 3600      # 1 hour
SQLITE_CACHE_TTL_SECONDS = 86400     # 24 hours
CACHE_DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'risk_cache.db')


class RiskLevel(str, Enum):
    """Risk level classification."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class RiskAnalysisResult:
    """Claude-generated risk analysis result."""
    ticker: str
    risk_score: int               # 0-100 (higher = riskier)
    risk_level: RiskLevel         # low/medium/high/critical
    risk_factors: List[str]       # Identified risk factors
    recommendation: str           # "reduce" / "hold" / "monitor"
    reasoning: str                # Natural language explanation
    confidence: float             # 0-1 confidence in analysis
    analyzed_at: datetime
    cached: bool = False          # Whether this was from cache
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "risk_score": self.risk_score,
            "risk_level": self.risk_level.value,
            "risk_factors": self.risk_factors,
            "recommendation": self.recommendation,
            "reasoning": self.reasoning,
            "confidence": round(self.confidence, 2),
            "analyzed_at": self.analyzed_at.isoformat(),
            "cached": self.cached,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RiskAnalysisResult":
        """Create from dictionary (cache deserialization)."""
        return cls(
            ticker=data["ticker"],
            risk_score=data["risk_score"],
            risk_level=RiskLevel(data["risk_level"]),
            risk_factors=data["risk_factors"],
            recommendation=data["recommendation"],
            reasoning=data["reasoning"],
            confidence=data["confidence"],
            analyzed_at=datetime.fromisoformat(data["analyzed_at"]),
            cached=data.get("cached", False),
        )


class RiskAnalysisCache:
    """
    Multi-layer cache for Claude risk analysis results.
    
    Layer 1: In-memory (1-hour TTL)
    Layer 2: SQLite (24-hour TTL)
    """
    
    def __init__(self, db_path: str = CACHE_DB_PATH):
        self.db_path = db_path
        self._memory_cache: Dict[str, tuple[float, RiskAnalysisResult]] = {}
        self._init_db()
        self._hits = 0
        self._misses = 0
    
    def _init_db(self) -> None:
        """Initialize SQLite cache database."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS risk_analysis_cache (
                    cache_key TEXT PRIMARY KEY,
                    ticker TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NOT NULL
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_risk_cache_expires ON risk_analysis_cache(expires_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_risk_cache_ticker ON risk_analysis_cache(ticker)"
            )
    
    def _make_cache_key(
        self,
        ticker: str,
        price: Optional[float],
        vix: Optional[float],
        sentiment: Optional[float],
        return_5d: Optional[float],
    ) -> str:
        """
        Create cache key using bucketed values.
        
        Bucketing reduces cache misses for minor value changes:
        - Price: $5 buckets
        - VIX: integer
        - Sentiment: 5-point buckets
        - 5-day return: 1 decimal precision
        - Date: daily granularity
        """
        # Bucket values to reduce cache misses
        price_bucket = round((price or 0) / 5) * 5
        vix_bucket = round(vix or 20)
        sentiment_bucket = round((sentiment or 50) / 5) * 5
        return_bucket = round((return_5d or 0) * 10) / 10
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        content = f"{ticker}:p{price_bucket}:v{vix_bucket}:s{sentiment_bucket}:r{return_bucket}:d{date_str}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def get(
        self,
        ticker: str,
        price: Optional[float] = None,
        vix: Optional[float] = None,
        sentiment: Optional[float] = None,
        return_5d: Optional[float] = None,
    ) -> Optional[RiskAnalysisResult]:
        """Get cached result if valid."""
        import time
        
        cache_key = self._make_cache_key(ticker, price, vix, sentiment, return_5d)
        current_time = time.time()
        
        # Check memory cache first
        if cache_key in self._memory_cache:
            cached_time, result = self._memory_cache[cache_key]
            if current_time - cached_time < MEMORY_CACHE_TTL_SECONDS:
                self._hits += 1
                result.cached = True
                return result
            else:
                del self._memory_cache[cache_key]
        
        # Check SQLite cache
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT result_json FROM risk_analysis_cache WHERE cache_key = ? AND expires_at > ?",
                    (cache_key, datetime.now(timezone.utc).isoformat())
                )
                row = cursor.fetchone()
                
                if row:
                    result_data = json.loads(row[0])
                    result = RiskAnalysisResult.from_dict(result_data)
                    result.cached = True
                    
                    # Populate memory cache
                    self._memory_cache[cache_key] = (current_time, result)
                    self._hits += 1
                    
                    return result
        except Exception as e:
            logger.warning(f"SQLite cache read error: {e}")
        
        self._misses += 1
        return None
    
    def get_any(self, ticker: str) -> Optional[RiskAnalysisResult]:
        """
        Get any cached result for a ticker, regardless of price/vix/etc.
        Returns the most recent cached result if available.
        Used for instant response before running full analysis.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """SELECT result_json FROM risk_analysis_cache 
                       WHERE ticker = ? AND expires_at > ?
                       ORDER BY created_at DESC LIMIT 1""",
                    (ticker, datetime.now(timezone.utc).isoformat())
                )
                row = cursor.fetchone()
                
                if row:
                    result_data = json.loads(row[0])
                    result = RiskAnalysisResult.from_dict(result_data)
                    result.cached = True
                    self._hits += 1
                    logger.debug(f"get_any cache hit for {ticker}")
                    return result
        except Exception as e:
            logger.warning(f"get_any cache error: {e}")
        
        return None
    
    def set(
        self,
        ticker: str,
        result: RiskAnalysisResult,
        price: Optional[float] = None,
        vix: Optional[float] = None,
        sentiment: Optional[float] = None,
        return_5d: Optional[float] = None,
    ) -> None:
        """Store result in both cache layers."""
        import time
        
        cache_key = self._make_cache_key(ticker, price, vix, sentiment, return_5d)
        current_time = time.time()
        
        # Memory cache
        self._memory_cache[cache_key] = (current_time, result)
        
        # SQLite cache
        try:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=SQLITE_CACHE_TTL_SECONDS)
            result_json = json.dumps(result.to_dict())
            
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """INSERT OR REPLACE INTO risk_analysis_cache 
                       (cache_key, ticker, result_json, expires_at) 
                       VALUES (?, ?, ?, ?)""",
                    (cache_key, ticker, result_json, expires_at.isoformat())
                )
        except Exception as e:
            logger.warning(f"SQLite cache write error: {e}")
    
    def invalidate_ticker(self, ticker: str) -> None:
        """Invalidate all cache entries for a ticker."""
        # Memory cache
        self._memory_cache = {
            k: v for k, v in self._memory_cache.items()
            if ticker not in k  # Simplistic, but works since ticker is in key
        }
        
        # SQLite cache
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM risk_analysis_cache WHERE ticker = ?", (ticker,))
        except Exception as e:
            logger.warning(f"Failed to invalidate ticker cache: {e}")
    
    def cleanup_expired(self) -> int:
        """Remove expired entries from SQLite. Returns count deleted."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "DELETE FROM risk_analysis_cache WHERE expires_at < ?",
                    (datetime.now(timezone.utc).isoformat(),)
                )
                return cursor.rowcount
        except Exception as e:
            logger.warning(f"Cache cleanup error: {e}")
            return 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = self._hits + self._misses
        hit_rate = self._hits / total_requests if total_requests > 0 else 0
        
        sqlite_count = 0
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM risk_analysis_cache")
                sqlite_count = cursor.fetchone()[0]
        except Exception:
            pass
        
        return {
            "memory_entries": len(self._memory_cache),
            "sqlite_entries": sqlite_count,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(hit_rate, 3),
        }
    
    def clear(self) -> None:
        """Clear all caches (for testing)."""
        self._memory_cache = {}
        self._hits = 0
        self._misses = 0
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM risk_analysis_cache")
        except Exception:
            pass


# Global cache instance
_risk_cache = RiskAnalysisCache()


# Risk analysis prompt template
RISK_ANALYSIS_PROMPT = """You are a quantitative risk analyst. Analyze the following position and provide a risk assessment.

**Position Data:**
Ticker: {ticker}
Current Price: ${price:.2f}
{entry_info}

**Market Conditions:**
- VIX: {vix:.1f} ({vix_regime})
- 5-day return: {return_5d:.2f}%
- 20-day return: {return_20d:.2f}%
- Sentiment score: {sentiment}/100

**Additional Context:**
{additional_context}

Based on these metrics, provide a JSON response with:
1. "risk_score": 0-100 (higher = more risk)
2. "risk_level": "low" | "medium" | "high" | "critical"
3. "risk_factors": list of top 3 identified risks
4. "recommendation": "reduce" | "hold" | "monitor"
5. "reasoning": 2-3 sentence explanation
6. "confidence": 0-1 confidence level

Consider:
- Volatility relative to normal levels
- Recent price momentum and trend
- Market sentiment
- Overall market conditions (VIX)
- Concentration risk

Respond ONLY with valid JSON, no markdown formatting."""


class ClaudeRiskAnalyzer:
    """
    LLM-powered risk analysis for stocks (REC-272).
    
    Supports multiple providers via LLM abstraction:
    - Anthropic (Claude) - default
    - OpenAI (GPT)
    - Google (Gemini)
    
    Provider selection via LLM_PROVIDER env var.
    Uses cost-efficient models by default (~$5/month).
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.model = CLAUDE_MODEL
        self.cache = _risk_cache
        
        # Initialize LLM provider (REC-272)
        self._llm_provider: Optional[LLMProvider] = None
        if LLM_ABSTRACTION_AVAILABLE:
            try:
                self._llm_provider = get_llm_provider()
                logger.info(f"Risk analyzer using LLM provider: {self._llm_provider.provider_type.value}")
            except Exception as e:
                logger.warning(f"Failed to initialize LLM provider for risk: {e}")
    
    @property
    def provider_name(self) -> str:
        """Get the current provider name."""
        if self._llm_provider:
            return self._llm_provider.provider_type.value
        return "anthropic-direct"
    
    async def analyze(
        self,
        ticker: str,
        price: float,
        vix: float = 20.0,
        vix_regime: str = "normal",
        return_5d: float = 0.0,
        return_20d: float = 0.0,
        sentiment: float = 50.0,
        entry_price: Optional[float] = None,
        additional_context: str = "",
        use_cache: bool = True,
    ) -> RiskAnalysisResult:
        """
        Analyze risk for a stock position.
        
        Args:
            ticker: Stock symbol
            price: Current price
            vix: Current VIX value
            vix_regime: VIX regime classification
            return_5d: 5-day return percentage
            return_20d: 20-day return percentage
            sentiment: Sentiment score 0-100
            entry_price: Position entry price (optional)
            additional_context: Any additional context
            use_cache: Whether to use cached results
            
        Returns:
            RiskAnalysisResult with analysis
        """
        # Check cache first
        if use_cache:
            cached = self.cache.get(
                ticker=ticker,
                price=price,
                vix=vix,
                sentiment=sentiment,
                return_5d=return_5d,
            )
            if cached is not None:
                logger.debug(f"Cache hit for {ticker}")
                return cached
        
        # Build entry info
        entry_info = ""
        if entry_price is not None:
            pnl_pct = ((price - entry_price) / entry_price) * 100
            entry_info = f"Entry Price: ${entry_price:.2f} (P&L: {pnl_pct:+.2f}%)"
        
        # Format prompt
        prompt = RISK_ANALYSIS_PROMPT.format(
            ticker=ticker,
            price=price,
            entry_info=entry_info,
            vix=vix,
            vix_regime=vix_regime,
            return_5d=return_5d,
            return_20d=return_20d,
            sentiment=sentiment,
            additional_context=additional_context or "None",
        )
        
        # Call Claude API
        try:
            result = await self._call_claude(prompt, ticker)
        except Exception as e:
            logger.error(f"Claude API error for {ticker}: {e}")
            # Return default conservative result
            result = self._default_result(ticker, str(e))
        
        # Cache the result
        self.cache.set(
            ticker=ticker,
            result=result,
            price=price,
            vix=vix,
            sentiment=sentiment,
            return_5d=return_5d,
        )
        
        return result
    
    async def _call_claude(self, prompt: str, ticker: str) -> RiskAnalysisResult:
        """Call LLM API and parse response (REC-272: multi-provider support)."""
        
        # Use LLM abstraction layer if available
        if self._llm_provider and self._llm_provider.is_available:
            try:
                response = await self._llm_provider.generate(
                    prompt=prompt,
                    max_tokens=512,
                )
                response_text = response.text
                logger.debug(f"Risk analysis via {self.provider_name}: {response.usage.total_tokens} tokens")
                return self._parse_response(response_text, ticker)
            except Exception as e:
                logger.error(f"LLM provider call failed: {e}")
                raise
        
        # Fallback to direct Anthropic API
        try:
            from anthropic import AsyncAnthropic
            
            client = AsyncAnthropic(api_key=self.api_key)
            
            message = await client.messages.create(
                model=self.model,
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}]
            )
            
            response_text = message.content[0].text
            
            # Parse JSON response
            return self._parse_response(response_text, ticker)
            
        except ImportError:
            logger.error("anthropic package not installed")
            return self._default_result(ticker, "anthropic package not installed")
        except Exception as e:
            logger.error(f"Claude API call failed: {e}")
            raise
    
    def _parse_response(self, response: str, ticker: str) -> RiskAnalysisResult:
        """Parse Claude's JSON response into RiskAnalysisResult."""
        try:
            # Try to extract JSON from response
            import re
            
            # Remove markdown code blocks if present
            clean_response = response.strip()
            if clean_response.startswith("```"):
                clean_response = re.sub(r'^```(?:json)?\n?', '', clean_response)
                clean_response = re.sub(r'\n?```$', '', clean_response)
            
            data = json.loads(clean_response)
            
            # Validate and normalize
            risk_score = max(0, min(100, int(data.get("risk_score", 50))))
            
            risk_level_str = data.get("risk_level", "medium").lower()
            try:
                risk_level = RiskLevel(risk_level_str)
            except ValueError:
                risk_level = RiskLevel.MEDIUM
            
            risk_factors = data.get("risk_factors", [])
            if not isinstance(risk_factors, list):
                risk_factors = [str(risk_factors)]
            risk_factors = risk_factors[:5]  # Limit to 5 factors
            
            recommendation = data.get("recommendation", "monitor").lower()
            if recommendation not in ["reduce", "hold", "monitor"]:
                recommendation = "monitor"
            
            reasoning = data.get("reasoning", "Analysis completed.")
            if not isinstance(reasoning, str):
                reasoning = str(reasoning)
            
            confidence = float(data.get("confidence", 0.7))
            confidence = max(0, min(1, confidence))
            
            return RiskAnalysisResult(
                ticker=ticker,
                risk_score=risk_score,
                risk_level=risk_level,
                risk_factors=risk_factors,
                recommendation=recommendation,
                reasoning=reasoning,
                confidence=confidence,
                analyzed_at=datetime.now(timezone.utc),
                cached=False,
            )
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Claude response for {ticker}: {e}")
            logger.debug(f"Response was: {response[:500]}")
            return self._default_result(ticker, f"Parse error: {e}")
    
    def _default_result(self, ticker: str, error_reason: str) -> RiskAnalysisResult:
        """Return conservative default result on error."""
        return RiskAnalysisResult(
            ticker=ticker,
            risk_score=60,  # Conservative moderate risk
            risk_level=RiskLevel.MEDIUM,
            risk_factors=["Analysis unavailable", error_reason],
            recommendation="monitor",
            reasoning=f"Unable to complete analysis: {error_reason}. Defaulting to moderate risk.",
            confidence=0.3,
            analyzed_at=datetime.now(timezone.utc),
            cached=False,
        )
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return self.cache.get_stats()


# Synchronous wrapper
def analyze_risk_sync(
    ticker: str,
    price: float,
    vix: float = 20.0,
    vix_regime: str = "normal",
    return_5d: float = 0.0,
    return_20d: float = 0.0,
    sentiment: float = 50.0,
    entry_price: Optional[float] = None,
    use_cache: bool = True,
) -> RiskAnalysisResult:
    """Synchronous version of risk analysis."""
    import asyncio
    
    analyzer = ClaudeRiskAnalyzer()
    
    async def _run():
        return await analyzer.analyze(
            ticker=ticker,
            price=price,
            vix=vix,
            vix_regime=vix_regime,
            return_5d=return_5d,
            return_20d=return_20d,
            sentiment=sentiment,
            entry_price=entry_price,
            use_cache=use_cache,
        )
    
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Can't use run_until_complete in running loop
            # Return cached or default
            cached = _risk_cache.get(
                ticker=ticker,
                price=price,
                vix=vix,
                sentiment=sentiment,
                return_5d=return_5d,
            )
            if cached:
                return cached
            return analyzer._default_result(ticker, "Async context conflict")
        return loop.run_until_complete(_run())
    except RuntimeError:
        return asyncio.run(_run())


def get_risk_cache_stats() -> Dict[str, Any]:
    """Get global cache statistics."""
    return _risk_cache.get_stats()


def clear_risk_cache() -> None:
    """Clear the risk analysis cache (for testing)."""
    _risk_cache.clear()


def invalidate_risk_cache_for_ticker(ticker: str) -> None:
    """Invalidate cache entries for a specific ticker."""
    _risk_cache.invalidate_ticker(ticker)


async def warm_cache_for_tickers(
    tickers: List[str],
    force: bool = False,
) -> Dict[str, Any]:
    """
    Pre-warm the risk analysis cache for a list of tickers.
    
    Runs Claude analysis in the background for tickers without cached results.
    Used to pre-populate cache for portfolio holdings on login.
    
    Args:
        tickers: List of stock symbols to analyze
        force: If True, re-analyze even if cached
        
    Returns:
        Summary of what was cached/skipped/failed
    """
    from concurrent.futures import ThreadPoolExecutor
    import asyncio
    
    analyzer = ClaudeRiskAnalyzer()
    results = {
        "requested": len(tickers),
        "already_cached": 0,
        "analyzed": 0,
        "failed": 0,
        "details": [],
    }
    
    # Check which tickers need analysis
    tickers_to_analyze = []
    for ticker in tickers:
        if not force:
            cached = analyzer.cache.get_any(ticker)
            if cached is not None:
                results["already_cached"] += 1
                results["details"].append({
                    "ticker": ticker,
                    "status": "cached",
                    "risk_score": cached.risk_score,
                })
                continue
        tickers_to_analyze.append(ticker)
    
    if not tickers_to_analyze:
        logger.info(f"All {len(tickers)} tickers already cached")
        return results
    
    logger.info(f"Warming cache for {len(tickers_to_analyze)} tickers: {tickers_to_analyze}")
    
    # Fetch market data for analysis
    try:
        from .vix_service import fetch_vix
        vix_data = await fetch_vix(use_cache=True)
        vix = vix_data.value
        vix_regime = vix_data.regime
    except Exception:
        vix = 20.0
        vix_regime = "normal"
    
    # Analyze each ticker
    for ticker in tickers_to_analyze:
        try:
            # Get price and returns data
            price = 100.0
            return_5d = 0.0
            return_20d = 0.0
            sentiment = 50.0
            
            try:
                # Use run_in_executor to avoid blocking
                loop = asyncio.get_event_loop()
                price_data = await loop.run_in_executor(
                    None, _fetch_ticker_data_sync, ticker
                )
                if price_data:
                    price = price_data.get("price", 100.0)
                    return_5d = price_data.get("return_5d", 0.0)
                    return_20d = price_data.get("return_20d", 0.0)
                    sentiment = price_data.get("sentiment", 50.0)
            except Exception as e:
                logger.warning(f"Failed to fetch data for {ticker}: {e}")
            
            # Run Claude analysis
            result = await analyzer.analyze(
                ticker=ticker,
                price=price,
                vix=vix,
                vix_regime=vix_regime,
                return_5d=return_5d,
                return_20d=return_20d,
                sentiment=sentiment,
                use_cache=False,  # Force fresh analysis
            )
            
            results["analyzed"] += 1
            results["details"].append({
                "ticker": ticker,
                "status": "analyzed",
                "risk_score": result.risk_score,
                "risk_level": result.risk_level.value,
            })
            logger.info(f"Analyzed {ticker}: risk_score={result.risk_score}")
            
        except Exception as e:
            results["failed"] += 1
            results["details"].append({
                "ticker": ticker,
                "status": "failed",
                "error": str(e),
            })
            logger.error(f"Failed to analyze {ticker}: {e}")
    
    return results


def _fetch_ticker_data_sync(ticker: str) -> Dict[str, Any]:
    """
    Synchronously fetch ticker data for risk analysis.
    Called via run_in_executor to avoid blocking async loop.
    """
    try:
        import yfinance as yf
        
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1mo")
        
        if hist.empty:
            return None
        
        current_price = float(hist['Close'].iloc[-1])
        
        # Calculate returns
        if len(hist) >= 5:
            return_5d = ((hist['Close'].iloc[-1] / hist['Close'].iloc[-5]) - 1) * 100
        else:
            return_5d = 0.0
            
        if len(hist) >= 20:
            return_20d = ((hist['Close'].iloc[-1] / hist['Close'].iloc[-20]) - 1) * 100
        else:
            return_20d = return_5d
        
        return {
            "price": current_price,
            "return_5d": float(return_5d),
            "return_20d": float(return_20d),
            "sentiment": 50.0,  # Default, would need separate lookup
        }
        
    except Exception as e:
        logger.warning(f"yfinance fetch failed for {ticker}: {e}")
        return None
