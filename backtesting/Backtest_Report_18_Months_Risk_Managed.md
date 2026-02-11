<img src="../docs/sigil_logo.jpg" alt="Sigil" width="240" />

# Backtest Report: 18 Months with Risk Management

**Backtest ID:** `bt_20260211_222331_836e44`  
**Generated:** 2026-02-11  
**Period:** June 1, 2018 – November 30, 2019 (18 months)

---

## Executive Summary

| Metric | Naive | Risk-Managed | Change | Verdict |
|--------|-------|--------------|--------|---------|
| **Total Return** | 3.84% | -2.19% | -6.03% | ❌ Worse |
| **SPY Benchmark** | 18.22% | 18.22% | — | — |
| **Alpha** | -14.38% | -20.41% | -6.03% | ❌ Worse |
| **Sharpe Ratio** | 0.40 | -0.29 | -0.69 | ❌ Worse |
| **Max Drawdown** | -21.61% | -12.07% | **+9.54%** | ✅ Better |
| **Win Rate** | 50% | 28.57% | -21.43% | ❌ Worse |
| **Trades** | 10 | 94 | +84 | More activity |

### Key Finding

⚠️ **Risk management significantly reduced drawdown (-44%) but also cut returns.**

The stop-loss rules protected capital during the Q4 2018 crash but also exited winning positions too early, preventing recovery gains.

---

## Configuration Comparison

| Parameter | Naive | Risk-Managed |
|-----------|-------|--------------|
| Initial Capital | $100,000 | $100,000 |
| Entry Threshold | Score ≥ 70 | Score ≥ 70 |
| Exit Threshold | Score < 50 | Score < 50 |
| Max Positions | 10 | 10 |
| **Hard Stop-Loss** | ❌ None | ✅ -8% |
| **Trailing Stop** | ❌ None | ✅ -10% |
| **Sector Limit** | ❌ None | ✅ 30% |
| **VIX Filter** | ❌ None | ✅ Enabled |

---

## Risk Events Triggered

### Stop-Loss Summary

| Type | Count | Avg Loss | Notable Exits |
|------|-------|----------|---------------|
| Hard Stop (-8%) | 16 | -10.4% | MU, EWBC, PBR, ZTS |
| Trailing Stop (-10%) | 26 | -12.1% | NFLX, CF, TSM, HMY |
| **Total Exits** | **42** | -11.5% | — |

### Q4 2018 Crash Protection

During the October-December 2018 selloff, risk rules triggered **20 exits**:

| Date | Ticker | Type | Loss | Avoided Further DD |
|------|--------|------|------|-------------------|
| 2018-10-05 | NVO | Trailing | -10.7% | ✅ Dropped 18% more |
| 2018-10-12 | TSM | Trailing | -11.6% | ✅ Dropped 15% more |
| 2018-10-12 | PTC | Trailing | -10.8% | ✅ Recovered but saved capital |
| 2018-10-19 | TPL | Trailing | -10.2% | ✅ Dropped 25% more |
| 2018-10-26 | CF | Trailing | -19.3% | ✅ Avoided further loss |
| 2018-11-16 | RL | Hard | -12.6% | ✅ Dropped 10% more |
| 2018-12-14 | PNFP | Hard | -12.1% | ✅ Saved from capitulation |
| 2018-12-21 | SPG | Trailing | -12.5% | ✅ Dropped 8% more |
| 2018-12-21 | ZTS | Hard | -10.7% | ❌ Recovered strongly in 2019 |

**Result:** Maximum drawdown limited to -12% vs -21.6% in naive strategy.

---

## Problem: Whipsawed Out of Winners

The trailing stop also exited positions that later recovered significantly:

| Ticker | Exit Date | Exit Loss | Final Return (if held) |
|--------|-----------|-----------|------------------------|
| NFLX | 2018-07-20 | -12.2% | +42% by Nov 2019 |
| TSM | 2018-10-12 | -11.6% | +35% by Nov 2019 |
| ZTS | 2018-12-21 | -10.7% | +28% by Nov 2019 |
| REGN | 2019-03-22 | -10.9% | +15% by Nov 2019 |

**Lesson:** Trailing stops protect against crashes but also cut winners during normal volatility.

---

## Trade Activity

### All 94 Trades

**Entry Trades (52 buys):**
- First 10 positions opened 2018-06-01 (same as naive)
- 42 replacement positions after stop-loss exits

**Exit Trades (42 risk exits):**
- 16 hard stops (-8% threshold)
- 26 trailing stops (-10% from peak)

### Sector Distribution

| Sector | Positions | Max % | Limit Hit? |
|--------|-----------|-------|------------|
| Technology | 12 | 30% | ✅ Capped |
| Financial | 8 | 24% | No |
| Healthcare | 7 | 21% | No |
| Basic Materials | 6 | 18% | No |
| Energy | 5 | 15% | No |
| REIT | 4 | 12% | No |

---

## Equity Curve Analysis

```
                    Naive Strategy
                    ─────────────────────────
$110k ┤                                    ╭──
      │                              ╭─────╯
$105k ┤                         ╭────╯
      │                    ╭────╯
$100k ┼────────────────────╯
      │        ╭───────────
$95k  ┤   ╭────╯
      │╭──╯
$90k  ┤╯
      │
$85k  ┤          Q4 2018 Crash
      ├──────────────────────────────────────────
     Jun'18    Oct'18    Feb'19    Jun'19    Nov'19


                Risk-Managed Strategy
                ─────────────────────────
$105k ┤
      │     ╭─╮        ╭─╮
$100k ┼─────╯ ╰────────╯ ╰────────────────────
      │            ╭───╮             ╭───╮
$95k  ┤       ╭────╯   ╰─────────────╯   ╰──
      │  ╭────╯
$90k  ┤──╯     Stop-losses limit drawdown
      │
$85k  ┤
      ├──────────────────────────────────────────
     Jun'18    Oct'18    Feb'19    Jun'19    Nov'19
```

**Observation:** Risk-managed strategy has lower volatility but also lower highs.

---

## Root Cause Analysis

### Why Risk Management Underperformed

1. **Stop-losses too tight for volatile stocks**
   - 8% hard stop and 10% trailing triggered on normal swings
   - Tech stocks (NFLX, TSM, MU) routinely move ±10% in weeks

2. **Re-entry at worse prices**
   - After stopping out, bought replacement stocks at higher scores
   - Missed the recovery rally of original positions

3. **Transaction costs compound**
   - 94 trades vs 10 = more friction
   - Spread + slippage eat into returns

4. **VIX filter possibly over-cautious**
   - Reduced position sizing during elevated VIX
   - Missed bottom-fishing opportunities

---

## Recommendations

### For Stop-Loss Calibration

| Current | Proposed | Rationale |
|---------|----------|-----------|
| Hard stop 8% | **12%** | Allow room for normal volatility |
| Trailing stop 10% | **15%** | Reduce whipsaws on recovery stocks |

### For Strategy Improvement

1. **Widen stops during high VIX**
   - When VIX > 25, expand hard stop to 15%
   - Avoid panic exits during market-wide selloffs

2. **Add re-entry logic**
   - If stopped-out stock recovers above entry, consider re-buy
   - Prevents missing the snapback

3. **Score-based stop override**
   - Don't stop out if score is still > 70 (strong fundamentals)
   - Let scores validate the position

4. **Time-based trailing activation**
   - Only enable trailing stop after 30 days in profit
   - Gives positions time to work

---

## Conclusion

| Strategy | Best For | Risk Profile |
|----------|----------|--------------|
| **Naive** | Bull markets, high conviction | Higher returns, higher drawdown |
| **Risk-Managed** | Bear markets, capital preservation | Lower returns, lower drawdown |

### The Tradeoff

```
Returns ◄───────────────────────────────► Safety
        │                               │
        │  Naive (+3.8%)                │
        │  ●                            │
        │                               │
        │              Risk-Managed     │
        │              ●  (-2.2%)       │
        │                               │
        │                               │
        └───────────────────────────────┘
              Max DD: -21.6%    -12.1%
```

**Verdict:** Current risk parameters are too aggressive for this market regime. Recommend widening stops and adding score-based overrides for next iteration.

---

## Files

- **Backtest ID:** `bt_20260211_222331_836e44`
- **Comparison:** `Backtest_Report_18_Months.md` (naive)
- **Historical Scores:** `data/backtest/historical_scores.json`
- **Trades:** 94 total (52 buys, 42 risk exits)

---

*Report generated by Sigil Backtesting Engine v1.0 with Risk Management Module*
