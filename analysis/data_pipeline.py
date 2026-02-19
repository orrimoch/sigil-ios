"""
REC-322: Data Pipeline for Memory Evaluation

Loads historical data, generates composite scores, and prepares train/test datasets.
"""

import sys
from pathlib import Path

# Add backend to path
ANALYSIS_DIR = Path(__file__).parent
PROJECT_ROOT = ANALYSIS_DIR.parent
BACKEND_SRC = PROJECT_ROOT / "backend" / "src"
sys.path.insert(0, str(BACKEND_SRC))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

import json
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from loguru import logger
import yfinance as yf


# Paths
DATA_DIR = PROJECT_ROOT / "backend" / "data"
ANALYSIS_DATA_DIR = ANALYSIS_DIR / "data"
HISTORICAL_SENTIMENT_PATH = DATA_DIR / "historical_sentiment.json"
OUTPUT_DB_PATH = ANALYSIS_DATA_DIR / "evaluation_data.db"


@dataclass
class WeeklyScore:
    """Score record for a ticker on a specific week."""
    ticker: str
    week_start: str
    fundamental_score: float
    sentiment_score: float
    technical_score: float
    macro_score: float
    composite_score: float
    signal: str  # BUY, HOLD, SELL
    price: float
    sector: str
    

@dataclass
class TradeOutcome:
    """Trade outcome measured N weeks after entry."""
    ticker: str
    entry_week: str
    entry_price: float
    exit_week: str
    exit_price: float
    return_pct: float
    holding_weeks: int


class DataPipeline:
    """
    Pipeline for loading and preparing historical data for memory evaluation.
    """
    
    def __init__(
        self,
        output_db: Path = OUTPUT_DB_PATH,
        sentiment_path: Path = HISTORICAL_SENTIMENT_PATH,
    ):
        self.output_db = output_db
        self.sentiment_path = sentiment_path
        self._sentiment_data: Optional[Dict] = None
        self._price_cache: Dict[str, pd.DataFrame] = {}
        
        # Score weights (from production)
        self.weights = {
            "fundamental": 0.35,
            "sentiment": 0.25,
            "technical": 0.20,
            "macro": 0.20,
        }
        
        # Signal thresholds
        self.buy_threshold = 70
        self.sell_threshold = 40
        
        # Ensure output directory exists
        self.output_db.parent.mkdir(parents=True, exist_ok=True)
    
    def load_sentiment_data(self) -> Dict:
        """Load historical sentiment scores."""
        if self._sentiment_data is None:
            logger.info(f"Loading sentiment data from {self.sentiment_path}")
            with open(self.sentiment_path) as f:
                data = json.load(f)
            self._sentiment_data = data.get("weekly_scores", {})
            logger.info(f"Loaded {len(self._sentiment_data)} tickers")
        return self._sentiment_data
    
    def get_sentiment_score(self, ticker: str, week_start: str) -> Optional[float]:
        """Get sentiment score for a ticker on a specific week."""
        sentiment = self.load_sentiment_data()
        if ticker not in sentiment:
            return None
        
        for entry in sentiment[ticker]:
            if entry["week_start"] == week_start:
                return entry["score"]
        return None
    
    def get_available_weeks(self) -> List[str]:
        """Get sorted list of all available weeks."""
        sentiment = self.load_sentiment_data()
        weeks = set()
        for ticker, scores in sentiment.items():
            for entry in scores:
                weeks.add(entry["week_start"])
        return sorted(weeks)
    
    def get_tickers_for_week(self, week_start: str) -> List[str]:
        """Get tickers with sentiment data for a specific week."""
        sentiment = self.load_sentiment_data()
        tickers = []
        for ticker, scores in sentiment.items():
            for entry in scores:
                if entry["week_start"] == week_start:
                    tickers.append(ticker)
                    break
        return tickers
    
    def fetch_price(self, ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
        """Fetch price data from cached parquet files or yfinance."""
        cache_key = f"{ticker}_{start_date}_{end_date}"
        if cache_key in self._price_cache:
            return self._price_cache[cache_key]
        
        # Try cached parquet first
        parquet_path = DATA_DIR / "prices" / f"{ticker}.parquet"
        try:
            if parquet_path.exists():
                df = pd.read_parquet(parquet_path)
                # Handle parquet structure: date is a column, not index
                if 'date' in df.columns:
                    df['date'] = pd.to_datetime(df['date']).dt.tz_localize(None)
                    df = df.set_index('date')
                    # Rename columns to match yfinance format
                    df = df.rename(columns={
                        'open': 'Open', 'high': 'High', 'low': 'Low',
                        'close': 'Close', 'volume': 'Volume'
                    })
                # Convert date strings to datetime for comparison
                start_dt = pd.to_datetime(start_date)
                end_dt = pd.to_datetime(end_date)
                # Filter by date range
                df = df[(df.index >= start_dt) & (df.index <= end_dt)]
                if len(df) > 0:
                    self._price_cache[cache_key] = df
                    return df
        except Exception as e:
            logger.debug(f"Parquet load failed for {ticker}: {e}")
        
        # Fallback to yfinance
        try:
            df = yf.download(
                ticker,
                start=start_date,
                end=end_date,
                progress=False,
                auto_adjust=True,
            )
            self._price_cache[cache_key] = df
            return df
        except Exception as e:
            logger.warning(f"Failed to fetch {ticker}: {e}")
            return pd.DataFrame()
    
    def calculate_technical_score(self, prices: pd.DataFrame) -> float:
        """
        Calculate technical score based on price momentum.
        Simplified version for historical data.
        """
        if len(prices) < 20:
            return 50.0  # Neutral if not enough data
        
        try:
            # Handle multi-index columns from yfinance
            if isinstance(prices.columns, pd.MultiIndex):
                close = prices["Close"].iloc[:, 0] if len(prices["Close"].shape) > 1 else prices["Close"]
            else:
                close = prices["Close"]
            
            # Ensure we have scalar values
            close = close.squeeze() if hasattr(close, 'squeeze') else close
            
            # 20-day momentum
            momentum = float((close.iloc[-1] / close.iloc[-20] - 1) * 100)
            
            # RSI-like calculation
            delta = close.diff()
            gain = delta.where(delta > 0, 0).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = float(gain.iloc[-1]) / (float(loss.iloc[-1]) + 1e-10)
            rsi = 100 - (100 / (1 + rs))
            
            # Combine into score (0-100)
            momentum_score = min(100, max(0, 50 + momentum * 2))
            
            # Weight: 60% RSI, 40% momentum
            score = rsi * 0.6 + momentum_score * 0.4
            return float(np.clip(score, 0, 100))
        except Exception as e:
            logger.warning(f"Technical score calculation failed: {e}")
            return 50.0
    
    def calculate_fundamental_score(self, ticker: str) -> float:
        """
        Placeholder fundamental score.
        In production, this uses financial ratios, earnings, etc.
        For historical backtesting, we use a proxy based on market cap tier.
        """
        # For now, return moderate score - can be enhanced later
        # TODO: Load from cached fundamentals if available
        return 60.0
    
    def calculate_macro_score(self, week_start: str) -> float:
        """
        Calculate macro score based on market conditions.
        Uses VIX as a proxy for market stress.
        """
        try:
            # Fetch VIX for the period
            end_date = datetime.strptime(week_start, "%Y-%m-%d") + timedelta(days=7)
            vix = yf.download(
                "^VIX",
                start=week_start,
                end=end_date.strftime("%Y-%m-%d"),
                progress=False,
            )
            if len(vix) > 0:
                # Handle multi-index columns
                if isinstance(vix.columns, pd.MultiIndex):
                    close_col = vix["Close"].iloc[:, 0] if len(vix["Close"].shape) > 1 else vix["Close"]
                else:
                    close_col = vix["Close"]
                vix_level = float(close_col.iloc[-1])
                # Lower VIX = higher score (calmer markets)
                score = max(0, min(100, 100 - (vix_level - 12) * 3))
                return float(score)
        except Exception as e:
            logger.warning(f"Failed to fetch VIX: {e}")
        
        return 60.0  # Neutral fallback
    
    def calculate_composite_score(
        self,
        fundamental: float,
        sentiment: float,
        technical: float,
        macro: float,
    ) -> Tuple[float, str]:
        """Calculate composite score and signal."""
        score = (
            fundamental * self.weights["fundamental"] +
            sentiment * self.weights["sentiment"] +
            technical * self.weights["technical"] +
            macro * self.weights["macro"]
        )
        
        if score >= self.buy_threshold:
            signal = "BUY"
        elif score <= self.sell_threshold:
            signal = "SELL"
        else:
            signal = "HOLD"
        
        return score, signal
    
    def get_sector(self, ticker: str) -> str:
        """Get sector for a ticker."""
        try:
            info = yf.Ticker(ticker).info
            return info.get("sector", "Unknown")
        except:
            return "Unknown"
    
    def generate_weekly_scores(
        self,
        weeks: Optional[List[str]] = None,
        tickers: Optional[List[str]] = None,
        progress_callback=None,
    ) -> List[WeeklyScore]:
        """
        Generate composite scores for all tickers across all weeks.
        """
        if weeks is None:
            weeks = self.get_available_weeks()
        
        if tickers is None:
            sentiment = self.load_sentiment_data()
            tickers = list(sentiment.keys())
        
        scores = []
        total = len(weeks) * len(tickers)
        processed = 0
        
        # Cache sectors
        sector_cache = {}
        
        logger.info(f"Generating scores for {len(weeks)} weeks, {len(tickers)} tickers")
        
        for week in weeks:
            week_date = datetime.strptime(week, "%Y-%m-%d")
            price_start = (week_date - timedelta(days=30)).strftime("%Y-%m-%d")
            price_end = (week_date + timedelta(days=7)).strftime("%Y-%m-%d")
            
            # Get macro score once per week
            macro_score = self.calculate_macro_score(week)
            
            for ticker in tickers:
                processed += 1
                if progress_callback and processed % 100 == 0:
                    progress_callback(processed, total)
                
                # Get sentiment
                sentiment_score = self.get_sentiment_score(ticker, week)
                if sentiment_score is None:
                    continue  # Skip if no sentiment data for this week
                
                # Get prices
                prices = self.fetch_price(ticker, price_start, price_end)
                if len(prices) < 5:
                    continue
                
                # Calculate scores
                fundamental_score = self.calculate_fundamental_score(ticker)
                technical_score = self.calculate_technical_score(prices)
                
                # Composite
                composite, signal = self.calculate_composite_score(
                    fundamental_score,
                    sentiment_score,
                    technical_score,
                    macro_score,
                )
                
                # Get current price
                try:
                    # Handle multi-index columns
                    if isinstance(prices.columns, pd.MultiIndex):
                        close_col = prices["Close"].iloc[:, 0] if len(prices["Close"].shape) > 1 else prices["Close"]
                    else:
                        close_col = prices["Close"]
                    close_col = close_col.squeeze() if hasattr(close_col, 'squeeze') else close_col
                    
                    week_prices = close_col[close_col.index >= week]
                    current_price = float(week_prices.iloc[0]) if len(week_prices) > 0 else float(close_col.iloc[-1])
                except Exception as e:
                    logger.debug(f"Price extraction failed for {ticker}: {e}")
                    current_price = 0.0
                
                # Get sector (cached)
                if ticker not in sector_cache:
                    sector_cache[ticker] = self.get_sector(ticker)
                sector = sector_cache[ticker]
                
                scores.append(WeeklyScore(
                    ticker=ticker,
                    week_start=week,
                    fundamental_score=fundamental_score,
                    sentiment_score=sentiment_score,
                    technical_score=technical_score,
                    macro_score=macro_score,
                    composite_score=composite,
                    signal=signal,
                    price=current_price,
                    sector=sector,
                ))
        
        logger.info(f"Generated {len(scores)} score records")
        return scores
    
    def calculate_outcomes(
        self,
        scores: List[WeeklyScore],
        holding_weeks: int = 4,
    ) -> List[TradeOutcome]:
        """
        Calculate trade outcomes for BUY signals.
        """
        outcomes = []
        
        # Group scores by ticker for efficient price lookup
        by_ticker = {}
        for s in scores:
            if s.ticker not in by_ticker:
                by_ticker[s.ticker] = {}
            by_ticker[s.ticker][s.week_start] = s
        
        weeks = sorted(set(s.week_start for s in scores))
        
        for score in scores:
            if score.signal != "BUY":
                continue
            
            entry_week = score.week_start
            entry_idx = weeks.index(entry_week)
            exit_idx = entry_idx + holding_weeks
            
            if exit_idx >= len(weeks):
                continue  # Not enough future data
            
            exit_week = weeks[exit_idx]
            
            # Get exit price
            exit_score = by_ticker.get(score.ticker, {}).get(exit_week)
            if exit_score is None:
                continue
            
            if score.price > 0 and exit_score.price > 0:
                return_pct = (exit_score.price / score.price - 1) * 100
                
                outcomes.append(TradeOutcome(
                    ticker=score.ticker,
                    entry_week=entry_week,
                    entry_price=score.price,
                    exit_week=exit_week,
                    exit_price=exit_score.price,
                    return_pct=return_pct,
                    holding_weeks=holding_weeks,
                ))
        
        logger.info(f"Calculated {len(outcomes)} trade outcomes")
        return outcomes
    
    def save_to_db(
        self,
        scores: List[WeeklyScore],
        outcomes: List[TradeOutcome],
    ):
        """Save scores and outcomes to SQLite database."""
        conn = sqlite3.connect(self.output_db)
        
        # Create tables
        conn.execute("""
            CREATE TABLE IF NOT EXISTS weekly_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT,
                week_start TEXT,
                fundamental_score REAL,
                sentiment_score REAL,
                technical_score REAL,
                macro_score REAL,
                composite_score REAL,
                signal TEXT,
                price REAL,
                sector TEXT,
                UNIQUE(ticker, week_start)
            )
        """)
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS trade_outcomes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT,
                entry_week TEXT,
                entry_price REAL,
                exit_week TEXT,
                exit_price REAL,
                return_pct REAL,
                holding_weeks INTEGER,
                UNIQUE(ticker, entry_week)
            )
        """)
        
        # Insert scores
        for s in scores:
            conn.execute("""
                INSERT OR REPLACE INTO weekly_scores
                (ticker, week_start, fundamental_score, sentiment_score,
                 technical_score, macro_score, composite_score, signal, price, sector)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                s.ticker, s.week_start, s.fundamental_score, s.sentiment_score,
                s.technical_score, s.macro_score, s.composite_score, s.signal,
                s.price, s.sector,
            ))
        
        # Insert outcomes
        for o in outcomes:
            conn.execute("""
                INSERT OR REPLACE INTO trade_outcomes
                (ticker, entry_week, entry_price, exit_week, exit_price,
                 return_pct, holding_weeks)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                o.ticker, o.entry_week, o.entry_price, o.exit_week,
                o.exit_price, o.return_pct, o.holding_weeks,
            ))
        
        conn.commit()
        conn.close()
        logger.info(f"Saved to {self.output_db}")
    
    def run(self, holding_weeks: int = 4) -> Tuple[List[WeeklyScore], List[TradeOutcome]]:
        """Run the full data pipeline."""
        logger.info("Starting data pipeline...")
        
        # Generate scores
        scores = self.generate_weekly_scores()
        
        # Calculate outcomes
        outcomes = self.calculate_outcomes(scores, holding_weeks)
        
        # Save to DB
        self.save_to_db(scores, outcomes)
        
        return scores, outcomes


def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Memory Evaluation Data Pipeline")
    parser.add_argument("--holding-weeks", type=int, default=4, help="Weeks to hold trades")
    parser.add_argument("--output", type=Path, default=OUTPUT_DB_PATH, help="Output DB path")
    args = parser.parse_args()
    
    pipeline = DataPipeline(output_db=args.output)
    scores, outcomes = pipeline.run(holding_weeks=args.holding_weeks)
    
    print(f"\nPipeline complete:")
    print(f"  Scores: {len(scores)}")
    print(f"  Outcomes: {len(outcomes)}")
    print(f"  Database: {args.output}")


if __name__ == "__main__":
    main()
