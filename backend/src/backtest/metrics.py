"""
F12.4 Performance Metrics Calculator

Calculate comprehensive performance and validation metrics:

Core Metrics:
- Total Return, CAGR, Volatility, Sharpe Ratio, Max Drawdown, Win Rate

Score Validation Metrics:
- Score IC (Information Coefficient)
- Hit Rate (BUY signals that beat SPY)
- Quintile Spread (Top 20% vs Bottom 20%)

Benchmark Comparison:
- Alpha, Beta, Tracking Error
"""

import json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from scipy import stats
from loguru import logger
import yfinance as yf

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest.data_store import (
    BacktestDataStore,
    BacktestResult,
    EquityPoint,
    HistoricalScore,
    get_data_store,
)


# Cache directory
CACHE_DIR = Path(__file__).parent.parent.parent / "data"
PRICES_DIR = CACHE_DIR / "prices"


@dataclass
class PerformanceMetrics:
    """Complete set of performance metrics."""
    # Returns
    total_return: float
    cagr: float
    
    # Risk
    volatility: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    calmar_ratio: float
    
    # Trading
    win_rate: float
    profit_factor: float
    total_trades: int
    avg_holding_period_days: float
    
    # Benchmark
    benchmark_return: float
    alpha: float
    beta: float
    tracking_error: float
    information_ratio: float
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass 
class ScoreValidationMetrics:
    """Metrics specific to validating score effectiveness."""
    # Information Coefficient
    score_ic: float
    score_ic_t_stat: float
    score_ic_p_value: float
    
    # Hit Rate
    hit_rate: float  # % of BUY signals that beat benchmark
    hit_rate_by_score_bucket: Dict[str, float]  # e.g., "70-80": 0.55
    
    # Quintile Analysis
    quintile_returns: Dict[str, float]  # Q1 (top 20%) through Q5
    quintile_spread: float  # Q1 return - Q5 return
    
    # Signal Stability
    avg_score_change: float  # Average week-over-week score change
    signal_flip_rate: float  # % of stocks that change signal per week
    
    def to_dict(self) -> dict:
        return asdict(self)


class MetricsCalculator:
    """
    Calculates all performance and validation metrics.
    
    Can be used for:
    1. Backtest results analysis
    2. Live portfolio performance tracking
    3. Score validation studies
    """
    
    def __init__(self, data_store: Optional[BacktestDataStore] = None):
        self.data_store = data_store or get_data_store()
        self._benchmark_cache: Optional[pd.DataFrame] = None
        self._price_cache: Dict[str, pd.DataFrame] = {}
    
    def calculate_performance_metrics(
        self,
        equity_curve: List[EquityPoint],
        trades: List[dict],
        initial_capital: float,
        start_date: str,
        end_date: str,
        risk_free_rate: float = 0.04,
    ) -> PerformanceMetrics:
        """
        Calculate all performance metrics from equity curve and trades.
        
        Args:
            equity_curve: List of daily NAV points
            trades: List of trade records
            initial_capital: Starting capital
            start_date: Backtest start date
            end_date: Backtest end date
            risk_free_rate: Annual risk-free rate (default 4%)
            
        Returns:
            PerformanceMetrics dataclass
        """
        # Fetch benchmark
        self._fetch_benchmark(start_date, end_date)
        
        # Extract data
        navs = [ep.nav if isinstance(ep, EquityPoint) else ep['nav'] for ep in equity_curve]
        dates = [ep.date if isinstance(ep, EquityPoint) else ep['date'] for ep in equity_curve]
        
        if len(navs) < 2:
            return self._empty_metrics()
        
        # Calculate returns
        daily_returns = np.diff(navs) / navs[:-1]
        
        # Basic return metrics
        total_return = (navs[-1] / initial_capital) - 1
        
        # CAGR
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        years = (end - start).days / 365.25
        cagr = (navs[-1] / initial_capital) ** (1 / years) - 1 if years > 0 else 0
        
        # Volatility (annualized)
        volatility = np.std(daily_returns) * np.sqrt(252)
        
        # Sharpe Ratio
        daily_rf = risk_free_rate / 252
        excess_returns = daily_returns - daily_rf
        sharpe = (np.mean(excess_returns) / np.std(excess_returns)) * np.sqrt(252) if np.std(excess_returns) > 0 else 0
        
        # Sortino Ratio (uses downside deviation)
        negative_returns = daily_returns[daily_returns < 0]
        downside_dev = np.std(negative_returns) * np.sqrt(252) if len(negative_returns) > 0 else volatility
        sortino = (cagr - risk_free_rate) / downside_dev if downside_dev > 0 else 0
        
        # Max Drawdown
        peak = np.maximum.accumulate(navs)
        drawdowns = (navs - peak) / peak
        max_drawdown = np.min(drawdowns)
        
        # Calmar Ratio
        calmar = cagr / abs(max_drawdown) if max_drawdown < 0 else 0
        
        # Win Rate and Profit Factor
        win_rate, profit_factor, avg_holding = self._calculate_trade_metrics(trades)
        
        # Benchmark comparison
        benchmark_return, alpha, beta, tracking_error, info_ratio = self._calculate_benchmark_metrics(
            daily_returns, dates, start_date, end_date
        )
        
        return PerformanceMetrics(
            total_return=round(total_return, 4),
            cagr=round(cagr, 4),
            volatility=round(volatility, 4),
            sharpe_ratio=round(sharpe, 2),
            sortino_ratio=round(sortino, 2),
            max_drawdown=round(max_drawdown, 4),
            calmar_ratio=round(calmar, 2),
            win_rate=round(win_rate, 4),
            profit_factor=round(profit_factor, 2),
            total_trades=len(trades),
            avg_holding_period_days=round(avg_holding, 1),
            benchmark_return=round(benchmark_return, 4),
            alpha=round(alpha, 4),
            beta=round(beta, 2),
            tracking_error=round(tracking_error, 4),
            information_ratio=round(info_ratio, 2),
        )
    
    def calculate_score_validation_metrics(
        self,
        start_date: str,
        end_date: str,
        forward_period_days: int = 5,
    ) -> ScoreValidationMetrics:
        """
        Calculate metrics that validate score effectiveness.
        
        The key question: Do higher scores predict higher returns?
        
        Args:
            start_date: Analysis start date
            end_date: Analysis end date
            forward_period_days: Days ahead to measure returns (default 5 = 1 week)
            
        Returns:
            ScoreValidationMetrics dataclass
        """
        logger.info(f"Calculating score validation metrics from {start_date} to {end_date}")
        
        # Get historical scores
        scores_by_date = self.data_store.get_historical_scores(start_date, end_date)
        
        if not scores_by_date:
            return self._empty_validation_metrics()
        
        # Get all tickers
        all_tickers = set()
        for date_scores in scores_by_date.values():
            all_tickers.update(date_scores.keys())
        
        # Fetch prices
        self._prefetch_prices(list(all_tickers), start_date, end_date)
        
        # Fetch benchmark
        self._fetch_benchmark(start_date, end_date)
        
        # Calculate IC for each date
        ics = []
        hit_rates = []
        quintile_data = {f"Q{i}": [] for i in range(1, 6)}
        score_changes = []
        signal_flips = []
        
        sorted_dates = sorted(scores_by_date.keys())
        
        for i, score_date in enumerate(sorted_dates):
            # Get scores for this date
            date_scores = scores_by_date[score_date]
            
            if len(date_scores) < 10:
                continue
            
            # Calculate forward returns
            forward_date = self._add_trading_days(score_date, forward_period_days)
            
            scores_list = []
            returns_list = []
            benchmark_return = self._get_benchmark_return(score_date, forward_date)
            
            for ticker, score in date_scores.items():
                current_price = self._get_price(ticker, score_date)
                forward_price = self._get_price(ticker, forward_date)
                
                if current_price and forward_price and current_price > 0:
                    fwd_return = (forward_price / current_price) - 1
                    scores_list.append(score.composite_score)
                    returns_list.append(fwd_return)
                    
                    # Check if BUY signal beat benchmark
                    if score.signal == "BUY" and benchmark_return is not None:
                        hit_rates.append(1 if fwd_return > benchmark_return else 0)
            
            if len(scores_list) >= 10:
                # Calculate IC (correlation)
                ic, _ = stats.spearmanr(scores_list, returns_list)
                if not np.isnan(ic):
                    ics.append(ic)
                
                # Quintile analysis
                df = pd.DataFrame({'score': scores_list, 'return': returns_list})
                df['quintile'] = pd.qcut(df['score'], q=5, labels=['Q5', 'Q4', 'Q3', 'Q2', 'Q1'])
                
                for q in ['Q1', 'Q2', 'Q3', 'Q4', 'Q5']:
                    q_returns = df[df['quintile'] == q]['return'].values
                    if len(q_returns) > 0:
                        quintile_data[q].append(np.mean(q_returns))
            
            # Track score changes (compare to previous week)
            if i > 0:
                prev_date = sorted_dates[i - 1]
                prev_scores = scores_by_date.get(prev_date, {})
                
                changes = []
                flips = []
                
                for ticker, score in date_scores.items():
                    if ticker in prev_scores:
                        prev_score = prev_scores[ticker]
                        changes.append(abs(score.composite_score - prev_score.composite_score))
                        if score.signal != prev_score.signal:
                            flips.append(1)
                        else:
                            flips.append(0)
                
                if changes:
                    score_changes.append(np.mean(changes))
                if flips:
                    signal_flips.append(np.mean(flips))
        
        # Aggregate metrics
        avg_ic = np.mean(ics) if ics else 0
        ic_std = np.std(ics) if ics else 1
        ic_t_stat = avg_ic / (ic_std / np.sqrt(len(ics))) if len(ics) > 1 and ic_std > 0 else 0
        ic_p_value = 2 * (1 - stats.t.cdf(abs(ic_t_stat), len(ics) - 1)) if len(ics) > 1 else 1
        
        avg_hit_rate = np.mean(hit_rates) if hit_rates else 0.5
        
        # Hit rate by score bucket
        hit_by_bucket = self._calculate_hit_rate_by_bucket(scores_by_date, forward_period_days)
        
        # Quintile returns
        quintile_returns = {q: np.mean(returns) if returns else 0 for q, returns in quintile_data.items()}
        quintile_spread = quintile_returns['Q1'] - quintile_returns['Q5']
        
        avg_score_change = np.mean(score_changes) if score_changes else 0
        flip_rate = np.mean(signal_flips) if signal_flips else 0
        
        return ScoreValidationMetrics(
            score_ic=round(avg_ic, 4),
            score_ic_t_stat=round(ic_t_stat, 2),
            score_ic_p_value=round(ic_p_value, 4),
            hit_rate=round(avg_hit_rate, 4),
            hit_rate_by_score_bucket=hit_by_bucket,
            quintile_returns={k: round(v, 4) for k, v in quintile_returns.items()},
            quintile_spread=round(quintile_spread, 4),
            avg_score_change=round(avg_score_change, 2),
            signal_flip_rate=round(flip_rate, 4),
        )
    
    def calculate_ic_by_day_of_week(
        self,
        start_date: str,
        end_date: str,
    ) -> Dict[int, float]:
        """
        Calculate IC decay by day of week.
        
        Measures how score predictive power changes as days pass.
        
        Returns:
            Dict mapping day offset (1-5) to average IC
        """
        logger.info("Calculating IC by day of week...")
        
        scores_by_date = self.data_store.get_historical_scores(start_date, end_date)
        
        if not scores_by_date:
            return {}
        
        all_tickers = set()
        for date_scores in scores_by_date.values():
            all_tickers.update(date_scores.keys())
        
        self._prefetch_prices(list(all_tickers), start_date, end_date)
        
        ic_by_day = {i: [] for i in range(1, 6)}
        
        sorted_dates = sorted(scores_by_date.keys())
        
        for score_date in sorted_dates:
            date_scores = scores_by_date[score_date]
            
            if len(date_scores) < 10:
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
                
                if len(scores_list) >= 10:
                    ic, _ = stats.spearmanr(scores_list, returns_list)
                    if not np.isnan(ic):
                        ic_by_day[day_offset].append(ic)
        
        # Average ICs
        result = {}
        for day, ics in ic_by_day.items():
            result[day] = round(np.mean(ics), 4) if ics else 0
        
        return result
    
    def _calculate_trade_metrics(
        self,
        trades: List[dict]
    ) -> Tuple[float, float, float]:
        """Calculate win rate, profit factor, and average holding period."""
        if not trades:
            return 0.5, 1.0, 0.0
        
        # Group trades by ticker to match buys and sells
        trades_by_ticker = {}
        for t in trades:
            ticker = t.get('ticker', t.get('symbol'))
            if ticker not in trades_by_ticker:
                trades_by_ticker[ticker] = []
            trades_by_ticker[ticker].append(t)
        
        wins = 0
        losses = 0
        gross_profit = 0
        gross_loss = 0
        holding_periods = []
        
        for ticker, ticker_trades in trades_by_ticker.items():
            buys = [t for t in ticker_trades if t.get('side') == 'buy']
            sells = [t for t in ticker_trades if t.get('side') == 'sell']
            
            for sell in sells:
                # Find corresponding buy
                matching_buys = [b for b in buys if b.get('date', '') < sell.get('date', '')]
                if matching_buys:
                    buy = matching_buys[-1]
                    
                    buy_price = buy.get('price', 0)
                    sell_price = sell.get('price', 0)
                    qty = min(buy.get('quantity', 0), sell.get('quantity', 0))
                    
                    pnl = (sell_price - buy_price) * qty
                    
                    if pnl > 0:
                        wins += 1
                        gross_profit += pnl
                    else:
                        losses += 1
                        gross_loss += abs(pnl)
                    
                    # Calculate holding period
                    try:
                        buy_date = datetime.strptime(buy.get('date', ''), "%Y-%m-%d")
                        sell_date = datetime.strptime(sell.get('date', ''), "%Y-%m-%d")
                        holding_periods.append((sell_date - buy_date).days)
                    except:
                        pass
        
        total = wins + losses
        win_rate = wins / total if total > 0 else 0.5
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 2.0
        avg_holding = np.mean(holding_periods) if holding_periods else 0
        
        return win_rate, profit_factor, avg_holding
    
    def _calculate_benchmark_metrics(
        self,
        strategy_returns: np.ndarray,
        dates: List[str],
        start_date: str,
        end_date: str,
    ) -> Tuple[float, float, float, float, float]:
        """Calculate benchmark comparison metrics."""
        if self._benchmark_cache is None or len(self._benchmark_cache) < 2:
            return 0, 0, 1, 0, 0
        
        try:
            # Get benchmark returns for matching dates
            benchmark_df = self._benchmark_cache.set_index('date')
            benchmark_returns = []
            
            for i, date in enumerate(dates[:-1]):
                next_date = dates[i + 1]
                if date in benchmark_df.index and next_date in benchmark_df.index:
                    prev_close = benchmark_df.loc[date, 'close']
                    curr_close = benchmark_df.loc[next_date, 'close']
                    if prev_close > 0:
                        benchmark_returns.append((curr_close / prev_close) - 1)
            
            if len(benchmark_returns) != len(strategy_returns):
                # Truncate to match
                min_len = min(len(benchmark_returns), len(strategy_returns))
                benchmark_returns = benchmark_returns[:min_len]
                strategy_returns = strategy_returns[:min_len]
            
            if len(benchmark_returns) < 10:
                return 0, 0, 1, 0, 0
            
            benchmark_returns = np.array(benchmark_returns)
            
            # Total benchmark return
            benchmark_total = np.prod(1 + benchmark_returns) - 1
            strategy_total = np.prod(1 + strategy_returns) - 1
            
            # Alpha (simple)
            alpha = strategy_total - benchmark_total
            
            # Beta
            covariance = np.cov(strategy_returns, benchmark_returns)[0, 1]
            benchmark_var = np.var(benchmark_returns)
            beta = covariance / benchmark_var if benchmark_var > 0 else 1
            
            # Tracking Error
            excess_returns = strategy_returns - benchmark_returns
            tracking_error = np.std(excess_returns) * np.sqrt(252)
            
            # Information Ratio
            info_ratio = (alpha / tracking_error) if tracking_error > 0 else 0
            
            return benchmark_total, alpha, beta, tracking_error, info_ratio
            
        except Exception as e:
            logger.warning(f"Benchmark calculation failed: {e}")
            return 0, 0, 1, 0, 0
    
    def _calculate_hit_rate_by_bucket(
        self,
        scores_by_date: Dict,
        forward_days: int
    ) -> Dict[str, float]:
        """Calculate hit rate for different score buckets."""
        buckets = {
            "60-70": [],
            "70-80": [],
            "80-90": [],
            "90-100": [],
        }
        
        sorted_dates = sorted(scores_by_date.keys())
        
        for score_date in sorted_dates:
            date_scores = scores_by_date[score_date]
            forward_date = self._add_trading_days(score_date, forward_days)
            benchmark_return = self._get_benchmark_return(score_date, forward_date)
            
            for ticker, score in date_scores.items():
                if score.signal != "BUY":
                    continue
                
                current_price = self._get_price(ticker, score_date)
                forward_price = self._get_price(ticker, forward_date)
                
                if current_price and forward_price and benchmark_return is not None:
                    fwd_return = (forward_price / current_price) - 1
                    beat = 1 if fwd_return > benchmark_return else 0
                    
                    s = score.composite_score
                    if 60 <= s < 70:
                        buckets["60-70"].append(beat)
                    elif 70 <= s < 80:
                        buckets["70-80"].append(beat)
                    elif 80 <= s < 90:
                        buckets["80-90"].append(beat)
                    elif s >= 90:
                        buckets["90-100"].append(beat)
        
        return {k: round(np.mean(v), 4) if v else 0.5 for k, v in buckets.items()}
    
    def _fetch_benchmark(self, start_date: str, end_date: str) -> None:
        """Fetch SPY benchmark data."""
        if self._benchmark_cache is not None:
            return
        
        try:
            stock = yf.Ticker("SPY")
            df = stock.history(start=start_date, end=end_date, interval="1d")
            
            if not df.empty:
                df = df.reset_index()
                df.columns = [c.lower().replace(' ', '_') for c in df.columns]
                df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
                self._benchmark_cache = df
                
        except Exception as e:
            logger.warning(f"Failed to fetch benchmark: {e}")
    
    def _prefetch_prices(self, tickers: List[str], start_date: str, end_date: str) -> None:
        """Pre-fetch prices for all tickers."""
        for ticker in tickers:
            if ticker in self._price_cache:
                continue
            
            try:
                parquet_path = PRICES_DIR / f"{ticker}.parquet"
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
    
    def _get_benchmark_return(self, start_date: str, end_date: str) -> Optional[float]:
        """Get benchmark return between two dates."""
        if self._benchmark_cache is None:
            return None
        
        try:
            df = self._benchmark_cache
            
            start_mask = df['date'] <= start_date
            end_mask = df['date'] <= end_date
            
            start_data = df[start_mask]
            end_data = df[end_mask]
            
            if start_data.empty or end_data.empty:
                return None
            
            start_price = start_data.iloc[-1]['close']
            end_price = end_data.iloc[-1]['close']
            
            return (end_price / start_price) - 1
            
        except Exception:
            return None
    
    def _add_trading_days(self, date: str, days: int) -> str:
        """Add trading days to a date."""
        dt = datetime.strptime(date, "%Y-%m-%d")
        added = 0
        
        while added < days:
            dt += timedelta(days=1)
            if dt.weekday() < 5:  # Monday=0, Friday=4
                added += 1
        
        return dt.strftime("%Y-%m-%d")
    
    def _empty_metrics(self) -> PerformanceMetrics:
        """Return empty metrics."""
        return PerformanceMetrics(
            total_return=0, cagr=0, volatility=0, sharpe_ratio=0,
            sortino_ratio=0, max_drawdown=0, calmar_ratio=0,
            win_rate=0.5, profit_factor=1, total_trades=0,
            avg_holding_period_days=0, benchmark_return=0,
            alpha=0, beta=1, tracking_error=0, information_ratio=0,
        )
    
    def _empty_validation_metrics(self) -> ScoreValidationMetrics:
        """Return empty validation metrics."""
        return ScoreValidationMetrics(
            score_ic=0, score_ic_t_stat=0, score_ic_p_value=1,
            hit_rate=0.5, hit_rate_by_score_bucket={},
            quintile_returns={}, quintile_spread=0,
            avg_score_change=0, signal_flip_rate=0,
        )


# Convenience functions
def calculate_backtest_metrics(result: BacktestResult) -> PerformanceMetrics:
    """Calculate metrics for a completed backtest."""
    calc = MetricsCalculator()
    
    trades = get_data_store().get_trades(result.backtest_id)
    trades_dict = [t.to_dict() for t in trades]
    
    return calc.calculate_performance_metrics(
        equity_curve=result.equity_curve,
        trades=trades_dict,
        initial_capital=result.parameters.initial_capital,
        start_date=result.parameters.start_date,
        end_date=result.parameters.end_date,
    )


def validate_scores(start_date: str, end_date: str) -> ScoreValidationMetrics:
    """Validate score effectiveness over a period."""
    calc = MetricsCalculator()
    return calc.calculate_score_validation_metrics(start_date, end_date)


# CLI for testing
if __name__ == "__main__":
    print("\n=== Metrics Calculator Test ===\n")
    
    calc = MetricsCalculator()
    
    # Test IC by day of week
    print("Testing IC by day of week...")
    
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    
    ic_by_day = calc.calculate_ic_by_day_of_week(start_date, end_date)
    print(f"\nIC by day offset:")
    for day, ic in ic_by_day.items():
        print(f"  Day {day}: IC = {ic:.4f}")
    
    print("\n✅ Metrics Calculator working!")
