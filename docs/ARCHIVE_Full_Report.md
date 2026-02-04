<img src="sigil_logo.jpg" alt="Sigil" width="240" />

# TradingApp iOS - Research & Architecture Report

**Project:** iOS Stock Trading App with AI-Powered Recommendations  
**Author:** Blaze Neon  
**Date:** February 2, 2026  
**Status:** Research Phase  

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Goal & Vision](#goal--vision)
3. [Stock Universe](#stock-universe)
4. [Data Sources](#data-sources)
5. [Recommendation System Architecture](#recommendation-system-architecture)
6. [Models & Algorithms](#models--algorithms)
7. [Buy/Sell Logic](#buysell-logic)
8. [Evaluation Metrics](#evaluation-metrics)
9. [System Architecture](#system-architecture)
10. [iOS App Modules](#ios-app-modules)
11. [UX/UI Design](#uxui-design)
12. [Interactive Brokers Integration](#interactive-brokers-integration)
13. [Security & Compliance](#security--compliance)
14. [Restrictions & Limitations](#restrictions--limitations)
15. [Development Roadmap](#development-roadmap)
16. [References & Resources](#references--resources)

---

## Executive Summary

This report outlines the architecture for an iOS trading application that combines predictive modeling and AI-powered recommendations for S&P 500 stocks. The system integrates company earnings, macroeconomic indicators, and news sentiment to generate weekly stock scores — ranking opportunities while forecasting expected performance. Trading execution via Interactive Brokers API.

**Key Features:**
- Predictive scoring model combining fundamentals, sentiment, macro, and technicals
- Weekly stock rankings with actionable buy/hold/sell signals
- Score explainability — transparent breakdown of why each stock ranks where it does
- Real-time portfolio tracking and execution
- Paper trading and real money modes
- Risk management and position sizing
- Performance analytics and backtesting

---

## ⚠️ Core Development Principles

> **FUNCTIONALITY FIRST. EVERYTHING ELSE IS SECONDARY.**

```
┌─────────────────────────────────────────────────────────────────────┐
│                     PRIORITY HIERARCHY                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   #1  WORKS         Does it function correctly? No bugs, no        │
│       ═══════       crashes, data is accurate, flows complete.     │
│                                                                     │
│   #2  RELIABLE      Does it work every time? Pipeline runs,        │
│       ─────────     API responds, no random failures.              │
│                                                                     │
│   #3  USABLE        Can user complete tasks? Clear navigation,     │
│       ─────────     obvious actions, no confusion.                 │
│                                                                     │
│   #4  FAST          Is it responsive? No lag, no spinners,         │
│       ─────────     instant feedback.                              │
│                                                                     │
│   #5  PRETTY        Does it look good? Only after 1-4 are solid.   │
│       · · · · ·                                                     │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### What This Means in Practice

| Decision | Wrong ❌ | Right ✅ |
|----------|---------|---------|
| Scoring model | Spend weeks on FinBERT accuracy | Ship with simple keywords that work |
| UI animations | Perfect 60fps spring physics | Basic transitions, focus on data correctness |
| Data pipeline | Fancy ML preprocessing | Simple ETL that runs 100% reliably |
| Charts | Custom animated candlesticks | Standard library chart that displays correctly |
| Error handling | Generic "Something went wrong" | Clear message, retry button, works |

### The MVP Checklist

Before adding ANY feature, ask:

1. ✅ **Does the app launch without crashing?**
2. ✅ **Does the data pipeline run successfully every week?**
3. ✅ **Are the numbers displayed accurate?**
4. ✅ **Can I browse stocks and see their scores?**
5. ✅ **Can I submit a paper trade?**
6. ✅ **Does the portfolio show correct positions?**

If ANY answer is "No" → fix that before doing anything else.

### Separation of Concerns

> 🎯 **Principle:** Every module does ONE thing well. No god classes. No spaghetti. If you can't describe a module's purpose in one sentence, split it.

**Why It Matters:**
- Easier to test (isolated units)
- Easier to debug (problems are localized)
- Easier to modify (change one thing without breaking another)
- Easier to understand (new contributor can grasp a module quickly)

**Layer Separation:**

```
┌─────────────────────────────────────────────────────────────────┐
│  PRESENTATION (Views)                                           │
│  • SwiftUI Views, UIKit if needed                               │
│  • ONLY handles display and user input                          │
│  • No business logic, no API calls, no data transformation     │
└─────────────────────────┬───────────────────────────────────────┘
                          │ Bindings / ObservableObject
┌─────────────────────────▼───────────────────────────────────────┐
│  VIEW MODELS                                                    │
│  • Prepare data for display                                     │
│  • Handle user actions                                          │
│  • Coordinate between services                                  │
│  • No UI code, no direct API calls                              │
└─────────────────────────┬───────────────────────────────────────┘
                          │ Protocols / Dependency Injection
┌─────────────────────────▼───────────────────────────────────────┐
│  SERVICES                                                       │
│  • Business logic (scoring, portfolio calculations)             │
│  • Data transformation                                          │
│  • Orchestration                                                 │
│  • No UI awareness, no HTTP knowledge                           │
└─────────────────────────┬───────────────────────────────────────┘
                          │ Protocols
┌─────────────────────────▼───────────────────────────────────────┐
│  REPOSITORIES / DATA ACCESS                                     │
│  • API calls, database queries                                  │
│  • Caching logic                                                 │
│  • Data mapping (DTO → Domain models)                           │
│  • No business logic                                            │
└─────────────────────────────────────────────────────────────────┘
```

**Backend Separation:**

| Layer | Responsibility | Example |
|-------|---------------|---------|
| **Routes/Controllers** | HTTP handling, validation | `POST /api/scores` |
| **Services** | Business logic | `ScoringService.calculate()` |
| **Models** | ML/scoring algorithms | `CompositeScorer.score()` |
| **Repositories** | Data access | `StockRepository.get_by_ticker()` |
| **Data/ETL** | External data fetching | `YahooFinanceFetcher.fetch()` |

**Practical Rules:**

| ❌ Don't | ✅ Do |
|----------|-------|
| API call inside a SwiftUI View | API call in Repository, exposed via ViewModel |
| Business logic in ViewController | Business logic in Service, VC just displays |
| SQL queries in scoring function | Scoring function receives data, Repository handles SQL |
| One 2000-line file | Multiple focused files, <300 lines each |
| Global state everywhere | Dependency injection, explicit data flow |

**File Size Guideline:**
- If a file exceeds **300 lines**, consider splitting
- If a class has more than **5 public methods**, it might be doing too much
- If you need to scroll to understand a function, it's too long

### Build Order

```
Week 1-4:   Make data pipeline WORK
Week 5-8:   Make iOS app WORK (show data correctly)
Week 9-10:  Make scoring WORK (simple is fine)
Week 11-13: Make trading WORK (paper mode)
Week 14-16: Fix bugs, stabilize
───────────────────────────────────────
ONLY THEN: Improve accuracy, polish UI, add features
```

---

## Goal & Vision

### Primary Goal
Build an intelligent iOS trading application that democratizes quantitative trading strategies by providing actionable, data-driven stock recommendations to retail investors.

### Vision
- **Accessibility:** Make institutional-grade analysis available to individual investors
- **Transparency:** Explain why each stock receives its score
- **Automation:** Weekly updates with optional automated execution
- **Risk Management:** Built-in position sizing and portfolio diversification

### Success Criteria
- Generate alpha (excess returns) over S&P500 benchmark
- Achieve Sharpe ratio > 1.5
- Maximum drawdown < 20%
- User satisfaction score > 4.5/5

---

## Stock Universe

### Selection Criteria
- **Index:** S&P500 constituents
- **Market Cap Filter:** > $10 billion USD
- **Liquidity:** Average daily volume > 1M shares
- **Data Availability:** Complete financial statements and analyst coverage

### Estimated Universe Size
- S&P500 has ~503 stocks
- ~400-450 meet the $10B market cap threshold
- Final universe: ~400 stocks after liquidity filters

### Universe Maintenance
- Quarterly rebalancing aligned with S&P index reconstitution
- Automatic removal of stocks falling below thresholds
- Addition of newly qualified stocks

### Sector Representation
| Sector | Est. Count | Weight |
|--------|-----------|--------|
| Technology | 80+ | ~30% |
| Healthcare | 60+ | ~15% |
| Financials | 65+ | ~13% |
| Consumer Discretionary | 50+ | ~11% |
| Industrials | 55+ | ~9% |
| Communication Services | 25+ | ~8% |
| Consumer Staples | 35+ | ~6% |
| Energy | 20+ | ~4% |
| Utilities | 25+ | ~2% |
| Real Estate | 25+ | ~2% |
| Materials | 20+ | ~2% |

---

## Data Sources

> ⚠️ **Availability Legend:**
> - ✅ **FREE** — No cost, suitable for production
> - 🆓 **FREE TIER** — Limited free usage, may need paid for scale
> - 💰 **PAID** — Requires subscription/payment
> - ❌ **NOT AVAILABLE** — Cannot be used

---

### Data Sources Availability Summary

| Source | Availability | Free Limits | Paid Cost | Notes |
|--------|--------------|-------------|-----------|-------|
| **Interactive Brokers** | ✅ FREE | Unlimited with account | — | Paper trading free, need funded account for live |
| **Financial Modeling Prep** | 🆓 FREE TIER | 250 req/day | $19/mo+ | Good for MVP |
| **SEC EDGAR** | ✅ FREE | Unlimited | — | Public government data |
| **FRED** | ✅ FREE | Unlimited | — | Federal Reserve public data |
| **Yahoo Finance** | ✅ FREE | Unlimited | — | Via yfinance Python library |
| **Alpha Vantage** | 🆓 FREE TIER | 5 req/min, 500/day | $50/mo+ | Backup option |
| **Polygon.io** | 🆓 FREE TIER | 5 req/min | $29/mo+ | Good historical data |
| **NewsAPI** | 🆓 FREE TIER | 100 req/day (dev only) | $449/mo | ⚠️ Free tier not for production |
| **Benzinga** | 💰 PAID | None | $99/mo+ | High quality but expensive |
| **Trading Economics** | 💰 PAID | None | $49/mo+ | Macro data |
| **Twitter/X API** | 💰 PAID | None | $100/mo+ | Expensive, not recommended |

### Recommended MVP Stack (100% Free)

| Data Type | Source | Why |
|-----------|--------|-----|
| **Prices (OHLCV)** | Yahoo Finance (yfinance) | Free, reliable, no API key |
| **Fundamentals** | Financial Modeling Prep (free tier) | 250 req/day enough for weekly |
| **SEC Filings** | SEC EDGAR | Free, authoritative |
| **Macro Data** | FRED | Free, comprehensive |
| **Trading** | Interactive Brokers | Free with account |

---

### 1. Market Data

#### Primary: Yahoo Finance (yfinance) ✅ FREE
- **Cost:** Free, no API key required
- **Library:** `pip install yfinance`
- Real-time and historical OHLCV
- Dividends, splits, market cap
- **Limits:** None (but be respectful, no aggressive scraping)
- **Link:** https://github.com/ranaroussi/yfinance

```python
import yfinance as yf
aapl = yf.Ticker("AAPL")
hist = aapl.history(period="1y")  # Free!
```

#### Secondary: Interactive Brokers API ✅ FREE (with account)
- **Cost:** Free with IBKR account (paper trading is free)
- Real-time and historical price data
- Order execution, portfolio info
- **Requirement:** Must open IBKR account
- **Link:** https://www.interactivebrokers.com/en/trading/ib-api.php

#### Backup: Financial Modeling Prep 🆓 FREE TIER
- **Free tier:** 250 requests/day
- **Paid:** $19/month for 300 req/min
- Historical prices, financials, earnings calendar
- **Link:** https://financialmodelingprep.com/

#### Alternative: Alpha Vantage 🆓 FREE TIER
- **Free tier:** 5 calls/min, 500/day
- **Paid:** $50/month for higher limits
- **Link:** https://www.alphavantage.co/

### 2. Fundamental Data

#### SEC EDGAR ✅ FREE
- **Cost:** Completely free (public government data)
- 10-K, 10-Q, 8-K filings
- Earnings reports, insider trading
- **Link:** https://www.sec.gov/edgar/searchedgar/companysearch
- **API:** https://www.sec.gov/developer

#### Financial Modeling Prep 🆓 FREE TIER
- **Free tier:** 250 requests/day (sufficient for weekly batch)
- Revenue, EPS, margins, ratios
- Earnings calendar, estimates
- **Note:** Cache responses to stay within limits

### 3. Macroeconomic Data

#### FRED (Federal Reserve) ✅ FREE
- **Cost:** Completely free
- **API Key:** Free, just register
- All major economic indicators
- **Link:** https://fred.stlouisfed.org/
- **Python:** `pip install fredapi`

```python
from fredapi import Fred
fred = Fred(api_key='your_free_key')
gdp = fred.get_series('GDP')  # Free!
```

#### Key Indicators (All available via FRED for FREE)
| Indicator | FRED Code | Frequency |
|-----------|-----------|-----------|
| Federal Funds Rate | FEDFUNDS | Monthly |
| CPI (Inflation) | CPIAUCSL | Monthly |
| Unemployment Rate | UNRATE | Monthly |
| GDP Growth | GDP | Quarterly |
| 10-Year Treasury | DGS10 | Daily |
| VIX | VIXCLS | Daily |

#### ~~Trading Economics~~ 💰 PAID — NOT RECOMMENDED
- Expensive ($49/mo+), FRED provides same data free

### 4. News & Sentiment Data

#### SEC Filings (8-K) ✅ FREE
- **Cost:** Free
- Material events, earnings announcements
- Best source for official company news

#### News Sources — Start Free, Scale Later

> 🎯 **MVP Philosophy:** Start with minimal FREE sources that work reliably. Add premium sources later when the pipeline is proven and ROI is clear.

##### MVP Sources (FREE Only)

| Source | RSS Feed | Cost | Why Include |
|--------|----------|------|-------------|
| **Yahoo Finance** | ✅ | FREE | Reliable, broad coverage, good API |
| **Reuters** | ✅ | FREE | Breaking news, credible |
| **SEC EDGAR** | ✅ | FREE | Official filings (8-K, 10-Q) — ground truth |
| **MarketWatch** | ✅ | FREE | Market coverage, earnings |

**That's it for MVP.** 4 sources. All free. All reliable.

```python
# MVP: Minimal free sources
NEWS_RSS_FEEDS = {
    'yahoo_finance': 'https://finance.yahoo.com/news/rssindex',
    'reuters': 'https://www.reutersagency.com/feed/?taxonomy=best-sectors&post_type=best',
    'marketwatch': 'https://www.marketwatch.com/rss/topstories',
    'sec_filings': 'https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&output=atom',
}
```

##### Future: Premium Sources (Phase 6+)

> ⚠️ **Add only after MVP is working and you've validated sentiment actually improves scores.**

| Source | Cost | When to Add |
|--------|------|-------------|
| **The Economist** | 💰 ~$200/yr | Headlines free via RSS, full articles need subscription |
| **Wall Street Journal** | 💰 ~$400/yr | When you need deeper macro analysis |
| **Bloomberg** | 💰 ~$25K/yr | Probably never for personal project |
| **Sector-specific** | Varies | When sector accuracy matters |

##### Weighting (Simplified)

For MVP, all sources weighted equally. Complexity comes later.

```python
# MVP: Simple equal weighting
def get_source_weight(source: str) -> float:
    return 1.0  # All sources equal for now

# FUTURE: Tiered weighting (uncomment when adding premium)
# SOURCE_WEIGHTS = {
#     'economist': 3.0,   # Premium
#     'wsj': 3.0,         # Premium  
#     'reuters': 2.0,     # Quality free
#     'yahoo_finance': 1.0,
#     'marketwatch': 1.0,
# }
```

##### News Fetcher Implementation

```python
import feedparser
from datetime import datetime, timedelta
from typing import List, Dict

##### News Fetcher (MVP)

```python
import feedparser
from datetime import datetime, timedelta
from typing import List, Dict

class NewsFetcher:
    """
    MVP: Simple news fetcher using free RSS sources only.
    """
    
    def __init__(self):
        self.feeds = {
            'yahoo_finance': 'https://finance.yahoo.com/news/rssindex',
            'reuters': 'https://www.reutersagency.com/feed/?taxonomy=best-sectors&post_type=best',
            'marketwatch': 'https://www.marketwatch.com/rss/topstories',
            'sec_filings': 'https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&output=atom',
        }
    
    def fetch_all(self, hours: int = 24) -> List[Dict]:
        """Fetch news from all sources in the last N hours."""
        articles = []
        cutoff = datetime.now() - timedelta(hours=hours)
        
        for source, url in self.feeds.items():
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries:
                    pub_date = entry.get('published_parsed') or entry.get('updated_parsed')
                    if pub_date:
                        pub_datetime = datetime(*pub_date[:6])
                        if pub_datetime < cutoff:
                            continue
                    
                    articles.append({
                        'source': source,
                        'title': entry.get('title', ''),
                        'summary': entry.get('summary', '')[:500],
                        'link': entry.get('link', ''),
                    })
            except Exception as e:
                print(f"  {source}: ERROR - {e}")
        
        return articles
    
    def fetch_for_ticker(self, ticker: str) -> List[Dict]:
        """Fetch news mentioning a specific stock."""
        all_news = self.fetch_all(hours=168)  # 7 days
        return [
            a for a in all_news
            if ticker.upper() in a['title'].upper() or ticker.upper() in a['summary'].upper()
        ]
```

##### Skipped Sources (Not Needed for MVP)

| Source | Why Skip |
|--------|----------|
| NewsAPI | Free tier dev-only, can't use in production |
| Benzinga | $99/month — overkill for MVP |
| Twitter/X | $100/month — low signal-to-noise anyway |
| Bloomberg | $25K/year — lol no |
- Skip for MVP

---

## Recommendation System Architecture

### Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    DATA INGESTION LAYER                        │
├─────────────────┬─────────────────┬─────────────────────────────┤
│  Market Data    │  Fundamentals   │  News & Sentiment          │
│  (Prices, Vol)  │  (Earnings,     │  (Articles, Social,        │
│                 │   Financials)   │   Transcripts)             │
└────────┬────────┴────────┬────────┴─────────────┬───────────────┘
         │                 │                      │
         ▼                 ▼                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FEATURE ENGINEERING                          │
├─────────────────┬─────────────────┬─────────────────────────────┤
│  Technical      │  Fundamental    │  Sentiment                  │
│  Features       │  Features       │  Features                   │
│  - Returns      │  - Growth       │  - News Score               │
│  - Volatility   │  - Valuation    │  - Transcript Score         │
│  - Momentum     │  - Quality      │  - Event Flags              │
└────────┬────────┴────────┬────────┴─────────────┬───────────────┘
         │                 │                      │
         └─────────────────┼──────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    SCORING ENGINE                               │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Multi-Factor Model                                        │ │
│  │  Score = w1*Fundamental + w2*Sentiment + w3*Macro + w4*Tech│ │
│  └────────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  ML Enhancement Layer (Optional)                           │ │
│  │  - XGBoost for feature interactions                        │ │
│  │  - Neural network for time-series patterns                 │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────┬───────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    RANKING & OUTPUT                             │
│  - Stock scores (0-100)                                         │
│  - Buy/Sell/Hold signals                                        │
│  - Confidence levels                                            │
│  - Top picks per sector                                         │
└─────────────────────────────────────────────────────────────────┘
```

### Scoring Framework

Each stock receives a composite score from 0-100 based on:

| Component | Weight | Description |
|-----------|--------|-------------|
| Fundamental Score | 35% | Earnings quality, growth, valuation |
| Sentiment Score | 25% | News sentiment, earnings call tone |
| Macro Alignment | 20% | Sector sensitivity to current macro environment |
| Technical Score | 20% | Momentum, relative strength, support/resistance |

### Update Frequency & Data Refresh Schedule

> **Principle:** Match refresh frequency to data change frequency. Don't over-fetch stable data.

#### Data Refresh Matrix

| Data Type | Refresh Frequency | When | Notes |
|-----------|-------------------|------|-------|
| **Prices (OHLCV)** | Daily | After market close | 4:30 PM ET |
| **News & Sentiment** | Weekly | Sunday night | Aggregate past week |
| **Technical indicators** | Weekly | Sunday night | Calculated from prices |
| **Earnings reports** | Quarterly | After release | ~2 weeks after quarter end |
| **Financial statements** | Quarterly | After 10-Q/10-K | SEC filing date |
| **Analyst estimates** | Quarterly | Before earnings | Update when revised |
| **Macro indicators** | Monthly/Quarterly | When released | FRED provides dates |
| **Stock universe** | Quarterly | S&P rebalance | March, June, Sept, Dec |
| **Scores (final)** | Weekly | Sunday night | After all inputs ready |

#### Refresh Schedule (Cron Jobs)

```python
# Data refresh schedule
REFRESH_SCHEDULE = {
    # Daily (after market close)
    'prices': {
        'frequency': 'daily',
        'cron': '0 17 * * 1-5',  # 5:00 PM ET, Mon-Fri
        'source': 'yfinance',
    },
    
    # Weekly (Sunday night before market open)
    'news_sentiment': {
        'frequency': 'weekly',
        'cron': '0 22 * * 0',  # 10:00 PM ET, Sunday
        'source': 'RSS feeds',
    },
    'technical_indicators': {
        'frequency': 'weekly',
        'cron': '0 23 * * 0',  # 11:00 PM ET, Sunday
        'depends_on': ['prices'],
    },
    'scores': {
        'frequency': 'weekly',
        'cron': '0 0 * * 1',  # 12:00 AM ET, Monday (after all inputs)
        'depends_on': ['prices', 'news_sentiment', 'technical_indicators'],
    },
    
    # Quarterly (after earnings season)
    'earnings_reports': {
        'frequency': 'quarterly',
        'cron': '0 6 15 1,4,7,10 *',  # 15th of Jan, Apr, Jul, Oct
        'source': 'SEC EDGAR / FMP',
    },
    'financial_statements': {
        'frequency': 'quarterly',
        'cron': '0 6 20 1,4,7,10 *',  # 20th of Jan, Apr, Jul, Oct
        'source': 'SEC EDGAR',
    },
    
    # Quarterly (S&P rebalance)
    'stock_universe': {
        'frequency': 'quarterly',
        'cron': '0 6 1 3,6,9,12 *',  # 1st of Mar, Jun, Sep, Dec
        'source': 'S&P Global',
    },
}
```

#### Pipeline Execution Order

```
┌─────────────────────────────────────────────────────────────────┐
│                    WEEKLY REFRESH (Sunday Night)                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  5:00 PM (Fri) │ Daily prices already updated                  │
│                │                                                │
│ 10:00 PM (Sun) │ Fetch news from past 7 days                   │
│                │ → Parse RSS feeds                              │
│                │ → Run sentiment analysis (keywords)            │
│                │ → Store news_sentiment table                   │
│                │                                                │
│ 11:00 PM (Sun) │ Calculate technical indicators                │
│                │ → Momentum, RSI, moving averages               │
│                │ → Store technical_scores table                 │
│                │                                                │
│ 12:00 AM (Mon) │ Generate final scores                         │
│                │ → Combine: fundamental + sentiment + technical │
│                │ → Rank all stocks                              │
│                │ → Store scores table                           │
│                │ → Push to API cache                            │
│                │                                                │
│  6:00 AM (Mon) │ App shows fresh scores for the week           │
│                │                                                │
└─────────────────────────────────────────────────────────────────┘
```

```
┌─────────────────────────────────────────────────────────────────┐
│               QUARTERLY REFRESH (After Earnings)                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Earnings Season │ Q4: Jan-Feb, Q1: Apr-May,                   │
│                  │ Q2: Jul-Aug, Q3: Oct-Nov                     │
│                  │                                              │
│  15th of month   │ Fetch new earnings reports                  │
│                  │ → Download 10-Q/10-K from SEC                │
│                  │ → Parse revenue, EPS, margins                │
│                  │ → Calculate YoY/QoQ growth                   │
│                  │ → Update fundamentals table                  │
│                  │                                              │
│  20th of month   │ Update fundamental scores                   │
│                  │ → Recalculate value/quality/growth factors   │
│                  │ → These persist until next quarter           │
│                  │                                              │
└─────────────────────────────────────────────────────────────────┘
```

#### Data Staleness Rules

```python
def is_data_stale(data_type: str, last_updated: datetime) -> bool:
    """
    Check if data needs refresh.
    """
    now = datetime.now()
    age = now - last_updated
    
    STALENESS_THRESHOLDS = {
        'prices': timedelta(days=1),           # Stale after 1 day
        'news_sentiment': timedelta(days=7),   # Stale after 1 week
        'technical': timedelta(days=7),        # Stale after 1 week
        'earnings': timedelta(days=100),       # Stale after ~1 quarter
        'fundamentals': timedelta(days=100),   # Stale after ~1 quarter
        'scores': timedelta(days=7),           # Stale after 1 week
    }
    
    threshold = STALENESS_THRESHOLDS.get(data_type, timedelta(days=7))
    return age > threshold


# In API response, include freshness
def get_stock_score(ticker: str) -> dict:
    score_data = db.get_score(ticker)
    
    return {
        'ticker': ticker,
        'score': score_data['score'],
        'signal': score_data['signal'],
        'last_updated': score_data['updated_at'],
        'is_stale': is_data_stale('scores', score_data['updated_at']),
    }
```

#### Summary Table

| Data | Frequency | Rationale |
|------|-----------|-----------|
| **Prices** | Daily | Markets move daily |
| **News** | Weekly | Aggregate for signal, reduce noise |
| **Sentiment** | Weekly | Derived from news |
| **Technical** | Weekly | Based on weekly price action |
| **Earnings** | Quarterly | Companies report quarterly |
| **Fundamentals** | Quarterly | Tied to earnings |
| **Scores** | Weekly | Balance freshness vs stability |

---

## Models & Algorithms

> ⚠️ **Availability Legend:**
> - ✅ **FREE** — Open source, free to use commercially
> - 🆓 **FREE (Non-commercial)** — Free for personal/research, check license for commercial
> - 💰 **PAID** — Requires payment/subscription
> - ❌ **NOT AVAILABLE** — Proprietary, cannot access

---

### 🎯 Core Modeling Philosophy

> **"Rank, don't predict. Time series data is noisy."**

#### Why Recommendation Over Prediction

```
❌ HARD (Time Series Prediction):
   "AAPL will be $190.50 next week"
   → Extremely noisy, low accuracy
   → Small errors compound
   → Markets are efficient, hard to beat

✅ EASIER (Cross-Sectional Ranking):
   "AAPL ranks better than MSFT this week"
   → Relative comparison is more stable
   → Noise cancels out across stocks
   → Don't need exact prices, just order
```

#### The Approach

| Component | Approach | Why |
|-----------|----------|-----|
| **Primary** | Recommendation/Ranking System | Rank 400 stocks 1-100, pick top N |
| **Secondary** | Light HMM for macro regime | Identify market state (4 regimes) |
| **Avoid** | Heavy time-series forecasting | Too noisy, overfits easily |

#### What This Means in Practice

```python
# ❌ DON'T: Try to predict exact returns
predicted_return = model.predict(features)  # Very noisy, unreliable

# ✅ DO: Rank stocks relative to each other
scores = rank_all_stocks(features)  # Cross-sectional comparison
top_stocks = scores.nlargest(10)    # Pick top 10
```

#### Model Complexity Guidelines

| Model Type | Use? | Notes |
|------------|------|-------|
| **Linear ranking** | ✅ Yes | Simple, interpretable, robust |
| **Percentile scores** | ✅ Yes | Relative ranking, noise-resistant |
| **HMM (2-4 states)** | ✅ Light | Macro regime only, not stock-level |
| **XGBoost ranking** | ⚠️ Careful | Easy to overfit, validate thoroughly |
| **LSTM/RNN** | ⚠️ Careful | See detailed comparison below |
| **Price prediction** | ❌ Avoid | Too noisy, don't try |

---

#### HMM vs LSTM: Why HMM for This Use Case?

> **Short answer:** We use HMM for regime detection (discrete states), not price prediction. LSTM is powerful but prone to overfitting on noisy financial data.

##### What Each Model Does Best

| Model | Best For | Not For |
|-------|----------|---------|
| **HMM** | Discrete state detection (4 regimes) | Continuous price prediction |
| **LSTM** | Sequence patterns with clear signal | Noisy financial time series |

##### HMM: Our Use Case

```
┌─────────────────────────────────────────────────────────────────┐
│                    HMM FOR REGIME DETECTION                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   INPUT:  Macro indicators (VIX, yield curve, PMI)             │
│                         ↓                                       │
│   HMM:    Hidden states = market regimes                       │
│           [Expansion] [Contraction] [Recovery] [Overheating]   │
│                         ↓                                       │
│   OUTPUT: P(current_state) → Adjust sector weights             │
│                                                                 │
│   • 4 discrete states (not continuous prediction)              │
│   • Market-wide (not per-stock)                                │
│   • Interpretable (we know what each regime means)             │
│   • Stable (doesn't overfit to daily noise)                    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

##### Why Not LSTM for Regime Detection?

| Factor | HMM | LSTM |
|--------|-----|------|
| **Output** | Discrete states (4 regimes) | Continuous values |
| **Interpretability** | Clear regime meanings | Black box |
| **Data needed** | Works with small data | Needs lots of data |
| **Overfitting risk** | Low (few parameters) | High (millions of params) |
| **Training time** | Fast | Slow |
| **Regime transitions** | Explicit probabilities | Implicit, hard to extract |

##### When LSTM CAN Work in Finance

LSTM isn't bad — it's just often misapplied. It works when:

| ✅ LSTM Works | ❌ LSTM Fails |
|--------------|--------------|
| High-frequency data (tick-level) | Daily/weekly price prediction |
| Order book patterns | Long-term return forecasting |
| Sentiment sequence modeling | Noisy fundamentals |
| Clear sequential structure | Random walk data |
| Large, clean datasets | Small, noisy datasets |

##### The Overfitting Problem

```
LSTM on Financial Data:

Training data (2015-2023):
  → LSTM finds complex patterns
  → Training accuracy: 65%
  → "This model is great!"

Test data (2024):
  → Patterns don't repeat
  → Test accuracy: 48% (worse than random)
  → "Why doesn't it work??"

The Problem:
  Financial markets are noisy + non-stationary
  LSTM memorizes noise patterns that don't recur
  More parameters = more ways to overfit
```

##### Academic Evidence

Research on LSTM for stock prediction:

| Study | Finding |
|-------|---------|
| Fischer & Krauss (2018) | LSTM beat baseline in 2000s, failed in 2010s (markets adapted) |
| Gu et al. (2020) | Simple models often beat deep learning on financial data |
| Lim & Zohren (2021) | LSTM needs careful regularization for finance |

> **Key insight:** Markets are adversarial. If LSTM finds a pattern, traders exploit it until it disappears.

##### Our Recommendation

```
┌─────────────────────────────────────────────────────────────────┐
│                    MODEL SELECTION GUIDE                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  USE HMM FOR:                                                  │
│  • Macro regime detection (4 states)                           │
│  • Market-wide state (not per-stock)                           │
│  • When you need interpretability                              │
│  • When data is limited                                        │
│                                                                 │
│  CONSIDER LSTM FOR (Phase 6+, experimental):                   │
│  • Sentiment sequence modeling (news flow)                     │
│  • Earnings call transcript analysis                           │
│  • High-frequency patterns (if you have the data)              │
│  • As one input to ensemble (not sole predictor)               │
│                                                                 │
│  ALWAYS:                                                       │
│  • Validate on out-of-sample data                              │
│  • Compare to simple baseline (does LSTM beat average?)        │
│  • Use walk-forward testing                                    │
│  • Be skeptical of high training accuracy                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

##### If You Want to Try LSTM (Phase 6+)

```python
# LSTM for sentiment sequence (not price prediction)
# This is a more appropriate use case

from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout

def build_sentiment_lstm():
    """
    LSTM for sentiment trajectory modeling.
    Input: Sequence of daily sentiment scores
    Output: Sentiment trend direction
    """
    model = Sequential([
        LSTM(32, input_shape=(30, 1), return_sequences=False),  # 30 days
        Dropout(0.3),  # Regularization!
        Dense(16, activation='relu'),
        Dropout(0.3),
        Dense(3, activation='softmax')  # Up/Flat/Down
    ])
    
    model.compile(
        optimizer='adam',
        loss='categorical_crossentropy',
        metrics=['accuracy']
    )
    
    return model

# Key settings to reduce overfitting:
# - Small network (32 units, not 256)
# - Heavy dropout (0.3)
# - Early stopping
# - Walk-forward validation
```

##### Summary

| Question | Answer |
|----------|--------|
| Why HMM? | Discrete regime detection, interpretable, won't overfit |
| Why not LSTM? | Overfits noisy data, black box, needs careful tuning |
| Is LSTM useless? | No — good for sequences with clear patterns (sentiment, NLP) |
| Will we use LSTM? | Maybe in Phase 6+ for sentiment sequences, as experiment |
| What's the priority? | Recommendation ranking > Time series prediction |

#### Scoring = Recommendation System

Our scoring model IS a recommendation system:

```
┌─────────────────────────────────────────────────────────────────┐
│                   RECOMMENDATION SYSTEM                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   INPUT:  400 stocks with features (fundamentals, momentum...)  │
│                         ↓                                       │
│   PROCESS: Score each stock 0-100 (cross-sectional ranking)    │
│                         ↓                                       │
│   OUTPUT: Ranked list with BUY/HOLD/SELL signals               │
│                                                                 │
│   This is Netflix for stocks — "Top picks for you"             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### HMM: Keep It Light

Use HMM only for macro regime detection (market-wide), not stock-level prediction:

```python
# ✅ GOOD: HMM for macro regime (4 states)
regimes = ['Expansion', 'Contraction', 'Recovery', 'Overheating']
current_regime = hmm.predict(macro_indicators)  # One prediction for whole market

# Then adjust sector weights based on regime
if current_regime == 'Expansion':
    overweight = ['Technology', 'Consumer Discretionary']
elif current_regime == 'Contraction':
    overweight = ['Utilities', 'Healthcare', 'Consumer Staples']

# ❌ BAD: HMM for each stock's price
for stock in stocks:
    predicted_price = hmm.predict(stock_prices)  # Too noisy, don't do this
```

#### Why Ranking Works Better

1. **Noise cancels out:** When comparing AAPL vs MSFT, random noise affects both similarly
2. **Relative is stable:** "AAPL is stronger than average" is more reliable than "AAPL goes up 5%"
3. **No need for magnitude:** Just need to know which stocks are better, not by how much
4. **Information ratio:** Ranking models have better IC (Information Coefficient) than return prediction

---

### 📊 Data Preprocessing: Bucketing Continuous Variables

> **Principle:** Continuous variables are noisy. Convert to discrete buckets to reduce noise and improve signal.

#### Why Bucketing?

```
❌ RAW CONTINUOUS (noisy):
   P/E ratios: 18.23, 18.45, 18.31, 19.02, 18.87...
   → Small differences are noise, not signal
   → Model overfits to random fluctuations

✅ BUCKETED (cleaner):
   P/E buckets: "Low", "Medium", "High", "Very High"
   → Captures meaningful differences
   → Robust to small noise
```

#### Bucketing Methods

##### 1. Quantile Bucketing (Recommended)

Equal number of observations in each bucket:

```python
import pandas as pd
import numpy as np

def quantile_bucket(series: pd.Series, n_buckets: int = 5, labels: list = None) -> pd.Series:
    """
    Bucket continuous variable into quantiles.
    
    Args:
        series: Continuous data (e.g., P/E ratios)
        n_buckets: Number of buckets (default 5 = quintiles)
        labels: Optional labels (e.g., ['Very Low', 'Low', 'Medium', 'High', 'Very High'])
    
    Returns:
        Categorical series with bucket labels
    """
    if labels is None:
        labels = [f'Q{i+1}' for i in range(n_buckets)]
    
    return pd.qcut(series, q=n_buckets, labels=labels, duplicates='drop')


# Example: P/E Ratio
pe_ratios = pd.Series([12, 15, 18, 22, 25, 28, 35, 45, 60, 100])
pe_buckets = quantile_bucket(pe_ratios, n_buckets=5, 
                             labels=['Very Cheap', 'Cheap', 'Fair', 'Expensive', 'Very Expensive'])

# Result: Each bucket has ~20% of stocks
```

##### 2. Fixed Threshold Bucketing

Domain-knowledge based cutoffs:

```python
def fixed_bucket(series: pd.Series, thresholds: list, labels: list) -> pd.Series:
    """
    Bucket based on fixed thresholds.
    
    Args:
        series: Continuous data
        thresholds: Cut points [t1, t2, t3, ...]
        labels: Labels for each bucket (len = len(thresholds) + 1)
    """
    return pd.cut(series, bins=[-np.inf] + thresholds + [np.inf], labels=labels)


# Example: P/E with domain knowledge
PE_THRESHOLDS = [10, 15, 20, 30]  # Classic value investing cutoffs
PE_LABELS = ['Deep Value', 'Value', 'Fair', 'Growth', 'Expensive']

pe_buckets = fixed_bucket(pe_ratios, PE_THRESHOLDS, PE_LABELS)
```

##### 3. Standard Deviation Bucketing

Distance from mean:

```python
def zscore_bucket(series: pd.Series, n_std: float = 1.0) -> pd.Series:
    """
    Bucket based on standard deviations from mean.
    
    Buckets:
    - Very Low:  < -2σ
    - Low:       -2σ to -1σ
    - Normal:    -1σ to +1σ
    - High:      +1σ to +2σ
    - Very High: > +2σ
    """
    z = (series - series.mean()) / series.std()
    
    return pd.cut(z, 
                  bins=[-np.inf, -2, -1, 1, 2, np.inf],
                  labels=['Very Low', 'Low', 'Normal', 'High', 'Very High'])
```

#### Variables to Bucket

| Variable | Bucketing Method | # Buckets | Notes |
|----------|------------------|-----------|-------|
| **P/E Ratio** | Quantile or Fixed | 5 | Use sector-relative P/E |
| **P/B Ratio** | Quantile | 5 | High variance across sectors |
| **ROE** | Quantile | 5 | Normalize within sector |
| **Revenue Growth** | Quantile | 5 | YoY % change |
| **Momentum (3M)** | Quantile | 5 | Relative performance |
| **Volatility** | Quantile | 3-5 | Low/Medium/High |
| **Market Cap** | Fixed | 3 | Large/Mid/Small |
| **Volume** | Quantile | 3 | Low/Normal/High |

#### Sector-Relative Bucketing

Compare within sector, not across all stocks:

```python
def sector_relative_bucket(df: pd.DataFrame, column: str, sector_col: str = 'sector', n_buckets: int = 5) -> pd.Series:
    """
    Bucket within each sector separately.
    
    Example: Tech stocks compete with tech, not utilities.
    """
    def bucket_group(group):
        return pd.qcut(group, q=n_buckets, labels=range(1, n_buckets + 1), duplicates='drop')
    
    return df.groupby(sector_col)[column].transform(bucket_group)


# Example: P/E relative to sector peers
df['pe_bucket'] = sector_relative_bucket(df, 'pe_ratio', sector_col='sector', n_buckets=5)

# Now a P/E of 30 might be:
# - "Expensive" for Utilities (sector avg P/E = 15)
# - "Cheap" for Tech (sector avg P/E = 40)
```

#### Composite Score with Buckets

```python
def calculate_bucketed_score(stock_data: dict, sector: str) -> float:
    """
    Calculate score using bucketed features.
    
    Each bucket maps to a score (1-5), then weighted average.
    """
    # Bucket mappings (1 = worst, 5 = best)
    BUCKET_SCORES = {'Q1': 1, 'Q2': 2, 'Q3': 3, 'Q4': 4, 'Q5': 5}
    
    # For value factors, LOWER is better → invert
    VALUE_FACTORS = ['pe_ratio', 'pb_ratio', 'ev_ebitda']
    
    features = {
        'pe_bucket': quantile_bucket(stock_data['pe_ratio'], 5),
        'roe_bucket': quantile_bucket(stock_data['roe'], 5),
        'momentum_bucket': quantile_bucket(stock_data['momentum_3m'], 5),
        'growth_bucket': quantile_bucket(stock_data['revenue_growth'], 5),
    }
    
    scores = []
    for feature, bucket in features.items():
        score = BUCKET_SCORES.get(bucket, 3)  # Default to middle
        
        # Invert for value factors (low P/E = good = high score)
        if any(vf in feature for vf in VALUE_FACTORS):
            score = 6 - score  # Flip: 1→5, 2→4, 3→3, 4→2, 5→1
        
        scores.append(score)
    
    # Average bucket scores → scale to 0-100
    avg_score = np.mean(scores)  # 1-5 range
    final_score = (avg_score - 1) / 4 * 100  # 0-100 range
    
    return final_score
```

#### Benefits of Bucketing

| Benefit | Explanation |
|---------|-------------|
| **Noise reduction** | Small fluctuations don't change bucket |
| **Interpretability** | "High P/E" is clearer than "P/E = 28.34" |
| **Robustness** | Less sensitive to outliers |
| **Non-linearity** | Captures "P/E of 10 vs 15 matters, but 50 vs 55 doesn't" |
| **Comparability** | All features on same 1-5 scale |

#### When NOT to Bucket

| Case | Keep Continuous |
|------|-----------------|
| Price data for charts | Display exact prices |
| Order execution | Need precise numbers |
| Return calculations | Need exact percentages |
| Backtesting P&L | Precision matters |

**Rule:** Bucket for scoring/ranking, keep continuous for display/execution.

---

### 🚫 Outlier Detection & Filtering

> **Principle:** Time series financial data contains outliers (data errors, splits, corporate actions). Filter them before analysis.

#### Types of Outliers in Financial Data

| Type | Example | Cause |
|------|---------|-------|
| **Data errors** | Price = $0 or $999,999 | Feed glitch |
| **Stock splits** | Price drops 50% overnight | 2:1 split (not a real drop) |
| **Earnings jumps** | EPS goes from $1 to $50 | One-time gain, accounting |
| **Volume spikes** | 100x normal volume | Index rebalancing, news |
| **Fat fingers** | Price spikes 20% then back | Trading error |

#### Outlier Detection Methods

##### 1. Z-Score Method (Simple)

Flag values beyond N standard deviations:

```python
import pandas as pd
import numpy as np

def detect_outliers_zscore(series: pd.Series, threshold: float = 3.0) -> pd.Series:
    """
    Detect outliers using z-score.
    
    Args:
        series: Time series data
        threshold: Number of standard deviations (default 3)
    
    Returns:
        Boolean series (True = outlier)
    """
    z_scores = np.abs((series - series.mean()) / series.std())
    return z_scores > threshold


# Example: Flag daily returns > 3 standard deviations
returns = prices.pct_change()
outliers = detect_outliers_zscore(returns, threshold=3.0)
print(f"Found {outliers.sum()} outliers out of {len(returns)} days")
```

##### 2. IQR Method (Robust)

Less sensitive to extreme outliers:

```python
def detect_outliers_iqr(series: pd.Series, k: float = 1.5) -> pd.Series:
    """
    Detect outliers using Interquartile Range.
    
    Outlier if: value < Q1 - k*IQR or value > Q3 + k*IQR
    
    Args:
        series: Time series data
        k: IQR multiplier (1.5 = standard, 3.0 = extreme only)
    
    Returns:
        Boolean series (True = outlier)
    """
    Q1 = series.quantile(0.25)
    Q3 = series.quantile(0.75)
    IQR = Q3 - Q1
    
    lower_bound = Q1 - k * IQR
    upper_bound = Q3 + k * IQR
    
    return (series < lower_bound) | (series > upper_bound)


# Example
outliers = detect_outliers_iqr(returns, k=1.5)
```

##### 3. Rolling Window Method (Time Series)

Detect outliers relative to recent history:

```python
def detect_outliers_rolling(series: pd.Series, window: int = 20, threshold: float = 3.0) -> pd.Series:
    """
    Detect outliers using rolling statistics.
    
    Compares each value to its recent history, not full dataset.
    Better for non-stationary time series.
    
    Args:
        series: Time series data
        window: Rolling window size (days)
        threshold: Number of rolling std devs
    
    Returns:
        Boolean series (True = outlier)
    """
    rolling_mean = series.rolling(window=window, min_periods=10).mean()
    rolling_std = series.rolling(window=window, min_periods=10).std()
    
    z_scores = np.abs((series - rolling_mean) / rolling_std)
    
    return z_scores > threshold


# Example: Flag returns that are 3x rolling volatility
outliers = detect_outliers_rolling(returns, window=20, threshold=3.0)
```

##### 4. Domain-Specific Rules

Hard limits based on market knowledge:

```python
def detect_outliers_domain(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply domain-specific outlier rules.
    
    Returns:
        DataFrame with 'is_outlier' column
    """
    outliers = pd.Series(False, index=df.index)
    
    # Price outliers
    if 'price' in df.columns:
        outliers |= (df['price'] <= 0)           # Price can't be negative
        outliers |= (df['price'] > 100000)       # Sanity check
    
    # Return outliers
    if 'daily_return' in df.columns:
        outliers |= (df['daily_return'] > 0.5)   # >50% daily gain unlikely
        outliers |= (df['daily_return'] < -0.5)  # >50% daily loss unlikely
    
    # Volume outliers
    if 'volume' in df.columns:
        outliers |= (df['volume'] <= 0)          # Must have volume
    
    # P/E outliers
    if 'pe_ratio' in df.columns:
        outliers |= (df['pe_ratio'] < 0)         # Negative P/E = losses
        outliers |= (df['pe_ratio'] > 500)       # Extreme P/E
    
    # Market cap outliers
    if 'market_cap' in df.columns:
        outliers |= (df['market_cap'] < 1e9)     # Below $1B (our filter)
    
    return outliers


# Apply domain rules
domain_outliers = detect_outliers_domain(stock_data)
```

#### Handling Outliers

##### Option 1: Remove (Drop)

```python
def remove_outliers(df: pd.DataFrame, outlier_mask: pd.Series) -> pd.DataFrame:
    """Remove rows flagged as outliers."""
    clean_df = df[~outlier_mask].copy()
    print(f"Removed {outlier_mask.sum()} outliers ({outlier_mask.mean()*100:.1f}%)")
    return clean_df
```

##### Option 2: Winsorize (Cap)

Replace outliers with boundary values:

```python
def winsorize(series: pd.Series, lower_pct: float = 0.01, upper_pct: float = 0.99) -> pd.Series:
    """
    Cap outliers at percentile boundaries.
    
    Values below 1st percentile → set to 1st percentile
    Values above 99th percentile → set to 99th percentile
    """
    lower = series.quantile(lower_pct)
    upper = series.quantile(upper_pct)
    
    return series.clip(lower=lower, upper=upper)


# Example: Cap extreme returns
returns_clean = winsorize(returns, lower_pct=0.01, upper_pct=0.99)
```

##### Option 3: Replace with NaN (then interpolate)

```python
def replace_outliers_with_nan(series: pd.Series, outlier_mask: pd.Series) -> pd.Series:
    """Replace outliers with NaN, then forward fill."""
    clean = series.copy()
    clean[outlier_mask] = np.nan
    clean = clean.fillna(method='ffill')  # Forward fill
    return clean
```

#### Complete Preprocessing Pipeline

```python
def preprocess_time_series(df: pd.DataFrame) -> pd.DataFrame:
    """
    Full preprocessing pipeline for time series data.
    
    1. Detect outliers (multiple methods)
    2. Handle outliers (winsorize)
    3. Forward fill gaps
    4. Validate
    """
    df = df.copy()
    
    # Calculate returns if not present
    if 'daily_return' not in df.columns and 'price' in df.columns:
        df['daily_return'] = df['price'].pct_change()
    
    # Detect outliers using multiple methods
    outliers_zscore = detect_outliers_zscore(df['daily_return'], threshold=4.0)
    outliers_iqr = detect_outliers_iqr(df['daily_return'], k=3.0)
    outliers_domain = detect_outliers_domain(df)
    
    # Combine: flag if ANY method detects
    outliers = outliers_zscore | outliers_iqr | outliers_domain
    
    print(f"Outliers detected: {outliers.sum()} ({outliers.mean()*100:.2f}%)")
    print(f"  - Z-score: {outliers_zscore.sum()}")
    print(f"  - IQR: {outliers_iqr.sum()}")
    print(f"  - Domain: {outliers_domain.sum()}")
    
    # Handle outliers: winsorize continuous, remove invalid
    df['daily_return'] = winsorize(df['daily_return'], 0.01, 0.99)
    df = df[~outliers_domain]  # Remove truly invalid data
    
    # Forward fill any gaps
    df = df.fillna(method='ffill')
    
    # Validate
    assert df['price'].isna().sum() == 0, "Missing prices after preprocessing"
    assert (df['price'] > 0).all(), "Invalid prices after preprocessing"
    
    return df
```

#### Outlier Summary Table

| Data Type | Method | Threshold | Action |
|-----------|--------|-----------|--------|
| Daily returns | Z-score + Rolling | 4σ | Winsorize |
| Prices | Domain rules | ≤0 or >100K | Remove |
| Volume | Domain rules | ≤0 | Remove |
| P/E ratio | Domain + IQR | <0 or >500 | Winsorize |
| Fundamentals | IQR | 3× IQR | Winsorize |

#### Logging Outliers

```python
def log_outliers(df: pd.DataFrame, outlier_mask: pd.Series, output_file: str = 'outliers_log.csv'):
    """
    Log detected outliers for review.
    
    Helps debug data quality issues.
    """
    outlier_df = df[outlier_mask].copy()
    outlier_df['detection_date'] = pd.Timestamp.now()
    
    # Append to log file
    outlier_df.to_csv(output_file, mode='a', header=not os.path.exists(output_file))
    
    print(f"Logged {len(outlier_df)} outliers to {output_file}")
```

**Always log outliers** — they might reveal data feed issues that need fixing upstream.

---

---

### ML Models Availability Summary

| Model | Availability | License | Size | Link |
|-------|--------------|---------|------|------|
| **FinBERT** (ProsusAI) | ✅ FREE | Apache 2.0 | 110M | [HuggingFace](https://huggingface.co/ProsusAI/finbert) |
| **FinancialBERT** | ✅ FREE | MIT | 110M | [HuggingFace](https://huggingface.co/ahmedrachid/FinancialBERT-Sentiment-Analysis) |
| **DistilRoBERTa-Financial** | ✅ FREE | MIT | 82M | [HuggingFace](https://huggingface.co/mrm8488/distilroberta-finetuned-financial-news-sentiment-analysis) |
| **FinBERT-Tone** | ✅ FREE | Apache 2.0 | 110M | [HuggingFace](https://huggingface.co/yiyanghkust/finbert-tone) |
| **FinGPT** | ✅ FREE | Apache 2.0 | Various | [GitHub](https://github.com/AI4Finance-Foundation/FinGPT) |
| **XGBoost** | ✅ FREE | Apache 2.0 | — | [GitHub](https://github.com/dmlc/xgboost) |
| **hmmlearn** (HMM) | ✅ FREE | BSD | — | [GitHub](https://github.com/hmmlearn/hmmlearn) |
| **BloombergGPT** | ❌ NOT AVAILABLE | Proprietary | 50B | Paper only, no access |
| **GPT-4 / Claude** | 💰 PAID | API | — | ~$0.01-0.03/1K tokens |

### Recommended Stack (100% Free)

| Purpose | MVP (Phase 1-5) | Later (Phase 6+) |
|---------|-----------------|------------------|
| **Sentiment Analysis** | Keyword-based ✅ | FinBERT (ready to enable) |
| **Earnings Call Tone** | Skip | FinBERT-tone |
| **Gradient Boosting** | XGBoost | XGBoost |
| **Regime Detection** | Hardcoded rules | hmmlearn (HMM) |

---

### 1. Sentiment Analysis Models

> **MVP Strategy:** Start with keywords (fast, simple, no GPU). FinBERT is implemented and ready — just flip a flag to enable it later.

#### Phase 1-5: Keyword-Based (DEFAULT) ✅
- **Method:** Dictionary matching (see implementation below)
- **Speed:** 1000s of headlines/second
- **Cost:** Zero (no GPU, no API)
- **Accuracy:** 70-80% (good enough for MVP)
- **Explainable:** Yes — shows matched words

#### Phase 6+: FinBERT (READY TO ENABLE) 🔌
- **Model:** `ProsusAI/finbert`
- **License:** Apache 2.0 ✅ FREE
- **Size:** 110M parameters
- **Speed:** 10-50 headlines/second (needs GPU for speed)
- **Accuracy:** 85-90%
- **Status:** Code implemented, disabled by default

```python
# Configuration flag — flip this to enable FinBERT
SENTIMENT_MODEL = "keyword"  # Options: "keyword" | "finbert"

def get_sentiment(text: str) -> dict:
    """
    Get sentiment using configured model.
    Change SENTIMENT_MODEL to switch methods.
    """
    if SENTIMENT_MODEL == "keyword":
        return keyword_sentiment(text)  # Fast, simple
    elif SENTIMENT_MODEL == "finbert":
        return finbert_sentiment(text)  # Accurate, slower
    else:
        raise ValueError(f"Unknown model: {SENTIMENT_MODEL}")
```

#### FinBERT Implementation (Ready, Not Active)

```python
# This code is ready — just set SENTIMENT_MODEL = "finbert" to use it

from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch

class FinBERTSentiment:
    """
    FinBERT sentiment analyzer.
    Ready to use, disabled by default for MVP.
    """
    
    _instance = None
    _model = None
    _tokenizer = None
    
    @classmethod
    def get_instance(cls):
        """Lazy load model only when needed."""
        if cls._model is None:
            print("Loading FinBERT model (first time only)...")
            cls._tokenizer = AutoTokenizer.from_pretrained("ProsusAI/finbert")
            cls._model = AutoModelForSequenceClassification.from_pretrained("ProsusAI/finbert")
            cls._model.eval()
        return cls
    
    @classmethod
    def analyze(cls, text: str) -> dict:
        """Get sentiment from text."""
        instance = cls.get_instance()
        
        inputs = instance._tokenizer(
            text, 
            return_tensors="pt", 
            truncation=True, 
            max_length=512
        )
        
        with torch.no_grad():
            outputs = instance._model(**inputs)
            probs = torch.nn.functional.softmax(outputs.logits, dim=-1)[0]
        
        # FinBERT outputs: [positive, negative, neutral]
        return {
            'positive': probs[0].item(),
            'negative': probs[1].item(),
            'neutral': probs[2].item(),
            'score': probs[0].item() - probs[1].item(),  # -1 to +1
            'model': 'finbert'
        }


def finbert_sentiment(text: str) -> dict:
    """Wrapper for FinBERT sentiment."""
    return FinBERTSentiment.analyze(text)
```

#### Other Models (Available for Future)
| Model | License | Size | Enable When |
|-------|---------|------|-------------|
| `ahmedrachid/FinancialBERT-Sentiment-Analysis` | MIT ✅ | 110M | Need different training data |
| `mrm8488/distilroberta-finetuned-financial-news-sentiment-analysis` | MIT ✅ | 82M | Need faster inference |
| `yiyanghkust/finbert-tone` | Apache 2.0 ✅ | 110M | Analyzing earnings calls |

#### ❌ NOT AVAILABLE: BloombergGPT
- **Status:** Proprietary, closed source
- **Access:** None (Bloomberg internal only)
- **Note:** Paper published for research, but model weights not released

#### Implementation (FinBERT)
```python
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch

model_name = "ProsusAI/finbert"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForSequenceClassification.from_pretrained(model_name)

def get_sentiment(text):
    inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
    outputs = model(**inputs)
    probs = torch.nn.functional.softmax(outputs.logits, dim=-1)
    return {"positive": probs[0][0].item(), 
            "negative": probs[0][1].item(), 
            "neutral": probs[0][2].item()}
```

---

#### Alternative: Keyword-Based Sentiment ✅ FREE (Recommended for MVP)

> **Why Keywords?** Simple, fast, interpretable, no GPU needed. Research shows keyword-based methods can be surprisingly effective for financial text where domain vocabulary is well-defined.

##### Financial Keyword Dictionaries

```python
# Curated financial sentiment keywords
POSITIVE_KEYWORDS = {
    # Earnings & Performance
    'beat', 'beats', 'exceeded', 'exceeds', 'surpass', 'surpassed',
    'record', 'strong', 'strength', 'robust', 'solid', 'stellar',
    'outperform', 'outperformed', 'top-line', 'bottom-line',
    
    # Growth
    'growth', 'growing', 'grew', 'increase', 'increased', 'rising',
    'expand', 'expanded', 'expansion', 'gain', 'gains', 'gained',
    'surge', 'surged', 'soar', 'soared', 'jump', 'jumped',
    
    # Guidance & Outlook
    'raised', 'raises', 'upgrade', 'upgraded', 'bullish', 'optimistic',
    'confident', 'positive', 'upbeat', 'encouraging', 'promising',
    'reaffirm', 'reaffirmed', 'above-consensus',
    
    # Actions
    'buy', 'bought', 'buyback', 'dividend', 'acquisition', 'deal',
    'partnership', 'launch', 'launched', 'innovation', 'breakthrough'
}

NEGATIVE_KEYWORDS = {
    # Earnings & Performance
    'miss', 'missed', 'misses', 'below', 'under', 'weak', 'weakness',
    'disappoint', 'disappointed', 'disappointing', 'shortfall',
    'underperform', 'underperformed', 'decline', 'declined',
    
    # Problems
    'loss', 'losses', 'lost', 'drop', 'dropped', 'fall', 'fell',
    'plunge', 'plunged', 'crash', 'crashed', 'tumble', 'tumbled',
    'slump', 'slumped', 'sink', 'sank', 'collapse', 'collapsed',
    
    # Guidance & Outlook
    'cut', 'cuts', 'lowered', 'downgrade', 'downgraded', 'bearish',
    'pessimistic', 'concerned', 'concerns', 'warning', 'warns',
    'below-consensus', 'guidance-cut', 'revised-down',
    
    # Risk Events
    'lawsuit', 'sued', 'investigation', 'probe', 'fraud', 'scandal',
    'recall', 'layoff', 'layoffs', 'restructuring', 'bankruptcy',
    'default', 'debt', 'fine', 'fined', 'penalty', 'violation'
}

# Intensity modifiers (multiply sentiment score)
INTENSIFIERS = {
    'very': 1.5, 'extremely': 2.0, 'significantly': 1.5,
    'sharply': 1.5, 'dramatically': 2.0, 'substantially': 1.5,
    'slightly': 0.5, 'marginally': 0.5, 'modest': 0.7
}

# Negation words (flip sentiment)
NEGATIONS = {'not', 'no', 'never', 'neither', 'hardly', 'barely', 'fails', 'failed'}
```

##### Keyword Sentiment Scoring

```python
import re
from typing import Dict, Tuple
from collections import Counter

def keyword_sentiment(
    text: str,
    positive_words: set = POSITIVE_KEYWORDS,
    negative_words: set = NEGATIVE_KEYWORDS
) -> Dict[str, float]:
    """
    Calculate sentiment score based on keyword frequency.
    
    Returns:
        {
            'score': float (-1 to +1),
            'positive_count': int,
            'negative_count': int,
            'signal': str ('positive', 'negative', 'neutral'),
            'matched_positive': list,
            'matched_negative': list
        }
    """
    # Normalize text
    text_lower = text.lower()
    words = re.findall(r'\b\w+\b', text_lower)
    
    # Count matches
    matched_positive = [w for w in words if w in positive_words]
    matched_negative = [w for w in words if w in negative_words]
    
    pos_count = len(matched_positive)
    neg_count = len(matched_negative)
    total = pos_count + neg_count
    
    # Calculate score (-1 to +1)
    if total == 0:
        score = 0.0
        signal = 'neutral'
    else:
        score = (pos_count - neg_count) / total
        if score > 0.2:
            signal = 'positive'
        elif score < -0.2:
            signal = 'negative'
        else:
            signal = 'neutral'
    
    return {
        'score': round(score, 3),
        'positive_count': pos_count,
        'negative_count': neg_count,
        'signal': signal,
        'matched_positive': list(set(matched_positive)),
        'matched_negative': list(set(matched_negative))
    }


# Example usage:
headline = "Apple beats earnings expectations, raises guidance amid strong iPhone demand"
result = keyword_sentiment(headline)
# → {'score': 1.0, 'positive_count': 4, 'negative_count': 0, 'signal': 'positive',
#    'matched_positive': ['beats', 'raises', 'strong', 'demand'], 'matched_negative': []}
```

##### Advanced: Negation Handling

```python
def keyword_sentiment_with_negation(text: str) -> Dict[str, float]:
    """
    Handle negations: "not good" → negative, "not bad" → positive
    """
    text_lower = text.lower()
    words = re.findall(r'\b\w+\b', text_lower)
    
    pos_score = 0
    neg_score = 0
    negation_window = 3  # Words to look ahead after negation
    
    i = 0
    while i < len(words):
        word = words[i]
        
        # Check for negation
        is_negated = any(
            words[j] in NEGATIONS 
            for j in range(max(0, i - negation_window), i)
        )
        
        if word in POSITIVE_KEYWORDS:
            if is_negated:
                neg_score += 1  # "not good" → negative
            else:
                pos_score += 1
        elif word in NEGATIVE_KEYWORDS:
            if is_negated:
                pos_score += 0.5  # "not bad" → slightly positive
            else:
                neg_score += 1
        
        i += 1
    
    total = pos_score + neg_score
    score = (pos_score - neg_score) / total if total > 0 else 0
    
    return {'score': round(score, 3), 'pos': pos_score, 'neg': neg_score}


# Example:
keyword_sentiment_with_negation("Apple did not miss expectations")
# → {'score': 0.5, 'pos': 0.5, 'neg': 0}  (negated negative = slight positive)
```

##### TF-IDF Weighted Keywords

```python
from sklearn.feature_extraction.text import TfidfVectorizer
import numpy as np

class TfidfKeywordSentiment:
    """
    Weight keywords by TF-IDF: rare keywords matter more.
    """
    
    def __init__(self, corpus: list = None):
        self.vectorizer = TfidfVectorizer(
            vocabulary=list(POSITIVE_KEYWORDS | NEGATIVE_KEYWORDS),
            lowercase=True
        )
        if corpus:
            self.vectorizer.fit(corpus)
    
    def score(self, text: str) -> float:
        """Score using TF-IDF weighted keywords."""
        tfidf = self.vectorizer.transform([text]).toarray()[0]
        feature_names = self.vectorizer.get_feature_names_out()
        
        pos_score = sum(
            tfidf[i] for i, word in enumerate(feature_names) 
            if word in POSITIVE_KEYWORDS
        )
        neg_score = sum(
            tfidf[i] for i, word in enumerate(feature_names) 
            if word in NEGATIVE_KEYWORDS
        )
        
        total = pos_score + neg_score
        return (pos_score - neg_score) / total if total > 0 else 0
```

##### Aggregate News Sentiment for a Stock

```python
def aggregate_stock_sentiment(
    headlines: list,
    method: str = 'keyword'  # 'keyword' or 'finbert'
) -> Dict[str, float]:
    """
    Aggregate sentiment across multiple headlines for one stock.
    
    Args:
        headlines: List of news headlines/snippets
        method: 'keyword' (fast, free) or 'finbert' (accurate, slower)
    
    Returns:
        Aggregated sentiment with confidence
    """
    if not headlines:
        return {'score': 0, 'signal': 'neutral', 'confidence': 0, 'n_articles': 0}
    
    scores = []
    for headline in headlines:
        if method == 'keyword':
            result = keyword_sentiment(headline)
            scores.append(result['score'])
        else:  # finbert
            result = get_sentiment(headline)  # FinBERT function
            scores.append(result['positive'] - result['negative'])
    
    avg_score = np.mean(scores)
    std_score = np.std(scores) if len(scores) > 1 else 0
    
    # Confidence based on agreement (low std = high confidence)
    confidence = max(0, 1 - std_score)
    
    if avg_score > 0.2:
        signal = 'positive'
    elif avg_score < -0.2:
        signal = 'negative'
    else:
        signal = 'neutral'
    
    return {
        'score': round(avg_score, 3),
        'signal': signal,
        'confidence': round(confidence, 2),
        'n_articles': len(headlines),
        'std': round(std_score, 3)
    }


# Example:
headlines = [
    "Apple beats Q4 earnings, strong iPhone sales",
    "Apple raises guidance for holiday quarter", 
    "Analysts upgrade Apple after stellar results"
]
aggregate_stock_sentiment(headlines, method='keyword')
# → {'score': 0.85, 'signal': 'positive', 'confidence': 0.92, 'n_articles': 3}
```

##### When to Use Keywords vs FinBERT

| Criteria | Keywords | FinBERT |
|----------|----------|---------|
| **Speed** | ✅ 1000s/sec | ⚠️ 10-50/sec |
| **Cost** | ✅ Free (no GPU) | ⚠️ Needs GPU or slow on CPU |
| **Accuracy** | Good (70-80%) | Better (85-90%) |
| **Interpretability** | ✅ Explainable | ⚠️ Black box |
| **MVP Phase** | ✅ Recommended | Phase 2+ |
| **Nuance/Sarcasm** | ❌ Misses | ✅ Better |

**Recommendation:** Start with keywords for MVP, add FinBERT in Phase 2 for comparison.

##### Extending the Dictionary

```python
# Add industry-specific keywords
TECH_POSITIVE = {'innovation', 'patent', 'ai', 'cloud', 'subscription', 'recurring'}
TECH_NEGATIVE = {'hack', 'breach', 'antitrust', 'monopoly', 'regulation'}

FINANCE_POSITIVE = {'loan-growth', 'nim', 'credit-quality', 'deposits'}
FINANCE_NEGATIVE = {'provision', 'charge-off', 'delinquency', 'exposure'}

# Combine for sector-specific analysis
def get_sector_keywords(sector: str) -> Tuple[set, set]:
    base_pos = POSITIVE_KEYWORDS.copy()
    base_neg = NEGATIVE_KEYWORDS.copy()
    
    if sector == 'Technology':
        base_pos.update(TECH_POSITIVE)
        base_neg.update(TECH_NEGATIVE)
    elif sector == 'Financials':
        base_pos.update(FINANCE_POSITIVE)
        base_neg.update(FINANCE_NEGATIVE)
    
    return base_pos, base_neg
```

---

### 2. Earnings Surprise Model

#### Features
- Historical earnings surprise patterns
- Analyst estimate dispersion
- Management guidance trends
- Sector-level earnings momentum

#### Model: Gradient Boosting (XGBoost)
```python
import xgboost as xgb

features = [
    'prev_surprise_1q', 'prev_surprise_2q', 'prev_surprise_3q',
    'estimate_revisions_30d', 'analyst_dispersion',
    'guidance_change', 'sector_earnings_momentum'
]

model = xgb.XGBRegressor(
    n_estimators=100,
    max_depth=5,
    learning_rate=0.1,
    objective='reg:squarederror'
)
```

### 3. Macro Regime Detection

> 📖 **Academic Foundation:** Hamilton (1989) Regime-Switching Models, Guidolin & Timmermann (2007). See [papers/REFERENCES.md](papers/REFERENCES.md).

#### Model: Hidden Markov Model (HMM)
Detect market regimes: Expansion, Contraction, Recovery, Overheating

#### Features
- Yield curve slope (10Y - 2Y)
- Credit spreads (BAA - AAA)
- VIX levels
- PMI trends

### 4. Multi-Factor Ranking Model

> 📖 **Academic Foundation:** Fama-French Three-Factor Model (1993), Carhart Four-Factor Model (1997), Fama-French Five-Factor Model (2015). See [papers/REFERENCES.md](papers/REFERENCES.md).

#### Factor Definitions

**Value Factors:**
- P/E ratio (trailing and forward)
- P/B ratio
- EV/EBITDA
- Free cash flow yield

**Quality Factors:**
- ROE, ROA
- Gross margin
- Debt/Equity
- Interest coverage

**Momentum Factors:**
- 3-month return
- 6-month return
- 52-week relative strength
- Earnings momentum

**Growth Factors:**
- Revenue growth (YoY, QoQ)
- EPS growth
- Analyst estimate revisions

#### Composite Score Calculation
```python
def calculate_composite_score(stock_data):
    # Normalize each factor to 0-100 scale using percentile ranking
    fundamental_score = (
        0.25 * value_score +
        0.35 * quality_score +
        0.40 * growth_score
    )
    
    sentiment_score = (
        0.50 * news_sentiment +
        0.30 * earnings_call_sentiment +
        0.20 * social_sentiment
    )
    
    macro_score = sector_macro_alignment(current_regime)
    
    technical_score = (
        0.40 * momentum_score +
        0.30 * relative_strength +
        0.30 * trend_score
    )
    
    composite = (
        0.35 * fundamental_score +
        0.25 * sentiment_score +
        0.20 * macro_score +
        0.20 * technical_score
    )
    
    return composite
```

---

### Score Explainability — Why This Score?

> 🎯 **Design Goal:** The Busy Builder doesn't want a black box. They're sophisticated enough to understand the reasoning and want to validate the model's logic. Explainability builds trust and enables informed decisions.

#### Explainability Principles

1. **Every score has a story** — Users can drill into any stock's score and see exactly which factors drove it up or down
2. **Plain English summaries** — Not just numbers, but human-readable explanations
3. **Comparison context** — Show how this stock compares to sector peers and market average
4. **Historical tracking** — How has the score changed over time, and why?

#### Component Breakdown (Per Stock)

```
┌─────────────────────────────────────────────────────────────────┐
│  AAPL Score: 85                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  FUNDAMENTALS (35%)                          Score: 88         │
│  ├─ Value:    72  (P/E slightly high vs sector)                │
│  ├─ Quality:  95  (Strong margins, low debt)                   │
│  └─ Growth:   91  (Revenue +12% YoY, EPS beat)                 │
│                                                                 │
│  SENTIMENT (25%)                             Score: 82         │
│  ├─ News:     85  (Positive iPhone coverage)                   │
│  ├─ Earnings: 78  (Call tone: confident)                       │
│  └─ Social:   80  (Retail bullish)                             │
│                                                                 │
│  MACRO (20%)                                 Score: 75         │
│  └─ Tech sector neutral in current rate environment            │
│                                                                 │
│  TECHNICAL (20%)                             Score: 90         │
│  ├─ Momentum: 92  (Above all MAs)                              │
│  ├─ RSI:      65  (Strong but not overbought)                  │
│  └─ Trend:    88  (Higher highs, higher lows)                  │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│  📝 SUMMARY                                                     │
│  "Strong buy driven by excellent fundamentals and momentum.     │
│   Slight valuation concern but offset by quality metrics.       │
│   Watch for Fed policy impact on tech sector."                  │
└─────────────────────────────────────────────────────────────────┘
```

#### Auto-Generated Explanations

Generate human-readable summaries for each score component:

| Score Range | Fundamental Template |
|-------------|---------------------|
| 90-100 | "Exceptional fundamentals: {top_factor} stands out" |
| 75-89 | "Strong fundamentals with {strength}, minor concern on {weakness}" |
| 50-74 | "Mixed fundamentals: {strength} offset by {weakness}" |
| 25-49 | "Weak fundamentals: {primary_concern} is concerning" |
| 0-24 | "Poor fundamentals across the board, especially {worst_factor}" |

#### Key Drivers (What Moved the Score?)

When score changes week-over-week, highlight the top 3 factors:

```
AAPL: 78 → 85 (+7 pts)

📈 What improved:
• Earnings beat (+4 pts) — EPS $2.18 vs $2.10 expected
• News sentiment (+2 pts) — iPhone 16 reviews positive
• Technical breakout (+1 pt) — Crossed 50-day MA

📉 What declined:
• Macro headwind (-1 pt) — Fed hawkish tone
```

#### Implementation Notes (TBD)

> ⚠️ **Implementation details to be determined:**
> - Storage format for explanation metadata
> - NLG (Natural Language Generation) approach for summaries
> - Caching strategy for pre-computed explanations
> - Localization considerations
> - Explanation versioning (when model changes)

The explainability layer should be designed as a separate module that can evolve independently of the scoring model itself.

---

## Buy/Sell Logic

### Signal Generation

#### Buy Signals (Entry)
| Condition | Description | Weight |
|-----------|-------------|--------|
| Score > 75 | High composite score | Required |
| Score Δ > 10 | Week-over-week improvement | +1 |
| Positive Earnings Surprise | Beat estimates by >5% | +1 |
| Bullish Sentiment Shift | Sentiment score improved significantly | +1 |
| Technical Breakout | Price above 50-day MA with volume | +1 |

**Entry Threshold:** Sum of conditions ≥ 3

#### Sell Signals (Exit)
| Condition | Description | Priority |
|-----------|-------------|----------|
| Score < 40 | Low composite score | High |
| Score Δ < -15 | Sharp deterioration | High |
| Stop-Loss Hit | -10% from entry | Critical |
| Trailing Stop | -7% from peak | Critical |
| Max Hold Period | 90 days without profit | Medium |
| Negative Earnings Surprise | Miss by >10% | Medium |

### Position Sizing

#### Kelly Criterion (Modified)
> 📖 **Academic Foundation:** Kelly (1956) — optimal bet sizing for long-term growth. See [papers/REFERENCES.md](papers/REFERENCES.md).
```python
def calculate_position_size(win_rate, avg_win, avg_loss, max_position=0.10):
    """
    Modified Kelly Criterion for position sizing
    """
    kelly = (win_rate * avg_win - (1 - win_rate) * avg_loss) / avg_win
    # Use half-Kelly for safety
    half_kelly = kelly / 2
    # Cap at maximum position size
    return min(max(half_kelly, 0.02), max_position)
```

#### Risk Parameters
- **Maximum position size:** 10% of portfolio
- **Maximum sector exposure:** 30%
- **Maximum correlated positions:** 5 stocks with correlation > 0.7
- **Minimum cash buffer:** 10%

---

### Portfolio Balancing — Volatility-Based Allocation

> **Goal:** Prevent the portfolio from being skewed toward high-risk (high-volatility) stocks. Each position contributes roughly equal risk, not equal dollars.

#### The Problem with Equal-Weight

Equal-dollar allocation ignores risk:
```
Portfolio: $10,000 each in AAPL and NVDA

AAPL volatility (σ): 25% annually
NVDA volatility (σ): 55% annually

Risk contribution:
- AAPL: $10,000 × 25% = $2,500 risk
- NVDA: $10,000 × 55% = $5,500 risk

→ NVDA contributes 69% of portfolio risk despite being 50% of value!
```

#### Solution: Inverse Volatility Weighting ✅ FREE

Allocate more to stable stocks, less to volatile stocks.

```python
import numpy as np
import pandas as pd

def inverse_volatility_weights(returns_df: pd.DataFrame, lookback: int = 60) -> pd.Series:
    """
    Calculate portfolio weights inversely proportional to volatility.
    
    Args:
        returns_df: DataFrame of daily returns (columns = tickers)
        lookback: Days to calculate volatility (60 = ~3 months)
    
    Returns:
        Series of weights that sum to 1.0
    """
    # Calculate annualized volatility for each stock
    volatility = returns_df.tail(lookback).std() * np.sqrt(252)
    
    # Inverse volatility (lower vol = higher weight)
    inv_vol = 1 / volatility
    
    # Normalize to sum to 1
    weights = inv_vol / inv_vol.sum()
    
    return weights


# Example output:
# AAPL (σ=25%): weight = 0.15 (15%)
# MSFT (σ=22%): weight = 0.17 (17%)
# NVDA (σ=55%): weight = 0.07 (7%)   ← High vol = low weight
# JNJ  (σ=18%): weight = 0.21 (21%)  ← Low vol = high weight
```

#### Enhanced: Risk Parity (Equal Risk Contribution)

Each stock contributes equal volatility to the portfolio.

```python
def risk_parity_weights(returns_df: pd.DataFrame, lookback: int = 60) -> pd.Series:
    """
    Risk Parity: Each position contributes equal risk.
    
    Target: weight_i × σ_i = constant for all i
    """
    volatility = returns_df.tail(lookback).std() * np.sqrt(252)
    
    # Target: w_i * σ_i = equal → w_i = 1/σ_i (normalized)
    inv_vol = 1 / volatility
    weights = inv_vol / inv_vol.sum()
    
    return weights


def verify_risk_contribution(weights: pd.Series, volatility: pd.Series) -> pd.Series:
    """Verify each position's risk contribution."""
    risk_contrib = weights * volatility
    risk_contrib_pct = risk_contrib / risk_contrib.sum() * 100
    return risk_contrib_pct  # Should be ~equal for each stock
```

#### Adding Score-Based Tilts

Combine AI scores with volatility weighting:

```python
def score_adjusted_weights(
    returns_df: pd.DataFrame,
    scores: pd.Series,  # AI scores 0-100
    vol_weight: float = 0.6,  # 60% based on volatility
    score_weight: float = 0.4,  # 40% based on AI score
    lookback: int = 60
) -> pd.Series:
    """
    Blend inverse-volatility weights with AI score weights.
    
    - High score + low volatility → highest weight
    - Low score + high volatility → lowest weight
    """
    # Base weights from inverse volatility
    vol_weights = inverse_volatility_weights(returns_df, lookback)
    
    # Score-based weights (higher score = higher weight)
    score_weights = scores / scores.sum()
    
    # Blend
    combined = vol_weight * vol_weights + score_weight * score_weights
    
    # Normalize
    final_weights = combined / combined.sum()
    
    return final_weights
```

#### Constraints & Caps

Apply hard limits to prevent concentration:

```python
def apply_constraints(
    weights: pd.Series,
    max_position: float = 0.10,      # Max 10% in any stock
    min_position: float = 0.02,      # Min 2% if included
    max_sector: float = 0.30,        # Max 30% in any sector
    sectors: pd.Series = None        # Ticker → Sector mapping
) -> pd.Series:
    """
    Apply position and sector constraints.
    """
    constrained = weights.copy()
    
    # Cap individual positions
    constrained = constrained.clip(upper=max_position)
    
    # Apply minimum (or exclude if too small)
    constrained[constrained < min_position] = 0
    
    # Sector caps (if sector mapping provided)
    if sectors is not None:
        for sector in sectors.unique():
            sector_tickers = sectors[sectors == sector].index
            sector_weight = constrained[sector_tickers].sum()
            
            if sector_weight > max_sector:
                # Scale down sector proportionally
                scale = max_sector / sector_weight
                constrained[sector_tickers] *= scale
    
    # Re-normalize to sum to 1
    constrained = constrained / constrained.sum()
    
    return constrained
```

#### Complete Rebalancing Flow

```python
def calculate_target_portfolio(
    current_prices: pd.Series,
    returns_df: pd.DataFrame,
    ai_scores: pd.Series,
    sectors: pd.Series,
    portfolio_value: float
) -> pd.DataFrame:
    """
    Weekly rebalancing calculation.
    
    Returns DataFrame with target positions.
    """
    # 1. Calculate blended weights
    raw_weights = score_adjusted_weights(returns_df, ai_scores)
    
    # 2. Apply constraints
    final_weights = apply_constraints(
        raw_weights,
        max_position=0.10,
        min_position=0.02,
        max_sector=0.30,
        sectors=sectors
    )
    
    # 3. Calculate dollar amounts and shares
    target_dollars = final_weights * portfolio_value
    target_shares = (target_dollars / current_prices).round()
    
    # 4. Build output
    result = pd.DataFrame({
        'ticker': final_weights.index,
        'weight': final_weights.values,
        'target_dollars': target_dollars.values,
        'target_shares': target_shares.values,
        'volatility': returns_df.std() * np.sqrt(252),
        'ai_score': ai_scores.values
    })
    
    return result
```

#### Rebalancing Triggers

Don't rebalance constantly — only when needed:

| Trigger | Threshold | Action |
|---------|-----------|--------|
| **Time-based** | Weekly (Sunday) | Full recalculation |
| **Drift** | Position drifts >3% from target | Rebalance that position |
| **Score change** | AI score changes signal | Review position |
| **New money** | Cash > 5% of portfolio | Deploy to underweight |
| **Volatility spike** | Stock vol jumps >50% | Reduce position |

```python
def needs_rebalancing(current_weights: pd.Series, target_weights: pd.Series, threshold: float = 0.03) -> bool:
    """Check if any position has drifted beyond threshold."""
    drift = (current_weights - target_weights).abs()
    return (drift > threshold).any()
```

#### Summary: Portfolio Balancing Rules

| Rule | Implementation | Why |
|------|----------------|-----|
| **Inverse volatility** | Weight ∝ 1/σ | Equal risk, not equal dollars |
| **Max position** | ≤10% per stock | No single stock dominates |
| **Max sector** | ≤30% per sector | Diversification |
| **Min position** | ≥2% or exclude | Avoid noise from tiny positions |
| **Weekly rebalance** | Sunday night | Aligned with score updates |
| **Drift trigger** | >3% drift | Don't over-trade |

#### Libraries (All FREE ✅)

| Library | Purpose | Link |
|---------|---------|------|
| **NumPy** | Matrix math | Built-in |
| **Pandas** | Data manipulation | Built-in |
| **PyPortfolioOpt** | Portfolio optimization | [github.com/robertmartin8/PyPortfolioOpt](https://github.com/robertmartin8/PyPortfolioOpt) |
| **Riskfolio-Lib** | Advanced risk parity | [github.com/dcajasn/Riskfolio-Lib](https://github.com/dcajasn/Riskfolio-Lib) |

### Order Types (IBKR-Style)

> **Goal:** Provide full order type flexibility similar to Interactive Brokers platform.

#### Supported Order Types

| Order Type | Description | Use Case |
|------------|-------------|----------|
| **Market** | Execute immediately at best available price | Urgency, high liquidity stocks |
| **Limit** | Execute only at specified price or better | Control entry/exit price |
| **Stop** | Trigger market order when price reaches level | Stop-loss protection |
| **Stop-Limit** | Trigger limit order when price reaches level | Controlled stop-loss |
| **Trailing Stop** | Stop that moves with price ($ or %) | Lock in profits |
| **Trailing Stop-Limit** | Trailing stop with limit order | Precise profit lock |

#### Order Entry Screen (IBKR-Style)

```
┌─────────────────────────────────────────────────────────────────┐
│  Order Entry                                               ✕    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  AAPL · Apple Inc.                                             │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Last: $185.42    Bid: $185.40    Ask: $185.44          │   │
│  │ Volume: 45.2M    Day Range: $180.85 - $186.20          │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  Action                                                         │
│  ┌──────────────────────┬──────────────────────┐               │
│  │        BUY           │        SELL          │               │
│  └──────────────────────┴──────────────────────┘               │
│                                                                 │
│  Quantity                               [ Shares ▼ ]           │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                        100                              │   │
│  └─────────────────────────────────────────────────────────┘   │
│  [ 25 ]  [ 50 ]  [ 100 ]  [ All ]     Est: $18,544.00         │
│                                                                 │
│  ─────────────────────────────────────────────────────────────  │
│                                                                 │
│  Order Type                                                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Limit                                              ▼   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─ Limit Price ─────────────────────────────────────────┐     │
│  │                                                       │     │
│  │  [ - ]         $185.40              [ + ]            │     │
│  │                                                       │     │
│  │  [ Bid ]  [ Mid ]  [ Ask ]  [ Last ]                 │     │
│  └───────────────────────────────────────────────────────┘     │
│                                                                 │
│  Time in Force                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Day                                                ▼   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ─────────────────────────────────────────────────────────────  │
│                                                                 │
│  [ + Add Stop-Loss ]              [ + Add Take-Profit ]        │
│                                                                 │
│  ─────────────────────────────────────────────────────────────  │
│                                                                 │
│  Order Summary                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Action              BUY                                 │   │
│  │ Symbol              AAPL                                │   │
│  │ Quantity            100 shares                          │   │
│  │ Order Type          Limit @ $185.40                     │   │
│  │ Time in Force       Day                                 │   │
│  │ Est. Total          $18,540.00                          │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  Available Buying Power: $25,000.00                            │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                   PREVIEW ORDER                         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ⚠ Paper Trading Mode                                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### Stop-Loss / Take-Profit Attachment

```
┌─────────────────────────────────────────────────────────────────┐
│  Attached Orders (Optional)                                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ☑ STOP-LOSS                                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Type:   [ Stop-Limit ▼ ]                                │   │
│  │ Stop:   $176.15  (-5%)     [ $ ▼ ]                     │   │
│  │ Limit:  $175.50  (-5.4%)                                │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ☑ TAKE-PROFIT                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Type:   [ Trailing Stop ▼ ]                             │   │
│  │ Trail:  7%                  [ % ▼ ]                     │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### Time in Force Options

| Option | Description |
|--------|-------------|
| **DAY** | Expires at market close |
| **GTC** | Good-til-cancelled (90 days max) |
| **IOC** | Immediate or cancel (fill what you can) |
| **FOK** | Fill or kill (all or nothing) |
| **GTD** | Good-til-date (custom expiry) |

#### Order Types Data Model

```swift
enum OrderType: String, Codable {
    case market = "MKT"
    case limit = "LMT"
    case stop = "STP"
    case stopLimit = "STP_LMT"
    case trailingStop = "TRAIL"
    case trailingStopLimit = "TRAIL_LMT"
}

enum TimeInForce: String, Codable {
    case day = "DAY"
    case gtc = "GTC"
    case ioc = "IOC"
    case fok = "FOK"
}

struct Order: Codable {
    let ticker: String
    let action: OrderAction  // .buy or .sell
    let quantity: Int
    let orderType: OrderType
    let timeInForce: TimeInForce
    
    // Price fields (optional based on order type)
    var limitPrice: Decimal?
    var stopPrice: Decimal?
    var trailAmount: Decimal?
    var trailPercent: Decimal?
    
    // Attached orders
    var stopLoss: AttachedOrder?
    var takeProfit: AttachedOrder?
}

struct AttachedOrder: Codable {
    let orderType: OrderType
    var triggerPrice: Decimal?
    var limitPrice: Decimal?
    var trailPercent: Decimal?
}
```

---

### Performance Chart Screen (1D, 1W, 1M, etc.)

> **Goal:** Show stock price performance across multiple time periods with interactive chart.

#### Performance Chart Screen Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  ←  AAPL Performance                                    ☆   ⋮  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Apple Inc.                                                     │
│                                                                 │
│  $185.42                                                        │
│  ▲ $4.21 (+2.33%)  Today                                       │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                                                         │   │
│  │  $190 ┤                                   ╱             │   │
│  │       │                              ╱───╱              │   │
│  │  $185 ┤                    ╱────────╱                   │   │
│  │       │               ╱───╱                             │   │
│  │  $180 ┤         ╱────╱                                  │   │
│  │       │    ╱───╱                                        │   │
│  │  $175 ┤───╱                                             │   │
│  │       │                                                 │   │
│  │  $170 ┼─────────────────────────────────────────────    │   │
│  │        9:30   10:30   11:30   12:30   13:30   14:30     │   │
│  │                                                         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌──────┬──────┬──────┬──────┬──────┬──────┬──────┬───────┐    │
│  │  1D  │  1W  │  1M  │  3M  │  6M  │  1Y  │  5Y  │  ALL  │    │
│  └──────┴──────┴──────┴──────┴──────┴──────┴──────┴───────┘    │
│                                                                 │
│  ─────────────────────────────────────────────────────────────  │
│                                                                 │
│  PERIOD PERFORMANCE                                             │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                                                         │   │
│  │  1 Day     ▲ +2.33%     │  1 Year    ▲ +28.45%        │   │
│  │  1 Week    ▲ +4.12%     │  5 Years   ▲ +312.50%       │   │
│  │  1 Month   ▲ +8.75%     │  YTD       ▲ +15.20%        │   │
│  │  3 Months  ▲ +12.30%    │  Max       ▲ +1,245.00%     │   │
│  │                                                         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ─────────────────────────────────────────────────────────────  │
│                                                                 │
│  COMPARE TO                                                     │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  [ ] S&P 500 (SPY)                         ▲ +18.20%   │    │
│  │  [ ] Sector (XLK)                          ▲ +22.15%   │    │
│  │  [ ] MSFT                                  ▲ +25.30%   │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                 │
│  ─────────────────────────────────────────────────────────────  │
│                                                                 │
│  KEY STATISTICS                                                 │
│  ┌───────────────────┬──────────────────────────────────────┐  │
│  │ 52-Week High      │  $198.23  (-6.4% from high)         │  │
│  │ 52-Week Low       │  $142.18  (+30.4% from low)         │  │
│  │ Avg Volume        │  52.1M                               │  │
│  │ Market Cap        │  $2.89T                              │  │
│  │ P/E Ratio         │  28.45                               │  │
│  │ Dividend Yield    │  0.52%                               │  │
│  └───────────────────┴──────────────────────────────────────┘  │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                      TRADE AAPL                         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│    Home      Scores      Trade      Portfolio    Settings      │
└─────────────────────────────────────────────────────────────────┘
```

#### Time Period Options

| Period | Data Points | Interval | Chart Type |
|--------|-------------|----------|------------|
| **1D** | 78 | 5 min | Line/Area |
| **1W** | 5 | Daily | Line/Candle |
| **1M** | 22 | Daily | Line/Candle |
| **3M** | 65 | Daily | Line/Candle |
| **6M** | 130 | Daily | Line/Candle |
| **1Y** | 252 | Daily | Line/Candle |
| **5Y** | 260 | Weekly | Line |
| **ALL** | Variable | Monthly | Line |

#### Chart Implementation

```swift
struct PerformanceChartView: View {
    let ticker: String
    @State private var selectedPeriod: ChartPeriod = .oneDay
    @State private var chartData: [PricePoint] = []
    @State private var comparisonEnabled: Set<String> = []
    
    enum ChartPeriod: String, CaseIterable {
        case oneDay = "1D"
        case oneWeek = "1W"
        case oneMonth = "1M"
        case threeMonths = "3M"
        case sixMonths = "6M"
        case oneYear = "1Y"
        case fiveYears = "5Y"
        case all = "ALL"
        
        var interval: String {
            switch self {
            case .oneDay: return "5m"
            case .oneWeek, .oneMonth, .threeMonths, .sixMonths, .oneYear: return "1d"
            case .fiveYears: return "1wk"
            case .all: return "1mo"
            }
        }
    }
    
    var body: some View {
        VStack(spacing: 16) {
            // Price header
            PriceHeaderView(ticker: ticker, change: calculateChange())
            
            // Interactive chart
            Chart(chartData) { point in
                LineMark(
                    x: .value("Time", point.date),
                    y: .value("Price", point.price)
                )
                .foregroundStyle(chartColor)
                
                AreaMark(
                    x: .value("Time", point.date),
                    y: .value("Price", point.price)
                )
                .foregroundStyle(chartGradient)
            }
            .chartYScale(domain: yAxisRange)
            .frame(height: 250)
            
            // Period selector
            HStack(spacing: 0) {
                ForEach(ChartPeriod.allCases, id: \.self) { period in
                    Button(period.rawValue) {
                        selectedPeriod = period
                        loadChartData()
                    }
                    .buttonStyle(PeriodButtonStyle(isSelected: selectedPeriod == period))
                }
            }
            
            // Period performance grid
            PerformanceGridView(ticker: ticker)
            
            // Comparison toggles
            ComparisonSelectorView(enabled: $comparisonEnabled)
            
            // Key statistics
            KeyStatisticsView(ticker: ticker)
            
            // Trade button
            TradeButton(ticker: ticker)
        }
    }
    
    var chartColor: Color {
        let change = calculateChange()
        return change >= 0 ? .green : .red
    }
}
```

#### Performance Data Model

```swift
struct PerformanceData: Codable {
    let ticker: String
    let periods: [PeriodPerformance]
    let keyStats: KeyStatistics
}

struct PeriodPerformance: Codable {
    let period: String  // "1D", "1W", etc.
    let startPrice: Decimal
    let endPrice: Decimal
    let change: Decimal
    let changePercent: Decimal
    let high: Decimal
    let low: Decimal
}

struct KeyStatistics: Codable {
    let high52Week: Decimal
    let low52Week: Decimal
    let avgVolume: Int
    let marketCap: Decimal
    let peRatio: Decimal?
    let dividendYield: Decimal?
    let beta: Decimal?
}
```

#### API Endpoint

```python
@app.get("/api/v1/stocks/{ticker}/performance")
def get_stock_performance(ticker: str, period: str = "1D") -> dict:
    """
    Get stock performance data for charting.
    
    Args:
        ticker: Stock symbol
        period: Time period (1D, 1W, 1M, 3M, 6M, 1Y, 5Y, ALL)
    
    Returns:
        {
            "ticker": "AAPL",
            "period": "1M",
            "prices": [{"date": "2026-01-02", "open": 180.5, "high": 182.0, ...}, ...],
            "performance": {
                "1D": {"change": 4.21, "change_pct": 2.33},
                "1W": {"change": 7.50, "change_pct": 4.12},
                ...
            },
            "key_stats": {...}
        }
    """
    prices = get_historical_prices(ticker, period)
    performance = calculate_all_period_performance(ticker)
    stats = get_key_statistics(ticker)
    
    return {
        "ticker": ticker,
        "period": period,
        "prices": prices,
        "performance": performance,
        "key_stats": stats,
    }
```

---

## Evaluation Metrics

### ⚠️ Critical: Separate Recommendation vs Non-Recommendation Performance

> **Why?** To evaluate if the recommendation system actually adds value, we MUST track performance separately for trades driven by recommendations vs user's own decisions.

#### Trade Classification

```
┌─────────────────────────────────────────────────────────────────┐
│                    TRADE ATTRIBUTION                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   RECOMMENDATION-DRIVEN                                         │
│   ────────────────────                                          │
│   • User bought stock with score ≥ 70 (BUY signal)             │
│   • User sold stock with score < 40 (SELL signal)              │
│   • Trade executed within 7 days of signal                      │
│   → Attribute P&L to recommendation system                      │
│                                                                 │
│   USER-INITIATED (Non-Recommendation)                           │
│   ───────────────────────────────────                          │
│   • User bought stock with score < 70 (no BUY signal)          │
│   • User held despite SELL signal                               │
│   • User's own stock picks outside top recommendations          │
│   → Attribute P&L to user decisions                             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### Data Model for Attribution

```python
from enum import Enum
from dataclasses import dataclass
from datetime import datetime

class TradeAttribution(Enum):
    RECOMMENDATION = "recommendation"   # Followed system signal
    USER_INITIATED = "user_initiated"   # User's own decision
    MIXED = "mixed"                      # Partial overlap

@dataclass
class Trade:
    ticker: str
    action: str  # 'buy' or 'sell'
    quantity: int
    price: float
    timestamp: datetime
    
    # Attribution fields
    score_at_trade: int              # Stock's score when traded
    signal_at_trade: str             # 'BUY', 'HOLD', 'SELL'
    attribution: TradeAttribution    # Who drove this decision?
    days_since_signal: int           # How fresh was the signal?


def classify_trade(trade: Trade) -> TradeAttribution:
    """
    Classify trade as recommendation-driven or user-initiated.
    """
    # BUY trade
    if trade.action == 'buy':
        if trade.signal_at_trade == 'BUY' and trade.days_since_signal <= 7:
            return TradeAttribution.RECOMMENDATION
        else:
            return TradeAttribution.USER_INITIATED
    
    # SELL trade
    elif trade.action == 'sell':
        if trade.signal_at_trade == 'SELL' and trade.days_since_signal <= 7:
            return TradeAttribution.RECOMMENDATION
        else:
            return TradeAttribution.USER_INITIATED
    
    return TradeAttribution.USER_INITIATED
```

#### Separate Performance Tracking

```python
@dataclass
class PerformanceMetrics:
    total_return: float
    sharpe_ratio: float
    win_rate: float
    avg_gain: float
    avg_loss: float
    trade_count: int


def calculate_separate_performance(trades: list, positions: list) -> dict:
    """
    Calculate performance metrics separately for each attribution type.
    
    Returns:
        {
            'recommendation': PerformanceMetrics,
            'user_initiated': PerformanceMetrics,
            'combined': PerformanceMetrics,
            'recommendation_value_add': float  # Alpha from recommendations
        }
    """
    # Separate trades by attribution
    rec_trades = [t for t in trades if t.attribution == TradeAttribution.RECOMMENDATION]
    user_trades = [t for t in trades if t.attribution == TradeAttribution.USER_INITIATED]
    
    # Calculate metrics for each
    rec_metrics = calculate_metrics(rec_trades)
    user_metrics = calculate_metrics(user_trades)
    combined_metrics = calculate_metrics(trades)
    
    # Value add = recommendation performance - user performance
    value_add = rec_metrics.total_return - user_metrics.total_return
    
    return {
        'recommendation': rec_metrics,
        'user_initiated': user_metrics,
        'combined': combined_metrics,
        'recommendation_value_add': value_add,
    }
```

#### Performance Dashboard (Dual View)

```
┌─────────────────────────────────────────────────────────────────┐
│                   PERFORMANCE ATTRIBUTION                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  📊 RECOMMENDATION-DRIVEN TRADES                                │
│  ──────────────────────────────                                 │
│  Trades:        45                                              │
│  Win Rate:      62%                                             │
│  Total Return:  +18.5%                                          │
│  Sharpe Ratio:  1.8                                             │
│  Avg Win:       +8.2%                                           │
│  Avg Loss:      -4.1%                                           │
│                                                                 │
│  👤 USER-INITIATED TRADES                                       │
│  ─────────────────────────                                      │
│  Trades:        23                                              │
│  Win Rate:      48%                                             │
│  Total Return:  +5.2%                                           │
│  Sharpe Ratio:  0.9                                             │
│  Avg Win:       +6.5%                                           │
│  Avg Loss:      -5.8%                                           │
│                                                                 │
│  ═══════════════════════════════════════════════════════════   │
│                                                                 │
│  🎯 RECOMMENDATION VALUE ADD:  +13.3%                           │
│     (Rec return - User return)                                  │
│                                                                 │
│  💡 Following recommendations outperformed by 13.3%             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### Database Schema for Attribution

```sql
CREATE TABLE trades (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL,
    ticker VARCHAR(10) NOT NULL,
    action VARCHAR(4) NOT NULL,  -- 'buy' or 'sell'
    quantity INT NOT NULL,
    price DECIMAL(10, 2) NOT NULL,
    executed_at TIMESTAMP NOT NULL,
    
    -- Attribution fields
    score_at_trade INT,
    signal_at_trade VARCHAR(4),  -- 'BUY', 'HOLD', 'SELL'
    attribution VARCHAR(20) NOT NULL,  -- 'recommendation', 'user_initiated'
    signal_date DATE,  -- When the signal was generated
    
    -- P&L tracking
    closed_at TIMESTAMP,
    close_price DECIMAL(10, 2),
    realized_pnl DECIMAL(10, 2),
    
    CONSTRAINT valid_attribution CHECK (attribution IN ('recommendation', 'user_initiated', 'mixed'))
);

-- Index for performance queries
CREATE INDEX idx_trades_attribution ON trades(user_id, attribution, executed_at);

-- View for easy reporting
CREATE VIEW performance_by_attribution AS
SELECT 
    attribution,
    COUNT(*) as trade_count,
    SUM(CASE WHEN realized_pnl > 0 THEN 1 ELSE 0 END)::FLOAT / COUNT(*) as win_rate,
    AVG(realized_pnl) as avg_pnl,
    SUM(realized_pnl) as total_pnl
FROM trades
WHERE closed_at IS NOT NULL
GROUP BY attribution;
```

#### Key Metrics to Track

| Metric | Recommendation | User-Initiated | Comparison |
|--------|----------------|----------------|------------|
| **Trade Count** | # of rec trades | # of user trades | Volume split |
| **Win Rate** | % winners (rec) | % winners (user) | Which is better? |
| **Total Return** | Return from rec | Return from user | Value add |
| **Sharpe Ratio** | Risk-adj (rec) | Risk-adj (user) | Quality of returns |
| **Avg Holding Period** | Days held (rec) | Days held (user) | Patience |
| **Adherence Rate** | — | — | % of BUY signals followed |

#### Adherence Tracking

Track how often users follow recommendations:

```python
def calculate_adherence(signals: list, trades: list) -> dict:
    """
    Calculate how often users follow system recommendations.
    """
    buy_signals = [s for s in signals if s.signal == 'BUY']
    sell_signals = [s for s in signals if s.signal == 'SELL']
    
    # How many BUY signals were followed?
    buy_followed = sum(
        1 for s in buy_signals 
        if any(t.ticker == s.ticker and t.action == 'buy' 
               and 0 <= (t.timestamp - s.date).days <= 7 
               for t in trades)
    )
    
    # How many SELL signals were followed?
    sell_followed = sum(
        1 for s in sell_signals
        if any(t.ticker == s.ticker and t.action == 'sell'
               and 0 <= (t.timestamp - s.date).days <= 7
               for t in trades)
    )
    
    return {
        'buy_adherence': buy_followed / len(buy_signals) if buy_signals else 0,
        'sell_adherence': sell_followed / len(sell_signals) if sell_signals else 0,
        'overall_adherence': (buy_followed + sell_followed) / (len(buy_signals) + len(sell_signals)),
    }
```

#### Why This Matters

| Question | How Attribution Answers It |
|----------|---------------------------|
| Does the system add value? | Compare rec return vs user return |
| Should users trust recommendations? | Show rec win rate vs user win rate |
| Is the model improving? | Track rec metrics over time |
| Where do users deviate? | Analyze user-initiated trades |
| What's the cost of ignoring signals? | Compare "followed" vs "ignored" outcomes |

---

### Portfolio Performance Metrics

| Metric | Target | Description |
|--------|--------|-------------|
| Total Return | > S&P500 | Absolute portfolio return |
| Alpha | > 5% annually | Excess return over benchmark |
| Sharpe Ratio | > 1.5 | Risk-adjusted return |
| Sortino Ratio | > 2.0 | Downside risk-adjusted return |
| Max Drawdown | < 20% | Largest peak-to-trough decline |
| Win Rate | > 55% | Percentage of profitable trades |
| Profit Factor | > 1.5 | Gross profit / Gross loss |
| Calmar Ratio | > 1.0 | Annual return / Max drawdown |

### Model Performance Metrics

| Metric | Application | Target |
|--------|-------------|--------|
| Accuracy | Sentiment classification | > 80% |
| Precision/Recall | Buy/Sell signals | > 60% precision |
| MAE | Earnings surprise prediction | < 5% |
| Information Coefficient | Factor ranking | > 0.05 |
| Hit Rate | Score quintile returns | Top quintile > bottom |

### Backtesting Framework

#### Recommended Packages

| Package | Type | Best For | GitHub Stars | Link |
|---------|------|----------|--------------|------|
| **VectorBT** | Vectorized | Fast iteration, ML integration | 4k+ | [github.com/polakowo/vectorbt](https://github.com/polakowo/vectorbt) |
| **Backtrader** | Event-driven | Production strategies, realism | 12k+ | [github.com/mementum/backtrader](https://github.com/mementum/backtrader) |
| **Zipline** | Event-driven | Quantopian-style, research | 17k+ | [github.com/quantopian/zipline](https://github.com/quantopian/zipline) |
| **QuantConnect Lean** | Event-driven | Live trading ready, multi-asset | 9k+ | [github.com/QuantConnect/Lean](https://github.com/QuantConnect/Lean) |
| **Backtesting.py** | Vectorized | Learning, quick prototypes | 5k+ | [github.com/kernc/backtesting.py](https://github.com/kernc/backtesting.py) |

#### Supporting Libraries

| Package | Purpose | Link |
|---------|---------|------|
| **PyFolio** | Performance & risk analysis | [github.com/quantopian/pyfolio](https://github.com/quantopian/pyfolio) |
| **Empyrical** | Financial risk metrics | [github.com/quantopian/empyrical](https://github.com/quantopian/empyrical) |
| **FinRL** | RL-based trading strategies | [github.com/AI4Finance-Foundation/FinRL](https://github.com/AI4Finance-Foundation/FinRL) |

#### Our Stack Choice: **VectorBT + PyFolio**

**Why VectorBT:**
- 1000x faster than event-driven (vectorized NumPy/Pandas)
- Native integration with ML workflows
- Built-in optimization and parameter sweeps
- Excellent visualization

**Why PyFolio:**
- Industry-standard tearsheet analysis
- Rolling Sharpe, drawdowns, sector exposure
- Originally from Quantopian (battle-tested)

> ⚠️ **Note on Quantopian:** Shut down in 2020, but open-sourced Zipline, PyFolio, and Empyrical. These remain actively maintained by the community.

#### Implementation

```python
import vectorbt as vbt
import pyfolio as pf
import pandas as pd

class Backtester:
    def __init__(self, start_date, end_date, initial_capital=100000):
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = initial_capital
        
    def run(self, signals: pd.DataFrame, prices: pd.DataFrame):
        """
        Run backtest using VectorBT
        
        Args:
            signals: DataFrame with buy/sell signals (1, -1, 0)
            prices: DataFrame with OHLCV data
        """
        # Create portfolio from signals
        portfolio = vbt.Portfolio.from_signals(
            prices['close'],
            entries=signals > 0,
            exits=signals < 0,
            init_cash=self.initial_capital,
            fees=0.001,  # 0.1% transaction cost
            slippage=0.001,  # 0.1% slippage
            freq='1D'
        )
        return portfolio
        
    def generate_report(self, portfolio):
        """Generate PyFolio tearsheet"""
        returns = portfolio.returns()
        
        # Full tearsheet
        pf.create_full_tear_sheet(returns)
        
        return {
            'total_return': portfolio.total_return(),
            'sharpe_ratio': portfolio.sharpe_ratio(),
            'max_drawdown': portfolio.max_drawdown(),
            'trade_log': portfolio.trades.records_readable,
            'equity_curve': portfolio.value()
        }
```

#### Walk-Forward Optimization

```python
def walk_forward_backtest(data, strategy, window=252, step=63):
    """
    Walk-forward optimization to prevent overfitting
    
    Args:
        window: Training window (252 = 1 year)
        step: Step size (63 = 1 quarter)
    """
    results = []
    for i in range(window, len(data), step):
        train = data[i-window:i]
        test = data[i:i+step]
        
        # Optimize on train
        best_params = strategy.optimize(train)
        
        # Evaluate on test (out-of-sample)
        oos_result = strategy.backtest(test, best_params)
        results.append(oos_result)
    
    return pd.concat(results)
```

---

### Backtesting Implementation (Simple First)

> **Philosophy:** Start with the simplest possible backtest. Validate the approach works before adding complexity.

#### Data Requirements

| Data Type | Source | Frequency | History Needed |
|-----------|--------|-----------|----------------|
| **Prices (OHLCV)** | Yahoo Finance (yfinance) | Daily | 5 years minimum |
| **Fundamentals** | Financial Modeling Prep | Quarterly | 3 years minimum |
| **Scores** | Our model | Weekly | Generate historically |
| **Benchmark** | SPY (S&P 500 ETF) | Daily | Same as prices |

```python
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

def fetch_backtest_data(tickers: list, years: int = 5) -> dict:
    """
    Fetch historical data for backtesting.
    
    Returns:
        {
            'prices': DataFrame (date × ticker),
            'returns': DataFrame (date × ticker),
            'benchmark': Series (SPY returns)
        }
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=years * 365)
    
    # Fetch prices for all tickers
    prices = yf.download(
        tickers + ['SPY'],
        start=start_date,
        end=end_date,
        progress=False
    )['Adj Close']
    
    # Calculate returns
    returns = prices.pct_change().dropna()
    
    return {
        'prices': prices[tickers],
        'returns': returns[tickers],
        'benchmark': returns['SPY']
    }
```

#### Train/Test Split (Keep It Simple)

```
┌─────────────────────────────────────────────────────────────────┐
│                     5 YEARS OF DATA                             │
├────────────────────────────────────┬────────────────────────────┤
│           TRAIN (80%)              │       TEST (20%)           │
│         Jan 2021 - Dec 2024        │    Jan 2025 - Present      │
│                                    │                            │
│  • Calculate scores historically   │  • Simulate live trading   │
│  • Tune weights (if needed)        │  • Measure real performance│
│  • Validate logic                  │  • NO peeking/tuning!      │
└────────────────────────────────────┴────────────────────────────┘
```

```python
def train_test_split_timeseries(data: pd.DataFrame, test_ratio: float = 0.2):
    """
    Split time series data chronologically (no shuffle!).
    
    Args:
        data: DataFrame with DatetimeIndex
        test_ratio: Fraction for test set (default 20%)
    
    Returns:
        train_data, test_data
    """
    split_idx = int(len(data) * (1 - test_ratio))
    
    train = data.iloc[:split_idx]
    test = data.iloc[split_idx:]
    
    print(f"Train: {train.index[0].date()} to {train.index[-1].date()} ({len(train)} days)")
    print(f"Test:  {test.index[0].date()} to {test.index[-1].date()} ({len(test)} days)")
    
    return train, test


# Example:
# Train: 2021-01-01 to 2024-12-31 (1008 days)
# Test:  2025-01-01 to 2026-02-02 (252 days)
```

#### V1 Backtest: Simplest Possible

**Strategy:** Buy top N stocks by score, hold for 1 week, rebalance.

```python
import numpy as np

def simple_backtest(
    scores: pd.DataFrame,      # Weekly scores (date × ticker)
    prices: pd.DataFrame,      # Daily prices (date × ticker)
    top_n: int = 10,           # How many stocks to hold
    rebalance_freq: str = 'W', # Weekly rebalance
    initial_capital: float = 100000
) -> dict:
    """
    Simplest backtest: equal-weight top N stocks, weekly rebalance.
    
    Args:
        scores: DataFrame with weekly scores (index=date, columns=tickers)
        prices: DataFrame with daily prices
        top_n: Number of stocks to hold
        rebalance_freq: Rebalance frequency ('W' = weekly)
    
    Returns:
        Dictionary with performance metrics
    """
    # Resample prices to weekly (last price of week)
    weekly_prices = prices.resample('W').last()
    weekly_returns = weekly_prices.pct_change()
    
    # Align scores with returns
    scores_aligned = scores.reindex(weekly_returns.index, method='ffill')
    
    portfolio_returns = []
    holdings_history = []
    
    for date in scores_aligned.index[1:]:  # Skip first (need previous prices)
        # Get scores for this week
        week_scores = scores_aligned.loc[date].dropna()
        
        if len(week_scores) < top_n:
            continue
        
        # Select top N stocks
        top_stocks = week_scores.nlargest(top_n).index.tolist()
        holdings_history.append({'date': date, 'holdings': top_stocks})
        
        # Equal weight
        weight = 1.0 / top_n
        
        # Calculate portfolio return for this week
        stock_returns = weekly_returns.loc[date, top_stocks]
        portfolio_return = (stock_returns * weight).sum()
        portfolio_returns.append({'date': date, 'return': portfolio_return})
    
    # Convert to Series
    returns_series = pd.DataFrame(portfolio_returns).set_index('date')['return']
    
    # Calculate metrics
    total_return = (1 + returns_series).prod() - 1
    annual_return = (1 + total_return) ** (52 / len(returns_series)) - 1
    volatility = returns_series.std() * np.sqrt(52)
    sharpe = annual_return / volatility if volatility > 0 else 0
    max_drawdown = calculate_max_drawdown(returns_series)
    
    return {
        'total_return': total_return,
        'annual_return': annual_return,
        'volatility': volatility,
        'sharpe_ratio': sharpe,
        'max_drawdown': max_drawdown,
        'n_weeks': len(returns_series),
        'returns': returns_series,
        'holdings': holdings_history
    }


def calculate_max_drawdown(returns: pd.Series) -> float:
    """Calculate maximum drawdown from returns series."""
    cumulative = (1 + returns).cumprod()
    running_max = cumulative.cummax()
    drawdown = (cumulative - running_max) / running_max
    return drawdown.min()
```

#### Generate Historical Scores

To backtest, we need scores for the past — calculate them historically:

```python
def generate_historical_scores(
    fundamentals: pd.DataFrame,  # Quarterly fundamentals (point-in-time!)
    prices: pd.DataFrame,        # Daily prices
    start_date: str,
    end_date: str
) -> pd.DataFrame:
    """
    Generate weekly scores historically.
    
    IMPORTANT: Use point-in-time data only!
    - Don't use Q4 earnings to calculate Q3 scores
    - Only use data that was available at that time
    
    Returns:
        DataFrame with weekly scores (date × ticker)
    """
    scores_list = []
    
    # Generate for each Sunday
    for date in pd.date_range(start_date, end_date, freq='W-SUN'):
        # Get data available as of this date (point-in-time)
        available_fundamentals = fundamentals[fundamentals['report_date'] <= date]
        available_prices = prices[prices.index <= date]
        
        # Calculate score using only available data
        week_scores = calculate_scores(
            fundamentals=available_fundamentals,
            prices=available_prices,
            as_of_date=date
        )
        
        scores_list.append(week_scores)
    
    return pd.concat(scores_list)
```

#### Avoid Look-Ahead Bias!

```
❌ WRONG (Look-ahead bias):
   - Using future earnings to calculate past scores
   - Using Monday's price to trade on Sunday
   - Using full dataset statistics (mean/std) for normalization

✅ CORRECT (Point-in-time):
   - Only use data available at decision time
   - Trade at next day's open, not current close
   - Calculate rolling statistics (expanding window)
```

```python
# ❌ WRONG: Uses future data for normalization
def wrong_normalize(scores, all_data):
    mean = all_data.mean()  # Uses future!
    std = all_data.std()    # Uses future!
    return (scores - mean) / std

# ✅ CORRECT: Uses only past data
def correct_normalize(scores, historical_data):
    mean = historical_data.mean()  # Only past
    std = historical_data.std()    # Only past
    return (scores - mean) / std
```

#### Benchmark Comparison

Always compare against buy-and-hold SPY:

```python
def compare_to_benchmark(strategy_returns: pd.Series, benchmark_returns: pd.Series):
    """Compare strategy to SPY benchmark."""
    
    # Align dates
    common_dates = strategy_returns.index.intersection(benchmark_returns.index)
    strat = strategy_returns.loc[common_dates]
    bench = benchmark_returns.loc[common_dates]
    
    # Calculate metrics for both
    strat_total = (1 + strat).prod() - 1
    bench_total = (1 + bench).prod() - 1
    
    strat_sharpe = strat.mean() / strat.std() * np.sqrt(52)
    bench_sharpe = bench.mean() / bench.std() * np.sqrt(52)
    
    # Alpha (excess return)
    alpha = strat_total - bench_total
    
    print(f"{'Metric':<20} {'Strategy':>12} {'SPY':>12} {'Diff':>12}")
    print("-" * 56)
    print(f"{'Total Return':<20} {strat_total:>12.2%} {bench_total:>12.2%} {alpha:>+12.2%}")
    print(f"{'Sharpe Ratio':<20} {strat_sharpe:>12.2f} {bench_sharpe:>12.2f} {strat_sharpe - bench_sharpe:>+12.2f}")
    
    return {
        'strategy_return': strat_total,
        'benchmark_return': bench_total,
        'alpha': alpha,
        'strategy_sharpe': strat_sharpe,
        'benchmark_sharpe': bench_sharpe
    }
```

#### Full Backtest Script (Copy-Paste Ready)

```python
"""
Simple Backtest Script for TradingApp
Run this to validate the scoring model.
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime

# 1. CONFIG
TICKERS = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 
           'JPM', 'JNJ', 'V', 'UNH', 'HD', 'PG', 'MA', 'DIS']  # Sample
TOP_N = 5
START_DATE = '2021-01-01'
END_DATE = '2025-12-31'
INITIAL_CAPITAL = 100000

# 2. FETCH DATA
print("Fetching price data...")
prices = yf.download(TICKERS + ['SPY'], start=START_DATE, end=END_DATE)['Adj Close']

# 3. GENERATE SCORES (placeholder - use your actual scoring function)
print("Generating historical scores...")
# For demo: random scores (replace with real scoring!)
np.random.seed(42)
weekly_dates = pd.date_range(START_DATE, END_DATE, freq='W-SUN')
scores = pd.DataFrame(
    np.random.randint(0, 100, size=(len(weekly_dates), len(TICKERS))),
    index=weekly_dates,
    columns=TICKERS
)

# 4. TRAIN/TEST SPLIT
split_date = '2025-01-01'
train_scores = scores[scores.index < split_date]
test_scores = scores[scores.index >= split_date]
print(f"Train: {len(train_scores)} weeks, Test: {len(test_scores)} weeks")

# 5. RUN BACKTEST (on test set only!)
print("Running backtest on test set...")
results = simple_backtest(test_scores, prices, top_n=TOP_N)

# 6. COMPARE TO BENCHMARK
benchmark = prices['SPY'].resample('W').last().pct_change().dropna()
benchmark = benchmark[benchmark.index >= split_date]
comparison = compare_to_benchmark(results['returns'], benchmark)

# 7. PRINT RESULTS
print("\n" + "="*60)
print("BACKTEST RESULTS (Test Period)")
print("="*60)
print(f"Period:          {test_scores.index[0].date()} to {test_scores.index[-1].date()}")
print(f"Total Return:    {results['total_return']:.2%}")
print(f"Annual Return:   {results['annual_return']:.2%}")
print(f"Sharpe Ratio:    {results['sharpe_ratio']:.2f}")
print(f"Max Drawdown:    {results['max_drawdown']:.2%}")
print(f"Alpha vs SPY:    {comparison['alpha']:+.2%}")
print("="*60)
```

#### When to Add Complexity

| Phase | Backtest Complexity |
|-------|---------------------|
| **MVP (Phase 5)** | Simple: Top N, equal weight, weekly |
| **Phase 6** | Add: Transaction costs, slippage |
| **Phase 6** | Add: Walk-forward validation |
| **Phase 7+** | Add: Risk parity weights, sector constraints |
| **Phase 7+** | Add: Multiple parameter sweeps |

**Rule:** Only add complexity after simple backtest shows promise.

---

## System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         iOS APPLICATION                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────┐ │
│  │  Portfolio  │  │   Scores    │  │   Trading   │  │  Settings  │ │
│  │    View     │  │    View     │  │    View     │  │    View    │ │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └─────┬──────┘ │
│         └─────────────────┼─────────────────┘              │        │
│                           ▼                                │        │
│  ┌────────────────────────────────────────────────────────────────┐│
│  │                    API CLIENT LAYER                            ││
│  │   (Authentication, Request/Response, Caching, Offline Mode)   ││
│  └────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────┬───────────────────────────────┘
                                      │ HTTPS
                                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        BACKEND SERVICES                             │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────────────┐│
│  │   API Gateway  │  │  Auth Service  │  │   Rate Limiter         ││
│  │   (FastAPI)    │  │  (JWT/OAuth2)  │  │                        ││
│  └───────┬────────┘  └────────────────┘  └────────────────────────┘│
│          ▼                                                          │
│  ┌────────────────────────────────────────────────────────────────┐│
│  │                    MICROSERVICES                               ││
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐││
│  │  │ Scoring  │  │  Data    │  │  Trading │  │   Notification   │││
│  │  │ Service  │  │  Service │  │  Service │  │   Service        │││
│  │  └────┬─────┘  └────┬─────┘  └────┬─────┘  └──────────────────┘││
│  └───────┼─────────────┼─────────────┼────────────────────────────┘│
│          ▼             ▼             ▼                              │
│  ┌────────────────────────────────────────────────────────────────┐│
│  │                    DATA LAYER                                  ││
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐││
│  │  │PostgreSQL│  │  Redis   │  │ TimeSeries│  │    S3/Blob      │││
│  │  │(Metadata)│  │ (Cache)  │  │   (Prices)│  │   (Models)      │││
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────────────┘││
│  └────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     EXTERNAL SERVICES                               │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────────┐│
│  │ Interactive  │  │  Financial   │  │  News APIs                 ││
│  │ Brokers API  │  │  Data APIs   │  │  (NewsAPI, Benzinga)       ││
│  └──────────────┘  └──────────────┘  └────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
```

### Technology Stack

| Layer | Technology |
|-------|------------|
| iOS App | Swift, SwiftUI |
| Backend API | Python, FastAPI |
| Database | PostgreSQL, Redis, TimescaleDB |
| ML Models | PyTorch, Hugging Face Transformers |
| Message Queue | Redis Pub/Sub or RabbitMQ |
| Cloud | AWS or GCP |
| CI/CD | GitHub Actions |
| Monitoring | Prometheus, Grafana |

---

### Development Environment — Dockerized & Separated

> 🎯 **Principle:** Backend and frontend are completely separate concerns. Different repos (or folders), different containers, different test suites, different deployment pipelines.

#### Project Structure

```
tradingapp/
├── backend/                    # Python backend (FastAPI)
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── requirements.txt
│   ├── pyproject.toml
│   ├── src/
│   │   ├── api/               # FastAPI routes
│   │   ├── services/          # Business logic
│   │   ├── models/            # ML models & scoring
│   │   ├── data/              # Data fetching & processing
│   │   └── db/                # Database models & migrations
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   └── e2e/
│   └── scripts/               # Data pipelines, cron jobs
│
├── ios/                        # Swift/SwiftUI app
│   ├── TradingApp/
│   │   ├── Views/
│   │   ├── ViewModels/
│   │   ├── Models/
│   │   ├── Services/
│   │   └── Resources/
│   ├── TradingAppTests/
│   ├── TradingAppUITests/
│   └── TradingApp.xcodeproj
│
├── shared/                     # Shared contracts
│   ├── api-spec/              # OpenAPI/Swagger specs
│   └── schemas/               # JSON schemas for validation
│
└── docker-compose.yml          # Full stack orchestration
```

#### Docker Configuration

**Backend (`backend/Dockerfile`):**
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY scripts/ ./scripts/

EXPOSE 8000
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Docker Compose (`docker-compose.yml`):**
```yaml
version: '3.8'

services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/tradingapp
      - REDIS_URL=redis://redis:6379
    depends_on:
      - db
      - redis
    volumes:
      - ./backend/src:/app/src  # Hot reload in dev

  db:
    image: postgres:15
    environment:
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
      POSTGRES_DB: tradingapp
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  # Optional: TimescaleDB for time-series data
  timescale:
    image: timescale/timescaledb:latest-pg15
    environment:
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
      POSTGRES_DB: timeseries
    ports:
      - "5433:5432"

volumes:
  postgres_data:
```

#### Separate Test Suites

| Layer | Test Type | Tool | Run Command |
|-------|-----------|------|-------------|
| **Backend** | Unit | pytest | `cd backend && pytest tests/unit` |
| **Backend** | Integration | pytest + testcontainers | `cd backend && pytest tests/integration` |
| **Backend** | API/E2E | pytest + httpx | `cd backend && pytest tests/e2e` |
| **iOS** | Unit | XCTest | `xcodebuild test -scheme TradingApp` |
| **iOS** | UI | XCUITest | `xcodebuild test -scheme TradingAppUITests` |
| **Contract** | API spec validation | Spectral/Dredd | `npm run validate-api` |

#### CI/CD Pipeline (GitHub Actions)

```yaml
# .github/workflows/backend.yml
name: Backend CI

on:
  push:
    paths:
      - 'backend/**'

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build and test
        run: |
          cd backend
          docker-compose -f docker-compose.test.yml up --build --abort-on-container-exit

  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Lint
        run: |
          cd backend
          pip install ruff
          ruff check src/
```

```yaml
# .github/workflows/ios.yml
name: iOS CI

on:
  push:
    paths:
      - 'ios/**'

jobs:
  test:
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build and test
        run: |
          cd ios
          xcodebuild test -scheme TradingApp -destination 'platform=iOS Simulator,name=iPhone 15'
```

#### Development Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│  LOCAL DEVELOPMENT                                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Terminal 1 (Backend):                                          │
│  $ cd backend && docker-compose up                              │
│  → API at http://localhost:8000                                 │
│  → Swagger docs at http://localhost:8000/docs                   │
│                                                                 │
│  Terminal 2 (iOS):                                              │
│  $ open ios/TradingApp.xcodeproj                                │
│  → Run on simulator, pointing to localhost:8000                 │
│                                                                 │
│  Terminal 3 (Tests):                                            │
│  $ cd backend && pytest --watch                                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### Environment Variables

| Variable | Dev | Staging | Prod |
|----------|-----|---------|------|
| `API_URL` | `localhost:8000` | `api.staging.tradingapp.com` | `api.tradingapp.com` |
| `IBKR_MODE` | `paper` | `paper` | `live` |
| `LOG_LEVEL` | `DEBUG` | `INFO` | `WARNING` |
| `REDIS_URL` | `redis://localhost:6379` | (managed) | (managed) |

#### Git Branching Strategy

> 🎯 **Rule:** One feature = one branch. Meaningful names. Merge to master when complete.

**Branch Naming Convention:**
```
<type>/<ticket>-<short-description>

Types:
  feat/     New feature
  fix/      Bug fix
  refactor/ Code refactoring
  test/     Adding tests
  docs/     Documentation
  chore/    Maintenance, dependencies
```

**Examples:**
```
feat/REC-21-scoring-pipeline
feat/REC-22-portfolio-view
fix/REC-45-price-rounding-error
refactor/REC-50-sentiment-module
test/REC-21-scoring-unit-tests
docs/api-swagger-update
```

**Workflow:**
```
┌─────────────────────────────────────────────────────────────────┐
│  GIT WORKFLOW                                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. Create branch from master:                                  │
│     $ git checkout master && git pull                           │
│     $ git checkout -b feat/REC-21-scoring-pipeline              │
│                                                                 │
│  2. Work on feature (commit often):                             │
│     $ git add . && git commit -m "feat(scoring): add base model"│
│                                                                 │
│  3. Push and create PR:                                         │
│     $ git push -u origin feat/REC-21-scoring-pipeline           │
│                                                                 │
│  4. After review, merge to master:                              │
│     $ git checkout master && git pull                           │
│     $ git merge feat/REC-21-scoring-pipeline                    │
│     $ git push                                                  │
│                                                                 │
│  5. Delete branch:                                              │
│     $ git branch -d feat/REC-21-scoring-pipeline                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Commit Message Format:**
```
<type>(<scope>): <short description>

Types: feat, fix, refactor, test, docs, chore
Scope: scoring, api, ios, data, sentiment, etc.

Examples:
  feat(scoring): implement composite score calculation
  fix(api): handle missing earnings data gracefully
  test(scoring): add unit tests for sentiment scoring
  docs(readme): update setup instructions
```

**Branch Protection (master):**
- Require PR before merge
- Require passing CI checks
- Require at least 1 approval (if team > 1)
- No direct pushes to master

#### Linear as Source of Truth

> 🎯 **Rule:** Linear is the project's memory. Use it before, during, and after every feature.

**Before Starting a Feature:**
```
┌─────────────────────────────────────────────────────────────────┐
│  PRE-WORK CHECKLIST                                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  □ Read the ticket description thoroughly                       │
│  □ Check related/linked tickets for context                     │
│  □ Review comments on previous features in same area            │
│  □ Look at completed tickets for patterns & decisions           │
│  □ Note any blockers or dependencies                            │
│                                                                 │
│  Ask: "What did we learn last time that applies here?"          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**During Feature Development:**
```
┌─────────────────────────────────────────────────────────────────┐
│  DOCUMENTATION AS YOU GO                                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Update Linear ticket with:                                     │
│                                                                 │
│  • Progress notes ("Started API integration", "Tests passing")  │
│  • Decisions made ("Using Redis for caching because...")        │
│  • Blockers encountered ("Waiting on API key")                  │
│  • Technical notes future-you will thank you for                │
│  • Links to relevant PRs, docs, or resources                    │
│                                                                 │
│  Frequency: At minimum, update at start and end of each         │
│  work session. More is better.                                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**After Feature Completion:**
```
┌─────────────────────────────────────────────────────────────────┐
│  WRAP-UP                                                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  • Summary of what was built                                    │
│  • Any gotchas or edge cases discovered                         │
│  • Technical debt noted (if any)                                │
│  • Link to merged PR                                            │
│  • Move ticket to Done                                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Why This Matters:**
- Context switching is expensive — Linear preserves your train of thought
- Future features build on past decisions — those decisions must be findable
- Debugging is easier when you know what changed and why
- Onboarding (yourself after a break, or others) becomes trivial

---

## iOS App Modules

### 1. Dashboard Module
- Portfolio summary (value, P&L, daily change)
- Top movers in portfolio
- Market overview (S&P500, VIX)
- Notifications feed

### 2. Scores Module
- Stock ranking table (sortable by score, sector, change)
- Individual stock cards with score breakdown
- Score history charts
- Filter by sector, score range, buy/sell signal

### 3. Stock Detail Module
- Score breakdown (fundamental, sentiment, macro, technical)
- Price chart with technical indicators
- Recent news with sentiment tags
- Analyst ratings
- Financial highlights

### 4. Trading Module
- Order entry (market, limit, stop)
- Position management
- Order history
- Paper/Live toggle

### 5. Portfolio Module
- Holdings list with P&L
- Allocation pie chart
- Performance chart vs benchmark
- Risk metrics (beta, Sharpe)

### 6. Settings Module
- Account linking (IBKR)
- Notification preferences
- Risk preferences
- Paper/Live mode toggle
- Theme settings

### UI Components
- Reusable stock cell
- Score gauge (circular progress)
- Mini price chart
- Sentiment indicator (🟢🟡🔴)
- Sector badge

---

## UX/UI Design

> 📁 **Design Resources:** See [design/inspiration/](design/inspiration/) for curated references and screenshot collection links.

### Target User

**The Busy Builder** — Our ideal user is a high-tech professional, 30-40 years old, navigating the demands of a hectic career while wanting their wealth to grow intelligently in the background. They're sophisticated enough to understand markets but too busy (and too smart) to day-trade. They appreciate elegant design, data-driven decisions, and tools that respect their time. They don't want to babysit their portfolio — they want to set intelligent parameters and let their money work for them while they focus on building the next big thing.

---

### Daily Inspiration

Each time the user opens the app, display a rotating motivational quote from luminaries in science, art, strategy, and finance. Short, punchy, relevant to investing mindset.

**Example Quotes:**
- *"In investing, what is comfortable is rarely profitable."* — Robert Arnott
- *"The stock market is a device for transferring money from the impatient to the patient."* — Warren Buffett  
- *"You have to be odd to be number one."* — Dr. Seuss
- *"The best move is the one you want to make."* — Bobby Fischer
- *"Simplicity is the ultimate sophistication."* — Leonardo da Vinci
- *"Time is the friend of the wonderful company, the enemy of the mediocre."* — Warren Buffett
- *"Risk comes from not knowing what you're doing."* — Warren Buffett
- *"I'd rather be approximately right than precisely wrong."* — John Maynard Keynes
- *"The four most dangerous words in investing: 'This time it's different.'"* — Sir John Templeton
- *"In the middle of difficulty lies opportunity."* — Albert Einstein

**Implementation:** Store 50+ quotes in the app bundle; randomly select on launch. Subtle typography, positioned below the main header. Tappable to see attribution/source.

---

### Design Philosophy

**"Institutional Trust for the Busy Builder"** — Every pixel serves the time-constrained professional. The app should feel like a Bloomberg terminal distilled for mobile — sophisticated enough to earn respect, efficient enough to use in 30 seconds between meetings. No learning curve, no clutter, no wasted taps. Our user recognizes quality instantly; the design must signal "this was built by someone who gets it."

> 🎯 **Design North Star:** If a feature takes more than 3 taps or 10 seconds to understand, redesign it.

### Design Principles

*Every principle flows from serving the Busy Builder.*

1. **Respect Their Time** — Glanceable dashboards, instant insights. They have 30 seconds, not 30 minutes. Surface what matters, hide the noise.

2. **Accuracy First** — Numbers are sacred. Right-aligned, monospaced, properly formatted. These users will notice if something's off by a penny.

3. **Sophisticated Simplicity** — High information density without cognitive overload. They're smart — don't dumb it down, but do organize it brilliantly.

4. **Zero Learning Curve** — Intuitive from first launch. They'll delete the app before watching a tutorial.

5. **Dark Mode** — Non-negotiable. Reduces eye strain, signals professionalism, looks great in dim conference rooms.

6. **Confidence-Building** — Every interaction should feel solid, responsive, trustworthy. Subtle haptics, instant feedback, no jank.

7. **Let Them Forget** — The ultimate goal: set up once, check weekly. Push insights to them; don't make them hunt.

> 📋 **Validation Checkpoint:** For every design decision, ask: *"Does this respect the Busy Builder's time and intelligence?"* If not, cut it.

### Design References

*What our user already knows and respects:*

| Reference | What to Learn |
|-----------|---------------|
| **Interactive Brokers TWS** | Data tables, order entry, professional charts |
| **Bloomberg Terminal** | Information density, color coding, typography |
| **Fidelity Active Trader Pro** | Clean layouts, watchlists, portfolio views |
| **Charles Schwab** | Institutional trust, clean forms |
| **TD Ameritrade thinkorswim** | Chart styling, technical indicators |
| **Apple Stocks** | Native iOS patterns, clean dark mode |

---

### Color Palette — "Institutional Dark"

#### Core Colors
| Role | Color | Hex | Usage |
|------|-------|-----|-------|
| **Background** | True Black | `#000000` | Main background |
| **Surface** | Dark Gray | `#0D0D0D` | Cards, elevated surfaces |
| **Surface 2** | Charcoal | `#161616` | Modals, input fields |
| **Border** | Subtle | `#222222` | Dividers, table borders |
| **Border Active** | Medium | `#333333` | Focus states |

#### Semantic Colors (Industry Standard)
| Role | Color | Hex | Usage |
|------|-------|-----|-------|
| **Gain/Positive** | Standard Green | `#00C853` | Price up, profits, buy |
| **Loss/Negative** | Standard Red | `#FF1744` | Price down, losses, sell |
| **Neutral** | Gray | `#9E9E9E` | Unchanged, hold |
| **Primary Action** | Blue | `#2196F3` | Buttons, links, CTAs |
| **Warning** | Amber | `#FFC107` | Alerts, caution |
| **Info** | Light Blue | `#03A9F4` | Informational |

#### Text Colors
| Role | Hex | Usage |
|------|-----|-------|
| **Text Primary** | `#FFFFFF` | Headlines, prices, key data |
| **Text Secondary** | `#B0B0B0` | Labels, descriptions |
| **Text Muted** | `#707070` | Timestamps, hints, footnotes |
| **Text Disabled** | `#404040` | Disabled states |

#### Chart Colors (Professional)
| Element | Hex | Notes |
|---------|-----|-------|
| Price Line (Up) | `#00C853` | Green |
| Price Line (Down) | `#FF1744` | Red |
| Candle Body (Up) | `#00C853` | Filled green |
| Candle Body (Down) | `#FF1744` | Filled red |
| Volume Bars | `#2196F3` | Blue, 50% opacity |
| MA 20 | `#FFC107` | Amber |
| MA 50 | `#9C27B0` | Purple |
| MA 200 | `#03A9F4` | Light blue |
| Grid Lines | `#1A1A1A` | Subtle |
| Axis Labels | `#707070` | Muted |

---

### Typography — Professional & Readable

#### Font Stack
| Purpose | Font | Fallback |
|---------|------|----------|
| **UI Text** | SF Pro Text | -apple-system, Helvetica |
| **Numbers/Data** | SF Mono | Menlo, Monaco, monospace |
| **Headlines** | SF Pro Display | -apple-system |

#### Type Scale
| Style | Font | Size | Weight | Line Height | Usage |
|-------|------|------|--------|-------------|-------|
| **Large Value** | SF Mono | 32pt | Semibold | 1.1 | Portfolio total |
| **Price** | SF Mono | 18pt | Medium | 1.2 | Stock prices |
| **Table Header** | SF Pro Text | 12pt | Semibold | 1.3 | Column headers |
| **Table Data** | SF Mono | 14pt | Regular | 1.4 | Table cells |
| **Title** | SF Pro Display | 20pt | Semibold | 1.2 | Screen titles |
| **Section** | SF Pro Text | 14pt | Semibold | 1.3 | Section headers |
| **Body** | SF Pro Text | 15pt | Regular | 1.5 | Descriptions |
| **Caption** | SF Pro Text | 12pt | Regular | 1.4 | Timestamps, notes |
| **Label** | SF Pro Text | 11pt | Medium | 1.3 | Field labels |

#### Number Formatting
```
Prices:      $185.42      (2 decimals, right-aligned)
Large:       $1,234,567   (comma separators)
Percent:     +2.34%       (sign always shown)
             -1.52%
Volume:      1.2M         (abbreviated with suffix)
             845.3K
Shares:      100          (no decimals)
Dates:       Feb 2, 2026  (readable format)
Times:       09:30 ET     (with timezone)
```

---

### Data Tables — Bloomberg/IBKR Style

#### Watchlist Table
```
┌──────────────────────────────────────────────────────────────────┐
│ SYMBOL │    LAST │   CHG │    CHG% │    BID │    ASK │    VOL   │
├──────────────────────────────────────────────────────────────────┤
│ AAPL   │  185.42 │ +4.21 │  +2.33% │ 185.40 │ 185.44 │   45.2M  │
│ MSFT   │  378.91 │ +6.72 │  +1.81% │ 378.88 │ 378.95 │   22.1M  │
│ GOOGL  │  141.80 │ -0.92 │  -0.64% │ 141.78 │ 141.82 │   18.7M  │
│ NVDA   │  682.35 │ -8.41 │  -1.22% │ 682.30 │ 682.40 │   38.9M  │
│ AMZN   │  178.25 │ +2.15 │  +1.22% │ 178.22 │ 178.28 │   31.4M  │
└──────────────────────────────────────────────────────────────────┘

Design specs:
- Header: #707070, 12pt, uppercase, left-aligned (except numbers)
- Numbers: SF Mono, 14pt, right-aligned
- Positive: #00C853
- Negative: #FF1744
- Row hover: #161616
- Alternating rows: #0D0D0D / #000000
- Border: #222222
```

#### AI Score Table
```
┌──────────────────────────────────────────────────────────────────┐
│ SYMBOL │ SCORE │ SIGNAL │ FUND │ SENT │ MACRO │ TECH │ UPDATED  │
├──────────────────────────────────────────────────────────────────┤
│ AAPL   │    85 │ BUY    │   82 │   90 │    75 │   80 │ 2h ago   │
│ MSFT   │    82 │ BUY    │   78 │   85 │    80 │   82 │ 2h ago   │
│ GOOGL  │    61 │ HOLD   │   65 │   58 │    62 │   60 │ 2h ago   │
│ NVDA   │    78 │ BUY    │   72 │   82 │    78 │   80 │ 2h ago   │
│ AMZN   │    45 │ SELL   │   42 │   38 │    50 │   52 │ 2h ago   │
└──────────────────────────────────────────────────────────────────┘

Signal colors:
- BUY: #00C853
- HOLD: #9E9E9E
- SELL: #FF1744

Score colors (gradient based on value):
- 80-100: #00C853
- 60-79:  #FFC107
- 40-59:  #9E9E9E
- 0-39:   #FF1744
```

#### Portfolio Holdings
```
┌────────────────────────────────────────────────────────────────────────────┐
│ SYMBOL │   QTY │ AVG COST │    LAST │  MKT VAL │   P&L $ │  P&L % │ % PORT │
├────────────────────────────────────────────────────────────────────────────┤
│ AAPL   │   100 │   172.50 │  185.42 │ $18,542  │ +$1,292 │ +7.49% │  14.9% │
│ MSFT   │    50 │   355.00 │  378.91 │ $18,946  │ +$1,196 │ +6.73% │  15.2% │
│ NVDA   │    30 │   650.00 │  682.35 │ $20,471  │   +$971 │ +4.98% │  16.4% │
├────────────────────────────────────────────────────────────────────────────┤
│ TOTAL  │       │          │         │$124,532  │ +$8,421 │ +7.25% │ 100.0% │
└────────────────────────────────────────────────────────────────────────────┘
```

---

### Charts — Professional Trading Style

#### Price Chart (Candlestick)
```
┌─────────────────────────────────────────────────────────────────┐
│  AAPL · 1D · Feb 2, 2026                           ≡  ⚙  ↗    │
├─────────────────────────────────────────────────────────────────┤
│ 190 ┤                                                          │
│     │                           ┃                              │
│ 188 ┤                     ╻     ┃     ╻                        │
│     │               ┃     ┃     ┃     ┃                        │
│ 186 ┤         ╻     ┃     ┃     ┃     ┃     ╻                  │
│     │   ╻     ┃     ┃     ┃     ┃     ┃     ┃                  │
│ 184 ┤   ┃     ┃     ┃                 ┃     ┃                  │
│     │   ┃     ┃                             ┃                  │
│ 182 ┤   ┃                                                      │
│     │                                                          │
│ 180 ┼────────────────────────────────────────────────────────  │
│      9:30    10:30    11:30    12:30    13:30    14:30   15:30 │
├─────────────────────────────────────────────────────────────────┤
│ Vol │ ▃ █ ▅ ▂ ▇ ▄ █ ▃ ▅ ▂ ▄ ▆ ▃ ▅ █ ▄ ▂ ▅ ▃ ▆ ▄ ▂ █ ▅ ▃ ▄ ▆ │
└─────────────────────────────────────────────────────────────────┘
│  1D    5D    1M    3M    6M    1Y    5Y    MAX                 │
└─────────────────────────────────────────────────────────────────┘

Chart specs:
- Background: #000000
- Grid: #1A1A1A (subtle)
- Axis labels: #707070, SF Mono 11pt
- Green candles: #00C853 fill
- Red candles: #FF1744 fill
- Volume: #2196F3 at 50% opacity
```

#### Score Gauge (Clean/Professional)
```
        ┌─────────────────┐
        │                 │
        │       85        │   ← Large SF Mono number
        │     ───────     │   ← Thin progress bar
        │                 │
        │      BUY        │   ← Signal text in green
        │                 │
        └─────────────────┘

Progress bar: 
- Track: #222222
- Fill: Gradient from red (0) → amber (50) → green (100)
- No circular gauges — horizontal bar is cleaner
```

---

### Key Screens

> 📱 **Screen Design Principle:** Every screen answers one question the Busy Builder has. Home = "How's my portfolio?" Scores = "What should I buy/sell?" Trade = "Execute." No screen makes them think; every screen makes them act.

#### Home Dashboard
```
┌────────────────────────────────────────────────────────────────┐
│                                                      9:41 AM   │
│  Portfolio                                                     │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  Total Value                                                   │
│  $124,532.18                                                   │
│  +$1,234.56 (+1.00%) today                                     │
│                                                                │
│  ───────────────────────────────────────────────────────────   │
│                                                                │
│  MARKETS                                                       │
│  ┌────────────┬────────────┬────────────┬────────────┐        │
│  │ S&P 500    │ NASDAQ     │ DOW        │ VIX        │        │
│  │ 4,892.45   │ 15,234.12  │ 38,456.78  │ 15.23      │        │
│  │ +0.52%     │ +0.78%     │ +0.31%     │ -2.15%     │        │
│  └────────────┴────────────┴────────────┴────────────┘        │
│                                                                │
│  ───────────────────────────────────────────────────────────   │
│                                                                │
│  TOP AI PICKS                                          See All │
│  ┌────────────────────────────────────────────────────────┐   │
│  │ AAPL │  85 │ BUY  │  185.42 │ +2.33% │ Technology     │   │
│  │ MSFT │  82 │ BUY  │  378.91 │ +1.81% │ Technology     │   │
│  │ NVDA │  78 │ BUY  │  682.35 │ -1.22% │ Technology     │   │
│  │ JPM  │  76 │ BUY  │  178.45 │ +0.92% │ Financials     │   │
│  └────────────────────────────────────────────────────────┘   │
│                                                                │
│  ───────────────────────────────────────────────────────────   │
│                                                                │
│  ALERTS                                                        │
│  ┌────────────────────────────────────────────────────────┐   │
│  │ ● AMZN earnings beat estimates by 8%          2h ago   │   │
│  │ ● Fed rate decision scheduled for tomorrow    5h ago   │   │
│  │ ● NVDA score dropped from 85 to 78           1d ago   │   │
│  └────────────────────────────────────────────────────────┘   │
│                                                                │
├────────────────────────────────────────────────────────────────┤
│    Home      Scores      Trade      Portfolio    Settings     │
└────────────────────────────────────────────────────────────────┘
```

#### Stock Detail Screen
```
┌────────────────────────────────────────────────────────────────┐
│  ←  AAPL                                             ★    ⋮   │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  Apple Inc.                                                    │
│  Technology · NASDAQ · $2.89T                                  │
│                                                                │
│  $185.42                                            +$4.21     │
│                                                     +2.33%     │
│                                                                │
│  ┌────────────────────────────────────────────────────────┐   │
│  │                    [PRICE CHART]                       │   │
│  │         Candlestick chart with volume                  │   │
│  │              (see chart spec above)                    │   │
│  └────────────────────────────────────────────────────────┘   │
│   1D     5D     1M     3M     6M     1Y     ALL              │
│                                                                │
│  ───────────────────────────────────────────────────────────   │
│                                                                │
│  AI SCORE                                                      │
│  ┌────────────────────────────────────────────────────────┐   │
│  │  85 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━░░░░░░░░░  │   │
│  │  Signal: BUY                    Updated: 2 hours ago   │   │
│  └────────────────────────────────────────────────────────┘   │
│                                                                │
│  SCORE BREAKDOWN                                               │
│  ┌─────────────────────────────────────────────┐              │
│  │ Fundamental    82  ━━━━━━━━━━━━━━━━━━░░░░░ │              │
│  │ Sentiment      90  ━━━━━━━━━━━━━━━━━━━━━░░ │              │
│  │ Macro          75  ━━━━━━━━━━━━━━━━░░░░░░░ │              │
│  │ Technical      80  ━━━━━━━━━━━━━━━━━━░░░░░ │              │
│  └─────────────────────────────────────────────┘              │
│                                                                │
│  ───────────────────────────────────────────────────────────   │
│                                                                │
│  KEY STATS                                                     │
│  ┌───────────────────┬───────────────────┐                    │
│  │ Open      181.50  │ P/E        28.45  │                    │
│  │ High      186.20  │ EPS         6.52  │                    │
│  │ Low       180.85  │ Div Yield   0.52% │                    │
│  │ Volume    45.2M   │ 52W High   198.23 │                    │
│  │ Avg Vol   52.1M   │ 52W Low    142.18 │                    │
│  └───────────────────┴───────────────────┘                    │
│                                                                │
│  ┌────────────────────────────────────────────────────────┐   │
│  │                      TRADE                             │   │
│  └────────────────────────────────────────────────────────┘   │
│                                                                │
├────────────────────────────────────────────────────────────────┤
│    Home      Scores      Trade      Portfolio    Settings     │
└────────────────────────────────────────────────────────────────┘
```

#### Order Entry (Clean Form)
```
┌────────────────────────────────────────────────────────────────┐
│  Order Entry                                              ✕    │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  AAPL · Apple Inc.                                             │
│  Last: $185.42   Bid: $185.40   Ask: $185.44                   │
│                                                                │
│  ───────────────────────────────────────────────────────────   │
│                                                                │
│  Action                                                        │
│  ┌─────────────────┬─────────────────┐                        │
│  │      BUY        │      SELL       │                        │
│  └─────────────────┴─────────────────┘                        │
│                                                                │
│  Quantity                                                      │
│  ┌────────────────────────────────────────────────────────┐   │
│  │                         100                            │   │
│  └────────────────────────────────────────────────────────┘   │
│                                                                │
│  Order Type                                                    │
│  ┌────────────────────────────────────────────────────────┐   │
│  │  Market                                            ▼   │   │
│  └────────────────────────────────────────────────────────┘   │
│                                                                │
│  Time in Force                                                 │
│  ┌────────────────────────────────────────────────────────┐   │
│  │  Day                                               ▼   │   │
│  └────────────────────────────────────────────────────────┘   │
│                                                                │
│  ───────────────────────────────────────────────────────────   │
│                                                                │
│  Order Summary                                                 │
│  ┌────────────────────────────────────────────────────────┐   │
│  │ Action              BUY                                │   │
│  │ Symbol              AAPL                               │   │
│  │ Quantity            100 shares                         │   │
│  │ Order Type          Market                             │   │
│  │ Est. Total          $18,544.00                         │   │
│  └────────────────────────────────────────────────────────┘   │
│                                                                │
│  Available: $25,000.00                                         │
│                                                                │
│  ┌────────────────────────────────────────────────────────┐   │
│  │                  SUBMIT ORDER                          │   │
│  └────────────────────────────────────────────────────────┘   │
│                                                                │
│  ⚠ Paper Trading Mode                                         │
│                                                                │
└────────────────────────────────────────────────────────────────┘

Button: #2196F3 background, white text
Paper Trading badge: #FFC107 text
```

---

### Interactions & Feedback

| Action | Feedback | Duration |
|--------|----------|----------|
| Price update | Subtle flash (green/red) | 200ms |
| Order submitted | Success banner + haptic | 300ms |
| Error | Red banner + error haptic | Stays until dismissed |
| Pull to refresh | Native iOS spinner | Variable |
| Row selection | Highlight #161616 | Instant |
| Button press | Slight darken + haptic | 100ms |

**No decorative animations.** Every animation serves a functional purpose.

---

### Accessibility

- **Dynamic Type:** Full support, tables remain readable
- **VoiceOver:** All data cells properly labeled with context
- **Color Blind:** Green/Red always paired with ▲/▼ arrows
- **Reduce Motion:** Respected, no price animations
- **Minimum Touch Target:** 44×44pt for all interactive elements

---

### Design Standards & Guidelines

#### Apple Human Interface Guidelines (HIG)
> 📖 https://developer.apple.com/design/human-interface-guidelines/

**Key principles we follow:**

| Guideline | Implementation |
|-----------|----------------|
| **Clarity** | Text is legible, icons precise, adornments subtle |
| **Deference** | Content is the focus, UI doesn't compete with data |
| **Depth** | Visual layers and motion convey hierarchy |

**iOS-specific patterns:**
- **Navigation:** Standard navigation bar with back button, title, actions
- **Tab Bar:** 5 tabs max, icons + labels, 49pt height
- **Safe Areas:** Respect notch, home indicator, rounded corners
- **SF Symbols:** Use Apple's icon system for consistency
- **Haptics:** UIFeedbackGenerator for confirmations and errors

**Dark Mode (HIG):**
- Use semantic colors (`systemBackground`, `label`, `secondaryLabel`)
- Elevated surfaces are lighter, not darker
- Vibrancy for text over materials
- Test in both light and dark

#### Material Design 3 (Reference)
> 📖 https://m3.material.io/

While this is iOS-first, Material Design provides useful guidance for:
- **Data tables:** Column alignment, sorting indicators, row states
- **Color system:** Semantic color roles (on-surface, on-primary)
- **Elevation:** Shadow and surface tint for depth
- **Motion:** Duration and easing curves

#### Financial Data Visualization Standards

**Edward Tufte Principles:**
- **Data-ink ratio:** Maximize data, minimize chartjunk
- **Small multiples:** Repeat chart patterns for comparison
- **Sparklines:** Word-sized graphics for inline data

**Bloomberg Terminal Conventions:**
| Element | Standard |
|---------|----------|
| Positive values | Green text |
| Negative values | Red text |
| Unchanged | White/gray text |
| Headers | UPPERCASE, smaller size |
| Numbers | Right-aligned, monospaced |
| Timestamps | 24-hour format with timezone |

**Candlestick Chart Standards (OHLC):**
- Green/hollow candle = Close > Open (bullish)
- Red/filled candle = Close < Open (bearish)
- Wicks show high/low
- Volume bars below, same color as candle

#### WCAG 2.1 Accessibility Standards
> 📖 https://www.w3.org/WAI/WCAG21/quickref/

| Level | Requirement | Our Implementation |
|-------|-------------|-------------------|
| **AA** | Color contrast ≥ 4.5:1 (text) | All text passes, verified with Stark |
| **AA** | Color contrast ≥ 3:1 (UI components) | Borders and icons pass |
| **AA** | Text resizable to 200% | Dynamic Type supported |
| **AA** | No color-only information | Arrows accompany green/red |
| **AAA** | Color contrast ≥ 7:1 | Primary text on background passes |

**Testing tools:**
- Xcode Accessibility Inspector
- Stark (Figma/Sketch plugin)
- Color Oracle (color blindness simulator)

#### iOS App Store Review Guidelines (Finance)
> 📖 https://developer.apple.com/app-store/review/guidelines/

**Section 3.1.1 - In-App Purchase:**
- Trading features don't require IAP (external service)
- Premium features (if any) must use IAP

**Section 3.2.1 - Acceptable Business:**
- Must be a registered business to offer financial services
- Link to external broker (IBKR) is acceptable

**Section 5.1 - Privacy:**
- Financial data is sensitive, must disclose in privacy policy
- Must request only necessary permissions
- Data deletion must be supported

#### SEC/FINRA Compliance (UI Disclosures)

**Required disclosures:**
```
┌────────────────────────────────────────────────────────────────┐
│ ⚠️ IMPORTANT DISCLOSURES                                       │
│                                                                │
│ • AI-generated scores are not financial advice                │
│ • Past performance does not guarantee future results          │
│ • Investing involves risk, including loss of principal        │
│ • Securities offered through Interactive Brokers LLC          │
│   Member FINRA/SIPC                                           │
└────────────────────────────────────────────────────────────────┘
```

**Placement:**
- Onboarding flow (must acknowledge)
- Settings > Legal
- Before first trade
- Footer on score screens (abbreviated)

#### Number Formatting Standards (ISO/Finance)

| Data Type | Format | Example |
|-----------|--------|---------|
| Currency (USD) | `$#,##0.00` | $1,234.56 |
| Currency (large) | `$#.##B/M/K` | $2.89T |
| Percentage | `+#.##%` / `-#.##%` | +2.34% |
| Shares | `#,##0` | 1,000 |
| Volume | `#.#M/K` | 45.2M |
| Price change | `+$#.##` / `-$#.##` | +$4.21 |
| Date | `MMM D, YYYY` | Feb 2, 2026 |
| Time | `HH:MM ET` | 09:30 ET |
| DateTime | `MMM D, HH:MM ET` | Feb 2, 09:30 ET |

**Locale considerations:**
- US market = USD, comma thousands, period decimal
- Future: Support EU format (period thousands, comma decimal)

#### iOS Charts Best Practices
> 📖 https://developer.apple.com/documentation/charts

**Swift Charts (iOS 16+) guidelines:**
- Use `Chart` view with proper `accessibilityLabel`
- Support VoiceOver audio graphs
- Respect Dynamic Type for axis labels
- Use semantic colors for adaptability

**Performance:**
- Limit visible data points to ~500 for smooth scrolling
- Use downsampling for large datasets (LTTB algorithm)
- Lazy load historical data

#### Haptic Feedback Standards

| Event | Haptic Type | UIKit |
|-------|-------------|-------|
| Button tap | Light impact | `UIImpactFeedbackGenerator(style: .light)` |
| Toggle switch | Light impact | `UIImpactFeedbackGenerator(style: .light)` |
| Order submitted | Success notification | `UINotificationFeedbackGenerator.success` |
| Order failed | Error notification | `UINotificationFeedbackGenerator.error` |
| Price alert triggered | Warning notification | `UINotificationFeedbackGenerator.warning` |
| Pull to refresh | Selection changed | `UISelectionFeedbackGenerator` |
| Slider value change | Selection changed | `UISelectionFeedbackGenerator` |

---

### Animation & Motion Design

> **Philosophy:** Animations should be subtle, purposeful, and fast. They guide attention, provide feedback, and make the app feel responsive — never decorative or slow.

#### Animation Timing Standards

| Duration | Use Case | Easing |
|----------|----------|--------|
| **100ms** | Button press, toggle, micro-feedback | `easeOut` |
| **200ms** | State changes, highlights, fades | `easeInOut` |
| **300ms** | Sheet present/dismiss, navigation | `spring(response: 0.3)` |
| **400ms** | Modal transitions, complex reveals | `spring(response: 0.4, damping: 0.8)` |
| **600ms** | Score bar fill, chart draw-in | `easeOut` |

#### SwiftUI Animation Curves

```swift
// Standard easing
.animation(.easeOut(duration: 0.2), value: isPressed)

// Spring for natural feel
.animation(.spring(response: 0.3, dampingFraction: 0.7), value: isPresented)

// Interactive spring (interruptible)
.animation(.interactiveSpring(response: 0.3, dampingFraction: 0.8), value: offset)
```

---

#### Button Animations

**Primary Button (CTA)**
```
┌─────────────────────────────┐
│        SUBMIT ORDER         │  ← Idle state
└─────────────────────────────┘

     ↓ On press (100ms)

┌───────────────────────────┐
│       SUBMIT ORDER        │    ← Scale to 0.97, darken 10%
└───────────────────────────┘

     ↓ On release (100ms)

┌─────────────────────────────┐
│        SUBMIT ORDER         │  ← Spring back to 1.0
└─────────────────────────────┘
```

```swift
struct PrimaryButton: View {
    @State private var isPressed = false
    
    var body: some View {
        Button(action: { /* action */ }) {
            Text("SUBMIT ORDER")
        }
        .scaleEffect(isPressed ? 0.97 : 1.0)
        .opacity(isPressed ? 0.9 : 1.0)
        .animation(.easeOut(duration: 0.1), value: isPressed)
        .simultaneousGesture(
            DragGesture(minimumDistance: 0)
                .onChanged { _ in isPressed = true }
                .onEnded { _ in isPressed = false }
        )
    }
}
```

**Table Row / Card Tap**
```swift
// Scale down slightly on press
.scaleEffect(isPressed ? 0.98 : 1.0)
.animation(.easeOut(duration: 0.1), value: isPressed)
```

**Icon Button (Favorite/Star)**
```
☆ → ★  (tap)

Animation: Scale up to 1.3, then spring back to 1.0
Duration: 300ms total
Add: Subtle rotation (15°) during scale
```

```swift
struct StarButton: View {
    @State private var isFavorited = false
    
    var body: some View {
        Image(systemName: isFavorited ? "star.fill" : "star")
            .foregroundColor(isFavorited ? .yellow : .gray)
            .scaleEffect(isFavorited ? 1.0 : 1.0)
            .animation(.spring(response: 0.3, dampingFraction: 0.5), value: isFavorited)
            .onTapGesture {
                withAnimation { isFavorited.toggle() }
            }
    }
}
```

---

#### Navigation & Transitions

**Screen Push (Standard iOS)**
```
┌──────────┐      ┌──────────┐
│  Screen  │  →   │  Screen  │
│    A     │      │    B     │
└──────────┘      └──────────┘

• Screen B slides in from right (300ms)
• Screen A slides left and dims slightly
• Use NavigationStack default
```

**Bottom Sheet Present**
```
                    ┌──────────────┐
                    │              │
                    │    Sheet     │
                    │   Content    │
┌──────────────┐    │              │
│              │ →  ├──────────────┤
│    Main      │    │    Main      │
│   Content    │    │   (dimmed)   │
│              │    │              │
└──────────────┘    └──────────────┘

• Sheet springs up from bottom (300ms)
• Background dims to 60% black
• Drag to dismiss with velocity detection
```

```swift
.sheet(isPresented: $showSheet) {
    OrderEntryView()
        .presentationDetents([.medium, .large])
        .presentationDragIndicator(.visible)
}
```

**Modal Present (Full Screen)**
```
• Slide up from bottom (400ms)
• Spring easing with slight overshoot
• Background cross-fades
```

---

#### Data & Feedback Animations

**Price Update Flash**
```
$185.42 → $185.67 (price increased)

Animation sequence:
1. Text color → bright green (instant)
2. Subtle background flash (green at 20% opacity)
3. Fade back to normal (400ms)
```

```swift
struct PriceView: View {
    @State private var flashColor: Color = .clear
    
    func priceUpdated(increased: Bool) {
        flashColor = increased ? .green.opacity(0.2) : .red.opacity(0.2)
        withAnimation(.easeOut(duration: 0.4)) {
            flashColor = .clear
        }
    }
}
```

**Score Bar Fill**
```
Fundamental  ░░░░░░░░░░░░░░░░░░░░  0
             ↓ (600ms ease-out)
Fundamental  ████████████████░░░░  82
```

```swift
struct ScoreBar: View {
    let score: Int
    @State private var animatedScore = 0
    
    var body: some View {
        GeometryReader { geo in
            Rectangle()
                .fill(scoreColor)
                .frame(width: geo.size.width * CGFloat(animatedScore) / 100)
        }
        .onAppear {
            withAnimation(.easeOut(duration: 0.6)) {
                animatedScore = score
            }
        }
    }
}
```

**Number Counter (Odometer Effect)**
```
$124,532 → $125,847

Animation: Each digit rolls independently
Duration: 400ms
Use: Portfolio value changes
```

```swift
// Use NumberFormatter with animated Text
Text(value, format: .currency(code: "USD"))
    .contentTransition(.numericText(value: value))
    .animation(.easeInOut(duration: 0.4), value: value)
```

**Loading States**
```
┌────────────────────────────────┐
│  ░░░░░░░░░░░░░░░░░░░░░░░░░░░  │  ← Skeleton shimmer
│  ░░░░░░░░░░░░                  │
│  ░░░░░░░░░░░░░░░░░░░░         │
└────────────────────────────────┘

• Gradient shimmer moves left to right
• Duration: 1.5s, repeat forever
• Subtle, not distracting
```

```swift
struct ShimmerView: View {
    @State private var shimmerOffset: CGFloat = -1
    
    var body: some View {
        RoundedRectangle(cornerRadius: 4)
            .fill(Color.gray.opacity(0.3))
            .overlay(
                LinearGradient(
                    colors: [.clear, .white.opacity(0.2), .clear],
                    startPoint: .leading,
                    endPoint: .trailing
                )
                .offset(x: shimmerOffset * 200)
            )
            .onAppear {
                withAnimation(.linear(duration: 1.5).repeatForever(autoreverses: false)) {
                    shimmerOffset = 1
                }
            }
    }
}
```

---

#### Chart Animations

**Initial Chart Draw**
```
• Line/candles draw in from left to right
• Duration: 600ms
• Volume bars grow up from bottom
```

**Time Period Change (1D → 1W)**
```
• Current data fades out (150ms)
• New data fades in (150ms)
• Axis labels cross-fade
```

**Hover/Touch on Data Point**
```
• Point scales up 1.5x
• Tooltip fades in above (200ms)
• Vertical line appears
• Other points dim slightly
```

---

#### Tab Bar Animations

**Tab Switch**
```
┌────┬────┬────┬────┬────┐
│ 🏠 │ 📊 │ 💹 │ 📁 │ ⚙️ │
└────┴────┴────┴────┴────┘

• Selected icon: Scale 1.0 → 1.1 → 1.0 (bounce)
• Unselected icons: No animation
• Label fades in under selected
```

**Badge Notification**
```
• Badge scales in with spring (0 → 1.0)
• Subtle bounce overshoot
• Duration: 300ms
```

---

#### Pull to Refresh

```
↓ Pull down

┌────────────────────────────────┐
│         ↻ (rotating)           │
│                                │
│  Updating...                   │
└────────────────────────────────┘

• Use native iOS RefreshControl
• Custom: Circular progress that fills as you pull
• Spinner rotates while loading
• Snap back with spring when complete
```

---

#### Accessibility: Reduced Motion

```swift
@Environment(\.accessibilityReduceMotion) var reduceMotion

// Conditional animation
.animation(reduceMotion ? nil : .spring(), value: isExpanded)

// Fallback to instant transitions
withAnimation(reduceMotion ? nil : .easeOut(duration: 0.3)) {
    isPresented = true
}
```

**When Reduce Motion is ON:**
- Replace slides with cross-fades
- Disable spring bounces
- Keep essential feedback (color changes, opacity)
- Remove decorative animations

---

#### Animation Don'ts ❌

| Avoid | Why |
|-------|-----|
| Animations > 500ms | Feels slow, blocks interaction |
| Bouncy springs on data | Looks unprofessional for finance |
| Parallax effects | Distracting, causes motion sickness |
| Auto-playing animations | Annoying, battery drain |
| Blocking animations | User should never wait for animation |
| Inconsistent timing | Feels broken |

---

### Design Files & Resources

📁 **Inspiration folder:** `design/inspiration/`
- `DESIGN_INSPIRATION.md` — Curated references with links
- `DIRECT_LINKS.md` — Behance/Dribbble/Mobbin links to browse
- `screenshots/` — Save reference screenshots here

📱 **Professional apps to study:**
- Interactive Brokers TWS Mobile
- Bloomberg (if accessible)
- Fidelity Active Trader Pro
- TD Ameritrade thinkorswim
- Apple Stocks (native iOS dark mode)

---

## Interactive Brokers Integration

### API Options

| API | Best For | Features |
|-----|----------|----------|
| **Web API (REST)** | Modern apps | OAuth2, WebSocket, full features |
| **TWS API** | Desktop integration | Full order types, real-time data |
| **Client Portal API** | Quick setup | Simpler auth, good for mobile |

### Recommended: Web API (REST + WebSocket)

#### Authentication Flow
1. User logs into IBKR via OAuth2
2. App receives access token
3. Token used for API calls
4. Refresh token for session extension

#### Key Endpoints

```
# Market Data
GET /v1/api/iserver/marketdata/snapshot
GET /v1/api/iserver/marketdata/history

# Orders
POST /v1/api/iserver/account/{accountId}/orders
GET /v1/api/iserver/account/{accountId}/orders
DELETE /v1/api/iserver/account/{accountId}/order/{orderId}

# Portfolio
GET /v1/api/portfolio/{accountId}/positions
GET /v1/api/portfolio/accounts

# Account
GET /v1/api/iserver/account/trades
GET /v1/api/portfolio/{accountId}/summary
```

#### Paper Trading
- IBKR provides separate paper trading accounts
- Same API, different account ID
- Toggle in app settings

### Implementation Example

```swift
class IBKRClient {
    private let baseURL = "https://localhost:5000/v1/api"
    private var accessToken: String?
    
    func placeOrder(symbol: String, quantity: Int, orderType: OrderType) async throws -> OrderResponse {
        let order = Order(
            conid: try await getContractId(symbol),
            orderType: orderType.rawValue,
            quantity: quantity,
            side: quantity > 0 ? "BUY" : "SELL"
        )
        
        let response = try await post("/iserver/account/\(accountId)/orders", body: order)
        return response
    }
}
```

---

## Security & Compliance

### Data Security

| Layer | Protection |
|-------|------------|
| Transport | TLS 1.3 for all API calls |
| Storage | AES-256 encryption at rest |
| Authentication | OAuth2 + biometric (Face ID/Touch ID) |
| API Keys | Stored in iOS Keychain |
| Session | JWT with 1-hour expiry |

### Compliance Requirements

#### SEC Regulations
- No insider trading features
- Clear disclosure of AI recommendations
- User acknowledgment of trading risks

#### App Store Guidelines
- Financial app category requirements
- Clear in-app purchase disclosure
- No guaranteed returns claims

#### Data Privacy
- GDPR compliance for EU users
- CCPA compliance for CA users
- Clear privacy policy
- User data deletion capability

### Risk Disclosures
- **Mandatory:** Disclaimer that past performance doesn't guarantee future results
- **Mandatory:** AI recommendations are not financial advice
- **Recommended:** Risk tolerance questionnaire during onboarding

---

## Restrictions & Limitations

### Technical Limitations
- IBKR API rate limits (varies by endpoint)
- Sentiment model inference time (~100ms per text)
- Weekly score updates (not real-time)
- Mobile data usage for real-time features

### Trading Limitations
- No options or derivatives (initial version)
- US stocks only (S&P500 universe)
- Minimum account size: $2,000 (IBKR requirement)
- Market hours trading only (no extended hours initially)

### Model Limitations
- Sentiment models may miss sarcasm/nuance
- Backtesting ≠ live performance
- Macro regime detection has lag
- Black swan events unpredictable

### Regulatory Limitations
- Not registered as RIA (Registered Investment Advisor)
- Cannot manage money on behalf of users
- Must disclaim: "Not financial advice"

---

## Development Roadmap

> **#1 RULE: FUNCTIONALITY FIRST.**
> 
> A working app with simple scoring beats a broken app with sophisticated ML.
> An ugly app that functions beats a beautiful app that crashes.
> Ship something that WORKS, then iterate.
> 
> **If it doesn't work, nothing else matters.**

### Priority Stack

```
┌─────────────────────────────────────────────────────────────────┐
│  P0 - CRITICAL (Must have for MVP)                              │
│  ─────────────────────────────────────────────────────────────  │
│  • Flawless UX/UI (no glitches, 60fps, instant feedback)       │
│  • Reliable data pipeline (weekly refresh, no failures)         │
│  • Correct data preprocessing (accurate numbers displayed)      │
│  • Paper trading works perfectly                                │
├─────────────────────────────────────────────────────────────────┤
│  P1 - IMPORTANT (MVP, but can be basic)                         │
│  ─────────────────────────────────────────────────────────────  │
│  • Scoring model (simple is fine, must be explainable)         │
│  • Basic sentiment (can use simple rules initially)             │
│  • Core screens (dashboard, scores, stock detail, trade)        │
├─────────────────────────────────────────────────────────────────┤
│  P2 - NICE TO HAVE (Post-MVP iteration)                         │
│  ─────────────────────────────────────────────────────────────  │
│  • Advanced ML models (FinBERT, XGBoost ensembles)             │
│  • Model accuracy optimization                                  │
│  • Backtesting with real performance metrics                    │
│  • Push notifications                                           │
├─────────────────────────────────────────────────────────────────┤
│  P3 - FUTURE (V2+)                                              │
│  ─────────────────────────────────────────────────────────────  │
│  • Live trading (real money)                                    │
│  • Advanced analytics                                           │
│  • Social features                                              │
│  • iPad/watchOS                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

### Phase 1: Foundation & Data Pipeline (Weeks 1-4)

**Goal:** Bulletproof data infrastructure that runs reliably every week.

#### Week 1-2: Data Pipeline Core
| Task | Priority | Details |
|------|----------|---------|
| Set up PostgreSQL database | P0 | Stock metadata, prices, scores |
| Create stock universe table | P0 | S&P500 >$10B, ~400 stocks |
| Price data ingestion | P0 | Daily OHLCV from Financial Modeling Prep |
| Fundamental data ingestion | P0 | Quarterly financials, ratios |
| Scheduled jobs (cron) | P0 | Weekly Sunday night refresh |
| Data validation layer | P0 | Check for nulls, outliers, staleness |
| Logging & alerting | P0 | Slack/email on pipeline failures |

#### Week 3-4: Data Preprocessing & API
| Task | Priority | Details |
|------|----------|---------|
| Feature engineering | P0 | Calculate all derived metrics |
| Percentile ranking | P0 | Normalize scores 0-100 |
| FastAPI backend | P0 | REST endpoints for iOS app |
| API response caching | P0 | Redis for fast reads |
| Data freshness checks | P0 | "Last updated" timestamps |

#### 🧪 Phase 1 Testing (Required)
| Test Type | What to Test | Pass Criteria |
|-----------|--------------|---------------|
| **Unit Tests** | Each calculation function | All formulas return expected values |
| **Unit Tests** | Data validation rules | Catches nulls, outliers, bad data |
| **Unit Tests** | API endpoints | Correct responses, error handling |
| **Integration Test** | Full pipeline run | Data flows from source → DB → API |
| **Integration Test** | Scheduled job | Cron triggers, completes, alerts on failure |
| **Smoke Test** | API health check | `/health` returns 200 |

```python
# Example unit tests
def test_percentile_ranking():
    data = [10, 20, 30, 40, 50]
    result = percentile_rank(data)
    assert result == [0, 25, 50, 75, 100]

def test_pipeline_handles_missing_data():
    with pytest.raises(DataValidationError):
        process_stock_data({'price': None})

# Example integration test        
def test_full_pipeline_run():
    result = run_weekly_pipeline(dry_run=True)
    assert result['stocks_processed'] >= 400
    assert result['errors'] == 0
    assert result['duration_seconds'] < 3600
```

**Milestone:** Pipeline runs Sunday night, all data correct Monday morning. Zero manual intervention. **All tests pass.**

---

### Phase 2: iOS App Foundation (Weeks 5-8)

**Goal:** Functional app that displays data correctly. Polish is secondary.

#### Week 5-6: Core UI Shell
| Task | Priority | Details |
|------|----------|---------|
| Project setup (SwiftUI) | P0 | Xcode project, folder structure |
| Design system implementation | P0 | Colors, typography, components |
| Tab bar navigation | P0 | Home, Scores, Trade, Portfolio, Settings |
| Dark mode only | P0 | Single theme, done right |
| Loading states | P0 | Skeleton views, spinners |
| Error states | P0 | Friendly error messages |
| Empty states | P0 | "No data" placeholders |
| Pull to refresh | P0 | On all data screens |

#### Week 6-7: Core Screens
| Task | Priority | Details |
|------|----------|---------|
| Dashboard screen | P0 | Portfolio value, market overview, top picks |
| Score list screen | P0 | Sortable table, filters |
| Stock detail screen | P0 | Price chart, score breakdown, key stats |
| API integration | P0 | Connect to backend |
| Offline handling | P0 | Cache last data, show stale indicator |

#### Week 7-8: Testing & Stability
| Task | Priority | Details |
|------|----------|---------|
| Memory leak check | P0 | Instruments profiling |
| Crash-free testing | P0 | No crashes in any flow |
| Accessibility audit | P0 | VoiceOver, Dynamic Type |

#### 🧪 Phase 2 Testing (Required)
| Test Type | What to Test | Pass Criteria |
|-----------|--------------|---------------|
| **Unit Tests** | ViewModels | Data transforms correctly |
| **Unit Tests** | API client | Handles success, errors, timeouts |
| **Unit Tests** | Data formatting | Numbers, dates, currencies display correctly |
| **UI Tests** | Navigation flows | All tabs accessible, back works |
| **UI Tests** | Screen renders | No crashes on any screen |
| **UI Tests** | Loading states | Skeleton shows, then data loads |
| **UI Tests** | Error states | Error message shows, retry works |

```swift
// Example XCTest
func testDashboardLoadsData() throws {
    let app = XCUIApplication()
    app.launch()
    
    // Wait for data to load
    let portfolioValue = app.staticTexts["portfolioValue"]
    XCTAssertTrue(portfolioValue.waitForExistence(timeout: 5))
    XCTAssertFalse(portfolioValue.label.isEmpty)
}

func testScoreListDisplaysStocks() throws {
    let app = XCUIApplication()
    app.tabBars.buttons["Scores"].tap()
    
    let stockCells = app.tables.cells
    XCTAssertGreaterThan(stockCells.count, 0)
}
```

#### 🔗 INTEGRATION TEST: Backend ↔ iOS (End of Phase 2)
| Test | What to Test | Pass Criteria |
|------|--------------|---------------|
| **E2E** | App fetches real data from API | Stocks display with correct prices |
| **E2E** | Pull to refresh | New data loads from backend |
| **E2E** | Offline mode | Cached data shows when offline |
| **E2E** | Error recovery | API error → error screen → retry → success |

**Milestone:** App displays correct data from backend. **All tests pass. Integration verified.**

---

### Phase 3: Simple Scoring Model (Weeks 9-10)

**Goal:** Working score that's explainable. Accuracy is secondary — reliability is primary.

#### Week 9: V1 Scoring Model
| Task | Priority | Details |
|------|----------|---------|
| Fundamental score | P1 | Simple weighted average of ratios |
| Technical score | P1 | Momentum + relative strength |
| Macro score | P1 | Sector × regime matrix (hardcoded) |
| Sentiment score | P1 | **V1: Skip or use simple keyword match** |
| Composite score | P1 | Weighted sum, percentile ranked |
| Score explanation | P1 | "High because: strong earnings, momentum" |

**V1 Scoring Formula (Simple):**
```python
# Start simple, iterate later
fundamental = 0.5 * earnings_growth_rank + 0.3 * roe_rank + 0.2 * pe_rank
technical = 0.6 * momentum_3m_rank + 0.4 * rsi_rank
composite = 0.50 * fundamental + 0.30 * technical + 0.20 * sector_adjustment
```

#### Week 10: Score Display & Testing
| Task | Priority | Details |
|------|----------|---------|
| Score breakdown UI | P1 | Show component contributions |
| Signal generation | P1 | BUY (>70), HOLD (40-70), SELL (<40) |
| Historical score tracking | P1 | Store weekly snapshots |
| Documentation | P1 | How scores are calculated |

#### 🧪 Phase 3 Testing (Required)
| Test Type | What to Test | Pass Criteria |
|-----------|--------------|---------------|
| **Unit Tests** | Each score component | Returns 0-100 for all inputs |
| **Unit Tests** | Composite calculation | Weights sum to 1.0, output 0-100 |
| **Unit Tests** | Signal generation | BUY/HOLD/SELL thresholds correct |
| **Unit Tests** | Edge cases | Handles missing data, NaN, zeros |
| **Sanity Test** | Top 20 stocks | Manual review — makes sense? |
| **Sanity Test** | Bottom 20 stocks | Manual review — no obvious errors? |
| **Sanity Test** | Known stocks | AAPL, MSFT not ranked last |

```python
# Example unit tests
def test_fundamental_score_range():
    for stock in all_stocks:
        score = calculate_fundamental_score(stock)
        assert 0 <= score <= 100

def test_composite_weights_sum_to_one():
    weights = [0.50, 0.30, 0.20]  # fundamental, technical, macro
    assert sum(weights) == 1.0

def test_signal_thresholds():
    assert get_signal(75) == 'BUY'
    assert get_signal(50) == 'HOLD'
    assert get_signal(30) == 'SELL'

# Sanity check
def test_top_stocks_not_garbage():
    top_20 = get_top_stocks(20)
    # At least some well-known quality stocks should be in top 20
    quality_stocks = {'AAPL', 'MSFT', 'GOOGL', 'JNJ', 'V'}
    overlap = set(top_20) & quality_stocks
    assert len(overlap) >= 2, "Top 20 should include some quality stocks"
```

**Milestone:** Scores appear in app. They make sense (AAPL not ranked last). Fully explainable. **All tests pass.**

---

### Phase 4: Paper Trading (Weeks 11-13)

**Goal:** Full trading flow works with paper money. No real money until bulletproof.

#### Week 11-12: IBKR Paper Trading
| Task | Priority | Details |
|------|----------|---------|
| IBKR account setup | P0 | Paper trading account |
| OAuth2 integration | P0 | Secure login flow |
| Portfolio sync | P0 | Read positions from IBKR |
| Market data | P0 | Real-time quotes (or delayed) |
| Order entry UI | P0 | Buy/Sell form |
| Order submission | P0 | POST to IBKR API |
| Order confirmation | P0 | Success/error handling |
| Order history | P0 | List past orders |

#### Week 13: Trading Testing
| Task | Priority | Details |
|------|----------|---------|
| Position display | P0 | P&L, cost basis, % change |
| Paper/Live toggle | P0 | Clear indicator in UI |
| Risk warnings | P0 | "Paper mode" banner |
| Legal disclaimers | P0 | Required disclosures |

#### 🧪 Phase 4 Testing (Required)
| Test Type | What to Test | Pass Criteria |
|-----------|--------------|---------------|
| **Unit Tests** | Order validation | Rejects invalid qty, price |
| **Unit Tests** | P&L calculation | Cost basis, returns correct |
| **Unit Tests** | Position sizing | Constraints enforced |
| **API Tests** | IBKR auth flow | Token refresh works |
| **API Tests** | Order submission | Returns order ID |
| **API Tests** | Portfolio fetch | Returns positions correctly |
| **UI Tests** | Order entry form | All fields work, validation shows |
| **UI Tests** | Order confirmation | Shows success/error |

```swift
// Example UI tests
func testOrderEntryValidation() throws {
    let app = XCUIApplication()
    // Navigate to trade
    app.tabBars.buttons["Trade"].tap()
    app.buttons["AAPL"].tap()
    
    // Try invalid quantity
    let qtyField = app.textFields["quantity"]
    qtyField.tap()
    qtyField.typeText("-10")
    app.buttons["Review Order"].tap()
    
    // Should show error
    XCTAssertTrue(app.staticTexts["Invalid quantity"].exists)
}

func testPaperTradeSubmission() throws {
    let app = XCUIApplication()
    // Submit a paper trade
    navigateToTradeScreen(app, ticker: "AAPL")
    enterQuantity(app, qty: 10)
    app.buttons["Review Order"].tap()
    app.buttons["Submit Order"].tap()
    
    // Should show confirmation
    XCTAssertTrue(app.staticTexts["Order Submitted"].waitForExistence(timeout: 10))
}
```

#### 🔗 INTEGRATION TEST: Full Trading Flow (End of Phase 4)
| Test | What to Test | Pass Criteria |
|------|--------------|---------------|
| **E2E** | Browse → Trade → Confirm | Complete flow without errors |
| **E2E** | Order appears in IBKR | Check IBKR portal shows order |
| **E2E** | Portfolio updates | Position shows after fill |
| **E2E** | P&L calculates | Correct cost basis, unrealized P&L |
| **E2E** | Order history | Past orders display correctly |

```
INTEGRATION TEST SCRIPT:
1. Login to app
2. Browse to AAPL
3. Tap Trade → Buy 10 shares → Market order
4. Submit order
5. ✓ Order confirmation shows
6. ✓ Check IBKR portal — order exists
7. Wait for fill
8. ✓ Portfolio shows AAPL position
9. ✓ P&L shows correct cost basis
10. ✓ Order history shows the trade
```

**Milestone:** Can browse scores → tap trade → submit paper order → see in portfolio. **All tests pass. E2E verified.**

---

### Phase 5: MVP Launch & Stabilization (Weeks 14-16)

**Goal:** Stable, reliable app ready for daily use.

#### Week 14: QA & Bug Fixing
| Task | Priority | Details |
|------|----------|---------|
| Full regression testing | P0 | Every screen, every flow |
| Edge case testing | P0 | No data, slow network, errors |
| Device testing | P0 | iPhone 12-15, different sizes |
| Memory profiling | P0 | No leaks |
| Battery profiling | P0 | No excessive drain |
| Crash analytics setup | P0 | Firebase Crashlytics |

#### Week 15: Soft Launch
| Task | Priority | Details |
|------|----------|---------|
| TestFlight release | P0 | Internal testing |
| Monitor pipeline | P0 | Watch Sunday refresh |
| Monitor app analytics | P0 | Usage patterns |
| Bug fixes | P0 | Address critical issues |

#### Week 16: Stabilization
| Task | Priority | Details |
|------|----------|---------|
| Performance tuning | P0 | Based on real usage |
| Error rate reduction | P0 | Target: <0.1% crash rate |
| Pipeline reliability | P0 | Target: 100% weekly success |

#### 🧪 Phase 5 Testing (Required)
| Test Type | What to Test | Pass Criteria |
|-----------|--------------|---------------|
| **Regression** | All previous tests | 100% pass rate |
| **Device Matrix** | iPhone 12, 13, 14, 15 | Works on all |
| **Device Matrix** | iOS 16, 17 | Works on both |
| **Performance** | Memory usage | No leaks, <200MB |
| **Performance** | Battery | No excessive drain |
| **Performance** | Scroll fps | 60fps in lists |
| **Stress Test** | 1000 stocks in list | No crash, smooth scroll |
| **Network** | Slow 3G | Graceful degradation |
| **Network** | Offline | Cached data shows |
| **Network** | Timeout | Error + retry works |

#### 🔗 FULL SYSTEM INTEGRATION TEST (End of Phase 5)

**This is the final MVP acceptance test. ALL must pass.**

```
╔════════════════════════════════════════════════════════════════════╗
║                    MVP ACCEPTANCE TEST CHECKLIST                   ║
╠════════════════════════════════════════════════════════════════════╣
║                                                                    ║
║  DATA PIPELINE                                                     ║
║  [ ] Pipeline runs Sunday night without intervention               ║
║  [ ] All ~400 stocks have fresh data Monday morning                ║
║  [ ] Scores calculated correctly (spot check 10 stocks)            ║
║  [ ] API returns data in <500ms                                    ║
║                                                                    ║
║  iOS APP - LAUNCH                                                  ║
║  [ ] App launches without crash                                    ║
║  [ ] App launches in <3 seconds                                    ║
║  [ ] Dashboard shows portfolio value                               ║
║  [ ] No crashes after 30 min of use                                ║
║                                                                    ║
║  iOS APP - DATA                                                    ║
║  [ ] Score list shows all stocks                                   ║
║  [ ] Sorting works (by score, name, sector)                        ║
║  [ ] Stock detail shows correct data                               ║
║  [ ] Prices match external source (Yahoo)                          ║
║  [ ] Score breakdown adds up to composite                          ║
║                                                                    ║
║  iOS APP - TRADING                                                 ║
║  [ ] Can login to IBKR                                             ║
║  [ ] Can view paper portfolio                                      ║
║  [ ] Can submit paper buy order                                    ║
║  [ ] Can submit paper sell order                                   ║
║  [ ] Order appears in portfolio                                    ║
║  [ ] P&L calculates correctly                                      ║
║                                                                    ║
║  iOS APP - EDGE CASES                                              ║
║  [ ] Works offline (shows cached data)                             ║
║  [ ] Handles API errors gracefully                                 ║
║  [ ] Handles no network gracefully                                 ║
║  [ ] Pull to refresh works                                         ║
║                                                                    ║
║  ACCESSIBILITY                                                     ║
║  [ ] VoiceOver can read all screens                                ║
║  [ ] Dynamic Type works                                            ║
║                                                                    ║
╠════════════════════════════════════════════════════════════════════╣
║  ALL BOXES CHECKED = MVP READY TO SHIP                             ║
╚════════════════════════════════════════════════════════════════════╝
```

**Milestone: MVP COMPLETE** ✅
- App runs smoothly
- Data refreshes weekly without fail
- Paper trading works
- Scores display correctly
- Zero critical bugs
- **All acceptance tests pass**

---

### Phase 6: Model Improvement (Weeks 17-22)

**Goal:** Now that foundation is solid, improve model accuracy.

#### Week 17-18: Sentiment Analysis
| Task | Priority | Details |
|------|----------|---------|
| Enable FinBERT | P2 | Flip flag: `SENTIMENT_MODEL = "finbert"` |
| Compare keyword vs FinBERT | P2 | A/B test accuracy |
| News data pipeline | P2 | Free RSS feeds or SEC filings |
| Earnings call transcripts | P2 | SEC filings parsing (optional) |
| Sentiment score v2 | P2 | ML-based if FinBERT proves better |

#### Week 19-20: Advanced Models
| Task | Priority | Details |
|------|----------|---------|
| XGBoost for earnings | P2 | Surprise prediction |
| Backtesting framework | P2 | VectorBT integration |
| Walk-forward testing | P2 | Prevent overfitting |
| Model comparison | P2 | V1 vs V2 performance |

#### Week 21-22: Model Iteration
| Task | Priority | Details |
|------|----------|---------|
| A/B test scoring | P2 | Compare old vs new |
| Feature importance | P2 | Which factors matter |
| Hyperparameter tuning | P2 | Optimize weights |
| Model documentation | P2 | Methodology whitepaper |

#### 🧪 Phase 6 Testing (Required)
| Test Type | What to Test | Pass Criteria |
|-----------|--------------|---------------|
| **Unit Tests** | FinBERT wrapper | Returns sentiment scores |
| **Unit Tests** | News parsing | Extracts headlines correctly |
| **Unit Tests** | Transcript parsing | SEC filings parsed |
| **Backtest** | V1 model | Establish baseline performance |
| **Backtest** | V2 model | Compare to V1 |
| **Backtest** | Walk-forward | No overfitting (OOS performance) |
| **Regression** | All MVP tests | Still pass after changes |

```python
# Model comparison tests
def test_v2_not_worse_than_v1():
    v1_sharpe = backtest_model(v1_scores)['sharpe']
    v2_sharpe = backtest_model(v2_scores)['sharpe']
    assert v2_sharpe >= v1_sharpe * 0.9, "V2 should not be significantly worse"

def test_walk_forward_no_overfitting():
    in_sample_sharpe = backtest_in_sample()['sharpe']
    out_of_sample_sharpe = backtest_out_of_sample()['sharpe']
    assert out_of_sample_sharpe >= in_sample_sharpe * 0.7, "OOS should not collapse"
```

**Milestone:** Model accuracy measurably improved. Backtests show positive alpha. **No regression in MVP functionality.**

---

### Phase 7: Advanced Features (Weeks 23+)

**Goal:** Premium features for power users.

| Feature | Priority | Target |
|---------|----------|--------|
| **Onboarding & User Guide** | P2 | New user education |
| Push notifications | P2 | Score changes, alerts |
| Watchlists | P2 | Custom stock lists |
| Performance analytics | P2 | Personal trading stats |
| Live trading | P3 | Real money (requires audit) |
| Earnings calendar | P2 | Upcoming events |
| Sector analysis | P2 | Sector-level views |
| iPad support | P3 | Responsive layouts |
| Widget | P3 | Home screen widget |

---

### 🎓 Onboarding & New User Experience (Phase 7)

> **Goal:** Respect the user's intelligence and time. No patronizing tutorials — just fast context-setting and immediate value. The Busy Builder should be productive within 60 seconds.

#### Design Philosophy for Onboarding

Our target user is a sophisticated tech professional. They've seen a thousand apps. They'll figure out basic navigation. What they need:
1. **Why this app is different** (30 seconds)
2. **How to interpret the scores** (30 seconds)
3. **Quick portfolio setup** (60 seconds)
4. **Then get out of their way**

> 🎯 **Onboarding North Star:** Skip button always visible. No forced carousels. Get them to value fast.

#### First Launch Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                                                     [ Skip → ]  │
│                                                                 │
│              Your Portfolio, On Autopilot.                     │
│                                                                 │
│    We rank S&P 500 stocks weekly using fundamentals,           │
│    momentum, and sentiment. You decide. We execute.            │
│                                                                 │
│    ⏱️ 5 minutes/week. That's it.                                │
│                                                                 │
│                    [ Let's Go ]                                 │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  THE SCORE SYSTEM                                  [ Skip → ]  │
│                                                                 │
│    Every stock gets a score (0-100) updated weekly.            │
│                                                                 │
│    🟢 70+    Strong Buy — fundamentals + momentum aligned       │
│    🟡 40-70  Hold — mixed signals, wait for clarity            │
│    🔴 <40   Sell — weakening thesis                            │
│                                                                 │
│    Scores combine:                                              │
│    35% Fundamentals · 25% Sentiment · 20% Macro · 20% Technical│
│                                                                 │
│    (You can drill into each component anytime.)                 │
│                                                                 │
│                    [ Got It ]                                   │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  PORTFOLIO SIZE                                    [ Skip → ]  │
│                                                                 │
│    How much are you investing?                                  │
│                                                                 │
│    [ < $25K ]  [ $25K-100K ]  [ $100K+ ]                       │
│                                                                 │
│    ───────────────────────────────────────                     │
│    Based on your selection:                                     │
│    • Recommended positions: 8-12 stocks                        │
│    • Max per stock: 10%                                        │
│    • Min 3 sectors                                             │
│                                                                 │
│    (Adjustable later in Settings)                              │
│                                                                 │
│                    [ Continue ]                                 │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  YOU'RE SET                                                     │
│                                                                 │
│    ✓ Paper trading enabled (switch to live anytime)            │
│    ✓ Weekly notifications ON (Sundays, after scores refresh)   │
│    ✓ Top 10 picks ready to view                                │
│                                                                 │
│    ─────────────────────────────────────────                   │
│    💡 Pro tip: Check in Sundays after market close.            │
│       New scores drop, fresh opportunities surface.             │
│                                                                 │
│                  [ Show Me the Scores ]                         │
└─────────────────────────────────────────────────────────────────┘
│                                                                 │
│             [ Start Paper Trading ]                            │
│                                                                 │
│    ⚠️ This is not financial advice. Investing involves risk.   │
└─────────────────────────────────────────────────────────────────┘
```

#### Interactive Tooltips (First-Time Hints)

Show contextual hints when user first visits each screen:

```
┌─────────────────────────────────────────────────────────────────┐
│  Score: 85                                                      │
│         ↑                                                       │
│    ┌────────────────────────────────────────┐                  │
│    │ 💡 SCORE EXPLAINED                     │                  │
│    │                                        │                  │
│    │ This stock scores 85/100, placing it   │                  │
│    │ in the top 15% of all stocks.          │                  │
│    │                                        │                  │
│    │ Tap to see the breakdown.              │                  │
│    │                                        │                  │
│    │              [ Got it ]                │                  │
│    └────────────────────────────────────────┘                  │
└─────────────────────────────────────────────────────────────────┘
```

**Tooltip triggers:**
| Screen | First-Time Tooltip |
|--------|-------------------|
| Score List | "Tap any stock to see details" |
| Score Detail | "Scroll down to see what's driving the score" |
| Trade Button | "Start with paper trading to practice" |
| Portfolio | "This shows your positions and P&L" |
| Score Breakdown | "These 4 factors combine into the total score" |

#### Guided Portfolio Builder (Optional Feature)

Help new users build their first portfolio:

```
┌─────────────────────────────────────────────────────────────────┐
│               🚀 BUILD YOUR FIRST PORTFOLIO                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  How much are you starting with?                               │
│                                                                 │
│  ○ Under $5,000                                                │
│  ● $5,000 - $25,000                                            │
│  ○ $25,000 - $100,000                                          │
│  ○ Over $100,000                                               │
│                                                                 │
│                    [ Continue ]                                 │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│               SUGGESTED PORTFOLIO                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Based on $15,000, we suggest 10 stocks:                       │
│                                                                 │
│  TECHNOLOGY (30%)                                              │
│  ├─ AAPL   Score: 85  │  $1,500 (10%)                         │
│  ├─ MSFT   Score: 82  │  $1,500 (10%)                         │
│  └─ NVDA   Score: 78  │  $1,500 (10%)                         │
│                                                                 │
│  HEALTHCARE (20%)                                              │
│  ├─ JNJ    Score: 76  │  $1,500 (10%)                         │
│  └─ UNH    Score: 74  │  $1,500 (10%)                         │
│                                                                 │
│  FINANCIALS (20%)                                              │
│  ├─ JPM    Score: 75  │  $1,500 (10%)                         │
│  └─ V      Score: 73  │  $1,500 (10%)                         │
│                                                                 │
│  CONSUMER (15%)                                                │
│  └─ AMZN   Score: 71  │  $1,500 (10%)                         │
│                                                                 │
│  INDUSTRIAL (15%)                                              │
│  └─ CAT    Score: 70  │  $1,500 (10%)                         │
│                                                                 │
│  ─────────────────────────────────────────────────────         │
│  💰 CASH BUFFER: $1,500 (10%)                                  │
│  ─────────────────────────────────────────────────────         │
│                                                                 │
│  [ Customize ]              [ Use This Portfolio ]             │
│                                                                 │
│  ⚠️ This is a suggestion, not financial advice.                │
└─────────────────────────────────────────────────────────────────┘
```

#### Education Cards (In-App Learning)

Sprinkle educational content throughout the app:

```
┌─────────────────────────────────────────────────────────────────┐
│  📚 LEARN: What is P/E Ratio?                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  P/E (Price-to-Earnings) measures how much you pay for         │
│  each dollar of earnings.                                       │
│                                                                 │
│  P/E = Stock Price ÷ Earnings Per Share                        │
│                                                                 │
│  • Low P/E (<15): May be undervalued or struggling             │
│  • Average P/E (15-25): Fairly valued                          │
│  • High P/E (>25): Growth expected or overvalued               │
│                                                                 │
│  AAPL's P/E: 28.5 (above average — investors expect growth)    │
│                                                                 │
│                    [ Got it ]                                   │
└─────────────────────────────────────────────────────────────────┘
```

**Education topics:**
- What is P/E Ratio?
- Understanding Momentum
- Why Diversification Matters
- What Moves Stock Prices?
- Reading a Stock Chart
- Market Hours & Trading
- What is a Limit Order?

#### Progress Tracker (Gamification - Light)

```
┌─────────────────────────────────────────────────────────────────┐
│  🎯 YOUR PROGRESS                                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ✅ Completed onboarding                                       │
│  ✅ Viewed your first stock                                    │
│  ✅ Read a score breakdown                                     │
│  ⬜ Made your first paper trade                                │
│  ⬜ Built a watchlist                                          │
│  ⬜ Held a position for 1 week                                 │
│                                                                 │
│  Progress: ████████░░░░░░░░ 50%                                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### Portfolio Size Recommendations (Reference)

| Portfolio Size | # of Stocks | Max per Stock | Min Sectors |
|----------------|-------------|---------------|-------------|
| < $5,000 | 3-5 | 25% | 2 |
| $5K - $10K | 5-8 | 15% | 3 |
| $10K - $25K | 8-12 | 12% | 4 |
| $25K - $50K | 10-15 | 10% | 5 |
| $50K - $100K | 12-20 | 8% | 6 |
| > $100K | 15-25 | 5% | 7+ |

#### Onboarding Implementation Priority

| Feature | Priority | Phase |
|---------|----------|-------|
| First-launch tutorial (4 screens) | P2 | Week 23-24 |
| Contextual tooltips | P2 | Week 24-25 |
| Education cards | P3 | Week 26+ |
| Portfolio builder wizard | P3 | Week 27+ |
| Progress tracker | P3 | Week 28+ |

**Key principle:** Onboarding should be skippable but valuable. Never block the user from using the app.

#### 🧪 Phase 7 Testing (Per Feature)
Each new feature requires:
- Unit tests for new logic
- UI tests for new screens
- Regression tests (MVP still works)
- **Live trading requires security audit before launch**

---

### 🧪 Testing Summary

#### Test Types by Phase

| Phase | Unit Tests | UI Tests | Integration | Acceptance |
|-------|------------|----------|-------------|------------|
| **1** | ✅ Pipeline, API | — | ✅ Full pipeline | — |
| **2** | ✅ ViewModels | ✅ Screens | ✅ Backend ↔ iOS | — |
| **3** | ✅ Scoring | — | — | Sanity check |
| **4** | ✅ Trading | ✅ Order flow | ✅ Full trade E2E | — |
| **5** | Regression | Regression | Regression | ✅ **MVP Checklist** |
| **6** | ✅ ML models | — | ✅ Backtest | — |

#### When to Run Tests

| Trigger | What to Run |
|---------|-------------|
| Every commit | Unit tests (fast) |
| Every PR | Unit + UI tests |
| Before merge | Full test suite |
| Weekly (Sunday) | Integration + pipeline test |
| Before release | Full regression + acceptance |

#### Test Coverage Targets

| Component | Target Coverage |
|-----------|-----------------|
| Data pipeline | 90%+ |
| API endpoints | 90%+ |
| Score calculations | 100% |
| iOS ViewModels | 80%+ |
| iOS UI flows | All critical paths |

---

### Success Metrics by Phase

| Phase | Key Metrics | Target |
|-------|-------------|--------|
| **Phase 1** | Pipeline success rate | 100% |
| **Phase 2** | App crash rate | 0% |
| **Phase 2** | UI frame rate | 60fps |
| **Phase 3** | Score sanity check | Pass manual review |
| **Phase 4** | Order success rate | >99% |
| **Phase 5** | User-reported bugs | <5 |
| **Phase 6** | Model IC | >0.05 |
| **Phase 6** | Backtest Sharpe | >1.0 |

---

### Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Pipeline fails on Sunday | Retry logic + Slack alerts + manual fallback |
| IBKR API changes | Abstract API layer, easy to swap |
| Model performs poorly | V1 is simple and explainable, easy to defend |
| App Store rejection | Follow all guidelines, no guaranteed returns claims |
| Data quality issues | Validation layer catches anomalies early |

---

## References & Resources

> 📚 **Full Academic References:** See [papers/REFERENCES.md](papers/REFERENCES.md) for complete citations with DOIs and abstracts.

---

### Complete Availability Matrix

#### Data Sources
| Resource | Availability | Free Tier | Link |
|----------|--------------|-----------|------|
| Interactive Brokers API | ✅ FREE | Unlimited (with account) | [interactivebrokers.com](https://www.interactivebrokers.com/en/trading/ib-api.php) |
| Yahoo Finance (yfinance) | ✅ FREE | Unlimited | [github.com/ranaroussi/yfinance](https://github.com/ranaroussi/yfinance) |
| Financial Modeling Prep | 🆓 FREE TIER | 250 req/day | [financialmodelingprep.com](https://financialmodelingprep.com/) |
| FRED Economic Data | ✅ FREE | Unlimited | [fred.stlouisfed.org](https://fred.stlouisfed.org/) |
| SEC EDGAR | ✅ FREE | Unlimited | [sec.gov/edgar](https://www.sec.gov/edgar/searchedgar/companysearch) |
| Alpha Vantage | 🆓 FREE TIER | 500 req/day | [alphavantage.co](https://www.alphavantage.co/) |
| Polygon.io | 🆓 FREE TIER | 5 req/min | [polygon.io](https://polygon.io/) |
| NewsAPI | ⚠️ DEV ONLY | 100 req/day (not for prod) | [newsapi.org](https://newsapi.org/) |
| Benzinga | 💰 PAID | None | [benzinga.com](https://www.benzinga.com/apis/) |
| Twitter/X API | 💰 PAID | None | [developer.twitter.com](https://developer.twitter.com/) |

#### ML Models
| Model | Availability | License | Link |
|-------|--------------|---------|------|
| FinBERT (ProsusAI) | ✅ FREE | Apache 2.0 | [huggingface.co/ProsusAI/finbert](https://huggingface.co/ProsusAI/finbert) |
| FinancialBERT | ✅ FREE | MIT | [huggingface.co/ahmedrachid/FinancialBERT](https://huggingface.co/ahmedrachid/FinancialBERT-Sentiment-Analysis) |
| DistilRoBERTa-Financial | ✅ FREE | MIT | [huggingface.co/mrm8488/distilroberta](https://huggingface.co/mrm8488/distilroberta-finetuned-financial-news-sentiment-analysis) |
| FinBERT-Tone | ✅ FREE | Apache 2.0 | [huggingface.co/yiyanghkust/finbert-tone](https://huggingface.co/yiyanghkust/finbert-tone) |
| FinGPT | ✅ FREE | Apache 2.0 | [github.com/AI4Finance-Foundation/FinGPT](https://github.com/AI4Finance-Foundation/FinGPT) |
| BloombergGPT | ❌ NOT AVAILABLE | Proprietary | Paper only: [arxiv.org/abs/2303.17564](https://arxiv.org/abs/2303.17564) |

#### Libraries & Frameworks
| Library | Availability | License | Link |
|---------|--------------|---------|------|
| Hugging Face Transformers | ✅ FREE | Apache 2.0 | [huggingface.co/transformers](https://huggingface.co/transformers) |
| XGBoost | ✅ FREE | Apache 2.0 | [xgboost.readthedocs.io](https://xgboost.readthedocs.io/) |
| hmmlearn | ✅ FREE | BSD | [github.com/hmmlearn](https://github.com/hmmlearn/hmmlearn) |
| VectorBT | ✅ FREE | GPL-3.0 | [github.com/polakowo/vectorbt](https://github.com/polakowo/vectorbt) |
| PyFolio | ✅ FREE | Apache 2.0 | [github.com/quantopian/pyfolio](https://github.com/quantopian/pyfolio) |
| Zipline | ✅ FREE | Apache 2.0 | [github.com/quantopian/zipline](https://github.com/quantopian/zipline) |
| FastAPI | ✅ FREE | MIT | [fastapi.tiangolo.com](https://fastapi.tiangolo.com/) |
| SwiftUI | ✅ FREE | Apple | [developer.apple.com](https://developer.apple.com/xcode/swiftui/) |
| PostgreSQL | ✅ FREE | PostgreSQL | [postgresql.org](https://www.postgresql.org/) |
| Redis | ✅ FREE | BSD | [redis.io](https://redis.io/) |

---

### Key Academic Papers (Research Only)

> ⚠️ These are **research papers** — they describe methods, not always usable models.

#### Multi-Factor Ranking Model
- Fama & French (1993) — *Three-Factor Model* — foundational
- Carhart (1997) — *Four-Factor Model* — added momentum
- Fama & French (2015) — *Five-Factor Model* — added profitability & investment

#### Sentiment Analysis
- Araci (2019) — *FinBERT* — model is FREE ✅
- Yang et al. (2023) — *FinGPT* — model is FREE ✅
- ~~Wu et al. (2023) — *BloombergGPT*~~ — **paper only, model NOT available** ❌

#### Other Foundations
- Hamilton (1989) — *Regime Switching* — use hmmlearn ✅
- Kelly (1956) — *Kelly Criterion* — implement yourself ✅
- López de Prado (2018) — *Advances in Financial ML* — book 💰

### Research Paper Links
1. **FinBERT:** https://arxiv.org/abs/1908.10063 (model available ✅)
2. **FinGPT:** https://arxiv.org/abs/2306.06031 (model available ✅)
3. **BloombergGPT:** https://arxiv.org/abs/2303.17564 (paper only ❌)
4. **FinRL:** https://github.com/AI4Finance-Foundation/FinRL (code available ✅)

### Books & Courses
| Resource | Cost | Notes |
|----------|------|-------|
| "Advances in Financial ML" - López de Prado | 💰 ~$50 | Highly recommended |
| "ML for Asset Managers" - López de Prado | 💰 ~$40 | Shorter, focused |
| IBKR Traders' Academy | ✅ FREE | [interactivebrokers.com/campus](https://www.interactivebrokers.com/campus/traders-academy/api/) |
| Coursera ML Course | 🆓 FREE (audit) | Andrew Ng's classic |
| Fast.ai | ✅ FREE | Practical deep learning |

---

## Appendix: S&P500 Stocks >$10B (Sample)

Top 50 by Market Cap (as of Feb 2026):
| Ticker | Company | Sector | Market Cap |
|--------|---------|--------|------------|
| AAPL | Apple Inc. | Technology | $3.0T |
| MSFT | Microsoft Corp. | Technology | $2.8T |
| GOOGL | Alphabet Inc. | Communication | $1.9T |
| AMZN | Amazon.com Inc. | Consumer Disc. | $1.8T |
| NVDA | NVIDIA Corp. | Technology | $1.5T |
| META | Meta Platforms | Communication | $1.2T |
| TSLA | Tesla Inc. | Consumer Disc. | $800B |
| BRK.B | Berkshire Hathaway | Financials | $780B |
| ... | ... | ... | ... |

*(Full list maintained in data pipeline)*

---

**Report Status:** Complete  
**Next Steps:** Create Linear tasks, begin implementation  
**Contact:** Blaze Neon (via OpenClaw)
