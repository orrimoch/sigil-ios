<img src="docs/sigil_logo.jpg" alt="Sigil" width="240" />

# Sigil — AI Stock Intelligence

**Explainable BUY / HOLD / SELL signals for the S&P 500, delivered to an iOS app.**

Sigil scores ~486 US equities from four independent angles — fundamentals, news
sentiment, technicals, and macro alignment — combines them into a single signal,
and shows *why* it reached that conclusion. A SwiftUI client presents the
ranking; a FastAPI backend does the work.

Built for the "busy builder": someone technical who wants a defensible weekly
read on the market in five minutes, not a day-trading terminal.

---

## Why it exists

Retail stock tools tend to sit at two extremes: opaque black-box "AI picks" with
no reasoning, or raw screeners that hand you 40 columns and no opinion.

Sigil takes a deliberate middle position:

- **Ranking, not prediction.** It does not forecast prices. It ranks the universe
  on evidence available today, which is a far more honest problem.
- **Every score is explainable.** Each signal decomposes into the factors that
  produced it, so you can disagree with the reasoning rather than the number.
- **Free data only.** Yahoo Finance, SEC filings, FRED, RSS feeds, Alpha Vantage
  and Finnhub free tiers — no paid market-data dependency.

---

## Architecture

```
┌─────────────────┐        ┌──────────────────────────────────┐
│  iOS (SwiftUI)  │ ─────▶ │  FastAPI  /api/v1                │
│  85 Swift files │  REST  │                                  │
└─────────────────┘        │  scoring/     4-factor composite │
                           │  sentiment/   news + recency     │
                           │  backtest/    historical harness │
                           │  crowd_wisdom/ aggregate signal  │
                           │  agent/ llm/  LLM analysis       │
                           │  ibkr/ trading/ risk/  execution │
                           │  scheduler/   periodic refresh   │
                           └───────────────┬──────────────────┘
                                           │
                              PostgreSQL + Redis
                                           │
              Yahoo Finance · SEC · FRED · RSS · Alpha Vantage · Finnhub
```

**Backend** — Python, FastAPI, SQLAlchemy, Alembic, Redis, pandas, scikit-learn.
21 modules under `backend/src/`, 78 test modules under `backend/tests/`.

**iOS** — SwiftUI, Xcode project at `ios/TradingApp/TradingApp.xcodeproj`.
Design direction is "Institutional Dark" — Bloomberg/IBKR restraint rather than
neon fintech.

**Infrastructure** — Docker Compose for local, Railway for deploy.

---

## The scoring model

| Factor | Inputs | Question it answers |
|---|---|---|
| **Fundamental** | Value, quality, growth from SEC filings | Is the business sound and fairly priced? |
| **Sentiment** | News and RSS, weighted by recency | What is the market being told right now? |
| **Technical** | RSI, momentum, trend | What is price action doing? |
| **Macro** | FRED indicators, sector alignment | Is this sector positioned for the regime? |

The four combine into a composite BUY / HOLD / SELL, and every score carries an
explanation of the factors that drove it.

Beyond the core model, the repo includes a **backtesting harness** over stored
historical scores, a **crowd-wisdom** aggregate signal, LLM-assisted sentiment
analysis, and Interactive Brokers integration for paper trading.

---

## Running it

**Docker (recommended):**
```bash
cd backend
cp .env.example .env      # then fill in your keys
docker compose up
```

**Direct:**
```bash
cd backend
pip install -r requirements.txt
uvicorn src.api.main:app --reload
```

**iOS:** open `ios/TradingApp/TradingApp.xcodeproj` in Xcode and run.

**Tests:**
```bash
cd backend && pytest
```

### API keys

All optional — the app degrades gracefully without them, using free sources only.

```bash
ALPHA_VANTAGE_API_KEY=...   # free tier: alphavantage.co
FINNHUB_API_KEY=...         # free tier: finnhub.io
```

See `backend/.env.example` for the full list. **Never commit a filled-in `.env`.**

---

## Selected endpoints

```
GET  /api/v1/stocks               Stock universe
GET  /api/v1/stocks/{ticker}      Single stock
GET  /api/v1/scores               All scores with signals
GET  /api/v1/scores/{ticker}      Score plus explanation
GET  /api/v1/scores/top/{n}       Top N ranked
POST /api/v1/scores/calculate     Trigger a scoring run
GET  /api/v1/news/{ticker}        News with sentiment
GET  /api/v1/macro                Macro indicators
```

---

## Repository layout

```
backend/       FastAPI service — scoring, sentiment, backtesting, trading
ios/           SwiftUI client (Xcode project)
analysis/      Research notebooks and exploratory analysis
backtesting/   Backtest configurations and outputs
docs/          Product, technical, design, and feature specifications
infra/         Deployment configuration
scripts/       Operational tooling
```

`docs/` holds the full written record — PRD, technical spec, UX spec, analytics
plan, and per-feature specs for backtesting, crowd wisdom, sentiment, and sector
analysis. Start with `docs/01_PRD.md` for the product argument and
`docs/02_TECHNICAL_SPEC.md` for the system design.

---

## Status

Working system, actively developed. The data pipeline and four-factor scoring
model are complete and tested; the iOS client, backtesting harness, and broker
integration are functional and evolving.

This is a personal project — the trading logic is research, not investment
advice.
