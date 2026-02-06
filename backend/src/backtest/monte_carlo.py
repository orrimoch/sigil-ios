"""
F12.12 Monte Carlo Simulation for Backtest Validation

Bootstrap resampling to assess statistical significance of backtest results.

Features:
- Bootstrap resampling of daily returns
- Confidence intervals for key metrics (Sharpe, CAGR, Max DD, Win Rate)
- P-value calculation for statistical significance
- Benchmark comparison (SPY) for alpha significance
- Progress logging for long simulations
"""

import numpy as np
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
from loguru import logger
import sys
import json

sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest.data_store import (
    BacktestDataStore,
    BacktestResult,
    EquityPoint,
    get_data_store,
)


@dataclass
class MetricStats:
    """Statistics for a single metric from Monte Carlo simulation."""
    observed: float
    mean: float
    std: float
    ci_lower: float  # 2.5 percentile
    ci_upper: float  # 97.5 percentile
    p_value: float   # P(random >= observed)
    is_significant: bool  # p < 0.05
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MonteCarloResult:
    """Complete result from Monte Carlo simulation."""
    n_simulations: int
    
    # Sharpe Ratio stats
    observed_sharpe: float
    sharpe_mean: float
    sharpe_std: float
    sharpe_ci_lower: float
    sharpe_ci_upper: float
    sharpe_p_value: float
    sharpe_is_significant: bool
    
    # CAGR stats
    observed_cagr: float
    cagr_mean: float
    cagr_std: float
    cagr_ci_lower: float
    cagr_ci_upper: float
    cagr_p_value: float
    cagr_is_significant: bool
    
    # Max Drawdown stats (note: lower is better, so p-value logic inverted)
    observed_max_dd: float
    max_dd_mean: float
    max_dd_std: float
    max_dd_ci_lower: float
    max_dd_ci_upper: float
    max_dd_p_value: float
    max_dd_is_significant: bool
    
    # Win Rate stats
    observed_win_rate: float
    win_rate_mean: float
    win_rate_std: float
    win_rate_ci_lower: float
    win_rate_ci_upper: float
    win_rate_p_value: float
    win_rate_is_significant: bool
    
    # Overall significance
    strategy_is_significant: bool  # All key metrics significant at 95%
    confidence_level: float = 0.95
    
    # Benchmark comparison
    benchmark_sharpe: Optional[float] = None
    alpha_p_value: Optional[float] = None
    alpha_is_significant: Optional[bool] = None
    
    # Simulation distribution samples (for visualization)
    sharpe_distribution: List[float] = field(default_factory=list)
    cagr_distribution: List[float] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        d = asdict(self)
        # Truncate distributions for API response (keep first 100 for histograms)
        d['sharpe_distribution'] = d['sharpe_distribution'][:100] if d['sharpe_distribution'] else []
        d['cagr_distribution'] = d['cagr_distribution'][:100] if d['cagr_distribution'] else []
        return d
    
    @classmethod
    def from_dict(cls, data: dict) -> "MonteCarloResult":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
    
    def summary(self) -> str:
        """Generate human-readable summary."""
        lines = [
            f"Monte Carlo Simulation Results ({self.n_simulations} simulations)",
            "=" * 60,
            "",
            f"Sharpe Ratio: {self.observed_sharpe:.3f}",
            f"  95% CI: [{self.sharpe_ci_lower:.3f}, {self.sharpe_ci_upper:.3f}]",
            f"  p-value: {self.sharpe_p_value:.4f} {'✓' if self.sharpe_is_significant else '✗'}",
            "",
            f"CAGR: {self.observed_cagr:.2%}",
            f"  95% CI: [{self.cagr_ci_lower:.2%}, {self.cagr_ci_upper:.2%}]",
            f"  p-value: {self.cagr_p_value:.4f} {'✓' if self.cagr_is_significant else '✗'}",
            "",
            f"Max Drawdown: {self.observed_max_dd:.2%}",
            f"  95% CI: [{self.max_dd_ci_lower:.2%}, {self.max_dd_ci_upper:.2%}]",
            f"  p-value: {self.max_dd_p_value:.4f} {'✓' if self.max_dd_is_significant else '✗'}",
            "",
            f"Win Rate: {self.observed_win_rate:.2%}",
            f"  95% CI: [{self.win_rate_ci_lower:.2%}, {self.win_rate_ci_upper:.2%}]",
            f"  p-value: {self.win_rate_p_value:.4f} {'✓' if self.win_rate_is_significant else '✗'}",
            "",
            "=" * 60,
            f"Strategy Significant: {'YES ✓' if self.strategy_is_significant else 'NO ✗'}",
        ]
        
        if self.alpha_p_value is not None:
            lines.extend([
                "",
                f"Alpha vs Benchmark: p={self.alpha_p_value:.4f}",
                f"  Significant: {'YES ✓' if self.alpha_is_significant else 'NO ✗'}",
            ])
        
        return "\n".join(lines)


class MonteCarloSimulator:
    """
    Monte Carlo simulation engine for backtest validation.
    
    Uses bootstrap resampling to generate synthetic return paths
    and assess statistical significance of observed metrics.
    
    The key question: Could this performance happen by chance?
    """
    
    def __init__(
        self,
        seed: Optional[int] = None,
        risk_free_rate: float = 0.04,
    ):
        """
        Initialize Monte Carlo simulator.
        
        Args:
            seed: Random seed for reproducibility (None for random)
            risk_free_rate: Annual risk-free rate for Sharpe calculation
        """
        self.seed = seed
        self.risk_free_rate = risk_free_rate
        self._rng = np.random.default_rng(seed)
    
    def run_simulation(
        self,
        daily_returns: np.ndarray,
        n_simulations: int = 1000,
        benchmark_returns: Optional[np.ndarray] = None,
        observed_win_rate: Optional[float] = None,
        progress_callback: Optional[callable] = None,
    ) -> MonteCarloResult:
        """
        Run Monte Carlo simulation on daily returns.
        
        Args:
            daily_returns: Array of daily returns (decimal, not percent)
            n_simulations: Number of bootstrap simulations
            benchmark_returns: Optional benchmark returns for alpha testing
            observed_win_rate: Actual win rate from trades (if available)
            progress_callback: Optional callback(current, total) for progress
            
        Returns:
            MonteCarloResult with all statistics
        """
        if len(daily_returns) < 20:
            raise ValueError(f"Insufficient data: {len(daily_returns)} returns. Need at least 20.")
        
        daily_returns = np.asarray(daily_returns, dtype=np.float64)
        
        # Remove any NaN or inf values
        valid_mask = np.isfinite(daily_returns)
        if not valid_mask.all():
            logger.warning(f"Removing {(~valid_mask).sum()} invalid return values")
            daily_returns = daily_returns[valid_mask]
        
        if len(daily_returns) < 20:
            raise ValueError(f"Insufficient valid data after cleaning: {len(daily_returns)} returns")
        
        logger.info(f"Running Monte Carlo simulation: {n_simulations} iterations on {len(daily_returns)} returns")
        
        # Calculate observed metrics
        observed_sharpe = self._calculate_sharpe(daily_returns)
        observed_cagr = self._calculate_cagr(daily_returns)
        observed_max_dd = self._calculate_max_drawdown(daily_returns)
        
        # Use provided win rate or estimate from returns
        if observed_win_rate is None:
            observed_win_rate = np.mean(daily_returns > 0)
        
        # Run bootstrap simulations
        sharpe_samples = []
        cagr_samples = []
        max_dd_samples = []
        win_rate_samples = []
        
        log_interval = max(1, n_simulations // 10)
        
        for i in range(n_simulations):
            # Bootstrap resample: sample with replacement
            resampled = self._bootstrap_resample(daily_returns)
            
            # Calculate metrics on resampled data
            sharpe_samples.append(self._calculate_sharpe(resampled))
            cagr_samples.append(self._calculate_cagr(resampled))
            max_dd_samples.append(self._calculate_max_drawdown(resampled))
            win_rate_samples.append(np.mean(resampled > 0))
            
            # Progress callback
            if progress_callback and (i + 1) % log_interval == 0:
                progress_callback(i + 1, n_simulations)
        
        sharpe_samples = np.array(sharpe_samples)
        cagr_samples = np.array(cagr_samples)
        max_dd_samples = np.array(max_dd_samples)
        win_rate_samples = np.array(win_rate_samples)
        
        # Calculate statistics for each metric
        sharpe_stats = self._calculate_stats(observed_sharpe, sharpe_samples, higher_is_better=True)
        cagr_stats = self._calculate_stats(observed_cagr, cagr_samples, higher_is_better=True)
        max_dd_stats = self._calculate_stats(observed_max_dd, max_dd_samples, higher_is_better=False)
        win_rate_stats = self._calculate_stats(observed_win_rate, win_rate_samples, higher_is_better=True)
        
        # Overall significance: Sharpe > 0 with p < 0.05
        strategy_is_significant = (
            sharpe_stats.is_significant and 
            observed_sharpe > 0 and
            win_rate_stats.p_value < 0.10  # Win rate at 90% confidence
        )
        
        # Benchmark comparison
        benchmark_sharpe = None
        alpha_p_value = None
        alpha_is_significant = None
        
        if benchmark_returns is not None and len(benchmark_returns) > 0:
            benchmark_returns = np.asarray(benchmark_returns, dtype=np.float64)
            valid_mask = np.isfinite(benchmark_returns)
            benchmark_returns = benchmark_returns[valid_mask]
            
            if len(benchmark_returns) >= 20:
                benchmark_sharpe = self._calculate_sharpe(benchmark_returns)
                
                # Test if strategy Sharpe > benchmark Sharpe
                alpha_p_value = self._calculate_alpha_pvalue(
                    daily_returns, 
                    benchmark_returns, 
                    n_simulations
                )
                alpha_is_significant = alpha_p_value < 0.05
        
        result = MonteCarloResult(
            n_simulations=n_simulations,
            
            observed_sharpe=round(observed_sharpe, 4),
            sharpe_mean=round(sharpe_stats.mean, 4),
            sharpe_std=round(sharpe_stats.std, 4),
            sharpe_ci_lower=round(sharpe_stats.ci_lower, 4),
            sharpe_ci_upper=round(sharpe_stats.ci_upper, 4),
            sharpe_p_value=round(sharpe_stats.p_value, 4),
            sharpe_is_significant=sharpe_stats.is_significant,
            
            observed_cagr=round(observed_cagr, 4),
            cagr_mean=round(cagr_stats.mean, 4),
            cagr_std=round(cagr_stats.std, 4),
            cagr_ci_lower=round(cagr_stats.ci_lower, 4),
            cagr_ci_upper=round(cagr_stats.ci_upper, 4),
            cagr_p_value=round(cagr_stats.p_value, 4),
            cagr_is_significant=cagr_stats.is_significant,
            
            observed_max_dd=round(observed_max_dd, 4),
            max_dd_mean=round(max_dd_stats.mean, 4),
            max_dd_std=round(max_dd_stats.std, 4),
            max_dd_ci_lower=round(max_dd_stats.ci_lower, 4),
            max_dd_ci_upper=round(max_dd_stats.ci_upper, 4),
            max_dd_p_value=round(max_dd_stats.p_value, 4),
            max_dd_is_significant=max_dd_stats.is_significant,
            
            observed_win_rate=round(observed_win_rate, 4),
            win_rate_mean=round(win_rate_stats.mean, 4),
            win_rate_std=round(win_rate_stats.std, 4),
            win_rate_ci_lower=round(win_rate_stats.ci_lower, 4),
            win_rate_ci_upper=round(win_rate_stats.ci_upper, 4),
            win_rate_p_value=round(win_rate_stats.p_value, 4),
            win_rate_is_significant=win_rate_stats.is_significant,
            
            strategy_is_significant=strategy_is_significant,
            confidence_level=0.95,
            
            benchmark_sharpe=round(benchmark_sharpe, 4) if benchmark_sharpe is not None else None,
            alpha_p_value=round(alpha_p_value, 4) if alpha_p_value is not None else None,
            alpha_is_significant=alpha_is_significant,
            
            sharpe_distribution=sharpe_samples.tolist(),
            cagr_distribution=cagr_samples.tolist(),
        )
        
        logger.info(f"Monte Carlo complete. Strategy significant: {strategy_is_significant}")
        
        return result
    
    def run_from_backtest(
        self,
        backtest_id: str,
        n_simulations: int = 1000,
        data_store: Optional[BacktestDataStore] = None,
        progress_callback: Optional[callable] = None,
    ) -> MonteCarloResult:
        """
        Run Monte Carlo simulation from a completed backtest.
        
        Args:
            backtest_id: ID of completed backtest
            n_simulations: Number of bootstrap simulations
            data_store: Optional data store (uses default if None)
            progress_callback: Optional progress callback
            
        Returns:
            MonteCarloResult
        """
        store = data_store or get_data_store()
        result = store.get_backtest_result(backtest_id)
        
        if result is None:
            raise ValueError(f"Backtest not found: {backtest_id}")
        
        if not result.equity_curve:
            raise ValueError(f"Backtest {backtest_id} has no equity curve data")
        
        # Extract daily returns from equity curve
        daily_returns = []
        for point in result.equity_curve:
            if isinstance(point, EquityPoint):
                if point.daily_return != 0:
                    daily_returns.append(point.daily_return)
            elif isinstance(point, dict):
                ret = point.get('daily_return', 0)
                if ret != 0:
                    daily_returns.append(ret)
        
        if len(daily_returns) < 20:
            raise ValueError(f"Insufficient return data: {len(daily_returns)} points")
        
        daily_returns = np.array(daily_returns)
        
        # Get observed win rate from trades
        trades = store.get_trades(backtest_id)
        observed_win_rate = None
        if trades:
            wins = sum(1 for t in trades if t.side == 'sell' and self._is_winning_trade(t, trades))
            sells = sum(1 for t in trades if t.side == 'sell')
            if sells > 0:
                observed_win_rate = wins / sells
        
        # Get benchmark returns if available
        benchmark_returns = None
        # TODO: Fetch SPY returns for the same period if needed
        
        return self.run_simulation(
            daily_returns=daily_returns,
            n_simulations=n_simulations,
            benchmark_returns=benchmark_returns,
            observed_win_rate=observed_win_rate or result.win_rate,
            progress_callback=progress_callback,
        )
    
    def _bootstrap_resample(self, data: np.ndarray) -> np.ndarray:
        """
        Generate bootstrap sample (sample with replacement).
        
        Uses the same length as original data to preserve time structure.
        """
        indices = self._rng.choice(len(data), size=len(data), replace=True)
        return data[indices]
    
    def _calculate_sharpe(self, daily_returns: np.ndarray) -> float:
        """Calculate annualized Sharpe ratio."""
        if len(daily_returns) < 2:
            return 0.0
        
        daily_rf = self.risk_free_rate / 252
        excess_returns = daily_returns - daily_rf
        
        mean_excess = np.mean(excess_returns)
        std_excess = np.std(excess_returns, ddof=1)
        
        if std_excess == 0 or not np.isfinite(std_excess):
            return 0.0
        
        return (mean_excess / std_excess) * np.sqrt(252)
    
    def _calculate_cagr(self, daily_returns: np.ndarray) -> float:
        """Calculate Compound Annual Growth Rate."""
        if len(daily_returns) < 2:
            return 0.0
        
        # Total return from daily returns
        cumulative = np.prod(1 + daily_returns)
        
        if cumulative <= 0:
            return -1.0  # Total loss
        
        # Annualize based on trading days
        years = len(daily_returns) / 252
        if years <= 0:
            return 0.0
        
        cagr = cumulative ** (1 / years) - 1
        return cagr if np.isfinite(cagr) else 0.0
    
    def _calculate_max_drawdown(self, daily_returns: np.ndarray) -> float:
        """Calculate maximum drawdown (returns negative value)."""
        if len(daily_returns) < 2:
            return 0.0
        
        # Build equity curve
        cumulative = np.cumprod(1 + daily_returns)
        peak = np.maximum.accumulate(cumulative)
        
        # Avoid division by zero
        peak = np.where(peak == 0, 1, peak)
        
        drawdown = (cumulative - peak) / peak
        max_dd = np.min(drawdown)
        
        return max_dd if np.isfinite(max_dd) else 0.0
    
    def _calculate_stats(
        self,
        observed: float,
        samples: np.ndarray,
        higher_is_better: bool = True,
    ) -> MetricStats:
        """Calculate statistics for a metric."""
        # Handle edge cases
        valid_samples = samples[np.isfinite(samples)]
        if len(valid_samples) == 0:
            return MetricStats(
                observed=observed,
                mean=0.0,
                std=0.0,
                ci_lower=0.0,
                ci_upper=0.0,
                p_value=1.0,
                is_significant=False,
            )
        
        mean = np.mean(valid_samples)
        std = np.std(valid_samples, ddof=1)
        
        # 95% confidence interval (2.5 and 97.5 percentiles)
        ci_lower = np.percentile(valid_samples, 2.5)
        ci_upper = np.percentile(valid_samples, 97.5)
        
        # P-value: proportion of samples as extreme as or more extreme than observed
        # For metrics where higher is better (Sharpe, CAGR, Win Rate):
        #   p = P(random >= observed) - low p means observed is unusually good
        # For metrics where lower is better (Max Drawdown - more negative is worse):
        #   p = P(random >= observed) - low p means observed is unusually good (less negative)
        #   Note: for max_dd, observed = -0.05 is better than sample = -0.20
        #   P(sample >= -0.05) when samples ~ -0.20 is LOW, which is correct
        p_value = np.mean(valid_samples >= observed)
        
        # Significance test: is observed value significantly better than random?
        # For all metrics: p < 0.05 means observed is in the top 5% (better than 95% of samples)
        # For higher_is_better: observed should be > mean
        # For lower_is_better (max_dd): observed should be > mean (less negative is better)
        is_significant = p_value < 0.05 and observed > mean
        
        return MetricStats(
            observed=observed,
            mean=mean,
            std=std,
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            p_value=p_value,
            is_significant=is_significant,
        )
    
    def _calculate_alpha_pvalue(
        self,
        strategy_returns: np.ndarray,
        benchmark_returns: np.ndarray,
        n_simulations: int,
    ) -> float:
        """
        Calculate p-value for alpha (strategy outperformance vs benchmark).
        
        Uses permutation test: shuffle combined returns and compare differences.
        """
        # Match lengths
        min_len = min(len(strategy_returns), len(benchmark_returns))
        strategy_returns = strategy_returns[:min_len]
        benchmark_returns = benchmark_returns[:min_len]
        
        # Observed difference in Sharpe
        observed_diff = self._calculate_sharpe(strategy_returns) - self._calculate_sharpe(benchmark_returns)
        
        # Permutation test
        combined = np.concatenate([strategy_returns, benchmark_returns])
        n = len(strategy_returns)
        
        extreme_count = 0
        for _ in range(n_simulations):
            # Shuffle and split
            self._rng.shuffle(combined)
            perm_strategy = combined[:n]
            perm_benchmark = combined[n:]
            
            perm_diff = self._calculate_sharpe(perm_strategy) - self._calculate_sharpe(perm_benchmark)
            
            if perm_diff >= observed_diff:
                extreme_count += 1
        
        return extreme_count / n_simulations
    
    def _is_winning_trade(self, sell_trade, all_trades) -> bool:
        """Check if a sell trade was profitable."""
        # Find corresponding buy trade
        ticker = sell_trade.ticker
        sell_date = sell_trade.date
        
        buys = [t for t in all_trades 
                if t.ticker == ticker and t.side == 'buy' and t.date < sell_date]
        
        if not buys:
            return False
        
        buy = buys[-1]  # Most recent buy
        return sell_trade.price > buy.price


# Convenience function
def run_monte_carlo(
    backtest_id: str,
    n_simulations: int = 1000,
    seed: Optional[int] = None,
) -> MonteCarloResult:
    """
    Run Monte Carlo simulation for a backtest.
    
    Args:
        backtest_id: ID of completed backtest
        n_simulations: Number of simulations (100-10000)
        seed: Random seed for reproducibility
        
    Returns:
        MonteCarloResult
    """
    simulator = MonteCarloSimulator(seed=seed)
    return simulator.run_from_backtest(backtest_id, n_simulations)


# Data directory for saving results
DATA_DIR = Path(__file__).parent.parent.parent / "data" / "backtest"


def save_monte_carlo_result(backtest_id: str, result: MonteCarloResult) -> None:
    """Save Monte Carlo result to file."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / f"monte_carlo_{backtest_id}.json"
    
    with open(path, 'w') as f:
        json.dump(result.to_dict(), f, indent=2)
    
    logger.info(f"Saved Monte Carlo result to {path}")


def load_monte_carlo_result(backtest_id: str) -> Optional[MonteCarloResult]:
    """Load Monte Carlo result from file."""
    path = DATA_DIR / f"monte_carlo_{backtest_id}.json"
    
    if not path.exists():
        return None
    
    try:
        with open(path) as f:
            data = json.load(f)
        return MonteCarloResult.from_dict(data)
    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"Failed to load Monte Carlo result: {e}")
        return None


# CLI for testing
if __name__ == "__main__":
    print("\n=== Monte Carlo Simulation Test ===\n")
    
    # Generate synthetic test data
    np.random.seed(42)
    
    # Simulate a modestly profitable strategy
    n_days = 252  # 1 year
    daily_returns = np.random.normal(0.0005, 0.015, n_days)  # ~12% annual, 24% vol
    
    # Run simulation
    simulator = MonteCarloSimulator(seed=42)
    
    result = simulator.run_simulation(
        daily_returns=daily_returns,
        n_simulations=1000,
        progress_callback=lambda c, t: print(f"Progress: {c}/{t}") if c % 200 == 0 else None,
    )
    
    print(result.summary())
    print("\n✅ Monte Carlo Simulation working!")
