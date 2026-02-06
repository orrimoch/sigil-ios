<img src="sigil_logo.jpg" alt="Sigil" width="240" />

# Backtesting Module Specification

**Date:** February 6, 2026  
**Version:** 2.0  
**Author:** PM Agent + Or Rim feedback  
**Status:** Approved  
**Priority:** P1 (Post-MVP Enhancement)

---

## Executive Summary

The Backtesting Module is an **internal analytics tool** that validates Sigil's scoring model by measuring historical predictive power. This is NOT a user-facing feature — it's for developers/founders to verify the model works before shipping.

**Approach:** Internal tooling first. User-facing backtesting can be added later if scores prove valuable.

### Key Questions We Answer

1. **Does Score = Returns?** — Do higher scores predict higher returns? (IC metric)
2. **How Fast Do Scores Decay?** — Should we refresh daily or weekly? (IC by day-of-week)
3. **What Are Optimal Thresholds?** — Is 70/50 the best entry/exit? (HPO with Optuna)
4. **Would You Have Made Money?** — Simulated P&L following the scores (CAGR, Sharpe)

---

## Data Strategy (A + C Approach)

### A) Retroactive Score Generation

Generate historical scores using point-in-time data:

| Component | Data Source | History Available |
|-----------|-------------|-------------------|
| Fundamental (35%) | FMP quarterly financials | 5+ years |
| Technical (20%) | yfinance daily OHLCV | 5+ years |
| Macro (20%) | FRED economic data | 5+ years |
| Sentiment (25%) | **Neutral (50)** for historical | N/A |

**Limitation:** Historical sentiment unavailable — use neutral baseline. Real sentiment tracked from Feb 2026 onward.

**Default: 1.5 years** (78 weeks) — sufficient for initial validation with free yfinance data.
**Optional: 5 years** — available if paid data source (FMP) is configured.

### C) Rolling Live Validation

Track real performance starting now:

| Period | Validation Type | Confidence |
|--------|-----------------|------------|
| Week 1-4 | Preliminary IC, hit rate | Low (wide CI) |
| Month 1-3 | Short-term validation | Medium |
| Month 3-12 | Meaningful statistics | High |
| Year 1+ | Robust validation | Publication-ready |

**Dashboard shows both:** Historical backtest (5yr) + Live performance (since launch)

---

## Module Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        BACKTESTING MODULE                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌────────────────┐    ┌────────────────┐    ┌────────────────┐        │
│  │   Historical   │───▶│    Backtest    │───▶│   Performance  │        │
│  │ Score Generator│    │     Engine     │    │    Analyzer    │        │
│  └────────────────┘    └────────────────┘    └────────────────┘        │
│          │                     │                     │                  │
│          ▼                     ▼                     ▼                  │
│  ┌────────────────┐    ┌────────────────┐    ┌────────────────┐        │
│  │  Data Store    │    │   Portfolio    │    │   Dashboard    │        │
│  │  (Persistence) │    │   Simulator    │    │    (iOS)       │        │
│  └────────────────┘    └────────────────┘    └────────────────┘        │
│          │                                           │                  │
│          ▼                                           ▼                  │
│  ┌────────────────┐                         ┌────────────────┐        │
│  │   HPO Engine   │                         │   IC Decay     │        │
│  │   (Optuna)     │                         │   Analyzer     │        │
│  └────────────────┘                         └────────────────┘        │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Foundation (4 weeks)

### F12.1 Historical Data Persistence
**Priority:** P0 (Blocker)  
**Effort:** 1 week  
**Dependencies:** None

Store all data needed for backtesting and future analysis.

**Requirements:**
- [ ] Store daily scores for all 677 stocks (append-only)
- [ ] Store weekly score snapshots with component breakdown
- [ ] Store daily portfolio snapshots (positions, NAV, cash)
- [ ] Store all executed trades (real + simulated)
- [ ] Implement data versioning (schema migrations)
- [ ] Auto-cleanup old raw data (keep aggregates)

**Storage Schema:**
```python
# score_history table
{
    "date": "2026-02-06",
    "ticker": "AAPL",
    "composite_score": 72,
    "fundamental_score": 68,
    "technical_score": 75,
    "sentiment_score": 71,
    "macro_score": 74,
    "signal": "BUY"
}

# backtest_results table
{
    "backtest_id": "bt_20260206_001",
    "params": {...},
    "metrics": {...},
    "equity_curve": [...],
    "created_at": "2026-02-06T10:00:00Z"
}
```

---

### F12.2 Historical Score Generator
**Priority:** P0  
**Effort:** 2 weeks  
**Dependencies:** F12.1

Generate point-in-time historical scores (no lookahead bias).

**Requirements:**
- [ ] Calculate fundamental scores using quarterly data with 60-day lag
- [ ] Calculate technical scores from historical OHLCV
- [ ] Calculate macro scores from FRED historical data
- [ ] Use neutral (50) for historical sentiment
- [ ] Generate 1.5 years of weekly scores for all 677 stocks (default)
- [ ] Optional: Support 5 years with paid data source
- [ ] Validate no lookahead bias (audit trail)
- [ ] Store generated scores in persistence layer

**Point-in-Time Rules:**
```
Score Date: 2024-03-15
├── Fundamentals: Use Q4 2023 (filed by ~Feb 28)
├── Technical: Use prices up to 2024-03-14
├── Macro: Use data released by 2024-03-14
└── Sentiment: Neutral (50) for historical
```

---

### F12.3 Basic Backtest Engine
**Priority:** P0  
**Effort:** 1.5 weeks  
**Dependencies:** F12.2

Execute simulated trades and track portfolio performance.

**Requirements:**
- [ ] Signal-based entry (BUY when score ≥ threshold)
- [ ] Signal-based exit (SELL when score < threshold)
- [ ] Equal-weight position sizing
- [ ] Configurable max positions (default: 10)
- [ ] Weekly rebalancing frequency
- [ ] Transaction costs (default: 0.1%)
- [ ] Slippage modeling (default: 0.1%)
- [ ] Track daily NAV, positions, cash
- [ ] Generate complete trade log

**Default Parameters:**
```python
DEFAULT_STRATEGY = {
    "entry_threshold": 70,
    "exit_threshold": 50,
    "max_positions": 10,
    "rebalance_freq": "weekly",
    "position_sizing": "equal_weight",
    "transaction_cost": 0.001,
    "slippage": 0.001,
    "initial_capital": 100000,
}
```

---

### F12.4 Performance Metrics Calculator
**Priority:** P0  
**Effort:** 1 week  
**Dependencies:** F12.3

Calculate all performance and validation metrics.

**Core Metrics:**

| Metric | Formula | Target |
|--------|---------|--------|
| Total Return | (End / Start) - 1 | — |
| CAGR | (1 + Return)^(1/years) - 1 | > SPY + 2% |
| Volatility | StdDev(daily returns) × √252 | < 25% |
| Sharpe Ratio | (Return - RiskFree) / Volatility | > 1.0 |
| Max Drawdown | Max peak-to-trough | < 25% |
| Win Rate | Winning trades / Total trades | > 55% |

**Score Validation Metrics:**

| Metric | Formula | Target |
|--------|---------|--------|
| Score IC | Corr(Score_t, Return_t+1) | > 0.05 |
| Hit Rate | BUY signals that beat SPY / Total BUYs | > 55% |
| Quintile Spread | Top 20% return - Bottom 20% return | > 10%/yr |

**Benchmark Comparison:**
- SPY (S&P 500) — primary benchmark
- QQQ (NASDAQ-100) — tech comparison
- Risk-free rate (3-month Treasury)

---

## Phase 2: Score Analysis (2 weeks)

### F12.5 IC Decay Analyzer
**Priority:** P1  
**Effort:** 1 week  
**Dependencies:** F12.4

Measure how predictive power decays over time to optimize refresh frequency.

**Requirements:**
- [ ] Calculate IC at day 1, 2, 3, 4, 5 after score generation
- [ ] Plot IC decay curve
- [ ] Statistical significance test for decay
- [ ] Recommend optimal refresh frequency
- [ ] Track IC decay over different market regimes

**Expected Output:**
```
Day of Week Analysis (1.5-year average):
├── Monday (Day 1):    IC = 0.072 ± 0.015
├── Tuesday (Day 2):   IC = 0.065 ± 0.014
├── Wednesday (Day 3): IC = 0.058 ± 0.016
├── Thursday (Day 4):  IC = 0.049 ± 0.018
└── Friday (Day 5):    IC = 0.041 ± 0.020

Recommendation: Refresh scores on Wednesday (IC drops below 0.05)
```

---

### F12.6 Walk-Forward Validation
**Priority:** P1  
**Effort:** 1 week  
**Dependencies:** F12.4

Prevent overfitting with proper out-of-sample testing.

**Methodology:**
```
Fold 1: Train [2021-2023] → Test [2024] (OOS)
Fold 2: Train [2022-2024] → Test [2025] (OOS)
Fold 3: Train [2023-2025] → Test [2026] (OOS)
─────────────────────────────────────────────
Aggregate OOS results = True performance estimate
```

**Requirements:**
- [ ] Rolling 3-year train / 1-year test splits
- [ ] Calculate metrics on OOS data only
- [ ] Report IS vs OOS gap (overfitting indicator)
- [ ] Aggregate OOS periods for final metrics
- [ ] Flag if IS >> OOS (strategy may be overfit)

---

## Phase 3: Optimization (2 weeks)

### F12.7 HPO Engine (Optuna)
**Priority:** P1  
**Effort:** 2 weeks  
**Dependencies:** F12.6

Bayesian hyperparameter optimization with overfitting protection.

**Search Space:**
```python
search_space = {
    "entry_threshold": (60, 85),      # Continuous
    "exit_threshold": (35, 60),       # Continuous
    "max_positions": (5, 20),         # Integer
    "hold_days_min": (1, 20),         # Integer
    "rebalance_freq": ["daily", "weekly", "biweekly"],
}
```

**Optuna Configuration:**
```python
study = optuna.create_study(
    direction="maximize",  # Maximize Sharpe ratio
    sampler=TPESampler(seed=42),
    pruner=MedianPruner(n_warmup_steps=10),
)

study.optimize(
    objective,  # Walk-forward Sharpe
    n_trials=200,
    timeout=3600,  # 1 hour max
)
```

**Requirements:**
- [ ] Integrate Optuna for Bayesian optimization
- [ ] Objective function: Walk-forward Sharpe ratio
- [ ] Use walk-forward validation (no data leakage)
- [ ] Report confidence intervals on optimal params
- [ ] Save study results for reproducibility
- [ ] Early stopping for poor trials (pruning)

**Overfitting Protection:**
- Optimize on walk-forward OOS Sharpe (not in-sample)
- Report parameter stability across folds
- Penalize extreme parameters
- Require statistical significance

---

## Phase 4: Dashboard (3 weeks)

### F12.8 Backend API Endpoints
**Priority:** P1  
**Effort:** 1 week  
**Dependencies:** F12.4, F12.5

REST API for backtest operations.

**Endpoints:**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/backtest/run` | POST | Start new backtest |
| `/api/v1/backtest/{id}` | GET | Get backtest results |
| `/api/v1/backtest/{id}/equity` | GET | Get equity curve |
| `/api/v1/backtest/{id}/trades` | GET | Get trade log |
| `/api/v1/backtest/history` | GET | List past backtests |
| `/api/v1/analytics/ic-decay` | GET | Get IC decay analysis |
| `/api/v1/analytics/live-performance` | GET | Get live validation metrics |
| `/api/v1/analytics/score-validation` | GET | Get score IC, hit rate |

---

### F12.9 Internal Analytics Dashboard (CLI/Web)
**Priority:** P2 (Deferred)  
**Effort:** 1 week  
**Dependencies:** F12.8

**NOTE:** This is an INTERNAL tool, not user-facing iOS UI. Implemented as CLI commands and optional web dashboard for founders/devs.

**CLI Commands:**
```bash
python -m backtest run --start 2021-01-01 --end 2025-12-31
python -m backtest results <backtest_id>
python -m backtest metrics --ic-decay
python -m backtest report <backtest_id> --format html
```

**Optional Web Dashboard (Future):**
- Simple Flask/FastAPI HTML pages
- View backtest results in browser
- Charts via Chart.js or Plotly
- NOT part of iOS app

**Metrics Displayed:**
- CAGR, Sharpe, Max DD vs SPY
- Score IC and Hit Rate
- Equity curve chart
- Trade log table

**Design:** Simple, functional, not polished UI. Internal tool only.

---

## Phase 5: Enhancement (Optional, 2 weeks)

### F12.10 Report Generator
**Priority:** P2  
**Effort:** 1 week  
**Dependencies:** F12.9

Generate shareable PDF/HTML reports.

**Sections:**
1. Executive Summary
2. Performance Metrics Table
3. Equity Curve Chart
4. Drawdown Analysis
5. Score Validation (IC, Hit Rate)
6. Monthly Returns
7. Methodology Notes
8. Disclaimers

---

### F12.11 Advanced Rebalancing (Future)
**Priority:** P3  
**Effort:** 2 weeks  
**Dependencies:** F12.7

Linear Programming optimization (deferred — start with equal weight).

**Future Constraints:**
- Max position size (15%)
- Max sector exposure (30%)
- Turnover limits
- Transaction cost optimization

---

## Success Criteria

### Minimum Viable Backtest (Phase 1-2)

- [ ] Generate 1.5-year historical scores (5-year optional)
- [ ] Run basic strategy simulation
- [ ] Calculate Sharpe, CAGR, Max DD, IC, Hit Rate
- [ ] Compare against SPY
- [ ] Store all data for future analysis
- [ ] IC decay analysis complete

### Target Metrics (Validation)

| Metric | Target | Action if Miss |
|--------|--------|----------------|
| CAGR | > SPY + 2% | Review scoring weights |
| Sharpe | > 1.0 | Reduce position volatility |
| Max DD | < 25% | Add drawdown controls |
| Score IC | > 0.05 | Scores lack predictive power — major review |
| Hit Rate | > 55% | Adjust entry threshold |

---

## Implementation Timeline

| Phase | Features | Duration | Dependencies |
|-------|----------|----------|--------------|
| **Phase 1** | F12.1, F12.2, F12.3, F12.4 | 4 weeks | — |
| **Phase 2** | F12.5, F12.6 | 2 weeks | Phase 1 |
| **Phase 3** | F12.7 | 2 weeks | Phase 2 |
| **Phase 4** | F12.8, F12.9 | 3 weeks | Phase 1 |
| **Phase 5** | F12.10, F12.11 | 2 weeks | Phase 4 |

**Total:** 9 weeks (Phases 1-4), +2 weeks optional (Phase 5)

**Note:** iOS Dashboard removed from scope. Backtesting is internal tooling only.

**Parallelization:** Phase 4 (Dashboard) can start after Phase 1 completes.

```
Week:  1   2   3   4   5   6   7   8   9  10  11  12  13
       ├───────────────────┤
       │     Phase 1       │
       │   (Foundation)    │
       └───────────────────┼───────────┤
                           │  Phase 2  │
                           │ (Analysis)│
                           └───────────┼───────────┤
                                       │  Phase 3  │
                                       │   (HPO)   │
                           ┌───────────┴───────────┴────┤
                           │        Phase 4             │
                           │      (Dashboard)           │
                           └────────────────────────────┤
                                                        │ Phase 5 │
                                                        │(Optional)│
```

---

## Linear Tickets

### Phase 1: Foundation

| Ticket | Title | Priority | Effort | Dependencies |
|--------|-------|----------|--------|--------------|
| REC-190 | F12.1 Historical Data Persistence | P0 | 1w | — |
| REC-191 | F12.2 Historical Score Generator | P0 | 2w | REC-190 |
| REC-192 | F12.3 Basic Backtest Engine | P0 | 1.5w | REC-191 |
| REC-193 | F12.4 Performance Metrics Calculator | P0 | 1w | REC-192 |

### Phase 2: Score Analysis

| Ticket | Title | Priority | Effort | Dependencies |
|--------|-------|----------|--------|--------------|
| REC-194 | F12.5 IC Decay Analyzer | P1 | 1w | REC-193 |
| REC-195 | F12.6 Walk-Forward Validation | P1 | 1w | REC-193 |

### Phase 3: Optimization

| Ticket | Title | Priority | Effort | Dependencies |
|--------|-------|----------|--------|--------------|
| REC-196 | F12.7 HPO Engine (Optuna) | P1 | 2w | REC-195 |

### Phase 4: API & Internal Tools

| Ticket | Title | Priority | Effort | Dependencies |
|--------|-------|----------|--------|--------------|
| REC-197 | F12.8 Backend API Endpoints | P1 | 1w | REC-193, REC-194 |
| REC-198 | F12.9 Internal CLI/Dashboard | P2 | 1w | REC-197 |

### Phase 5: Enhancement (Optional)

| Ticket | Title | Priority | Effort | Dependencies |
|--------|-------|----------|--------|--------------|
| REC-199 | F12.10 Report Generator | P2 | 1w | REC-198 |
| REC-200 | F12.11 Advanced Rebalancing (LP) | P3 | 2w | REC-196 |

---

## Risk & Limitations

### Known Limitations

1. **No Historical Sentiment** — Using neutral (50) for pre-2026 sentiment
2. **Survivorship Bias** — Current 677 stocks only (no delisted)
3. **Transaction Cost Estimates** — Real costs may vary
4. **Slippage Model** — Assumes execution at close price
5. **No Position Size Impact** — Ignores market impact for large orders

### Required Disclaimers

> ⚠️ **IMPORTANT:** Past performance does not guarantee future results. Backtesting has inherent limitations including survivorship bias, transaction cost estimation, and market regime changes. This tool is for educational purposes only and should not be considered investment advice.

---

## Appendix: Glossary

| Term | Definition |
|------|------------|
| **IC (Information Coefficient)** | Correlation between predicted score and actual return |
| **CAGR** | Compound Annual Growth Rate |
| **Sharpe Ratio** | Risk-adjusted return (excess return / volatility) |
| **Max Drawdown** | Largest peak-to-trough portfolio decline |
| **Walk-Forward** | Rolling train/test validation to prevent overfitting |
| **HPO** | Hyperparameter Optimization |
| **OOS** | Out-of-Sample (test data not used in training) |

---

*Document Version: 2.0*  
*Last Updated: February 6, 2026*  
*Approved by: Or Rim*
