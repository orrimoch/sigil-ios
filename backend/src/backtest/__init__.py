"""
Module 12: Backtesting System

Components:
- F12.1: Historical Data Persistence (data_store.py)
- F12.2: Historical Score Generator (historical_scores.py)
- F12.3: Basic Backtest Engine (engine.py)
- F12.4: Performance Metrics Calculator (metrics.py)
- F12.5: IC Decay Analyzer (ic_decay.py)
- F12.6: Walk-Forward Validation (walk_forward.py)
- F12.7: HPO Engine (optimizer.py)
"""

from .data_store import BacktestDataStore
from .engine import BacktestEngine
from .metrics import MetricsCalculator

__all__ = [
    "BacktestDataStore",
    "BacktestEngine", 
    "MetricsCalculator",
]
