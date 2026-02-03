<img src="sigil_logo.jpg" alt="Sigil" width="240" />

# Agentic Analysis Research — market-analyzer Integration

**Source:** [github.com/barkain/market-analyzer](https://github.com/barkain/market-analyzer)
**Author:** Nadav Barkain
**Date:** February 3, 2026

---

## Architecture Overview

Nadav's market-analyzer is a **multi-agent AI system** that autonomously discovers market opportunities using a 5-phase pipeline:

```
Phase 1: MacroScanner       → Global macro regime (growth/recession/inflation)
Phase 2: SectorRotator      → Sector momentum & rotation signals
Phase 3: OpportunityHunter  → Screen for specific stock opportunities
Phase 4: Deep Dive Analysts → 5 specialist agents analyze each candidate
Phase 5: SynthesisLead      → Rank, aggregate, produce final insights
```

### Specialist Agents (Phase 4)

| Agent | Role | What It Does |
|-------|------|-------------|
| `technical_analyst` | Price Action | RSI, MACD, Bollinger, patterns, support/resistance |
| `macro_economist` | Macro Context | Regime classification, yield curve, rate environment |
| `sector_strategist` | Sector Positioning | Sector vs benchmark, rotation patterns |
| `risk_analyst` | Risk Assessment | Downside risk, volatility, tail events |
| `correlation_detective` | Cross-Asset | Inter-stock correlations, contagion risk |

### Synthesis Lead (65KB — the brain)
- Receives all analyst reports
- Cross-references with historical patterns (knowledge base)
- Adjusts confidence based on track record
- Produces ranked insights with actionable recommendations (BUY/SELL/WATCH)

---

## Key Features Not In Sigil

### 1. LLM-Powered Analysis (Claude Agent SDK)
- Uses `claude-agent-sdk` with MCP tool calling
- Each agent has a specialized system prompt
- Tools: `get_stock_data`, `analyze_technical`, `detect_patterns`, `get_economic_indicators`, etc.
- **Conversational**: Users can ask follow-up questions about insights

### 2. Autonomous Discovery
- Doesn't need user-specified stocks
- Scans entire market → identifies opportunities → deep dives
- Our app requires the user to look at specific stocks

### 3. Outcome Tracking + Learning Loop
- Tracks predictions over 20 trading days
- Measures actual vs predicted direction
- Updates pattern success rates
- Confidence adjuster learns from past accuracy

### 4. Institutional Memory Service
- Stores past analyses and their outcomes
- Builds knowledge patterns over time
- Used by SynthesisLead to improve future predictions

### 5. Insight Conversations
- Chat with any insight for deeper analysis
- Follow-up research agent for specific questions

---

## Integration Plan for Sigil

### Phase 1: Enhanced Scoring (Low effort, High impact)
**Replace keyword sentiment with LLM analysis**

Current: `scoring/sentiment_score.py` uses keyword matching
New: Add optional LLM-powered sentiment analysis when API key available

```python
# Config flag (already planned)
SENTIMENT_MODEL = "keyword"  # or "llm" 
```

### Phase 2: Autonomous Discovery Engine (Medium effort)
**Add a discovery pipeline alongside our weekly scoring**

- MacroScanner → Already have `macro_fetcher.py` (FRED data)
- SectorRotator → Already have sector sensitivity in `macro_score.py`
- OpportunityHunter → New: screen top scores for confirmation signals
- Deep Dive → New: LLM analysis of top 5-10 picks

Output: "AI Deep Analysis" card on Home Dashboard showing discovered opportunities with thesis explanations.

### Phase 3: Outcome Tracking (Medium effort)
**Track our score predictions over time**

- When we give a BUY signal at score 75, did the stock go up?
- Track 20-day performance after each signal
- Build confidence adjuster for our scoring weights
- Display "prediction accuracy" on the app

```python
# New module
backend/src/tracking/
├── outcome_tracker.py    # Track prediction outcomes
├── confidence_adjuster.py # Adjust weights based on accuracy
└── knowledge_base.py     # Pattern storage
```

### Phase 4: Chat with AI (High effort, differentiated feature)
**Add conversational AI to stock detail view**

- "Why is AAPL rated BUY?"
- "What are the risks for NVDA?"
- "Compare AAPL vs MSFT"
- Uses Claude Agent SDK with MCP tools (from market-analyzer)

New iOS feature: Chat bubble on StockDetailView

### Phase 5: Full Agent Integration (High effort)
**Run Nadav's full 5-phase pipeline weekly**

- Fork market-analyzer's autonomous engine
- Feed results into our scoring as an "AI confidence" factor
- Add as 5th scoring component: Fundamental (30%) + Sentiment (20%) + Technical (20%) + Macro (15%) + **AI Agent (15%)**

---

## Technical Requirements

| Requirement | Current | Needed |
|------------|---------|--------|
| Python | 3.9 | 3.11+ (for market-analyzer) |
| LLM Access | None | Claude API or Claude Agent SDK |
| Database | JSON files | SQLite/PostgreSQL (for outcome tracking) |
| Dependencies | yfinance, feedparser | + claude-agent-sdk, sqlalchemy async |

---

## Recommended Implementation Order

1. **Outcome Tracking** (Phase 3) — Validates our existing scores, low risk
2. **Enhanced Sentiment** (Phase 1) — Quick win with LLM upgrade
3. **Autonomous Discovery** (Phase 2) — "AI Deep Analysis" feature
4. **Chat with AI** (Phase 4) — Killer UX feature
5. **Full Agent Integration** (Phase 5) — Long-term architecture

---

## Key Takeaways from market-analyzer

1. **Structured prompts matter** — Each agent has a detailed, specialized prompt
2. **Parse → Validate → Store** — LLM outputs are parsed into typed dataclasses
3. **Confidence calibration** — Track outcomes to improve future confidence
4. **Memory is crucial** — Institutional memory prevents repeated mistakes
5. **Synthesis > Individual** — The SynthesisLead combining all agents is where the real value is

---

*Research by Blaze Neon — February 3, 2026*
