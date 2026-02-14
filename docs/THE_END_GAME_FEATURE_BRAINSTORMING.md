<img src="sigil_logo.jpg" alt="Sigil" width="240" />

# THE END GAME FEATURE BRAINSTORMING

**Autonomous AI Trading Agent for Sigil**

> *"The ultimate goal: an AI agent that uses all Sigil's insights as levers to maximize profit and manage risk autonomously."*

---

## Table of Contents

**Part I: Strategy & Context**
1. [Vision](#vision)
2. [Alignment with PRD & Target User](#alignment-with-prd--target-user)
3. [Integration with Existing Features](#integration-with-existing-features)
4. [Strategic Plan & Simplifying Assumptions](#strategic-plan--simplifying-assumptions)

**Part II: Technical Approaches**
5. [Advanced: LLM Reasoning + Sequential Rec + RL](#advanced-llm-reasoning--sequential-rec--rl)
6. [Reference Projects (Don't Reinvent the Wheel)](#reference-projects-dont-reinvent-the-wheel)

**Part III: Architecture & Design**
7. [Trading Resolution & Frequency](#trading-resolution--frequency) ⚠️ NOT HFT
8. [Data Freshness & Coherence](#data-freshness--coherence)
9. [Core Challenges](#core-challenges)
10. [Architecture Overview](#architecture-overview)
11. [Module Breakdown](#module-breakdown)
12. [State & Signal Integration](#state--signal-integration)
13. [Decision Framework](#decision-framework)
14. [Position Sizing & Risk Management](#position-sizing--risk-management)
15. [Execution Layer](#execution-layer)
16. [User Preference Alignment](#user-preference-alignment)
17. [iOS App Integration](#ios-app-integration)
18. [Real-Time vs Batch Considerations](#real-time-vs-batch-considerations)

**Part IV: Validation & Governance**
19. [Validation & Backtesting](#validation--backtesting)
20. [Regulatory & Compliance](#regulatory--compliance)
21. [Success Metrics](#success-metrics)

**Part V: Resources & Planning**
22. [Research & References](#research--references)
23. [Open Questions](#open-questions)
24. [Phased Implementation Plan](#phased-implementation-plan)
25. [Next Steps](#next-steps)

---

## Vision

Transform Sigil from a **recommendation engine** into an **autonomous portfolio manager** that:

- **Observes**: All signals (composite scores, sentiment, technical, macro, crowd wisdom, sector trends)
- **Reasons**: Synthesizes signals into coherent market view and portfolio strategy
- **Decides**: BUY/SELL/HOLD decisions with precise position sizing
- **Executes**: Sends orders to IBKR (paper → live) with proper risk controls
- **Learns**: Tracks outcomes and improves over time

The agent operates within user-defined risk parameters, acting as a tireless portfolio manager that never sleeps.

---

## Alignment with PRD & Target User

> **Reference**: See `01_PRD.md` for full product context.

### Target User: "The Busy Builder"

From the PRD:
> *"A high-tech professional, 30-40 years old, navigating the demands of a hectic career while wanting their wealth to grow intelligently in the background. They're sophisticated enough to understand markets but too busy (and too smart) to day-trade."*

**Key characteristics**:
- Time available: **5-10 minutes per week**
- Goal: **Passive wealth growth, not active trading**
- Want: **Set intelligent parameters and let money work for them**

### Why Autonomous Agent is Perfect for This User

| User Need (PRD) | How Agent Delivers |
|-----------------|-------------------|
| "Glanceable insights" | Agent provides weekly summary of actions taken |
| "Confidence" | Agent explains every decision with rationale |
| "Simplicity" | User sets preferences once, agent handles rest |
| "Time efficiency" | User does nothing — agent acts autonomously |
| "Set-and-forget" | Agent monitors 24/7, acts on signals |

### PRD Success Criteria → Agent Metrics

From `01_PRD.md`:

| PRD Metric | Target | Agent Constraint |
|------------|--------|------------------|
| Alpha over S&P 500 | > 0% | Agent must beat benchmark |
| Sharpe Ratio | > 1.5 | Risk-adjusted returns |
| Maximum Drawdown | < 20% | Hard stop, agent pauses |
| User Retention (30-day) | > 60% | Agent must build trust |

### PRD Core Flows Enhanced by Agent

| Flow | PRD Version | With Agent |
|------|-------------|------------|
| **Weekly Check-In** | User sees recommendations, decides | Agent already executed, user reviews |
| **Execute a Trade** | User taps Buy → Confirm | Already done (with approval option) |
| **Understand a Score** | User taps, reads | Agent explains why it acted |

---

## Integration with Existing Features

> **Key Principle**: The autonomous agent doesn't replace our features — it **consumes** them. Every feature we've built becomes a lever/input to the decision function.

### Feature → Lever Mapping

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         EXISTING FEATURES AS INPUTS                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐       │
│  │ SCORING ENGINE  │     │  RISK MODULE    │     │ CROWD WISDOM    │       │
│  │ F1, F2          │     │  Phase 1-3      │     │ Insider/Reddit  │       │
│  ├─────────────────┤     ├─────────────────┤     ├─────────────────┤       │
│  │ • Composite 0-100│    │ • VaR (95%)     │     │ • Smart money   │       │
│  │ • BUY/HOLD/SELL │     │ • Stop-loss     │     │ • Viral scores  │       │
│  │ • Sub-scores    │     │ • HMM regime    │     │ • Top picks     │       │
│  │ • Sector/Industry│    │ • Position limits│    │ • Cluster bonus │       │
│  └────────┬────────┘     └────────┬────────┘     └────────┬────────┘       │
│           │                       │                       │                 │
│           └───────────────────────┼───────────────────────┘                 │
│                                   │                                         │
│                                   ▼                                         │
│  ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐       │
│  │ SECTOR ANALYSIS │     │   PORTFOLIO     │     │  IBKR SERVICE   │       │
│  │ (New)           │     │   STATE         │     │  F6.3           │       │
│  ├─────────────────┤     ├─────────────────┤     ├─────────────────┤       │
│  │ • Sector trends │     │ • Holdings      │     │ • Live prices   │       │
│  │ • Momentum      │     │ • Cash          │     │ • Order exec    │       │
│  │ • Heatmaps      │     │ • P&L           │     │ • Account info  │       │
│  │ • Distribution  │     │ • Concentration │     │ • Order status  │       │
│  └────────┬────────┘     └────────┬────────┘     └────────┬────────┘       │
│           │                       │                       │                 │
│           └───────────────────────┼───────────────────────┘                 │
│                                   │                                         │
│                                   ▼                                         │
│                    ┌──────────────────────────────┐                         │
│                    │     DECISION FUNCTION        │                         │
│                    │                              │                         │
│                    │  f(context) → {action, size} │                         │
│                    │                              │                         │
│                    │  action ∈ {BUY, SELL, HOLD}  │                         │
│                    │  size = dollar amount        │                         │
│                    └──────────────────────────────┘                         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Complete Feature Inventory (What We Already Have)

| Feature | Module | Output Type | Role as Lever |
|---------|--------|-------------|---------------|
| **Composite Scores** | `src/scoring/` | 0-100 per stock | Primary signal strength |
| **BUY/HOLD/SELL Signal** | `src/scoring/` | Categorical | Direction indicator |
| **Fundamental Score** | `src/scoring/` | 0-100 | Long-term value |
| **Sentiment Score** | `src/sentiment/` | 0-100 | Market mood |
| **Technical Score** | `src/scoring/` | 0-100 | Price momentum |
| **Macro Score** | `src/scoring/` | 0-100 | Economic context |
| **VaR (Value at Risk)** | `src/risk/var_calculator.py` | Dollar amount | Max loss estimate |
| **Portfolio VaR** | `src/risk/portfolio_var.py` | Dollar amount | Correlated risk |
| **HMM Regime** | `src/risk/hmm_regime.py` | low_vol/normal/high_vol/crisis | Market state |
| **Stop-Loss Distance** | `src/risk/stop_loss.py` | Percentage | Exit trigger |
| **VIX Level** | `src/risk/vix_service.py` | Number | Fear gauge |
| **Claude Risk Analysis** | `src/risk/claude_analyzer.py` | Risk rating + narrative | AI judgment |
| **Position Limits** | `src/risk/position_limits.py` | Warnings | Constraint check |
| **Sector Concentration** | `src/risk/sector_limits.py` | Percentage per sector | Diversification |
| **Sector Trends** | `src/analytics/sector_analysis.py` | Trend direction | Sector momentum |
| **Insider Transactions** | `src/crowd_wisdom/insider_*` | Buy/Sell signals | Smart money |
| **Reddit Viral Scores** | `src/crowd_wisdom/` | 0-100 | Social sentiment |
| **Portfolio Holdings** | `src/portfolio/` | Positions + P&L | Current state |
| **IBKR Connection** | `src/ibkr/` | Live data + execution | Action capability |
| **Price History** | `src/data/` | OHLCV | Technical context |

### The Agent as an Orchestrator

The agent doesn't need new data sources — it **orchestrates** existing ones:

```python
# Pseudocode: Agent decision loop
async def make_decision(ticker: str) -> Decision:
    # 1. Gather context from EXISTING features
    context = {
        # From scoring engine
        "score": await scores_api.get_score(ticker),
        "signal": await scores_api.get_signal(ticker),
        "score_history": await scores_api.get_history(ticker),
        
        # From risk module
        "var": await risk_api.calculate_var(ticker),
        "regime": await risk_api.get_regime(),
        "vix": await risk_api.get_vix(),
        "stop_distance": await risk_api.get_stop_distance(ticker),
        "claude_analysis": await risk_api.get_claude_analysis(ticker),
        
        # From portfolio
        "holding": await portfolio_api.get_position(ticker),
        "portfolio_var": await portfolio_api.get_var(),
        "sector_exposure": await portfolio_api.get_sector_exposure(),
        "cash_available": await portfolio_api.get_cash(),
        
        # From crowd wisdom
        "insider_signal": await crowd_api.get_insider_score(ticker),
        "reddit_viral": await crowd_api.get_viral_score(ticker),
        
        # From sector analysis
        "sector_trend": await sector_api.get_trend(ticker.sector),
        
        # From IBKR
        "live_price": await ibkr_api.get_quote(ticker),
    }
    
    # 2. Pass to decision function
    decision = decision_function(context)
    
    # 3. Return action
    return decision  # {action: BUY/SELL/HOLD, size: $X, reason: "..."}
```

---

## Strategic Plan & Simplifying Assumptions

### Simplifying Assumptions (Start Simple, Add Complexity)

| Assumption | Simplification | Future Enhancement |
|------------|----------------|-------------------|
| **A1: Weekly decisions** | Act once per week after pipeline runs | Add daily/intraday triggers |
| **A2: Score = Truth** | Trust composite score as ground truth | Add real-time adjustments |
| **A3: Single account** | One IBKR account per user | Multi-account support |
| **A4: Market orders** | Use market orders for simplicity | Smart order routing |
| **A5: No leverage** | Cash only, no margin | Add margin management |
| **A6: US equities only** | 850 stocks (NASDAQ+NYSE, >$10B) | Add crypto, forex, etc. |
| **A7: Equal conviction** | All BUY signals treated equally | Conviction-weighted |
| **A8: Fixed position size** | 5% of portfolio per position | Dynamic sizing |
| **A9: No short selling** | Long only | Add short capability |
| **A10: Paper first** | Mandatory paper trading period | Gradual live rollout |

### Strategic Approach: Build the Chain

```
┌─────────────────────────────────────────────────────────────────────┐
│                    THE DECISION CHAIN                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  STEP 1           STEP 2           STEP 3           STEP 4         │
│  ────────         ────────         ────────         ────────        │
│                                                                     │
│  ┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐       │
│  │ CONTEXT │ ──▶ │ FILTER  │ ──▶ │  RANK   │ ──▶ │ EXECUTE │       │
│  │ BUILDER │     │  GATE   │     │ & SIZE  │     │ & LOG   │       │
│  └─────────┘     └─────────┘     └─────────┘     └─────────┘       │
│                                                                     │
│  Gather all      Apply hard       Rank by          Send orders,    │
│  signals into    constraints      conviction,      record all      │
│  unified state   (regime, VaR,    allocate         decisions       │
│                  limits)          capital                          │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Pros/Cons of Different Approaches

#### Approach 1: Rule-Based System (Deterministic)

```python
# Simple if-then rules
if score >= 70 and regime != "crisis" and sector_exposure < 30%:
    return BUY
elif score < 40 or stop_triggered:
    return SELL
else:
    return HOLD
```

| Pros | Cons |
|------|------|
| ✅ Fully explainable | ❌ Brittle, doesn't adapt |
| ✅ Fast execution | ❌ Can't handle nuance |
| ✅ Easy to debug | ❌ Many edge cases |
| ✅ No API costs | ❌ Requires manual tuning |
| ✅ Predictable | ❌ May miss complex patterns |

**Best for**: MVP, baseline, safety fallback

---

#### Approach 2: LLM-Powered Reasoning (Claude/GPT)

```python
# LLM synthesizes context into decision
prompt = f"""
You are an autonomous trading agent. Given the current context:
- Stock: {ticker}
- Score: {score} (signal: {signal})
- Regime: {regime}, VIX: {vix}
- Portfolio exposure: {exposure}
- Insider activity: {insider}
- Your position: {holding}

Should you BUY, SELL, or HOLD? How much? Explain your reasoning.
"""
decision = await claude.complete(prompt)
```

| Pros | Cons |
|------|------|
| ✅ Handles nuance | ❌ API costs (~$0.01/decision) |
| ✅ Natural reasoning | ❌ Non-deterministic |
| ✅ Can explain itself | ❌ Latency (1-3 sec) |
| ✅ Adapts to context | ❌ May hallucinate |
| ✅ Considers all factors | ❌ Harder to backtest |

**Best for**: Complex decisions, conflict resolution, explanations

---

#### Approach 3: HMM/ML-Based (Statistical)

```python
# Use HMM regime + score to determine action
regime_weights = {
    "low_vol": {"buy_threshold": 65, "sell_threshold": 45},
    "normal": {"buy_threshold": 70, "sell_threshold": 40},
    "high_vol": {"buy_threshold": 80, "sell_threshold": 50},
    "crisis": {"buy_threshold": 999, "sell_threshold": 30},  # No buys in crisis
}
thresholds = regime_weights[current_regime]
```

| Pros | Cons |
|------|------|
| ✅ Data-driven | ❌ Needs training data |
| ✅ Adapts to regimes | ❌ Black box |
| ✅ Fast inference | ❌ May overfit |
| ✅ Backtestable | ❌ Cold start problem |

**Best for**: Regime-adaptive decisions, position sizing

---

#### Approach 4: Hybrid (Recommended)

```
┌──────────────────────────────────────────────────────────────────┐
│                     HYBRID APPROACH                              │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐                                                │
│  │ RULE-BASED   │  Fast filter: Hard constraints                 │
│  │ (Gate)       │  - Regime check                                │
│  │              │  - Position limits                             │
│  │              │  - Cash available                              │
│  └──────┬───────┘                                                │
│         │ Candidates pass through                                │
│         ▼                                                        │
│  ┌──────────────┐                                                │
│  │ HMM/ML       │  Adaptive sizing: Regime-aware allocation      │
│  │ (Sizing)     │  - Volatility targeting                        │
│  │              │  - Regime-adjusted thresholds                  │
│  └──────┬───────┘                                                │
│         │ Sized candidates                                       │
│         ▼                                                        │
│  ┌──────────────┐                                                │
│  │ LLM          │  Final arbiter: Complex cases only             │
│  │ (Reasoning)  │  - Conflicting signals                         │
│  │              │  - Unusual patterns                            │
│  │              │  - Generate explanations                       │
│  └──────┬───────┘                                                │
│         │ Final decision                                         │
│         ▼                                                        │
│  ┌──────────────┐                                                │
│  │ EXECUTOR     │  Execute: IBKR order submission                │
│  └──────────────┘                                                │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

| Pros | Cons |
|------|------|
| ✅ Best of all worlds | ❌ More complex |
| ✅ Fast for simple cases | ❌ Multiple systems to maintain |
| ✅ LLM only when needed | ❌ Integration complexity |
| ✅ Explainable | |
| ✅ Backtestable (rule layer) | |

---

### MVP Definition (Minimum Viable Agent)

**Goal**: An agent that can make weekly portfolio rebalancing decisions using our existing scores.

**Scope**:
- ✅ Read composite scores and signals
- ✅ Read current portfolio state
- ✅ Apply hard constraints (regime, limits)
- ✅ Generate BUY/SELL recommendations
- ✅ Fixed position sizing (5% per stock)
- ✅ Paper trading only
- ✅ Weekly cadence
- ❌ No intraday trading
- ❌ No LLM reasoning (rules only)
- ❌ No dynamic sizing

**Success Metrics**:
- Matches or beats naive score-following strategy
- No catastrophic decisions (blow-ups)
- All decisions logged with rationale

---

### Implementation Phases (Refined)

#### Phase 0: Context Builder (1 week)
Build the unified context aggregator that pulls from all existing APIs:
```python
context = await build_agent_context()
# Returns: scores, portfolio, risk metrics, crowd wisdom, sector data
```

#### Phase 1: Rule-Based Gate (1-2 weeks)
Hard constraints that filter candidates:
- Regime gate (no BUYs in crisis)
- Position limit gate (max 10% per stock)
- Sector limit gate (max 30% per sector)
- Cash gate (sufficient funds)
- Score threshold gate (>70 for BUY, <40 for SELL)

#### Phase 2: Ranking & Fixed Sizing (1-2 weeks)
Rank filtered candidates, allocate capital:
- Sort BUY candidates by score (highest first)
- Allocate 5% of portfolio per position
- Limit to max 10 new positions per week

#### Phase 3: Paper Trading Loop (2 weeks)
Run weekly with paper account:
- Every Sunday: run pipeline, generate decisions
- Monday open: execute via IBKR paper
- Track performance vs benchmark

#### Phase 4: LLM Enhancement (2-3 weeks)
Add Claude for complex cases:
- Signal conflicts (high score but negative sentiment)
- Regime transitions
- Unusual patterns
- Generate human-readable explanations

#### Phase 5: Dynamic Sizing (2 weeks)
Replace fixed sizing with:
- Conviction-weighted (higher score = bigger size)
- Volatility-adjusted (lower vol = bigger size)
- Kelly Criterion option

#### Phase 6: Live Trading (Gradual)
- Start with 10% of portfolio under agent control
- Scale up as confidence grows

---

## Advanced: LLM Reasoning + Sequential Rec + RL

> **Key Insight**: The most powerful approach combines real-time LLM reasoning with learned policies from RL, framed as a sequential recommendation problem.

### Why This Combination?

| Component | Strength | Weakness | Complementary Role |
|-----------|----------|----------|-------------------|
| **LLM Reasoning** | Handles nuance, explains decisions, generalizes | No memory of past performance | Immediate decision quality |
| **Sequential Rec** | Models temporal dependencies, session context | Needs training data | Captures order effects |
| **RL** | Learns from outcomes, optimizes long-term reward | Sample inefficient, slow | Improves over time |

Together: **LLM proposes** → **RL evaluates** → **Sequential context informs both**

---

### LLM Reasoning Modes (Real-Time)

> **Note**: We implemented LLM provider abstraction in REC-272. See `backend/src/llm/` for provider-agnostic interface.

We have access to multiple LLM providers:

```python
from src.llm import get_llm_provider

# Provider selected via LLM_PROVIDER env var (anthropic/openai/google)
llm = get_llm_provider()

# Standard: Fast (Sonnet/GPT-4o-mini/Gemini Flash)
response = await llm.complete(prompt)

# Extended Thinking: Deep reasoning (Opus with thinking, or o1)
response = await llm.complete(
    prompt,
    model="claude-opus-4-5-20250514",  # or "o1-preview"
    thinking={"type": "enabled", "budget_tokens": 10000}
)
```

**Available Providers** (via `GET /api/v1/config/llm/providers`):
- **Anthropic**: Claude Sonnet (default), Claude Opus (thinking)
- **OpenAI**: GPT-4o, o1-preview (reasoning)
- **Google**: Gemini Pro, Gemini Flash

**Real-Time Reasoning Flow**:
```
┌─────────────────────────────────────────────────────────────────────┐
│                    LLM REASONING IN REAL-TIME                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  CONTEXT INJECTION           CHAIN-OF-THOUGHT           OUTPUT     │
│  ─────────────────           ────────────────           ──────     │
│                                                                     │
│  ┌─────────────────┐       ┌─────────────────┐       ┌──────────┐  │
│  │ • Score: 78     │       │ "Let me analyze │       │ ACTION:  │  │
│  │ • Signal: BUY   │       │  this step by   │       │ BUY AAPL │  │
│  │ • VIX: 18       │  ──▶  │  step...        │  ──▶  │ $5,000   │  │
│  │ • Regime: normal│       │                 │       │          │  │
│  │ • Holding: none │       │  1. Score is    │       │ REASON:  │  │
│  │ • Cash: $50K    │       │     strong...   │       │ High     │  │
│  │ • Sector: 15%   │       │  2. Regime OK   │       │ score,   │  │
│  │ • Insider: +3   │       │  3. Risk OK     │       │ low VIX, │  │
│  └─────────────────┘       │  4. Size calc   │       │ insider  │  │
│                            └─────────────────┘       │ confirm  │  │
│                                                      └──────────┘  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**Prompt Engineering for Trading**:
```python
TRADING_AGENT_PROMPT = """
You are an autonomous trading agent managing a portfolio.

CURRENT CONTEXT:
{context_json}

PORTFOLIO STATE:
{portfolio_json}

RISK CONSTRAINTS:
- Max position: 10% of portfolio
- Max sector: 30% of portfolio  
- Current regime: {regime}
- VaR limit: ${var_limit}

DECISION HISTORY (last 5):
{recent_decisions}

TASK: Analyze the opportunity for {ticker} and decide:
1. Should you BUY, SELL, or HOLD?
2. If BUY/SELL, how much (in dollars)?
3. What's your confidence (0-100)?
4. Explain your reasoning step by step.

Think carefully about:
- Signal strength vs risk
- Portfolio impact (correlation, concentration)
- Market regime appropriateness
- Historical patterns with similar setups
"""
```

---

### Sequential Recommendation Framing

Portfolio management IS a sequential recommendation problem:

```
SESSION-BASED RECSYS              PORTFOLIO MANAGEMENT
─────────────────────             ────────────────────
User session                  ═   Trading week/month
Items to recommend            ═   Stocks to trade
Click/purchase               ═   BUY action
Item features                ═   Stock scores/signals
Session history              ═   Trade history
Next-item prediction         ═   Next optimal trade
```

**Key Sequential Models**:

| Model | Mechanism | Trading Application |
|-------|-----------|---------------------|
| **GRU4Rec** | RNN for sessions | Capture trade sequence dependencies |
| **SASRec** | Self-attention | Long-range dependencies in portfolio |
| **BERT4Rec** | Bidirectional | Understand full context |
| **Transformer** | Attention | Multi-stock joint decisions |

**Portfolio as Sequence**:
```
t=0: [AAPL:BUY, MSFT:HOLD, GOOGL:HOLD, ...]
t=1: [AAPL:HOLD, MSFT:BUY, GOOGL:SELL, ...]  
t=2: [AAPL:SELL, MSFT:HOLD, GOOGL:BUY, ...]
     ...
     
The model learns: given sequence t=0..t-1, predict optimal action at t
```

**Why Sequential Matters**:
1. **Order effects**: Selling AAPL before buying MSFT frees cash
2. **Momentum**: Recent winners may continue (or revert)
3. **Regime memory**: What worked in last crisis?
4. **Portfolio path**: How we got here affects where to go

---

### Reinforcement Learning Formulation

**MDP (Markov Decision Process)**:

```python
State s_t = {
    # Portfolio state
    "holdings": Dict[ticker, shares],
    "cash": float,
    "portfolio_value": float,
    
    # Market state  
    "scores": Dict[ticker, 0-100],
    "signals": Dict[ticker, BUY/HOLD/SELL],
    "vix": float,
    "regime": str,
    
    # History
    "recent_returns": List[float],  # Last N days
    "recent_trades": List[Trade],   # Last M trades
}

Action a_t = {
    "ticker": str,
    "action": BUY | SELL | HOLD,
    "amount": float,  # Dollars or shares
}

Reward r_t = {
    # Option 1: Simple P&L
    "pnl": portfolio_value(t+1) - portfolio_value(t)
    
    # Option 2: Risk-adjusted
    "sharpe": (return - rf) / volatility
    
    # Option 3: Composite
    "composite": pnl * (1 - max_drawdown_penalty) * regime_bonus
}

Transition: s_{t+1} = execute(s_t, a_t, market_movement)
```

**RL Algorithms for Trading**:

| Algorithm | Type | Best For |
|-----------|------|----------|
| **PPO** | Policy Gradient | Stable training, continuous actions |
| **A2C** | Actor-Critic | Fast, parallel training |
| **DDPG** | Off-policy | Continuous action space (sizing) |
| **SAC** | Entropy-regularized | Exploration-exploitation balance |
| **DQN** | Value-based | Discrete actions (BUY/SELL/HOLD) |

**The RL Challenge**:
- **Sparse rewards**: P&L only realized on sell
- **Non-stationary**: Markets change (regime shifts)
- **Sample efficiency**: Can't do millions of real trades
- **Simulation gap**: Backtest ≠ live market

---

### Hybrid: LLM + RL (State of the Art)

**Approach 1: LLM as Policy, RL as Critic**

```
┌──────────────────────────────────────────────────────────────────┐
│               LLM-ACTOR + RL-CRITIC ARCHITECTURE                 │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────┐                        ┌─────────────┐         │
│  │    STATE    │                        │   ACTION    │         │
│  │   s_t       │                        │   a_t       │         │
│  └──────┬──────┘                        └──────▲──────┘         │
│         │                                      │                 │
│         ▼                                      │                 │
│  ┌─────────────┐         ┌─────────────┐      │                 │
│  │    LLM      │ ──────▶ │  CANDIDATE  │ ─────┤                 │
│  │   ACTOR     │         │   ACTIONS   │      │                 │
│  │  (Claude)   │         │  [a1,a2,a3] │      │                 │
│  └─────────────┘         └──────┬──────┘      │                 │
│                                 │              │                 │
│                                 ▼              │                 │
│                          ┌─────────────┐       │                 │
│                          │     RL      │       │                 │
│                          │   CRITIC    │ ──────┘                 │
│                          │  Q(s,a)     │  Select best action     │
│                          └─────────────┘                         │
│                                                                  │
│  LLM proposes actions with reasoning                             │
│  RL critic scores actions based on learned value function        │
│  Best action executed                                            │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

**Approach 2: RL Learns Prompt Selection**

```python
# RL agent learns WHICH prompt to use for Claude
prompts = {
    "aggressive": "Look for high-conviction opportunities...",
    "defensive": "Focus on capital preservation...",
    "balanced": "Balance risk and reward...",
    "momentum": "Follow recent winners...",
    "contrarian": "Look for oversold opportunities...",
}

# RL policy: state → prompt_id
prompt_id = rl_policy(state)
decision = claude.complete(prompts[prompt_id], context=state)
```

**Approach 3: In-Context RL (Few-Shot Learning)**

```python
# Include past decisions + outcomes in prompt
prompt = f"""
You are a trading agent. Here are your recent decisions and outcomes:

Decision 1: BUY AAPL at $150 (score: 75) → Result: +8% in 2 weeks ✓
Decision 2: BUY TSLA at $200 (score: 68) → Result: -12% (stopped out) ✗
Decision 3: HOLD MSFT (score: 72) → Result: +3% (missed opportunity) ≈

Pattern: High scores (>75) in stable regime → good outcomes
Pattern: Moderate scores in volatile regime → poor outcomes

Current situation:
{current_context}

Based on your past experience, what should you do?
"""
```

**Approach 4: Memory-Enhanced LLM (FinMem-style)**

```
┌─────────────────────────────────────────────────────────────────┐
│                   MEMORY-ENHANCED AGENT                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────┐       │
│  │                    MEMORY LAYERS                     │       │
│  ├─────────────────────────────────────────────────────┤       │
│  │                                                      │       │
│  │  WORKING MEMORY     SHORT-TERM        LONG-TERM     │       │
│  │  ───────────────    ──────────        ─────────     │       │
│  │  Current context    Last 10 trades   All history    │       │
│  │  Live prices        Recent P&L       Learned        │       │
│  │  Today's news       This week        patterns       │       │
│  │                                                      │       │
│  └──────────────────────────┬──────────────────────────┘       │
│                             │                                   │
│                             ▼                                   │
│                    ┌─────────────────┐                          │
│                    │  LLM REASONER   │                          │
│                    │  + Memory       │                          │
│                    │  Retrieval      │                          │
│                    └────────┬────────┘                          │
│                             │                                   │
│                             ▼                                   │
│                       DECISION                                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

### Practical Implementation Path

**Phase A: LLM Reasoning First (Fastest to Value)**
1. Use Claude with extended thinking for complex decisions
2. Inject all context (scores, portfolio, risk)
3. Few-shot examples of good decisions
4. Log everything for later RL training

**Phase B: Add Memory Layer**
1. Store all decisions + outcomes in DB
2. Retrieve similar past situations
3. Include in prompt for in-context learning

**Phase C: Train RL Critic**
1. Use logged decisions as offline RL data
2. Train Q-function to evaluate actions
3. Use critic to filter LLM proposals

**Phase D: Sequential Model**
1. Train transformer on trade sequences
2. Predict "next best action" distribution
3. Combine with LLM reasoning

---

---

## Reference Projects (Don't Reinvent the Wheel)

> **Key Insight**: These 5 projects provide battle-tested architectures we can adapt.

### 1. FinMem (Best for Memory Architecture) ⭐

**Paper**: arxiv:2311.13743 | **Repo**: github.com/pipiku915/FinMem-LLM-StockTrading

**Architecture** (directly applicable to us):
```
┌─────────────────────────────────────────────────────────────────┐
│                        FINMEM MODULES                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. PROFILING          2. MEMORY             3. DECISION        │
│  ───────────           ────────              ─────────          │
│  Agent character       Layered storage       Convert memories   │
│  Risk tolerance        Working/Short/Long    to trading         │
│  Trading style         term memory           decisions          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Key Takeaways for Sigil**:
- ✅ **Layered Memory**: Working (current), Short-term (recent), Long-term (patterns)
- ✅ **Character Design**: Agent has "personality" (risk profile, trading style)
- ✅ **Train/Test Split**: Populate memory in "training", use it in "testing"
- ✅ **Adjustable Perceptual Span**: How far back the agent looks

**What to Copy**:
```python
# Memory structure we should implement
class SigilAgentMemory:
    working_memory: Dict      # Current context (today's signals)
    short_term: List[Event]   # Recent trades (last 10)
    long_term: Dict           # Patterns learned (regime→performance)
```

---

### 2. TradingAgents (Best for Multi-Agent Debate) ⭐

**Paper**: arxiv:2412.20138 | **Repo**: github.com/TauricResearch/TradingAgents

**Architecture** (mirrors real trading firms):
```
┌─────────────────────────────────────────────────────────────────┐
│                    TRADINGAGENTS ROLES                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ANALYST TEAM              RESEARCHER TEAM        EXECUTION     │
│  ────────────              ───────────────        ─────────     │
│  • Fundamentals Analyst    • Bull Researcher      • Trader      │
│  • Sentiment Analyst       • Bear Researcher      • Risk Mgmt   │
│  • News Analyst            (debate!)              • Portfolio   │
│  • Technical Analyst                              • Manager     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Key Takeaways for Sigil**:
- ✅ **Specialized Analysts**: Each signal type has dedicated "expert"
- ✅ **Bull/Bear Debate**: Forces consideration of both sides
- ✅ **Risk Management Layer**: Separate from trading decision
- ✅ **Portfolio Manager Approval**: Final gate before execution

**What to Copy**:
```python
# Multi-agent flow we should implement
async def make_decision(ticker: str) -> Decision:
    # 1. Gather analyst opinions (parallel)
    fundamental = await fundamental_analyst(context)
    sentiment = await sentiment_analyst(context)
    technical = await technical_analyst(context)
    
    # 2. Bull/Bear debate
    bull_case = await bull_researcher(fundamental, sentiment, technical)
    bear_case = await bear_researcher(fundamental, sentiment, technical)
    
    # 3. Trader synthesizes
    proposal = await trader(bull_case, bear_case)
    
    # 4. Risk management check
    risk_check = await risk_manager(proposal, portfolio)
    
    # 5. Portfolio manager approves/rejects
    decision = await portfolio_manager(proposal, risk_check)
    
    return decision
```

---

### 3. FinRL (Best for RL Environment) ⭐

**Paper**: arxiv:2011.09607 | **Repo**: github.com/AI4Finance-Foundation/FinRL

**Architecture** (three-layer design):
```
┌─────────────────────────────────────────────────────────────────┐
│                      FINRL LAYERS                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Layer 1: APPLICATIONS     Stock, Crypto, Portfolio, HFT       │
│           ────────────────────────────────────────────          │
│                              │                                  │
│  Layer 2: AGENTS           PPO, A2C, DDPG, SAC, TD3            │
│           ────────────────────────────────────────────          │
│                              │                                  │
│  Layer 3: ENVIRONMENTS     Market gym envs (state/action/reward)│
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Key Takeaways for Sigil**:
- ✅ **Train-Test-Trade Pipeline**: Structured workflow
- ✅ **Gym-style Environment**: Standard interface
- ✅ **Multiple RL Algorithms**: Compare what works
- ✅ **Extensive Data Sources**: Yahoo, Alpaca, etc.

**What to Copy**:
```python
# Environment interface we should implement
class SigilTradingEnv(gym.Env):
    def __init__(self, df, initial_amount, ...):
        self.action_space = gym.spaces.Box(-1, 1, shape=(num_stocks,))
        self.observation_space = ...
    
    def step(self, action):
        # Execute trades based on action
        reward = self._calculate_reward()
        state = self._get_state()
        return state, reward, done, info
    
    def reset(self):
        # Reset to initial state
        return self._get_state()
```

---

### 4. FinRL-DeepSeek (Best for LLM+RL Integration) ⭐

**Paper**: arxiv:2502.07393 | **Repo**: github.com/AI4Finance-Foundation/FinRL_DeepSeek

**Key Innovation**: LLM-Infused Risk-Sensitive RL
```
┌─────────────────────────────────────────────────────────────────┐
│                  FINRL-DEEPSEEK FLOW                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  NEWS DATA                                                      │
│      │                                                          │
│      ▼                                                          │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐         │
│  │  DeepSeek   │    │  DeepSeek   │    │   RL Agent  │         │
│  │  Sentiment  │ ─▶ │    Risk     │ ─▶ │  (CPPO)     │         │
│  │  Analysis   │    │  Analysis   │    │             │         │
│  └─────────────┘    └─────────────┘    └──────┬──────┘         │
│                                               │                 │
│                                               ▼                 │
│                                         TRADING ACTION          │
│                                                                 │
│  Key Finding: PPO for bull markets, CPPO-DeepSeek for bear     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Key Takeaways for Sigil**:
- ✅ **LLM generates features for RL**: Sentiment + Risk signals
- ✅ **CPPO (Conservative PPO)**: Risk-sensitive RL variant
- ✅ **Regime-dependent strategy**: Different algo for different markets
- ✅ **Simple but effective**: LLM→signal→RL pipeline

**What to Copy**:
```python
# LLM signal generation for RL
def generate_llm_signals(news: List[str]) -> Dict:
    sentiment = claude.analyze_sentiment(news)  # -1 to 1
    risk_level = claude.analyze_risk(news)      # 0 to 1
    return {"sentiment": sentiment, "risk": risk_level}

# These become features for the RL agent
state = {
    "prices": price_data,
    "technicals": technical_indicators,
    "llm_sentiment": sentiment,  # LLM-generated
    "llm_risk": risk_level,      # LLM-generated
}
```

---

### 5. FinGPT (Best for Financial LLM) ⭐

**Paper**: arxiv:2306.06031 | **Repo**: github.com/AI4Finance-Foundation/FinGPT

**Key Features**:
- Fine-tuned LLMs for financial tasks
- Sentiment analysis SOTA (beats GPT-4 for $17 training cost!)
- FinGPT-Forecaster: Direct stock prediction

**Key Takeaways for Sigil**:
- ✅ **RLHF for personalization**: Learn user preferences
- ✅ **Lightweight fine-tuning**: LoRA on RTX 3090
- ✅ **Multiple tasks**: Sentiment, NER, QA, Headlines
- ✅ **Forecaster pattern**: Ticker + date + context → prediction

**Prompt Template to Copy**:
```python
FINGPT_FORECASTER_PROMPT = """
[Ticker]: {ticker}
[Date]: {date}

[Recent News]:
{news_summary}

[Basic Financials]:
{financials}

Based on the above information, predict the stock price movement 
for next week. Provide:
1. Direction: UP / DOWN / NEUTRAL
2. Confidence: 0-100
3. Key factors supporting your prediction
"""
```

---

### Consolidated Architecture for Sigil

Combining best practices from all 5 projects:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      SIGIL AUTONOMOUS AGENT v1.0                            │
│                  (Inspired by FinMem + TradingAgents + FinRL)               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         MEMORY MODULE (FinMem)                       │   │
│  │  Working: Current signals    Short: Recent trades    Long: Patterns │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                      │                                      │
│                                      ▼                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      ANALYST TEAM (TradingAgents)                    │   │
│  │                                                                      │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐            │   │
│  │  │Fundamental│  │Sentiment │  │Technical │  │ Macro/   │            │   │
│  │  │ Analyst  │  │ Analyst  │  │ Analyst  │  │ Risk     │            │   │
│  │  │(scores)  │  │(sentiment│  │(technical│  │(VIX/HMM) │            │   │
│  │  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘            │   │
│  │       │             │             │             │                   │   │
│  │       └─────────────┴──────┬──────┴─────────────┘                   │   │
│  │                            │                                        │   │
│  └────────────────────────────┼────────────────────────────────────────┘   │
│                               │                                             │
│                               ▼                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    DEBATE MODULE (TradingAgents)                     │   │
│  │                                                                      │   │
│  │           ┌──────────────┐    vs    ┌──────────────┐                │   │
│  │           │    BULL      │    ⚔️    │    BEAR      │                │   │
│  │           │  Researcher  │          │  Researcher  │                │   │
│  │           └──────────────┘          └──────────────┘                │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                               │                                             │
│                               ▼                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     DECISION MODULE (Hybrid)                         │   │
│  │                                                                      │   │
│  │  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐             │   │
│  │  │    TRADER    │ → │RISK MANAGER  │ → │  PORTFOLIO   │             │   │
│  │  │  (Propose)   │   │  (Validate)  │   │  MANAGER     │             │   │
│  │  │              │   │              │   │  (Approve)   │             │   │
│  │  └──────────────┘   └──────────────┘   └──────────────┘             │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                               │                                             │
│                               ▼                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    EXECUTION MODULE (FinRL + IBKR)                   │   │
│  │                                                                      │   │
│  │  Order Generation → Risk Limit Check → IBKR Submit → Log Outcome   │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                               │                                             │
│                               ▼                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    LEARNING MODULE (FinRL-DeepSeek)                  │   │
│  │                                                                      │   │
│  │  Log all decisions → Track outcomes → Update memory → Improve       │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### Our Edge: Integration

**What we have that others don't**:
1. ✅ Pre-computed scores (not raw data → insights)
2. ✅ Risk module (VaR, HMM, Claude analysis, position limits)
3. ✅ Crowd wisdom (insider transactions + Reddit viral)
4. ✅ Sector analysis (trends, momentum, 12 sectors, 131 industries)
5. ✅ IBKR integration (paper: DUP526287, live ready)
6. ✅ 850-stock scored universe (NASDAQ+NYSE, >$10B market cap)
7. ✅ LLM abstraction (Anthropic/OpenAI/Google, see REC-272)
8. ✅ Backtest system with historical sentiment (30K+ headlines)

**The LLM doesn't start from raw data** — it gets pre-digested insights. This is more efficient and likely more effective.

---

## Trading Resolution & Frequency

> **Critical Clarification**: Sigil is **NOT** a High-Frequency Trading (HFT) system. The agent captures **weekly trends**, not intraday noise.

### Trading Philosophy

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SIGIL TRADING RESOLUTION                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ❌ NOT THIS (HFT)                    ✅ THIS (Weekly Trend Capture)        │
│  ──────────────────                   ────────────────────────────          │
│                                                                             │
│  • Millisecond execution              • Weekly decision cycle               │
│  • Exploit tick-by-tick noise         • Capture multi-day/week trends      │
│  • Thousands of trades/day            • 3-10 trades/week maximum           │
│  • Requires co-location               • Standard retail execution          │
│  • Scalping small profits             • Position trades for 5-30 days      │
│  • Real-time data feeds ($$$)         • Weekly pipeline + minute execution │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Time Horizons

| Layer | Time Resolution | Purpose |
|-------|-----------------|---------|
| **Strategic** | Weekly | Score generation, signal identification, target portfolio |
| **Tactical** | Daily | Regime check, VIX adjustment, queue prioritization |
| **Execution** | Minutes | Order placement, price validation, fill confirmation |

### Why Weekly Trends?

1. **Signal Quality**: Composite scores are based on fundamentals, sentiment, technicals — these move on weekly timescales, not seconds
2. **Noise Reduction**: Intraday price movements are mostly noise; weekly trends are more predictable
3. **Cost Efficiency**: Fewer trades = lower commissions, lower slippage, better tax treatment
4. **Data Alignment**: Our pipeline updates weekly — decisions should match data freshness
5. **User Fit**: "Busy Builder" persona wants set-and-forget, not day-trading

### Decision Cycle

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    WEEKLY DECISION CYCLE                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  SUNDAY 6PM          MONDAY 9:30AM         DURING WEEK        FRIDAY       │
│  ───────────         ─────────────         ────────────       ──────       │
│                                                                             │
│  Pipeline runs       Agent executes        Monitor:           Review:      │
│  Scores updated      planned trades        • Stop-losses      • P&L        │
│  Agent decides:      (minute-level         • Regime shifts    • Positions  │
│  • What to BUY       execution)            • VIX spikes       • Prepare    │
│  • What to SELL                            • Earnings          for next    │
│  • Position sizes                          (react if needed)   week        │
│                                                                             │
│  ◄──────────── STRATEGIC ────────────►    ◄─── TACTICAL ───►              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Execution Resolution (Minutes, Not Milliseconds)

When the agent executes, it operates at **minute-level resolution**:

```python
class ExecutionTiming:
    """Execution operates at minute resolution, not HFT."""
    
    # NOT doing this (HFT):
    # - Sub-second order routing
    # - Market microstructure exploitation
    # - Latency arbitrage
    
    # DOING this (minute-level):
    CHECK_INTERVAL_SECONDS = 60      # Check prices every minute
    PRICE_STALENESS_MINUTES = 5      # Price valid for 5 minutes
    ORDER_TIMEOUT_MINUTES = 15       # Cancel unfilled orders after 15 min
    
    def execute_trade(self, trade: PlannedTrade):
        # 1. Get current price (minute-level)
        price = self.get_quote(trade.ticker)  # ~1 sec latency is fine
        
        # 2. Validate price hasn't moved too much from decision time
        if abs(price - trade.decision_price) / trade.decision_price > 0.02:
            return self.re_evaluate(trade)  # >2% move → reconsider
        
        # 3. Submit order (market or limit)
        order = self.submit_order(trade)
        
        # 4. Wait for fill (up to 15 minutes)
        return self.await_fill(order, timeout_minutes=15)
```

### Data Freshness Aligned with Strategy

| Data Type | Update Frequency | Aligns With |
|-----------|------------------|-------------|
| Composite Scores | Weekly (Sunday) | Strategic decisions |
| HMM Regime | Daily (6am) | Tactical adjustment |
| VIX | Every 4 hours | Tactical adjustment |
| Prices | Real-time via IBKR | Execution only |
| Insider Data | Weekly | Strategic (slow signal) |
| Sector Trends | Weekly | Strategic context |

**Key Principle**: Strategic decisions use weekly data. Real-time data is only for execution validation, not for changing the strategy mid-week.

### When to React Intraday

The agent only reacts intraday for **risk events**, not opportunities:

| Event | Action | Rationale |
|-------|--------|-----------|
| Stop-loss triggered | Execute SELL immediately | Risk management |
| VIX > 30 spike | Halt new BUYs | Crisis protection |
| Regime → "crisis" | Review all positions | Risk management |
| Earnings surprise (>5%) | Flag for review | May invalidate thesis |

**NOT reacting to**:
- Normal intraday price swings
- Minor news headlines
- Short-term momentum shifts

---

## Data Freshness & Coherence

> **Critical Principle**: The agent can only make good decisions if its data accurately represents **current market reality**. Stale data → wrong decisions → losses.

### The Freshness Problem

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    DATA FRESHNESS TIMELINE                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  DATA TYPE          UPDATE FREQ       VALID FOR        STALENESS RISK      │
│  ─────────          ───────────       ─────────        ──────────────      │
│                                                                             │
│  Composite Scores   Weekly (Sun)      7 days           HIGH after 3 days   │
│  Sentiment          Weekly (Sun)      7 days           HIGH (news moves)   │
│  Fundamentals       Quarterly         90 days          LOW                  │
│  Technical          Weekly            7 days           MEDIUM               │
│  Prices             Real-time (IBKR)  Minutes          CRITICAL if stale   │
│  VIX                Real-time         Hours            HIGH in volatility  │
│  HMM Regime         Daily             24 hours         MEDIUM               │
│  Insider Data       Weekly            14 days          LOW                  │
│  Sector Trends      Weekly            7 days           MEDIUM               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Data Coherence Requirements

**All signals must be temporally aligned** — the agent should not mix:
- Monday's scores with Friday's prices
- Last week's sentiment with this week's regime
- Old VIX with new positions

```python
class DataCoherenceValidator:
    """Ensure all data is from compatible time windows."""
    
    MAX_SCORE_AGE_DAYS = 7
    MAX_REGIME_AGE_HOURS = 24
    MAX_PRICE_AGE_MINUTES = 15  # During market hours
    
    def validate_context(self, context: AgentContext) -> ValidationResult:
        errors = []
        warnings = []
        
        # 1. Score freshness
        score_age = (now() - context.scores_updated_at).days
        if score_age > self.MAX_SCORE_AGE_DAYS:
            errors.append(f"Scores are {score_age} days old (max: {self.MAX_SCORE_AGE_DAYS})")
        elif score_age > 3:
            warnings.append(f"Scores are {score_age} days old — confidence reduced")
        
        # 2. Regime freshness
        regime_age = (now() - context.regime_updated_at).total_seconds() / 3600
        if regime_age > self.MAX_REGIME_AGE_HOURS:
            errors.append(f"HMM regime is {regime_age:.1f}h old (max: {self.MAX_REGIME_AGE_HOURS})")
        
        # 3. Price freshness (critical during market hours)
        if is_market_open():
            price_age = (now() - context.prices_updated_at).total_seconds() / 60
            if price_age > self.MAX_PRICE_AGE_MINUTES:
                errors.append(f"Prices are {price_age:.0f}min old (max: {self.MAX_PRICE_AGE_MINUTES})")
        
        # 4. Cross-source coherence
        time_spread = max(context.all_timestamps) - min(context.all_timestamps)
        if time_spread > timedelta(hours=24):
            warnings.append(f"Data sources span {time_spread} — may be inconsistent")
        
        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            confidence_multiplier=self._calculate_confidence(score_age, regime_age)
        )
    
    def _calculate_confidence(self, score_age_days: int, regime_age_hours: float) -> float:
        """Reduce confidence as data ages."""
        base = 1.0
        
        # Score decay: -5% per day after day 2
        if score_age_days > 2:
            base *= max(0.7, 1 - 0.05 * (score_age_days - 2))
        
        # Regime decay: -10% per 12 hours after hour 12
        if regime_age_hours > 12:
            base *= max(0.8, 1 - 0.1 * ((regime_age_hours - 12) / 12))
        
        return base
```

### Freshness Metadata Schema

Every data point must carry freshness metadata:

```python
@dataclass
class FreshnessMetadata:
    source: str                    # "pipeline", "ibkr", "vix_service"
    fetched_at: datetime           # When we got the data
    source_timestamp: datetime     # When source generated it
    valid_until: datetime          # Expiry time
    confidence: float              # 0-1, decays with age
    
@dataclass  
class ScoredStock:
    ticker: str
    composite_score: float
    signal: str
    
    # Freshness
    freshness: FreshnessMetadata
    
    def is_valid(self) -> bool:
        return datetime.now() < self.freshness.valid_until
    
    def adjusted_score(self) -> float:
        """Score adjusted for staleness — moves toward neutral (50) as data ages."""
        age_factor = self.freshness.confidence
        return self.composite_score * age_factor + 50 * (1 - age_factor)
```

### Pipeline Health Monitoring

The agent must **refuse to act** on stale data:

```python
class AgentHealthCheck:
    """Pre-flight check before any trading decision."""
    
    def check_pipeline_health(self) -> HealthStatus:
        checks = {
            "scores_fresh": self._check_scores_freshness(),
            "regime_fresh": self._check_regime_freshness(),
            "prices_available": self._check_price_feed(),
            "ibkr_connected": self._check_ibkr_connection(),
            "vix_current": self._check_vix_freshness(),
        }
        
        critical_failures = [k for k, v in checks.items() if not v and k in CRITICAL_CHECKS]
        
        if critical_failures:
            return HealthStatus(
                healthy=False,
                action="HALT",  # Do not trade
                reason=f"Critical data stale: {critical_failures}"
            )
        
        warnings = [k for k, v in checks.items() if not v]
        if warnings:
            return HealthStatus(
                healthy=True,
                action="PROCEED_WITH_CAUTION",
                reason=f"Non-critical warnings: {warnings}",
                confidence_reduction=0.2
            )
        
        return HealthStatus(healthy=True, action="PROCEED", confidence_reduction=0)
```

### Freshness-Aware Decision Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                 FRESHNESS-AWARE AGENT LOOP                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. HEALTH CHECK                                                            │
│     ├── Are scores < 7 days old?           → If NO: HALT                   │
│     ├── Is HMM regime < 24 hours old?      → If NO: HALT                   │
│     ├── Are prices < 15 min old?           → If NO: HALT (market hours)    │
│     └── Is VIX current?                    → If NO: Use last known + warn  │
│                                                                             │
│  2. CONFIDENCE ADJUSTMENT                                                   │
│     ├── Score age 0-2 days: confidence = 100%                              │
│     ├── Score age 3-4 days: confidence = 90%                               │
│     ├── Score age 5-6 days: confidence = 80%                               │
│     └── Score age 7+ days:  confidence = HALT                              │
│                                                                             │
│  3. COHERENCE CHECK                                                         │
│     ├── All timestamps within 24h window?  → If NO: WARN                   │
│     └── Price vs Score direction match?    → If NO: FLAG for LLM review    │
│                                                                             │
│  4. PROCEED WITH ADJUSTED CONFIDENCE                                        │
│     └── Position size *= confidence_multiplier                              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Recommended Pipeline Schedule

To maintain data freshness:

| Component | Current | Recommended | Rationale |
|-----------|---------|-------------|-----------|
| **Full Pipeline** | Sunday 6pm | Sunday 6pm | Weekly scores |
| **HMM Regime** | Daily 6am | Daily 6am | Market regime |
| **VIX Fetch** | On-demand | Every 4 hours | Fear gauge |
| **Price Sync** | On-demand | Real-time via IBKR | Execution prices |
| **Insider Data** | Weekly | Weekly | Slow-moving signal |

### Database: Freshness Tracking Table

```sql
CREATE TABLE data_freshness (
    id SERIAL PRIMARY KEY,
    data_type VARCHAR(50) NOT NULL,  -- 'scores', 'regime', 'vix', etc.
    last_updated TIMESTAMPTZ NOT NULL,
    valid_until TIMESTAMPTZ NOT NULL,
    source VARCHAR(100),
    record_count INT,
    status VARCHAR(20) DEFAULT 'valid',  -- 'valid', 'stale', 'error'
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for quick freshness checks
CREATE INDEX idx_freshness_type_updated ON data_freshness(data_type, last_updated DESC);

-- Example query: Is scores data fresh?
SELECT 
    data_type,
    last_updated,
    valid_until,
    CASE WHEN valid_until > NOW() THEN 'FRESH' ELSE 'STALE' END as status,
    EXTRACT(EPOCH FROM (NOW() - last_updated)) / 3600 as hours_old
FROM data_freshness
WHERE data_type = 'scores'
ORDER BY last_updated DESC
LIMIT 1;
```

### API: Freshness Endpoint

```
GET /api/v1/data/freshness
Response:
{
  "overall_status": "healthy",
  "components": {
    "scores": {
      "last_updated": "2026-02-14T18:00:00Z",
      "age_hours": 23.5,
      "status": "fresh",
      "valid_until": "2026-02-21T18:00:00Z"
    },
    "regime": {
      "last_updated": "2026-02-14T06:00:00Z",
      "age_hours": 11.5,
      "status": "fresh",
      "current_value": "normal"
    },
    "vix": {
      "last_updated": "2026-02-14T17:30:00Z",
      "age_hours": 0.2,
      "status": "fresh",
      "current_value": 15.2
    }
  },
  "agent_can_trade": true,
  "confidence_multiplier": 0.95
}
```

### Key Principle: "No Fresh Data, No Trade"

The agent must **never** trade on stale data. When data is stale:

1. **HALT** — Do not execute any trades
2. **NOTIFY** — Alert user that agent is paused
3. **DIAGNOSE** — Log which data source is stale
4. **RETRY** — Attempt to refresh the data
5. **ESCALATE** — If refresh fails, require manual intervention

This ensures the agent's decisions always reflect **current market reality**, not historical artifacts.

---

## Core Challenges

### 1. **Signal Timing Mismatch**
- Composite scores update **weekly** (pipeline runs)
- Market prices change **real-time**
- How to bridge batch insights with real-time execution?

### 2. **Multi-Signal Coherence**
- 6+ signal types (fundamental, sentiment, technical, macro, crowd wisdom, sector)
- Signals may conflict (e.g., good fundamentals but negative sentiment)
- How to synthesize into unified trading thesis?

### 3. **Position Sizing**
- Not just "BUY AAPL" but "BUY $X of AAPL"
- Kelly Criterion? Mean-Variance Optimization? Risk Parity?
- How much of portfolio to risk on each trade?

### 4. **Portfolio-Level Optimization**
- Individual stock decisions must consider overall portfolio
- Correlation, concentration, sector exposure
- Rebalancing frequency and triggers

### 5. **Risk Management Integration**
- We have Phase 1-3 risk modules (stop-loss, VaR, HMM regimes, Claude analyzer)
- How does agent respect these constraints?
- When to override vs when to follow?

### 6. **User Preference Alignment**
- Different users have different risk tolerances
- Aggressive vs conservative modes
- How to parameterize agent behavior?

### 7. **Real-Time Decision Making**
- Price moves can invalidate week-old signals
- Intraday events (earnings, news) need fast response
- How to balance conviction vs reactivity?

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                     AUTONOMOUS TRADING AGENT                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │   OBSERVER   │  │   REASONER   │  │   EXECUTOR   │              │
│  │              │  │              │  │              │              │
│  │ • Scores     │  │ • Synthesis  │  │ • Order Gen  │              │
│  │ • Prices     │  │ • Strategy   │  │ • Risk Check │              │
│  │ • Portfolio  │  │ • Allocation │  │ • IBKR Send  │              │
│  │ • Risk State │  │ • Sizing     │  │ • Confirm    │              │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘              │
│         │                 │                 │                       │
│         └────────────┬────┴────────┬────────┘                       │
│                      │             │                                │
│              ┌───────▼─────────────▼───────┐                        │
│              │      MEMORY & CONTEXT       │                        │
│              │  • Trade History            │                        │
│              │  • Decision Logs            │                        │
│              │  • Performance Tracking     │                        │
│              │  • Market Context           │                        │
│              └─────────────────────────────┘                        │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│                        USER PREFERENCES                             │
│  Risk Tolerance │ Max Drawdown │ Sector Limits │ Trading Hours     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Module Breakdown

### Module 1: Observer (State Aggregation)

**Responsibility**: Collect and normalize all available signals into unified state representation.

```python
class AgentState:
    # Portfolio State
    holdings: Dict[str, Position]      # Current positions
    cash: float                        # Available cash
    total_value: float                 # Portfolio value
    daily_pnl: float                   # Today's P&L
    
    # Signal State (per stock)
    scores: Dict[str, CompositeScore]  # Latest composite scores
    signals: Dict[str, Signal]         # BUY/HOLD/SELL
    score_changes: Dict[str, float]    # Week-over-week delta
    
    # Market Context
    vix: float                         # Current VIX
    regime: str                        # HMM regime (low_vol/normal/high_vol/crisis)
    sector_trends: Dict[str, float]    # Sector momentum
    
    # Risk Metrics
    portfolio_var: float               # 95% 1-day VaR
    sector_concentration: Dict[str, float]
    correlation_matrix: np.ndarray
    
    # Crowd Wisdom
    smart_money_picks: List[str]       # Insider buying signals
    
    # Time Context
    market_hours: bool                 # Is market open?
    days_since_last_trade: int
    earnings_upcoming: Dict[str, date]
```

### Module 2: Reasoner (Strategy Engine)

**Responsibility**: Synthesize signals into actionable trading thesis.

**Key Functions**:
1. **Signal Aggregation**: Weighted combination of all signals
2. **Conflict Resolution**: When signals disagree, how to resolve?
3. **Opportunity Ranking**: Which stocks deserve capital allocation?
4. **Rebalancing Triggers**: When to act vs wait?

```python
class TradingThesis:
    action: Literal["BUY", "SELL", "HOLD"]
    ticker: str
    conviction: float  # 0-1
    rationale: str     # Human-readable explanation
    
    # Supporting signals
    score: float
    signal_agreement: float  # How many signals agree?
    risk_adjusted: bool      # Passed risk checks?
    
    # Sizing hints
    suggested_size: float    # % of portfolio
    max_size: float          # Risk limit
```

### Module 3: Allocator (Position Sizing)

**Responsibility**: Determine exact dollar amounts for each trade.

**Approaches**:
1. **Kelly Criterion**: Optimal sizing based on edge and odds
2. **Risk Parity**: Equal risk contribution from each position
3. **Mean-Variance (Markowitz)**: Classic portfolio optimization
4. **Conviction-Weighted**: Size based on signal strength
5. **Volatility Targeting**: Size inversely to volatility

```python
class AllocationEngine:
    def calculate_position_size(
        self,
        thesis: TradingThesis,
        portfolio: Portfolio,
        risk_budget: float,       # Max loss acceptable
        conviction: float,        # 0-1 confidence
        volatility: float,        # Stock's realized vol
    ) -> float:
        """Returns dollar amount to allocate"""
        pass
```

### Module 4: Risk Gate (Pre-Trade Checks)

**Responsibility**: Validate proposed trades against risk limits.

```python
class RiskGate:
    def check_trade(self, trade: ProposedTrade) -> RiskCheckResult:
        checks = [
            self.check_position_limit(trade),      # Max 10% per stock
            self.check_sector_concentration(trade), # Max 30% per sector
            self.check_correlation(trade),          # Avoid clustered risk
            self.check_var_impact(trade),           # Post-trade VaR
            self.check_regime_appropriate(trade),   # Crisis mode limits
            self.check_drawdown_headroom(trade),    # Max drawdown limit
        ]
        return RiskCheckResult(
            approved=all(c.passed for c in checks),
            warnings=[c for c in checks if not c.passed],
            adjustments=self.suggest_adjustments(checks)
        )
```

### Module 5: Executor (Order Management)

**Responsibility**: Send orders to IBKR with proper execution logic.

```python
class OrderExecutor:
    def execute(self, trade: ApprovedTrade) -> OrderResult:
        # 1. Pre-execution check (prices moved?)
        current_price = self.get_quote(trade.ticker)
        if self.price_stale(trade, current_price):
            return self.re_evaluate(trade)
        
        # 2. Order type selection
        order = self.create_order(trade)  # Limit vs Market
        
        # 3. Submit to IBKR
        result = self.ibkr.place_order(order)
        
        # 4. Monitor fill
        fill = self.await_fill(result)
        
        # 5. Log and confirm
        self.log_trade(fill)
        return fill
```

### Module 6: Memory (Context & Learning)

**Responsibility**: Track decisions and outcomes for improvement.

```python
class AgentMemory:
    # Decision log
    decisions: List[Decision]      # What we decided and why
    
    # Trade outcomes
    trades: List[TradeOutcome]     # Actual fills and P&L
    
    # Performance tracking
    daily_returns: pd.Series
    benchmark_alpha: float
    sharpe_ratio: float
    
    # Pattern recognition
    regime_performance: Dict[str, float]  # How we perform in each regime
    sector_performance: Dict[str, float]  # Which sectors we're good at
    
    def learn(self):
        """Analyze past decisions to improve future ones"""
        pass
```

---

## State & Signal Integration

### Current Signals Available

| Signal | Source | Update Frequency | Weight (Current) |
|--------|--------|------------------|------------------|
| Fundamental | Backend Scoring | Weekly | 35% |
| Sentiment | Claude/News | Weekly | 25% |
| Technical | Price/Volume | Weekly | 20% |
| Macro | VIX/Rates | Weekly | 20% |
| Crowd Wisdom | Reddit/Insider | Weekly | Boost |
| Sector Momentum | Sector Analysis | Weekly | Context |
| HMM Regime | Risk Module | Daily | Filter |

### Signal Synthesis Strategy

```
                    ┌─────────────────────────┐
                    │   COMPOSITE SCORE (0-100)│
                    │   Weekly from pipeline   │
                    └───────────┬─────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        │                       │                       │
        ▼                       ▼                       ▼
┌───────────────┐      ┌───────────────┐      ┌───────────────┐
│ PRICE ACTION  │      │ RISK OVERLAY  │      │ MARKET REGIME │
│ Real-time adj │      │ Stop distance │      │ HMM state     │
│ Momentum      │      │ VaR limit     │      │ VIX level     │
└───────┬───────┘      └───────┬───────┘      └───────┬───────┘
        │                       │                       │
        └───────────────────────┼───────────────────────┘
                                │
                                ▼
                    ┌─────────────────────────┐
                    │   TRADING DECISION      │
                    │   Action + Size + Time  │
                    └─────────────────────────┘
```

---

## Decision Framework

### When to BUY

```python
def should_buy(state: AgentState, ticker: str) -> BuyDecision:
    score = state.scores[ticker]
    
    # Strong conviction conditions
    strong_buy = (
        score.composite >= 75 and
        score.signal == "BUY" and
        state.regime in ["low_vol", "normal"] and
        ticker not in state.holdings and
        state.sector_concentration[score.sector] < 0.25
    )
    
    # Opportunistic buy conditions
    opportunistic = (
        score.composite >= 65 and
        score.delta_week > 5 and  # Improving
        state.smart_money_picks.includes(ticker) and
        state.vix < 25
    )
    
    return BuyDecision(
        should_buy=strong_buy or opportunistic,
        conviction=score.composite / 100,
        thesis=f"Score {score.composite}, signal {score.signal}"
    )
```

### When to SELL

```python
def should_sell(state: AgentState, ticker: str) -> SellDecision:
    position = state.holdings[ticker]
    score = state.scores[ticker]
    
    # Mandatory sell conditions
    must_sell = (
        score.signal == "SELL" or
        score.composite < 40 or
        position.stop_loss_triggered or
        state.regime == "crisis" and position.unrealized_pnl < 0
    )
    
    # Profit taking conditions
    take_profit = (
        position.unrealized_pnl_pct > 20 and
        score.delta_week < -3  # Score declining
    )
    
    # Rebalancing conditions
    rebalance = (
        state.sector_concentration[score.sector] > 0.30 or
        position.weight > 0.12  # Over 12% of portfolio
    )
    
    return SellDecision(
        should_sell=must_sell or take_profit,
        partial_sell=rebalance,
        reason=determine_reason(must_sell, take_profit, rebalance)
    )
```

### Decision Frequency

| Trigger | Action | Frequency |
|---------|--------|-----------|
| Score Update | Full portfolio review | Weekly |
| Price Alert | Re-evaluate affected | Real-time |
| Stop Loss Hit | Execute sell | Real-time |
| Regime Change | Risk adjustment | Daily |
| VIX Spike | Defensive posture | Real-time |
| Earnings Event | Hold/Re-evaluate | Pre-market |

---

## Position Sizing & Risk Management

### Kelly Criterion (Simplified)

```python
def kelly_size(
    win_rate: float,      # Historical win rate for similar signals
    win_loss_ratio: float, # Avg win / Avg loss
    confidence: float,     # 0-1, multiply Kelly by this
) -> float:
    """Returns fraction of bankroll to bet"""
    kelly = (win_rate * win_loss_ratio - (1 - win_rate)) / win_loss_ratio
    
    # Half Kelly for conservatism
    return kelly * 0.5 * confidence
```

### Risk Parity Approach

```python
def risk_parity_weight(
    stock_vol: float,       # Stock's annualized volatility
    target_portfolio_vol: float,  # e.g., 15%
    num_positions: int,
) -> float:
    """Equal risk contribution sizing"""
    individual_vol_budget = target_portfolio_vol / np.sqrt(num_positions)
    weight = individual_vol_budget / stock_vol
    return min(weight, 0.10)  # Cap at 10%
```

### Integration with Risk Module

```python
def apply_risk_constraints(
    proposed_size: float,
    ticker: str,
    state: AgentState,
) -> float:
    # 1. Position limit
    size = min(proposed_size, state.risk_settings.max_position_pct)
    
    # 2. Sector limit
    sector = state.scores[ticker].sector
    sector_headroom = state.risk_settings.max_sector_pct - state.sector_concentration[sector]
    size = min(size, sector_headroom)
    
    # 3. VaR limit
    marginal_var = calculate_marginal_var(ticker, size, state.portfolio)
    if state.portfolio_var + marginal_var > state.risk_settings.max_var:
        size = scale_to_var_limit(size, marginal_var, state)
    
    # 4. Regime adjustment
    if state.regime == "high_vol":
        size *= 0.7
    elif state.regime == "crisis":
        size *= 0.3
    
    return size
```

---

## Execution Layer

### Order Type Selection

```python
def select_order_type(trade: ProposedTrade, state: AgentState) -> OrderType:
    # High conviction + good liquidity = Market order
    if trade.conviction > 0.8 and trade.avg_volume > 1_000_000:
        return OrderType.MARKET
    
    # Moderate conviction = Limit at midpoint
    if trade.conviction > 0.6:
        return OrderType.LIMIT_MIDPOINT
    
    # Lower conviction = Limit at favorable price
    return OrderType.LIMIT_PASSIVE
```

### Execution Timing

```python
def optimal_execution_time(trade: ProposedTrade) -> ExecutionWindow:
    # Avoid first 30 min (volatility)
    # Avoid last 30 min (MOC orders)
    # Prefer 10:00-11:30 or 14:00-15:30
    
    if trade.urgency == "high":
        return ExecutionWindow.IMMEDIATE
    
    return ExecutionWindow.OPTIMAL_HOURS
```

---

## User Preference Alignment

### Risk Profile Configuration

```python
class UserRiskProfile:
    # Core parameters
    risk_tolerance: Literal["conservative", "moderate", "aggressive"]
    max_drawdown_pct: float  # e.g., 10%, 15%, 20%
    target_return_pct: float  # Annual target
    
    # Position limits
    max_position_pct: float  # 5%, 8%, 10%
    max_sector_pct: float    # 25%, 30%, 35%
    max_positions: int       # 10, 20, 30
    
    # Trading behavior
    trading_frequency: Literal["passive", "active", "hyperactive"]
    rebalancing_threshold: float  # Drift before rebalance
    
    # Asset preferences
    excluded_sectors: List[str]
    esg_filter: bool
    min_market_cap: float
```

### Profile Templates

| Profile | Max DD | Max Position | Trades/Week | Target Return |
|---------|--------|--------------|-------------|---------------|
| Conservative | 10% | 5% | 1-2 | 8-12% |
| Moderate | 15% | 8% | 3-5 | 12-18% |
| Aggressive | 25% | 12% | 5-10 | 20-30% |

---

## iOS App Integration

> **Key Principle**: The agent runs on the backend; the iOS app provides visibility, control, and override capability.

### User Experience Modes

| Mode | Description | Agent Behavior |
|------|-------------|----------------|
| **Manual** (Default) | User makes all decisions | Agent suggests, doesn't act |
| **Supervised** | Agent proposes, user approves | Push notification → tap to approve/reject |
| **Autonomous** | Agent acts, user monitors | Agent executes, user can override |

### New iOS Views Required

#### 1. Agent Dashboard (`AgentDashboardView.swift`)
```
┌─────────────────────────────────────────────────────────┐
│  🤖 SIGIL AGENT                              [Settings] │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Status: ● ACTIVE                                       │
│  Mode: Supervised                                       │
│  Last Action: 2h ago — BUY AAPL $5,000                 │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │  THIS WEEK                                      │   │
│  │  Trades: 3 │ P&L: +$1,234 │ Win Rate: 67%      │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  PENDING ACTIONS (2)                                    │
│  ┌─────────────────────────────────────────────────┐   │
│  │  BUY MSFT $3,000                    [✓] [✗]    │   │
│  │  Score: 82, Conviction: 0.78                    │   │
│  └─────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────┐   │
│  │  SELL TSLA (partial)                [✓] [✗]    │   │
│  │  Stop-loss triggered at -8%                     │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  [View Agent History]                                   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

#### 2. Agent History (`AgentHistoryView.swift`)
- Chronological list of all agent decisions
- Filter by: action type, ticker, date range
- Each entry shows: decision + rationale + outcome

#### 3. Agent Settings (`AgentSettingsView.swift`)
- Mode selector (Manual / Supervised / Autonomous)
- Risk profile (Conservative / Moderate / Aggressive)
- Trading limits (max per trade, daily limit)
- Sector exclusions
- Pause/Resume agent toggle
- Emergency stop button

### API Endpoints for iOS

```
# Agent state
GET /api/v1/agent/status
  → {mode, active, last_action, pending_count}

# Pending decisions (for approval)
GET /api/v1/agent/pending
  → [{id, ticker, action, amount, rationale, confidence}]

POST /api/v1/agent/pending/{id}/approve
POST /api/v1/agent/pending/{id}/reject

# Agent history
GET /api/v1/agent/history?limit=50
  → [{timestamp, ticker, action, amount, outcome, rationale}]

# Agent control
POST /api/v1/agent/pause
POST /api/v1/agent/resume
POST /api/v1/agent/emergency-stop

# Agent settings
GET /api/v1/agent/settings
PUT /api/v1/agent/settings
```

### Push Notifications

| Event | Notification | iOS Action |
|-------|--------------|------------|
| Pending approval | "Agent wants to BUY AAPL" | Tap → approve/reject |
| Trade executed | "Bought AAPL at $185.50" | Tap → view details |
| Stop-loss triggered | "Sold TSLA (stop-loss -8%)" | Tap → view portfolio |
| Weekly summary | "Agent: +3.2% this week" | Tap → agent dashboard |
| Agent paused | "Agent paused: VIX > 30" | Tap → settings |

---

## Real-Time vs Batch Considerations

### The Core Tension

```
BATCH (Weekly Scores)           REAL-TIME (Prices/Events)
        │                               │
        │  ┌─────────────────────┐      │
        └──┤  HOW TO RECONCILE?  ├──────┘
           └─────────────────────┘
```

### Proposed Solution: Layered Decision Making

```
Layer 1: STRATEGIC (Weekly)
├── Run full pipeline (scores)
├── Generate target portfolio
├── Set position targets
└── Create trading queue

Layer 2: TACTICAL (Daily)
├── Check regime (HMM)
├── Adjust for VIX
├── Prioritize queue
└── Set daily limits

Layer 3: EXECUTION (Real-time)
├── Monitor prices
├── Execute when favorable
├── Respect stop-losses
└── React to events
```

### Score Staleness Handling

```python
def adjust_for_staleness(score: float, days_old: int) -> float:
    """Decay confidence in older scores"""
    if days_old <= 2:
        return score  # Fresh enough
    
    # Linear decay: lose 2% confidence per day after 2 days
    decay = min((days_old - 2) * 0.02, 0.20)
    
    # Move score toward neutral (50) as it ages
    return score * (1 - decay) + 50 * decay
```

### Real-Time Overrides

Events that can override weekly signals:
1. **Earnings surprise** (>5% move) → Re-evaluate immediately
2. **VIX spike** (>30) → Reduce exposure
3. **Stop-loss triggered** → Execute regardless of signal
4. **News sentiment shift** (breaking news) → Flag for review
5. **Technical breakdown** (price < 20-day low on volume) → Warning

---

## Validation & Backtesting

> **Key Asset**: We already have a backtesting system! See `backend/src/backtest/` and `how_tos/BACKTESTING_TUTORIAL.md`.

### Existing Backtest Infrastructure

| Component | Location | Purpose |
|-----------|----------|---------|
| Backtest Engine | `src/backtest/engine.py` | Simulate trading over historical data |
| Historical Sentiment | `src/sentiment_historical/` | 30K+ scored headlines |
| CLI | `python3 -m src.backtest` | Run backtests |
| Reports | `backend/reports/` | Generated analysis |

### Validated Results (Jun-Nov 2019)

From `reports/backtest_report_2019_sentiment.md`:

| Metric | Sigil Agent | SPY | Alpha |
|--------|-------------|-----|-------|
| Return | +20.85% | +15.56% | **+5.29%** |
| Sharpe | 4.42 | — | — |
| Max Drawdown | -6.26% | — | — |

### Risk-Managed Backtest (with stop-losses)

From `reports/backtest_risk_managed_2019.md`:

| Metric | Risk-Managed | Naive | Change |
|--------|--------------|-------|--------|
| Return | +22.92% | +20.85% | +2.07% |
| Sharpe | 5.34 | 4.42 | +0.92 |
| Stop-losses triggered | 5 | 0 | — |

### Agent Validation Strategy

```
┌─────────────────────────────────────────────────────────────────────┐
│                    VALIDATION PIPELINE                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  PHASE 1: BACKTEST (Historical)                                    │
│  ─────────────────────────────                                     │
│  • Run agent logic on 2019-2023 data                               │
│  • Compare vs naive score-following                                │
│  • Verify risk controls work                                       │
│  • Minimum: Alpha > 0, Max DD < 20%                                │
│                                                                     │
│  PHASE 2: PAPER TRADING (Live simulation)                          │
│  ────────────────────────────────────────                          │
│  • Connect to IBKR paper account (DUP526287)                       │
│  • Run for 4-8 weeks                                               │
│  • Compare real execution vs backtest                              │
│  • Identify slippage, timing issues                                │
│                                                                     │
│  PHASE 3: SMALL LIVE (Real money, limited)                         │
│  ─────────────────────────────────────────                         │
│  • 10% of portfolio under agent control                            │
│  • Manual approval required                                        │
│  • Run for 4-12 weeks                                              │
│  • Scale up only if metrics hold                                   │
│                                                                     │
│  PHASE 4: FULL LIVE (Real money, autonomous)                       │
│  ────────────────────────────────────────────                      │
│  • Gradual increase to 50%, then 100%                              │
│  • Continuous monitoring                                           │
│  • Kill switch always available                                    │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Backtest Commands

```bash
# Run backtest with current scoring logic
cd backend
python3 -m src.backtest run --period 2019 --output reports/

# Generate comparison report
python3 -m src.backtest report --id bt_xxx --format html

# Test agent decision logic (dry run)
python3 -m src.agent simulate --period 2023 --mode rule-based
```

---

## Regulatory & Compliance

> **Critical**: From `01_PRD.md` — this app is NOT financial advice.

### Required Disclosures

| Disclosure | Where | Text |
|------------|-------|------|
| Not advice | Onboarding, Settings | "Sigil provides information, not financial advice." |
| Risk of loss | Before enabling agent | "You can lose money. Past performance ≠ future results." |
| Broker | Settings | "Trades executed by Interactive Brokers." |
| Autonomous | Before enabling | "Agent will trade on your behalf. You remain responsible." |

### Agent-Specific Compliance

| Concern | Mitigation |
|---------|------------|
| **Unauthorized trading** | User must explicitly enable agent mode |
| **Runaway losses** | Max daily loss limit, emergency stop |
| **Insider trading** | Agent uses only public data |
| **Market manipulation** | 850 stocks, no concentrated positions |
| **Audit trail** | Every decision logged with timestamp + rationale |

### Legal Considerations

1. **Terms of Service**: Must cover autonomous trading
2. **User Agreement**: Explicit consent for agent trades
3. **Kill Switch**: User can disable instantly
4. **Liability**: User accepts responsibility for agent actions
5. **IBKR Compliance**: All trades via regulated broker

### SEC/FINRA Notes

- App is a **tool**, not a registered investment advisor
- No personalized advice (same algorithm for all users)
- Clear that user makes final decision (even if delegated to agent)

---

## Success Metrics

> **Note**: Unlike code generation agents (pass^K, pass@K), trading agents are evaluated on **financial performance** and **risk control** over time.

### Primary Objective

**Maximize risk-adjusted returns** subject to user-defined constraints.

```
Objective: max E[R] - λ * Var(R)
           ─────────────────────
           subject to:
             • Max Drawdown ≤ user_limit
             • Sector concentration ≤ 30%
             • Position size ≤ 10%
             • VaR ≤ portfolio_var_limit
```

### Financial Performance Metrics

| Metric | Formula | Target | Why It Matters |
|--------|---------|--------|----------------|
| **Cumulative Return** | (V_end - V_start) / V_start | Positive | Raw performance |
| **Alpha** | R_portfolio - R_benchmark | > 0% | Beat the market |
| **CAGR** | (V_end/V_start)^(1/years) - 1 | > 10% | Annualized growth |

### Risk-Adjusted Metrics

| Metric | Formula | Target | Why It Matters |
|--------|---------|--------|----------------|
| **Sharpe Ratio** | (R - Rf) / σ | > 1.5 | Return per unit risk |
| **Sortino Ratio** | (R - Rf) / σ_downside | > 2.0 | Penalizes downside only |
| **Calmar Ratio** | CAGR / Max Drawdown | > 1.0 | Return vs worst loss |
| **Information Ratio** | Alpha / Tracking Error | > 0.5 | Consistency of alpha |

### Risk Control Metrics

| Metric | Formula | Limit | Why It Matters |
|--------|---------|-------|----------------|
| **Max Drawdown** | (Peak - Trough) / Peak | < 20% | Worst-case loss |
| **VaR (95%, 1-day)** | Parametric VaR | < 2% of portfolio | Daily risk exposure |
| **Volatility** | Annualized σ | < 20% | Return variability |
| **Beta** | Cov(R, Rm) / Var(Rm) | 0.8 - 1.2 | Market sensitivity |

### Operational Metrics

| Metric | Target | Why It Matters |
|--------|--------|----------------|
| **Win Rate** | > 55% | More wins than losses |
| **Profit Factor** | Gross Profit / Gross Loss > 1.5 | Wins outweigh losses |
| **Avg Holding Period** | 5-30 days | Not churning |
| **Trades per Month** | 5-20 | Reasonable activity |
| **Turnover** | < 100% annually | Tax efficiency |

### User Trust Metrics (Supervised Mode)

| Metric | Target | Description |
|--------|--------|-------------|
| **Approval Rate** | > 80% | User agrees with agent proposals |
| **Override Rate** | < 10% | User changes agent decisions |
| **Time to Approve** | < 1 hour | Quick response to proposals |

### Dashboard Metrics (For User)

```
┌─────────────────────────────────────────────────────────┐
│  YOUR AGENT PERFORMANCE                                 │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Since Enabled: 47 days                                 │
│                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  Return      │  │  Alpha       │  │  Sharpe      │  │
│  │  +12.3%      │  │  +4.1%       │  │  1.82        │  │
│  │  ▲           │  │  vs S&P 500  │  │  ▲           │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  Max DD      │  │  Win Rate    │  │  Trades      │  │
│  │  -6.2%       │  │  62%         │  │  23          │  │
│  │  (limit 20%) │  │              │  │              │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### Backtesting Validation Thresholds

Before going live, agent must demonstrate:

| Metric | Minimum | Ideal |
|--------|---------|-------|
| Backtest Alpha | > 0% | > 3% |
| Sharpe Ratio | > 1.0 | > 1.5 |
| Max Drawdown | < 25% | < 15% |
| Win Rate | > 50% | > 55% |
| Profit Factor | > 1.2 | > 1.5 |

**Current backtest results (Jun-Nov 2019)**: Alpha +5.29%, Sharpe 4.42, Max DD -6.26% ✓

---

## Research & References

### Academic Papers

| Paper | Topic | Key Insight |
|-------|-------|-------------|
| "Deep Reinforcement Learning for Automated Stock Trading" | DRL Trading | PPO/A2C for portfolio management |
| "FinRL: A Deep Reinforcement Learning Library for Automated Stock Trading" | Library | Modular DRL framework |
| "Sentiment Analysis and Machine Learning in Finance" | Sentiment | NLP for trading signals |
| "The Kelly Criterion in Blackjack, Sports Betting, and the Stock Market" | Position Sizing | Optimal bet sizing theory |
| "Risk Parity Fundamentals" | Risk Parity | Equal risk contribution |
| "Volatility Targeting" | Vol Targeting | Dynamic leverage |

### GitHub Repositories

| Repo | Description | Stars | Link |
|------|-------------|-------|------|
| **FinRL** | DRL library for trading (PPO, A2C, DDPG) | 9k+ | https://github.com/AI4Finance-Foundation/FinRL |
| **FinGPT** | Open-source LLM for finance | 14k+ | https://github.com/AI4Finance-Foundation/FinGPT |
| **FinMem** | Long-term memory enhanced LLM trading | 500+ | https://github.com/pipiku915/FinMem-LLM-StockTrading |
| **QLib** | Quant platform by Microsoft | 15k+ | https://github.com/microsoft/qlib |
| **Alpaca Trade API** | Commission-free trading API | 1.5k+ | https://github.com/alpacahq/alpaca-trade-api-python |
| **zipline-reloaded** | Backtesting framework | 1k+ | https://github.com/stefan-jansen/zipline-reloaded |
| **vectorbt** | Vectorized backtesting | 4k+ | https://github.com/polakowo/vectorbt |
| **FreqTrade** | Crypto trading bot | 28k+ | https://github.com/freqtrade/freqtrade |
| **Jesse** | Advanced crypto trading | 5k+ | https://github.com/jesse-ai/jesse |
| **Trading Gym** | OpenAI Gym for trading | 1k+ | https://github.com/hackthemarket/gym-trading |
| **FinAgent** | LLM-based financial agent | 300+ | https://github.com/AI4Finance-Foundation/FinAgent |
| **TradingAgents** | Multi-agent trading system | 200+ | https://github.com/TauricResearch/TradingAgents |

### Key Frameworks & Platforms

| Platform | Use Case | Notes |
|----------|----------|-------|
| **Interactive Brokers API** | Live execution | We already have this (IBKR) |
| **QuantConnect** | Algo trading platform | Cloud backtesting + live |
| **Alpaca** | Commission-free API | Good for paper trading |
| **LangChain/LangGraph** | LLM agent orchestration | For reasoning layer |
| **AutoGen** | Multi-agent framework | Microsoft, debate patterns |
| **CrewAI** | Agent collaboration | Role-based agents |

### Relevant Concepts

| Concept | Description | Application |
|---------|-------------|-------------|
| **Kelly Criterion** | Optimal bet sizing | Position sizing |
| **Modern Portfolio Theory** | Mean-variance optimization | Portfolio construction |
| **Risk Parity** | Equal risk contribution | Diversification |
| **Black-Litterman** | Combine views with market | Signal integration |
| **Hierarchical Risk Parity** | Clustering + risk parity | Better diversification |
| **DDPG/PPO/A2C** | Policy gradient RL | Learning to trade |
| **Multi-Armed Bandits** | Exploration vs exploitation | Stock selection |
| **Monte Carlo Tree Search** | Planning under uncertainty | Trade sequencing |

### Books

- "Advances in Financial Machine Learning" - Marcos López de Prado
- "Machine Learning for Algorithmic Trading" - Stefan Jansen
- "Quantitative Trading" - Ernest P. Chan
- "Active Portfolio Management" - Grinold & Kahn
- "The Kelly Capital Growth Investment Criterion" - MacLean et al.

---

## Open Questions

### Technical

1. **How often should the agent "wake up"?**
   - Continuous monitoring vs scheduled checks?
   - Cost of real-time vs benefit?

2. **How to handle partial fills?**
   - Retry? Adjust quantity? Move on?

3. **What's the right number of positions?**
   - Too few = concentration risk
   - Too many = diluted alpha

4. **How to validate before going live?**
   - Paper trading duration?
   - Confidence threshold for live?

### Philosophical

5. **Should agent explain decisions in real-time?**
   - Transparency vs information overload

6. **Human oversight levels?**
   - Full auto vs approval required vs veto window?

7. **How to handle agent "mistakes"?**
   - Circuit breakers? Daily loss limits?

8. **Liability and regulatory considerations?**
   - Is this "advice"? Investment management?

---

## Phased Implementation Plan

### Phase 1: Observer + Memory (2-3 weeks)
- [ ] AgentState class with all signals
- [ ] State persistence (SQLite)
- [ ] Signal aggregation logic
- [ ] Decision logging framework
- [ ] Basic CLI for state inspection

### Phase 2: Reasoner (Strategy Engine) (3-4 weeks)
- [ ] Signal synthesis algorithms
- [ ] Opportunity ranking
- [ ] Buy/Sell decision framework
- [ ] Conflict resolution logic
- [ ] Backtesting integration

### Phase 3: Allocator (Position Sizing) (2-3 weeks)
- [ ] Kelly Criterion implementation
- [ ] Risk parity option
- [ ] Integration with Risk Module
- [ ] User preference weighting
- [ ] Size limit enforcement

### Phase 4: Executor (Order Management) (2-3 weeks)
- [ ] Order type selection
- [ ] IBKR order submission
- [ ] Fill monitoring
- [ ] Partial fill handling
- [ ] Trade confirmation logging

### Phase 5: Integration & Testing (3-4 weeks)
- [ ] End-to-end paper trading
- [ ] Performance tracking
- [ ] Alerting and monitoring
- [ ] User dashboard
- [ ] Safety controls (circuit breakers)

### Phase 6: Live Trading (Gradual)
- [ ] Small allocation live test
- [ ] Scaling up with confidence
- [ ] Continuous improvement loop

---

### Estimated Timeline

| Phase | Duration | Cumulative |
|-------|----------|------------|
| Phase 1 | 2-3 weeks | 3 weeks |
| Phase 2 | 3-4 weeks | 7 weeks |
| Phase 3 | 2-3 weeks | 10 weeks |
| Phase 4 | 2-3 weeks | 13 weeks |
| Phase 5 | 3-4 weeks | 17 weeks |
| Phase 6 | Ongoing | - |

**Total: ~4 months to paper trading, ~5 months to initial live**

---

## Next Steps

1. **Research deep dive**: Read FinRL, FinGPT papers in detail
2. **Prototype Observer**: Build AgentState class with current signals
3. **Define MVP scope**: What's the simplest version that adds value?
4. **User research**: What do users actually want from automation?
5. **Risk assessment**: Legal/regulatory considerations

---

*This document is a living brainstorm. Update as we learn more.*

**Last Updated**: 2026-02-14
**Author**: Blaze Neon 🔥
