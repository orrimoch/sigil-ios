<img src="../../docs/sigil_logo.jpg" alt="Sigil" width="240" />

# Backtest with Z-Score Normalization (Jun 2018 - Nov 2019)

## Summary

| Field | Value |
|-------|-------|
| **Backtest ID** | `bt_20260213_134210_b9d2d5` |
| **Date Range** | June 1, 2018 – November 30, 2019 (18 months) |
| **Initial Capital** | $100,000 |
| **Max Positions** | 10 |
| **Entry Threshold** | 70 (BUY signal) |
| **Exit Threshold** | 50 (SELL signal) |

---

## Key Performance Metrics

| Metric | Value |
|--------|-------|
| **Total Return** | +4.56% |
| **CAGR** | +3.02% |
| **Sharpe Ratio** | 0.47 |
| **Max Drawdown** | -19.75% |
| **Volatility** | 34.97% |
| **Win Rate** | 66.67% |
| **Total Trades** | 22 |

### Benchmark Comparison (SPY)

| Metric | Portfolio | SPY |
|--------|-----------|-----|
| Return | +4.56% | +18.22% |
| Alpha | -13.66% | — |

---

## Trade Summary

| Metric | Value |
|--------|-------|
| **BUY Signals Generated** | 16 |
| **SELL Signals Generated** | 6 |
| **Completed Round Trips** | 6 |

### Top 5 Winning Trades

| Ticker | Return | Entry Date | Exit Date |
|--------|--------|------------|-----------|
| INCY | +18.36% | 2018-06-01 | 2019-07-19 |
| CF | +17.92% | 2018-06-01 | 2019-11-01 |
| MRVL | +3.33% | 2019-06-07 | 2019-09-20 |
| NFLX | +1.85% | 2018-06-01 | 2019-06-28 |
| TSM | -3.62% | 2018-06-01 | 2018-12-07 |

### Top 5 Losing Trades

| Ticker | Return | Entry Date | Exit Date |
|--------|--------|------------|-----------|
| MU | -42.25% | 2018-06-01 | 2019-06-07 |
| TSM | -3.62% | 2018-06-01 | 2018-12-07 |
| NFLX | +1.85% | 2018-06-01 | 2019-06-28 |
| MRVL | +3.33% | 2019-06-07 | 2019-09-20 |
| CF | +17.92% | 2018-06-01 | 2019-11-01 |

---

## Score Distribution Statistics (Z-Score Normalized)

| Metric | Value |
|--------|-------|
| **Total Scores Generated** | 66,929 |
| **Min Composite Score** | 5.00 |
| **Max Composite Score** | 95.00 |
| **Mean Composite Score** | 51.14 |
| **Median Composite Score** | 52.98 |
| **Std Deviation** | 14.58 |

### Signal Distribution

| Signal | Count | Percentage |
|--------|-------|------------|
| BUY (≥70) | 4,547 | 6.8% |
| HOLD (30-70) | 48,992 | 73.2% |
| SELL (≤30) | 13,390 | 20.0% |

---

## Methodology Notes

> **This backtest uses Z-score normalized scoring (50 + z*15) matching the live pipeline.**

The scoring system normalizes each pillar (fundamental, technical, sentiment, macro) to a standard distribution with:
- **Mean**: 50
- **Standard Deviation**: 15
- **Bounds**: Clamped to [5, 95] range

This ensures consistent score distributions across different market conditions and makes historical backtests comparable to live scoring.

---

## Files Generated

- **HTML Report**: `backtest_normalized_2018_2019.html` (269 KB)
- **This Summary**: `backtest_normalized_2018_2019.md`

---

*Generated: February 13, 2026*
