<img src="./sigil_logo.jpg" alt="Sigil" width="240" />

# Historical Sentiment Plan

*Created: 2026-02-07*

## Objective

Generate historical sentiment scores for backtesting to validate Sigil's scoring model has predictive power.

**Current Problem:** Backtest shows -4.15% return vs SPY +35.59% because all historical sentiment scores are stuck at 50 (neutral) — no news archive existed.

**Solution:** Implement multi-source news providers with Claude Haiku agentic scoring:
1. **Kaggle Dataset** — Historical news (2009-2020) for backtesting
2. **Polygon.io API** — Real-time and recent news (2020+) for production

---

## Data Sources

### Source 1: Kaggle Dataset (Historical)
- **Dataset:** [Massive Stock News Analysis DB](https://www.kaggle.com/datasets/miguelaenlle/massive-stock-news-analysis-db-for-nlpbacktests)
- **Coverage:** 2009-2020
- **Size:** 845MB (4.6M headlines)
- **Location:** `TradingApp_iOS/kaggle_sentiment/`
- **Use:** Backtesting validation

### Source 2: Polygon.io API (Real-time)
- **API:** Polygon.io News API
- **Coverage:** 2020-present
- **Use:** Production live scoring
- **Status:** Future implementation (REC-213)

### Architecture
```
┌─────────────────────────────────────────────────┐
│           MultiSourceNewsProvider               │
├─────────────────────────────────────────────────┤
│  Date < 2020    │    Date >= 2020               │
│       ↓         │         ↓                     │
│  KaggleProvider │    PolygonProvider            │
│   (CSV files)   │    (REST API)                 │
└─────────────────────────────────────────────────┘
                    ↓
            Claude Haiku Scoring
                    ↓
             0-100 Sentiment Score
```

---

## Kaggle Table Selection

| File | Records | Use? | Reason |
|------|---------|------|--------|
| `analyst_ratings_processed.csv` | 1.4M | ✅ **PRIMARY** | Clean, deduplicated, has all needed columns |
| `raw_partner_headlines.csv` | 1.8M | ⚠️ Backup | More data but includes duplicates |
| `raw_analyst_ratings.csv` | 1.4M | ❌ Skip | Raw version of processed file |

---

## Column Mapping

### Primary Table: `analyst_ratings_processed.csv`

| Column | Type | Description | Use |
|--------|------|-------------|-----|
| `Unnamed: 0` | int | Row index | ❌ Ignore |
| `title` | string | News headline | ✅ **SENTIMENT INPUT** |
| `date` | datetime | Publication timestamp (with timezone) | ✅ **TIME MAPPING** |
| `stock` | string | Ticker symbol | ✅ **TICKER FILTER** |

### Sample Row
```
title: "B of A Securities Maintains Neutral on Agilent Technologies, Raises Price Target to $88"
date: 2020-05-22 11:38:00-04:00
stock: A
```

---

## Filtering Criteria

### Time Window
- **Period:** Pre-COVID normal market conditions
- **Start Date:** 2019-06-01
- **End Date:** 2019-11-30
- **Duration:** 6 months (~26 weeks)
- **Rationale:** 
  - Normal market conditions (no black swan events)
  - Representative of typical market behavior
  - Better baseline for validating scoring model
  - Lower cost (~$1)

### Ticker Universe
- **Filter to:** 938 tickers in `fundamentals.json`
- **Match rate:** 598 tickers have headlines in this period

### Final Dataset
| Metric | Value |
|--------|-------|
| Headlines | 30,826 |
| Tickers | 598 |
| Date range | 2019-06-01 to 2019-11-30 |

---

## Sentiment Scoring Model

### Claude Haiku Agentic Scoring
- **Provider:** Anthropic
- **Model:** Claude 3.5 Haiku (`claude-3-5-haiku-20241022`)
- **Approach:** Agentic LLM scoring — same as live Sigil pipeline
- **Consistency:** Identical to production (REC-170, REC-172)
- **Pricing:**
  - Input: $0.25 / 1M tokens
  - Output: $1.25 / 1M tokens
  - **Total cost: ~$1.00** for 30k headlines

### Prompt Template
```
Score this financial news headline for stock {ticker} on a scale of 0-100:
- 0-30: Bearish (bad news, downgrades, losses)
- 31-45: Slightly bearish
- 46-54: Neutral
- 55-69: Slightly bullish  
- 70-100: Bullish (good news, upgrades, beats)

Headline: "{title}"

Reply with just the number.
```

### Output Schema
```json
{
  "ticker": "AAPL",
  "date": "2020-01-15",
  "headline": "Apple beats Q4 earnings expectations",
  "sentiment_score": 78
}
```

---

## Aggregation Strategy

### Per-Week Sentiment Score
1. Collect all headlines for ticker in that week
2. Calculate weighted average (more recent = higher weight)
3. Normalize to 0-100 scale

### Formula
```python
weekly_sentiment = sum(score * recency_weight) / sum(recency_weight)
```

Where `recency_weight = 1.0 - (days_old / 7) * 0.3`

---

## Cost Estimate

| Metric | Value |
|--------|-------|
| Headlines | 30,826 |
| Avg input tokens | 80 |
| Avg output tokens | 10 |
| Total input | 2.5M tokens |
| Total output | 308K tokens |
| **Claude Haiku input cost** | $0.62 |
| **Claude Haiku output cost** | $0.38 |
| **Total** | **~$1.00** |

---

## Implementation Steps

1. **Extract** — Filter CSV to our tickers + date range
2. **Score** — Batch process through Haiku API
3. **Aggregate** — Calculate weekly scores per ticker
4. **Export** — Save as `historical_sentiment.json`
5. **Integrate** — Update `historical_scores.py` to use real data
6. **Backtest** — Re-run and validate alpha

---

## Success Criteria

- [ ] 30k headlines scored
- [ ] Weekly sentiment scores for 598 tickers
- [ ] Backtest shows improved returns vs baseline
- [ ] Positive alpha over SPY (target: >5%)
- [ ] Sharpe ratio > 0.5

---

## Files

| File | Purpose |
|------|---------|
| `kaggle_sentiment/analyst_ratings_processed.csv` | Source data (historical) |
| `backend/src/backtest/sentiment_scorer.py` | Haiku scoring pipeline |
| `backend/data/historical_sentiment.json` | Generated scores |
| `backend/src/backtest/historical_scores.py` | Integration point |

---

## Timeline

| Phase | Duration | Status |
|-------|----------|--------|
| Kaggle data acquisition | Done | ✅ |
| Pipeline development | 1 hour | 🔄 Pending |
| Scoring run | 2-3 hours | ⏳ |
| Integration + backtest | 30 min | ⏳ |
| Polygon.io integration | Future | 📅 REC-213 |

---

## Related Tickets

| Ticket | Description | Status |
|--------|-------------|--------|
| REC-206 | Download Kaggle dataset | ✅ Done |
| REC-207 | Data parsing + ticker mapping | Backlog |
| REC-208 | News provider abstraction | Backlog |
| REC-209 | Sentiment generation script | Backlog |
| REC-210 | Backtest integration | Backlog |
| REC-213 | Polygon.io integration | Future |

---

*Document maintained by: Blaze Neon (AI Engineer)*
