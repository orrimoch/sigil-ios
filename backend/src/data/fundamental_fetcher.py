"""
F1.3 Fundamental Data Fetcher

Fetches quarterly fundamentals (P/E, EPS, revenue, margins) for stocks.
Source: Yahoo Finance — FREE
"""

import pandas as pd
import yfinance as yf
from typing import List, Dict, Optional
from datetime import datetime
from pathlib import Path
import json
from loguru import logger
from concurrent.futures import ThreadPoolExecutor, as_completed
import time


# Cache directory
CACHE_DIR = Path(__file__).parent.parent.parent / "data"
FUNDAMENTALS_CACHE = CACHE_DIR / "fundamentals.json"


def fetch_fundamentals(ticker: str) -> Optional[Dict]:
    """
    Fetch fundamental data for a single stock.
    
    Returns:
        Dict with fundamental metrics or None if failed
    """
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        # Check if valid stock
        if not info.get("marketCap"):
            logger.warning(f"No fundamental data for {ticker}")
            return None
        
        # Extract fundamental metrics
        fundamentals = {
            "ticker": ticker,
            "updated_at": datetime.now().isoformat(),
            
            # Valuation metrics
            "market_cap": info.get("marketCap"),
            "enterprise_value": info.get("enterpriseValue"),
            "pe_ratio": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "peg_ratio": info.get("pegRatio"),
            "pb_ratio": info.get("priceToBook"),
            "ps_ratio": info.get("priceToSalesTrailing12Months"),
            
            # Earnings & Revenue
            "eps_ttm": info.get("trailingEps"),
            "eps_forward": info.get("forwardEps"),
            "revenue_ttm": info.get("totalRevenue"),
            "revenue_per_share": info.get("revenuePerShare"),
            "revenue_growth": info.get("revenueGrowth"),
            "earnings_growth": info.get("earningsGrowth"),
            "earnings_quarterly_growth": info.get("earningsQuarterlyGrowth"),
            
            # Profitability
            "profit_margin": info.get("profitMargins"),
            "operating_margin": info.get("operatingMargins"),
            "gross_margin": info.get("grossMargins"),
            "ebitda_margin": info.get("ebitdaMargins"),
            "roe": info.get("returnOnEquity"),
            "roa": info.get("returnOnAssets"),
            
            # Financial Health
            "debt_to_equity": info.get("debtToEquity"),
            "current_ratio": info.get("currentRatio"),
            "quick_ratio": info.get("quickRatio"),
            "total_debt": info.get("totalDebt"),
            "total_cash": info.get("totalCash"),
            "free_cash_flow": info.get("freeCashflow"),
            "operating_cash_flow": info.get("operatingCashflow"),
            
            # Dividends
            "dividend_yield": info.get("dividendYield"),
            "dividend_rate": info.get("dividendRate"),
            "payout_ratio": info.get("payoutRatio"),
            
            # Analyst Data
            "target_mean_price": info.get("targetMeanPrice"),
            "target_high_price": info.get("targetHighPrice"),
            "target_low_price": info.get("targetLowPrice"),
            "recommendation_mean": info.get("recommendationMean"),
            "recommendation_key": info.get("recommendationKey"),
            "number_of_analysts": info.get("numberOfAnalystOpinions"),
            
            # Company Info
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "employees": info.get("fullTimeEmployees"),
            "beta": info.get("beta"),
            "52_week_high": info.get("fiftyTwoWeekHigh"),
            "52_week_low": info.get("fiftyTwoWeekLow"),
            "50_day_avg": info.get("fiftyDayAverage"),
            "200_day_avg": info.get("twoHundredDayAverage"),
        }
        
        return fundamentals
        
    except Exception as e:
        logger.error(f"Failed to fetch fundamentals for {ticker}: {e}")
        return None


def fetch_all_fundamentals(
    tickers: List[str] = None,
    max_workers: int = 2,
    delay: float = 1.0,
    batch_size: int = 20,
    batch_pause: float = 10.0
) -> Dict[str, Dict]:
    """
    Fetch fundamentals for multiple stocks with rate-limit-safe batching.
    
    Args:
        tickers: List of tickers (if None, uses full universe)
        max_workers: Number of parallel threads (kept very low — fundamentals hit Yahoo hard)
        delay: Delay between individual requests
        batch_size: Number of stocks per batch
        batch_pause: Seconds to pause between batches
    
    Returns:
        Dict mapping ticker to fundamentals dict
    """
    if tickers is None:
        from .stock_universe import get_universe
        universe = get_universe()
        tickers = [s["ticker"] for s in universe]
    
    # Load existing cached fundamentals to skip already-fetched
    existing = {}
    if FUNDAMENTALS_CACHE.exists():
        try:
            with open(FUNDAMENTALS_CACHE) as f:
                cached = json.load(f)
            existing = cached.get("stocks", {})
            logger.info(f"Found {len(existing)} cached fundamentals")
        except Exception:
            pass
    
    # Skip tickers with valid cached data (has pe_ratio or market_cap)
    remaining = []
    for t in tickers:
        cached_data = existing.get(t, {})
        if cached_data and (cached_data.get("market_cap") or cached_data.get("pe_ratio")):
            continue
        remaining.append(t)
    
    logger.info(f"Fetching fundamentals for {len(remaining)} stocks ({len(tickers) - len(remaining)} cached)...")
    
    results = dict(existing)  # Start with cached data
    failed = []
    
    # Process in batches
    total_batches = (len(remaining) + batch_size - 1) // batch_size
    
    for batch_idx in range(total_batches):
        batch_start = batch_idx * batch_size
        batch_end = min(batch_start + batch_size, len(remaining))
        batch = remaining[batch_start:batch_end]
        
        logger.info(f"Batch {batch_idx + 1}/{total_batches}: processing {len(batch)} stocks...")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_ticker = {
                executor.submit(fetch_fundamentals, ticker): ticker
                for ticker in batch
            }
            
            for future in as_completed(future_to_ticker):
                ticker = future_to_ticker[future]
                try:
                    data = future.result()
                    if data is not None:
                        results[ticker] = data
                    else:
                        failed.append(ticker)
                except Exception as e:
                    logger.error(f"Error fetching {ticker}: {e}")
                    failed.append(ticker)
                
                time.sleep(delay)
        
        # Save incrementally after each batch (don't lose progress on crash)
        save_fundamentals(results)
        
        # Pause between batches
        if batch_idx < total_batches - 1:
            logger.info(f"Batch {batch_idx + 1} done ({len(results)} total). Pausing {batch_pause}s...")
            time.sleep(batch_pause)
    
    logger.info(f"Fetched fundamentals for {len(results)} stocks")
    if failed:
        logger.warning(f"Failed: {len(failed)} stocks: {failed[:20]}...")
    
    return results


def save_fundamentals(fundamentals: Dict[str, Dict], path: Path = FUNDAMENTALS_CACHE) -> None:
    """Save fundamentals to JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    
    data = {
        "updated_at": datetime.now().isoformat(),
        "count": len(fundamentals),
        "stocks": fundamentals
    }
    
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)
    
    logger.info(f"Saved fundamentals to {path}")


def load_fundamentals(path: Path = FUNDAMENTALS_CACHE) -> Optional[Dict]:
    """Load fundamentals from JSON file."""
    if not path.exists():
        return None
    
    with open(path, 'r') as f:
        return json.load(f)


def get_fundamentals(ticker: str) -> Optional[Dict]:
    """
    Get fundamentals for a stock (from cache or live).
    """
    # Try cache first
    cached = load_fundamentals()
    if cached and ticker in cached.get("stocks", {}):
        return cached["stocks"][ticker]
    
    # Fallback to live
    return fetch_fundamentals(ticker)


def calculate_quality_score(fundamentals: Dict) -> float:
    """
    Calculate a quality score (0-100) based on fundamentals.
    
    Higher is better:
    - High ROE, ROA
    - High margins
    - Low debt
    - Strong cash flow
    """
    score = 50  # Start at neutral
    
    # ROE (weight: 25)
    roe = fundamentals.get("roe")
    if roe is not None:
        if roe > 0.20:
            score += 25
        elif roe > 0.15:
            score += 20
        elif roe > 0.10:
            score += 10
        elif roe < 0:
            score -= 15
    
    # Profit margin (weight: 20)
    margin = fundamentals.get("profit_margin")
    if margin is not None:
        if margin > 0.20:
            score += 20
        elif margin > 0.10:
            score += 15
        elif margin > 0.05:
            score += 5
        elif margin < 0:
            score -= 10
    
    # Debt to equity (weight: 15) - lower is better
    de = fundamentals.get("debt_to_equity")
    if de is not None:
        if de < 30:
            score += 15
        elif de < 50:
            score += 10
        elif de < 100:
            score += 5
        elif de > 200:
            score -= 10
    
    # Revenue growth (weight: 15)
    rev_growth = fundamentals.get("revenue_growth")
    if rev_growth is not None:
        if rev_growth > 0.20:
            score += 15
        elif rev_growth > 0.10:
            score += 10
        elif rev_growth > 0:
            score += 5
        elif rev_growth < -0.10:
            score -= 10
    
    # Current ratio (weight: 10) - measures liquidity
    current = fundamentals.get("current_ratio")
    if current is not None:
        if current > 2:
            score += 10
        elif current > 1.5:
            score += 7
        elif current > 1:
            score += 3
        elif current < 1:
            score -= 5
    
    # Free cash flow positive (weight: 15)
    fcf = fundamentals.get("free_cash_flow")
    if fcf is not None:
        if fcf > 0:
            score += 15
        else:
            score -= 10
    
    # Clamp to 0-100
    return max(0, min(100, score))


def calculate_value_score(fundamentals: Dict) -> float:
    """
    Calculate a value score (0-100) based on valuation metrics.
    
    Higher = more undervalued:
    - Low P/E, P/B, P/S
    - PEG < 1
    """
    score = 50
    
    # P/E ratio (weight: 30)
    pe = fundamentals.get("pe_ratio")
    if pe is not None and pe > 0:
        if pe < 10:
            score += 30
        elif pe < 15:
            score += 20
        elif pe < 20:
            score += 10
        elif pe < 25:
            score += 0
        elif pe > 40:
            score -= 15
    
    # P/B ratio (weight: 20)
    pb = fundamentals.get("pb_ratio")
    if pb is not None and pb > 0:
        if pb < 1:
            score += 20
        elif pb < 2:
            score += 15
        elif pb < 3:
            score += 5
        elif pb > 5:
            score -= 10
    
    # PEG ratio (weight: 25)
    peg = fundamentals.get("peg_ratio")
    if peg is not None and peg > 0:
        if peg < 0.5:
            score += 25
        elif peg < 1:
            score += 20
        elif peg < 1.5:
            score += 10
        elif peg > 2:
            score -= 10
    
    # P/S ratio (weight: 15)
    ps = fundamentals.get("ps_ratio")
    if ps is not None and ps > 0:
        if ps < 1:
            score += 15
        elif ps < 2:
            score += 10
        elif ps < 5:
            score += 5
        elif ps > 10:
            score -= 10
    
    # Dividend yield bonus (weight: 10)
    div_yield = fundamentals.get("dividend_yield")
    if div_yield is not None and div_yield > 0:
        if div_yield > 0.04:
            score += 10
        elif div_yield > 0.02:
            score += 5
    
    return max(0, min(100, score))


def calculate_growth_score(fundamentals: Dict) -> float:
    """
    Calculate a growth score (0-100) based on growth metrics.
    """
    score = 50
    
    # Revenue growth (weight: 35)
    rev_growth = fundamentals.get("revenue_growth")
    if rev_growth is not None:
        if rev_growth > 0.30:
            score += 35
        elif rev_growth > 0.20:
            score += 25
        elif rev_growth > 0.10:
            score += 15
        elif rev_growth > 0:
            score += 5
        elif rev_growth < -0.10:
            score -= 20
    
    # Earnings growth (weight: 35)
    earn_growth = fundamentals.get("earnings_growth")
    if earn_growth is not None:
        if earn_growth > 0.30:
            score += 35
        elif earn_growth > 0.20:
            score += 25
        elif earn_growth > 0.10:
            score += 15
        elif earn_growth > 0:
            score += 5
        elif earn_growth < -0.10:
            score -= 20
    
    # Forward EPS vs trailing (momentum)
    eps_ttm = fundamentals.get("eps_ttm")
    eps_fwd = fundamentals.get("eps_forward")
    if eps_ttm and eps_fwd and eps_ttm > 0:
        growth = (eps_fwd - eps_ttm) / eps_ttm
        if growth > 0.20:
            score += 15
        elif growth > 0.10:
            score += 10
        elif growth > 0:
            score += 5
        elif growth < -0.10:
            score -= 10
    
    return max(0, min(100, score))


# CLI for testing
if __name__ == "__main__":
    import sys
    logger.add(sys.stderr, level="INFO")
    
    print("\n=== Fundamental Fetcher Test ===\n")
    
    # Test single stock
    print("Fetching AAPL fundamentals...")
    fund = fetch_fundamentals("AAPL")
    if fund:
        print(f"  P/E Ratio: {fund.get('pe_ratio', 'N/A')}")
        print(f"  EPS (TTM): ${fund.get('eps_ttm', 'N/A')}")
        print(f"  Revenue Growth: {fund.get('revenue_growth', 'N/A')}")
        print(f"  Profit Margin: {fund.get('profit_margin', 'N/A')}")
        print(f"  ROE: {fund.get('roe', 'N/A')}")
        print(f"  Debt/Equity: {fund.get('debt_to_equity', 'N/A')}")
        
        print(f"\n  Quality Score: {calculate_quality_score(fund):.0f}/100")
        print(f"  Value Score: {calculate_value_score(fund):.0f}/100")
        print(f"  Growth Score: {calculate_growth_score(fund):.0f}/100")
    
    print("\n✅ Fundamental fetcher working!")
