<img src="sigil_logo.jpg" alt="Sigil" width="240" />

# Sigil iOS — Analytics & Instrumentation Plan

**Project:** iOS Stock Trading App with AI-Powered Recommendations  
**Author:** Blaze Neon  
**Date:** February 2, 2026  
**Version:** 1.0  

---

## Table of Contents

1. [Success Metrics](#success-metrics)
2. [Event Tracking](#event-tracking)
3. [Performance Attribution](#performance-attribution)
4. [Model Metrics](#model-metrics)
5. [Testing Strategy](#testing-strategy)
6. [Dashboards](#dashboards)

---

## Success Metrics

### North Star Metrics

| Metric | Definition | Target |
|--------|------------|--------|
| **Recommendation Alpha** | Return of rec-driven trades vs S&P 500 | > 0% |
| **Weekly Active Users** | Users who open app at least once/week | Growing MoM |
| **Follow-Through Rate** | % of BUY signals acted on | > 30% |

### Business Metrics

| Metric | Target | Phase |
|--------|--------|-------|
| User Retention (7-day) | > 40% | MVP |
| User Retention (30-day) | > 25% | MVP |
| App Store Rating | > 4.5 | Post-MVP |
| Crash-Free Sessions | > 99.5% | MVP |
| Average Session Duration | > 30s | MVP |

### Product Health Metrics

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| App Launch Time | < 2s | > 3s |
| API Response Time (p95) | < 200ms | > 500ms |
| Pipeline Success Rate | 100% | < 100% |
| Score Calculation Time | < 5 min | > 15 min |

### Phase-Specific Metrics

| Phase | Key Metric | Target |
|-------|------------|--------|
| **Phase 1** | Pipeline success rate | 100% |
| **Phase 2** | App crash rate | 0% |
| **Phase 2** | UI frame rate | 60fps |
| **Phase 3** | Score sanity check | Pass manual review |
| **Phase 4** | Order success rate | > 99% |
| **Phase 5** | User-reported bugs | < 5 |
| **Phase 6** | Model IC (Information Coefficient) | > 0.05 |
| **Phase 6** | Backtest Sharpe Ratio | > 1.0 |

---

## Event Tracking

### Core Events

#### App Lifecycle
| Event | Properties | Trigger |
|-------|------------|---------|
| `app_launch` | `source`, `is_first_launch` | App opens |
| `app_background` | `session_duration` | App backgrounded |
| `app_terminate` | `session_duration` | App killed |

#### Onboarding
| Event | Properties | Trigger |
|-------|------------|---------|
| `onboarding_start` | — | First screen shown |
| `onboarding_skip` | `screen_number` | Skip button tapped |
| `onboarding_complete` | `portfolio_size_selected` | Final screen completed |
| `onboarding_drop_off` | `last_screen` | App closed during onboarding |

#### Score Browsing
| Event | Properties | Trigger |
|-------|------------|---------|
| `scores_viewed` | `filter`, `sort_by` | Scores screen loaded |
| `stock_detail_viewed` | `ticker`, `score`, `signal` | Stock detail opened |
| `score_breakdown_viewed` | `ticker` | Breakdown section expanded |
| `score_history_viewed` | `ticker`, `period` | History chart viewed |

#### Trading
| Event | Properties | Trigger |
|-------|------------|---------|
| `trade_initiated` | `ticker`, `side`, `quantity`, `is_paper` | Trade flow started |
| `trade_confirmed` | `ticker`, `side`, `quantity`, `order_type` | Order submitted |
| `trade_completed` | `ticker`, `fill_price`, `latency_ms` | Order filled |
| `trade_cancelled` | `ticker`, `reason` | Order cancelled |
| `trade_error` | `ticker`, `error_code`, `error_message` | Order failed |

#### Portfolio
| Event | Properties | Trigger |
|-------|------------|---------|
| `portfolio_viewed` | `position_count`, `total_value` | Portfolio screen loaded |
| `position_detail_viewed` | `ticker`, `pnl_percent` | Position tapped |

#### Settings
| Event | Properties | Trigger |
|-------|------------|---------|
| `setting_changed` | `setting_name`, `old_value`, `new_value` | Any setting modified |
| `paper_to_live_switch` | — | User enables live trading |
| `ibkr_connected` | `account_type` | IBKR auth completed |

### Event Properties (Global)

Include with every event:
```json
{
  "user_id": "anonymous_uuid",
  "session_id": "session_uuid",
  "timestamp": "2026-02-02T12:00:00Z",
  "app_version": "1.0.0",
  "os_version": "17.2",
  "device_model": "iPhone 15 Pro",
  "is_paper_mode": true
}
```

### Analytics SDK

**Recommended:** Amplitude or Mixpanel (free tier sufficient for MVP)

```swift
// Example: Amplitude integration
Analytics.track("stock_detail_viewed", properties: [
    "ticker": "AAPL",
    "score": 85,
    "signal": "buy",
    "source": "scores_list"
])
```

---

## Performance Attribution

### Why Separate Tracking?

To prove the recommendation system adds value, track performance separately for:
1. **Recommendation-driven trades** — User followed the system's signal
2. **User-initiated trades** — User's own decisions

### Trade Classification Rules

```
┌─────────────────────────────────────────────────────────────────┐
│                    TRADE ATTRIBUTION                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   RECOMMENDATION-DRIVEN                                         │
│   • User bought stock with score ≥ 70 (BUY signal)             │
│   • User sold stock with score < 40 (SELL signal)              │
│   • Trade executed within 7 days of signal                      │
│                                                                 │
│   USER-INITIATED                                                │
│   • User bought stock with score < 70                          │
│   • User held despite SELL signal                               │
│   • User's own picks outside recommendations                    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Attribution Data Model

```python
@dataclass
class Trade:
    ticker: str
    action: str              # 'buy' or 'sell'
    quantity: int
    price: float
    timestamp: datetime
    
    # Attribution
    score_at_trade: int
    signal_at_trade: str     # 'BUY', 'HOLD', 'SELL'
    attribution: str         # 'recommendation' or 'user_initiated'
    days_since_signal: int
```

### Performance Dashboard

Track separately:

| Metric | Recommendation | User-Initiated |
|--------|----------------|----------------|
| Trade Count | — | — |
| Win Rate | — | — |
| Total Return | — | — |
| Sharpe Ratio | — | — |
| Avg Win | — | — |
| Avg Loss | — | — |

**Value Add = Recommendation Return − User Return**

---

## Model Metrics

### Scoring Model Quality

| Metric | Definition | Target |
|--------|------------|--------|
| **Information Coefficient (IC)** | Correlation between score and forward returns | > 0.05 |
| **Hit Rate** | % of BUY signals that beat benchmark | > 55% |
| **Signal Stability** | Week-over-week score volatility | Low |
| **Coverage** | % of universe with valid scores | 100% |

### Backtesting Metrics

| Metric | Definition | Target |
|--------|------------|--------|
| **CAGR** | Compound annual growth rate | > S&P 500 |
| **Sharpe Ratio** | Risk-adjusted return | > 1.0 |
| **Max Drawdown** | Largest peak-to-trough decline | < 20% |
| **Sortino Ratio** | Downside risk-adjusted return | > 1.5 |
| **Calmar Ratio** | CAGR / Max Drawdown | > 0.5 |

### Sentiment Model Quality

| Metric | Definition | Target |
|--------|------------|--------|
| **Accuracy** | Correct sentiment classification | > 70% |
| **Latency** | Time to score one article | < 100ms |
| **Coverage** | % of articles successfully scored | > 95% |

---

## Testing Strategy

### Test Types by Phase

| Phase | Unit | UI | Integration | Acceptance |
|-------|------|----|----|------------|
| 1 | ✅ Pipeline, API | — | ✅ Full pipeline | — |
| 2 | ✅ ViewModels | ✅ Screens | ✅ Backend ↔ iOS | — |
| 3 | ✅ Scoring | — | — | Sanity check |
| 4 | ✅ Trading | ✅ Order flow | ✅ E2E trade | — |
| 5 | Regression | Regression | Regression | ✅ **MVP Checklist** |
| 6 | ✅ ML models | — | ✅ Backtest | — |

### Test Triggers

| Trigger | What to Run |
|---------|-------------|
| Every commit | Unit tests (fast) |
| Every PR | Unit + UI tests |
| Before merge | Full test suite |
| Weekly (Sunday) | Integration + pipeline |
| Before release | Full regression + acceptance |

### Coverage Targets

| Component | Target |
|-----------|--------|
| Data pipeline | 90%+ |
| API endpoints | 90%+ |
| Score calculations | 100% |
| iOS ViewModels | 80%+ |
| iOS UI flows | All critical paths |

### MVP Acceptance Checklist

Before MVP launch, verify:

| # | Check | Status |
|---|-------|--------|
| 1 | App launches without crashing | ☐ |
| 2 | Pipeline runs successfully (3 weeks in a row) | ☐ |
| 3 | Scores display correctly for all 400 stocks | ☐ |
| 4 | Score breakdown UI works | ☐ |
| 5 | Paper trade flow completes | ☐ |
| 6 | Portfolio shows correct positions | ☐ |
| 7 | Push notifications work | ☐ |
| 8 | No critical bugs in TestFlight | ☐ |

---

## Dashboards

### Operations Dashboard

**Tools:** Grafana + Prometheus

| Panel | Metrics |
|-------|---------|
| Pipeline Status | Last run time, success/fail, duration |
| API Health | Request count, latency (p50, p95, p99), error rate |
| Database | Query latency, connection pool, storage |
| Cache | Hit rate, memory usage |

### Product Dashboard

**Tools:** Amplitude / Mixpanel

| Panel | Metrics |
|-------|---------|
| Daily Active Users | DAU trend, cohort retention |
| Feature Usage | Scores viewed, trades executed, detail views |
| Funnel | Onboarding completion, trade conversion |
| Errors | Crash rate, error events |

### Model Dashboard

**Tools:** Custom + Grafana

| Panel | Metrics |
|-------|---------|
| Score Distribution | Histogram of scores, signal breakdown |
| Model Performance | IC over time, hit rate, backtest returns |
| Data Quality | Missing data, outliers, freshness |
| Attribution | Rec vs user performance comparison |

### Alert Rules

| Condition | Severity | Action |
|-----------|----------|--------|
| Pipeline failed | Critical | Page on-call |
| API error rate > 5% | High | Slack alert |
| Score calculation > 30 min | Medium | Slack alert |
| App crash spike | High | Slack alert |
| Model IC < 0.02 | Low | Review next week |

---

## Data Retention

| Data Type | Retention |
|-----------|-----------|
| Event logs | 90 days (raw), 2 years (aggregated) |
| Price history | Indefinite |
| Score history | 2 years |
| Trade history | Indefinite (legal requirement) |
| User PII | Until account deletion |

---

**Related Docs:**
- `01_PRD.md` — Product requirements, vision, user flows
- `02_TECHNICAL_SPEC.md` — Architecture, APIs, data models
- `03_DESIGN_UX_SPEC.md` — Wireframes, colors, interactions
- `05_FEATURE_SPEC.md` — All 45 features with acceptance criteria
