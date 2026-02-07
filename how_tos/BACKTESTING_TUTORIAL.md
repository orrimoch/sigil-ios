<img src="../docs/sigil_logo.jpg" alt="Sigil" width="240" />

# Backtesting Module Tutorial

**Last Updated:** February 7, 2026  
**Module Location:** `backend/src/backtest/`

---

## What Is Backtesting?

Backtesting answers one question:

> **"If Sigil existed 1.5 years ago and you followed its BUY/SELL signals, would you have made money?"**

It's a **time-machine simulation** that validates whether the scoring model works before you risk real capital.

| Backtesting | Your Real Portfolio |
|-------------|---------------------|
| Starts with $100,000 hypothetical cash | Your actual IBKR positions |
| Goes back 1.5 years | Starts today |
| Simulated trades | Real trades |
| Purpose: Validate the model | Purpose: Make money |

---

## Quick Start

```bash
# Navigate to backend
cd ~/Desktop/Cool_Apps/TradingApp_iOS/backend

# Step 1: Generate historical scores (required first time)
python3 -m src.backtest generate

# Step 2: Run a backtest
python3 -m src.backtest run

# Step 3: View results
python3 -m src.backtest list
python3 -m src.backtest results <backtest_id>

# Step 4: Generate report
python3 -m src.backtest report <backtest_id> --format html
```

---

## CLI Commands Reference

### `generate` — Generate Historical Scores

**⚠️ Required before first backtest.** Retroactively calculates what scores *would have been* using historical data.

```bash
python3 -m src.backtest generate [OPTIONS]
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `--start` | DATE | 18 months ago | Start date (YYYY-MM-DD) |
| `--end` | DATE | Today | End date (YYYY-MM-DD) |
| `--frequency` | STRING | weekly | Score frequency: `daily` or `weekly` |
| `--tickers` | STRING | All (677) | Comma-separated tickers to process |
| `--force` | FLAG | false | Force regenerate, ignore cached scores |

**Data sources used:**
- **Prices:** yfinance (5+ years available)
- **Fundamentals:** FMP API with 60-day lag (simulates earnings delay)
- **Macro:** FRED economic data
- **Sentiment:** Neutral (50) for historical periods (no news archive)

**⚡ Smart Caching:**

The generator caches scores by date. On subsequent runs:
- Dates with existing scores are **skipped automatically**
- Only missing dates are generated
- Use `--force` to regenerate everything

```bash
# First run: generates all 78 weeks (~5-10 min)
python3 -m src.backtest generate

# Second run: skips cached dates (~instant)
python3 -m src.backtest generate

# Force regenerate everything
python3 -m src.backtest generate --force
```

**Examples:**

```bash
# Generate all 677 stocks, 18 months (default)
python3 -m src.backtest generate

# Custom date range
python3 -m src.backtest generate --start 2024-01-01 --end 2026-02-07

# Quick test with specific tickers
python3 -m src.backtest generate --tickers AAPL,MSFT,NVDA,GOOGL,META

# Daily frequency (more granular, slower)
python3 -m src.backtest generate --frequency daily

# Force regenerate all scores (ignore cache)
python3 -m src.backtest generate --force
```

**Time estimate:** 
- First run: ~5-10 minutes for 677 stocks × 78 weeks
- Subsequent runs: ~instant (cached)

---

### `run` — Run a Backtest

Executes a trading simulation over historical data.

```bash
python3 -m src.backtest run [OPTIONS]
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `--start` | DATE | 18 months ago | Start date (YYYY-MM-DD) |
| `--end` | DATE | Today | End date (YYYY-MM-DD) |
| `--capital` | NUMBER | 100000 | Initial capital in USD |
| `--entry` | NUMBER | 70 | Entry threshold (buy when score ≥ this) |
| `--exit` | NUMBER | 50 | Exit threshold (sell when score < this) |
| `--positions` | NUMBER | 10 | Maximum positions to hold |
| `--rebalance` | STRING | weekly | Rebalance frequency: `daily`, `weekly`, `biweekly` |

**Entry/Exit Logic:**
```
Score ≥ 70 (entry)  →  BUY signal
Score < 50 (exit)   →  SELL signal
Score 50-69         →  HOLD (do nothing)
```

**Examples:**

```bash
# Default backtest (18 months, $100k, entry=70, exit=50)
python3 -m src.backtest run

# Custom date range
python3 -m src.backtest run --start 2024-01-01 --end 2025-12-31

# Aggressive strategy (higher entry, lower exit)
python3 -m src.backtest run --entry 75 --exit 40 --positions 15

# Conservative strategy
python3 -m src.backtest run --entry 80 --exit 60 --positions 5 --capital 50000
```

---

### `results` — View Backtest Results

Shows detailed metrics for a completed backtest.

```bash
python3 -m src.backtest results <backtest_id>
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `backtest_id` | STRING | ✅ | The backtest ID (e.g., `bt_20260206_123456_abc123`) |

**Output includes:**
- Total Return, CAGR, Sharpe Ratio
- Max Drawdown, Win Rate
- Score IC, Hit Rate
- Comparison to SPY benchmark

---

### `list` — List All Backtests

Shows history of all backtests run.

```bash
python3 -m src.backtest list [OPTIONS]
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `--limit` | NUMBER | 20 | Maximum results to show |

---

### `trades` — View Trade Log

Shows all simulated trades from a backtest.

```bash
python3 -m src.backtest trades <backtest_id> [OPTIONS]
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `backtest_id` | STRING | ✅ | The backtest ID |
| `--limit` | NUMBER | 100 | Maximum trades to show |

---

### `report` — Generate Report

Creates a shareable HTML or PDF report.

```bash
python3 -m src.backtest report <backtest_id> [OPTIONS]
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `backtest_id` | STRING | ✅ | The backtest ID |
| `--format` | STRING | html | Output format: `html` or `pdf` |
| `--output`, `-o` | PATH | Auto-generated | Output file path |
| `--title` | STRING | Auto | Custom report title |
| `--no-trades` | FLAG | false | Exclude trade log from report |
| `--no-charts` | FLAG | false | Exclude charts from report |

**Examples:**

```bash
# HTML report (default)
python3 -m src.backtest report bt_20260206_123456_abc123

# PDF with custom title
python3 -m src.backtest report bt_20260206_123456_abc123 --format pdf --title "Q4 2025 Backtest"

# Minimal report (no trades/charts)
python3 -m src.backtest report bt_20260206_123456_abc123 --no-trades --no-charts -o summary.html
```

---

### `optimize` — Hyperparameter Optimization

Uses Optuna to find optimal strategy parameters via Bayesian optimization.

```bash
python3 -m src.backtest optimize [OPTIONS]
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `--start` | DATE | 18 months ago | Start date |
| `--end` | DATE | Today | End date |
| `--trials` | NUMBER | 50 | Number of optimization trials |
| `--timeout` | NUMBER | 3600 | Timeout in seconds (1 hour default) |
| `--train-months` | NUMBER | 9 | Training period in months |
| `--test-months` | NUMBER | 3 | Test period in months |

**What it optimizes:**
- Entry threshold (60-85)
- Exit threshold (35-60)
- Max positions (5-20)
- Rebalance frequency

**Example:**

```bash
# Quick optimization (50 trials)
python3 -m src.backtest optimize --trials 50 --timeout 1800

# Full optimization
python3 -m src.backtest optimize --trials 200 --train-months 12 --test-months 6
```

---

### `ic-decay` — Score Decay Analysis

Measures how quickly score predictive power decays over time.

```bash
python3 -m src.backtest ic-decay [OPTIONS]
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `--start` | DATE | 18 months ago | Start date |
| `--end` | DATE | Today | End date |

**Output example:**

```
Day of Week Analysis:
├── Monday (Day 1):    IC = 0.072 ± 0.015
├── Tuesday (Day 2):   IC = 0.065 ± 0.014
├── Wednesday (Day 3): IC = 0.058 ± 0.016
├── Thursday (Day 4):  IC = 0.049 ± 0.018
└── Friday (Day 5):    IC = 0.041 ± 0.020

Recommendation: Refresh scores on Wednesday
```

---

### `walk-forward` — Walk-Forward Validation

Prevents overfitting by using rolling train/test periods.

```bash
python3 -m src.backtest walk-forward [OPTIONS]
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `--start` | DATE | 18 months ago | Start date |
| `--end` | DATE | Today | End date |
| `--train-months` | NUMBER | 9 | Training period in months |
| `--test-months` | NUMBER | 3 | Test period (out-of-sample) in months |

**How it works:**

```
Fold 1: Train [2022-2023] → Test [2024 H1] (OOS)
Fold 2: Train [2022-2024 H1] → Test [2024 H2] (OOS)
Fold 3: Train [2023-2024] → Test [2025 H1] (OOS)
─────────────────────────────────────────────────
Aggregate OOS results = True performance estimate
```

---

### `monte-carlo` — Monte Carlo Simulation

Randomizes trade order to estimate outcome uncertainty and confidence intervals.

```bash
python3 -m src.backtest monte-carlo <backtest_id> [OPTIONS]
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `backtest_id` | STRING | ✅ | Backtest ID to analyze |
| `--sims` | NUMBER | 1000 | Number of simulations (100-10000) |
| `--seed` | NUMBER | Random | Random seed for reproducibility |
| `--no-save` | FLAG | false | Don't save results to file |

**Output:**
- Median CAGR with 5th/95th percentile confidence bands
- Probability of positive returns
- Worst-case and best-case scenarios

---

### `import-scores` — Import Pipeline Scores

Imports existing scores from the live scoring pipeline into backtest storage.

```bash
python3 -m src.backtest import-scores
```

**Note:** Only imports scores that already exist in `score_history.json`. Use `generate` to create historical scores from raw data.

---

### `stats` — Storage Statistics

Shows database statistics and storage usage.

```bash
python3 -m src.backtest stats
```

**Output:**
- Number of stored historical scores
- Number of backtests run
- Date range of available data
- Storage directory path

---

## Key Metrics Explained

### Performance Metrics

| Metric | What It Means | Target |
|--------|---------------|--------|
| **Total Return** | Overall gain/loss | — |
| **CAGR** | Annualized return | > SPY + 2% |
| **Sharpe Ratio** | Risk-adjusted return | > 1.0 |
| **Max Drawdown** | Largest peak-to-trough drop | < 25% |
| **Win Rate** | % of profitable trades | > 55% |

### Score Validation Metrics

| Metric | What It Means | Target |
|--------|---------------|--------|
| **IC (Information Coefficient)** | Correlation between score and future return | > 0.05 |
| **Hit Rate** | % of BUY signals that beat SPY | > 55% |
| **Quintile Spread** | Top 20% return minus Bottom 20% return | > 10%/yr |

---

## Typical Workflow

```bash
# 1. Generate historical scores (first time only)
python3 -m src.backtest generate

# 2. Check what data is available
python3 -m src.backtest stats

# 3. Run initial backtest with default settings
python3 -m src.backtest run

# 4. Check results
python3 -m src.backtest list
python3 -m src.backtest results <id>

# 5. Analyze score predictive power
python3 -m src.backtest ic-decay

# 6. Validate not overfit
python3 -m src.backtest walk-forward

# 7. Find optimal parameters
python3 -m src.backtest optimize --trials 100

# 8. Run backtest with optimized params
python3 -m src.backtest run --entry 72 --exit 48 --positions 12

# 9. Estimate uncertainty
python3 -m src.backtest monte-carlo <id>

# 10. Generate final report
python3 -m src.backtest report <id> --format html
```

---

## Troubleshooting

### "Only 5 tickers found"

**Problem:** Backtest ran on almost no data.

**Solution:** Run `python3 -m src.backtest generate` first to create historical scores.

### "Sharpe ratio unrealistically high (>10)"

**Problem:** Almost no trades executed, low volatility from inactivity.

**Solution:** Generate more historical scores or lower entry threshold.

### "Alpha is very negative"

**Problem:** Strategy sat in cash while market went up.

**Solution:** Ensure scores exist for the backtest period. Check with `stats` command.

---

## Limitations & Disclaimers

⚠️ **Important:**

1. **No Historical Sentiment** — Uses neutral (50) for pre-2026 sentiment data
2. **Survivorship Bias** — Only tests current 677 stocks (no delisted companies)
3. **Transaction Costs** — Estimates may differ from real execution
4. **Slippage** — Assumes execution at close price
5. **Past ≠ Future** — Historical performance does not guarantee future results

---

## Related Files

| Path | Description |
|------|-------------|
| `backend/src/backtest/` | Module source code |
| `backend/data/backtest/` | Stored backtest results |
| `docs/06_BACKTESTING_SPEC.md` | Full technical specification |
| `reports/` | Generated HTML/PDF reports |

---

*For questions or issues, check the technical spec or run any command with `--help`*
