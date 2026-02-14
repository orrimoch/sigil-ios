<img src="sigil_logo.jpg" alt="Sigil" width="240" />

# Agent Feature Mapping

**Purpose**: Verify every Sigil feature is used by the autonomous agent as a coherent algorithm.

---

## Backend Modules → Agent Role

| Module | Location | Agent Role | Status |
|--------|----------|------------|--------|
| **scoring** | `src/scoring/` | Primary signal (composite 0-100, BUY/HOLD/SELL) | ✅ Core input |
| **risk** | `src/risk/` | Constraints (VaR, stop-loss, HMM regime, position limits) | ✅ Core input |
| **crowd_wisdom** | `src/crowd_wisdom/` | Boost/penalty signals (insider, Reddit viral) | ✅ Core input |
| **analytics** | `src/analytics/` | Sector trends, momentum context | ✅ Core input |
| **ibkr** | `src/ibkr/` | Execution layer (orders, quotes, account) | ✅ Executor |
| **llm** | `src/llm/` | Reasoning layer (conflict resolution, explanations) | ✅ Reasoner |
| **backtest** | `src/backtest/` | Validation before live | ✅ Validation |
| **data** | `src/data/` | Price/fundamental data for context | ✅ Observer |
| **sentiment_historical** | `src/sentiment_historical/` | Training data for backtests | ✅ Validation |
| **trading** | `src/trading/` | Paper trading service | ✅ Executor |
| **alerts** | `src/alerts/` | User notifications of agent actions | ✅ Notification |
| **notifications** | `src/notifications/` | Push notification infrastructure | ✅ Notification |
| **scheduler** | `src/scheduler/` | Pipeline scheduling (agent trigger) | ✅ Trigger |
| **auth** | `src/auth/` | User identity + preferences | ✅ Foundation — agent knows WHO (user_id, risk_profile, IBKR creds) |
| **api** | `src/api/` | API routes | ✅ Foundation — agent exposes `/agent/*` + uses existing routes |
| **db** | `src/db/` | Database access | ✅ Foundation — agent stores decisions, reads scores, persists memory |

---

## Feature Spec → Agent Integration

### Module 1: Data Pipeline (F1.x)

| Feature | Agent Role | Integration |
|---------|------------|-------------|
| F1.1 Stock Universe | Define tradable universe | Agent only considers stocks in universe |
| F1.2 Price Data | Technical analysis input | Observer uses for price context |
| F1.3 Fundamental Data | Fundamental score input | Already in composite score |
| F1.4 News Data | Sentiment score input | Already in composite score |
| F1.5 Macro Data | Macro score input + VIX | HMM regime uses VIX |
| F1.6 Weekly Pipeline | **Agent trigger** | Agent runs after pipeline completes |

### Module 2: Scoring System (F2.x)

| Feature | Agent Role | Integration |
|---------|------------|-------------|
| F2.1 Fundamental Score | 35% of composite | Primary signal component |
| F2.2 Sentiment Score | 25% of composite | Primary signal component |
| F2.3 Technical Score | 20% of composite | Primary signal component |
| F2.4 Macro Score | 20% of composite | Primary signal component |
| F2.5 Composite Score | **Primary decision input** | BUY if ≥70, SELL if <40 |
| F2.6 Score Explainability | Agent explanation source | Agent cites score breakdown |

### Module 3-5: iOS App Core (F3.x-F5.x)

| Feature | Agent Role | Integration |
|---------|------------|-------------|
| F3.x Navigation | Display agent status | New "Agent" tab or dashboard |
| F4.1 Portfolio Summary | Agent reads state | Observer gets current holdings |
| F4.3 Top AI Picks | Agent's BUY candidates | Same list, agent acts on it |
| F5.3 Stock Detail | Agent explains decisions here | Link to agent rationale |

### Module 6: Trading (F6.x)

| Feature | Agent Role | Integration |
|---------|------------|-------------|
| F6.1 Order Entry | **Agent executes orders** | Executor submits via same API |
| F6.2 Paper Trading | Agent validation mode | Agent starts in paper |
| F6.3 Live Trading | Agent production mode | Agent graduates to live |
| F6.4 Order Status | Agent monitors fills | Executor tracks order status |

### Module 7: Portfolio (F7.x)

| Feature | Agent Role | Integration |
|---------|------------|-------------|
| F7.1 Holdings List | Agent reads positions | Observer gets holdings for sizing |
| F7.2 Performance Chart | Agent tracked here | Compare agent vs benchmark |
| F7.3 Sector Allocation | Sector limit constraint | Agent respects 30% sector max |

### Module 8: Settings (F8.x)

| Feature | Agent Role | Integration |
|---------|------------|-------------|
| F8.1 Account Settings | Agent preferences | Risk profile controls agent behavior |
| F8.2 IBKR Connection | Agent execution path | Agent uses same IBKR connection |
| F8.3 Paper/Live Toggle | Agent mode | Agent follows user's mode |
| **NEW: Agent Settings** | Agent control | Mode (Manual/Supervised/Auto), limits |

### Module 9: Notifications (F9.x)

| Feature | Agent Role | Integration |
|---------|------------|-------------|
| F9.1 Weekly Score | Agent trigger notification | "Agent reviewing new scores..." |
| F9.2 Trade Confirmation | Agent action notification | "Agent bought AAPL $5,000" |
| F9.3 Score Alert | Agent considers these | Agent may act on signal changes |

---

## Risk Module → Agent Constraints

| Risk Feature | Location | Agent Integration |
|--------------|----------|-------------------|
| **VaR Calculator** | `var_calculator.py` | Position sizing constraint |
| **Portfolio VaR** | `portfolio_var.py` | Total risk budget check |
| **HMM Regime** | `hmm_regime.py` | **Trading mode selector** |
| **Stop-Loss** | `stop_loss.py` | Exit trigger (mandatory sell) |
| **VIX Service** | `vix_service.py` | Regime input + fear gauge |
| **Claude Analyzer** | `claude_analyzer.py` | LLM risk assessment |
| **Position Limits** | `position_limits.py` | Max 10% per stock |
| **Sector Limits** | `sector_limits.py` | Max 30% per sector |
| **Pattern Memory** | `pattern_memory.py` | Learning from past trades |

---

## The Coherent Algorithm

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ONE COHERENT ALGORITHM                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  TRIGGER: Weekly Pipeline Completes (F1.6)                                  │
│           └── scheduler/pipeline.py runs                                    │
│                                                                             │
│  STEP 1: OBSERVE (gather all signals)                                       │
│  ─────────────────────────────────────                                      │
│  │                                                                          │
│  ├── scoring/          → composite_score, signal, sub-scores                │
│  ├── risk/hmm_regime   → current_regime (low_vol/normal/high_vol/crisis)    │
│  ├── risk/vix_service  → vix_level                                          │
│  ├── risk/var_*        → portfolio_var, per_stock_var                       │
│  ├── crowd_wisdom/     → insider_score, viral_score, smart_money_picks      │
│  ├── analytics/        → sector_trends, sector_momentum                     │
│  ├── portfolio/        → holdings, cash, sector_exposure                    │
│  └── ibkr/             → live_prices, account_info                          │
│                                                                             │
│  STEP 2: FILTER (apply hard constraints)                                    │
│  ───────────────────────────────────────                                    │
│  │                                                                          │
│  ├── IF regime == "crisis" → NO BUYs, consider defensive sells              │
│  ├── IF position > 10% → SKIP (position limit)                              │
│  ├── IF sector > 30% → SKIP (sector limit)                                  │
│  ├── IF cash < order_size → SKIP (insufficient funds)                       │
│  └── IF score < 70 → SKIP for BUY                                           │
│                                                                             │
│  STEP 3: RANK (prioritize candidates)                                       │
│  ─────────────────────────────────────                                      │
│  │                                                                          │
│  ├── Sort BUY candidates by: score DESC, crowd_wisdom_boost DESC            │
│  ├── Sort SELL candidates by: score ASC, stop_loss_triggered DESC           │
│  └── Apply regime multiplier (high_vol → fewer trades)                      │
│                                                                             │
│  STEP 4: SIZE (determine amounts)                                           │
│  ─────────────────────────────────                                          │
│  │                                                                          │
│  ├── Base size = user_risk_profile.position_pct (5-10%)                     │
│  ├── Adjust for conviction (score/100)                                      │
│  ├── Adjust for volatility (lower vol → bigger size)                        │
│  ├── Constrain by VaR budget                                                │
│  └── Constrain by sector headroom                                           │
│                                                                             │
│  STEP 5: REASON (LLM for complex cases)                                     │
│  ───────────────────────────────────────                                    │
│  │                                                                          │
│  ├── IF signals conflict → Claude resolves                                  │
│  ├── IF unusual pattern → Claude reviews                                    │
│  └── Generate human-readable rationale                                      │
│                                                                             │
│  STEP 6: EXECUTE (submit orders)                                            │
│  ─────────────────────────────────                                          │
│  │                                                                          │
│  ├── IF mode == "manual" → Store as recommendation, notify user             │
│  ├── IF mode == "supervised" → Queue for approval, notify user              │
│  ├── IF mode == "autonomous" → ibkr/service.py places order                 │
│  └── Log decision + rationale to agent_decisions table                      │
│                                                                             │
│  STEP 7: LEARN (track outcomes)                                             │
│  ─────────────────────────────────                                          │
│  │                                                                          │
│  ├── Monitor fills via ibkr/                                                │
│  ├── Track P&L per decision                                                 │
│  ├── Update pattern_memory (what worked in which regime)                    │
│  └── Feed into backtest for continuous validation                           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Gaps Identified

| Gap | Description | Action Needed |
|-----|-------------|---------------|
| **Agent Module** | No `src/agent/` folder exists yet | Create: observer.py, reasoner.py, executor.py |
| **Agent State Table** | No DB table for agent decisions | Add: agent_decisions, agent_memory tables |
| **Agent API Routes** | No `/agent/*` endpoints | Add routes in api/agent_routes.py |
| **iOS Agent UI** | No Agent tab/dashboard in app | Add AgentDashboardView.swift |
| **Agent Config** | No user-facing agent settings | Add to SettingsView.swift |

---

## Summary

**✅ All existing features ARE used by the agent**:
- Scoring → Primary signal
- Risk → Constraints + regime
- Crowd Wisdom → Boost signals  
- Sector Analysis → Context
- IBKR → Execution
- LLM → Reasoning
- Backtest → Validation

**🔨 What needs to be built**:
- `src/agent/` module (orchestrator)
- Database tables for agent state
- API endpoints for agent control
- iOS views for agent visibility

**The algorithm is coherent** — every feature has a clear role.
