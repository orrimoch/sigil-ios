<img src="sigil_logo.jpg" alt="Sigil" width="240" />

# Sigil iOS — Technical Specification

**Project:** iOS Stock Trading App with AI-Powered Recommendations  
**Author:** Blaze Neon  
**Date:** February 2, 2026  
**Version:** 1.0  

---

## Table of Contents

1. [System Architecture](#system-architecture)
2. [Technology Stack](#technology-stack)
3. [Development Environment](#development-environment)
4. [Data Pipeline](#data-pipeline)
5. [Scoring System](#scoring-system)
6. [API Contracts](#api-contracts)
7. [Database Schema](#database-schema)
8. [Interactive Brokers Integration](#interactive-brokers-integration)
9. [Security & Compliance](#security--compliance)
10. [Performance Requirements](#performance-requirements)

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
│  │ Interactive  │  │  Financial   │  │  News RSS Feeds            ││
│  │ Brokers API  │  │  Data APIs   │  │  (Yahoo, Reuters, SEC)     ││
│  └──────────────┘  └──────────────┘  └────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
```

### Microservice Responsibilities

| Service | Responsibility |
|---------|---------------|
| **Scoring Service** | Calculate and store weekly stock scores |
| **Data Service** | Fetch and normalize external data |
| **Trading Service** | Execute orders via IBKR, track positions |
| **Notification Service** | Push notifications, alerts |

---

## Technology Stack

| Layer | Technology | Rationale |
|-------|------------|-----------|
| **iOS App** | Swift, SwiftUI | Native performance, modern UI |
| **Backend API** | Python 3.11, FastAPI | ML ecosystem, async support |
| **Database** | PostgreSQL 15 | ACID compliance, JSON support |
| **Cache** | Redis 7 | Fast lookups, pub/sub |
| **Time Series** | TimescaleDB | Efficient price history |
| **ML/Scoring** | scikit-learn, pandas | Simple, fast, reliable |
| **Message Queue** | Redis Pub/Sub | Simple, sufficient for scale |
| **CI/CD** | GitHub Actions | Integrated, free tier |
| **Monitoring** | Prometheus + Grafana | Industry standard |
| **Cloud** | AWS or GCP | Flexible, scalable |

---

## Development Environment

### Project Structure

```
sigil/
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
│   ├── Sigil/
│   │   ├── Views/
│   │   ├── ViewModels/
│   │   ├── Models/
│   │   ├── Services/
│   │   └── Resources/
│   ├── SigilTests/
│   ├── SigilUITests/
│   └── Sigil.xcodeproj
│
├── shared/                     # Shared contracts
│   ├── api-spec/              # OpenAPI/Swagger specs
│   └── schemas/               # JSON schemas for validation
│
└── docker-compose.yml          # Full stack orchestration
```

### Docker Configuration

**docker-compose.yml:**
```yaml
version: '3.8'

services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/sigil
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
      POSTGRES_DB: sigil
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

volumes:
  postgres_data:
```

### Git Branching Strategy

**Branch Naming:**
```
<type>/<ticket>-<short-description>

Types: feat/, fix/, refactor/, test/, docs/, chore/
```

**Examples:**
```
feat/REC-21-scoring-pipeline
fix/REC-45-price-rounding-error
test/REC-21-scoring-unit-tests
```

**Workflow:**
1. Create branch from master
2. Work + commit often (conventional commits)
3. Push + create PR
4. Merge to master when complete
5. Delete branch

**Commit Format:**
```
<type>(<scope>): <short description>

feat(scoring): implement composite score calculation
fix(api): handle missing earnings data gracefully
```

### Test Suites

| Layer | Test Type | Tool | Command |
|-------|-----------|------|---------|
| Backend | Unit | pytest | `pytest tests/unit` |
| Backend | Integration | pytest + testcontainers | `pytest tests/integration` |
| Backend | E2E | pytest + httpx | `pytest tests/e2e` |
| iOS | Unit | XCTest | `xcodebuild test -scheme Sigil` |
| iOS | UI | XCUITest | `xcodebuild test -scheme SigilUITests` |

---

## Data Pipeline

### Data Sources (MVP — FREE Only)

| Source | Data Type | Update Frequency | API |
|--------|-----------|------------------|-----|
| **Yahoo Finance** | Prices, fundamentals | Daily | `yfinance` library |
| **SEC EDGAR** | 10-K, 10-Q, 8-K filings | As filed | REST API |
| **FRED** | Macro indicators | Varies | REST API |
| **RSS Feeds** | News headlines | Real-time | feedparser |

### News Sources (MVP)

```python
# RSS Feeds (always free, no API key)
NEWS_RSS_FEEDS = {
    'yahoo_finance': 'https://finance.yahoo.com/news/rssindex',
    'reuters': 'https://www.reutersagency.com/feed/',
    'marketwatch': 'https://www.marketwatch.com/rss/topstories',
    'sec_filings': 'https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&output=atom',
}

# API Sources (optional, free tier available)
# Set env vars: ALPHA_VANTAGE_API_KEY, FINNHUB_API_KEY
NEWS_APIS = {
    'alpha_vantage': 'https://www.alphavantage.co/query?function=NEWS_SENTIMENT',
    'finnhub': 'https://finnhub.io/api/v1/news',
}

# Source tier weights (per PRD)
SOURCE_TIERS = {
    'wsj': 3, 'ft': 3, 'economist': 3,           # Tier 1 (future)
    'reuters': 2, 'alpha_vantage': 2, 'finnhub': 2,  # Tier 2
    'yahoo_finance': 1, 'marketwatch': 1,        # Tier 3
}
```

### Pipeline Schedule

```
┌─────────────────────────────────────────────────────────────────────┐
│  WEEKLY PIPELINE (Sundays 6pm EST, after market close)             │
├─────────────────────────────────────────────────────────────────────┤
│  1. Fetch price data (all ~800 stocks)             ~10 min         │
│  2. Fetch fundamentals (quarterly, cached)         ~2 min          │
│  3. Fetch macro indicators                         ~1 min          │
│  4. Fetch news (last 7 days)                       ~3 min          │
│  5. Calculate sentiment scores                     ~5 min          │
│  6. Calculate composite scores                     ~2 min          │
│  7. Store results, trigger notifications           ~1 min          │
│                                                    ───────          │
│  Total: ~20 minutes                                                │
└─────────────────────────────────────────────────────────────────────┘
```

### Data Models

```python
@dataclass
class StockData:
    ticker: str
    date: date
    price: float
    volume: int
    market_cap: float
    pe_ratio: float
    eps: float
    revenue_growth: float
    profit_margin: float
    debt_to_equity: float
    sector: str

@dataclass
class SentimentData:
    ticker: str
    date: date
    news_sentiment: float      # -1 to 1
    article_count: int
    sources: List[str]

@dataclass
class MacroData:
    date: date
    fed_rate: float
    inflation_yoy: float
    gdp_growth: float
    unemployment: float
    vix: float
    sp500_level: float
```

---

## Scoring System

### Core Philosophy

> **"Rank, don't predict."** — Time series prediction is noisy; relative ranking is more robust.

### Composite Score Formula

```python
def calculate_composite_score(stock_data):
    # Each component normalized to 0-100 via percentile ranking
    
    fundamental_score = (
        0.25 * value_score +       # P/E, P/B ratios
        0.35 * quality_score +     # ROE, margins, debt
        0.40 * growth_score        # Revenue/EPS growth
    )
    
    sentiment_score = (
        0.60 * news_sentiment +    # Keyword-based
        0.40 * earnings_sentiment  # Earnings call tone
    )
    
    macro_score = sector_macro_alignment(sector, current_regime)
    
    technical_score = (
        0.40 * momentum_score +    # Price momentum
        0.30 * relative_strength + # RSI
        0.30 * trend_score         # MA crossovers
    )
    
    # Final composite
    composite = (
        0.35 * fundamental_score +
        0.25 * sentiment_score +
        0.20 * macro_score +
        0.20 * technical_score
    )
    
    return composite  # 0-100
```

### Signal Generation

| Score Range | Signal | Action |
|-------------|--------|--------|
| 70-100 | 🟢 BUY | Strong candidate for entry |
| 40-69 | 🟡 HOLD | Mixed signals, wait |
| 0-39 | 🔴 SELL | Consider exit |

### Data Preprocessing: Bucketing

> For continuous variables, use efficient bucketing to reduce noise.

```python
def bucket_continuous(values: pd.Series, n_buckets: int = 10) -> pd.Series:
    """Convert continuous values to discrete buckets (deciles)."""
    return pd.qcut(values, q=n_buckets, labels=False, duplicates='drop')

# Example: P/E ratios bucketed into deciles
df['pe_bucket'] = bucket_continuous(df['pe_ratio'], n_buckets=10)
```

---

## API Contracts

### Base URL
- Dev: `http://localhost:8000/api/v1`
- Prod: `https://api.sigil.com/v1`

### Endpoints

#### Scores
```
GET /scores
  Query: ?sector=Technology&signal=buy&limit=50
  Response: { "scores": [{ "ticker": "AAPL", "score": 85, "signal": "buy", ... }] }

GET /scores/{ticker}
  Response: { "ticker": "AAPL", "score": 85, "breakdown": { "fundamental": 88, ... } }

GET /scores/{ticker}/history
  Query: ?weeks=12
  Response: { "history": [{ "date": "2026-01-26", "score": 82 }, ...] }
```

#### Portfolio
```
GET /portfolio
  Response: { "positions": [...], "total_value": 125000, "daily_pnl": 1234 }

GET /portfolio/performance
  Query: ?period=1m
  Response: { "returns": [...], "benchmark": [...] }
```

#### Trading
```
POST /orders
  Body: { "ticker": "AAPL", "quantity": 10, "order_type": "market" }
  Response: { "order_id": "123", "status": "pending" }

GET /orders/{order_id}
  Response: { "order_id": "123", "status": "filled", "fill_price": 185.50 }
```

### Response Format

```json
{
  "success": true,
  "data": { ... },
  "meta": {
    "timestamp": "2026-02-02T12:00:00Z",
    "version": "1.0"
  }
}
```

### Error Format

```json
{
  "success": false,
  "error": {
    "code": "INVALID_TICKER",
    "message": "Ticker XYZ not found in universe"
  }
}
```

---

## Database Schema

### Core Tables

```sql
-- Stock universe
CREATE TABLE stocks (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    sector VARCHAR(100),
    market_cap BIGINT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Weekly scores
CREATE TABLE scores (
    id SERIAL PRIMARY KEY,
    stock_id INTEGER REFERENCES stocks(id),
    score_date DATE NOT NULL,
    composite_score DECIMAL(5,2),
    fundamental_score DECIMAL(5,2),
    sentiment_score DECIMAL(5,2),
    macro_score DECIMAL(5,2),
    technical_score DECIMAL(5,2),
    signal VARCHAR(10),  -- 'buy', 'hold', 'sell'
    explanation JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(stock_id, score_date)
);

-- User portfolios
CREATE TABLE portfolios (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    is_paper BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Portfolio positions
CREATE TABLE positions (
    id SERIAL PRIMARY KEY,
    portfolio_id INTEGER REFERENCES portfolios(id),
    stock_id INTEGER REFERENCES stocks(id),
    quantity DECIMAL(15,4),
    avg_cost DECIMAL(15,4),
    opened_at TIMESTAMP,
    closed_at TIMESTAMP,
    UNIQUE(portfolio_id, stock_id)
);

-- Orders
CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    portfolio_id INTEGER REFERENCES portfolios(id),
    stock_id INTEGER REFERENCES stocks(id),
    order_type VARCHAR(20),  -- 'market', 'limit'
    side VARCHAR(10),        -- 'buy', 'sell'
    quantity DECIMAL(15,4),
    limit_price DECIMAL(15,4),
    status VARCHAR(20),      -- 'pending', 'filled', 'cancelled'
    ibkr_order_id VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW(),
    filled_at TIMESTAMP,
    fill_price DECIMAL(15,4)
);

-- Price history (TimescaleDB hypertable)
CREATE TABLE prices (
    time TIMESTAMPTZ NOT NULL,
    stock_id INTEGER REFERENCES stocks(id),
    open DECIMAL(15,4),
    high DECIMAL(15,4),
    low DECIMAL(15,4),
    close DECIMAL(15,4),
    volume BIGINT
);
SELECT create_hypertable('prices', 'time');
```

---

## Interactive Brokers Integration

### API Choice
**Web API (REST + WebSocket)** — Modern, OAuth2 auth, suitable for mobile.

### Authentication Flow
1. User taps "Connect IBKR"
2. Opens IBKR OAuth2 login page
3. User authenticates
4. App receives access token
5. Token stored in iOS Keychain
6. Refresh token used for session extension

### Key Endpoints

```
# Market Data
GET /v1/api/iserver/marketdata/snapshot?conids=265598
GET /v1/api/iserver/marketdata/history?conid=265598&period=1m

# Orders
POST /v1/api/iserver/account/{accountId}/orders
GET /v1/api/iserver/account/{accountId}/orders
DELETE /v1/api/iserver/account/{accountId}/order/{orderId}

# Portfolio
GET /v1/api/portfolio/{accountId}/positions
GET /v1/api/portfolio/accounts
```

### Paper vs Live Trading

| Mode | Account Type | Risk | Toggle |
|------|--------------|------|--------|
| Paper | Separate IBKR paper account | Zero | Default |
| Live | Real IBKR account | Real money | User must explicitly enable |

---

## Security & Compliance

### Data Security

| Layer | Protection |
|-------|------------|
| Transport | TLS 1.3 |
| Storage (iOS) | iOS Keychain for tokens |
| Storage (Backend) | AES-256 encryption at rest |
| Authentication | OAuth2 + biometric (Face ID/Touch ID) |
| Sessions | JWT, 1-hour expiry |

### Compliance

| Regulation | Requirement | Implementation |
|------------|-------------|----------------|
| SEC | No insider trading, clear disclosures | Disclaimer screens |
| App Store | Financial app guidelines | Proper categorization |
| GDPR/CCPA | Data privacy | Privacy policy, deletion API |

### Required Disclosures
- "Not financial advice"
- "Past performance ≠ future results"
- "Risk of loss"
- "IBKR is executing broker"

---

## Performance Requirements

| Metric | Target |
|--------|--------|
| API Response Time (p95) | < 200ms |
| Score Calculation (all 400) | < 5 minutes |
| App Launch Time | < 2 seconds |
| Dashboard Load | < 1 second |
| Order Submission | < 500ms |

### Caching Strategy

| Data | Cache Duration | Location |
|------|----------------|----------|
| Stock scores | 1 week | Redis + App |
| Price quotes | 1 minute | Redis |
| Portfolio | 30 seconds | Redis |
| User settings | Until changed | App |

---

**Related Docs:**
- `01_PRD.md` — Product requirements, vision, user flows
- `03_DESIGN_UX_SPEC.md` — Wireframes, colors, interactions
- `04_ANALYTICS_PLAN.md` — Metrics, events, dashboards
- `05_FEATURE_SPEC.md` — All 45 features with acceptance criteria
