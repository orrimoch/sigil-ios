<img src="sigil_logo.jpg" alt="Sigil" width="240" />

# THE END GAME FEATURE BRAINSTORMING

**Autonomous AI Trading Agent for Sigil**

> *"The ultimate goal: an AI agent that uses all Sigil's insights as levers to maximize profit and manage risk autonomously."*

---

## Table of Contents

**Part I: Vision & Philosophy**
1. [Vision](#vision)
2. [The Expert Trader Mental Model](#the-expert-trader-mental-model)
3. [Why This Works: Reducing Unknown Variables](#why-this-works-reducing-unknown-variables)

**Part II: Core Technology**
4. [Technology Stack](#technology-stack)
5. [Two-Model Architecture](#two-model-architecture)
6. [Existing Implementations to Adapt](#existing-implementations-to-adapt)

**Part III: Architecture**
7. [Integration with Existing Features](#integration-with-existing-features)
8. [Decision Framework](#decision-framework)
9. [Data Freshness & Coherence](#data-freshness--coherence)
10. [iOS App Integration](#ios-app-integration)

**Part IV: Validation & Governance**
11. [Validation & Backtesting](#validation--backtesting)
12. [Success Metrics](#success-metrics)
13. [Regulatory & Compliance](#regulatory--compliance)

**Part V: Implementation**
14. [Phased Implementation Plan](#phased-implementation-plan)
15. [Timeline](#timeline)

---

## Vision

Transform Sigil from a **recommendation engine** into an **autonomous portfolio manager** that:

- **Observes**: All signals (composite scores, sentiment, technical, macro, crowd wisdom, sector trends)
- **Reasons**: Synthesizes signals into coherent market view and portfolio strategy
- **Decides**: BUY/SELL/HOLD decisions with precise position sizing
- **Executes**: Sends orders to IBKR (paper → live) with proper risk controls
- **Learns**: Tracks outcomes and improves over time

The agent operates within user-defined risk parameters, acting as a tireless portfolio manager that never sleeps.

### Alignment with PRD: "The Busy Builder"

From `01_PRD.md`:
> *"A high-tech professional, 30-40 years old, navigating the demands of a hectic career while wanting their wealth to grow intelligently in the background. They're sophisticated enough to understand markets but too busy (and too smart) to day-trade."*

| User Need | How Agent Delivers |
|-----------|-------------------|
| 5-10 min/week | Agent acts autonomously |
| Set-and-forget | User sets preferences once |
| Confidence | Agent explains every decision |
| Glanceable | Weekly summary of actions taken |

---

## The Expert Trader Mental Model

> **Core Insight**: The agent is not an algorithm with ML bolted on. It's a **very knowledgeable person** — an expert trader with perfect recall and clear, refined context.

| Rules Engine | Expert Trader (Our Agent) |
|--------------|---------------------------|
| "IF score > 70 AND regime = low_vol THEN BUY 5%" | "JPM scores 95. Sector rotating into financials. Fed dovish. Insiders bought. Risk budget allows. **This is the moment.**" |
| Follows static rules | Synthesizes context dynamically |
| Treats all signals equally | Weighs relevance by situation |
| Fails on edge cases | Reasons through ambiguity |

**What makes an expert trader:**
1. **Perfect context** — Sees everything simultaneously
2. **Pattern recognition** — Knows when signals converge vs conflict
3. **Timing intuition** — Understands *when* to act, not just *what*
4. **Risk awareness** — Never forgets position limits, drawdown
5. **Adaptive judgment** — Adjusts for regime (crisis vs calm)

**The agent thinks:**
> "Given everything I know about this stock and my portfolio, what would a thoughtful portfolio manager do right now?"

---

## Why This Works: Reducing Unknown Variables

> **Core Insight:** We sidestep the prediction problem by making the LLM's job a *reasoning* problem.

**Traditional approach (hard):**
```
Raw data → Predictive Model → "AAPL +3.2% tomorrow"
                 ↓
    Massive unknowns, low accuracy, overfitting
```

**Sigil approach (tractable):**
```
Raw data → Pipelines → Refined Signals → LLM Reasoning → Decision
              ↓              ↓                 ↓
         (hard work)    Score: 95         "Given this
         - Scoring      Insiders: ↑        context,
         - Sentiment    Regime: calm       should I
         - Risk/VaR     Risk: green        buy?"
         - Crowd wisdom
```

| Prediction Problem | Reasoning Problem (Ours) |
|--------------------|--------------------------|
| "Will AAPL go up?" | "Given these signals, is this a good trade?" |
| Unknown: everything | Unknown: very little |
| Accuracy: ~50% | Decision quality: high |

**What's left for the LLM:**
- Synthesize 5-6 refined signals (not 1000 data points)
- Apply judgment: "Is confluence strong enough?"
- Consider timing: "Is now the moment?"

---

## Technology Stack

### 1. Vector Database: pgvector

Store contextualized experiences for semantic retrieval.

| Memory Type | Example |
|-------------|---------|
| Decision context | "Bought JPM at $185, score 95, regime low_vol" |
| Outcome | "JPM +12% in 2 weeks, thesis validated" |
| Lesson learned | "Waiting after VIX spike paid off 3/4 times" |

**Why pgvector:**
- PostgreSQL extension — fits REC-272 infrastructure
- Same DB for relational + vector data
- Good enough for ~100K vectors

**Memory retrieval:**
```
Current context → Embed → Query top-K similar → Inject into prompt
```

### 2. Anthropic SDK for Agent

Native tool use with extended thinking:

```python
tools = [
    {"name": "get_stock_score", ...},
    {"name": "get_portfolio_state", ...},
    {"name": "get_market_regime", ...},
    {"name": "execute_trade", ...},
    {"name": "recall_similar_situations", ...}
]

response = client.messages.create(
    model="claude-sonnet-4-20250514",
    thinking={"type": "enabled", "budget_tokens": 5000},
    tools=tools,
    messages=[{"role": "user", "content": "Weekly portfolio review..."}]
)
```

### 3. In-Context Learning (Phase 1)

Store every decision + outcome in pgvector. When deciding, retrieve similar past situations:

```
Similar past situations:
1. BAC (Dec 2024): Score 92, same regime → Bought → +8% ✓
2. WFC (Mar 2024): Score 88, same regime → Bought → -3% ✗ (earnings)

Given this history, what's your decision?
```

The LLM learns from its own history without fine-tuning.

---

## Two-Model Architecture

> **Constraint:** Claude can't be fine-tuned. Solution: separate learning from reasoning.

```
┌─────────────────────────────────────────────────────────────┐
│                    TWO-MODEL ARCHITECTURE                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────┐                       │
│  │  PATTERN MODEL (Learnable)      │  ← DPO fine-tuned     │
│  │  Llama 8B / Mistral 7B          │     on our data       │
│  │                                 │                       │
│  │  Output: "73% confidence,       │                       │
│  │   68% historical win rate"      │                       │
│  └──────────────┬──────────────────┘                       │
│                 ↓                                          │
│  ┌─────────────────────────────────┐                       │
│  │  CLAUDE (Reasoning)             │  ← No fine-tuning     │
│  │                                 │                       │
│  │  Output: "Buy JPM. High pattern │                       │
│  │   score, risk budget allows."   │                       │
│  └─────────────────────────────────┘                       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

| Component | Role | Trainable |
|-----------|------|-----------|
| **Pattern Model** | "What worked before?" | ✅ DPO/LoRA |
| **Claude** | "What should I do now?" | ❌ But doesn't need it |

**Phased rollout:**
- Phase 1-3: Claude + pgvector ICL only
- Phase 4: Collect 500+ decision pairs
- Phase 5: **DECISION POINT** — Evaluate if Pattern Model needed
- Phase 6: (Optional) Train Llama 8B pattern model

### ⚠️ Pattern Model is OPTIONAL

**Claude + pgvector might be enough.** After 3-6 months of paper trading:

```
Performance Review (Phase 4)
           ↓
Is Claude + ICL achieving targets?
     (Alpha > 0, Sharpe > 1.5)
          /            \
        YES             NO
         ↓               ↓
    SKIP Pattern      ADD Pattern Model
    Model (simpler)   (Phase 5-6)
```

**Arguments for skipping DPO:**
- Claude reasons well without training
- pgvector retrieval shows 10-20 relevant past decisions
- Simpler architecture = fewer failure points
- Markets change — patterns from 2025 may not work in 2027

**Arguments for adding DPO:**
- Model learns subtle patterns from 500+ decisions
- Cheaper inference if running locally
- Less reliant on Anthropic API

**Recommendation:** Start with Claude + ICL. Add Pattern Model only if needed.

---

## Existing Implementations to Adapt

> **Principle:** Don't reinvent. Fork and adapt.

| Project | What to Take | GitHub |
|---------|--------------|--------|
| **FinMem** | 3-tier memory (working/short/long), trading loop | `pipiku915/FinMem-LLM-StockTrading` |
| **FinGPT** | LoRA fine-tuning scripts, forecaster prompts | `AI4Finance-Foundation/FinGPT` |
| **TRL** | `DPOTrainer` (production-ready) | `huggingface/trl` |

**FinMem → Sigil mapping:**
```
FinMem/puppy/                    Sigil/src/agent/
├── memory/                      ├── memory/
│   ├── working_memory.py   →    │   ├── working.py
│   ├── short_term_memory.py →   │   ├── short_term.py
│   └── long_term_memory.py  →   │   └── long_term.py (pgvector)
├── profiling/               →   ├── profile.py
└── decision/                →   └── decision.py (Anthropic SDK)
```

**Clone:**
```bash
git clone https://github.com/pipiku915/FinMem-LLM-StockTrading.git ~/refs/finmem
git clone https://github.com/AI4Finance-Foundation/FinGPT.git ~/refs/fingpt
pip install trl peft transformers
```

---

## Integration with Existing Features

> **Key Principle**: The agent **consumes** existing features. Every module becomes a lever.

| Feature | Module | Agent Role |
|---------|--------|------------|
| Composite Scores | `src/scoring/` | Primary signal |
| Sentiment | `src/sentiment/` | Market mood |
| VaR / Stop-Loss | `src/risk/` | Risk constraints |
| HMM Regime | `src/risk/hmm_regime.py` | Market state filter |
| Crowd Wisdom | `src/crowd_wisdom/` | Smart money signal |
| Sector Trends | `src/analytics/` | Sector momentum |
| IBKR | `src/ibkr/` | Execution |
| Portfolio | `src/portfolio/` | Current state |

**Context aggregation:**
```python
context = {
    "score": await scores_api.get_score(ticker),
    "regime": await risk_api.get_regime(),
    "vix": await risk_api.get_vix(),
    "portfolio": await portfolio_api.get_state(),
    "insider_signal": await crowd_api.get_insider_score(ticker),
    "sector_trend": await sector_api.get_trend(sector),
}
decision = await agent.decide(context)
```

---

## Decision Framework

### Trading Philosophy

**NOT HFT** — Sigil captures weekly trends:
- Weekly decision cycle (after pipeline runs)
- 3-10 trades/week maximum
- Position trades for 5-30 days

### When to BUY

```python
strong_buy = (
    score >= 75 and
    signal == "BUY" and
    regime in ["low_vol", "normal"] and
    sector_concentration < 25% and
    pattern_confidence > 60%  # From pattern model
)
```

### When to SELL

```python
must_sell = (
    signal == "SELL" or
    score < 40 or
    stop_loss_triggered or
    (regime == "crisis" and unrealized_pnl < 0)
)
```

### Position Sizing

**MVP:** Fixed 5% per position
**Later:** Conviction-weighted (higher score = bigger size)

### Risk Constraints

- Max position: 10% of portfolio
- Max sector: 30% of portfolio
- Regime adjustment: reduce size in high_vol/crisis
- Daily loss limit: pause if exceeded

---

## Data Freshness & Coherence

> **Critical:** Agent must HALT on stale data.

| Data Type | Max Age | Action if Stale |
|-----------|---------|-----------------|
| Composite scores | 7 days | HALT |
| HMM regime | 24 hours | HALT |
| Prices | 15 min (market hours) | HALT |
| VIX | 4 hours | WARN |
| Crowd wisdom | 14 days | WARN |

**Health check before trading:**
```python
def check_health():
    if scores_age > 7 days: return HALT
    if regime_age > 24 hours: return HALT
    if is_market_open() and prices_age > 15 min: return HALT
    return PROCEED
```

**API endpoint:** `GET /api/v1/data/freshness`

---

## iOS App Integration

### User Modes

| Mode | Description |
|------|-------------|
| **Manual** | Agent suggests, user decides |
| **Supervised** | Agent proposes, user approves via push notification |
| **Autonomous** | Agent acts, user monitors |

### New Views

1. **Agent Dashboard** — Status, pending actions, weekly P&L
2. **Agent History** — All decisions with rationale + outcome
3. **Agent Settings** — Mode, risk profile, pause/resume

### API Endpoints

```
GET  /api/v1/agent/status
GET  /api/v1/agent/pending
POST /api/v1/agent/pending/{id}/approve
POST /api/v1/agent/pending/{id}/reject
GET  /api/v1/agent/history
POST /api/v1/agent/pause
POST /api/v1/agent/resume
```

---

## Validation & Backtesting

### Existing Infrastructure

| Component | Location |
|-----------|----------|
| Backtest Engine | `src/backtest/engine.py` |
| Historical Sentiment | `src/sentiment_historical/` (30K+ headlines) |
| CLI | `python3 -m src.backtest` |

### Validated Results (Jun-Nov 2019)

| Metric | Sigil | SPY | Alpha |
|--------|-------|-----|-------|
| Return | +20.85% | +15.56% | **+5.29%** |
| Sharpe | 4.42 | — | — |
| Max DD | -6.26% | — | — |

### Validation Pipeline

1. **Backtest** — Run on 2019-2023 data
2. **Paper Trading** — IBKR paper (DUP526287), 4-8 weeks
3. **Small Live** — 10% capital, manual approval
4. **Full Live** — Gradual scale-up

---

## Success Metrics

### Financial Performance

| Metric | Target |
|--------|--------|
| Alpha | > 0% |
| Sharpe Ratio | > 1.5 |
| Max Drawdown | < 20% |
| Win Rate | > 55% |

### Risk Control

| Metric | Limit |
|--------|-------|
| Max Drawdown | < 20% |
| VaR (95%, 1-day) | < 2% |
| Position Size | < 10% |
| Sector Concentration | < 30% |

### User Trust (Supervised Mode)

| Metric | Target |
|--------|--------|
| Approval Rate | > 80% |
| Override Rate | < 10% |

---

## Regulatory & Compliance

### Required Disclosures

- "Sigil provides information, not financial advice."
- "You can lose money. Past performance ≠ future results."
- "Agent will trade on your behalf. You remain responsible."

### Agent-Specific

| Concern | Mitigation |
|---------|------------|
| Unauthorized trading | User must explicitly enable |
| Runaway losses | Max daily loss limit, emergency stop |
| Audit trail | Every decision logged |

---

## Phased Implementation Plan

### Phase 0: Context Builder (Week 1)
- [ ] Unified context aggregator (`src/agent/context.py`)
- [ ] Single API returns all signals
- [ ] CLI for context inspection

### Phase 1: Memory Infrastructure (Weeks 2-3)
- [ ] pgvector setup in PostgreSQL
- [ ] Three-tier memory (working/short/long)
- [ ] Memory retrieval and storage

### Phase 2: Claude Agent + ICL (Weeks 4-5)
- [ ] Anthropic SDK integration
- [ ] Sigil APIs as Claude tools
- [ ] Extended thinking for decisions
- [ ] In-context learning with retrieved memories

### Phase 3: Paper Trading Loop (Weeks 6-7)
- [ ] Weekly decision cadence
- [ ] IBKR paper integration (DUP526287)
- [ ] Outcome tracking

**🎯 MILESTONE: First Paper Trade (~Week 7)**

### Phase 4: Data Collection + Evaluation (Months 2-6)
- [ ] Automated decision pair logging
- [ ] Target: 500+ pairs
- [ ] Weekly performance reports
- [ ] **DECISION POINT: Evaluate if Claude + ICL is sufficient**

```
Month 6 Review:
├── Alpha > 0%? Sharpe > 1.5? Win rate > 55%?
│     ↓
│   YES → Skip to Phase 7 (Live Trading)
│   NO  → Continue to Phase 5 (Pattern Model)
```

### Phase 5: Pattern Model Training (OPTIONAL - Month 6-7)
> ⚠️ **Only if Phase 4 evaluation shows Claude + ICL is insufficient**

- [ ] Prepare DPO dataset from 500+ decisions
- [ ] Fine-tune Llama 8B with LoRA
- [ ] Evaluate improvement vs Claude-only

### Phase 6: Two-Model Production (OPTIONAL - Month 7)
> ⚠️ **Only if Pattern Model shows measurable improvement**

- [ ] Deploy pattern model locally
- [ ] Two-model pipeline
- [ ] Monitoring and alerting

**🎯 MILESTONE: Pattern Model Live (~Month 7) — IF NEEDED**

### Phase 7: Live Trading (Month 4+ or Month 8+)
- [ ] Start with 10% capital, manual approval
- [ ] Scale based on performance
- [ ] Can start as early as Month 4 if Claude + ICL is sufficient

---

## Timeline

| Phase | Duration | Cumulative | Required? |
|-------|----------|------------|-----------|
| **0** Context Builder | 1 week | Week 1 | ✅ Yes |
| **1** Memory (pgvector) | 2 weeks | Week 3 | ✅ Yes |
| **2** Claude Agent + ICL | 2 weeks | Week 5 | ✅ Yes |
| **3** Paper Trading | 2 weeks | Week 7 | ✅ Yes |
| | **🎯 FIRST PAPER TRADE** | **~7 weeks** | |
| **4** Data Collection + Eval | 4-5 months | Month 6 | ✅ Yes |
| | **🔀 DECISION POINT** | **Month 6** | |
| **5** Pattern Model (DPO) | 2 weeks | Month 7 | ⚠️ Optional |
| **6** Two-Model Integration | 2 weeks | Month 7 | ⚠️ Optional |
| **7** Live Trading | Ongoing | Month 4-8 | ✅ Yes |

### Key Milestones

| Milestone | Target |
|-----------|--------|
| First paper trade | Week 7 |
| Stable paper trading | Month 3 |
| **Decision: Pattern Model needed?** | **Month 6** |
| Live trading (10%) | Month 4-8 (depends on path) |

### Two Paths to Live Trading

```
PATH A: Claude + ICL Sufficient (Faster)
Week 7 → Paper Trade → Month 3-4 Evaluate → Month 4 Live
Total: ~4 months

PATH B: Pattern Model Needed (Full)
Week 7 → Paper Trade → Month 6 Evaluate → Train DPO → Month 8 Live
Total: ~8 months
```

### Total Timeline

| Scenario | Time to Live |
|----------|--------------|
| **Claude-only (Path A)** | **~4 months** ← Start here |
| Full two-model (Path B) | ~7-8 months |
| Conservative (extended paper) | ~10 months |

**Recommendation:** Start with Path A. Add Pattern Model only if evaluation shows it's needed.

### Resource Requirements

| Resource | Phase 0-3 | Phase 4-6 | Phase 7+ |
|----------|-----------|-----------|----------|
| Development | Active | Monitoring | Maintenance |
| GPU | None | Training (~$50-100) | Local inference |
| Claude API | ~$5/month | ~$10/month | ~$20/month |

---

*This document is a living brainstorm. Update as we learn more.*

**Last Updated**: 2026-02-14
**Author**: Blaze Neon 🔥
