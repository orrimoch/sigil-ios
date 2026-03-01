<img src="sigil_logo.jpg" alt="Sigil" width="240" />

# Sigil iOS — Feature Specification

**Version:** 1.0  
**Date:** February 2, 2026  

---

## Overview

This document defines all features with acceptance criteria, organized by module and priority.

**Priority Legend:**

- **P0** — MVP Required (must ship)
- **P1** — MVP Important (should ship)
- **P2** — Post-MVP (nice to have)

---

## Module 1: Data Pipeline (Backend)

### F1.1 Stock Universe Management

|                         |                                                                                                                                                                                       |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Priority**            | P0                                                                                                                                                                                    |
| **Description**         | Maintain list of ~800 US large-cap stocks (NASDAQ + NYSE, market cap > $10B)                                                                                                          |
| **Acceptance Criteria** | • Store ticker, name, sector, market cap<br>• Sources: NASDAQ screener API + S&P 500 Wikipedia fallback<br>• Quarterly refresh<br>• API endpoint: `GET /stocks` returns full universe |

### F1.2 Price Data Fetcher

|                         |                                                                                                                                     |
| ----------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| **Priority**            | P0                                                                                                                                  |
| **Description**         | Fetch daily price data for all stocks                                                                                               |
| **Source**              | Yahoo Finance (yfinance) — FREE                                                                                                     |
| **Acceptance Criteria** | • Daily OHLCV for all ~800 stocks<br>• 5+ years historical data<br>• Runs reliably on schedule<br>• Handles API failures gracefully |

### F1.3 Fundamental Data Fetcher

|                         |                                                                                                                                       |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| **Priority**            | P0                                                                                                                                    |
| **Description**         | Fetch quarterly fundamentals (P/E, EPS, revenue, margins)                                                                             |
| **Source**              | Yahoo Finance / SEC EDGAR — FREE                                                                                                      |
| **Acceptance Criteria** | • P/E, P/B, EPS, revenue, profit margin, debt/equity<br>• Updated after earnings releases<br>• Missing data handled (null, not crash) |

### F1.4 News Fetcher

|                         |                                                                                                                                                                                  |
| ----------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Priority**            | P0                                                                                                                                                                               |
| **Description**         | Fetch news headlines from multiple sources                                                                                                                                       |
| **Sources**             | **RSS (free):** Yahoo Finance, Reuters, MarketWatch, SEC<br>**APIs (free tier):** Alpha Vantage, Finnhub                                                                         |
| **Source Tiers**        | Tier 1 (3x): WSJ, FT *(future)*<br>Tier 2 (2x): Reuters, Alpha Vantage, Finnhub<br>Tier 3 (1x): Yahoo, MarketWatch                                                               |
| **Acceptance Criteria** | • Last 7 days of headlines per stock<br>• Store title, source, date, link, tier<br>• Filter by ticker mention<br>• Deduplication by title<br>• Works without API keys (RSS only) |

### F1.5 Macro Data Fetcher

|                         |                                                                                                    |
| ----------------------- | -------------------------------------------------------------------------------------------------- |
| **Priority**            | P1                                                                                                 |
| **Description**         | Fetch macroeconomic indicators                                                                     |
| **Source**              | FRED — FREE                                                                                        |
| **Acceptance Criteria** | • Fed rate, CPI, GDP, unemployment, VIX<br>• Updated when released<br>• API endpoint: `GET /macro` |

### F1.6 Weekly Pipeline Orchestration

|                         |                                                                                                                                                                              |
| ----------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Priority**            | P0                                                                                                                                                                           |
| **Description**         | Run full pipeline every Sunday 6pm EST                                                                                                                                       |
| **Acceptance Criteria** | • Fetches all data sources<br>• Calculates scores for all stocks<br>• Completes in < 30 minutes<br>• Alerts on failure (Slack/email)<br>• Retry logic for transient failures |

---

## Module 2: Scoring System (Backend)

### F2.1 Fundamental Score

|                         |                                                                                            |
| ----------------------- | ------------------------------------------------------------------------------------------ |
| **Priority**            | P0                                                                                         |
| **Description**         | Score stocks 0-100 based on fundamentals                                                   |
| **Components**          | Value (25%), Quality (35%), Growth (40%)                                                   |
| **Acceptance Criteria** | • Percentile ranking across universe<br>• Handles missing data<br>• Explainable sub-scores |

### F2.2 Sentiment Score

|                         |                                                                                                                     |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------- |
| **Priority**            | P0                                                                                                                  |
| **Description**         | Score stocks 0-100 based on news sentiment                                                                          |
| **Method**              | Claude Haiku Agentic Scoring (live pipeline)                                                                        |
| **Acceptance Criteria** | • Positive/negative/neutral classification<br>• Weighted by recency<br>• Config flag: `SENTIMENT_MODEL = "keyword"` |

### F2.3 Technical Score

|                         |                                                                               |
| ----------------------- | ----------------------------------------------------------------------------- |
| **Priority**            | P1                                                                            |
| **Description**         | Score stocks 0-100 based on price momentum                                    |
| **Components**          | Momentum (40%), RSI (30%), Trend (30%)                                        |
| **Acceptance Criteria** | • MA crossovers detected<br>• RSI calculated correctly<br>• Percentile ranked |

### F2.4 Macro Score

|                         |                                                                         |
| ----------------------- | ----------------------------------------------------------------------- |
| **Priority**            | P1                                                                      |
| **Description**         | Score sector alignment with macro environment                           |
| **Acceptance Criteria** | • Map sectors to macro sensitivity<br>• Adjust scores by current regime |

### F2.5 Composite Score

|                         |                                                                                                                            |
| ----------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| **Priority**            | P0                                                                                                                         |
| **Description**         | Combine all scores into final 0-100 score                                                                                  |
| **Weights**             | Fundamental 35%, Sentiment 25%, Macro 20%, Technical 20%                                                                   |
| **Acceptance Criteria** | • All 400 stocks scored weekly<br>• Signal generated: BUY (≥70), HOLD (40-69), SELL (<40)<br>• API endpoint: `GET /scores` |

### F2.6 Score Explainability

|                         |                                                                                             |
| ----------------------- | ------------------------------------------------------------------------------------------- |
| **Priority**            | P1                                                                                          |
| **Description**         | Generate human-readable explanation for each score                                          |
| **Acceptance Criteria** | • Component breakdown visible<br>• Plain English summary<br>• Week-over-week change drivers |

---

## Module 3: iOS App — Core

### F3.1 App Launch & Onboarding

|                         |                                                                                                                              |
| ----------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| **Priority**            | P0                                                                                                                           |
| **Description**         | First launch experience (4 screens, <60 sec)                                                                                 |
| **Acceptance Criteria** | • Skip button always visible<br>• Score system explained<br>• Portfolio size selection<br>• Paper trading enabled by default |

### F3.2 Daily Quote

|                         |                                                                            |
| ----------------------- | -------------------------------------------------------------------------- |
| **Priority**            | P2                                                                         |
| **Description**         | Show motivational quote on app launch                                      |
| **Acceptance Criteria** | • 50+ quotes in bundle<br>• Random selection<br>• Tappable for attribution |

### F3.3 Tab Navigation

|                         |                                                                                            |
| ----------------------- | ------------------------------------------------------------------------------------------ |
| **Priority**            | P0                                                                                         |
| **Description**         | Bottom tab bar with 5 tabs                                                                 |
| **Tabs**                | Home, Scores, Trade, Portfolio, Settings                                                   |
| **Acceptance Criteria** | • Native iOS tab bar<br>• Badge on Scores when new data<br>• Maintains state on tab switch |

---

## Module 4: iOS App — Home Dashboard

### F4.1 Portfolio Summary Card

|                         |                                                                                                     |
| ----------------------- | --------------------------------------------------------------------------------------------------- |
| **Priority**            | P0                                                                                                  |
| **Description**         | Show total portfolio value and daily P&L                                                            |
| **Acceptance Criteria** | • Large value display (SF Mono, 32pt)<br>• Daily change ($ and %)<br>• Green/red based on direction |

### F4.2 Market Overview

|                         |                                                                                        |
| ----------------------- | -------------------------------------------------------------------------------------- |
| **Priority**            | P1                                                                                     |
| **Description**         | Show major indices (S&P, NASDAQ, DOW, VIX)                                             |
| **Acceptance Criteria** | • Current value + daily change<br>• Updated on pull-to-refresh<br>• Cached for offline |

### F4.3 Top AI Picks

|                         |                                                                                                 |
| ----------------------- | ----------------------------------------------------------------------------------------------- |
| **Priority**            | P0                                                                                              |
| **Description**         | Show top 5 BUY-rated stocks                                                                     |
| **Acceptance Criteria** | • Ticker, score, signal, price, change<br>• Tappable → stock detail<br>• "See All" → Scores tab |

### F4.4 Alerts Feed

|                         |                                                                   |
| ----------------------- | ----------------------------------------------------------------- |
| **Priority**            | P2                                                                |
| **Description**         | Show recent notable events                                        |
| **Acceptance Criteria** | • Score changes > 10 pts<br>• Earnings surprises<br>• Timestamped |

---

## Module 5: iOS App — Scores

### F5.1 Score List

|                         |                                                                                                               |
| ----------------------- | ------------------------------------------------------------------------------------------------------------- |
| **Priority**            | P0                                                                                                            |
| **Description**         | Sortable list of all 400 stocks with scores                                                                   |
| **Acceptance Criteria** | • Columns: Ticker, Score, Signal, Price, Change, Sector<br>• Sort by any column<br>• Filter by sector, signal |

### F5.2 Score Search

|                         |                                                        |
| ----------------------- | ------------------------------------------------------ |
| **Priority**            | P1                                                     |
| **Description**         | Search stocks by ticker or name                        |
| **Acceptance Criteria** | • Instant results as typing<br>• Recent searches saved |

### F5.3 Stock Detail View

|                         |                                                                                                    |
| ----------------------- | -------------------------------------------------------------------------------------------------- |
| **Priority**            | P0                                                                                                 |
| **Description**         | Full detail for a single stock                                                                     |
| **Acceptance Criteria** | • Price + chart (1D, 1W, 1M, 1Y)<br>• Score with breakdown<br>• Signal + rank<br>• Buy/Sell button |

### F5.4 Score Breakdown View

|                         |                                                                                       |
| ----------------------- | ------------------------------------------------------------------------------------- |
| **Priority**            | P1                                                                                    |
| **Description**         | Expandable breakdown of score components                                              |
| **Acceptance Criteria** | • Show 4 components + sub-scores<br>• Visual progress bars<br>• Plain English summary |

### F5.5 Score History Chart

|                         |                                         |
| ----------------------- | --------------------------------------- |
| **Priority**            | P2                                      |
| **Description**         | Show score trend over past 12 weeks     |
| **Acceptance Criteria** | • Line chart<br>• Signal changes marked |

---

## Module 6: iOS App — Trading

### F6.1 Order Entry

|                         |                                                                                                                                  |
| ----------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| **Priority**            | P0                                                                                                                               |
| **Description**         | Submit buy/sell orders                                                                                                           |
| **Acceptance Criteria** | • Quantity input (shares or $)<br>• Market order (MVP)<br>• Limit order (P1)<br>• Preview before submit<br>• Confirmation dialog |

### F6.2 Paper Trading Mode

|                         |                                                                                                                   |
| ----------------------- | ----------------------------------------------------------------------------------------------------------------- |
| **Priority**            | P0                                                                                                                |
| **Description**         | Simulated trading with virtual money                                                                              |
| **Acceptance Criteria** | • Default mode for new users<br>• Clear "PAPER" indicator<br>• Tracks P&L accurately<br>• Can reset paper account |

### F6.3 Live Trading Mode

|                         |                                                                                                                                                   |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Priority**            | P1                                                                                                                                                |
| **Description**         | Real trading via IBKR                                                                                                                             |
| **Acceptance Criteria** | • Requires IBKR OAuth connection<br>• Clear "LIVE" indicator (different color)<br>• Extra confirmation for live trades<br>• Risk disclosure shown |

### F6.4 Order Status

|                         |                                                                                          |
| ----------------------- | ---------------------------------------------------------------------------------------- |
| **Priority**            | P0                                                                                       |
| **Description**         | Show pending/filled/cancelled orders                                                     |
| **Acceptance Criteria** | • List of today's orders<br>• Status updates in real-time<br>• Ability to cancel pending |

---

## Module 7: iOS App — Portfolio

### F7.1 Holdings List

|                         |                                                              |
| ----------------------- | ------------------------------------------------------------ |
| **Priority**            | P0                                                           |
| **Description**         | List of current positions                                    |
| **Columns**             | Ticker, Qty, Avg Cost, Current, P&L $, P&L %, % of Portfolio |
| **Acceptance Criteria** | • Sorted by value or P&L<br>• Tappable → stock detail        |

### F7.2 Portfolio Performance Chart

|                         |                                                                                             |
| ----------------------- | ------------------------------------------------------------------------------------------- |
| **Priority**            | P1                                                                                          |
| **Description**         | Portfolio value over time vs benchmark                                                      |
| **Acceptance Criteria** | • Line chart (1W, 1M, 3M, 1Y, All)<br>• S&P 500 benchmark overlay<br>• Shows total return % |

### F7.3 Sector Allocation

|                         |                                              |
| ----------------------- | -------------------------------------------- |
| **Priority**            | P2                                           |
| **Description**         | Pie/bar chart of sector weights              |
| **Acceptance Criteria** | • Visual breakdown<br>• Comparison to target |

---

## Module 8: iOS App — Settings

### F8.1 Account Settings

|                         |                                                                                                               |
| ----------------------- | ------------------------------------------------------------------------------------------------------------- |
| **Priority**            | P0                                                                                                            |
| **Description**         | User profile and preferences                                                                                  |
| **Acceptance Criteria** | • Portfolio size setting<br>• Risk tolerance (conservative/moderate/aggressive)<br>• Notification preferences |

### F8.2 IBKR Connection

|                         |                                                                                      |
| ----------------------- | ------------------------------------------------------------------------------------ |
| **Priority**            | P1                                                                                   |
| **Description**         | Connect/disconnect IBKR account                                                      |
| **Acceptance Criteria** | • OAuth flow<br>• Connection status indicator<br>• Account type display (paper/live) |

### F8.3 Paper/Live Toggle

|                         |                                                                   |
| ----------------------- | ----------------------------------------------------------------- |
| **Priority**            | P0                                                                |
| **Description**         | Switch between trading modes                                      |
| **Acceptance Criteria** | • Clear warning when switching to live<br>• Requires confirmation |

### F8.4 Notifications

|                         |                                                                                        |
| ----------------------- | -------------------------------------------------------------------------------------- |
| **Priority**            | P1                                                                                     |
| **Description**         | Push notification settings                                                             |
| **Acceptance Criteria** | • Weekly score updates ON/OFF<br>• Trade confirmations ON/OFF<br>• Score alerts ON/OFF |

---

## Module 9: Notifications

### F9.1 Weekly Score Notification

|                         |                                                                               |
| ----------------------- | ----------------------------------------------------------------------------- |
| **Priority**            | P1                                                                            |
| **Description**         | Push notification when new scores available                                   |
| **Timing**              | Sundays ~7pm EST (after pipeline)                                             |
| **Acceptance Criteria** | • "New scores available. 8 BUY signals this week."<br>• Tappable → Scores tab |

### F9.2 Trade Confirmation

|                         |                                                                   |
| ----------------------- | ----------------------------------------------------------------- |
| **Priority**            | P1                                                                |
| **Description**         | Push notification when order filled                               |
| **Acceptance Criteria** | • "AAPL: Bought 10 shares @ $185.42"<br>• Tappable → order detail |

### F9.3 Score Alert

|                         |                                                                                |
| ----------------------- | ------------------------------------------------------------------------------ |
| **Priority**            | P2                                                                             |
| **Description**         | Alert when watched stock changes signal                                        |
| **Acceptance Criteria** | • "AAPL signal changed: HOLD → BUY (score: 72)"<br>• Only for watchlist stocks |

---

## Module 10: API Endpoints

### F10.1 Scores API

|                         |                                                                                   |
| ----------------------- | --------------------------------------------------------------------------------- |
| **Endpoints**           | `GET /scores`, `GET /scores/{ticker}`, `GET /scores/{ticker}/history`             |
| **Priority**            | P0                                                                                |
| **Acceptance Criteria** | • Returns all fields needed by app<br>• Cached (1 hour TTL)<br>• < 200ms response |

### F10.2 Portfolio API

|                         |                                                                |
| ----------------------- | -------------------------------------------------------------- |
| **Endpoints**           | `GET /portfolio`, `GET /portfolio/performance`                 |
| **Priority**            | P0                                                             |
| **Acceptance Criteria** | • Positions, P&L, total value<br>• Historical performance data |

### F10.3 Orders API

|                         |                                                           |
| ----------------------- | --------------------------------------------------------- |
| **Endpoints**           | `POST /orders`, `GET /orders`, `DELETE /orders/{id}`      |
| **Priority**            | P0                                                        |
| **Acceptance Criteria** | • Create, list, cancel orders<br>• Validates against IBKR |

### F10.4 Stocks API

|                         |                                       |
| ----------------------- | ------------------------------------- |
| **Endpoints**           | `GET /stocks`, `GET /stocks/{ticker}` |
| **Priority**            | P0                                    |
| **Acceptance Criteria** | • Universe list<br>• Stock metadata   |

---

## Feature Count Summary

| Priority  | Count | Status        |
| --------- | ----- | ------------- |
| **P0**    | 24    | MVP Required  |
| **P1**    | 14    | MVP Important |
| **P2**    | 7     | Post-MVP      |
| **Total** | 45    |               |

---

## Cross-References

- **Technical details:** `02_TECHNICAL_SPEC.md`
- **UI wireframes:** `03_DESIGN_UX_SPEC.md`
- **Success metrics:** `04_ANALYTICS_PLAN.md`
- **Product context:** `01_PRD.md`

---

*Use this document to create Linear tickets. Each feature = one ticket.*
