"""
REC-266: Real Fundamentals Fetcher

Fetches real company fundamentals from Yahoo Finance.
Used to filter out low-quality meme stocks (no revenue, poor earnings).
"""

import yfinance as yf
import logging
from typing import Dict, Optional, List
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Import TickerFundamentals from reddit_scorer for compatibility
from .reddit_scorer import TickerFundamentals

logger = logging.getLogger(__name__)

# Cache for fundamentals (avoid hammering Yahoo Finance)
_fundamentals_cache: Dict[str, tuple] = {}  # ticker -> (data, timestamp)
_cache_lock = threading.Lock()
CACHE_TTL = timedelta(hours=6)  # Cache fundamentals for 6 hours


def fetch_fundamentals(ticker: str) -> Optional[TickerFundamentals]:
    """
    Fetch fundamentals for a single ticker from Yahoo Finance.
    
    Uses caching to avoid rate limits.
    """
    ticker = ticker.upper()
    
    # Check cache first
    with _cache_lock:
        if ticker in _fundamentals_cache:
            data, timestamp = _fundamentals_cache[ticker]
            if datetime.utcnow() - timestamp < CACHE_TTL:
                return data
    
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        if not info or info.get("regularMarketPrice") is None:
            logger.debug(f"No data available for {ticker}")
            return None
        
        # Extract fundamentals (match reddit_scorer.TickerFundamentals fields)
        earnings_growth = info.get("earningsGrowth")
        if earnings_growth is not None:
            earnings_growth = earnings_growth * 100  # Convert to %
        
        fundamentals = TickerFundamentals(
            ticker=ticker,
            company_name=info.get("longName", info.get("shortName", "")),
            current_price=info.get("regularMarketPrice"),
            revenue_ttm=info.get("totalRevenue"),
            eps_latest=info.get("trailingEps"),
            eps_prev_quarter=None,  # Would need quarterly data
            earnings_growth=earnings_growth
        )
        
        # Cache the result
        with _cache_lock:
            _fundamentals_cache[ticker] = (fundamentals, datetime.utcnow())
        
        revenue_str = f"${fundamentals.revenue_ttm:,.0f}" if fundamentals.revenue_ttm else "N/A"
        eps_str = f"${fundamentals.eps_latest:.2f}" if fundamentals.eps_latest else "N/A"
        logger.debug(f"Fetched fundamentals for {ticker}: revenue={revenue_str}, EPS={eps_str}")
        return fundamentals
        
    except Exception as e:
        logger.warning(f"Failed to fetch fundamentals for {ticker}: {e}")
        return None


def fetch_fundamentals_batch(
    tickers: List[str],
    max_workers: int = 5
) -> Dict[str, TickerFundamentals]:
    """
    Fetch fundamentals for multiple tickers in parallel.
    
    Args:
        tickers: List of ticker symbols
        max_workers: Max parallel requests (keep low to avoid rate limits)
        
    Returns:
        Dict mapping ticker to TickerFundamentals (only successful fetches)
    """
    results: Dict[str, TickerFundamentals] = {}
    
    # Filter out tickers we already have cached
    tickers_to_fetch = []
    for ticker in tickers:
        ticker = ticker.upper()
        with _cache_lock:
            if ticker in _fundamentals_cache:
                data, timestamp = _fundamentals_cache[ticker]
                if datetime.utcnow() - timestamp < CACHE_TTL:
                    if data is not None:
                        results[ticker] = data
                    continue
        tickers_to_fetch.append(ticker)
    
    if not tickers_to_fetch:
        return results
    
    logger.info(f"Fetching fundamentals for {len(tickers_to_fetch)} tickers...")
    
    # Fetch in parallel with limited workers
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_ticker = {
            executor.submit(fetch_fundamentals, ticker): ticker 
            for ticker in tickers_to_fetch
        }
        
        for future in as_completed(future_to_ticker):
            ticker = future_to_ticker[future]
            try:
                fundamentals = future.result()
                if fundamentals:
                    results[ticker] = fundamentals
            except Exception as e:
                logger.warning(f"Error fetching {ticker}: {e}")
    
    logger.info(f"Successfully fetched fundamentals for {len(results)} tickers")
    return results


def get_fundamentals_for_trending(
    trending_tickers: List[str]
) -> Dict[str, TickerFundamentals]:
    """
    Get fundamentals for trending Reddit tickers.
    
    Convenience function that handles the batch fetch and returns
    a dict suitable for RedditScorer.set_fundamentals().
    """
    return fetch_fundamentals_batch(trending_tickers, max_workers=5)


# For backwards compatibility with existing code
def create_real_fundamentals(tickers: List[str]) -> Dict[str, TickerFundamentals]:
    """
    Replacement for create_mock_fundamentals() that fetches real data.
    """
    return fetch_fundamentals_batch(tickers, max_workers=5)
