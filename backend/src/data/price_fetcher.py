"""
F1.2 Price Data Fetcher

Fetches daily OHLCV price data for all stocks in the universe.
Source: Yahoo Finance (yfinance) — FREE
"""

import pandas as pd
import yfinance as yf
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from pathlib import Path
import json
from loguru import logger
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

from .stock_universe import get_universe, load_universe


# Cache directory
CACHE_DIR = Path(__file__).parent.parent.parent / "data"
PRICES_DIR = CACHE_DIR / "prices"


def fetch_price_history(
    ticker: str,
    period: str = "5y",
    interval: str = "1d"
) -> Optional[pd.DataFrame]:
    """
    Fetch price history for a single stock.
    
    Args:
        ticker: Stock ticker symbol
        period: Data period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
        interval: Data interval (1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo)
    
    Returns:
        DataFrame with OHLCV data or None if failed
    """
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period, interval=interval)
        
        if df.empty:
            logger.warning(f"No price data for {ticker}")
            return None
        
        # Clean up column names
        df = df.reset_index()
        df.columns = [c.lower().replace(' ', '_') for c in df.columns]
        
        # Add ticker column
        df['ticker'] = ticker
        
        # Select relevant columns
        columns = ['date', 'ticker', 'open', 'high', 'low', 'close', 'volume']
        df = df[[c for c in columns if c in df.columns]]
        
        return df
        
    except Exception as e:
        logger.error(f"Failed to fetch prices for {ticker}: {e}")
        return None


def fetch_latest_price(ticker: str) -> Optional[Dict]:
    """
    Fetch latest price for a single stock.
    Uses fast_info first (lightweight), falls back to full info.
    
    Returns:
        Dict with current price data or None if failed
    """
    try:
        stock = yf.Ticker(ticker)
        
        # Try fast_info first (much lighter, less likely to rate limit)
        try:
            fi = stock.fast_info
            price = fi.get("lastPrice") or fi.get("last_price")
            prev_close = fi.get("previousClose") or fi.get("previous_close") or fi.get("regularMarketPreviousClose")
            if price and price > 0:
                change = (price - prev_close) if prev_close else None
                change_pct = (change / prev_close * 100) if (prev_close and change) else None
                return {
                    "ticker": ticker,
                    "price": float(price),
                    "previous_close": float(prev_close) if prev_close else None,
                    "open": float(fi.get("open", 0)) or None,
                    "high": float(fi.get("dayHigh", 0) or fi.get("day_high", 0)) or None,
                    "low": float(fi.get("dayLow", 0) or fi.get("day_low", 0)) or None,
                    "volume": int(fi.get("lastVolume", 0) or fi.get("last_volume", 0)) or None,
                    "market_cap": int(fi.get("marketCap", 0) or fi.get("market_cap", 0)) or None,
                    "change": float(change) if change else None,
                    "change_percent": float(change_pct) if change_pct else None,
                    "timestamp": datetime.now().isoformat(),
                }
        except Exception as e:
            logger.debug(f"fast_info failed for {ticker}, trying full info: {e}")
        
        # Fallback to full info
        info = stock.info
        
        return {
            "ticker": ticker,
            "price": info.get("currentPrice") or info.get("regularMarketPrice"),
            "previous_close": info.get("previousClose"),
            "open": info.get("open") or info.get("regularMarketOpen"),
            "high": info.get("dayHigh") or info.get("regularMarketDayHigh"),
            "low": info.get("dayLow") or info.get("regularMarketDayLow"),
            "volume": info.get("volume") or info.get("regularMarketVolume"),
            "market_cap": info.get("marketCap"),
            "change": info.get("regularMarketChange"),
            "change_percent": info.get("regularMarketChangePercent"),
            "timestamp": datetime.now().isoformat(),
        }
        
    except Exception as e:
        logger.warning(f"yfinance failed for {ticker}: {e}, trying direct API...")
    
    # Last resort: direct Yahoo chart API (bypasses yfinance rate limits)
    try:
        import requests
        headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
        url = f'https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range=1d&interval=1m'
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            meta = resp.json()['chart']['result'][0]['meta']
            price = meta.get('regularMarketPrice', 0)
            prev_close = meta.get('chartPreviousClose', 0)
            change = price - prev_close if prev_close else None
            change_pct = (change / prev_close * 100) if (prev_close and change) else None
            return {
                "ticker": ticker,
                "price": float(price),
                "previous_close": float(prev_close) if prev_close else None,
                "open": float(meta.get('regularMarketOpen', 0)) or None,
                "high": float(meta.get('regularMarketDayHigh', 0)) or None,
                "low": float(meta.get('regularMarketDayLow', 0)) or None,
                "volume": int(meta.get('regularMarketVolume', 0)) or None,
                "market_cap": None,
                "change": float(change) if change else None,
                "change_percent": float(change_pct) if change_pct else None,
                "timestamp": datetime.now().isoformat(),
            }
    except Exception as e2:
        logger.error(f"Direct API also failed for {ticker}: {e2}")
    
    return None


def fetch_all_prices(
    tickers: List[str] = None,
    period: str = "5y",
    max_workers: int = 3,
    delay: float = 0.5,
    batch_size: int = 25,
    batch_pause: float = 5.0
) -> Dict[str, pd.DataFrame]:
    """
    Fetch price history for multiple stocks with rate-limit-safe batching.
    
    Args:
        tickers: List of tickers (if None, uses full universe)
        period: Data period
        max_workers: Number of parallel threads (kept low to avoid rate limits)
        delay: Delay between individual requests
        batch_size: Number of stocks per batch
        batch_pause: Seconds to pause between batches
    
    Returns:
        Dict mapping ticker to DataFrame
    """
    if tickers is None:
        universe = get_universe()
        tickers = [s["ticker"] for s in universe]
    
    # Skip tickers that already have cached data
    cached = []
    remaining = []
    for t in tickers:
        path = PRICES_DIR / f"{t}.parquet"
        if path.exists():
            cached.append(t)
        else:
            remaining.append(t)
    
    if cached:
        logger.info(f"Skipping {len(cached)} already-cached tickers")
    
    logger.info(f"Fetching prices for {len(remaining)} stocks (period={period}, batch_size={batch_size})...")
    
    results = {}
    failed = []
    
    # Load already-cached data into results
    for t in cached:
        try:
            df = load_prices(t)
            if df is not None:
                results[t] = df
        except Exception:
            remaining.append(t)
    
    # Process in batches to avoid rate limiting
    total_batches = (len(remaining) + batch_size - 1) // batch_size
    
    for batch_idx in range(total_batches):
        batch_start = batch_idx * batch_size
        batch_end = min(batch_start + batch_size, len(remaining))
        batch = remaining[batch_start:batch_end]
        
        logger.info(f"Batch {batch_idx + 1}/{total_batches}: processing {len(batch)} stocks...")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_ticker = {
                executor.submit(fetch_price_history, ticker, period): ticker
                for ticker in batch
            }
            
            for future in as_completed(future_to_ticker):
                ticker = future_to_ticker[future]
                try:
                    df = future.result()
                    if df is not None:
                        results[ticker] = df
                    else:
                        failed.append(ticker)
                except Exception as e:
                    logger.error(f"Error fetching {ticker}: {e}")
                    failed.append(ticker)
                
                time.sleep(delay)
        
        # Pause between batches to let rate limits reset
        if batch_idx < total_batches - 1:
            logger.info(f"Batch {batch_idx + 1} done. Pausing {batch_pause}s...")
            time.sleep(batch_pause)
    
    logger.info(f"Fetched prices for {len(results)} stocks ({len(cached)} cached + {len(results) - len(cached)} new)")
    if failed:
        logger.warning(f"Failed: {len(failed)} stocks: {failed[:20]}...")
    
    return results


def fetch_latest_prices(
    tickers: List[str] = None,
    max_workers: int = 10
) -> List[Dict]:
    """
    Fetch latest prices for multiple stocks.
    
    Returns:
        List of price dicts
    """
    if tickers is None:
        universe = get_universe()
        tickers = [s["ticker"] for s in universe]
    
    logger.info(f"Fetching latest prices for {len(tickers)} stocks...")
    
    results = []
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_ticker = {
            executor.submit(fetch_latest_price, ticker): ticker
            for ticker in tickers
        }
        
        for future in as_completed(future_to_ticker):
            result = future.result()
            if result:
                results.append(result)
    
    logger.info(f"Fetched latest prices for {len(results)} stocks")
    return results


def save_prices(prices: Dict[str, pd.DataFrame], output_dir: Path = PRICES_DIR) -> None:
    """
    Save price data to parquet files.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    for ticker, df in prices.items():
        path = output_dir / f"{ticker}.parquet"
        df.to_parquet(path, index=False)
    
    # Save metadata
    metadata = {
        "updated_at": datetime.now().isoformat(),
        "count": len(prices),
        "tickers": list(prices.keys()),
    }
    
    with open(output_dir / "metadata.json", 'w') as f:
        json.dump(metadata, f, indent=2)
    
    logger.info(f"Saved prices to {output_dir}")


def load_prices(ticker: str, output_dir: Path = PRICES_DIR) -> Optional[pd.DataFrame]:
    """
    Load price data for a single stock from cache.
    """
    path = output_dir / f"{ticker}.parquet"
    
    if not path.exists():
        return None
    
    return pd.read_parquet(path)


def get_price_summary(ticker: str) -> Optional[Dict]:
    """
    Get price summary for a stock (from cache or live).
    """
    # Try cache first
    df = load_prices(ticker)
    
    if df is not None and len(df) > 0:
        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest
        
        return {
            "ticker": ticker,
            "price": float(latest["close"]),
            "open": float(latest["open"]),
            "high": float(latest["high"]),
            "low": float(latest["low"]),
            "volume": int(latest["volume"]),
            "previous_close": float(prev["close"]),
            "change": float(latest["close"] - prev["close"]),
            "change_percent": float((latest["close"] - prev["close"]) / prev["close"] * 100),
            "date": str(latest["date"]),
        }
    
    # Fallback to live
    return fetch_latest_price(ticker)


# CLI for manual testing
if __name__ == "__main__":
    import sys
    
    logger.add(sys.stderr, level="INFO")
    
    print("\n=== Price Fetcher Test ===\n")
    
    # Test single stock
    print("Fetching AAPL 5-year history...")
    df = fetch_price_history("AAPL", period="5y")
    if df is not None:
        print(f"  Rows: {len(df)}")
        print(f"  Date range: {df['date'].min()} to {df['date'].max()}")
        print(f"  Latest: ${df['close'].iloc[-1]:.2f}")
    
    # Test latest price
    print("\nFetching AAPL latest price...")
    price = fetch_latest_price("AAPL")
    if price:
        print(f"  Current: ${price['price']:.2f}")
        print(f"  Change: {price['change_percent']:.2f}%")
    
    print("\n✅ Price fetcher working!")
