"""
REC-264: Stock Discovery for Cheap Tech

Identifies trending stocks outside our universe that meet criteria:
- Tech sector (or related)
- Price < $30
- Market cap $500M - $50B

Max 10 additions per quarter to prevent universe bloat.
"""

import json
import logging
from datetime import datetime, date
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass
import yfinance as yf

logger = logging.getLogger(__name__)

# Discovery filters
DISCOVERY_FILTERS = {
    "max_price": 30.0,
    "min_market_cap": 500_000_000,      # $500M
    "max_market_cap": 50_000_000_000,   # $50B
    "sectors": ["Technology", "Communication Services", "Consumer Discretionary"],
    "min_viral_score": 50,              # Minimum Reddit viral score
    "max_quarterly_additions": 10,
}

# Storage path
DATA_DIR = Path(__file__).parent.parent.parent / "data"
DISCOVERY_FILE = DATA_DIR / "discovery_candidates.json"
QUARTERLY_LOG = DATA_DIR / "discovery_quarterly_log.json"


@dataclass
class DiscoveryCandidate:
    """Stock discovered via crowd wisdom that's not in our universe."""
    ticker: str
    company_name: str
    sector: str
    
    # Price data
    current_price: float
    market_cap: float
    
    # Crowd wisdom metrics
    viral_score: float
    mention_count: int
    total_upvotes: int
    sentiment_label: str
    
    # Discovery metadata
    discovered_at: str
    source: str  # "reddit"
    
    # Filter results
    passes_filters: bool
    filter_reasons: List[str]
    
    # Review status
    reviewed: bool = False
    approved: bool = False
    added_to_universe: bool = False


def check_discovery_filters(
    ticker: str,
    price: float,
    market_cap: float,
    sector: str,
    viral_score: float,
) -> tuple[bool, List[str]]:
    """
    Check if a stock passes discovery filters.
    
    Returns: (passes, list of reasons if fails)
    """
    reasons = []
    
    if price > DISCOVERY_FILTERS["max_price"]:
        reasons.append(f"Price ${price:.2f} > ${DISCOVERY_FILTERS['max_price']}")
    
    if market_cap < DISCOVERY_FILTERS["min_market_cap"]:
        reasons.append(f"Market cap ${market_cap/1e9:.2f}B < ${DISCOVERY_FILTERS['min_market_cap']/1e9:.1f}B")
    
    if market_cap > DISCOVERY_FILTERS["max_market_cap"]:
        reasons.append(f"Market cap ${market_cap/1e9:.2f}B > ${DISCOVERY_FILTERS['max_market_cap']/1e9:.1f}B")
    
    if sector not in DISCOVERY_FILTERS["sectors"]:
        reasons.append(f"Sector '{sector}' not in allowed list")
    
    if viral_score < DISCOVERY_FILTERS["min_viral_score"]:
        reasons.append(f"Viral score {viral_score:.1f} < {DISCOVERY_FILTERS['min_viral_score']}")
    
    return len(reasons) == 0, reasons


async def fetch_stock_info(ticker: str) -> Optional[Dict]:
    """Fetch stock info from Yahoo Finance."""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        return {
            "ticker": ticker,
            "company_name": info.get("longName", info.get("shortName", ticker)),
            "sector": info.get("sector", "Unknown"),
            "current_price": info.get("regularMarketPrice", info.get("currentPrice", 0)),
            "market_cap": info.get("marketCap", 0),
        }
    except Exception as e:
        logger.warning(f"Failed to fetch info for {ticker}: {e}")
        return None


def get_quarterly_additions() -> int:
    """Get count of stocks added this quarter."""
    try:
        if not QUARTERLY_LOG.exists():
            return 0
        
        with open(QUARTERLY_LOG, 'r') as f:
            log = json.load(f)
        
        # Get current quarter
        today = date.today()
        current_quarter = f"{today.year}-Q{(today.month - 1) // 3 + 1}"
        
        return log.get("quarters", {}).get(current_quarter, {}).get("count", 0)
    except Exception:
        return 0


def log_addition(ticker: str, company_name: str):
    """Log a stock addition to the quarterly log."""
    try:
        log = {"quarters": {}}
        if QUARTERLY_LOG.exists():
            with open(QUARTERLY_LOG, 'r') as f:
                log = json.load(f)
        
        today = date.today()
        current_quarter = f"{today.year}-Q{(today.month - 1) // 3 + 1}"
        
        if current_quarter not in log["quarters"]:
            log["quarters"][current_quarter] = {"count": 0, "additions": []}
        
        log["quarters"][current_quarter]["count"] += 1
        log["quarters"][current_quarter]["additions"].append({
            "ticker": ticker,
            "company_name": company_name,
            "added_at": datetime.now().isoformat(),
        })
        
        with open(QUARTERLY_LOG, 'w') as f:
            json.dump(log, f, indent=2)
            
    except Exception as e:
        logger.error(f"Failed to log addition: {e}")


async def discover_stocks(trending_data: List) -> List[DiscoveryCandidate]:
    """
    Analyze trending stocks and identify discovery candidates.
    
    Args:
        trending_data: List of TrendingTicker from Reddit
        
    Returns:
        List of DiscoveryCandidate that pass filters
    """
    from data.stock_universe import get_universe
    
    # Get current universe
    universe = get_universe()
    universe_tickers = {s["ticker"].upper() for s in universe}
    
    candidates = []
    
    for data in trending_data:
        ticker = data.ticker.upper()
        
        # Skip if already in universe
        if ticker in universe_tickers:
            continue
        
        # Skip low viral score
        if data.viral_score < DISCOVERY_FILTERS["min_viral_score"]:
            continue
        
        # Fetch stock info
        info = await fetch_stock_info(ticker)
        if not info:
            continue
        
        # Check filters
        passes, reasons = check_discovery_filters(
            ticker=ticker,
            price=info["current_price"],
            market_cap=info["market_cap"],
            sector=info["sector"],
            viral_score=data.viral_score,
        )
        
        candidate = DiscoveryCandidate(
            ticker=ticker,
            company_name=info["company_name"],
            sector=info["sector"],
            current_price=info["current_price"],
            market_cap=info["market_cap"],
            viral_score=data.viral_score,
            mention_count=data.mention_count,
            total_upvotes=data.total_upvotes,
            sentiment_label=data.sentiment_label,
            discovered_at=datetime.now().isoformat(),
            source="reddit",
            passes_filters=passes,
            filter_reasons=reasons,
        )
        
        if passes:
            candidates.append(candidate)
    
    # Sort by viral score
    candidates.sort(key=lambda x: x.viral_score, reverse=True)
    
    # Check quarterly limit
    current_additions = get_quarterly_additions()
    remaining_slots = DISCOVERY_FILTERS["max_quarterly_additions"] - current_additions
    
    if remaining_slots <= 0:
        logger.warning(f"Quarterly limit reached ({current_additions} additions)")
        return []
    
    # Return top candidates within limit
    return candidates[:remaining_slots]


def save_discovery_candidates(candidates: List[DiscoveryCandidate]) -> None:
    """Save discovery candidates to file for review."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    data = {
        "generated_at": datetime.now().isoformat(),
        "count": len(candidates),
        "quarterly_additions": get_quarterly_additions(),
        "max_quarterly": DISCOVERY_FILTERS["max_quarterly_additions"],
        "filters": DISCOVERY_FILTERS,
        "candidates": [
            {
                "ticker": c.ticker,
                "company_name": c.company_name,
                "sector": c.sector,
                "current_price": c.current_price,
                "market_cap": c.market_cap,
                "viral_score": c.viral_score,
                "mention_count": c.mention_count,
                "total_upvotes": c.total_upvotes,
                "sentiment_label": c.sentiment_label,
                "discovered_at": c.discovered_at,
                "passes_filters": c.passes_filters,
                "filter_reasons": c.filter_reasons,
            }
            for c in candidates
        ]
    }
    
    with open(DISCOVERY_FILE, 'w') as f:
        json.dump(data, f, indent=2)
    
    logger.info(f"Saved {len(candidates)} discovery candidates to {DISCOVERY_FILE}")


def load_discovery_candidates() -> List[Dict]:
    """Load discovery candidates from file."""
    if not DISCOVERY_FILE.exists():
        return []
    
    with open(DISCOVERY_FILE, 'r') as f:
        data = json.load(f)
    
    return data.get("candidates", [])
