"""
Agentic Sentiment Analysis using Claude API (REC-172)

LLM-powered sentiment analysis that provides nuanced, explainable scores.
Replaces keyword-based analysis with contextual understanding.

Target: Reduce neutral-stuck stocks from 62% to <15%
"""

import json
import re
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict, field
from pathlib import Path
from enum import Enum
from loguru import logger

from .sentiment_config import get_sentiment_config, SentimentModel
from .claude_client import get_claude_client, ClaudeClient


# LLM-001: Sanitize headlines to prevent prompt injection
def sanitize_headline(text: str) -> str:
    """
    Sanitize headline text before sending to LLM.
    
    Removes:
    - Control characters
    - Excessive whitespace
    - Potential prompt injection patterns
    - HTML/script tags
    
    Args:
        text: Raw headline text
    
    Returns:
        Sanitized text safe for LLM processing
    """
    if not text:
        return ""
    
    # Remove control characters except newlines and tabs
    import unicodedata
    text = ''.join(
        char for char in text
        if unicodedata.category(char) != 'Cc' or char in '\n\t'
    )
    
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    
    # Remove potential prompt injection patterns
    # Block system prompt overrides
    injection_patterns = [
        r'(?i)ignore\s+(previous|above|all)\s+(instructions?|prompts?)',
        r'(?i)disregard\s+(previous|above|all)',
        r'(?i)system\s*:\s*',
        r'(?i)assistant\s*:\s*',
        r'(?i)human\s*:\s*',
        r'(?i)user\s*:\s*',
        r'```',  # Code blocks
        r'\[\[.*?\]\]',  # Double brackets
    ]
    
    for pattern in injection_patterns:
        text = re.sub(pattern, '', text)
    
    # Normalize whitespace
    text = ' '.join(text.split())
    
    # Limit length to prevent token stuffing
    max_len = 500
    if len(text) > max_len:
        text = text[:max_len] + "..."
    
    return text.strip()


class SentimentLabel(str, Enum):
    """7-level sentiment classification for nuanced analysis."""
    VERY_BULLISH = "very_bullish"      # 85-100
    BULLISH = "bullish"                 # 70-84
    SLIGHTLY_BULLISH = "slightly_bullish"  # 55-69
    NEUTRAL = "neutral"                 # 45-54
    SLIGHTLY_BEARISH = "slightly_bearish"  # 31-44
    BEARISH = "bearish"                 # 16-30
    VERY_BEARISH = "very_bearish"       # 0-15
    
    @classmethod
    def from_score(cls, score: float) -> "SentimentLabel":
        """Convert score (0-100) to sentiment label."""
        if score >= 85:
            return cls.VERY_BULLISH
        elif score >= 70:
            return cls.BULLISH
        elif score >= 55:
            return cls.SLIGHTLY_BULLISH
        elif score >= 45:
            return cls.NEUTRAL
        elif score >= 31:
            return cls.SLIGHTLY_BEARISH
        elif score >= 16:
            return cls.BEARISH
        else:
            return cls.VERY_BEARISH


@dataclass
class ArticleAnalysis:
    """Analysis of a single news article."""
    headline: str
    sentiment: SentimentLabel
    score: float  # 0-100
    key_factors: List[str] = field(default_factory=list)  # Max 3
    relevance: float = 0.5  # 0-1, how relevant to the stock


@dataclass
class AgentSentimentResult:
    """Complete sentiment analysis for a ticker."""
    ticker: str
    overall_score: float  # 0-100
    overall_sentiment: SentimentLabel
    confidence: float  # 0-1
    rationale: str  # 2-3 sentence explanation
    article_analyses: List[ArticleAnalysis] = field(default_factory=list)
    bullish_factors: List[str] = field(default_factory=list)  # Max 3
    bearish_factors: List[str] = field(default_factory=list)  # Max 3
    analyzed_at: str = ""
    model_used: str = ""
    
    def __post_init__(self):
        if not self.analyzed_at:
            self.analyzed_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "ticker": self.ticker,
            "overall_score": self.overall_score,
            "overall_sentiment": self.overall_sentiment.value,
            "confidence": self.confidence,
            "rationale": self.rationale,
            "article_analyses": [
                {
                    "headline": a.headline,
                    "sentiment": a.sentiment.value,
                    "score": a.score,
                    "key_factors": a.key_factors,
                    "relevance": a.relevance,
                }
                for a in self.article_analyses
            ],
            "bullish_factors": self.bullish_factors,
            "bearish_factors": self.bearish_factors,
            "analyzed_at": self.analyzed_at,
            "model_used": self.model_used,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentSentimentResult":
        """Create from dict (for cache loading)."""
        article_analyses = [
            ArticleAnalysis(
                headline=a["headline"],
                sentiment=SentimentLabel(a["sentiment"]),
                score=a["score"],
                key_factors=a.get("key_factors", []),
                relevance=a.get("relevance", 0.5),
            )
            for a in data.get("article_analyses", [])
        ]
        
        return cls(
            ticker=data["ticker"],
            overall_score=data["overall_score"],
            overall_sentiment=SentimentLabel(data["overall_sentiment"]),
            confidence=data["confidence"],
            rationale=data["rationale"],
            article_analyses=article_analyses,
            bullish_factors=data.get("bullish_factors", []),
            bearish_factors=data.get("bearish_factors", []),
            analyzed_at=data.get("analyzed_at", ""),
            model_used=data.get("model_used", ""),
        )


# System prompt for the sentiment analysis agent
SENTIMENT_AGENT_SYSTEM_PROMPT = """You are a professional financial sentiment analyst for Sigil, 
an institutional-grade stock scoring system. Your task is to analyze news articles about a 
specific stock and provide a nuanced sentiment assessment.

## Your Analysis Framework

1. **Sentiment Classification**
   - VERY_BULLISH: Strong positive catalysts, beat expectations, major wins (score 85-100)
   - BULLISH: Positive news, growth signals, favorable outlook (score 70-84)
   - SLIGHTLY_BULLISH: Mildly positive, cautious optimism (score 55-69)
   - NEUTRAL: Mixed signals, no clear direction, routine news (score 45-54)
   - SLIGHTLY_BEARISH: Minor concerns, headwinds mentioned (score 31-44)
   - BEARISH: Negative developments, missed expectations (score 16-30)
   - VERY_BEARISH: Major problems, investigations, significant losses (score 0-15)

2. **Weighting Factors**
   Consider these when determining score magnitude:
   - Recency of news (newer = more weight)
   - Source credibility (WSJ/Reuters/Bloomberg > blogs/social media)
   - Specificity to the company (direct mention > sector news)
   - Magnitude of impact (earnings beat/miss amount matters)
   - Analyst consensus changes
   - Management guidance changes

3. **What to Ignore**
   - General market commentary not specific to this stock
   - Opinions without factual basis
   - Stale news rehashed in new articles
   - Clickbait headlines contradicted by article content

4. **Confidence Guidelines**
   - High (0.8-1.0): Multiple corroborating sources, clear directional signal
   - Medium (0.5-0.7): Mixed signals or limited sources
   - Low (0.3-0.4): Uncertain, conflicting information

## Output Requirements
You MUST respond with valid JSON only. No markdown, no explanation outside the JSON.
Match the schema exactly as requested."""


# JSON schema for structured output (documentation)
OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["ticker", "overall_score", "overall_sentiment", "confidence", "rationale", "article_analyses"],
    "properties": {
        "ticker": {"type": "string"},
        "overall_score": {"type": "number", "minimum": 0, "maximum": 100},
        "overall_sentiment": {
            "type": "string",
            "enum": ["very_bullish", "bullish", "slightly_bullish", "neutral", 
                    "slightly_bearish", "bearish", "very_bearish"]
        },
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "rationale": {"type": "string", "maxLength": 500},
        "article_analyses": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["headline", "sentiment", "score"],
                "properties": {
                    "headline": {"type": "string"},
                    "sentiment": {"type": "string"},
                    "score": {"type": "number"},
                    "key_factors": {"type": "array", "items": {"type": "string"}, "maxItems": 3},
                    "relevance": {"type": "number"}
                }
            }
        },
        "bullish_factors": {"type": "array", "items": {"type": "string"}, "maxItems": 3},
        "bearish_factors": {"type": "array", "items": {"type": "string"}, "maxItems": 3}
    }
}


class SentimentCache:
    """File-based cache for sentiment results with TTL."""
    
    def __init__(self, cache_dir: Path, ttl_hours: int = 24):
        self.cache_dir = cache_dir
        self.ttl_hours = ttl_hours
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _cache_path(self, ticker: str) -> Path:
        return self.cache_dir / f"{ticker.upper()}.json"
    
    def get(self, ticker: str) -> Optional[AgentSentimentResult]:
        """Get cached result if fresh."""
        path = self._cache_path(ticker)
        if not path.exists():
            return None
        
        try:
            data = json.loads(path.read_text())
            
            # Check freshness
            analyzed_at = datetime.fromisoformat(data.get("analyzed_at", "2000-01-01"))
            age_hours = (datetime.now() - analyzed_at).total_seconds() / 3600
            
            if age_hours > self.ttl_hours:
                logger.debug(f"Cache expired for {ticker} ({age_hours:.1f}h old)")
                return None
            
            return AgentSentimentResult.from_dict(data)
            
        except Exception as e:
            logger.warning(f"Failed to load cache for {ticker}: {e}")
            return None
    
    def set(self, result: AgentSentimentResult) -> None:
        """Cache a result."""
        path = self._cache_path(result.ticker)
        try:
            path.write_text(json.dumps(result.to_dict(), indent=2))
        except Exception as e:
            logger.warning(f"Failed to cache result for {result.ticker}: {e}")
    
    def invalidate(self, ticker: str) -> bool:
        """Remove cached result. Returns True if existed."""
        path = self._cache_path(ticker)
        if path.exists():
            path.unlink()
            return True
        return False
    
    def invalidate_all(self) -> int:
        """Clear all cache. Returns count removed."""
        count = 0
        for path in self.cache_dir.glob("*.json"):
            if path.name != "usage.json":  # Don't delete usage tracking
                path.unlink()
                count += 1
        return count
    
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        files = list(self.cache_dir.glob("*.json"))
        files = [f for f in files if f.name != "usage.json"]
        
        fresh = 0
        stale = 0
        
        for f in files:
            try:
                data = json.loads(f.read_text())
                analyzed_at = datetime.fromisoformat(data.get("analyzed_at", "2000-01-01"))
                age_hours = (datetime.now() - analyzed_at).total_seconds() / 3600
                if age_hours <= self.ttl_hours:
                    fresh += 1
                else:
                    stale += 1
            except:
                stale += 1
        
        return {
            "total": len(files),
            "fresh": fresh,
            "stale": stale,
            "ttl_hours": self.ttl_hours,
        }


class AgenticSentimentAnalyzer:
    """
    Claude-powered sentiment analyzer for financial news.
    
    Features:
    - Nuanced 7-level sentiment classification
    - Per-article analysis with relevance scoring
    - Bullish/bearish factor extraction
    - Confidence scoring
    - Result caching
    - Graceful fallback on errors
    """
    
    def __init__(
        self,
        client: Optional[ClaudeClient] = None,
        cache_ttl_hours: int = 24,
    ):
        """
        Initialize the analyzer.
        
        Args:
            client: ClaudeClient instance (uses global if None)
            cache_ttl_hours: How long to cache results
        """
        self.client = client or get_claude_client()
        self.config = get_sentiment_config()
        
        # Initialize cache
        self.cache = SentimentCache(
            cache_dir=self.config.cache_dir,
            ttl_hours=cache_ttl_hours,
        )
    
    @property
    def is_available(self) -> bool:
        """Check if LLM analysis is available."""
        return self.client.is_available
    
    def analyze(
        self,
        ticker: str,
        articles: List[Dict],
        use_cache: bool = True,
    ) -> AgentSentimentResult:
        """
        Analyze sentiment for a ticker based on news articles.
        
        Args:
            ticker: Stock symbol (e.g., "AAPL")
            articles: List of article dicts with title, summary, published, source
            use_cache: Whether to check/use cache
        
        Returns:
            AgentSentimentResult with full analysis
        
        Raises:
            RuntimeError: If LLM unavailable and no cached result
        """
        ticker = ticker.upper()
        
        # Check cache first
        if use_cache:
            cached = self.cache.get(ticker)
            if cached:
                logger.debug(f"Cache hit for {ticker}")
                return cached
        
        # Verify LLM is available
        if not self.is_available:
            raise RuntimeError(f"LLM unavailable and no cache for {ticker}")
        
        # Handle empty articles
        if not articles:
            return self._neutral_result(ticker, "No news articles found")
        
        # Prepare the prompt
        user_message = self._build_prompt(ticker, articles)
        
        # Call Claude
        response = self.client.analyze(
            system_prompt=SENTIMENT_AGENT_SYSTEM_PROMPT,
            user_message=user_message,
        )
        
        if response is None:
            raise RuntimeError(f"LLM returned no response for {ticker}")
        
        # Parse response into result
        result = self._parse_response(response, ticker)
        result.model_used = self.config.claude_model
        
        # Cache the result
        if use_cache:
            self.cache.set(result)
        
        logger.info(
            f"Analyzed {ticker}: {result.overall_score:.0f} "
            f"({result.overall_sentiment.value}, conf={result.confidence:.2f})"
        )
        
        return result
    
    def analyze_batch(
        self,
        tickers_articles: Dict[str, List[Dict]],
        use_cache: bool = True,
    ) -> Dict[str, AgentSentimentResult]:
        """
        Analyze multiple tickers sequentially.
        
        Args:
            tickers_articles: Dict mapping ticker -> articles list
            use_cache: Whether to use caching
        
        Returns:
            Dict mapping ticker -> AgentSentimentResult
        """
        import time
        
        results = {}
        failed = []
        total = len(tickers_articles)
        
        for i, (ticker, articles) in enumerate(tickers_articles.items(), 1):
            try:
                result = self.analyze(ticker, articles, use_cache=use_cache)
                results[ticker] = result
                
                # Progress logging
                if i % 10 == 0 or i == total:
                    logger.info(f"Progress: {i}/{total} tickers analyzed")
                
                # Rate limiting (handled by client, but add small buffer)
                time.sleep(0.5)
                
            except Exception as e:
                logger.warning(f"Failed to analyze {ticker}: {e}")
                failed.append((ticker, str(e)))
        
        if failed:
            logger.warning(f"Failed: {len(failed)}/{total} tickers")
        
        return results
    
    def _build_prompt(self, ticker: str, articles: List[Dict]) -> str:
        """Build the user message prompt."""
        # Format articles (max 10)
        articles_text = self._format_articles(articles[:10])
        
        return f"""Analyze the sentiment for **{ticker}** based on these recent news articles:

{articles_text}

Respond with JSON only, matching this structure:
{{
  "ticker": "{ticker}",
  "overall_score": <number 0-100>,
  "overall_sentiment": "<very_bullish|bullish|slightly_bullish|neutral|slightly_bearish|bearish|very_bearish>",
  "confidence": <number 0-1>,
  "rationale": "<2-3 sentence explanation>",
  "article_analyses": [
    {{
      "headline": "<headline>",
      "sentiment": "<label>",
      "score": <0-100>,
      "key_factors": ["<factor>", ...],
      "relevance": <0-1>
    }}
  ],
  "bullish_factors": ["<factor>", ...],
  "bearish_factors": ["<factor>", ...]
}}"""
    
    def _format_articles(self, articles: List[Dict]) -> str:
        """Format articles for the prompt."""
        formatted = []
        
        for i, article in enumerate(articles, 1):
            published = article.get("published", "Unknown date")
            source = article.get("source", "Unknown")
            # LLM-001: Sanitize all text content before LLM processing
            title = sanitize_headline(article.get("title", "No title"))
            summary = sanitize_headline(article.get("summary", ""))
            
            # Truncate summary to save tokens
            if len(summary) > 300:
                summary = summary[:300] + "..."
            
            formatted.append(f"""**Article {i}:**
- Date: {published}
- Source: {source}
- Headline: {title}
- Summary: {summary}
""")
        
        return "\n".join(formatted)
    
    def _parse_response(self, data: Dict, ticker: str) -> AgentSentimentResult:
        """Parse LLM response dict into AgentSentimentResult."""
        # Parse article analyses
        article_analyses = []
        for a in data.get("article_analyses", []):
            try:
                sentiment_str = a.get("sentiment", "neutral").lower()
                # Handle variations
                sentiment_str = sentiment_str.replace("-", "_").replace(" ", "_")
                
                article_analyses.append(ArticleAnalysis(
                    headline=a.get("headline", "")[:200],
                    sentiment=SentimentLabel(sentiment_str),
                    score=float(a.get("score", 50)),
                    key_factors=a.get("key_factors", [])[:3],
                    relevance=float(a.get("relevance", 0.5)),
                ))
            except Exception as e:
                logger.warning(f"Failed to parse article analysis: {e}")
        
        # Parse overall sentiment
        sentiment_str = data.get("overall_sentiment", "neutral").lower()
        sentiment_str = sentiment_str.replace("-", "_").replace(" ", "_")
        
        try:
            overall_sentiment = SentimentLabel(sentiment_str)
        except ValueError:
            # Fallback: derive from score
            overall_sentiment = SentimentLabel.from_score(data.get("overall_score", 50))
        
        # HIGH FIX SE-001: Validate score bounds (0-100)
        raw_score = float(data.get("overall_score", 50))
        validated_score = max(0.0, min(100.0, raw_score))
        
        return AgentSentimentResult(
            ticker=ticker,
            overall_score=validated_score,
            overall_sentiment=overall_sentiment,
            confidence=max(0.0, min(1.0, float(data.get("confidence", 0.5)))),
            rationale=data.get("rationale", "")[:500],
            article_analyses=article_analyses,
            bullish_factors=data.get("bullish_factors", [])[:3],
            bearish_factors=data.get("bearish_factors", [])[:3],
        )
    
    def _neutral_result(self, ticker: str, reason: str) -> AgentSentimentResult:
        """Create a neutral result for edge cases."""
        return AgentSentimentResult(
            ticker=ticker,
            overall_score=50.0,
            overall_sentiment=SentimentLabel.NEUTRAL,
            confidence=0.3,
            rationale=reason,
            article_analyses=[],
            bullish_factors=[],
            bearish_factors=[],
        )
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return self.cache.stats()
    
    def clear_cache(self) -> int:
        """Clear all cached results. Returns count cleared."""
        return self.cache.invalidate_all()


# Global analyzer instance (lazy-loaded)
_analyzer: Optional[AgenticSentimentAnalyzer] = None


def get_agentic_analyzer() -> AgenticSentimentAnalyzer:
    """Get the global agentic sentiment analyzer (lazy-loaded)."""
    global _analyzer
    if _analyzer is None:
        _analyzer = AgenticSentimentAnalyzer()
    return _analyzer


def reload_agentic_analyzer() -> AgenticSentimentAnalyzer:
    """Force reload of the analyzer."""
    global _analyzer
    _analyzer = AgenticSentimentAnalyzer()
    return _analyzer


# CLI for testing
if __name__ == "__main__":
    import sys
    from dotenv import load_dotenv
    load_dotenv()
    
    logger.add(sys.stderr, level="DEBUG")
    
    print("\n=== Agentic Sentiment Analyzer Test ===\n")
    
    analyzer = get_agentic_analyzer()
    
    print(f"LLM Available: {analyzer.is_available}")
    print(f"Cache Stats: {analyzer.get_cache_stats()}")
    
    if analyzer.is_available:
        # Test with sample articles
        test_articles = [
            {
                "title": "Apple Reports Record Q4 Revenue, Beats Expectations",
                "summary": "Apple Inc. reported quarterly revenue of $89.5 billion, up 8% year over year, beating analyst estimates of $87.3 billion. iPhone sales grew 10%.",
                "published": "2026-02-05",
                "source": "Reuters"
            },
            {
                "title": "Apple Faces Antitrust Scrutiny in EU Over App Store Practices",
                "summary": "European regulators announced new investigation into Apple's App Store policies, potentially leading to significant fines.",
                "published": "2026-02-04",
                "source": "Bloomberg"
            }
        ]
        
        print("\nAnalyzing AAPL with sample articles...")
        result = analyzer.analyze("AAPL", test_articles, use_cache=False)
        
        print(f"\n✅ Result:")
        print(f"   Score: {result.overall_score:.1f}/100")
        print(f"   Sentiment: {result.overall_sentiment.value}")
        print(f"   Confidence: {result.confidence:.2f}")
        print(f"   Rationale: {result.rationale}")
        print(f"   Bullish: {result.bullish_factors}")
        print(f"   Bearish: {result.bearish_factors}")
    else:
        print("\n❌ LLM not available. Check ANTHROPIC_API_KEY.")
