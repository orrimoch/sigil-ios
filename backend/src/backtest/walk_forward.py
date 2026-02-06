"""
F12.6 Walk-Forward Validation

Prevents overfitting by using rolling train/test splits.
True out-of-sample (OOS) performance is the only valid measure.

Methodology:
- Rolling window: Train on N months, test on M months
- Aggregate OOS results for true performance estimate
- Report IS vs OOS gap (overfitting indicator)

Default: 12 months train, 3 months test, rolling quarterly
"""

import numpy as np
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict, field
from loguru import logger

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest.data_store import (
    BacktestDataStore,
    BacktestParameters,
    get_data_store,
)
from backtest.engine import BacktestEngine
from backtest.metrics import MetricsCalculator, PerformanceMetrics


@dataclass
class FoldResult:
    """Results from a single train/test fold."""
    fold_number: int
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    
    # In-sample metrics (training period)
    is_total_return: float
    is_sharpe: float
    is_max_drawdown: float
    
    # Out-of-sample metrics (test period)
    oos_total_return: float
    oos_sharpe: float
    oos_max_drawdown: float
    
    # Overfitting indicators
    return_degradation: float  # IS return - OOS return
    sharpe_degradation: float  # IS sharpe - OOS sharpe
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class WalkForwardResult:
    """Complete walk-forward validation results."""
    # Configuration
    train_months: int
    test_months: int
    total_folds: int
    
    # Aggregated OOS metrics (the TRUE performance)
    oos_total_return: float
    oos_cagr: float
    oos_sharpe: float
    oos_max_drawdown: float
    oos_win_rate: float
    
    # Aggregated IS metrics (for comparison)
    is_total_return: float
    is_sharpe: float
    
    # Overfitting analysis
    avg_return_degradation: float
    avg_sharpe_degradation: float
    overfitting_score: float  # 0-100, higher = more overfit
    overfitting_assessment: str  # "low", "moderate", "high", "severe"
    
    # Time range
    start_date: str
    end_date: str
    
    # Individual folds (default at end)
    folds: List[FoldResult] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        d = asdict(self)
        d['folds'] = [f.to_dict() if isinstance(f, FoldResult) else f for f in self.folds]
        return d


class WalkForwardValidator:
    """
    Performs walk-forward validation to prevent overfitting.
    
    The key insight: In-sample (IS) performance is always better than
    out-of-sample (OOS). The gap tells you how overfit you are.
    
    A good model has:
    - Small IS vs OOS gap
    - Consistent OOS performance across folds
    - OOS Sharpe > 0.5
    """
    
    def __init__(self, data_store: Optional[BacktestDataStore] = None):
        self.data_store = data_store or get_data_store()
        self.engine = BacktestEngine(data_store)
        self.metrics_calc = MetricsCalculator(data_store)
    
    def run_walk_forward(
        self,
        start_date: str,
        end_date: str,
        train_months: int = 12,
        test_months: int = 3,
        step_months: int = 3,
        params: Optional[BacktestParameters] = None,
    ) -> WalkForwardResult:
        """
        Run walk-forward validation.
        
        Args:
            start_date: Overall start date
            end_date: Overall end date
            train_months: Training period length
            test_months: Test period length
            step_months: How far to advance between folds
            params: Backtest parameters (uses defaults if None)
            
        Returns:
            WalkForwardResult with aggregated metrics
        """
        logger.info(f"Running walk-forward validation: {start_date} to {end_date}")
        logger.info(f"Train: {train_months}mo, Test: {test_months}mo, Step: {step_months}mo")
        
        # Default parameters
        if params is None:
            params = BacktestParameters(
                start_date=start_date,
                end_date=end_date,
                initial_capital=100000,
                entry_threshold=70,
                exit_threshold=50,
                max_positions=10,
            )
        
        # Generate folds
        folds = self._generate_folds(
            start_date, end_date,
            train_months, test_months, step_months
        )
        
        if not folds:
            logger.warning("No folds generated - date range too short")
            return self._empty_result(start_date, end_date, train_months, test_months)
        
        logger.info(f"Generated {len(folds)} folds")
        
        # Run each fold
        fold_results = []
        
        for i, (train_start, train_end, test_start, test_end) in enumerate(folds):
            logger.info(f"Fold {i+1}/{len(folds)}: Train [{train_start} to {train_end}], Test [{test_start} to {test_end}]")
            
            try:
                fold_result = self._run_fold(
                    fold_number=i + 1,
                    train_start=train_start,
                    train_end=train_end,
                    test_start=test_start,
                    test_end=test_end,
                    params=params,
                )
                fold_results.append(fold_result)
                
            except Exception as e:
                logger.warning(f"Fold {i+1} failed: {e}")
                continue
        
        if not fold_results:
            return self._empty_result(start_date, end_date, train_months, test_months)
        
        # Aggregate results
        return self._aggregate_results(
            fold_results,
            start_date, end_date,
            train_months, test_months
        )
    
    def _generate_folds(
        self,
        start_date: str,
        end_date: str,
        train_months: int,
        test_months: int,
        step_months: int,
    ) -> List[Tuple[str, str, str, str]]:
        """Generate train/test fold date ranges."""
        folds = []
        
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        
        current_train_start = start
        
        while True:
            train_end = current_train_start + relativedelta(months=train_months)
            test_start = train_end + timedelta(days=1)
            test_end = test_start + relativedelta(months=test_months)
            
            # Check if test period fits
            if test_end > end:
                break
            
            folds.append((
                current_train_start.strftime("%Y-%m-%d"),
                train_end.strftime("%Y-%m-%d"),
                test_start.strftime("%Y-%m-%d"),
                test_end.strftime("%Y-%m-%d"),
            ))
            
            # Move forward
            current_train_start += relativedelta(months=step_months)
        
        return folds
    
    def _run_fold(
        self,
        fold_number: int,
        train_start: str,
        train_end: str,
        test_start: str,
        test_end: str,
        params: BacktestParameters,
    ) -> FoldResult:
        """Run a single train/test fold."""
        # Run training period backtest
        train_params = BacktestParameters(
            start_date=train_start,
            end_date=train_end,
            initial_capital=params.initial_capital,
            entry_threshold=params.entry_threshold,
            exit_threshold=params.exit_threshold,
            max_positions=params.max_positions,
            rebalance_freq=params.rebalance_freq,
            transaction_cost=params.transaction_cost,
            slippage=params.slippage,
        )
        
        train_result = self.engine.run_backtest(train_params)
        
        # Run test period backtest
        test_params = BacktestParameters(
            start_date=test_start,
            end_date=test_end,
            initial_capital=params.initial_capital,
            entry_threshold=params.entry_threshold,
            exit_threshold=params.exit_threshold,
            max_positions=params.max_positions,
            rebalance_freq=params.rebalance_freq,
            transaction_cost=params.transaction_cost,
            slippage=params.slippage,
        )
        
        test_result = self.engine.run_backtest(test_params)
        
        # Extract metrics
        is_return = train_result.total_return or 0
        is_sharpe = train_result.sharpe_ratio or 0
        is_max_dd = train_result.max_drawdown or 0
        
        oos_return = test_result.total_return or 0
        oos_sharpe = test_result.sharpe_ratio or 0
        oos_max_dd = test_result.max_drawdown or 0
        
        return FoldResult(
            fold_number=fold_number,
            train_start=train_start,
            train_end=train_end,
            test_start=test_start,
            test_end=test_end,
            is_total_return=round(is_return, 4),
            is_sharpe=round(is_sharpe, 2),
            is_max_drawdown=round(is_max_dd, 4),
            oos_total_return=round(oos_return, 4),
            oos_sharpe=round(oos_sharpe, 2),
            oos_max_drawdown=round(oos_max_dd, 4),
            return_degradation=round(is_return - oos_return, 4),
            sharpe_degradation=round(is_sharpe - oos_sharpe, 2),
        )
    
    def _aggregate_results(
        self,
        folds: List[FoldResult],
        start_date: str,
        end_date: str,
        train_months: int,
        test_months: int,
    ) -> WalkForwardResult:
        """Aggregate fold results into final metrics."""
        # OOS metrics (the TRUE performance)
        oos_returns = [f.oos_total_return for f in folds]
        oos_sharpes = [f.oos_sharpe for f in folds]
        oos_drawdowns = [f.oos_max_drawdown for f in folds]
        
        # IS metrics
        is_returns = [f.is_total_return for f in folds]
        is_sharpes = [f.is_sharpe for f in folds]
        
        # Degradation metrics
        return_degradations = [f.return_degradation for f in folds]
        sharpe_degradations = [f.sharpe_degradation for f in folds]
        
        # Calculate aggregates
        avg_oos_return = np.mean(oos_returns)
        avg_oos_sharpe = np.mean(oos_sharpes)
        avg_oos_max_dd = np.mean(oos_drawdowns)
        
        avg_is_return = np.mean(is_returns)
        avg_is_sharpe = np.mean(is_sharpes)
        
        avg_return_deg = np.mean(return_degradations)
        avg_sharpe_deg = np.mean(sharpe_degradations)
        
        # Estimate CAGR from average quarterly OOS return
        # Assuming test_months = 3 (quarterly)
        periods_per_year = 12 / test_months
        oos_cagr = (1 + avg_oos_return) ** periods_per_year - 1
        
        # Win rate (positive OOS returns)
        oos_win_rate = sum(1 for r in oos_returns if r > 0) / len(oos_returns)
        
        # Overfitting score (0-100)
        # Based on IS vs OOS gap, normalized
        if avg_is_sharpe > 0:
            sharpe_ratio_degradation = avg_sharpe_deg / max(avg_is_sharpe, 0.1)
        else:
            sharpe_ratio_degradation = 0
        
        overfitting_score = min(100, max(0, sharpe_ratio_degradation * 100))
        
        # Assessment
        if overfitting_score < 20:
            assessment = "low"
        elif overfitting_score < 40:
            assessment = "moderate"
        elif overfitting_score < 60:
            assessment = "high"
        else:
            assessment = "severe"
        
        return WalkForwardResult(
            train_months=train_months,
            test_months=test_months,
            total_folds=len(folds),
            oos_total_return=round(avg_oos_return, 4),
            oos_cagr=round(oos_cagr, 4),
            oos_sharpe=round(avg_oos_sharpe, 2),
            oos_max_drawdown=round(avg_oos_max_dd, 4),
            oos_win_rate=round(oos_win_rate, 4),
            is_total_return=round(avg_is_return, 4),
            is_sharpe=round(avg_is_sharpe, 2),
            avg_return_degradation=round(avg_return_deg, 4),
            avg_sharpe_degradation=round(avg_sharpe_deg, 2),
            overfitting_score=round(overfitting_score, 1),
            overfitting_assessment=assessment,
            folds=folds,
            start_date=start_date,
            end_date=end_date,
        )
    
    def _empty_result(
        self,
        start_date: str,
        end_date: str,
        train_months: int,
        test_months: int,
    ) -> WalkForwardResult:
        """Return empty result."""
        return WalkForwardResult(
            train_months=train_months,
            test_months=test_months,
            total_folds=0,
            oos_total_return=0,
            oos_cagr=0,
            oos_sharpe=0,
            oos_max_drawdown=0,
            oos_win_rate=0,
            is_total_return=0,
            is_sharpe=0,
            avg_return_degradation=0,
            avg_sharpe_degradation=0,
            overfitting_score=0,
            overfitting_assessment="insufficient_data",
            folds=[],
            start_date=start_date,
            end_date=end_date,
        )


# Convenience function
def run_walk_forward(
    start_date: str,
    end_date: str,
    train_months: int = 12,
    test_months: int = 3,
) -> WalkForwardResult:
    """Run walk-forward validation with default parameters."""
    validator = WalkForwardValidator()
    return validator.run_walk_forward(
        start_date=start_date,
        end_date=end_date,
        train_months=train_months,
        test_months=test_months,
    )


# CLI for testing
if __name__ == "__main__":
    print("\n=== Walk-Forward Validation Test ===\n")
    
    validator = WalkForwardValidator()
    
    # Use shorter periods for testing
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - relativedelta(months=18)).strftime("%Y-%m-%d")
    
    print(f"Running walk-forward: {start_date} to {end_date}")
    print("Train: 9 months, Test: 3 months, Step: 3 months\n")
    
    try:
        result = validator.run_walk_forward(
            start_date=start_date,
            end_date=end_date,
            train_months=9,
            test_months=3,
            step_months=3,
        )
        
        print(f"=== Results ({result.total_folds} folds) ===\n")
        
        print("Out-of-Sample (TRUE Performance):")
        print(f"  Total Return: {result.oos_total_return:.2%}")
        print(f"  CAGR: {result.oos_cagr:.2%}")
        print(f"  Sharpe: {result.oos_sharpe:.2f}")
        print(f"  Max Drawdown: {result.oos_max_drawdown:.2%}")
        print(f"  Win Rate: {result.oos_win_rate:.2%}")
        
        print("\nIn-Sample (Training):")
        print(f"  Total Return: {result.is_total_return:.2%}")
        print(f"  Sharpe: {result.is_sharpe:.2f}")
        
        print("\nOverfitting Analysis:")
        print(f"  Avg Return Degradation: {result.avg_return_degradation:.2%}")
        print(f"  Avg Sharpe Degradation: {result.avg_sharpe_degradation:.2f}")
        print(f"  Overfitting Score: {result.overfitting_score:.1f}/100")
        print(f"  Assessment: {result.overfitting_assessment}")
        
    except Exception as e:
        print(f"Walk-forward failed: {e}")
        raise
    
    print("\n✅ Walk-Forward Validation working!")
