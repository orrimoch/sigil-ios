<img src="sigil_logo.jpg" alt="Sigil" width="240" />

# Sigil iOS — Product Requirements Document

**Project:** iOS Stock Trading App with AI-Powered Recommendations  
**Author:** Blaze Neon  
**Date:** February 2, 2026  
**Version:** 1.0  
**Status:** Research Phase  

---

## Brand Identity

**Name:** Sigil  
**Logo:** The Sigil logo features a hexagonal mark with circuit-board patterns and an upward-pointing arrow motif, symbolizing growth, technology, and data-driven decision-making. The wordmark "Sigil" uses a tech-inspired typeface with integrated circuit traces.

<img src="sigil_logo.jpg" alt="Sigil Logo" width="450" />

**Mark:** The hexagonal icon represents the intersection of technology and financial markets — circuit nodes for data processing, the arrow for upward momentum.  
**Colors:** Navy blue and dark tones, reinforcing trust, sophistication, and professionalism.  
**App Icon:** The standalone hexagonal mark on a dark (#0D0D0F) background.

---

## Executive Summary

This document outlines the product vision for an iOS trading application that combines predictive modeling and AI-powered recommendations for US large-cap stocks (NASDAQ + NYSE, market cap > $10B). The system integrates company earnings, macroeconomic indicators, and news sentiment to generate weekly stock scores — ranking opportunities while forecasting expected performance. Trading execution via Interactive Brokers API.

**Key Features:**

- Predictive scoring model combining fundamentals, sentiment, macro, and technicals
- Weekly stock rankings with actionable buy/hold/sell signals
- Score explainability — transparent breakdown of why each stock ranks where it does
- Real-time portfolio tracking and execution
- Paper trading and real money modes
- Risk management and position sizing
- Performance analytics and backtesting

---

## Problem Statement

### The Problem

Individual investors lack access to institutional-grade quantitative analysis. They face:

- Information overload from countless news sources and stock tips
- No systematic way to rank opportunities across the entire market
- Emotional decision-making leading to poor timing
- Complex tools designed for professionals, not retail investors

### The Opportunity

Democratize quantitative trading strategies by providing:

- Automated data collection and analysis
- Simple, explainable stock scores
- Disciplined, rule-based recommendations
- Set-and-forget portfolio management

---

## Target User

**"The Busy Builder"** — Our ideal user is a high-tech professional, 30-40 years old, navigating the demands of a hectic career while wanting their wealth to grow intelligently in the background. They're sophisticated enough to understand markets but too busy (and too smart) to day-trade. They appreciate elegant design, data-driven decisions, and tools that respect their time. They don't want to babysit their portfolio — they want to set intelligent parameters and let their money work for them while they focus on building the next big thing.

### User Characteristics

- High-tech professional (engineer, PM, founder)
- Age 30-40
- Investable assets: $25K-$500K
- Time available: 5-10 minutes per week
- Sophistication: Understands markets, P/E ratios, basic technicals
- Goal: Passive wealth growth, not active trading

### User Needs

1. **Glanceable insights** — What should I do this week?
2. **Confidence** — Why is this stock recommended?
3. **Simplicity** — One app, clear actions, no noise
4. **Trust** — Professional, accurate, reliable
5. **Time efficiency** — Setup once, check weekly

---

## Vision & Goals

### Vision

Make institutional-grade analysis available to individual investors through an elegant, time-efficient mobile experience.

### Primary Goals

1. **Accessibility** — Democratize quantitative trading strategies
2. **Transparency** — Explain why each stock receives its score
3. **Automation** — Weekly updates with optional automated execution
4. **Risk Management** — Built-in position sizing and portfolio diversification

### Success Criteria

| Metric                  | Target                |
| ----------------------- | --------------------- |
| Alpha over S&P 500      | > 0% (beat benchmark) |
| Sharpe Ratio            | > 1.5                 |
| Maximum Drawdown        | < 20%                 |
| User Retention (30-day) | > 60%                 |
| Weekly Active Users     | Growing MoM           |
| User Satisfaction       | > 4.5/5               |

---

## Core User Flows

### Flow 1: First Launch (60 seconds)

```
Open App → Welcome Screen → Score System Explained (skip available)
→ Portfolio Size Selection → Paper Trading Enabled → See Top Picks
```

**Goal:** User understands the app and sees value within 60 seconds.

### Flow 2: Weekly Check-In (30 seconds)

```
Open App → Dashboard shows portfolio status
→ See "Actions This Week" (buy/sell recommendations)
→ Tap to drill into any recommendation → Execute or dismiss
```

**Goal:** User knows what to do in under 30 seconds.

### Flow 3: Execute a Trade (3 taps)

```
View Recommendation → Tap "Buy" → Confirm → Done
```

**Goal:** Frictionless execution when user decides to act.

### Flow 4: Understand a Score (10 seconds)

```
Tap any stock → See score breakdown
→ Fundamentals: 88, Sentiment: 75, Macro: 60, Technical: 82
→ Plain English summary: "Strong fundamentals, positive news momentum"
```

**Goal:** User understands WHY without reading a report.

---

## Feature Overview

### MVP Features (Phase 1-5)

| Feature             | Priority | Description                                                                                                   |
| ------------------- | -------- | ------------------------------------------------------------------------------------------------------------- |
| Stock Scores        | P0       | Weekly ranking of ~800 US large-cap stocks (0-100) with signals: 🟢 BUY (≥70), 🟡 HOLD (40-69), 🔴 SELL (<40) |
| Score Breakdown     | P0       | Explainable components for each score                                                                         |
| Portfolio Dashboard | P0       | Track holdings, P&L, daily changes                                                                            |
| Paper Trading       | P0       | Practice mode with virtual money                                                                              |
| Buy/Sell Signals    | P1       | Clear action recommendations                                                                                  |
| Position Sizing     | P1       | Automatic allocation suggestions                                                                              |
| Push Notifications  | P2       | Weekly score updates, significant changes                                                                     |

### Post-MVP Features (Phase 6+)

| Feature            | Priority | Description                          |
| ------------------ | -------- | ------------------------------------ |
| Live Trading       | P1       | Real money via IBKR integration      |
| Advanced Analytics | P2       | Backtesting, performance attribution |
| Watchlists         | P2       | Custom stock lists                   |
| Alerts             | P3       | Price/score threshold notifications  |
| Social Features    | P3       | Share picks, follow strategies       |

---

## Scope Boundaries

### In Scope

- US-listed stocks (NASDAQ + NYSE) with market cap > $10B (~800 stocks)
- Long positions only (no shorting)
- Weekly rebalancing cadence
- iOS app only (no Android, no web)
- Interactive Brokers for execution
- US market only

### Out of Scope (MVP)

- Options, futures, crypto
- International markets
- Intraday trading
- Real-time streaming prices
- Social/community features
- Android or web versions

### Future Considerations

- Expand to NASDAQ 100, Russell 2000
- Add options strategies (covered calls)
- Android version
- Web dashboard for deeper analysis

---

## Monetization (Future)

### Potential Models

1. **Freemium** — Paper trading free, live trading subscription
2. **Subscription** — $9.99/mo or $99/yr for full access
3. **Tiered** — Free (5 scores), Pro (all scores + execution)

### MVP Approach

- No monetization in MVP
- Focus on product-market fit
- Validate that scores generate alpha

---

## Competitive Landscape

| Competitor    | Strength              | Weakness                    | Our Differentiation         |
| ------------- | --------------------- | --------------------------- | --------------------------- |
| Robinhood     | Easy UX, free trading | No analysis, gamified       | Data-driven recommendations |
| Bloomberg     | Deep data             | $25K/year, complex          | Accessible, mobile-first    |
| Seeking Alpha | Good analysis         | Crowdsourced, noisy         | Systematic, algorithmic     |
| Morningstar   | Trusted ratings       | Slow updates, passive focus | Weekly active management    |

---

## Risks & Mitigations

| Risk                  | Impact            | Mitigation                                       |
| --------------------- | ----------------- | ------------------------------------------------ |
| Model underperforms   | Users churn       | Paper trading first, transparent backtests       |
| IBKR API changes      | Execution breaks  | Abstract broker layer, monitor API versions      |
| Data source goes paid | Pipeline breaks   | Multiple fallback sources, cache aggressively    |
| Regulatory issues     | App removed       | SEC/FINRA compliant disclosures, not advice      |
| User makes bad trades | Reputation damage | Clear disclaimers, education, paper mode default |

---

## Timeline Summary

| Phase | Weeks | Milestone                                   |
| ----- | ----- | ------------------------------------------- |
| 1     | 1-4   | Data pipeline working, scores calculating   |
| 2     | 5-8   | iOS app displaying scores, basic navigation |
| 3     | 9-10  | Scoring model V1, explainability            |
| 4     | 11-13 | Paper trading functional                    |
| 5     | 14-16 | MVP launch (TestFlight), bug fixes          |
| 6     | 17-22 | Model improvements, live trading            |
| 7     | 23+   | Advanced features, scale                    |

---

## Appendix: Regulatory Disclosures Required

The app must include:

- "Not financial advice" disclaimer
- Past performance disclaimer
- Risk of loss acknowledgment
- IBKR is executing broker disclosure
- No guarantee of results

---

*This PRD is the source of truth for product decisions.*

**Related Docs:**

- `02_TECHNICAL_SPEC.md` — Architecture, APIs, data models
- `03_DESIGN_UX_SPEC.md` — Wireframes, colors, interactions
- `04_ANALYTICS_PLAN.md` — Metrics, events, dashboards
- `05_FEATURE_SPEC.md` — All 45 features with acceptance criteria
