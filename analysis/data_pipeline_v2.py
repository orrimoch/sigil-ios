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
    """Trade outcome with multi-horizon returns (1W, 1M, 3M)."""
    ticker: str
    entry_week: str
    entry_price: float
    # Multi-horizon returns
    return_1w: Optional[float] = None   # 1 week return
    return_1m: Optional[float] = None   # 4 week (1 month) return  
    return_3m: Optional[float] = None   # 12 week (3 month) return
    # Exit prices for each horizon
    price_1w: Optional[float] = None
    price_1m: Optional[float] = None
    price_3m: Optional[float] = None


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
    
    def backfill_prices_yfinance(
        self,
        tickers: List[str],
        start_date: str = "2018-01-01",
        end_date: str = "2022-12-31",
        batch_size: int = 20,
    ) -> int:
        """
        Backfill historical prices from yfinance.
        
        Efficient batch fetching: one yfinance call per ticker gets all weekly prices.
        Maps daily prices to weekly (Friday) buckets.
        """
        import time
        
        logger.info(f"Backfilling prices for {len(tickers)} tickers from {start_date} to {end_date}")
        
        # Get all week_starts from DB for mapping
        conn = sqlite3.connect(self.output_db)
        week_starts = set(row[0] for row in conn.execute(
            "SELECT DISTINCT week_start FROM weekly_scores WHERE week_start BETWEEN ? AND ?",
            (start_date, end_date)
        ).fetchall())
        conn.close()
        
        # Convert to dates and sort
        week_dates = sorted([datetime.strptime(w, "%Y-%m-%d").date() for w in week_starts])
        logger.info(f"Found {len(week_dates)} distinct weeks to fill")
        
        updated = 0
        conn = sqlite3.connect(self.output_db)
        
        for i, ticker in enumerate(tickers):
            if (i + 1) % 50 == 0:
                logger.info(f"Progress: {i + 1}/{len(tickers)} tickers ({updated} prices updated)")
            
            try:
                # Fetch full history for ticker
                stock = yf.Ticker(ticker)
                hist = stock.history(start=start_date, end=end_date, interval="1d")
                
                if hist.empty:
                    continue
                
                # Create date -> price mapping
                prices_by_date = {}
                for idx, row in hist.iterrows():
                    d = idx.date() if hasattr(idx, 'date') else idx
                    prices_by_date[d] = float(row["Close"])
                
                # For each week, find the Friday price (or closest trading day before)
                for week_date in week_dates:
                    # Try week date first, then look backwards for closest trading day
                    price = None
                    for delta in range(0, 7):  # Look back up to 7 days
                        check_date = week_date - timedelta(days=delta)
                        if check_date in prices_by_date:
                            price = prices_by_date[check_date]
                            break
                    
                    if price is None:
                        continue
                    
                    week_str = week_date.strftime("%Y-%m-%d")
                    
                    # Update if price is currently 0
                    result = conn.execute("""
                        UPDATE weekly_scores 
                        SET price = ?
                        WHERE ticker = ? 
                          AND week_start = ?
                          AND (price IS NULL OR price = 0)
                    """, (price, ticker, week_str))
                    
                    if result.rowcount > 0:
                        updated += result.rowcount
                
                conn.commit()
                
                # Rate limit
                if (i + 1) % batch_size == 0:
                    time.sleep(1)
                    
            except Exception as e:
                logger.warning(f"Failed to fetch {ticker}: {e}")
                continue
        
        conn.close()
        logger.info(f"Backfilled {updated} prices")
        return updated
    
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
    ) -> List[TradeOutcome]:
        """Calculate multi-horizon trade outcomes (1W, 1M, 3M) for BUY signals."""
        outcomes = []
        
        # Horizon definitions (in weeks)
        HORIZONS = {
            '1w': 1,   # 1 week
            '1m': 4,   # 4 weeks (~1 month)
            '3m': 12,  # 12 weeks (~3 months)
        }
        
        # Group scores by ticker and week
        by_ticker_week = {}
        for s in scores:
            key = (s.ticker, s.week_start)
            by_ticker_week[key] = s
        
        weeks = sorted(set(s.week_start for s in scores))
        week_index = {w: i for i, w in enumerate(weeks)}
        
        buy_signals = [s for s in scores if s.signal == 'BUY' and s.price > 0]
        logger.info(f"Processing {len(buy_signals)} BUY signals for multi-horizon returns...")
        
        for s in buy_signals:
            entry_idx = week_index.get(s.week_start)
            if entry_idx is None:
                continue
            
            # Calculate returns for each horizon
            returns = {}
            prices = {}
            has_any_return = False
            
            for horizon_name, horizon_weeks in HORIZONS.items():
                exit_idx = entry_idx + horizon_weeks
                if exit_idx >= len(weeks):
                    continue
                
                exit_week = weeks[exit_idx]
                exit_score = by_ticker_week.get((s.ticker, exit_week))
                
                if exit_score is None or exit_score.price <= 0:
                    continue
                
                return_pct = (exit_score.price / s.price - 1) * 100
                returns[horizon_name] = return_pct
                prices[horizon_name] = exit_score.price
                has_any_return = True
            
            # Only include if we have at least one return horizon
            if not has_any_return:
                continue
            
            outcomes.append(TradeOutcome(
                ticker=s.ticker,
                entry_week=s.week_start,
                entry_price=s.price,
                return_1w=returns.get('1w'),
                return_1m=returns.get('1m'),
                return_3m=returns.get('3m'),
                price_1w=prices.get('1w'),
                price_1m=prices.get('1m'),
                price_3m=prices.get('3m'),
            ))
        
        # Log statistics
        has_1w = sum(1 for o in outcomes if o.return_1w is not None)
        has_1m = sum(1 for o in outcomes if o.return_1m is not None)
        has_3m = sum(1 for o in outcomes if o.return_3m is not None)
        logger.info(f"Calculated {len(outcomes)} outcomes: 1W={has_1w}, 1M={has_1m}, 3M={has_3m}")
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
                return_1w REAL,
                return_1m REAL,
                return_3m REAL,
                price_1w REAL,
                price_1m REAL,
                price_3m REAL,
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
                (ticker, entry_week, entry_price, return_1w, return_1m, return_3m,
                 price_1w, price_1m, price_3m)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                o.ticker, o.entry_week, o.entry_price, 
                o.return_1w, o.return_1m, o.return_3m,
                o.price_1w, o.price_1m, o.price_3m,
            ))
        
        conn.commit()
        conn.close()
        logger.info(f"Saved to {self.output_db}")
    
    def run(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Tuple[List[WeeklyScore], List[TradeOutcome]]:
        """Run the full data pipeline with multi-horizon returns."""
        logger.info("Starting data pipeline V2...")
        
        # Convert scores
        scores = self.convert_to_weekly_scores(start_date, end_date)
        
        # Calculate multi-horizon outcomes (1W, 1M, 3M)
        outcomes = self.calculate_outcomes(scores)
        
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
    parser.add_argument("--output", type=Path, default=OUTPUT_DB_PATH, help="Output DB path")
    parser.add_argument("--backfill-prices", action="store_true", help="Backfill historical prices from yfinance")
    parser.add_argument("--backfill-start", default="2018-01-01", help="Backfill start date")
    parser.add_argument("--backfill-end", default="2022-12-31", help="Backfill end date")
    parser.add_argument("--recalc-outcomes", action="store_true", help="Recalculate outcomes after backfill")
    args = parser.parse_args()
    
    pipeline = DataPipelineV2(output_db=args.output)
    
    if args.backfill_prices:
        # Get unique tickers from DB
        conn = sqlite3.connect(args.output)
        tickers = [row[0] for row in conn.execute("SELECT DISTINCT ticker FROM weekly_scores WHERE price = 0 OR price IS NULL").fetchall()]
        conn.close()
        
        print(f"Backfilling prices for {len(tickers)} tickers...")
        updated = pipeline.backfill_prices_yfinance(
            tickers=tickers,
            start_date=args.backfill_start,
            end_date=args.backfill_end,
        )
        print(f"Updated {updated} prices")
        
        if args.recalc_outcomes:
            print("Recalculating multi-horizon outcomes...")
            # Reload scores from DB with updated prices
            conn = sqlite3.connect(args.output)
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM weekly_scores ORDER BY week_start, ticker").fetchall()
            conn.close()
            
            scores = []
            for row in rows:
                scores.append(WeeklyScore(
                    ticker=row["ticker"],
                    week_start=row["week_start"],
                    fundamental_score=row["fundamental_score"],
                    sentiment_score=row["sentiment_score"],
                    technical_score=row["technical_score"],
                    macro_score=row["macro_score"],
                    composite_score=row["composite_score"],
                    signal=row["signal"],
                    price=row["price"],
                    sector=row["sector"],
                ))
            
            outcomes = pipeline.calculate_outcomes(scores)
            
            # Save outcomes with multi-horizon returns
            conn = sqlite3.connect(args.output)
            conn.execute("DELETE FROM trade_outcomes")
            for o in outcomes:
                conn.execute("""
                    INSERT INTO trade_outcomes
                    (ticker, entry_week, entry_price, return_1w, return_1m, return_3m,
                     price_1w, price_1m, price_3m)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (o.ticker, o.entry_week, o.entry_price, 
                      o.return_1w, o.return_1m, o.return_3m,
                      o.price_1w, o.price_1m, o.price_3m))
            conn.commit()
            conn.close()
            print(f"Saved {len(outcomes)} outcomes")
        
        return
    
    scores, outcomes = pipeline.run(
        start_date=args.start,
        end_date=args.end,
    )
    
    print(f"\nPipeline complete:")
    print(f"  Scores: {len(scores)}")
    print(f"  Outcomes: {len(outcomes)}")
    print(f"  Database: {args.output}")


if __name__ == "__main__":
    main()
