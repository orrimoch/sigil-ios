<img src="sigil_logo.jpg" alt="Sigil" width="240" />

# Crowd Wisdom: Reddit Viral Stocks Pivot

**Linear Ticket:** REC-266  
**Date:** 2026-02-13  
**Status:** Planning

---

## Executive Summary

Or has decided to pivot the Crowd Wisdom module from insider buying data (OpenInsider / 13F filings) to **Reddit-based viral stock detection**. This approach is inspired by the Teletraan implementation ([barkain.github.io/teletraan](https://barkain.github.io/teletraan)).

---

## Teletraan Reference Analysis

### What It Does
Teletraan is a full-stack AI market analysis platform that includes Reddit sentiment tracking as one of its data sources. From the latest reports:

- **Subreddits Tracked:** r/wallstreetbets, r/stocks, r/investing
- **Data Points Collected:**
  - Total mentions across all subreddits (e.g., 4,317 mentions across 50 trending tickers)
  - Per-ticker: mention count, upvote count, trending rank
  - Example: "NVDA: 132 mentions, 318 upvotes, ranked #9 trending"
- **Top Trending Display:** SPY (515), MU (398), MSFT (352), HOOD (254), RDDT (197), ASTS (149), NBIS (144), QQQ (137)
- **Sentiment Classification:** Very Bullish / Bullish / Neutral / Bearish / Very Bearish
- **Caveat Shown:** "Sentiment can lag institutional positioning by hours to days"

### Technical Stack (from GitHub)
- **Backend:** Python 3.11+, FastAPI, SQLAlchemy, Claude Agent SDK
- **Data Sources:** Yahoo Finance (prices), FRED API (macro), Finnhub, Reddit
- **Reddit Integration:** Likely using PRAW (Python Reddit API Wrapper) or similar

---

## New Crowd Wisdom Requirements

### Data Sources
| Priority | Subreddit | Signal Strength |
|----------|-----------|-----------------|
| Primary | r/wallstreetbets | Highest volume, strongest retail signal |
| Secondary | r/stocks | More measured discussion |
| Secondary | r/investing | Long-term focused |
| Optional | r/options | Options flow signals |

### Metrics to Track
- **Mention Count:** Number of times ticker appears in posts/comments
- **Upvote Count:** Total upvotes on posts mentioning the ticker
- **Comment Engagement:** Total comments discussing the ticker
- **Sentiment Score:** Bullish/Neutral/Bearish via LLM analysis
- **Trending Velocity:** Rate of mention increase (momentum)

### Quality Filters (MUST PASS ALL)
The key differentiator from pure meme stock tracking:

1. **Substantial Revenue** — Real business with actual revenue (not pre-revenue speculation)
2. **Strong Recent Earnings** — Positive EPS or improving trajectory over last 2-3 quarters

### Scoring Methodology
```
viral_score = (
  mention_count_normalized * 0.30 +
  upvote_weighted_score   * 0.20 +
  sentiment_score         * 0.20 +
  trending_velocity       * 0.15 +
  fundamentals_bonus      * 0.15
)
```

Where:
- `mention_count_normalized` = mentions / max_mentions in period
- `upvote_weighted_score` = upvotes weighted by recency
- `sentiment_score` = LLM-derived sentiment (0-1 scale)
- `trending_velocity` = mentions_today / mentions_yesterday
- `fundamentals_bonus` = bonus for earnings beats, revenue growth, analyst upgrades

---

## Implementation Plan

### Phase 1: Data Collection (Backend)

#### New Files
```
backend/
├── data/
│   └── reddit_fetcher.py     # Reddit API integration
├── models/
│   ├── reddit_mention.py     # Reddit mention ORM model
│   └── reddit_viral_score.py # Aggregated scores ORM model
├── services/
│   └── reddit_scoring.py     # Viral score calculation
```

#### Schema: `reddit_mentions` Table
```sql
CREATE TABLE reddit_mentions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ticker VARCHAR(10) NOT NULL,
  subreddit VARCHAR(50) NOT NULL,
  post_id VARCHAR(20) UNIQUE,
  post_title TEXT,
  post_body TEXT,
  upvotes INTEGER DEFAULT 0,
  comments INTEGER DEFAULT 0,
  sentiment VARCHAR(10),  -- bullish/neutral/bearish
  sentiment_score FLOAT,  -- 0.0 to 1.0
  post_created_at TIMESTAMP,
  fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_reddit_ticker ON reddit_mentions(ticker);
CREATE INDEX idx_reddit_created ON reddit_mentions(post_created_at);
```

#### Schema: `reddit_viral_scores` Table
```sql
CREATE TABLE reddit_viral_scores (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ticker VARCHAR(10) NOT NULL,
  week_start DATE NOT NULL,
  mention_count INTEGER DEFAULT 0,
  total_upvotes INTEGER DEFAULT 0,
  total_comments INTEGER DEFAULT 0,
  avg_sentiment FLOAT,
  trending_velocity FLOAT,
  viral_score FLOAT,
  -- Filter criteria results
  current_price FLOAT,
  revenue_ttm FLOAT,
  eps_latest FLOAT,
  passes_filters BOOLEAN DEFAULT FALSE,
  filter_reason TEXT,  -- If fails, why?
  -- Timestamps
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(ticker, week_start)
);
```

### Phase 2: API Endpoints

```python
# GET /api/v1/crowd-wisdom/picks
# Returns top 5 viral stocks that pass all filters
{
  "picks": [
    {
      "ticker": "NVDA",
      "viral_score": 87.5,
      "mention_count": 132,
      "total_upvotes": 318,
      "sentiment": "bullish",
      "price": 190.00,
      "revenue_ttm": 60000000000,
      "eps_latest": 0.65
    }
  ],
  "generated_at": "2026-02-13T00:00:00Z",
  "week_start": "2026-02-09"
}

# GET /api/v1/crowd-wisdom/trending
# All trending tickers with scores (unfiltered)

# GET /api/v1/stocks/{ticker}/crowd-wisdom
# Per-stock Reddit data
{
  "ticker": "NVDA",
  "mention_count": 132,
  "upvotes": 318,
  "sentiment": "bullish",
  "trending_rank": 9,
  "recent_posts": [...]
}
```

### Phase 3: iOS Integration

- **Keep existing UI:** `SmartMoneyPicksSection` component stays
- **Update model:** Decode new Reddit-based response
- **Badge change:** "🔥 Trending" instead of "Smart Money"
- **Stock Detail:** Add Reddit Sentiment subsection

### Phase 4: Cron Job

Weekly job (Sunday night):
1. Fetch last 7 days of Reddit posts from target subreddits
2. Extract and validate ticker mentions
3. Compute viral scores for each ticker
4. Apply quality filters
5. Store top picks for the week

---

## Existing Ticket Recommendations

### CANCEL (7 tickets)
These tickets are specific to the insider buying approach and are no longer needed:

| Ticket | Title | Reason |
|--------|-------|--------|
| REC-251 | OpenInsider Data Fetcher | Deprecated approach |
| REC-252 | Insider Transactions Storage Schema | Deprecated approach |
| REC-253 | Insider Signal Scoring | Deprecated approach |
| REC-255 | Superinvestor Registry | Deprecated approach |
| REC-256 | SEC EDGAR 13F Parser | Deprecated approach |
| REC-257 | CUSIP to Ticker Mapping | Deprecated approach |
| REC-258 | Institutional Signal Scoring | Deprecated approach |

### UPDATE SCOPE (8 tickets)
These tickets are still relevant but need scope updates:

| Ticket | Title | Update Needed |
|--------|-------|---------------|
| REC-254 | Crowd Wisdom API Endpoints | Update endpoints for Reddit data |
| REC-259 | Smart Money Badge | Rename to "Viral Badge" or "Trending Badge" |
| REC-260 | Stock Detail Section | Show Reddit mentions instead of insider data |
| REC-261 | iOS Models | Update to decode Reddit response schema |
| REC-262 | Weekly Cron Job | Keep, update to use Reddit data source |
| REC-263 | Score Boost Integration | Keep as-is (still integrates with composite) |
| REC-264 | Stock Discovery | Update filter criteria (revenue, earnings) |
| REC-265 | Weekly Top 5 | Keep, update data source to Reddit |

---

## Next Steps

1. **Create sub-tickets** under REC-266 for:
   - Reddit API setup & credentials
   - reddit_fetcher.py implementation
   - Database schema migration
   - Scoring service
   - API endpoints
   - iOS model updates
   - Cron job setup

2. **Cancel deprecated tickets** (REC-251, 252, 253, 255, 256, 257, 258)

3. **Update scope** on remaining tickets

---

## Appendix: Reddit API Options

### Option A: PRAW (Python Reddit API Wrapper)
- Official Reddit API
- Requires Reddit app credentials
- Rate limited (60 requests/minute for OAuth)
- Free but may require API approval

### Option B: TradeStalk API
- Third-party aggregator
- Pre-aggregated ticker mentions
- Faster implementation
- May have cost

### Option C: Apify Reddit Scraper
- Web scraping approach
- No API limits
- More fragile

**Recommendation:** Start with PRAW for direct Reddit access. If rate limits become an issue, evaluate TradeStalk.
