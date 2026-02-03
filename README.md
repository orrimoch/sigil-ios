# TradingApp iOS

**AI-Powered Stock Recommendations for S&P 500**

---

## 📁 Project Structure

```
TradingApp_iOS/
├── README.md                    ← You are here
│
├── 01_PRD.md                    ← Product Requirements (start here)
├── 02_TECHNICAL_SPEC.md         ← Technical Specification
├── 03_DESIGN_UX_SPEC.md         ← Design & UX Specification
├── 04_ANALYTICS_PLAN.md         ← Analytics & Metrics
├── 05_FEATURE_SPEC.md           ← All Features (for Linear tickets)
│
├── design/
│   └── inspiration/
│       ├── DESIGN_INSPIRATION.md    ← Design direction & palette
│       ├── DIRECT_LINKS.md          ← Reference links to open
│       └── screenshots/             ← (save screenshots here)
│
├── papers/
│   └── REFERENCES.md            ← Academic citations
│
├── references/
│   └── resources.md             ← Quick reference links
│
└── archive/
    └── TradingApp_Report_FULL.md    ← Original 6K line doc (reference)
```

---

## 📖 Document Guide

| Doc | Purpose | Audience |
|-----|---------|----------|
| **01_PRD.md** | Problem, vision, user flows, success metrics | Product, leadership |
| **02_TECHNICAL_SPEC.md** | Architecture, APIs, data models, Docker, Git | Engineering |
| **03_DESIGN_UX_SPEC.md** | Wireframes, colors, typography, interactions | Design, eng, PM |
| **04_ANALYTICS_PLAN.md** | Events, metrics, dashboards, testing | Analytics, product |
| **05_FEATURE_SPEC.md** | All 45 features with acceptance criteria | Eng, PM, QA |

---

## 🎯 Quick Start

1. **Understand the product:** Read `01_PRD.md`
2. **Technical setup:** Read `02_TECHNICAL_SPEC.md`
3. **Design system:** Read `03_DESIGN_UX_SPEC.md`
4. **Start building:** Create Linear tickets from roadmap

---

## 🔑 Key Decisions

- **Design:** "Institutional Dark" (Bloomberg/IBKR style, NOT neon fintech)
- **Target User:** "Busy Builder" (tech professional, 30-40, 5 min/week)
- **MVP Approach:** Ranking over prediction, simple keywords over ML
- **Data Sources:** FREE only for MVP (Yahoo Finance, SEC, FRED, RSS, Alpha Vantage, Finnhub)
- **Broker:** Interactive Brokers (paper trading first)

---

## 🛠 Backend Status

### F1.x Data Pipeline — ✅ COMPLETE

| Feature | Description | Tests |
|---------|-------------|-------|
| F1.1 | Stock Universe (486 stocks) | 9 ✅ |
| F1.2 | Price Fetcher (yfinance) | 12 ✅ |
| F1.3 | Fundamental Fetcher | 14 ✅ |
| F1.4 | News Fetcher (RSS + APIs) | 22 ✅ |
| F1.5 | Macro Fetcher (FRED) | 19 ✅ |
| F1.6 | Pipeline Orchestration | 15 ✅ |

### F2.x Scoring System — ✅ COMPLETE

| Feature | Description | Tests |
|---------|-------------|-------|
| F2.1 | Fundamental Score (Value/Quality/Growth) | 4 ✅ |
| F2.2 | Sentiment Score (News + Recency) | 4 ✅ |
| F2.3 | Technical Score (RSI/Momentum/Trend) | 5 ✅ |
| F2.4 | Macro Score (Sector alignment) | 5 ✅ |
| F2.5 | Composite Score (BUY/HOLD/SELL) | 6 ✅ |
| F2.6 | Score Explainability | 4 ✅ |

**Total: 118 tests**

### Run Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn src.api.main:app --reload
```

### API Endpoints
```
# Stocks
GET /api/v1/stocks              — Stock universe
GET /api/v1/stocks/{ticker}     — Single stock

# Scores (F2.x)
GET /api/v1/scores              — All scores with signals
GET /api/v1/scores/{ticker}     — Score + explanation
GET /api/v1/scores/top/{n}      — Top N stocks
POST /api/v1/scores/calculate   — Trigger scoring

# Data
GET /api/v1/prices/{ticker}     — Latest price
GET /api/v1/fundamentals/{ticker}
GET /api/v1/news/{ticker}       — News + sentiment
GET /api/v1/macro               — Macro indicators
```

### Optional API Keys (for enhanced news)
```bash
export ALPHA_VANTAGE_API_KEY="..."  # Free: alphavantage.co
export FINNHUB_API_KEY="..."        # Free: finnhub.io
```

---

## 📋 Linear Tasks

| ID | Task | Status |
|----|------|--------|
| REC-21 | Backend Scoring Pipeline (F2.x) | Todo |
| REC-22 | iOS App Foundation | Todo |
| REC-23 | IBKR Integration | Todo |
| REC-24 | ML Model Improvements | Todo |

---

*Last updated: February 2, 2026*
