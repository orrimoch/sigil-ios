<img src="sigil_logo.jpg" alt="Sigil" width="240" />

# SIGIL AUTONOMOUS TRADING AGENT

**Complete Algorithm Specification v2.0**

> *"An AI agent that uses all Sigil's insights as levers to maximize profit and manage risk autonomously."*

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [The Complete Algorithm](#2-the-complete-algorithm)
3. [Step 1: Signal Generation](#3-step-1-signal-generation)
4. [Step 2: Context Aggregation](#4-step-2-context-aggregation)
5. [Step 3: Memory Retrieval](#5-step-3-memory-retrieval)
6. [Step 4: Decision Engine](#6-step-4-decision-engine)
7. [Step 5: Position Sizing](#7-step-5-position-sizing)
8. [Step 6: Risk Validation](#8-step-6-risk-validation)
9. [Step 7: Execution](#9-step-7-execution)
10. [Step 8: Learning Loop](#10-step-8-learning-loop)
11. [iOS Integration](#11-ios-integration)
12. [Validation & Metrics](#12-validation--metrics)
13. [Implementation Plan](#13-implementation-plan)

---

## 1. Executive Summary

### What We're Building

Transform Sigil from a **recommendation engine** into an **autonomous portfolio manager**:

```
CURRENT STATE:                    END STATE:
┌─────────────────┐               ┌─────────────────┐
│  Sigil App      │               │  Sigil Agent    │
│                 │               │                 │
│  "CMI score 89" │      →        │  "Bought CMI"   │
│  "Consider BUY" │               │  "Here's why"   │
│                 │               │  "P&L: +$240"   │
│  [User decides] │               │  [Auto-managed] │
└─────────────────┘               └─────────────────┘
```

### Core Insight

**We don't predict prices. We reason about refined signals.**

| Traditional | Sigil Agent |
|-------------|-------------|
| "Will AAPL go up?" | "Given score 89, calm regime, insider buys — is this a good trade?" |
| Prediction (hard, ~50% accuracy) | Reasoning (tractable, high quality) |

### Target User

From PRD — "The Busy Builder":
- 5-10 min/week oversight
- Set preferences once
- Agent explains every decision
- Weekly summary of actions

---

## 2. The Complete Algorithm

### Full Trading Loop (Visual)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                        SIGIL AGENT TRADING LOOP                              │
│                                                                              │
│  ┌─────────────┐                                                            │
│  │  TRIGGER    │  Sunday 01:00 AM (after pipeline) OR on-demand             │
│  └──────┬──────┘                                                            │
│         ↓                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  STEP 1: SIGNAL GENERATION (Existing Pipelines)                     │    │
│  │  • Composite scores (F:35% + S:25% + T:20% + M:20%)                 │    │
│  │  • 850 stocks scored 0-100, signals: BUY/HOLD/SELL                  │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│         ↓                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  STEP 2: CONTEXT AGGREGATION                                        │    │
│  │  • Portfolio state (holdings, cash, P&L)                            │    │
│  │  • Market regime (HMM: low_vol/normal/high_vol/crisis)              │    │
│  │  • VIX level and trend                                              │    │
│  │  • Sector exposures                                                 │    │
│  │  • Top BUY candidates + SELL candidates                             │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│         ↓                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  STEP 3: MEMORY RETRIEVAL (pgvector)                                │    │
│  │  • Query: "Similar past situations"                                 │    │
│  │  • Returns: 5-10 relevant decisions + outcomes                      │    │
│  │  • Example: "CAT Dec 2025, score 87, regime normal → +12%"          │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│         ↓                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  STEP 4: DECISION ENGINE (Claude)                                   │    │
│  │  • Extended thinking enabled                                        │    │
│  │  • Synthesizes all context + memory                                 │    │
│  │  • Output: BUY/SELL decisions with rationale                        │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│         ↓                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  STEP 5: POSITION SIZING                                            │    │
│  │  • Risk Parity optimizer (equal risk contribution)                  │    │
│  │  • Conviction multiplier (higher score = bigger position)           │    │
│  │  • Regime multiplier (crisis = smaller positions)                   │    │
│  │  • Output: Exact share counts for each trade                        │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│         ↓                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  STEP 6: RISK VALIDATION                                            │    │
│  │  • Position limit check (max 10%)                                   │    │
│  │  • Sector limit check (max 30%)                                     │    │
│  │  • Portfolio VaR check (max 2% daily)                               │    │
│  │  • Correlation check (reduce if correlated with existing)           │    │
│  │  • PASS → Continue | FAIL → Reduce or Skip                          │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│         ↓                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  STEP 7: EXECUTION                                                  │    │
│  │  Mode A (Supervised): Push notification → User approves → Execute   │    │
│  │  Mode B (Autonomous): Execute directly via IBKR API                 │    │
│  │  • Order type: MARKET (MVP) or LIMIT (later)                        │    │
│  │  • Attach stop-loss order (trailing or hard)                        │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│         ↓                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  STEP 8: LEARNING LOOP                                              │    │
│  │  • Store decision + context in pgvector memory                      │    │
│  │  • After 1-4 weeks: Record outcome (+X% or -Y%)                     │    │
│  │  • Claude reflects: "What worked? What didn't?"                     │    │
│  │  • Lessons stored for future retrieval                              │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│         ↓                                                                    │
│  ┌─────────────┐                                                            │
│  │  REPEAT     │  Next week...                                              │
│  └─────────────┘                                                            │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Algorithm in Code (Pseudocode)

```python
async def run_weekly_trading_loop():
    """Main entry point — runs after Sunday pipeline."""
    
    # STEP 1: Signal Generation (already done by pipeline)
    scores = load_composite_scores()  # 850 stocks with scores
    
    # STEP 2: Context Aggregation
    context = await aggregate_context(scores)
    
    # STEP 3: Memory Retrieval
    similar_situations = await memory.retrieve_similar(context, k=10)
    
    # STEP 4: Decision Engine
    decisions = await claude.decide(context, similar_situations)
    
    # STEP 5 & 6: Position Sizing + Risk Validation
    validated_trades = []
    for decision in decisions:
        sized = await size_position(decision, context)
        if await validate_risk(sized, context):
            validated_trades.append(sized)
    
    # STEP 7: Execution
    if agent_mode == "supervised":
        await send_for_approval(validated_trades)  # User approves via app
    else:
        for trade in validated_trades:
            await execute_trade(trade)
    
    # STEP 8: Learning Loop
    await memory.store_decisions(validated_trades)
    await update_past_outcomes()  # Check outcomes of old trades
```

---

## 3. Step 1: Signal Generation

> **Status:** ✅ Already built (existing pipeline)

### What It Does

Transforms raw market data into refined scores:

```
850 stocks
    ↓
┌────────────────────────────────────────────────────┐
│  SCORING PIPELINE (runs Sunday 01:00 AM)           │
│                                                    │
│  Fundamental Score (35%)                           │
│    └─ P/E, ROE, revenue growth, debt ratios       │
│                                                    │
│  Sentiment Score (25%)                             │
│    └─ News + Claude analysis (bullish/bearish)    │
│                                                    │
│  Technical Score (20%)                             │
│    └─ RSI, MACD, momentum, price trends           │
│                                                    │
│  Macro Score (20%)                                 │
│    └─ VIX, sector trends, HMM regime              │
│                                                    │
│  + Crowd Wisdom Boost                              │
│    └─ Insider buys, Reddit sentiment              │
└────────────────────────────────────────────────────┘
    ↓
Composite Score 0-100
    ↓
Signal: BUY (≥70) | HOLD (40-69) | SELL (<40)
```

### Output

```json
{
  "CMI": {"score": 89.8, "signal": "BUY", "rank": 1, "sector": "Industrials"},
  "UPS": {"score": 87.8, "signal": "BUY", "rank": 2, "sector": "Logistics"},
  ...
}
```

### Location

- Code: `src/scoring/composite_score.py`
- Output: `data/composite_scores.json`
- Schedule: Sunday 01:00 AM (GitHub Actions)

---

## 4. Step 2: Context Aggregation

> **Status:** 🔨 To build (Phase 0)

### What It Does

Gathers all information needed for a trading decision into a single context object.

### Implementation

```python
# src/agent/context.py

from dataclasses import dataclass
from typing import List, Dict, Optional
from datetime import datetime

@dataclass
class PortfolioState:
    cash: float
    total_value: float
    positions: List[Dict]  # [{ticker, shares, avg_cost, current_price, pnl}]
    sector_exposure: Dict[str, float]  # {sector: percentage}
    unrealized_pnl: float
    realized_pnl_today: float

@dataclass
class MarketState:
    regime: str  # "low_vol" | "normal" | "high_vol" | "crisis"
    regime_confidence: float
    vix: float
    vix_percentile: float  # Where VIX is vs history
    trend: str  # "up" | "down" | "sideways"

@dataclass
class StockCandidate:
    ticker: str
    score: float
    signal: str
    sector: str
    fundamental_score: float
    sentiment_score: float
    technical_score: float
    macro_score: float
    insider_score: Optional[float]
    volatility: float  # For position sizing

@dataclass
class TradingContext:
    timestamp: datetime
    portfolio: PortfolioState
    market: MarketState
    buy_candidates: List[StockCandidate]  # Top 20 BUY signals not owned
    sell_candidates: List[StockCandidate]  # Holdings with SELL signal
    hold_review: List[StockCandidate]  # Holdings with score dropped >10 pts
    data_freshness: Dict[str, datetime]  # When each data source updated


async def aggregate_context() -> TradingContext:
    """
    Gather all context needed for trading decision.
    
    Called after pipeline runs (Sunday) or on-demand.
    """
    # Load scores
    scores = await load_composite_scores()
    
    # Load portfolio
    portfolio = await ibkr.get_portfolio()
    holdings = {p.ticker for p in portfolio.positions}
    
    # Get market state
    regime = await get_hmm_regime()
    vix = await get_vix()
    
    # Build candidates
    buy_candidates = [
        StockCandidate(**s) 
        for s in scores 
        if s["signal"] == "BUY" and s["ticker"] not in holdings
    ][:20]  # Top 20
    
    sell_candidates = [
        StockCandidate(**s)
        for s in scores
        if s["ticker"] in holdings and s["signal"] == "SELL"
    ]
    
    # Check data freshness
    freshness = await check_data_freshness()
    
    return TradingContext(
        timestamp=datetime.now(),
        portfolio=portfolio,
        market=MarketState(regime=regime, vix=vix, ...),
        buy_candidates=buy_candidates,
        sell_candidates=sell_candidates,
        hold_review=[],
        data_freshness=freshness
    )
```

### API Endpoint

```
GET /api/v1/agent/context

Response:
{
  "timestamp": "2026-02-16T01:30:00Z",
  "portfolio": {
    "cash": 45000,
    "total_value": 125000,
    "positions": [...],
    "sector_exposure": {"Technology": 0.35, "Industrials": 0.10}
  },
  "market": {
    "regime": "normal",
    "vix": 15.2,
    "trend": "up"
  },
  "buy_candidates": [...],
  "sell_candidates": [...]
}
```

---

## 5. Step 3: Memory Retrieval

> **Status:** 🔨 To build (Phase 1)

### What It Does

Retrieves similar past trading situations to inform the current decision.

### Three-Tier Memory Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  MEMORY SYSTEM                                                  │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  WORKING MEMORY (current session)                         │ │
│  │  • Current context                                        │ │
│  │  • Decisions being evaluated                              │ │
│  │  • Stored in RAM                                          │ │
│  └───────────────────────────────────────────────────────────┘ │
│                         ↓ (after decision)                      │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  SHORT-TERM MEMORY (recent weeks)                         │ │
│  │  • Last 50 decisions                                      │ │
│  │  • Full context + rationale                               │ │
│  │  • Stored in PostgreSQL                                   │ │
│  └───────────────────────────────────────────────────────────┘ │
│                         ↓ (after outcome known)                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  LONG-TERM MEMORY (historical patterns)                   │ │
│  │  • Decision + outcome + lesson learned                    │ │
│  │  • Embedded as vectors (pgvector)                         │ │
│  │  • Semantic search: "similar situations"                  │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
# src/agent/memory.py

import numpy as np
from datetime import datetime
from typing import List
import asyncpg

class AgentMemory:
    """
    Three-tier memory system with pgvector for semantic search.
    """
    
    def __init__(self, db_url: str, embedding_model: str = "text-embedding-3-small"):
        self.db_url = db_url
        self.embedding_model = embedding_model
    
    async def store_decision(self, decision: Decision, context: TradingContext):
        """Store a decision in short-term memory."""
        # Create embedding from decision context
        text = self._decision_to_text(decision, context)
        embedding = await self._embed(text)
        
        async with asyncpg.connect(self.db_url) as conn:
            await conn.execute("""
                INSERT INTO agent_decisions 
                (timestamp, ticker, action, shares, price, score, regime, 
                 rationale, context_json, embedding)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            """, datetime.now(), decision.ticker, decision.action, 
                decision.shares, decision.price, decision.score,
                context.market.regime, decision.rationale,
                context.to_json(), embedding)
    
    async def retrieve_similar(self, context: TradingContext, k: int = 10) -> List[Memory]:
        """
        Find similar past situations using vector similarity.
        
        Returns decisions with known outcomes for in-context learning.
        """
        # Embed current context
        text = self._context_to_text(context)
        embedding = await self._embed(text)
        
        async with asyncpg.connect(self.db_url) as conn:
            rows = await conn.fetch("""
                SELECT ticker, action, score, regime, outcome_pct, 
                       rationale, lesson_learned,
                       embedding <=> $1 as distance
                FROM agent_decisions
                WHERE outcome_pct IS NOT NULL  -- Only completed trades
                ORDER BY embedding <=> $1
                LIMIT $2
            """, embedding, k)
        
        return [Memory(**row) for row in rows]
    
    async def update_outcome(self, decision_id: int, outcome_pct: float):
        """Record the outcome of a past decision."""
        async with asyncpg.connect(self.db_url) as conn:
            await conn.execute("""
                UPDATE agent_decisions
                SET outcome_pct = $1, outcome_date = NOW()
                WHERE id = $2
            """, outcome_pct, decision_id)
    
    async def store_lesson(self, decision_id: int, lesson: str):
        """Store a lesson learned from a decision."""
        async with asyncpg.connect(self.db_url) as conn:
            await conn.execute("""
                UPDATE agent_decisions
                SET lesson_learned = $1
                WHERE id = $2
            """, lesson, decision_id)
    
    def _decision_to_text(self, decision: Decision, context: TradingContext) -> str:
        """Convert decision + context to text for embedding."""
        return f"""
        Action: {decision.action} {decision.ticker}
        Score: {decision.score}
        Regime: {context.market.regime}
        VIX: {context.market.vix}
        Sector: {decision.sector}
        Rationale: {decision.rationale}
        """
```

### Database Schema

```sql
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Agent decisions table
CREATE TABLE agent_decisions (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    
    -- Decision
    ticker VARCHAR(10) NOT NULL,
    action VARCHAR(10) NOT NULL,  -- BUY, SELL
    shares INTEGER NOT NULL,
    price DECIMAL(10, 2) NOT NULL,
    
    -- Context at decision time
    score DECIMAL(5, 2) NOT NULL,
    regime VARCHAR(20) NOT NULL,
    vix DECIMAL(5, 2),
    sector VARCHAR(50),
    context_json JSONB,
    
    -- Rationale
    rationale TEXT NOT NULL,
    confidence DECIMAL(3, 2),
    
    -- Outcome (filled later)
    outcome_pct DECIMAL(6, 2),
    outcome_date TIMESTAMPTZ,
    lesson_learned TEXT,
    
    -- Embedding for similarity search
    embedding vector(1536)  -- OpenAI embedding size
);

-- Index for fast similarity search
CREATE INDEX ON agent_decisions 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
```

---

## 6. Step 4: Decision Engine

> **Status:** 🔨 To build (Phase 2)

### What It Does

Uses Claude to synthesize context + memory into trading decisions.

### Implementation

```python
# src/agent/decision_engine.py

import anthropic
from typing import List
from dataclasses import dataclass

@dataclass
class TradeDecision:
    ticker: str
    action: str  # "BUY" or "SELL"
    rationale: str
    confidence: float  # 0-1
    score: float
    sector: str

SYSTEM_PROMPT = """
You are an expert portfolio manager for Sigil, an AI-powered trading system.

Your job is to review the current market context, portfolio state, and historical 
similar situations, then decide which trades to make this week.

TRADING PHILOSOPHY:
- You capture weekly trends, not intraday moves
- Maximum 3-5 trades per week
- Position trades held for 5-30 days
- You are risk-aware: never exceed position/sector limits
- When in doubt, don't trade (preserve capital)

DECISION RULES:
- BUY when: score ≥75, regime is calm/normal, sector not overweight
- SELL when: score <40, OR stop-loss triggered, OR regime is crisis + losing
- HOLD when: 40 ≤ score < 75, wait for stronger signal

For each decision, provide:
1. Action (BUY/SELL)
2. Ticker
3. Clear rationale (2-3 sentences)
4. Confidence (0-1)

Output as JSON array.
"""

class DecisionEngine:
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
    
    async def decide(
        self, 
        context: TradingContext, 
        memories: List[Memory]
    ) -> List[TradeDecision]:
        """
        Main decision function.
        
        Uses Claude with extended thinking to synthesize all inputs
        and produce trading decisions.
        """
        # Build prompt
        prompt = self._build_prompt(context, memories)
        
        # Call Claude with extended thinking
        response = await self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            thinking={
                "type": "enabled",
                "budget_tokens": 5000  # Let Claude think deeply
            },
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Parse response
        decisions = self._parse_response(response)
        
        return decisions
    
    def _build_prompt(self, context: TradingContext, memories: List[Memory]) -> str:
        """Build the prompt with all context and memories."""
        
        # Portfolio section
        portfolio_text = f"""
## Current Portfolio
- Cash: ${context.portfolio.cash:,.0f}
- Total Value: ${context.portfolio.total_value:,.0f}
- Unrealized P&L: ${context.portfolio.unrealized_pnl:+,.0f}

Holdings:
{self._format_holdings(context.portfolio.positions)}

Sector Exposure:
{self._format_sectors(context.portfolio.sector_exposure)}
"""
        
        # Market section
        market_text = f"""
## Market State
- Regime: {context.market.regime} (confidence: {context.market.regime_confidence:.0%})
- VIX: {context.market.vix:.1f} ({context.market.vix_percentile:.0f}th percentile)
- Trend: {context.market.trend}
"""
        
        # Candidates section
        candidates_text = f"""
## BUY Candidates (Top 10)
{self._format_candidates(context.buy_candidates[:10])}

## SELL Candidates (Current Holdings)
{self._format_candidates(context.sell_candidates)}
"""
        
        # Memory section
        memory_text = f"""
## Similar Past Situations
{self._format_memories(memories)}
"""
        
        # Final prompt
        return f"""
{portfolio_text}
{market_text}
{candidates_text}
{memory_text}

Based on all the above, what trades should I make this week?
Consider risk limits, diversification, and market regime.
Output your decisions as a JSON array.
"""
    
    def _format_candidates(self, candidates: List[StockCandidate]) -> str:
        lines = []
        for c in candidates:
            lines.append(
                f"- {c.ticker}: Score {c.score:.0f} ({c.signal}) | "
                f"Sector: {c.sector} | Vol: {c.volatility:.1%}"
            )
        return "\n".join(lines) or "None"
    
    def _format_memories(self, memories: List[Memory]) -> str:
        lines = []
        for m in memories:
            outcome = f"+{m.outcome_pct:.1f}%" if m.outcome_pct > 0 else f"{m.outcome_pct:.1f}%"
            lines.append(
                f"- {m.ticker} ({m.action}): Score {m.score:.0f}, "
                f"Regime {m.regime} → {outcome}"
            )
            if m.lesson_learned:
                lines.append(f"  Lesson: {m.lesson_learned}")
        return "\n".join(lines) or "No similar situations found."
```

### Example Claude Interaction

**Input to Claude:**
```
## Current Portfolio
- Cash: $45,000
- Total Value: $125,000
- Holdings: AAPL (50 shares), MSFT (30 shares)
- Sector Exposure: Technology 35%, Cash 36%

## Market State
- Regime: normal (confidence: 78%)
- VIX: 15.2 (32nd percentile)
- Trend: up

## BUY Candidates
- CMI: Score 89.8 (BUY) | Sector: Industrials | Vol: 22%
- UPS: Score 87.8 (BUY) | Sector: Logistics | Vol: 18%

## Similar Past Situations
- CAT (BUY): Score 87, Regime normal → +12%
  Lesson: Industrial momentum plays well in low vol
- FDX (BUY): Score 85, Regime normal → -3%
  Lesson: Earnings week caused whipsaw

What trades should I make this week?
```

**Claude's Thinking:**
```
<thinking>
Portfolio analysis:
- 36% cash is high, should deploy some
- Technology heavy at 35%, need diversification
- Market regime is normal, VIX low — good for risk-on

CMI analysis:
- Score 89.8 is very high
- Industrials sector — adds diversification (0% → ~5%)
- Similar situation: CAT worked +12%
- Volatility 22% is moderate

UPS analysis:
- Score 87.8 also strong
- Logistics similar to Industrials but different
- Would add further diversification

Risk check:
- Adding CMI at 5% keeps under 10% limit
- Sector limits fine (Industrials would be 5%)
- VaR budget allows

Decision: BUY both CMI and UPS
</thinking>
```

**Claude's Output:**
```json
[
  {
    "action": "BUY",
    "ticker": "CMI",
    "rationale": "Score 89.8 is exceptional. Industrials adds diversification to tech-heavy portfolio. Similar CAT trade in normal regime returned +12%. Volatility is manageable.",
    "confidence": 0.85
  },
  {
    "action": "BUY",
    "ticker": "UPS",
    "rationale": "Score 87.8 strong. Logistics exposure complements Industrials. Portfolio is 36% cash, can afford to deploy. Regime supports risk-on.",
    "confidence": 0.75
  }
]
```

---

## 7. Step 5: Position Sizing

> **Status:** 🔨 To build (Phase 1)

### What It Does

Determines exact share counts using Risk Parity optimization.

### Position Sizing Pipeline

```
Decision: "BUY CMI"
       ↓
┌─────────────────────────────────────────┐
│  1. RISK PARITY OPTIMIZATION            │
│     - Fetch covariance matrix           │
│     - Calculate equal risk weights      │
│     - Base weight for CMI: 6%           │
└─────────────────────────────────────────┘
       ↓
┌─────────────────────────────────────────┐
│  2. CONVICTION ADJUSTMENT               │
│     - Score 89.8 → multiplier 1.1       │
│     - Adjusted weight: 6% × 1.1 = 6.6%  │
└─────────────────────────────────────────┘
       ↓
┌─────────────────────────────────────────┐
│  3. REGIME ADJUSTMENT                   │
│     - Regime "normal" → multiplier 1.0  │
│     - Final weight: 6.6%                │
└─────────────────────────────────────────┘
       ↓
┌─────────────────────────────────────────┐
│  4. CALCULATE SHARES                    │
│     - Portfolio: $125,000               │
│     - Target: $125,000 × 6.6% = $8,250  │
│     - CMI price: $310                   │
│     - Shares: floor($8,250 / $310) = 26 │
└─────────────────────────────────────────┘
       ↓
Output: BUY 26 shares CMI
```

### Implementation

```python
# src/agent/position_sizing.py

import numpy as np
from scipy.optimize import minimize
import yfinance as yf
from typing import Dict, List
from dataclasses import dataclass

@dataclass
class SizedPosition:
    ticker: str
    action: str
    shares: int
    dollars: float
    weight: float
    rationale: str

class PositionSizer:
    """
    Position sizing using Risk Parity + conviction + regime adjustments.
    """
    
    def __init__(self, lookback_days: int = 60):
        self.lookback_days = lookback_days
    
    async def size_positions(
        self,
        decisions: List[TradeDecision],
        context: TradingContext
    ) -> List[SizedPosition]:
        """
        Size all positions using Risk Parity optimization.
        """
        if not decisions:
            return []
        
        buy_tickers = [d.ticker for d in decisions if d.action == "BUY"]
        
        if buy_tickers:
            # Get risk parity weights
            rp_weights = await self._risk_parity_weights(buy_tickers)
            
            # Apply conviction and regime adjustments
            final_weights = {}
            for decision in decisions:
                if decision.action == "BUY":
                    base = rp_weights.get(decision.ticker, 0.05)
                    conviction = self._conviction_multiplier(decision.score)
                    regime = self._regime_multiplier(context.market.regime)
                    final_weights[decision.ticker] = base * conviction * regime
        
        # Convert weights to shares
        results = []
        portfolio_value = context.portfolio.total_value
        
        for decision in decisions:
            if decision.action == "BUY":
                weight = min(final_weights[decision.ticker], 0.10)  # Cap at 10%
                dollars = portfolio_value * weight
                price = await self._get_price(decision.ticker)
                shares = int(dollars / price)
                
                results.append(SizedPosition(
                    ticker=decision.ticker,
                    action="BUY",
                    shares=shares,
                    dollars=shares * price,
                    weight=weight,
                    rationale=f"Risk parity {rp_weights[decision.ticker]:.1%} × "
                              f"conviction {conviction:.2f} × regime {regime:.2f}"
                ))
            
            elif decision.action == "SELL":
                # Sell entire position
                position = next(
                    p for p in context.portfolio.positions 
                    if p["ticker"] == decision.ticker
                )
                results.append(SizedPosition(
                    ticker=decision.ticker,
                    action="SELL",
                    shares=position["shares"],
                    dollars=position["shares"] * position["current_price"],
                    weight=0,
                    rationale="Full exit"
                ))
        
        return results
    
    async def _risk_parity_weights(self, tickers: List[str]) -> Dict[str, float]:
        """Calculate Risk Parity weights."""
        n = len(tickers)
        if n == 0:
            return {}
        if n == 1:
            return {tickers[0]: 0.05}  # Default 5%
        
        # Fetch returns and calculate covariance
        cov_matrix = await self._get_covariance_matrix(tickers)
        
        # Target: equal risk contribution
        target_risk = np.ones(n) / n
        
        def objective(weights):
            portfolio_vol = np.sqrt(weights @ cov_matrix @ weights)
            marginal_contrib = cov_matrix @ weights
            risk_contrib = weights * marginal_contrib / portfolio_vol
            return np.sum((risk_contrib - target_risk) ** 2)
        
        # Optimize
        constraints = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 0.40}]  # 40% total
        bounds = [(0.02, 0.12) for _ in range(n)]  # 2-12% each
        x0 = np.ones(n) * 0.40 / n
        
        result = minimize(objective, x0, bounds=bounds, constraints=constraints)
        
        return {ticker: weight for ticker, weight in zip(tickers, result.x)}
    
    def _conviction_multiplier(self, score: float) -> float:
        """Higher score = larger position."""
        # Score 70 → 0.85, Score 85 → 1.0, Score 100 → 1.15
        return 0.85 + (score - 70) / 100
    
    def _regime_multiplier(self, regime: str) -> float:
        """Crisis = smaller positions."""
        return {
            "low_vol": 1.1,
            "normal": 1.0,
            "high_vol": 0.7,
            "crisis": 0.5
        }.get(regime, 1.0)
    
    async def _get_covariance_matrix(self, tickers: List[str]) -> np.ndarray:
        """Fetch price history and compute covariance matrix."""
        data = yf.download(tickers, period=f"{self.lookback_days}d", progress=False)
        returns = data['Close'].pct_change().dropna()
        return returns.cov().values * 252  # Annualized
```

---

## 8. Step 6: Risk Validation

> **Status:** ✅ Partially built (existing risk module)

### What It Does

Validates that trades don't exceed risk limits. **Blocks or reduces trades that violate constraints.**

### Risk Checks

```python
# src/agent/risk_validator.py

from dataclasses import dataclass
from typing import List, Tuple

@dataclass
class RiskValidation:
    passed: bool
    original_shares: int
    adjusted_shares: int
    violations: List[str]
    warnings: List[str]

class RiskValidator:
    """
    Validates trades against risk constraints.
    Can reduce or block trades that exceed limits.
    """
    
    # Risk Limits
    MAX_POSITION_PCT = 0.10      # 10% max per position
    MAX_SECTOR_PCT = 0.30        # 30% max per sector
    MAX_PORTFOLIO_VAR = 0.02    # 2% daily VaR limit
    MAX_CORRELATION = 0.80       # Reduce if correlated with existing
    DAILY_LOSS_LIMIT = 0.03     # 3% pause threshold
    
    async def validate(
        self,
        trade: SizedPosition,
        context: TradingContext
    ) -> RiskValidation:
        """
        Validate a single trade against all risk limits.
        """
        violations = []
        warnings = []
        adjusted_shares = trade.shares
        
        # Check 1: Position limit
        position_check = self._check_position_limit(trade, context)
        if not position_check[0]:
            violations.append(position_check[1])
            adjusted_shares = position_check[2]
        
        # Check 2: Sector limit
        sector_check = await self._check_sector_limit(trade, context)
        if not sector_check[0]:
            violations.append(sector_check[1])
            adjusted_shares = min(adjusted_shares, sector_check[2])
        
        # Check 3: Portfolio VaR
        var_check = await self._check_portfolio_var(trade, context)
        if not var_check[0]:
            violations.append(var_check[1])
            adjusted_shares = min(adjusted_shares, var_check[2])
        
        # Check 4: Correlation with existing
        corr_check = await self._check_correlation(trade, context)
        if not corr_check[0]:
            warnings.append(corr_check[1])
            adjusted_shares = min(adjusted_shares, corr_check[2])
        
        # Check 5: Daily loss limit (halt all trading)
        if self._check_daily_loss(context):
            violations.append("Daily loss limit exceeded - trading halted")
            adjusted_shares = 0
        
        return RiskValidation(
            passed=len(violations) == 0 and adjusted_shares > 0,
            original_shares=trade.shares,
            adjusted_shares=adjusted_shares,
            violations=violations,
            warnings=warnings
        )
    
    def _check_position_limit(
        self, trade: SizedPosition, context: TradingContext
    ) -> Tuple[bool, str, int]:
        """Ensure position doesn't exceed 10% of portfolio."""
        max_dollars = context.portfolio.total_value * self.MAX_POSITION_PCT
        price = trade.dollars / trade.shares
        max_shares = int(max_dollars / price)
        
        if trade.shares > max_shares:
            return (
                False,
                f"Position exceeds {self.MAX_POSITION_PCT:.0%} limit",
                max_shares
            )
        return (True, "", trade.shares)
    
    async def _check_sector_limit(
        self, trade: SizedPosition, context: TradingContext
    ) -> Tuple[bool, str, int]:
        """Ensure sector doesn't exceed 30% of portfolio."""
        sector = await get_stock_sector(trade.ticker)
        current_exposure = context.portfolio.sector_exposure.get(sector, 0)
        new_exposure = current_exposure + trade.weight
        
        if new_exposure > self.MAX_SECTOR_PCT:
            allowed_weight = self.MAX_SECTOR_PCT - current_exposure
            allowed_shares = int(
                allowed_weight * context.portfolio.total_value / 
                (trade.dollars / trade.shares)
            )
            return (
                False,
                f"Sector {sector} would exceed {self.MAX_SECTOR_PCT:.0%} limit",
                max(0, allowed_shares)
            )
        return (True, "", trade.shares)
    
    async def _check_portfolio_var(
        self, trade: SizedPosition, context: TradingContext
    ) -> Tuple[bool, str, int]:
        """Ensure portfolio VaR stays under 2%."""
        # Calculate new portfolio VaR with this trade
        current_var = await calculate_portfolio_var(context.portfolio)
        new_var = await calculate_portfolio_var_with_trade(
            context.portfolio, trade
        )
        
        if new_var > self.MAX_PORTFOLIO_VAR:
            # Binary search for acceptable size
            acceptable_shares = self._find_acceptable_shares(
                trade, context, self.MAX_PORTFOLIO_VAR
            )
            return (
                False,
                f"Portfolio VaR would exceed {self.MAX_PORTFOLIO_VAR:.1%}",
                acceptable_shares
            )
        return (True, "", trade.shares)
    
    async def _check_correlation(
        self, trade: SizedPosition, context: TradingContext
    ) -> Tuple[bool, str, int]:
        """Warn/reduce if highly correlated with existing holdings."""
        max_corr = 0
        correlated_with = ""
        
        for position in context.portfolio.positions:
            corr = await get_correlation(trade.ticker, position["ticker"])
            if corr > max_corr:
                max_corr = corr
                correlated_with = position["ticker"]
        
        if max_corr > self.MAX_CORRELATION:
            # Reduce position by correlation factor
            reduction = 1 - (max_corr - self.MAX_CORRELATION)
            adjusted = int(trade.shares * reduction)
            return (
                False,
                f"High correlation ({max_corr:.0%}) with {correlated_with}",
                adjusted
            )
        return (True, "", trade.shares)
    
    def _check_daily_loss(self, context: TradingContext) -> bool:
        """Check if daily loss limit exceeded."""
        daily_pnl = context.portfolio.realized_pnl_today
        daily_pnl_pct = daily_pnl / context.portfolio.total_value
        return daily_pnl_pct < -self.DAILY_LOSS_LIMIT
```

### Risk Constraints Summary

| Constraint | Limit | Action if Violated |
|------------|-------|-------------------|
| Position size | 10% max | Reduce to 10% |
| Sector exposure | 30% max | Reduce or skip |
| Portfolio VaR | 2% daily | Reduce position |
| Correlation | 80% max | Reduce 20-50% |
| Daily loss | 3% | Halt all trading |

---

## 9. Step 7: Execution

> **Status:** ✅ Partially built (IBKR integration exists)

### What It Does

Executes approved trades via IBKR API.

### Execution Modes

```
┌─────────────────────────────────────────────────────────────────┐
│  EXECUTION MODES                                                │
│                                                                 │
│  MODE A: SUPERVISED (Default)                                   │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  Agent decision                                           │ │
│  │       ↓                                                   │ │
│  │  Push notification to user                                │ │
│  │       ↓                                                   │ │
│  │  User taps [Approve] or [Reject]                         │ │
│  │       ↓                                                   │ │
│  │  If approved → Execute via IBKR                          │ │
│  │  If rejected → Log and skip                              │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  MODE B: AUTONOMOUS                                             │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  Agent decision                                           │ │
│  │       ↓                                                   │ │
│  │  Execute immediately via IBKR                             │ │
│  │       ↓                                                   │ │
│  │  Notify user of action taken                              │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
# src/agent/executor.py

from enum import Enum
from typing import Optional
from dataclasses import dataclass

class ExecutionMode(Enum):
    SUPERVISED = "supervised"
    AUTONOMOUS = "autonomous"

@dataclass
class ExecutionResult:
    success: bool
    order_id: Optional[str]
    fill_price: Optional[float]
    message: str

class TradeExecutor:
    """
    Executes trades via IBKR.
    Supports supervised (user approval) and autonomous modes.
    """
    
    def __init__(self, ibkr_service, notification_service):
        self.ibkr = ibkr_service
        self.notifications = notification_service
    
    async def execute(
        self,
        trade: SizedPosition,
        mode: ExecutionMode,
        user_id: str
    ) -> ExecutionResult:
        """
        Execute a trade.
        
        In supervised mode, queues for approval.
        In autonomous mode, executes immediately.
        """
        if mode == ExecutionMode.SUPERVISED:
            return await self._supervised_execution(trade, user_id)
        else:
            return await self._autonomous_execution(trade, user_id)
    
    async def _supervised_execution(
        self, trade: SizedPosition, user_id: str
    ) -> ExecutionResult:
        """Queue trade for user approval."""
        # Store pending trade
        pending_id = await self._store_pending(trade, user_id)
        
        # Send push notification
        await self.notifications.send_push(
            user_id=user_id,
            title=f"🤖 Agent: {trade.action} {trade.ticker}",
            body=f"{trade.shares} shares (${trade.dollars:,.0f}) — Tap to review",
            data={"pending_id": pending_id}
        )
        
        return ExecutionResult(
            success=True,
            order_id=None,
            fill_price=None,
            message=f"Pending approval: {pending_id}"
        )
    
    async def _autonomous_execution(
        self, trade: SizedPosition, user_id: str
    ) -> ExecutionResult:
        """Execute trade immediately."""
        try:
            # Place market order
            order = await self.ibkr.place_order(
                ticker=trade.ticker,
                action=trade.action,
                quantity=trade.shares,
                order_type="MARKET"
            )
            
            # Attach stop-loss if BUY
            if trade.action == "BUY":
                await self._attach_stop_loss(trade, order.fill_price)
            
            # Notify user
            await self.notifications.send_push(
                user_id=user_id,
                title=f"✅ Executed: {trade.action} {trade.ticker}",
                body=f"{trade.shares} shares @ ${order.fill_price:.2f}",
                data={"order_id": order.id}
            )
            
            return ExecutionResult(
                success=True,
                order_id=order.id,
                fill_price=order.fill_price,
                message="Executed"
            )
        
        except Exception as e:
            return ExecutionResult(
                success=False,
                order_id=None,
                fill_price=None,
                message=str(e)
            )
    
    async def _attach_stop_loss(self, trade: SizedPosition, fill_price: float):
        """Attach trailing stop-loss to new position."""
        stop_price = fill_price * 0.92  # 8% trailing stop
        
        await self.ibkr.place_order(
            ticker=trade.ticker,
            action="SELL",
            quantity=trade.shares,
            order_type="TRAIL",
            trail_percent=8.0
        )
    
    async def approve_pending(self, pending_id: str) -> ExecutionResult:
        """User approved a pending trade."""
        trade = await self._get_pending(pending_id)
        
        # Execute
        result = await self._autonomous_execution(trade, trade.user_id)
        
        # Mark as executed
        await self._mark_executed(pending_id, result)
        
        return result
    
    async def reject_pending(self, pending_id: str, reason: str):
        """User rejected a pending trade."""
        await self._mark_rejected(pending_id, reason)
```

---

## 10. Step 8: Learning Loop

> **Status:** 🔨 To build (Continuous)

### What It Does

Tracks outcomes of past decisions and learns lessons for future retrieval.

### Learning Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│  LEARNING LOOP (runs weekly)                                    │
│                                                                 │
│  1. GET DECISIONS FROM 1-4 WEEKS AGO                           │
│     └─ Positions that are now closed OR >2 weeks old           │
│                                                                 │
│  2. CALCULATE OUTCOMES                                          │
│     └─ outcome_pct = (exit_price - entry_price) / entry_price  │
│                                                                 │
│  3. CLAUDE REFLECTS                                             │
│     └─ "Given this outcome, what lesson should I remember?"    │
│                                                                 │
│  4. STORE LESSON                                                │
│     └─ Update memory with outcome + lesson                     │
│                                                                 │
│  5. RE-EMBED                                                    │
│     └─ Update vector embedding with new info                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
# src/agent/learning.py

class LearningLoop:
    """
    Tracks outcomes and generates lessons from past decisions.
    """
    
    def __init__(self, memory: AgentMemory, claude: DecisionEngine):
        self.memory = memory
        self.claude = claude
    
    async def run_weekly_update(self):
        """
        Update outcomes for recent decisions.
        Called weekly after market close.
        """
        # Get decisions needing outcome update
        pending_outcomes = await self.memory.get_pending_outcomes()
        
        for decision in pending_outcomes:
            # Check if position is closed
            position = await self._get_position_status(decision)
            
            if position.closed or decision.age_days > 14:
                # Calculate outcome
                outcome_pct = self._calculate_outcome(decision, position)
                
                # Have Claude reflect
                lesson = await self._generate_lesson(decision, outcome_pct)
                
                # Update memory
                await self.memory.update_outcome(decision.id, outcome_pct)
                await self.memory.store_lesson(decision.id, lesson)
    
    async def _generate_lesson(self, decision, outcome_pct: float) -> str:
        """Use Claude to generate a lesson from this decision."""
        prompt = f"""
        I made this trading decision:
        - Action: {decision.action} {decision.ticker}
        - Score at time: {decision.score}
        - Regime at time: {decision.regime}
        - Rationale: {decision.rationale}
        
        Outcome: {outcome_pct:+.1f}%
        
        What lesson should I remember for similar future situations?
        Keep it to 1-2 sentences.
        """
        
        response = await self.claude.client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}]
        )
        
        return response.content[0].text
```

### Example Lessons

| Decision | Outcome | Lesson Learned |
|----------|---------|----------------|
| BUY CMI, score 89, regime normal | +12% | "High-conviction Industrials in normal regime tend to follow through" |
| BUY TSLA, score 75, regime high_vol | -8% | "Avoid high-beta stocks when regime is elevated, even with decent scores" |
| SELL JNJ, score 38 | +2% (avoided -5%) | "Trust SELL signals on defensive stocks; they often precede sector rotation" |

---

## 11. iOS Integration

### User Modes

| Mode | Description | Best For |
|------|-------------|----------|
| **Manual** | Agent suggests, user decides everything | Learning phase |
| **Supervised** | Agent proposes, user approves via push | Default mode |
| **Autonomous** | Agent acts, user monitors | Trusted agent |

### New Views

1. **Agent Dashboard**
   - Status: Active / Paused
   - Pending approvals count
   - This week's actions
   - P&L from agent trades

2. **Agent History**
   - All decisions with rationale
   - Outcomes when known
   - Filter by: BUY/SELL, date, ticker

3. **Agent Settings**
   - Mode: Manual / Supervised / Autonomous
   - Risk profile: Conservative / Moderate / Aggressive
   - Pause / Resume button
   - Max trades per week

### API Endpoints

```
Agent Status & Control:
GET  /api/v1/agent/status           # Agent state + stats
POST /api/v1/agent/pause            # Pause agent
POST /api/v1/agent/resume           # Resume agent
PUT  /api/v1/agent/settings         # Update settings

Pending Approvals:
GET  /api/v1/agent/pending          # List pending trades
POST /api/v1/agent/pending/{id}/approve
POST /api/v1/agent/pending/{id}/reject

History:
GET  /api/v1/agent/history          # Past decisions
GET  /api/v1/agent/history/{id}     # Single decision detail

Context (for debugging):
GET  /api/v1/agent/context          # Current aggregated context
```

---

## 12. Validation & Metrics

### Validation Pipeline

```
1. BACKTEST (before paper trading)
   └─ Run agent logic on 2019-2023 historical data
   └─ Target: Alpha > 0%, Sharpe > 1.5, Max DD < 20%

2. PAPER TRADING (4-8 weeks)
   └─ IBKR paper account: DUP526287
   └─ Target: Stable operation, no bugs, reasonable decisions

3. SMALL LIVE (10% capital, 4 weeks)
   └─ Real money, supervised mode only
   └─ Target: Confirm paper results hold

4. SCALE UP (gradual)
   └─ Increase allocation based on performance
   └─ Consider autonomous mode after 3+ months supervised
```

### Success Metrics

| Category | Metric | Target |
|----------|--------|--------|
| **Returns** | Alpha | > 0% |
| | Sharpe Ratio | > 1.5 |
| | Win Rate | > 55% |
| **Risk** | Max Drawdown | < 20% |
| | Daily VaR | < 2% |
| | Largest Loss | < 5% |
| **Trust** | Approval Rate (supervised) | > 80% |
| | Override Rate | < 10% |

### Existing Backtest Results

| Metric | Sigil (Jun-Nov 2019) | SPY | Alpha |
|--------|----------------------|-----|-------|
| Return | +20.85% | +15.56% | **+5.29%** |
| Sharpe | 4.42 | — | — |
| Max DD | -6.26% | — | — |

---

## 13. Implementation Plan

### Phase 0: Context Builder (Week 1)
- [ ] `src/agent/context.py` — Unified context aggregator
- [ ] `GET /api/v1/agent/context` endpoint
- [ ] CLI: `python -m src.agent.context --ticker CMI`

### Phase 1: Memory + Position Sizing (Weeks 2-3)
- [ ] pgvector setup in PostgreSQL
- [ ] `src/agent/memory.py` — Three-tier memory
- [ ] `src/agent/position_sizing.py` — Risk Parity optimizer
- [ ] Unit tests for both

### Phase 2: Decision Engine (Weeks 4-5)
- [ ] `src/agent/decision_engine.py` — Claude integration
- [ ] Anthropic SDK with extended thinking
- [ ] `src/agent/risk_validator.py` — Risk checks
- [ ] Integration tests

### Phase 3: Execution + Loop (Weeks 6-7)
- [ ] `src/agent/executor.py` — IBKR execution
- [ ] Supervised mode with push notifications
- [ ] `src/agent/learning.py` — Outcome tracking
- [ ] **🎯 FIRST PAPER TRADE**

### Phase 4: Data Collection (Months 2-6)
- [ ] Run weekly, collect 500+ decisions
- [ ] Monitor performance metrics
- [ ] **Month 6: Evaluate — Claude-only sufficient?**

### Phase 5-6: Pattern Model (OPTIONAL)
- [ ] Only if Phase 4 evaluation shows need
- [ ] DPO fine-tuning on decision pairs
- [ ] Two-model pipeline

### Phase 7: Live Trading
- [ ] Start with 10% capital, supervised
- [ ] Scale based on performance
- [ ] Can start Month 4 if Claude-only is sufficient

### Timeline

| Phase | Duration | Cumulative |
|-------|----------|------------|
| **0** Context Builder | 1 week | Week 1 |
| **1** Memory + Sizing | 2 weeks | Week 3 |
| **2** Decision Engine | 2 weeks | Week 5 |
| **3** Execution | 2 weeks | Week 7 |
| | 🎯 **First Paper Trade** | **Week 7** |
| **4** Data Collection | 5 months | Month 6 |
| **5-6** Pattern Model | Optional | Month 7 |
| **7** Live Trading | Month 4-8 | Ongoing |

### Two Paths

```
PATH A: Claude + ICL (Faster)
Weeks 1-7 build → Paper trade → Month 4 live
Total: ~4 months

PATH B: Full Two-Model (If needed)
Weeks 1-7 build → Paper trade → Train DPO → Month 8 live
Total: ~8 months
```

**Recommendation:** Start with Path A. Add Pattern Model only if evaluation shows it's needed.

---

*Document Version: 2.0*
*Last Updated: 2026-02-16*
*Author: Blaze Neon 🔥*
