"""
F12.7 HPO Engine with Optuna

Bayesian hyperparameter optimization for strategy parameters.
Uses walk-forward validation to prevent overfitting.

Search Space:
- entry_threshold: 60-85
- exit_threshold: 35-60
- max_positions: 5-20
- rebalance_freq: daily/weekly/biweekly

Objective: Maximize out-of-sample (OOS) Sharpe ratio
"""

import optuna
from optuna.samplers import TPESampler
from optuna.pruners import MedianPruner
import numpy as np
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict, field
from loguru import logger
import json

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest.data_store import (
    BacktestDataStore,
    BacktestParameters,
    get_data_store,
)
from backtest.walk_forward import WalkForwardValidator, WalkForwardResult


# Storage for optimization results
OPTIMIZER_DIR = Path(__file__).parent.parent.parent / "data" / "backtest" / "optimization"


@dataclass
class OptimizationResult:
    """Results from hyperparameter optimization."""
    # Best parameters found
    best_params: Dict[str, Any]
    best_value: float  # Best OOS Sharpe
    
    # Optimization stats
    n_trials: int
    n_completed: int
    n_pruned: int
    
    # Best trial details
    best_trial_number: int
    best_oos_return: float
    best_oos_sharpe: float
    best_oos_max_drawdown: float
    best_overfitting_score: float
    
    # Parameter importance (if available)
    param_importance: Dict[str, float] = field(default_factory=dict)
    
    # All trials summary
    trials_summary: List[Dict] = field(default_factory=list)
    
    # Metadata
    start_date: str = ""
    end_date: str = ""
    optimization_time_seconds: float = 0
    created_at: str = ""
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SearchSpace:
    """Defines the hyperparameter search space."""
    entry_threshold_min: float = 60
    entry_threshold_max: float = 85
    exit_threshold_min: float = 35
    exit_threshold_max: float = 60
    max_positions_min: int = 5
    max_positions_max: int = 20
    rebalance_options: List[str] = field(default_factory=lambda: ["weekly", "biweekly"])
    
    def to_dict(self) -> dict:
        return asdict(self)


class HPOEngine:
    """
    Hyperparameter optimization engine using Optuna.
    
    Key features:
    - Bayesian optimization (TPE sampler)
    - Early stopping for bad trials (median pruner)
    - Walk-forward validation as objective
    - Overfitting penalty
    """
    
    def __init__(self, data_store: Optional[BacktestDataStore] = None):
        self.data_store = data_store or get_data_store()
        self.validator = WalkForwardValidator(data_store)
        self._study: Optional[optuna.Study] = None
        self._best_result: Optional[WalkForwardResult] = None
    
    def optimize(
        self,
        start_date: str,
        end_date: str,
        n_trials: int = 50,
        timeout_seconds: Optional[int] = 3600,
        search_space: Optional[SearchSpace] = None,
        train_months: int = 9,
        test_months: int = 3,
        seed: int = 42,
    ) -> OptimizationResult:
        """
        Run hyperparameter optimization.
        
        Args:
            start_date: Data start date
            end_date: Data end date
            n_trials: Number of optimization trials
            timeout_seconds: Maximum optimization time
            search_space: Custom search space (uses defaults if None)
            train_months: Walk-forward training period
            test_months: Walk-forward test period
            seed: Random seed for reproducibility
            
        Returns:
            OptimizationResult with best parameters
        """
        logger.info(f"Starting HPO: {n_trials} trials, {start_date} to {end_date}")
        
        if search_space is None:
            search_space = SearchSpace()
        
        start_time = datetime.now()
        
        # Create Optuna study
        sampler = TPESampler(seed=seed)
        pruner = MedianPruner(n_warmup_steps=5, n_startup_trials=10)
        
        self._study = optuna.create_study(
            direction="maximize",  # Maximize OOS Sharpe
            sampler=sampler,
            pruner=pruner,
            study_name=f"sigil_hpo_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        )
        
        # Store context for objective function
        self._opt_context = {
            "start_date": start_date,
            "end_date": end_date,
            "search_space": search_space,
            "train_months": train_months,
            "test_months": test_months,
        }
        
        # Run optimization
        try:
            self._study.optimize(
                self._objective,
                n_trials=n_trials,
                timeout=timeout_seconds,
                show_progress_bar=False,
                callbacks=[self._log_callback],
            )
        except KeyboardInterrupt:
            logger.info("Optimization interrupted by user")
        
        optimization_time = (datetime.now() - start_time).total_seconds()
        
        # Extract results
        best_trial = self._study.best_trial
        
        # Get parameter importance
        try:
            importance = optuna.importance.get_param_importances(self._study)
        except Exception:
            importance = {}
        
        # Build trials summary
        trials_summary = []
        for trial in self._study.trials:
            if trial.state == optuna.trial.TrialState.COMPLETE:
                trials_summary.append({
                    "number": trial.number,
                    "value": round(trial.value, 4) if trial.value else None,
                    "params": trial.params,
                })
        
        # Sort by value descending
        trials_summary.sort(key=lambda x: x["value"] or -999, reverse=True)
        
        result = OptimizationResult(
            best_params=best_trial.params,
            best_value=round(best_trial.value, 4) if best_trial.value else 0,
            n_trials=len(self._study.trials),
            n_completed=len([t for t in self._study.trials if t.state == optuna.trial.TrialState.COMPLETE]),
            n_pruned=len([t for t in self._study.trials if t.state == optuna.trial.TrialState.PRUNED]),
            best_trial_number=best_trial.number,
            best_oos_return=best_trial.user_attrs.get("oos_return", 0),
            best_oos_sharpe=best_trial.value or 0,
            best_oos_max_drawdown=best_trial.user_attrs.get("oos_max_dd", 0),
            best_overfitting_score=best_trial.user_attrs.get("overfitting_score", 0),
            param_importance={k: round(v, 4) for k, v in importance.items()},
            trials_summary=trials_summary[:20],  # Top 20
            start_date=start_date,
            end_date=end_date,
            optimization_time_seconds=round(optimization_time, 1),
            created_at=datetime.now().isoformat(),
        )
        
        # Save result
        self._save_result(result)
        
        logger.info(f"HPO complete: Best Sharpe = {result.best_value:.2f}")
        logger.info(f"Best params: {result.best_params}")
        
        return result
    
    def _objective(self, trial: optuna.Trial) -> float:
        """
        Objective function for Optuna.
        
        Returns OOS Sharpe ratio (with overfitting penalty).
        """
        ctx = self._opt_context
        ss = ctx["search_space"]
        
        # Sample parameters
        entry_threshold = trial.suggest_float(
            "entry_threshold",
            ss.entry_threshold_min,
            ss.entry_threshold_max,
        )
        
        exit_threshold = trial.suggest_float(
            "exit_threshold",
            ss.exit_threshold_min,
            min(ss.exit_threshold_max, entry_threshold - 10),  # Exit must be < entry
        )
        
        max_positions = trial.suggest_int(
            "max_positions",
            ss.max_positions_min,
            ss.max_positions_max,
        )
        
        rebalance_freq = trial.suggest_categorical(
            "rebalance_freq",
            ss.rebalance_options,
        )
        
        # Create parameters
        params = BacktestParameters(
            start_date=ctx["start_date"],
            end_date=ctx["end_date"],
            initial_capital=100000,
            entry_threshold=entry_threshold,
            exit_threshold=exit_threshold,
            max_positions=max_positions,
            rebalance_freq=rebalance_freq,
        )
        
        # Run walk-forward validation
        try:
            wf_result = self.validator.run_walk_forward(
                start_date=ctx["start_date"],
                end_date=ctx["end_date"],
                train_months=ctx["train_months"],
                test_months=ctx["test_months"],
                step_months=ctx["test_months"],
                params=params,
            )
        except Exception as e:
            logger.warning(f"Trial {trial.number} failed: {e}")
            return -999  # Bad trial
        
        if wf_result.total_folds == 0:
            return -999
        
        # Store metrics for later
        trial.set_user_attr("oos_return", wf_result.oos_total_return)
        trial.set_user_attr("oos_max_dd", wf_result.oos_max_drawdown)
        trial.set_user_attr("overfitting_score", wf_result.overfitting_score)
        
        # Objective: OOS Sharpe with overfitting penalty
        oos_sharpe = wf_result.oos_sharpe
        
        # Penalize high overfitting (reduce score by up to 50%)
        overfitting_penalty = wf_result.overfitting_score / 200  # 0 to 0.5
        penalized_sharpe = oos_sharpe * (1 - overfitting_penalty)
        
        # Penalize extreme drawdowns
        if wf_result.oos_max_drawdown < -0.25:
            drawdown_penalty = abs(wf_result.oos_max_drawdown + 0.25) * 2
            penalized_sharpe -= drawdown_penalty
        
        return penalized_sharpe
    
    def _log_callback(self, study: optuna.Study, trial: optuna.trial.FrozenTrial) -> None:
        """Callback to log progress."""
        if trial.state == optuna.trial.TrialState.COMPLETE:
            logger.info(
                f"Trial {trial.number}: Sharpe = {trial.value:.2f}, "
                f"Best = {study.best_value:.2f}"
            )
    
    def _save_result(self, result: OptimizationResult) -> None:
        """Save optimization result to file."""
        OPTIMIZER_DIR.mkdir(parents=True, exist_ok=True)
        
        filename = f"hpo_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        path = OPTIMIZER_DIR / filename
        
        with open(path, "w") as f:
            json.dump(result.to_dict(), f, indent=2)
        
        logger.info(f"Saved optimization result to {path}")
    
    def get_best_params(self) -> Optional[Dict[str, Any]]:
        """Get best parameters from last optimization."""
        if self._study is None:
            return None
        return self._study.best_params
    
    def get_optimization_history(self) -> List[Dict]:
        """Get history of optimization values."""
        if self._study is None:
            return []
        
        history = []
        for trial in self._study.trials:
            if trial.state == optuna.trial.TrialState.COMPLETE:
                history.append({
                    "trial": trial.number,
                    "value": trial.value,
                    "params": trial.params,
                })
        
        return history


def load_latest_optimization() -> Optional[OptimizationResult]:
    """Load the most recent optimization result."""
    if not OPTIMIZER_DIR.exists():
        return None
    
    files = sorted(OPTIMIZER_DIR.glob("hpo_result_*.json"), reverse=True)
    
    if not files:
        return None
    
    with open(files[0]) as f:
        data = json.load(f)
    
    return OptimizationResult(**data)


# Convenience function
def optimize_strategy(
    start_date: str,
    end_date: str,
    n_trials: int = 50,
) -> OptimizationResult:
    """Run strategy optimization with default settings."""
    engine = HPOEngine()
    return engine.optimize(
        start_date=start_date,
        end_date=end_date,
        n_trials=n_trials,
    )


# CLI for testing
if __name__ == "__main__":
    from dateutil.relativedelta import relativedelta
    
    print("\n=== HPO Engine Test ===\n")
    
    engine = HPOEngine()
    
    # Use 1.5 years of data
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - relativedelta(months=18)).strftime("%Y-%m-%d")
    
    print(f"Optimizing: {start_date} to {end_date}")
    print("Running 10 trials (quick test)...\n")
    
    try:
        result = engine.optimize(
            start_date=start_date,
            end_date=end_date,
            n_trials=10,  # Quick test
            timeout_seconds=300,
            train_months=9,
            test_months=3,
        )
        
        print(f"\n=== Results ===")
        print(f"Trials: {result.n_completed} completed, {result.n_pruned} pruned")
        print(f"Best OOS Sharpe: {result.best_oos_sharpe:.2f}")
        print(f"Best OOS Return: {result.best_oos_return:.2%}")
        print(f"Overfitting Score: {result.best_overfitting_score:.1f}")
        print(f"\nBest Parameters:")
        for k, v in result.best_params.items():
            print(f"  {k}: {v}")
        
        if result.param_importance:
            print(f"\nParameter Importance:")
            for k, v in sorted(result.param_importance.items(), key=lambda x: -x[1]):
                print(f"  {k}: {v:.2%}")
        
    except Exception as e:
        print(f"Optimization failed: {e}")
        raise
    
    print("\n✅ HPO Engine working!")
