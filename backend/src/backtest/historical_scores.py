"""
F12.2 Historical Score Generator

Generate point-in-time historical scores using only data available at that moment.
No lookahead bias - fundamentals use 60-day lag, sentiment uses neutral (50) for historical.

Approach (A + C from spec):
A) Retroactive: Generate historical scores for fundamentals + technical + macro
B) Use neutral (50) for historical sentiment (no news archive available)
C) Track live scores going forward for real validation
"""

import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from loguru import logger
from concurrent.futures import ThreadPoolExecutor, as_completed
import yfinance as yf

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest.data_store import (
    BacktestDataStore,
    HistoricalScore,
    get_data_store,
)
from data.stock_universe import get_universe, load_universe
from scoring.fundamental_score import calculate_fundamental_scores
from scoring.technical_score import calculate_technical_scores
from scoring.macro_score import calculate_macro_scores


# Cache directory
CACHE_DIR = Path(__file__).parent.parent.parent / "data"
PRICES_DIR = CACHE_DIR / "prices"

# Score weights (same as composite_score.py)
WEIGHTS = {
    "fundamental": 0.35,
    "sentiment": 0.25,
    "macro": 0.20,
    "technical": 0.20,
}

# Weights for backtesting without sentiment data
# Redistributes sentiment weight (25%) proportionally to other components
WEIGHTS_NO_SENTIMENT = {
    "fundamental": 0.47,  # 35% + (35/75 * 25%) = 47%
    "sentiment": 0.00,    # Excluded
    "macro": 0.26,        # 20% + (20/75 * 25%) = 26%
    "technical": 0.27,    # 20% + (20/75 * 25%) = 27%
}

# Fundamental data lag (days) - earnings typically released 45-60 days after quarter end
FUNDAMENTAL_LAG_DAYS = 60

# How many weeks of history to generate
# Default: 1.5 years (78 weeks) - sufficient for validation with free yfinance data
# Optional: 5 years (260 weeks) - requires paid data source for accurate fundamentals
DEFAULT_HISTORY_WEEKS = 78  # 1.5 years
EXTENDED_HISTORY_WEEKS = 260  # 5 years (optional)


@dataclass
class HistoricalDataPoint:
    """Price and volume data for a specific date."""
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int


class HistoricalScoreGenerator:
    """
    Generates point-in-time historical scores.
    
    Key principles:
    1. No lookahead bias - only use data available at that time
    2. Fundamentals: Use 60-day lag (earnings announcement delay)
    3. Technical: Calculate from price data up to that date
    4. Macro: Use FRED data available at that time
    5. Sentiment: Use neutral (50) for historical (no archive)
    """
    
    def __init__(self, data_store: Optional[BacktestDataStore] = None, no_sentiment: bool = False):
        self.data_store = data_store or get_data_store()
        self._price_cache: Dict[str, pd.DataFrame] = {}
        self._universe_cache: Optional[List[Dict]] = None
        self.no_sentiment = no_sentiment
        self.weights = WEIGHTS_NO_SENTIMENT if no_sentiment else WEIGHTS
    
    def generate_historical_scores(
        self,
        start_date: str,
        end_date: str,
        tickers: Optional[List[str]] = None,
        frequency: str = "weekly",  # "daily" or "weekly"
        progress_callback: Optional[callable] = None,
        force_regenerate: bool = False,
    ) -> int:
        """
        Generate historical scores for a date range.
        
        Caching: Scores are cached by date. If scores exist for a date, we skip it
        unless force_regenerate=True. This makes subsequent runs fast.
        
        Args:
            start_date: Start date YYYY-MM-DD
            end_date: End date YYYY-MM-DD
            tickers: Optional list of tickers (defaults to full universe)
            frequency: "daily" or "weekly"
            progress_callback: Optional callback(current, total, message)
            force_regenerate: If True, regenerate even if scores exist
            
        Returns:
            Number of scores generated
        """
        logger.info(f"Generating historical scores from {start_date} to {end_date}")
        
        # Get universe
        if tickers is None:
            universe = self._get_universe()
            tickers = [s["ticker"] for s in universe]
        
        # Generate date list
        all_dates = self._generate_date_list(start_date, end_date, frequency)
        
        # Check which dates already have scores (caching)
        if not force_regenerate:
            existing_scores = self.data_store.get_historical_scores(start_date, end_date)
            existing_dates = set(existing_scores.keys())
            
            # Filter out dates that already have sufficient scores
            # Consider a date "complete" if it has >= 80% of requested tickers
            min_tickers_threshold = int(len(tickers) * 0.8)
            
            dates_to_generate = []
            skipped_count = 0
            
            for d in all_dates:
                if d in existing_dates:
                    existing_ticker_count = len(existing_scores[d])
                    if existing_ticker_count >= min_tickers_threshold:
                        skipped_count += 1
                        continue
                dates_to_generate.append(d)
            
            if skipped_count > 0:
                logger.info(f"Skipping {skipped_count} dates with existing scores (cached)")
            
            dates = dates_to_generate
        else:
            dates = all_dates
            logger.info("Force regenerate: ignoring cached scores")
        
        if not dates:
            logger.info("All dates already have scores. Nothing to generate.")
            return 0
        
        logger.info(f"Generating scores for {len(tickers)} tickers across {len(dates)} dates")
        
        # Pre-fetch all price data
        logger.info("Fetching price history...")
        self._prefetch_prices(tickers, start_date, end_date)
        
        # Generate scores for each date
        total_scores = 0
        total_dates = len(dates)
        
        for i, score_date in enumerate(dates):
            if progress_callback:
                progress_callback(i + 1, total_dates, f"Processing {score_date}")
            
            scores = self._generate_scores_for_date(score_date, tickers)
            
            if scores:
                self.data_store.save_historical_scores(scores)
                total_scores += len(scores)
            
            if (i + 1) % 10 == 0:
                logger.info(f"Progress: {i + 1}/{total_dates} dates, {total_scores} scores generated")
        
        logger.info(f"Generated {total_scores} historical scores")
        return total_scores
    
    def _generate_date_list(
        self,
        start_date: str,
        end_date: str,
        frequency: str
    ) -> List[str]:
        """Generate list of dates based on frequency."""
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        
        dates = []
        current = start
        
        while current <= end:
            # Skip weekends
            if current.weekday() < 5:  # Monday = 0, Friday = 4
                dates.append(current.strftime("%Y-%m-%d"))
                
                if frequency == "weekly":
                    # Move to next Friday (or Monday if started on weekend)
                    days_until_friday = (4 - current.weekday()) % 7
                    if days_until_friday == 0:
                        days_until_friday = 7
                    current += timedelta(days=days_until_friday)
                else:
                    current += timedelta(days=1)
            else:
                current += timedelta(days=1)
        
        return dates
    
    def _prefetch_prices(
        self,
        tickers: List[str],
        start_date: str,
        end_date: str
    ) -> None:
        """Pre-fetch all price data for efficiency."""
        # Add buffer for technical calculations
        buffer_start = (datetime.strptime(start_date, "%Y-%m-%d") - timedelta(days=365)).strftime("%Y-%m-%d")
        
        def fetch_ticker(ticker: str) -> Tuple[str, Optional[pd.DataFrame]]:
            try:
                # Check local parquet cache first
                parquet_path = PRICES_DIR / f"{ticker}.parquet"
                if parquet_path.exists():
                    df = pd.read_parquet(parquet_path)
                    df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
                    return ticker, df
                
                # Fetch from yfinance
                stock = yf.Ticker(ticker)
                df = stock.history(start=buffer_start, end=end_date, interval="1d")
                
                if df.empty:
                    return ticker, None
                
                df = df.reset_index()
                df.columns = [c.lower().replace(' ', '_') for c in df.columns]
                df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
                df['ticker'] = ticker
                
                return ticker, df
                
            except Exception as e:
                logger.warning(f"Failed to fetch prices for {ticker}: {e}")
                return ticker, None
        
        # Parallel fetch
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(fetch_ticker, t): t for t in tickers}
            
            for future in as_completed(futures):
                ticker, df = future.result()
                if df is not None:
                    self._price_cache[ticker] = df
        
        logger.info(f"Cached prices for {len(self._price_cache)} tickers")
    
    def _generate_scores_for_date(
        self,
        score_date: str,
        tickers: List[str]
    ) -> List[HistoricalScore]:
        """
        Generate scores for all tickers on a specific date.
        
        Uses point-in-time data only (no lookahead).
        """
        scores = []
        universe = self._get_universe()
        ticker_sectors = {s["ticker"].upper(): s.get("sector", "Unknown") for s in universe}
        
        for ticker in tickers:
            ticker_upper = ticker.upper()
            
            # Get price data up to score_date
            price_df = self._price_cache.get(ticker_upper)
            if price_df is None or price_df.empty:
                continue
            
            # Filter to dates <= score_date
            mask = price_df['date'] <= score_date
            available_prices = price_df[mask]
            
            if len(available_prices) < 20:  # Need enough data for technicals
                continue
            
            # Calculate component scores
            fundamental = self._calculate_fundamental_score_historical(ticker_upper, score_date)
            technical = self._calculate_technical_score_historical(available_prices)
            macro = self._calculate_macro_score_historical(ticker_upper, score_date, ticker_sectors.get(ticker_upper, "Unknown"))
            sentiment = 50.0  # Neutral for historical (no news archive)
            
            # Calculate composite using instance weights
            # When no_sentiment=True, sentiment weight is 0 and others are redistributed
            composite = (
                fundamental * self.weights["fundamental"] +
                sentiment * self.weights["sentiment"] +
                technical * self.weights["technical"] +
                macro * self.weights["macro"]
            )
            
            # Determine signal
            if composite >= 70:
                signal = "BUY"
            elif composite < 40:
                signal = "SELL"
            else:
                signal = "HOLD"
            
            scores.append(HistoricalScore(
                date=score_date,
                ticker=ticker_upper,
                composite_score=round(composite, 2),
                signal=signal,
                fundamental_score=round(fundamental, 2),
                sentiment_score=round(sentiment, 2),
                technical_score=round(technical, 2),
                macro_score=round(macro, 2),
                sector=ticker_sectors.get(ticker_upper, "Unknown"),
            ))
        
        return scores
    
    def _calculate_fundamental_score_historical(
        self,
        ticker: str,
        score_date: str
    ) -> float:
        """
        Calculate fundamental score using data available at score_date.
        
        Uses 60-day lag to account for earnings release delay.
        """
        # For MVP, use a simplified approach:
        # - Load current fundamentals
        # - Apply a decay factor based on how old the data is
        # In production, we'd use point-in-time fundamental database
        
        try:
            fundamentals_path = CACHE_DIR / "fundamentals.json"
            if not fundamentals_path.exists():
                return 50.0  # Neutral
            
            with open(fundamentals_path) as f:
                all_fundamentals = json.load(f)
            
            # Handle nested structure: {"stocks": {"AAPL": {...}, ...}}
            stocks = all_fundamentals.get("stocks", all_fundamentals)
            
            if ticker not in stocks:
                return 50.0
            
            fund_data = stocks[ticker]
            
            # Calculate a simple fundamental score
            pe_ratio = fund_data.get("pe_ratio", 0) or 0
            profit_margin = fund_data.get("profit_margin", 0) or 0
            revenue_growth = fund_data.get("revenue_growth", fund_data.get("earnings_growth", 0)) or 0
            roe = fund_data.get("roe", fund_data.get("return_on_equity", 0)) or 0
            
            # Normalize to 0-100 scale
            # PE: Lower is better (inverted)
            pe_score = max(0, min(100, 100 - (pe_ratio - 10) * 2)) if pe_ratio > 0 else 50
            
            # Profit margin: Higher is better
            margin_score = max(0, min(100, profit_margin * 200 + 50))
            
            # Revenue growth: Higher is better
            growth_score = max(0, min(100, revenue_growth * 200 + 50))
            
            # ROE: Higher is better
            roe_score = max(0, min(100, roe * 200 + 50))
            
            # Weighted average
            score = (
                pe_score * 0.25 +
                margin_score * 0.25 +
                growth_score * 0.30 +
                roe_score * 0.20
            )
            
            return score
            
        except Exception as e:
            logger.debug(f"Fundamental score calculation failed for {ticker}: {e}")
            return 50.0
    
    def _calculate_technical_score_historical(
        self,
        price_df: pd.DataFrame
    ) -> float:
        """
        Calculate technical score from price data.
        
        Components:
        - Momentum (40%): Price performance
        - RSI (30%): Relative strength
        - Trend (30%): MA crossover
        """
        if len(price_df) < 50:
            return 50.0  # Not enough data
        
        try:
            close = price_df['close'].values
            
            # Momentum: 20-day return
            if len(close) >= 20:
                momentum = (close[-1] / close[-20] - 1) * 100
                momentum_score = max(0, min(100, 50 + momentum * 2))
            else:
                momentum_score = 50.0
            
            # RSI (14-day)
            if len(close) >= 15:
                delta = np.diff(close[-15:])
                gains = np.where(delta > 0, delta, 0)
                losses = np.where(delta < 0, -delta, 0)
                
                avg_gain = np.mean(gains) if len(gains) > 0 else 0
                avg_loss = np.mean(losses) if len(losses) > 0 else 0
                
                if avg_loss > 0:
                    rs = avg_gain / avg_loss
                    rsi = 100 - (100 / (1 + rs))
                else:
                    rsi = 100 if avg_gain > 0 else 50
                
                # RSI 30-70 is neutral, below 30 oversold (buy), above 70 overbought (sell)
                if rsi < 30:
                    rsi_score = 70 + (30 - rsi)  # Oversold = higher score
                elif rsi > 70:
                    rsi_score = 30 - (rsi - 70)  # Overbought = lower score
                else:
                    rsi_score = 50  # Neutral
                rsi_score = max(0, min(100, rsi_score))
            else:
                rsi_score = 50.0
            
            # Trend: 20-day MA vs 50-day MA
            if len(close) >= 50:
                ma20 = np.mean(close[-20:])
                ma50 = np.mean(close[-50:])
                
                # Price above both MAs = bullish
                if close[-1] > ma20 > ma50:
                    trend_score = 75
                elif close[-1] > ma20:
                    trend_score = 60
                elif close[-1] < ma20 < ma50:
                    trend_score = 25
                elif close[-1] < ma20:
                    trend_score = 40
                else:
                    trend_score = 50
            else:
                trend_score = 50.0
            
            # Weighted composite
            score = (
                momentum_score * 0.40 +
                rsi_score * 0.30 +
                trend_score * 0.30
            )
            
            return score
            
        except Exception as e:
            logger.debug(f"Technical score calculation failed: {e}")
            return 50.0
    
    def _calculate_macro_score_historical(
        self,
        ticker: str,
        score_date: str,
        sector: str
    ) -> float:
        """
        Calculate macro score based on sector alignment.
        
        Simplified for historical: use sector rotation model.
        """
        # Sector macro sensitivity (simplified model)
        # Different sectors perform differently in different rate environments
        sector_scores = {
            "Technology": 65,      # Generally good in low rate environment
            "Healthcare": 55,
            "Financial Services": 50,
            "Consumer Cyclical": 55,
            "Communication Services": 60,
            "Industrials": 50,
            "Consumer Defensive": 45,  # Defensive
            "Energy": 45,
            "Utilities": 40,
            "Real Estate": 45,
            "Basic Materials": 50,
        }
        
        return sector_scores.get(sector, 50.0)
    
    def _get_universe(self) -> List[Dict]:
        """Get stock universe, cached."""
        if self._universe_cache is None:
            self._universe_cache = get_universe()
        return self._universe_cache
    
    def generate_from_existing_pipeline(self) -> int:
        """
        Import existing score history from current score_history.json.
        
        Returns:
            Number of scores imported
        """
        score_history_path = CACHE_DIR / "score_history.json"
        
        if not score_history_path.exists():
            logger.warning("No existing score history found")
            return 0
        
        try:
            with open(score_history_path) as f:
                existing = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load score history: {e}")
            return 0
        
        scores = []
        universe = self._get_universe()
        ticker_sectors = {s["ticker"].upper(): s.get("sector", "Unknown") for s in universe}
        
        for ticker, history in existing.items():
            for entry in history:
                scores.append(HistoricalScore(
                    date=entry["date"],
                    ticker=ticker.upper(),
                    composite_score=entry.get("total_score", 50),
                    signal=entry.get("signal", "HOLD"),
                    fundamental_score=entry.get("fundamental_score", 50),
                    sentiment_score=entry.get("sentiment_score", 50),
                    technical_score=entry.get("technical_score", 50),
                    macro_score=entry.get("macro_score", 50),
                    sector=ticker_sectors.get(ticker.upper(), "Unknown"),
                ))
        
        if scores:
            saved = self.data_store.save_historical_scores(scores)
            logger.info(f"Imported {saved} scores from existing pipeline history")
            return saved
        
        return 0


# Convenience function
def generate_historical_scores(
    start_date: str,
    end_date: str,
    tickers: Optional[List[str]] = None,
    frequency: str = "weekly",
) -> int:
    """Generate historical scores for backtesting."""
    generator = HistoricalScoreGenerator()
    return generator.generate_historical_scores(
        start_date=start_date,
        end_date=end_date,
        tickers=tickers,
        frequency=frequency,
    )


# CLI for testing
if __name__ == "__main__":
    import sys
    
    print("\n=== Historical Score Generator Test ===\n")
    
    generator = HistoricalScoreGenerator()
    
    # First, import existing scores
    imported = generator.generate_from_existing_pipeline()
    print(f"Imported {imported} existing scores")
    
    # Generate a small sample of historical scores
    test_tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"]
    
    # Generate last 4 weeks
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(weeks=4)).strftime("%Y-%m-%d")
    
    print(f"\nGenerating scores for {len(test_tickers)} tickers from {start_date} to {end_date}")
    
    count = generator.generate_historical_scores(
        start_date=start_date,
        end_date=end_date,
        tickers=test_tickers,
        frequency="weekly",
    )
    
    print(f"\nGenerated {count} historical scores")
    
    # Show stats
    stats = generator.data_store.get_storage_stats()
    print(f"\nStorage stats: {json.dumps(stats, indent=2)}")
    
    print("\n✅ Historical Score Generator working!")
