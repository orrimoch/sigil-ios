"""
Unit tests for F12.7 HPO Engine (optimizer.py)
"""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from backtest.optimizer import (
    HPOEngine,
    OptimizationResult,
    SearchSpace,
)
from backtest.data_store import BacktestDataStore


@pytest.fixture
def temp_store():
    """Create a temporary data store."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = BacktestDataStore(data_dir=Path(tmpdir))
        yield store


class TestSearchSpace:
    """Tests for SearchSpace dataclass."""
    
    def test_default_values(self):
        """Test default search space values."""
        ss = SearchSpace()
        
        assert ss.entry_threshold_min == 60
        assert ss.entry_threshold_max == 85
        assert ss.exit_threshold_min == 35
        assert ss.exit_threshold_max == 60
        assert ss.max_positions_min == 5
        assert ss.max_positions_max == 20
        assert "weekly" in ss.rebalance_options
    
    def test_custom_values(self):
        """Test custom search space."""
        ss = SearchSpace(
            entry_threshold_min=65,
            entry_threshold_max=90,
            max_positions_min=3,
            max_positions_max=15,
        )
        
        assert ss.entry_threshold_min == 65
        assert ss.entry_threshold_max == 90
        assert ss.max_positions_min == 3
    
    def test_to_dict(self):
        """Test converting search space to dict."""
        ss = SearchSpace()
        d = ss.to_dict()
        
        assert "entry_threshold_min" in d
        assert "rebalance_options" in d
        assert isinstance(d["rebalance_options"], list)


class TestOptimizationResult:
    """Tests for OptimizationResult dataclass."""
    
    def test_result_creation(self):
        """Test creating an optimization result."""
        result = OptimizationResult(
            best_params={
                "entry_threshold": 72.5,
                "exit_threshold": 45.0,
                "max_positions": 10,
                "rebalance_freq": "weekly",
            },
            best_value=1.25,
            n_trials=50,
            n_completed=45,
            n_pruned=5,
            best_trial_number=32,
            best_oos_return=0.12,
            best_oos_sharpe=1.25,
            best_oos_max_drawdown=-0.15,
            best_overfitting_score=25.0,
        )
        
        assert result.best_value == 1.25
        assert result.n_completed == 45
        assert result.best_params["entry_threshold"] == 72.5
    
    def test_result_to_dict(self):
        """Test converting result to dict."""
        result = OptimizationResult(
            best_params={"entry_threshold": 70},
            best_value=1.0,
            n_trials=10,
            n_completed=8,
            n_pruned=2,
            best_trial_number=5,
            best_oos_return=0.08,
            best_oos_sharpe=1.0,
            best_oos_max_drawdown=-0.10,
            best_overfitting_score=20.0,
            param_importance={"entry_threshold": 0.45, "max_positions": 0.30},
        )
        
        d = result.to_dict()
        
        assert d["best_value"] == 1.0
        assert "param_importance" in d
        assert d["param_importance"]["entry_threshold"] == 0.45


class TestHPOEngine:
    """Tests for HPOEngine."""
    
    def test_engine_creation(self, temp_store):
        """Test creating an HPO engine."""
        engine = HPOEngine(data_store=temp_store)
        assert engine is not None
    
    def test_get_best_params_before_optimization(self, temp_store):
        """Test getting best params before any optimization."""
        engine = HPOEngine(data_store=temp_store)
        
        params = engine.get_best_params()
        assert params is None
    
    def test_get_optimization_history_empty(self, temp_store):
        """Test getting history before optimization."""
        engine = HPOEngine(data_store=temp_store)
        
        history = engine.get_optimization_history()
        assert history == []


class TestSearchSpaceValidation:
    """Tests for search space validation."""
    
    def test_exit_less_than_entry(self):
        """Test that exit threshold max is less than entry threshold."""
        ss = SearchSpace()
        
        # Exit max should be less than entry min typically
        # But the actual constraint is enforced in optimization
        assert ss.exit_threshold_max < ss.entry_threshold_max
    
    def test_reasonable_position_range(self):
        """Test position range is reasonable."""
        ss = SearchSpace()
        
        assert ss.max_positions_min >= 1
        assert ss.max_positions_max <= 50
        assert ss.max_positions_min < ss.max_positions_max


class TestOptimizationResultMetadata:
    """Tests for optimization result metadata."""
    
    def test_with_metadata(self):
        """Test result with full metadata."""
        result = OptimizationResult(
            best_params={"entry_threshold": 70},
            best_value=1.2,
            n_trials=100,
            n_completed=90,
            n_pruned=10,
            best_trial_number=75,
            best_oos_return=0.15,
            best_oos_sharpe=1.2,
            best_oos_max_drawdown=-0.12,
            best_overfitting_score=18.5,
            start_date="2024-01-01",
            end_date="2025-06-30",
            optimization_time_seconds=1234.5,
            created_at="2025-02-06T20:00:00",
        )
        
        assert result.start_date == "2024-01-01"
        assert result.optimization_time_seconds == 1234.5
        assert result.created_at == "2025-02-06T20:00:00"
    
    def test_trials_summary(self):
        """Test with trials summary."""
        result = OptimizationResult(
            best_params={"entry_threshold": 70},
            best_value=1.0,
            n_trials=10,
            n_completed=10,
            n_pruned=0,
            best_trial_number=5,
            best_oos_return=0.10,
            best_oos_sharpe=1.0,
            best_oos_max_drawdown=-0.10,
            best_overfitting_score=20.0,
            trials_summary=[
                {"number": 5, "value": 1.0, "params": {"entry_threshold": 70}},
                {"number": 3, "value": 0.9, "params": {"entry_threshold": 72}},
            ],
        )
        
        d = result.to_dict()
        
        assert len(d["trials_summary"]) == 2
        assert d["trials_summary"][0]["number"] == 5


class TestParamImportance:
    """Tests for parameter importance."""
    
    def test_importance_values(self):
        """Test parameter importance values."""
        result = OptimizationResult(
            best_params={"entry_threshold": 70, "max_positions": 10},
            best_value=1.0,
            n_trials=50,
            n_completed=50,
            n_pruned=0,
            best_trial_number=25,
            best_oos_return=0.10,
            best_oos_sharpe=1.0,
            best_oos_max_drawdown=-0.10,
            best_overfitting_score=20.0,
            param_importance={
                "entry_threshold": 0.45,
                "exit_threshold": 0.30,
                "max_positions": 0.15,
                "rebalance_freq": 0.10,
            },
        )
        
        # Importance should sum to ~1.0
        total = sum(result.param_importance.values())
        assert 0.9 <= total <= 1.1
        
        # Entry threshold should be most important
        assert result.param_importance["entry_threshold"] >= result.param_importance["rebalance_freq"]
