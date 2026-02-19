"""
REC-322: Data Pipeline V2 - Uses Pre-computed Historical Scores

Uses existing historical_scores.json from backtest module.
Much faster than computing from scratch.
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
BACKTEST_DIR = DATA_DIR / "backtest"
ANALYSIS_DATA_DIR = ANALYSIS_DIR / "data"
HISTORICAL_SCORES_PATH = BACKTEST_DIR / "historical_scores.json"
HISTORICAL_TRADES_PATH = BACKTEST_DIR / "backtest_trades.json"
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
    signal: str
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


class DataPipelineV2:
    """
    Pipeline using pre-computed historical scores.
    """
    
    def __init__(
        self,
        output_db: Path = OUTPUT_DB_PATH,
        historical_scores_path: Path = HISTORICAL_SCORES_PATH,
    ):
        self.output_db = output_db
        self.historical_scores_path = historical_scores_path
        self._scores_data: Optional[Dict] = None
        self._price_cache: Dict[str, pd.DataFrame] = {}
        
        # Ensure output directory exists
        self.output_db.parent.mkdir(parents=True, exist_ok=True)
    
    def load_historical_scores(self) -> Dict:
        """Load pre-computed historical scores."""
        if self._scores_data is None:
            logger.info(f"Loading historical scores from {self.historical_scores_path}")
            with open(self.historical_scores_path) as f:
                self._scores_data = json.load(f)
            logger.info(f"Loaded {len(self._scores_data)} weeks of scores")
        return self._scores_data
    
    def get_available_weeks(self) -> List[str]:
        """Get sorted list of all available weeks."""
        scores = self.load_historical_scores()
        return sorted(scores.keys())
    
    def get_week_scores(self, week: str) -> Dict[str, Dict]:
        """Get all scores for a specific week."""
        scores = self.load_historical_scores()
        return scores.get(week, {})
    
    def fetch_price(self, ticker: str, date: str) -> Optional[float]:
        """Fetch price for a ticker on a specific date."""
        cache_key = f"{ticker}"
        
        # Try cached parquet first
        parquet_path = DATA_DIR / "prices" / f"{ticker}.parquet"
        if parquet_path.exists() and cache_key not in self._price_cache:
            try:
                df = pd.read_parquet(parquet_path)
                if 'date' in df.columns:
                    df['date'] = pd.to_datetime(df['date']).dt.tz_localize(None)
                    df = df.set_index('date')
                self._price_cache[cache_key] = df
            except Exception as e:
                logger.debug(f"Parquet load failed for {ticker}: {e}")
        
        # Try to get price from cache
        if cache_key in self._price_cache:
            df = self._price_cache[cache_key]
            try:
                target_date = pd.to_datetime(date)
                # Find nearest date
                if target_date in df.index:
                    return float(df.loc[target_date, 'close' if 'close' in df.columns else 'Close'])
                # Find closest date within 7 days
                mask = abs((df.index - target_date).days) <= 7
                if mask.any():
                    closest = df[mask].index[0]
                    return float(df.loc[closest, 'close' if 'close' in df.columns else 'Close'])
            except Exception as e:
                logger.debug(f"Price lookup failed for {ticker} on {date}: {e}")
        
        return None
    
    def convert_to_weekly_scores(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[WeeklyScore]:
        """Convert historical scores to WeeklyScore objects."""
        scores_data = self.load_historical_scores()
        weeks = sorted(scores_data.keys())
        
        if start_date:
            weeks = [w for w in weeks if w >= start_date]
        if end_date:
            weeks = [w for w in weeks if w <= end_date]
        
        scores = []
        logger.info(f"Processing {len(weeks)} weeks...")
        
        for i, week in enumerate(weeks):
            if (i + 1) % 20 == 0:
                logger.info(f"  Week {i+1}/{len(weeks)}")
            
            week_data = scores_data[week]
            
            for ticker, data in week_data.items():
                # Get price (use cached if available)
                price = self.fetch_price(ticker, week)
                if price is None:
                    price = 0.0  # Will need to fetch later
                
                scores.append(WeeklyScore(
                    ticker=ticker,
                    week_start=week,
                    fundamental_score=data.get('fundamental_score', 50.0),
                    sentiment_score=data.get('sentiment_score', 50.0),
                    technical_score=data.get('technical_score', 50.0),
                    macro_score=data.get('macro_score', 50.0),
                    composite_score=data.get('composite_score', 50.0),
                    signal=data.get('signal', 'HOLD'),
                    price=price,
                    sector=data.get('sector', 'Unknown'),
                ))
        
        logger.info(f"Converted {len(scores)} score records")
        return scores
    
    def calculate_outcomes(
        self,
        scores: List[WeeklyScore],
        holding_weeks: int = 4,
    ) -> List[TradeOutcome]:
        """Calculate trade outcomes for BUY signals."""
        outcomes = []
        
        # Group scores by ticker and week
        by_ticker_week = {}
        for s in scores:
            key = (s.ticker, s.week_start)
            by_ticker_week[key] = s
        
        weeks = sorted(set(s.week_start for s in scores))
        week_index = {w: i for i, w in enumerate(weeks)}
        
        buy_signals = [s for s in scores if s.signal == 'BUY' and s.price > 0]
        logger.info(f"Processing {len(buy_signals)} BUY signals...")
        
        for s in buy_signals:
            entry_idx = week_index.get(s.week_start)
            if entry_idx is None:
                continue
            
            exit_idx = entry_idx + holding_weeks
            if exit_idx >= len(weeks):
                continue
            
            exit_week = weeks[exit_idx]
            exit_score = by_ticker_week.get((s.ticker, exit_week))
            
            if exit_score is None or exit_score.price <= 0:
                continue
            
            return_pct = (exit_score.price / s.price - 1) * 100
            
            outcomes.append(TradeOutcome(
                ticker=s.ticker,
                entry_week=s.week_start,
                entry_price=s.price,
                exit_week=exit_week,
                exit_price=exit_score.price,
                return_pct=return_pct,
                holding_weeks=holding_weeks,
            ))
        
        logger.info(f"Calculated {len(outcomes)} outcomes")
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
        logger.info(f"Saving {len(scores)} scores...")
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
        logger.info(f"Saving {len(outcomes)} outcomes...")
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
    
    def run(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        holding_weeks: int = 4,
    ) -> Tuple[List[WeeklyScore], List[TradeOutcome]]:
        """Run the full data pipeline."""
        logger.info("Starting data pipeline V2...")
        
        # Convert scores
        scores = self.convert_to_weekly_scores(start_date, end_date)
        
        # Calculate outcomes
        outcomes = self.calculate_outcomes(scores, holding_weeks)
        
        # Save to DB
        self.save_to_db(scores, outcomes)
        
        # Summary stats
        buy_count = sum(1 for s in scores if s.signal == 'BUY')
        sell_count = sum(1 for s in scores if s.signal == 'SELL')
        hold_count = sum(1 for s in scores if s.signal == 'HOLD')
        
        logger.info(f"Summary: BUY={buy_count}, HOLD={hold_count}, SELL={sell_count}")
        
        return scores, outcomes


def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Memory Evaluation Data Pipeline V2")
    parser.add_argument("--start", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", help="End date (YYYY-MM-DD)")
    parser.add_argument("--holding-weeks", type=int, default=4, help="Weeks to hold trades")
    parser.add_argument("--output", type=Path, default=OUTPUT_DB_PATH, help="Output DB path")
    args = parser.parse_args()
    
    pipeline = DataPipelineV2(output_db=args.output)
    scores, outcomes = pipeline.run(
        start_date=args.start,
        end_date=args.end,
        holding_weeks=args.holding_weeks,
    )
    
    print(f"\nPipeline complete:")
    print(f"  Scores: {len(scores)}")
    print(f"  Outcomes: {len(outcomes)}")
    print(f"  Database: {args.output}")


if __name__ == "__main__":
    main()
