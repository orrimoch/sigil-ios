<img src="../docs/sigil_logo.jpg" alt="Sigil" width="240" />

# Risk Module — User Guide & Technical Specification

**Version:** 1.0  
**Last Updated:** 2026-02-10  
**Status:** ✅ Complete (Phases 1-3 + iOS Integration)

---

## Table of Contents

1. [Overview & Goals](#1-overview--goals)
2. [Where to Find Risk Indicators](#2-where-to-find-risk-indicators)
3. [Risk Settings (User Configurable)](#3-risk-settings-user-configurable)
4. [Sub-Modules Explained](#4-sub-modules-explained)
5. [Risk Scores & Calculations](#5-risk-scores--calculations)
6. [API Reference](#6-api-reference)
7. [Architecture](#7-architecture)

---

## 1. Overview & Goals

### 1.1 What is the Risk Module?

The Risk Module is Sigil's intelligent protection system that helps you:

- **Protect capital** — Automatic stop-loss orders to limit downside
- **Lock in profits** — Trailing stops that follow price up
- **Adapt to markets** — VIX-adjusted signals during volatility
- **Prevent over-concentration** — Position size and sector warnings
- **Understand risk** — AI-powered analysis and regime detection

### 1.2 Design Philosophy

| Principle | Implementation |
|-----------|----------------|
| **Opt-in by default** | All protections OFF until you enable them |
| **Non-blocking** | Risk warnings don't prevent trades, they inform |
| **Server-side execution** | IBKR stop orders execute even if app is closed |
| **Transparent** | Every calculation is explainable |
| **User-first** | Settings persist, sync across devices |

### 1.3 Original Goals (from PM Spec)

1. ✅ Implement stop-loss and trailing stop orders via IBKR
2. ✅ Add VIX-based signal adjustment during high volatility
3. ✅ Calculate portfolio VaR (Value at Risk) at 95% confidence
4. ✅ Detect market regimes (low vol / normal / high vol / crisis)
5. ✅ Warn users about position and sector concentration
6. ✅ Provide AI-powered risk analysis per stock
7. ✅ Track patterns and learn from user's trading history

---

## 2. Where to Find Risk Indicators

### 2.1 Location Map

| Indicator | Screen | Location | What It Shows |
|-----------|--------|----------|---------------|
| **VIX Level** | Home | Market Overview card | Current VIX value + daily change % |
| **HMM Regime** | Home | Top-right badge | Market state: `NORMAL`, `HIGH VOL`, `CRISIS` |
| **Risk Badge** | Portfolio | Summary card top-right | Portfolio risk: `LOW`, `MEDIUM`, `HIGH`, `CRITICAL` |
| **Stop Distance** | Portfolio | Position card | Distance to stop-loss (e.g., "8% to stop") |
| **Portfolio VaR** | Portfolio | Below summary | Daily Value-at-Risk in dollars |
| **Sector Warnings** | Portfolio → Sectors tab | Banner | Concentration alerts (>30% in one sector) |
| **Claude Risk** | Stock Detail | Risk section | AI-generated risk analysis |
| **Risk Settings** | Settings → Risk Management | Full screen | Configure all protections |

### 2.2 Visual Guide

```
┌─────────────────────────────────────────────────────┐
│                    HOME SCREEN                       │
│  ┌─────────────────┐    ┌──────────────────────┐    │
│  │ Market Open     │    │ 🟡 NORMAL            │◄───┼── HMM Regime Badge
│  │ Closes 2h 16m   │    │                      │    │
│  └─────────────────┘    └──────────────────────┘    │
│                                                      │
│  ┌─────────────────────────────────────────────┐    │
│  │ Market Overview                              │    │
│  │  S&P 500   NASDAQ    DOW       VIX          │    │
│  │  6,957     23,185    50,195    17.65 ◄──────┼────┼── VIX in Market Overview
│  └─────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│                  PORTFOLIO SCREEN                    │
│  ┌─────────────────────────────────────────────┐    │
│  │ Portfolio Value           🟢 LOW ◄──────────┼────┼── Risk Badge
│  │ $104,430.02                                  │    │
│  │ Daily VaR: $1,247 (95%) ◄───────────────────┼────┼── Portfolio VaR
│  └─────────────────────────────────────────────┘    │
│                                                      │
│  ┌─────────────────────────────────────────────┐    │
│  │ AAPL  150 shares                             │    │
│  │ $25,432 (+4.2%)                              │    │
│  │ 8% to stop ◄────────────────────────────────┼────┼── Stop Distance
│  └─────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘
```

### 2.3 Risk Badge Colors

| Badge | Color | Meaning | Trigger |
|-------|-------|---------|---------|
| `LOW` | 🟢 Green | Portfolio well-diversified, low VaR | VaR < 2% of portfolio |
| `MEDIUM` | 🟡 Gold | Some concentration or elevated vol | VaR 2-5% of portfolio |
| `HIGH` | 🟠 Orange | Significant risk exposure | VaR 5-10% or sector > 40% |
| `CRITICAL` | 🔴 Red | Extreme risk, action recommended | VaR > 10% or crisis regime |

---

## 3. Risk Settings (User Configurable)

### 3.1 Hard Stop-Loss

**What it does:** Places an IBKR stop order that automatically sells if price drops below your threshold.

| Setting | Range | Default | Description |
|---------|-------|---------|-------------|
| Enabled | ON/OFF | OFF | Toggle protection |
| Threshold | -5% to -20% | -8% | Trigger point from entry |

**How it works:**
1. You buy AAPL at $200
2. With -8% threshold, stop is at $184
3. If AAPL drops to $184, IBKR sells automatically
4. Works even if app is closed (server-side order)

### 3.2 Trailing Stop-Loss

**What it does:** A stop that follows price UP but never moves DOWN. Locks in profits.

| Setting | Range | Default | Description |
|---------|-------|---------|-------------|
| Enabled | ON/OFF | OFF | Toggle protection |
| Distance | -5% to -25% | -10% | Distance from peak |

**How it works:**
1. You buy AAPL at $200, set 10% trailing stop
2. Initial stop: $180 (10% below $200)
3. AAPL rises to $220 → stop moves to $198 (10% below $220)
4. AAPL rises to $250 → stop moves to $225
5. AAPL drops to $225 → SELL triggered, you keep $25 profit

### 3.3 VIX-Adjusted Signals

**What it does:** Makes scoring more conservative during high volatility.

| Setting | Range | Default | Description |
|---------|-------|---------|-------------|
| Enabled | ON/OFF | OFF | Toggle adjustment |

**How it works:**
- When VIX > 15: BUY threshold raised, SELL threshold lowered
- Formula: `adjusted_threshold = 50 + max(0, (VIX - 15) × 0.5)`
- At VIX 25: BUY requires score > 55 (vs normal 50)
- At VIX 35: BUY requires score > 60

### 3.4 Position Size Limit

**What it does:** Warns you before making any single position too large.

| Setting | Range | Default | Description |
|---------|-------|---------|-------------|
| Enabled | ON/OFF | OFF | Toggle warning |
| Max Size | 5% to 30% | 15% | Max % of portfolio |

**How it works:**
- You have $100,000 portfolio, limit set to 15%
- Trying to buy $20,000 of AAPL → Warning shown
- You can still proceed, but you're informed of the risk

---

## 4. Sub-Modules Explained

### 4.1 VIX Service (`vix_service.py`)

**Purpose:** Fetches and caches the CBOE Volatility Index (VIX).

**What is VIX?**
- The "fear index" — measures expected S&P 500 volatility
- VIX < 15: Low volatility, calm markets
- VIX 15-25: Normal volatility
- VIX 25-35: High volatility, caution advised
- VIX > 35: Extreme fear, potential crisis

**Data source:** Yahoo Finance (`^VIX`)  
**Cache:** 15 minutes (real-time during market hours)

**Key functions:**
- `fetch_vix()` — Get current VIX + change
- `calculate_dynamic_threshold()` — Adjust signal thresholds

### 4.2 HMM Regime Detection (`hmm_regime.py`)

**Purpose:** Classifies current market conditions using Hidden Markov Models.

**Regimes:**
| Regime | Characteristics | Trading Implication |
|--------|-----------------|---------------------|
| `low_vol` | VIX < 12, steady uptrend | Full position sizes |
| `normal` | VIX 12-20, typical conditions | Standard approach |
| `high_vol` | VIX 20-30, elevated uncertainty | Reduce exposure |
| `crisis` | VIX > 30, panic/crash | Capital preservation |

**Detection method:**
1. Collects 60-day rolling volatility
2. Trains 4-state HMM on historical patterns
3. Classifies current state with confidence %
4. Falls back to rule-based if insufficient data

**Update frequency:** Hourly

### 4.3 VaR Calculator (`var_calculator.py`)

**Purpose:** Estimates potential portfolio loss at a given confidence level.

**What is VaR?**
- "Value at Risk" — the maximum expected loss over a period
- 95% VaR of $1,000 means: "There's a 95% chance you won't lose more than $1,000 today"

**Calculation methods:**

1. **Parametric VaR (Primary)**
   ```
   VaR = Portfolio_Value × σ × z_score
   
   Where:
   - σ = 20-day rolling volatility
   - z_score = 1.645 for 95%, 2.326 for 99%
   ```

2. **Historical VaR (Validation)**
   - Uses actual return distribution from past 252 days
   - Finds the 5th percentile worst return

3. **Correlated VaR (Portfolio-level)**
   - Accounts for correlations between holdings
   - Uses covariance matrix for more accurate estimates

### 4.4 Claude AI Analyzer (`claude_analyzer.py`)

**Purpose:** Generates natural-language risk analysis for individual stocks.

**How it works:**
1. Collects stock data: price, volatility, sector, news
2. Sends prompt to Claude 3 Haiku (fast, cheap)
3. Receives structured risk assessment
4. Caches result for 24 hours

**Output includes:**
- Risk score (1-10)
- Key risk factors
- Risk mitigation suggestions
- Sector-specific concerns

**Cost:** ~$5/month for typical usage (70% cache hit rate)

### 4.5 Sector Limits (`sector_limits.py`)

**Purpose:** Monitors portfolio concentration by sector.

**Calculations:**
- **Exposure %:** Value in sector / Total portfolio value
- **HHI (Herfindahl-Hirschman Index):** Sum of squared sector weights
- **Diversification Score:** 100 - (HHI × 100)

**Warnings triggered when:**
- Any sector > 30% of portfolio (default threshold)
- HHI > 0.25 (concentrated portfolio)

### 4.6 Stop-Loss Manager (`stop_loss.py` + `ibkr_orders.py`)

**Purpose:** Places and manages IBKR stop orders.

**Order types:**
| Type | IBKR Code | Behavior |
|------|-----------|----------|
| Hard Stop | `STP` | Fixed price, sells at market when triggered |
| Stop Limit | `STP_LMT` | Fixed price, sells at limit price |
| Trailing Stop | `TRAIL` | Follows price up, never moves down |

**Execution flow:**
1. User enables stop-loss in settings
2. Backend calculates stop price from entry + threshold
3. Places IBKR order via ib_insync
4. IBKR monitors price server-side
5. Order executes automatically when triggered

### 4.7 Pattern Memory (`pattern_memory.py`)

**Purpose:** Learns from user's trading history to improve risk recommendations.

**What it tracks:**
- Stop-loss trigger events (what worked, what didn't)
- Regime changes and portfolio performance
- Sector rotation patterns
- Win/loss ratios by market condition

**Data retention:** Last 90 days in SQLite

---

## 5. Risk Scores & Calculations

### 5.1 Portfolio Risk Score

The overall portfolio risk badge (LOW/MEDIUM/HIGH/CRITICAL) is calculated by combining multiple factors:

```
risk_score = (
    var_component × 0.40 +
    concentration_component × 0.25 +
    regime_component × 0.20 +
    volatility_component × 0.15
)
```

**Component calculations:**

| Component | Score Range | Calculation |
|-----------|-------------|-------------|
| VaR | 0-100 | `min(100, (daily_var_pct / 0.10) × 100)` |
| Concentration | 0-100 | `max_sector_pct × 100 / 50` |
| Regime | 0-100 | `low_vol=0, normal=25, high_vol=60, crisis=100` |
| Volatility | 0-100 | `min(100, portfolio_vol_20d / 0.30 × 100)` |

**Final mapping:**
- Score 0-25: `LOW` (🟢)
- Score 25-50: `MEDIUM` (🟡)
- Score 50-75: `HIGH` (🟠)
- Score 75-100: `CRITICAL` (🔴)

### 5.2 Individual Stock Risk (Claude)

Claude analyzes each stock on 5 dimensions:

| Dimension | Weight | Factors Considered |
|-----------|--------|-------------------|
| Volatility | 25% | Historical vol, beta, ATR |
| Liquidity | 20% | Volume, bid-ask spread |
| Fundamental | 20% | Debt ratio, earnings stability |
| Sector | 20% | Industry risks, cyclicality |
| News/Sentiment | 15% | Recent headlines, analyst ratings |

Output: Risk score 1-10 with natural language explanation.

### 5.3 VIX-Adjusted Thresholds

When VIX adjustment is enabled, scoring thresholds shift:

```python
def calculate_adjusted_threshold(base_threshold: float, current_vix: float) -> float:
    """
    Adjust threshold based on VIX level.
    
    VIX < 15: No adjustment
    VIX 15-25: Gradual increase
    VIX > 25: Stronger adjustment
    """
    if current_vix <= 15:
        return base_threshold
    
    adjustment = (current_vix - 15) * 0.5
    return base_threshold + min(adjustment, 15)  # Cap at +15
```

**Example:**
| VIX Level | Base BUY Threshold | Adjusted Threshold |
|-----------|-------------------|-------------------|
| 12 | 70 | 70 (no change) |
| 18 | 70 | 71.5 |
| 25 | 70 | 75 |
| 35 | 70 | 80 |

---

## 6. API Reference

### 6.1 User Risk Settings

```
GET  /api/v1/user/risk-settings     — Get current settings
PUT  /api/v1/user/risk-settings     — Update settings
POST /api/v1/user/risk-settings/reset — Reset to defaults
```

### 6.2 Market Data

```
GET /api/v1/market/vix              — Current VIX + regime
GET /api/v1/market/vix/thresholds   — Dynamic threshold table
GET /api/v1/market/regime           — HMM regime classification
GET /api/v1/market/regime/history   — Historical regime changes
```

### 6.3 Portfolio Risk

```
GET /api/v1/risk/portfolio          — Overall risk score + badge
GET /api/v1/portfolio/var/correlated — Correlated VaR calculation
GET /api/v1/portfolio/sectors/exposure — Sector concentration
```

### 6.4 Stock Analysis

```
GET /api/v1/risk/analyze/{ticker}   — Claude AI risk analysis
GET /api/v1/risk/var/{ticker}       — Individual stock VaR
```

### 6.5 Pattern Memory

```
GET /api/v1/risk/patterns/stats     — Trading pattern statistics
GET /api/v1/risk/patterns/analysis/stops — Stop-loss effectiveness
GET /api/v1/risk/patterns/analysis/regimes — Performance by regime
```

---

## 7. Architecture

### 7.1 Module Structure

```
backend/src/risk/
├── __init__.py           # Module exports
├── models.py             # Data models (UserRiskSettings, etc.)
├── service.py            # Settings persistence + IBKR sync
├── routes.py             # Phase 1 API routes (settings)
├── routes_p2.py          # Phase 2 API routes (VIX, trade validation)
├── routes_p3.py          # Phase 3 API routes (regime, patterns)
├── vix_service.py        # VIX fetching + caching
├── var_calculator.py     # VaR calculations (parametric, historical)
├── hmm_regime.py         # HMM regime detection
├── claude_analyzer.py    # AI risk analysis
├── sector_limits.py      # Sector concentration analysis
├── portfolio_var.py      # Correlated portfolio VaR
├── position_limits.py    # Position size validation
├── stop_loss.py          # Stop-loss calculation logic
├── ibkr_orders.py        # IBKR order management
├── dynamic_thresholds.py # VIX-adjusted thresholds
└── pattern_memory.py     # SQLite pattern storage
```

### 7.2 Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER ACTION                              │
│                    (Enable stop-loss at 8%)                      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      iOS Risk Settings                           │
│              PUT /api/v1/user/risk-settings                      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    RiskSettingsService                           │
│  1. Validate settings                                            │
│  2. Save to SQLite (user_risk_settings table)                   │
│  3. Trigger IBKR sync                                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   IBKRStopOrderManager                           │
│  1. Get user's positions                                         │
│  2. Calculate stop price for each                                │
│  3. Place STP/TRAIL orders via ib_insync                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      IB Gateway                                  │
│  • Orders held server-side                                       │
│  • Executes automatically when price triggers                    │
│  • Works 24/7, even if app is closed                            │
└─────────────────────────────────────────────────────────────────┘
```

### 7.3 Database Schema

```sql
-- User Risk Settings
CREATE TABLE user_risk_settings (
    user_id TEXT PRIMARY KEY,
    settings_json TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Risk Cache (VIX, Regime)
CREATE TABLE risk_cache (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    expires_at TIMESTAMP
);

-- Pattern Memory
CREATE TABLE pattern_events (
    id INTEGER PRIMARY KEY,
    event_type TEXT NOT NULL,  -- 'stop_triggered', 'regime_change', etc.
    ticker TEXT,
    data_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## Appendix A: Linear Tickets

| Ticket | Description | Status |
|--------|-------------|--------|
| REC-214 | Risk Settings Data Model | ✅ Done |
| REC-215 | Risk Settings Screen | ✅ Done |
| REC-216 | Risk Settings API | ✅ Done |
| REC-217 | Hard Stop-Loss | ✅ Done |
| REC-218 | Trailing Stop-Loss | ✅ Done |
| REC-219 | VIX Adjustment | ✅ Done |
| REC-220 | Position Limits | ✅ Done |
| REC-221 | VaR Calculator | ✅ Done |
| REC-222 | Claude Risk Analyzer | ✅ Done |
| REC-223 | Dynamic Thresholds | ✅ Done |
| REC-224 | Trade Validation | ✅ Done |
| REC-225 | VIX Service | ✅ Done |
| REC-226 | Threshold Table | ✅ Done |
| REC-227 | VIX Indicators | ✅ Done |
| REC-228 | VIX Explanation | ✅ Done |
| REC-229 | Unit Tests (Phase 2) | ✅ Done |
| REC-230 | Portfolio Risk Badge | ✅ Done |
| REC-231 | Stop Distance Indicator | ✅ Done |
| REC-240 | HMM Regime Detection | ✅ Done |
| REC-241 | Sector Concentration | ✅ Done |
| REC-242 | Correlated Portfolio VaR | ✅ Done |
| REC-243-250 | Pattern Memory System | ✅ Done |

---

## Appendix B: Testing

**Total Risk Module Tests:** 135
- Unit tests: 116
- Integration tests: 19

**Run tests:**
```bash
cd backend
python3 -m pytest tests/unit/test_risk*.py -v
python3 -m pytest tests/integration/test_risk*.py -v
```

---

*Document authored by Blaze Neon | Sigil AI Team | 2026*
