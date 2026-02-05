<img src="sigil_logo.jpg" alt="Sigil" width="240" />

# Agentic Sentiment Analysis — Technical Specification

**Project:** Sigil iOS Trading App  
**Author:** AI Engineer (Subagent)  
**Date:** February 5, 2026  
**Version:** 1.0  
**Status:** Implementation Ready

---

## Executive Summary

This specification details the upgrade from keyword-based sentiment scoring to LLM-powered (Claude API) sentiment analysis. The current system scores 420 of 677 stocks at neutral (50.0) because keyword matching fails to capture nuanced financial sentiment. The agentic approach will analyze news context deeply, providing differentiated scores across the full 0-100 range.

**Expected Outcomes:**
- Reduce neutral-stuck stocks from 62% to <15%
- Capture nuanced sentiment (e.g., "cautious optimism", "mixed signals")
- Provide explainable sentiment rationale per stock
- Maintain backward compatibility with existing pipeline

---

## 1. Architecture Overview

### High-Level Design

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         AGENTIC SENTIMENT PIPELINE                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────┐    ┌─────────────────┐    ┌──────────────────────────┐   │
│   │ News Cache  │───▶│ Article Batcher │───▶│ LLM Sentiment Analyzer   │   │
│   │ (existing)  │    │ (by ticker)     │    │ (Claude claude-sonnet-4-20250514)      │   │
│   └─────────────┘    └─────────────────┘    └────────────┬─────────────┘   │
│                                                          │                  │
│                                    ┌─────────────────────▼───────────────┐  │
│                                    │      Score Aggregator              │  │
│                                    │  - Weighted by recency/tier        │  │
│                                    │  - Confidence-adjusted             │  │
│                                    └─────────────────────┬───────────────┘  │
│                                                          │                  │
│   ┌─────────────────┐    ┌──────────────────────────────▼───────────────┐  │
│   │ Fallback Engine │◀──▶│     Result Cache (24h TTL)                   │  │
│   │ (keyword/sector)│    │  - Per-ticker sentiment + rationale          │  │
│   └─────────────────┘    └──────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Processing Strategy

**Batch Processing (Weekly Pipeline)**
- Process all 677 stocks during weekly scoring run
- Batch articles by ticker (1-10 articles each)
- Single LLM call per ticker (not per article)
- Cache results for 24 hours

**On-Demand Processing (API Requests)**
- Check cache first
- If miss, analyze top 5 articles
- Return cached keyword fallback if LLM unavailable

---

## 2. Agent Design

### System Prompt

```python
SENTIMENT_AGENT_SYSTEM_PROMPT = """You are a professional financial sentiment analyst for Sigil, 
an institutional-grade stock scoring system. Your task is to analyze news articles about a 
specific stock and provide a nuanced sentiment assessment.

## Your Analysis Framework

1. **Sentiment Classification**
   - VERY_BULLISH: Strong positive catalysts, beat expectations, major wins
   - BULLISH: Positive news, growth signals, favorable outlook
   - SLIGHTLY_BULLISH: Mildly positive, cautious optimism
   - NEUTRAL: Mixed signals, no clear direction, routine news
   - SLIGHTLY_BEARISH: Minor concerns, headwinds mentioned
   - BEARISH: Negative developments, missed expectations
   - VERY_BEARISH: Major problems, investigations, significant losses

2. **Scoring Guidelines**
   - Score 0-100 where 50 is neutral
   - VERY_BULLISH: 85-100
   - BULLISH: 70-84
   - SLIGHTLY_BULLISH: 55-69
   - NEUTRAL: 45-54
   - SLIGHTLY_BEARISH: 31-44
   - BEARISH: 16-30
   - VERY_BEARISH: 0-15

3. **Weighting Factors**
   Consider these when determining score magnitude:
   - Recency of news (newer = more weight)
   - Source credibility (WSJ/Reuters > blogs)
   - Specificity to the company (direct mention > sector news)
   - Magnitude of impact (earnings beat/miss amount matters)
   - Analyst consensus changes
   - Management guidance

4. **What to Ignore**
   - General market commentary not specific to this stock
   - Opinions without factual basis
   - Stale news rehashed in new articles
   - Clickbait headlines contradicted by article content

## Output Format
You MUST respond with valid JSON matching this schema exactly. No markdown, no explanation outside the JSON.
"""
```

### Output Schema

```python
from dataclasses import dataclass
from typing import List, Optional
from enum import Enum

class SentimentLabel(str, Enum):
    VERY_BULLISH = "very_bullish"
    BULLISH = "bullish"
    SLIGHTLY_BULLISH = "slightly_bullish"
    NEUTRAL = "neutral"
    SLIGHTLY_BEARISH = "slightly_bearish"
    BEARISH = "bearish"
    VERY_BEARISH = "very_bearish"

@dataclass
class ArticleAnalysis:
    """Analysis of a single article."""
    headline: str
    sentiment: SentimentLabel
    score: float  # 0-100
    key_factors: List[str]  # Max 3 bullet points
    relevance: float  # 0-1, how relevant to this stock

@dataclass
class AgentSentimentResult:
    """Complete sentiment analysis for a ticker."""
    ticker: str
    overall_score: float  # 0-100
    overall_sentiment: SentimentLabel
    confidence: float  # 0-1
    rationale: str  # 2-3 sentence explanation
    article_analyses: List[ArticleAnalysis]
    bullish_factors: List[str]  # Max 3
    bearish_factors: List[str]  # Max 3
    analyzed_at: str  # ISO timestamp
```

### JSON Schema for LLM

```json
{
  "type": "object",
  "required": ["ticker", "overall_score", "overall_sentiment", "confidence", "rationale", "article_analyses"],
  "properties": {
    "ticker": {"type": "string"},
    "overall_score": {"type": "number", "minimum": 0, "maximum": 100},
    "overall_sentiment": {
      "type": "string",
      "enum": ["very_bullish", "bullish", "slightly_bullish", "neutral", "slightly_bearish", "bearish", "very_bearish"]
    },
    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    "rationale": {"type": "string", "maxLength": 500},
    "article_analyses": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["headline", "sentiment", "score", "key_factors", "relevance"],
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
```

---

## 3. Integration Points

### File: `backend/src/scoring/sentiment_score.py`

**Minimal Changes Required:**

```python
# Add at top of file
from scoring.agentic_sentiment import AgenticSentimentAnalyzer, AgentSentimentResult

# Modify config section
SENTIMENT_MODEL = os.environ.get("SENTIMENT_MODEL", "keyword")  # "keyword" | "llm" | "hybrid"
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# Add lazy-loaded analyzer
_agentic_analyzer: Optional[AgenticSentimentAnalyzer] = None

def _get_agentic_analyzer() -> Optional[AgenticSentimentAnalyzer]:
    """Lazy-load the agentic analyzer (only when needed)."""
    global _agentic_analyzer
    if _agentic_analyzer is None and ANTHROPIC_API_KEY:
        _agentic_analyzer = AgenticSentimentAnalyzer(api_key=ANTHROPIC_API_KEY)
    return _agentic_analyzer
```

**Modified `calculate_sentiment_score_for_ticker()`:**

```python
def calculate_sentiment_score_for_ticker(
    ticker: str,
    articles: List[Dict] = None,
    hours: int = 168
) -> SentimentScoreResult:
    """
    Calculate sentiment score for a single stock.
    Uses LLM analysis if configured and available, otherwise falls back to keyword.
    """
    if articles is None:
        articles = fetch_news_for_ticker(ticker, hours=hours)
    
    # Try LLM analysis if configured
    if SENTIMENT_MODEL in ("llm", "hybrid") and articles:
        analyzer = _get_agentic_analyzer()
        if analyzer:
            try:
                agent_result = analyzer.analyze(ticker, articles[:10])  # Max 10 articles
                return _convert_agent_result(agent_result)
            except Exception as e:
                logger.warning(f"LLM analysis failed for {ticker}, falling back: {e}")
    
    # Fallback to keyword analysis (existing code)
    return _keyword_sentiment_analysis(ticker, articles, hours)


def _convert_agent_result(agent_result: AgentSentimentResult) -> SentimentScoreResult:
    """Convert agentic result to existing SentimentScoreResult format."""
    return SentimentScoreResult(
        ticker=agent_result.ticker,
        total_score=agent_result.overall_score,
        raw_sentiment=(agent_result.overall_score / 50.0) - 1.0,  # Convert to -1 to 1
        article_count=len(agent_result.article_analyses),
        positive_count=sum(1 for a in agent_result.article_analyses if a.score > 55),
        negative_count=sum(1 for a in agent_result.article_analyses if a.score < 45),
        neutral_count=sum(1 for a in agent_result.article_analyses if 45 <= a.score <= 55),
        weighted_sentiment=(agent_result.overall_score / 50.0) - 1.0,
        details={
            "model": "llm",
            "confidence": agent_result.confidence,
            "rationale": agent_result.rationale,
            "bullish_factors": agent_result.bullish_factors,
            "bearish_factors": agent_result.bearish_factors,
        }
    )
```

### New File: `backend/src/scoring/agentic_sentiment.py`

```python
"""
Agentic Sentiment Analysis using Claude API.

This module provides LLM-powered sentiment analysis as an upgrade from
keyword-based analysis. It analyzes news articles in context and provides
nuanced, explainable sentiment scores.
"""

import json
import os
from typing import List, Dict, Optional
from datetime import datetime
from dataclasses import dataclass, asdict
from pathlib import Path
import anthropic
from loguru import logger

# ... (dataclasses from Section 2)

SENTIMENT_AGENT_SYSTEM_PROMPT = """..."""  # (from Section 2)


class AgenticSentimentAnalyzer:
    """Claude-powered sentiment analyzer."""
    
    def __init__(
        self,
        api_key: str = None,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 1500,
        cache_dir: Path = None
    ):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY required for agentic sentiment")
        
        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.model = model
        self.max_tokens = max_tokens
        self.cache_dir = cache_dir or Path(__file__).parent.parent.parent / "data" / "sentiment_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def analyze(self, ticker: str, articles: List[Dict]) -> AgentSentimentResult:
        """
        Analyze sentiment for a ticker based on its news articles.
        
        Args:
            ticker: Stock symbol
            articles: List of article dicts with title, summary, published, source
        
        Returns:
            AgentSentimentResult with full analysis
        """
        # Check cache first
        cached = self._load_cache(ticker)
        if cached:
            logger.debug(f"Cache hit for {ticker}")
            return cached
        
        # Prepare articles for prompt
        articles_text = self._format_articles(articles)
        
        # Build the user message
        user_message = f"""Analyze the sentiment for {ticker} based on these recent news articles:

{articles_text}

Respond with JSON matching this schema:
{{
  "ticker": "{ticker}",
  "overall_score": <0-100>,
  "overall_sentiment": "<very_bullish|bullish|slightly_bullish|neutral|slightly_bearish|bearish|very_bearish>",
  "confidence": <0-1>,
  "rationale": "<2-3 sentence explanation>",
  "article_analyses": [
    {{
      "headline": "<article headline>",
      "sentiment": "<sentiment label>",
      "score": <0-100>,
      "key_factors": ["<factor 1>", "<factor 2>"],
      "relevance": <0-1>
    }}
  ],
  "bullish_factors": ["<factor 1>", ...],
  "bearish_factors": ["<factor 1>", ...]
}}"""
        
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=SENTIMENT_AGENT_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}]
            )
            
            # Parse response
            result_json = self._extract_json(response.content[0].text)
            result = self._parse_result(result_json, ticker)
            
            # Cache the result
            self._save_cache(ticker, result)
            
            return result
            
        except anthropic.RateLimitError as e:
            logger.warning(f"Rate limited for {ticker}: {e}")
            raise
        except Exception as e:
            logger.error(f"Analysis failed for {ticker}: {e}")
            raise
    
    def analyze_batch(
        self,
        tickers_articles: Dict[str, List[Dict]],
        max_concurrent: int = 5
    ) -> Dict[str, AgentSentimentResult]:
        """
        Analyze multiple tickers (respecting rate limits).
        
        Args:
            tickers_articles: Dict mapping ticker -> articles list
            max_concurrent: Max parallel requests (keep low for rate limits)
        
        Returns:
            Dict mapping ticker -> AgentSentimentResult
        """
        import asyncio
        from concurrent.futures import ThreadPoolExecutor
        import time
        
        results = {}
        failed = []
        
        # Process sequentially with rate limit delay
        for i, (ticker, articles) in enumerate(tickers_articles.items()):
            if not articles:
                continue
            
            try:
                result = self.analyze(ticker, articles)
                results[ticker] = result
                logger.info(f"[{i+1}/{len(tickers_articles)}] {ticker}: {result.overall_score:.1f}")
                
                # Rate limit: ~50 requests/min for Sonnet
                time.sleep(1.2)
                
            except anthropic.RateLimitError:
                logger.warning(f"Rate limited, waiting 60s...")
                time.sleep(60)
                # Retry once
                try:
                    result = self.analyze(ticker, articles)
                    results[ticker] = result
                except Exception as e:
                    failed.append((ticker, str(e)))
            except Exception as e:
                failed.append((ticker, str(e)))
        
        if failed:
            logger.warning(f"Failed to analyze {len(failed)} tickers: {failed[:5]}")
        
        return results
    
    def _format_articles(self, articles: List[Dict]) -> str:
        """Format articles for the prompt."""
        formatted = []
        for i, article in enumerate(articles[:10], 1):  # Max 10 articles
            published = article.get("published", "Unknown date")
            source = article.get("source", "Unknown source")
            title = article.get("title", "No title")
            summary = article.get("summary", "")[:300]  # Limit summary length
            
            formatted.append(f"""Article {i}:
- Date: {published}
- Source: {source}
- Headline: {title}
- Summary: {summary}
""")
        
        return "\n".join(formatted)
    
    def _extract_json(self, text: str) -> dict:
        """Extract JSON from LLM response (handles markdown code blocks)."""
        # Try direct parse first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        # Try extracting from code block
        import re
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
        if json_match:
            return json.loads(json_match.group(1))
        
        # Try finding JSON object in text
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            return json.loads(json_match.group(0))
        
        raise ValueError(f"Could not extract JSON from response: {text[:200]}")
    
    def _parse_result(self, data: dict, ticker: str) -> AgentSentimentResult:
        """Parse JSON dict into AgentSentimentResult."""
        article_analyses = [
            ArticleAnalysis(
                headline=a["headline"],
                sentiment=SentimentLabel(a["sentiment"]),
                score=float(a["score"]),
                key_factors=a.get("key_factors", []),
                relevance=float(a.get("relevance", 0.5))
            )
            for a in data.get("article_analyses", [])
        ]
        
        return AgentSentimentResult(
            ticker=data.get("ticker", ticker),
            overall_score=float(data["overall_score"]),
            overall_sentiment=SentimentLabel(data["overall_sentiment"]),
            confidence=float(data.get("confidence", 0.7)),
            rationale=data.get("rationale", ""),
            article_analyses=article_analyses,
            bullish_factors=data.get("bullish_factors", []),
            bearish_factors=data.get("bearish_factors", []),
            analyzed_at=datetime.now().isoformat()
        )
    
    def _cache_path(self, ticker: str) -> Path:
        """Get cache file path for a ticker."""
        return self.cache_dir / f"{ticker.upper()}.json"
    
    def _load_cache(self, ticker: str, max_age_hours: int = 24) -> Optional[AgentSentimentResult]:
        """Load cached result if fresh enough."""
        cache_file = self._cache_path(ticker)
        if not cache_file.exists():
            return None
        
        try:
            with open(cache_file) as f:
                data = json.load(f)
            
            # Check age
            analyzed_at = datetime.fromisoformat(data["analyzed_at"])
            age_hours = (datetime.now() - analyzed_at).total_seconds() / 3600
            
            if age_hours > max_age_hours:
                return None
            
            return self._parse_result(data, ticker)
        except Exception as e:
            logger.debug(f"Cache load failed for {ticker}: {e}")
            return None
    
    def _save_cache(self, ticker: str, result: AgentSentimentResult) -> None:
        """Save result to cache."""
        cache_file = self._cache_path(ticker)
        try:
            data = {
                "ticker": result.ticker,
                "overall_score": result.overall_score,
                "overall_sentiment": result.overall_sentiment.value,
                "confidence": result.confidence,
                "rationale": result.rationale,
                "bullish_factors": result.bullish_factors,
                "bearish_factors": result.bearish_factors,
                "analyzed_at": result.analyzed_at,
                "article_analyses": [
                    {
                        "headline": a.headline,
                        "sentiment": a.sentiment.value,
                        "score": a.score,
                        "key_factors": a.key_factors,
                        "relevance": a.relevance
                    }
                    for a in result.article_analyses
                ]
            }
            with open(cache_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning(f"Cache save failed for {ticker}: {e}")
```

---

## 4. Data Flow

### Weekly Pipeline Flow

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                        WEEKLY SENTIMENT PIPELINE                             │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Step 1: News Collection (existing)                                          │
│  ─────────────────────────────────                                           │
│  news_fetcher.fetch_all_news(hours=168)                                      │
│  └─▶ ~500-1000 articles from RSS + Finnhub + Alpha Vantage                  │
│                                                                              │
│  Step 2: Article-Ticker Matching (existing + improved)                       │
│  ────────────────────────────────────────────────────────                    │
│  For each ticker in universe (677 stocks):                                   │
│    articles = match_articles_to_ticker(ticker, all_news)                     │
│    └─▶ 0-20 articles per ticker                                              │
│                                                                              │
│  Step 3: Tiered Analysis (NEW)                                               │
│  ─────────────────────────────                                               │
│  Tier A: Stocks with ≥3 articles → LLM Analysis                             │
│  Tier B: Stocks with 1-2 articles → LLM Analysis (batched)                  │
│  Tier C: Stocks with 0 articles → Sector Sentiment Fallback                 │
│                                                                              │
│  Step 4: LLM Analysis (NEW)                                                  │
│  ─────────────────────────                                                   │
│  For each ticker in Tier A + B:                                              │
│    agent_result = agentic_analyzer.analyze(ticker, articles)                │
│    └─▶ Structured JSON with score, rationale, factors                       │
│                                                                              │
│  Step 5: Score Aggregation                                                   │
│  ───────────────────────────                                                 │
│  Combine all results:                                                        │
│    - LLM scores (high confidence)                                            │
│    - Sector fallback scores (medium confidence)                              │
│    - Neutral default (low confidence)                                        │
│                                                                              │
│  Step 6: Cache & Persist                                                     │
│  ─────────────────────────                                                   │
│  save_sentiment_scores(results)                                              │
│  └─▶ data/sentiment_scores.json                                              │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Request Flow (API)

```
GET /api/v1/stocks/{ticker}/sentiment
         │
         ▼
┌─────────────────────────┐
│ Check sentiment cache   │
│ (data/sentiment_scores) │
└───────────┬─────────────┘
            │
      ┌─────▼─────┐
      │  Fresh?   │
      │ (<24h old)│
      └─────┬─────┘
         Yes│No
            │
      ┌─────▼─────────────────────┐
      │ Return cached score       │
      │ + rationale + factors     │
      └───────────────────────────┘

If cache miss or stale:
      │
      ▼
┌──────────────────────────────────┐
│ Fetch recent news for ticker     │
│ (last 7 days)                    │
└───────────┬──────────────────────┘
            │
      ┌─────▼─────┐
      │ Articles  │
      │   > 0 ?   │
      └─────┬─────┘
         Yes│No
            │           │
      ┌─────▼─────┐    │
      │ LLM avail?│    │
      └─────┬─────┘    │
         Yes│No        │
            │    │     │
      ┌─────▼────▼─────▼───────────┐
      │ LLM     Keyword   Neutral  │
      │ Analysis Analysis Default  │
      └───────────┬────────────────┘
                  │
            ┌─────▼─────┐
            │ Update    │
            │ Cache     │
            └─────┬─────┘
                  │
            ┌─────▼─────────────────┐
            │ Return SentimentScore │
            └───────────────────────┘
```

---

## 5. Fallback Strategy

### Fallback Hierarchy

```python
def get_sentiment_with_fallback(ticker: str, articles: List[Dict]) -> SentimentScoreResult:
    """
    Get sentiment score using tiered fallback strategy.
    
    Priority:
    1. LLM Analysis (if API available and articles exist)
    2. Cached LLM Result (if fresh, <24h)
    3. Keyword Analysis (if articles exist)
    4. Sector Sentiment (aggregated from sector peers)
    5. Neutral Default (50.0)
    """
    
    # Level 1: Try LLM analysis
    if SENTIMENT_MODEL in ("llm", "hybrid") and articles:
        analyzer = _get_agentic_analyzer()
        if analyzer:
            try:
                return analyzer.analyze(ticker, articles)
            except anthropic.RateLimitError:
                logger.warning(f"Rate limited for {ticker}, using fallback")
            except anthropic.APIError as e:
                logger.warning(f"API error for {ticker}: {e}")
    
    # Level 2: Check for cached LLM result
    cached = _load_llm_cache(ticker)
    if cached and _is_fresh(cached, max_age_hours=48):
        return cached
    
    # Level 3: Keyword analysis
    if articles:
        return _keyword_sentiment_analysis(ticker, articles)
    
    # Level 4: Sector sentiment
    sector = get_ticker_sector(ticker)
    sector_score = _calculate_sector_sentiment(sector)
    if sector_score != 50.0:
        return SentimentScoreResult(
            ticker=ticker,
            total_score=sector_score,
            details={"fallback": "sector", "sector": sector}
        )
    
    # Level 5: Neutral default
    return SentimentScoreResult(
        ticker=ticker,
        total_score=50.0,
        details={"fallback": "neutral", "reason": "no_data"}
    )
```

### Rate Limit Handling

```python
class RateLimitManager:
    """Manage API rate limits with exponential backoff."""
    
    def __init__(self, requests_per_minute: int = 50):
        self.rpm = requests_per_minute
        self.request_times: List[float] = []
        self.backoff_until: Optional[float] = None
    
    def wait_if_needed(self) -> None:
        """Block until rate limit allows next request."""
        import time
        
        now = time.time()
        
        # Check backoff
        if self.backoff_until and now < self.backoff_until:
            sleep_time = self.backoff_until - now
            logger.info(f"Rate limit backoff: sleeping {sleep_time:.1f}s")
            time.sleep(sleep_time)
        
        # Clean old requests (older than 1 minute)
        self.request_times = [t for t in self.request_times if now - t < 60]
        
        # Wait if at limit
        if len(self.request_times) >= self.rpm:
            sleep_time = 60 - (now - self.request_times[0])
            if sleep_time > 0:
                logger.debug(f"Rate limit: sleeping {sleep_time:.1f}s")
                time.sleep(sleep_time)
        
        self.request_times.append(time.time())
    
    def handle_rate_limit_error(self) -> None:
        """Set backoff after rate limit error."""
        self.backoff_until = time.time() + 60  # 1 minute backoff
```

### Circuit Breaker Pattern

```python
class SentimentCircuitBreaker:
    """Circuit breaker to prevent cascading failures."""
    
    CLOSED = "closed"  # Normal operation
    OPEN = "open"      # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failures = 0
        self.state = self.CLOSED
        self.last_failure_time: Optional[float] = None
    
    def can_execute(self) -> bool:
        """Check if request can proceed."""
        if self.state == self.CLOSED:
            return True
        
        if self.state == self.OPEN:
            # Check if recovery timeout elapsed
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = self.HALF_OPEN
                return True
            return False
        
        # HALF_OPEN: allow one request to test
        return True
    
    def record_success(self) -> None:
        """Record successful request."""
        self.failures = 0
        self.state = self.CLOSED
    
    def record_failure(self) -> None:
        """Record failed request."""
        self.failures += 1
        self.last_failure_time = time.time()
        
        if self.failures >= self.failure_threshold:
            self.state = self.OPEN
            logger.warning(f"Circuit breaker OPEN after {self.failures} failures")
```

---

## 6. Cost Estimation

### Token Usage Per Stock

| Component | Input Tokens | Output Tokens |
|-----------|-------------|---------------|
| System prompt | ~600 | — |
| Article data (5 avg) | ~1,500 | — |
| Response schema | ~200 | — |
| LLM response | — | ~400 |
| **Total per stock** | **~2,300** | **~400** |

### Weekly Pipeline Cost

```
Configuration:
- Model: Claude claude-sonnet-4-20250514 (cheapest capable model)
- Pricing: $3/M input tokens, $15/M output tokens
- Stocks with news: ~250 (others use fallback)
- Articles per stock: 5 average

Weekly Calculation:
┌─────────────────────────────────────────────────────────────┐
│ Input tokens:  250 stocks × 2,300 tokens = 575,000 tokens  │
│ Output tokens: 250 stocks × 400 tokens = 100,000 tokens    │
│                                                             │
│ Input cost:  575,000 × $3/M  = $1.73                       │
│ Output cost: 100,000 × $15/M = $1.50                       │
│                                                             │
│ WEEKLY TOTAL: $3.23                                        │
│ MONTHLY TOTAL: ~$13                                        │
│ ANNUAL TOTAL: ~$168                                        │
└─────────────────────────────────────────────────────────────┘
```

### Cost Optimization Strategies

1. **Aggressive Caching** — 24h TTL, refresh only changed articles
2. **Batching** — Analyze 3-5 related stocks in single prompt (sector batching)
3. **Tiered Models** — Use Haiku for low-article stocks, Sonnet for high-article
4. **Skip Unchanged** — Hash articles, skip analysis if same as cached

```python
# Optimized tier selection
def select_model_for_ticker(ticker: str, article_count: int) -> str:
    """Select cheapest sufficient model based on complexity."""
    if article_count >= 5:
        return "claude-sonnet-4-20250514"  # Complex analysis needs Sonnet
    elif article_count >= 2:
        return "claude-3-haiku-20240307"   # Simple analysis, 10x cheaper
    else:
        return None  # Use keyword fallback
```

**With Haiku optimization:**
- 150 stocks via Sonnet: $1.94
- 100 stocks via Haiku: $0.08
- **Optimized weekly: $2.02** (38% savings)

---

## 7. Technical Requirements

### Dependencies

```
# requirements.txt additions
anthropic>=0.18.0  # Claude API client
tenacity>=8.2.0    # Retry logic with backoff
pydantic>=2.0      # Schema validation (optional but recommended)
```

### Environment Variables

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-api03-...

# Optional
SENTIMENT_MODEL=llm          # keyword | llm | hybrid
SENTIMENT_CACHE_TTL=24       # Hours
SENTIMENT_MAX_ARTICLES=10    # Per stock
SENTIMENT_RATE_LIMIT=50      # Requests per minute
```

### File Structure

```
backend/src/scoring/
├── sentiment_score.py          # Existing (modified)
├── agentic_sentiment.py        # NEW: LLM analyzer
├── sentiment_cache.py          # NEW: Cache management
└── sentiment_fallback.py       # NEW: Fallback logic

backend/data/
└── sentiment_cache/            # NEW: Per-ticker cache
    ├── AAPL.json
    ├── MSFT.json
    └── ...
```

### Caching Strategy

```python
class SentimentCacheManager:
    """Manage sentiment result caching."""
    
    def __init__(self, cache_dir: Path, ttl_hours: int = 24):
        self.cache_dir = cache_dir
        self.ttl_hours = ttl_hours
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def get(self, ticker: str) -> Optional[AgentSentimentResult]:
        """Get cached result if fresh."""
        path = self.cache_dir / f"{ticker.upper()}.json"
        if not path.exists():
            return None
        
        data = json.loads(path.read_text())
        
        # Check freshness
        cached_at = datetime.fromisoformat(data["analyzed_at"])
        age_hours = (datetime.now() - cached_at).total_seconds() / 3600
        
        if age_hours > self.ttl_hours:
            return None
        
        return self._deserialize(data)
    
    def set(self, result: AgentSentimentResult) -> None:
        """Cache a result."""
        path = self.cache_dir / f"{result.ticker.upper()}.json"
        path.write_text(json.dumps(self._serialize(result), indent=2))
    
    def invalidate(self, ticker: str) -> None:
        """Remove cached result."""
        path = self.cache_dir / f"{ticker.upper()}.json"
        if path.exists():
            path.unlink()
    
    def invalidate_all(self) -> int:
        """Clear all cache. Returns count of removed files."""
        count = 0
        for path in self.cache_dir.glob("*.json"):
            path.unlink()
            count += 1
        return count
```

---

## 8. Implementation Checklist

### Phase 1: Core Implementation (3-4 days)

- [ ] Create `agentic_sentiment.py` with `AgenticSentimentAnalyzer`
- [ ] Implement output schema parsing with validation
- [ ] Add basic caching (file-based, 24h TTL)
- [ ] Integrate with existing `sentiment_score.py` via config flag
- [ ] Add unit tests for analyzer
- [ ] Test with 10 sample stocks

### Phase 2: Robustness (2-3 days)

- [ ] Implement rate limit manager
- [ ] Add circuit breaker pattern
- [ ] Build fallback hierarchy
- [ ] Add retry logic with exponential backoff
- [ ] Test failure scenarios

### Phase 3: Optimization (1-2 days)

- [ ] Implement tiered model selection (Haiku/Sonnet)
- [ ] Add article hash comparison (skip unchanged)
- [ ] Optimize prompt for token efficiency
- [ ] Add batch processing for weekly pipeline

### Phase 4: Monitoring & Validation (1-2 days)

- [ ] Add logging for LLM analysis (tokens used, latency)
- [ ] Create cost tracking dashboard
- [ ] Validate score distribution improvement
- [ ] A/B test against keyword scoring

---

## 9. Success Metrics

| Metric | Current (Keyword) | Target (Agentic) |
|--------|-------------------|------------------|
| Stocks at neutral 50.0 | 420 (62%) | <100 (15%) |
| Score standard deviation | ~5 | >15 |
| Sentiment rationale coverage | 0% | 100% |
| Bullish/bearish factor coverage | 0% | 100% |
| Weekly pipeline cost | $0 | <$5 |
| Analysis latency (per stock) | <100ms | <3s |

---

## 10. Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| API rate limits | Pipeline delays | Rate limit manager + batch processing |
| LLM hallucination | Wrong scores | Schema validation + confidence thresholds |
| Cost overrun | Budget impact | Haiku tier + aggressive caching |
| API downtime | No scores | Keyword fallback always available |
| Prompt injection via news | Security | Sanitize article text, use system prompt |

---

*This specification is implementation-ready. Follow the checklist in Section 8 to execute.*

**Related Documents:**
- `01_PRD.md` — Product requirements
- `02_TECHNICAL_SPEC.md` — Overall architecture
- `06_AGENTIC_ANALYSIS_RESEARCH.md` — market-analyzer patterns
