"""
F12.5 IC Decay Analyzer

Measures how score predictive power decays over time.
Key question: Should we refresh scores daily, weekly, or less often?

Outputs:
- IC by day offset (1-5 days after score generation)
- Rolling IC over time (weekly IC trend)
- Optimal refresh frequency recommendation
- Statistical significance tests
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from scipy import stats
from loguru import logger

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest.data_store import (
    BacktestDataStore,
    HistoricalScore,
    get_data_store,
)


@dataclass
class ICDecayResult:
    """Results of IC decay analysis."""
    # IC by day offset
    ic_by_day: Dict[int, float]  # day 1-5 -> IC
    ic_by_day_std: Dict[int, float]  # standard deviation
    ic_by_day_count: Dict[int, int]  # sample count
    
    # Statistical significance
    ic_t_stats: Dict[int, float]
    ic_p_values: Dict[int, float]
    
    # Decay analysis
    decay_rate: float  # IC loss per day
    half_life_days: float  # Days until IC drops by 50%
    
    # Recommendation
    recommended_refresh_freq: str  # "daily", "mid-week", "weekly"
    refresh_reason: str
    
    # Time range
    start_date: str
    end_date: str
    weeks_analyzed: int
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RollingICResult:
    """Rolling IC over time."""
    dates: List[str]
    ic_values: List[float]
    ic_moving_avg: List[float]  # 4-week moving average
    trend: str  # "improving", "stable", "declining"
    trend_slope: float
    
    def to_dict(self) -> dict:
        return asdict(self)


class ICDecayAnalyzer:
    """
    Analyzes how score predictive power decays over time.
    
    Key metrics:
    1. IC by day offset: Does Monday's score predict Friday's returns?
    2. Rolling IC: Is predictive power stable over months?
    3. Decay rate: How fast does IC drop?
    """
    
    def __init__(self, data_store: Optional[BacktestDataStore] = None):
        self.data_store = data_store or get_data_store()
        self._price_cache: Dict[str, pd.DataFrame] = {}
    
    def analyze_ic_decay(
        self,
        start_date: str,
        end_date: str,
        min_stocks_per_day: int = 20,
    ) -> ICDecayResult:
        """
        Analyze how IC decays by day of week.
        
        Args:
            start_date: Analysis start date
            end_date: Analysis end date
            min_stocks_per_day: Minimum stocks needed for IC calculation
            
        Returns:
            ICDecayResult with decay metrics
        """
        logger.info(f"Analyzing IC decay from {start_date} to {end_date}")
        
        # Get historical scores
        scores_by_date = self.data_store.get_historical_scores(start_date, end_date)
        
        if not scores_by_date:
            logger.warning("No historical scores found")
            return self._empty_result(start_date, end_date)
        
        # Get all tickers
        all_tickers = set()
        for date_scores in scores_by_date.values():
            all_tickers.update(date_scores.keys())
        
        # Prefetch prices
        self._prefetch_prices(list(all_tickers), start_date, end_date)
        
        # Calculate IC for each day offset (1-5 days)
        ic_samples = {i: [] for i in range(1, 6)}
        
        sorted_dates = sorted(scores_by_date.keys())
        
        for score_date in sorted_dates:
            date_scores = scores_by_date[score_date]
            
            if len(date_scores) < min_stocks_per_day:
                continue
            
            for day_offset in range(1, 6):
                forward_date = self._add_trading_days(score_date, day_offset)
                
                scores_list = []
                returns_list = []
                
                for ticker, score in date_scores.items():
                    current_price = self._get_price(ticker, score_date)
                    forward_price = self._get_price(ticker, forward_date)
                    
                    if current_price and forward_price and current_price > 0:
                        fwd_return = (forward_price / current_price) - 1
                        scores_list.append(score.composite_score)
                        returns_list.append(fwd_return)
                
                if len(scores_list) >= min_stocks_per_day:
                    # HIGH FIX BT-002: Check variance before correlation (avoid NaN)
                    scores_arr = np.array(scores_list)
                    returns_arr = np.array(returns_list)
                    if np.std(scores_arr) > 1e-10 and np.std(returns_arr) > 1e-10:
                        ic, _ = stats.spearmanr(scores_arr, returns_arr)
                        if not np.isnan(ic):
                            ic_samples[day_offset].append(ic)
        
        # Aggregate results
        ic_by_day = {}
        ic_by_day_std = {}
        ic_by_day_count = {}
        ic_t_stats = {}
        ic_p_values = {}
        
        for day, samples in ic_samples.items():
            if samples:
                ic_by_day[day] = round(np.mean(samples), 4)
                ic_by_day_std[day] = round(np.std(samples), 4)
                ic_by_day_count[day] = len(samples)
                
                # T-test: is IC significantly different from 0?
                if len(samples) > 2:
                    t_stat, p_value = stats.ttest_1samp(samples, 0)
                    ic_t_stats[day] = round(t_stat, 2)
                    ic_p_values[day] = round(p_value, 4)
                else:
                    ic_t_stats[day] = 0
                    ic_p_values[day] = 1
            else:
                ic_by_day[day] = 0
                ic_by_day_std[day] = 0
                ic_by_day_count[day] = 0
                ic_t_stats[day] = 0
                ic_p_values[day] = 1
        
        # Calculate decay rate
        decay_rate, half_life = self._calculate_decay_metrics(ic_by_day)
        
        # Generate recommendation
        refresh_freq, reason = self._recommend_refresh_frequency(ic_by_day, ic_p_values)
        
        return ICDecayResult(
            ic_by_day=ic_by_day,
            ic_by_day_std=ic_by_day_std,
            ic_by_day_count=ic_by_day_count,
            ic_t_stats=ic_t_stats,
            ic_p_values=ic_p_values,
            decay_rate=round(decay_rate, 4),
            half_life_days=round(half_life, 1),
            recommended_refresh_freq=refresh_freq,
            refresh_reason=reason,
            start_date=start_date,
            end_date=end_date,
            weeks_analyzed=len(sorted_dates),
        )
    
    def analyze_rolling_ic(
        self,
        start_date: str,
        end_date: str,
        forward_days: int = 5,
        window_weeks: int = 4,
    ) -> RollingICResult:
        """
        Calculate rolling IC over time to detect trend changes.
        
        Args:
            start_date: Analysis start date
            end_date: Analysis end date
            forward_days: Days ahead to measure returns
            window_weeks: Moving average window
            
        Returns:
            RollingICResult with time series
        """
        logger.info(f"Calculating rolling IC from {start_date} to {end_date}")
        
        scores_by_date = self.data_store.get_historical_scores(start_date, end_date)
        
        if not scores_by_date:
            return RollingICResult([], [], [], "unknown", 0)
        
        all_tickers = set()
        for date_scores in scores_by_date.values():
            all_tickers.update(date_scores.keys())
        
        self._prefetch_prices(list(all_tickers), start_date, end_date)
        
        dates = []
        ic_values = []
        
        sorted_dates = sorted(scores_by_date.keys())
        
        for score_date in sorted_dates:
            date_scores = scores_by_date[score_date]
            forward_date = self._add_trading_days(score_date, forward_days)
            
            scores_list = []
            returns_list = []
            
            for ticker, score in date_scores.items():
                current_price = self._get_price(ticker, score_date)
                forward_price = self._get_price(ticker, forward_date)
                
                if current_price and forward_price and current_price > 0:
                    fwd_return = (forward_price / current_price) - 1
                    scores_list.append(score.composite_score)
                    returns_list.append(fwd_return)
            
            if len(scores_list) >= 20:
                # HIGH FIX BT-002: Check variance before correlation (avoid NaN)
                scores_arr = np.array(scores_list)
                returns_arr = np.array(returns_list)
                if np.std(scores_arr) > 1e-10 and np.std(returns_arr) > 1e-10:
                    ic, _ = stats.spearmanr(scores_arr, returns_arr)
                    if not np.isnan(ic):
                        dates.append(score_date)
                        ic_values.append(round(ic, 4))
        
        # Calculate moving average
        ic_moving_avg = []
        for i in range(len(ic_values)):
            start_idx = max(0, i - window_weeks + 1)
            window = ic_values[start_idx:i + 1]
            ic_moving_avg.append(round(np.mean(window), 4))
        
        # Determine trend
        if len(ic_moving_avg) >= 4:
            recent = ic_moving_avg[-4:]
            slope = (recent[-1] - recent[0]) / 4
            
            if slope > 0.005:
                trend = "improving"
            elif slope < -0.005:
                trend = "declining"
            else:
                trend = "stable"
        else:
            slope = 0
            trend = "insufficient_data"
        
        return RollingICResult(
            dates=dates,
            ic_values=ic_values,
            ic_moving_avg=ic_moving_avg,
            trend=trend,
            trend_slope=round(slope, 4),
        )
    
    def _calculate_decay_metrics(
        self,
        ic_by_day: Dict[int, float]
    ) -> Tuple[float, float]:
        """Calculate decay rate and half-life."""
        if not ic_by_day or len(ic_by_day) < 2:
            return 0, float('inf')
        
        days = sorted(ic_by_day.keys())
        ics = [ic_by_day[d] for d in days]
        
        if ics[0] <= 0:
            return 0, float('inf')
        
        # Linear decay rate (IC loss per day)
        decay_rate = (ics[0] - ics[-1]) / (days[-1] - days[0])
        
        # Half-life: days until IC drops by 50%
        if decay_rate > 0:
            half_life = (ics[0] * 0.5) / decay_rate
        else:
            half_life = float('inf')
        
        return decay_rate, half_life
    
    def _recommend_refresh_frequency(
        self,
        ic_by_day: Dict[int, float],
        p_values: Dict[int, float]
    ) -> Tuple[str, str]:
        """Generate refresh frequency recommendation."""
        if not ic_by_day:
            return "weekly", "Insufficient data for analysis"
        
        # Check when IC becomes insignificant (p > 0.05)
        significant_days = [d for d, p in p_values.items() if p < 0.05]
        
        if not significant_days:
            return "daily", "IC not statistically significant - consider model improvements"
        
        max_significant_day = max(significant_days)
        
        # Check IC threshold (0.03 is minimum useful)
        useful_days = [d for d, ic in ic_by_day.items() if ic > 0.03]
        
        if not useful_days:
            return "daily", "IC too low for reliable predictions"
        
        max_useful_day = max(useful_days)
        
        # Recommendation logic
        effective_days = min(max_significant_day, max_useful_day)
        
        if effective_days <= 2:
            return "daily", f"IC drops below useful threshold after day {effective_days}"
        elif effective_days <= 3:
            return "mid-week", f"IC remains useful through day {effective_days}, refresh Wednesday"
        else:
            return "weekly", f"IC remains useful through day {effective_days}, weekly refresh sufficient"
    
    def _prefetch_prices(self, tickers: List[str], start_date: str, end_date: str) -> None:
        """Prefetch price data."""
        import yfinance as yf
        
        prices_dir = Path(__file__).parent.parent.parent / "data" / "prices"
        
        for ticker in tickers:
            if ticker in self._price_cache:
                continue
            
            try:
                parquet_path = prices_dir / f"{ticker}.parquet"
                if parquet_path.exists():
                    df = pd.read_parquet(parquet_path)
                    df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
                    self._price_cache[ticker] = df
                    continue
                
                stock = yf.Ticker(ticker)
                df = stock.history(start=start_date, end=end_date, interval="1d")
                
                if not df.empty:
                    df = df.reset_index()
                    df.columns = [c.lower().replace(' ', '_') for c in df.columns]
                    df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
                    self._price_cache[ticker] = df
                    
            except Exception:
                pass
    
    def _get_price(self, ticker: str, date: str) -> Optional[float]:
        """Get price for ticker on date."""
        df = self._price_cache.get(ticker)
        if df is None:
            return None
        
        mask = df['date'] <= date
        filtered = df[mask]
        
        if filtered.empty:
            return None
        
        return float(filtered.iloc[-1]['close'])
    
    def _add_trading_days(self, date: str, days: int) -> str:
        """Add trading days to a date."""
        dt = datetime.strptime(date, "%Y-%m-%d")
        added = 0
        
        while added < days:
            dt += timedelta(days=1)
            if dt.weekday() < 5:
                added += 1
        
        return dt.strftime("%Y-%m-%d")
    
    def _empty_result(self, start_date: str, end_date: str) -> ICDecayResult:
        """Return empty result."""
        return ICDecayResult(
            ic_by_day={i: 0 for i in range(1, 6)},
            ic_by_day_std={i: 0 for i in range(1, 6)},
            ic_by_day_count={i: 0 for i in range(1, 6)},
            ic_t_stats={i: 0 for i in range(1, 6)},
            ic_p_values={i: 1 for i in range(1, 6)},
            decay_rate=0,
            half_life_days=0,
            recommended_refresh_freq="weekly",
            refresh_reason="No data available",
            start_date=start_date,
            end_date=end_date,
            weeks_analyzed=0,
        )


# Convenience function
def analyze_ic_decay(start_date: str, end_date: str) -> ICDecayResult:
    """Analyze IC decay for a date range."""
    analyzer = ICDecayAnalyzer()
    return analyzer.analyze_ic_decay(start_date, end_date)


# CLI for testing
if __name__ == "__main__":
    print("\n=== IC Decay Analyzer Test ===\n")
    
    analyzer = ICDecayAnalyzer()
    
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")
    
    print(f"Analyzing {start_date} to {end_date}...")
    
    result = analyzer.analyze_ic_decay(start_date, end_date)
    
    print("\nIC by Day Offset:")
    for day in range(1, 6):
        ic = result.ic_by_day.get(day, 0)
        p = result.ic_p_values.get(day, 1)
        sig = "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.1 else ""
        print(f"  Day {day}: IC = {ic:.4f} (p = {p:.4f}) {sig}")
    
    print(f"\nDecay Rate: {result.decay_rate:.4f} per day")
    print(f"Half-Life: {result.half_life_days:.1f} days")
    print(f"\nRecommendation: {result.recommended_refresh_freq}")
    print(f"Reason: {result.refresh_reason}")
    
    print("\n✅ IC Decay Analyzer working!")
