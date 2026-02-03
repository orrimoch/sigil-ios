"""
F1.1 Stock Universe Management

Maintains list of US-listed large-cap stocks (NASDAQ + NYSE, market cap > $10B).
Sources tickers from the NASDAQ screener API with S&P 500 Wikipedia fallback.
Target: ~800-900 stocks after market cap filtering.
"""

import pandas as pd
import yfinance as yf
from typing import List, Dict, Optional
from datetime import datetime
from loguru import logger
import json
from pathlib import Path
import requests
from io import StringIO
import time


# Wikipedia S&P 500 URL (used as supplemental/fallback source)
SP500_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"

# NASDAQ screener API (primary source for broad US large-cap coverage)
NASDAQ_SCREENER_URL = "https://api.nasdaq.com/api/screener/stocks"

# Market cap threshold: $10 billion
MIN_MARKET_CAP = 10_000_000_000

# Cache file for universe
CACHE_DIR = Path(__file__).parent.parent.parent / "data"
UNIVERSE_CACHE = CACHE_DIR / "stock_universe.json"

# HTTP headers for web requests
_HTTP_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/html',
}


def fetch_sp500_tickers() -> List[str]:
    """
    Fetch S&P 500 ticker symbols from Wikipedia.
    
    Returns:
        List of ticker symbols (e.g., ['AAPL', 'MSFT', ...])
    """
    logger.info("Fetching S&P 500 tickers from Wikipedia...")
    
    try:
        response = requests.get(SP500_URL, headers=_HTTP_HEADERS, timeout=15)
        tables = pd.read_html(StringIO(response.text))
        df = tables[0]  # First table contains the tickers
        
        # Column name might vary, try common ones
        if 'Symbol' in df.columns:
            tickers = df['Symbol'].tolist()
        elif 'Ticker' in df.columns:
            tickers = df['Ticker'].tolist()
        else:
            tickers = df.iloc[:, 0].tolist()
        
        # Clean tickers (remove dots, replace with dash for yfinance)
        tickers = [t.replace('.', '-') for t in tickers]
        
        logger.info(f"Found {len(tickers)} S&P 500 tickers")
        return tickers
        
    except Exception as e:
        logger.error(f"Failed to fetch S&P 500 tickers: {e}")
        raise


def fetch_nasdaq_screener_tickers(exchanges: List[str] = None) -> List[str]:
    """
    Fetch large/mega-cap tickers from the NASDAQ screener API.
    
    Queries NASDAQ, NYSE, and AMEX exchanges for stocks classified
    as 'large' or 'mega' market cap by NASDAQ.
    
    Args:
        exchanges: List of exchanges to query. Default: ['NASDAQ', 'NYSE', 'AMEX']
    
    Returns:
        Deduplicated list of ticker symbols
    """
    if exchanges is None:
        exchanges = ['NASDAQ', 'NYSE', 'AMEX']
    
    all_tickers = []
    
    for exchange in exchanges:
        logger.info(f"Fetching large/mega-cap tickers from {exchange} screener...")
        
        try:
            params = {
                'tableType': '1',
                'limit': 2000,  # Generous limit to get all in one request
                'offset': 0,
                'exchange': exchange,
                'marketcap': 'large|mega',
            }
            
            resp = requests.get(
                NASDAQ_SCREENER_URL,
                headers=_HTTP_HEADERS,
                params=params,
                timeout=30
            )
            resp.raise_for_status()
            data = resp.json()
            
            rows = data.get('data', {}).get('table', {}).get('rows', [])
            total = data.get('data', {}).get('totalrecords', 0)
            
            tickers = [row['symbol'] for row in rows if row.get('symbol')]
            logger.info(f"  {exchange}: {len(tickers)} tickers (total available: {total})")
            
            all_tickers.extend(tickers)
            
            # Be polite to the API
            time.sleep(0.5)
            
        except Exception as e:
            logger.warning(f"Failed to fetch {exchange} screener data: {e}")
            continue
    
    # Deduplicate while preserving order
    seen = set()
    unique_tickers = []
    for t in all_tickers:
        # Clean ticker: remove whitespace, replace dots with dashes (yfinance convention)
        t = t.strip().replace('.', '-')
        if t and t not in seen:
            seen.add(t)
            unique_tickers.append(t)
    
    logger.info(f"NASDAQ screener total: {len(unique_tickers)} unique tickers across {len(exchanges)} exchanges")
    return unique_tickers


def fetch_us_large_cap_tickers() -> List[str]:
    """
    Fetch a comprehensive list of US-listed large-cap tickers.
    
    Strategy:
    1. Primary: NASDAQ screener API (NASDAQ + NYSE + AMEX, large/mega cap)
    2. Supplement: S&P 500 from Wikipedia (ensures blue-chips are never missed)
    3. Deduplicate the combined list
    
    Returns:
        Deduplicated list of ticker symbols (~900-1000 candidates)
    """
    logger.info("Building comprehensive US large-cap ticker list...")
    
    all_tickers = []
    
    # Primary source: NASDAQ screener API
    try:
        screener_tickers = fetch_nasdaq_screener_tickers()
        all_tickers.extend(screener_tickers)
        logger.info(f"NASDAQ screener contributed {len(screener_tickers)} tickers")
    except Exception as e:
        logger.error(f"NASDAQ screener failed: {e}")
    
    # Supplemental source: S&P 500 from Wikipedia (ensures completeness)
    try:
        sp500_tickers = fetch_sp500_tickers()
        all_tickers.extend(sp500_tickers)
        logger.info(f"S&P 500 contributed {len(sp500_tickers)} tickers")
    except Exception as e:
        logger.warning(f"S&P 500 fetch failed (non-critical): {e}")
    
    # Deduplicate while preserving order
    seen = set()
    unique_tickers = []
    for t in all_tickers:
        t_clean = t.strip().upper().replace('.', '-')
        if t_clean and t_clean not in seen:
            seen.add(t_clean)
            unique_tickers.append(t_clean)
    
    logger.info(f"Total unique candidate tickers: {len(unique_tickers)}")
    
    if not unique_tickers:
        raise RuntimeError("No tickers fetched from any source — cannot build universe")
    
    return unique_tickers


def get_stock_info(ticker: str) -> Optional[Dict]:
    """
    Get stock information from Yahoo Finance.
    
    Returns:
        Dict with ticker, name, sector, market_cap, or None if failed/not found
    """
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        # Check if stock exists (yfinance returns empty-ish dict for invalid tickers)
        if not info.get("marketCap") and not info.get("longName"):
            logger.warning(f"Stock not found: {ticker}")
            return None
        
        return {
            "ticker": ticker,
            "name": info.get("longName") or info.get("shortName") or ticker,
            "sector": info.get("sector") or "Unknown",
            "industry": info.get("industry") or "Unknown",
            "market_cap": info.get("marketCap") or 0,
            "currency": info.get("currency") or "USD",
        }
        
    except Exception as e:
        logger.warning(f"Failed to get info for {ticker}: {e}")
        return None


def build_universe(min_market_cap: int = MIN_MARKET_CAP) -> List[Dict]:
    """
    Build the stock universe from all US-listed large-cap stocks.
    
    Fetches tickers from NASDAQ screener (NASDAQ + NYSE + AMEX) plus S&P 500,
    then filters each by market cap via Yahoo Finance.
    
    Args:
        min_market_cap: Minimum market cap in USD (default $10B)
        
    Returns:
        List of stock dicts that meet criteria, sorted by market cap descending
    """
    logger.info(f"Building stock universe (min market cap: ${min_market_cap:,})")
    
    # Get broad US large-cap ticker candidates
    tickers = fetch_us_large_cap_tickers()
    
    # Fetch info for each ticker and filter by market cap
    universe = []
    failed = []
    
    for i, ticker in enumerate(tickers):
        if (i + 1) % 50 == 0:
            logger.info(f"Processing {i + 1}/{len(tickers)}...")
        
        info = get_stock_info(ticker)
        
        if info is None:
            failed.append(ticker)
            continue
            
        # Filter by market cap
        if info["market_cap"] >= min_market_cap:
            info["is_active"] = True
            info["added_date"] = datetime.now().isoformat()
            universe.append(info)
        else:
            logger.debug(f"Excluded {ticker}: market cap ${info['market_cap']:,} < ${min_market_cap:,}")
    
    # Sort by market cap descending
    universe.sort(key=lambda x: x["market_cap"], reverse=True)
    
    logger.info(f"Universe built: {len(universe)} stocks meet criteria")
    logger.info(f"Excluded: {len(tickers) - len(universe) - len(failed)} below market cap threshold")
    if failed:
        logger.warning(f"Failed to fetch: {len(failed)} tickers: {failed[:10]}...")
    
    return universe


def save_universe(universe: List[Dict], path: Path = UNIVERSE_CACHE) -> None:
    """Save universe to JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    
    data = {
        "updated_at": datetime.now().isoformat(),
        "count": len(universe),
        "min_market_cap": MIN_MARKET_CAP,
        "stocks": universe
    }
    
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)
    
    logger.info(f"Universe saved to {path}")


def load_universe(path: Path = UNIVERSE_CACHE) -> Optional[Dict]:
    """Load universe from JSON file."""
    if not path.exists():
        logger.warning(f"Universe cache not found: {path}")
        return None
    
    with open(path, 'r') as f:
        data = json.load(f)
    
    logger.info(f"Loaded universe: {data['count']} stocks (updated: {data['updated_at']})")
    return data


def get_universe() -> List[Dict]:
    """
    Get stock universe, loading from cache or building fresh.
    
    Returns:
        List of stock dicts
    """
    cached = load_universe()
    
    if cached:
        return cached["stocks"]
    
    # Build fresh
    universe = build_universe()
    save_universe(universe)
    return universe


def get_sectors() -> Dict[str, int]:
    """Get sector breakdown of universe."""
    universe = get_universe()
    
    sectors = {}
    for stock in universe:
        sector = stock["sector"]
        sectors[sector] = sectors.get(sector, 0) + 1
    
    return dict(sorted(sectors.items(), key=lambda x: x[1], reverse=True))


# CLI for manual testing
if __name__ == "__main__":
    import sys
    
    logger.add(sys.stderr, level="INFO")
    
    print("\n=== Building Stock Universe ===\n")
    
    universe = build_universe()
    save_universe(universe)
    
    print(f"\n✅ Universe: {len(universe)} stocks")
    print(f"\n📊 Top 10 by Market Cap:")
    for stock in universe[:10]:
        print(f"  {stock['ticker']:6} | {stock['name'][:30]:30} | ${stock['market_cap']/1e9:.1f}B | {stock['sector']}")
    
    print(f"\n📈 Sector Breakdown:")
    for sector, count in get_sectors().items():
        print(f"  {sector}: {count}")
