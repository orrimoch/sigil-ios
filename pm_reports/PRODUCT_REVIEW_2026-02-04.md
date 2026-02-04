# Sigil Product Report — February 4, 2026

## Status: 🟡 At Risk

**At risk** due to 2 unresolved MEDIUM bugs, authentication not wired as a gate (`AUTH_REQUIRED=False`), and the last remaining feature (REC-84 BERT sentiment) having significant quality gaps with the current keyword fallback. The app is functionally ~98% complete and builds/tests clean, but not yet launch-ready.

---

## Executive Summary

Sigil is 49/50 features implemented. The iOS app builds with zero errors, the backend passes 298 unit tests, and the last sprint shipped 5 major features (IBKR live trading, weekly notifications, biometric auth, score alerts, per-user data isolation). QA found 23 bugs across those 5 features — all CRITICAL and HIGH bugs have been fixed and verified. 4 MEDIUM bugs remain deferred. The sole remaining feature (REC-84: BERT sentiment analysis) is the biggest quality gap: keyword-based sentiment fails for 420/677 stocks (~62%), directly impacting our core value prop of "AI-powered recommendations."

---

## Key Metrics (This Period)

| Metric | Value |
|--------|-------|
| Features shipped (last sprint) | 5 |
| Features complete (total) | 49/50 (98%) |
| Features remaining | 1 (REC-84 BERT Sentiment) |
| Open bugs | 4 remaining (0 CRITICAL, 0 HIGH, 4 MEDIUM) |
| Bugs fixed this sprint | 19 (2 CRITICAL, 5 HIGH, 7 MEDIUM, 5 LOW) |
| Backend test suite | ✅ 298 passed, 0 failed |
| iOS build | ✅ BUILD SUCCEEDED (0 errors, 0 warnings) |
| Backend test coverage | ~250+ unit tests across all modules |

---

## What Shipped (Last Sprint)

| # | Ticket | Feature | Impact |
|---|--------|---------|--------|
| 1 | **REC-91** | IBKR Live Trading OAuth | Users can connect real brokerage accounts. OAuth flow, risk disclosure, paper/live detection. |
| 2 | **REC-81** | Weekly Score Notifications | Sunday 7pm EST push notification with BUY/HOLD/SELL counts. Dynamic content from API. |
| 3 | **REC-89** | Biometric Authentication | Face ID/Touch ID + PIN fallback. 3-tier lockout escalation (30s → 5min → wipe). |
| 4 | **REC-94** | Score Alert Notifications | Watchlist-based alerts when stocks change signals. Batched notifications for >3 changes. |
| 5 | **REC-92** | Per-User Data Isolation | SQLite-backed per-user portfolios, positions, and orders. Anonymous fallback for no-auth mode. |

**Also shipped:** Bug fix commit resolving all 15 CRITICAL/HIGH/some MEDIUM bugs found during QA across those 5 features.

---

## Feature Completion vs PRD

### By Module

| Module | Features | Complete | Status |
|--------|----------|----------|--------|
| M1: Data Pipeline | 6 | 6/6 | ✅ Done |
| M2: Scoring System | 6 | 5/6 | ⚠️ F2.2 Sentiment using keyword fallback |
| M3: iOS Core | 3 | 3/3 | ✅ Done |
| M4: Home Dashboard | 4 | 4/4 | ✅ Done |
| M5: Scores | 5 | 5/5 | ✅ Done |
| M6: Trading | 4 | 4/4 | ✅ Done |
| M7: Portfolio | 3 | 3/3 | ✅ Done |
| M8: Settings | 4 | 4/4 | ✅ Done |
| M9: Notifications | 3 | 3/3 | ✅ Done |
| M10: API Endpoints | 4 | 4/4 | ✅ Done |
| M11: Auth & Security | 4 | 4/4 | ✅ Done |
| M12: Quality of Life | 4 | 4/4 | ✅ Done |
| **Total** | **50** | **49/50** | **98%** |

### The Gap: F2.2 Sentiment Score (REC-84)

The spec defines two tiers for sentiment:
- **MVP:** Keyword-based (currently implemented via `SENTIMENT_MODEL = "keyword"`)
- **Phase 6:** FinBERT model

**Current state:** Keyword sentiment is technically "implemented" but has significant quality issues:
- Only works for stocks with recent news headlines
- **420/677 stocks (~62%) get no sentiment signal** — keyword matching finds no relevant headlines
- Stocks without sentiment data get a neutral 50 score, diluting the composite score's accuracy
- The scoring system was tuned (REC-84 commit) to produce BUY/SELL signals, but the underlying sentiment data is weak

**Impact on core value prop:** Our pitch is "AI does the research." Keyword matching isn't AI — it's string matching. For 62% of our universe, the "sentiment" component is a meaningless 50/100. This directly affects:
- Score accuracy and user trust
- The quality of BUY/HOLD/SELL signals
- Our differentiation vs. competitors

---

## Open Bugs Summary

### Fixed This Sprint: 19/23

| Severity | Found | Fixed | Remaining |
|----------|-------|-------|-----------|
| 🔴 CRITICAL | 2 | 2 | 0 |
| 🟠 HIGH | 5 | 5 | 0 |
| 🟡 MEDIUM | 7 | 3 | **4** |
| 🔵 LOW | 9 | 9 | 0 |
| **Total** | **23** | **19** | **4** |

### Remaining MEDIUM Bugs (deferred)

| Bug ID | Description | Feature | Risk |
|--------|-------------|---------|------|
| BUG-081-002 | No notification tap handler → Scores tab navigation | REC-81 | User taps notification, nothing happens. Poor UX but not broken. |
| BUG-081-003 | Stale notification content (updated only on app launch) | REC-81 | If user doesn't open app for a week, notification shows old data. Needs push notification architecture (APNs) for proper fix. |
| BUG-089-001 | `performWipe()` doesn't clear PIN/IBKR from Keychain | REC-89 | After security wipe, sensitive credentials persist. **Arguably HIGH** for a security feature. |
| BUG-089-002 | `biometricType` detected once, never refreshed | REC-89 | If user enables Face ID after first launch, won't show biometric option until restart. |

**Recommendation:** BUG-089-001 should be re-classified as HIGH and fixed before launch — a security wipe that doesn't actually wipe credentials is a trust violation.

---

## Backlog Review

### Only One Ticket Remains: REC-84 (BERT Sentiment)

| | |
|---|---|
| **Ticket** | REC-84 |
| **Feature** | F2.2 Sentiment Score — FinBERT upgrade |
| **Current State** | Keyword matching (MVP fallback) |
| **Target** | FinBERT or equivalent NLP model |
| **Effort** | L-XL (3-7 days) |
| **Impact** | HIGH — affects 62% of stock scores |
| **Dependencies** | Model selection, hosting (local vs API), inference latency |

### Options for REC-84

| Option | Effort | Quality | Cost |
|--------|--------|---------|------|
| **A) Ship with keyword** | 0 days | Poor (62% miss rate) | Free |
| **B) FinBERT local** | 5-7 days | Good | Free (CPU inference) |
| **C) OpenAI/Claude API** | 2-3 days | Excellent | ~$50-100/month |
| **D) Pre-trained sentiment API** (e.g. Finnhub sentiment) | 1-2 days | Good | Free tier available |

**Recommendation:** Option D as quick win (1-2 days), then Option B for full control. Don't ship with keyword-only — it undermines the "AI" positioning.

---

## What's Next (Prioritized)

### P0 — Must Do Before Launch

| # | Task | Effort | Why |
|---|------|--------|-----|
| 1 | **Fix BUG-089-001** (Keychain wipe) | S (hours) | Security wipe must actually wipe. Trust issue. |
| 2 | **Upgrade sentiment model** (REC-84) | M-L (2-5 days) | 62% miss rate on core feature is not shippable. |
| 3 | **Wire AUTH_REQUIRED=True** | M (1-2 days) | Auth system exists but isn't gated. Must decide: ship with auth or without. |
| 4 | **Fix BUG-081-002** (notification deep link) | S (hours) | Notification that does nothing on tap is embarrassing. |

### P1 — Should Do Before Launch

| # | Task | Effort | Why |
|---|------|--------|-----|
| 5 | **Integration test pass** | M (1-2 days) | Full E2E walkthrough: onboarding → scores → trade → portfolio → settings |
| 6 | **Fix BUG-089-002** (biometric refresh) | S (hours) | Edge case but easy fix. |
| 7 | **Fix BUG-081-003** (notification staleness) | L (3-5 days) | Requires APNs setup — may defer to post-launch. |
| 8 | **TestFlight beta** | M (1-2 days) | Internal testing before public launch. |

### P2 — Post-Launch

| # | Task | Effort |
|---|------|--------|
| 9 | Push notifications (APNs) to replace local notifications | L |
| 10 | Analytics/telemetry integration | M |
| 11 | App Store listing, screenshots, description | M |
| 12 | Performance optimization (cold start, API caching) | M |

---

## Metrics Readiness Assessment

### Can We Measure Our KPIs at Launch?

| Metric | Measurable Now? | What's Needed |
|--------|----------------|---------------|
| **WAU-Scores** (North Star) | ❌ No | Analytics SDK (Mixpanel/Amplitude/PostHog) not integrated |
| DAU/WAU ratio | ❌ No | Needs analytics SDK |
| Session duration | ❌ No | Needs analytics SDK |
| Scores Tab views/week | ❌ No | Needs event tracking |
| Score-to-Trade rate | ⚠️ Partial | Can calculate from backend order logs, but no frontend funnel tracking |
| Notification open rate | ❌ No | Needs APNs + analytics |
| Retention D7/D30 | ❌ No | Needs analytics SDK |
| Avg Trades/Week | ✅ Yes | Backend order table has timestamps per user |
| Paper→Live conversion | ✅ Yes | Backend tracks IBKR connection status |
| Portfolio Win Rate | ⚠️ Partial | Can backtest, no live tracking yet |
| App Crash Rate | ❌ No | Needs Crashlytics/Sentry |
| API Error Rate | ⚠️ Partial | Backend logs exist, no dashboard |
| Score Accuracy | ⚠️ Partial | Can compute historically, no automated tracking |

**Verdict:** We can measure almost nothing at launch. **Analytics is a critical gap.** Without telemetry, we're flying blind — can't validate product-market fit, can't measure the North Star metric, can't track retention.

**Recommendation:** Integrate a lightweight analytics SDK (PostHog or Mixpanel) before launch. This is 2-3 days of work but essential for knowing if the product is working.

---

## Decisions Needed from Or

### 1. Auth Gate: Ship with or without?
- `AUTH_REQUIRED=False` currently — auth exists (JWT + biometric) but isn't enforced
- **Option A:** Ship without auth (simpler, faster to test, but all data is shared as "anonymous")
- **Option B:** Enable auth gate (login required, per-user data isolation works properly)
- **Recommendation:** Option B. We built per-user isolation specifically for this. Ship it.

### 2. Sentiment Model: What's acceptable for launch?
- Keyword matching fails for 62% of stocks
- Do we ship with degraded sentiment, or block launch on a better model?
- **Recommendation:** Block on at minimum a sentiment API integration (2-3 days). The "AI" positioning requires actual AI.

### 3. Analytics: Pre-launch or post-launch?
- No telemetry exists. We can't measure any engagement KPIs.
- **Recommendation:** Pre-launch. 2-3 days. Non-negotiable for knowing if the product works.

### 4. Launch Scope: TestFlight beta first, or straight to App Store?
- **Recommendation:** TestFlight beta for 1-2 weeks with 5-10 users, then App Store.

### 5. Monetization: Free at launch?
- PRD says "no monetization in MVP — focus on product-market fit"
- **Recommendation:** Align. Ship free, validate scores generate alpha, then introduce subscription.

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation | Status |
|------|-----------|--------|------------|--------|
| **Sentiment quality undermines trust** | HIGH | HIGH | Upgrade to real NLP model before launch | 🔴 Open |
| **No analytics = flying blind** | HIGH | HIGH | Integrate PostHog/Mixpanel pre-launch | 🔴 Open |
| **Auth not enforced** | MEDIUM | HIGH | Flip `AUTH_REQUIRED=True`, test E2E | 🟡 Decision needed |
| **Keychain wipe incomplete** | LOW | HIGH | Fix BUG-089-001 (hours of work) | 🟡 Deferred |
| **Data source reliability** (yfinance) | MEDIUM | MEDIUM | Fallback sources identified in spec | 🟢 Mitigated |
| **IBKR API changes** | LOW | HIGH | Abstraction layer in place | 🟢 Mitigated |
| **Notification staleness** | MEDIUM | LOW | Needs APNs — defer to post-launch | 🟡 Accepted |
| **Regulatory compliance** | MEDIUM | HIGH | Disclaimers exist in code but need legal review | 🟡 Not validated |
| **Model underperformance** | MEDIUM | HIGH | Paper trading default, backtesting available | 🟢 Mitigated |

---

## Launch Readiness Assessment

### Scorecard

| Category | Score | Notes |
|----------|-------|-------|
| Feature completeness | 🟢 98% | 49/50, only BERT sentiment remains |
| Build health | 🟢 Clean | 0 errors, 0 warnings |
| Test coverage | 🟢 Strong | 298 backend tests, iOS tests passing |
| Bug status | 🟡 Good | 0 CRITICAL/HIGH, 4 MEDIUM remaining |
| Scoring quality | 🔴 Weak | 62% of stocks have no real sentiment data |
| Authentication | 🟡 Partial | Built but not enforced as gate |
| Analytics/telemetry | 🔴 None | Can't measure any engagement KPI |
| Regulatory disclosures | 🟡 Partial | In code, not legally reviewed |
| App Store readiness | 🔴 Not started | No screenshots, description, or listing |

### Verdict: NOT READY for public launch. READY for internal TestFlight with fixes.

**Estimated time to launch-ready:** 2-3 weeks

| Week | Focus |
|------|-------|
| **Week 1** | Fix remaining MEDIUMs, upgrade sentiment model, enable auth gate |
| **Week 2** | Analytics integration, integration test pass, TestFlight beta |
| **Week 3** | Beta feedback, App Store prep, legal review of disclaimers |

---

## Recommendation

**Ship to TestFlight in 1 week, App Store in 3 weeks.**

The app is architecturally sound and feature-complete. The sprint velocity has been excellent (5 features + 19 bug fixes). But three gaps prevent a confident public launch:

1. **Sentiment quality** — The "AI" in "AI Market Intelligence" needs to be real. Fix REC-84.
2. **Analytics** — Without telemetry, we can't tell if the product is working. Integrate before launch.
3. **Auth gate** — The per-user isolation we built doesn't matter if everyone is "anonymous." Flip the switch.

Fix these three, and Sigil is ready to ship.

---

*Report generated: February 4, 2026*
*Next review: February 11, 2026*
*PM Agent — Sigil Product Team*
