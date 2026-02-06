"""
Unit tests for F12.6 Walk-Forward Validation (walk_forward.py)
"""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime
from dateutil.relativedelta import relativedelta

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from backtest.walk_forward import (
    WalkForwardValidator,
    WalkForwardResult,
    FoldResult,
)
from backtest.data_store import (
    BacktestDataStore,
    BacktestParameters,
)


@pytest.fixture
def temp_store():
    """Create a temporary data store."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = BacktestDataStore(data_dir=Path(tmpdir))
        yield store


class TestWalkForwardValidator:
    """Tests for walk-forward validation."""
    
    def test_validator_creation(self, temp_store):
        """Test creating a validator."""
        validator = WalkForwardValidator(data_store=temp_store)
        assert validator is not None
    
    def test_generate_folds_basic(self, temp_store):
        """Test fold generation with basic params."""
        validator = WalkForwardValidator(data_store=temp_store)
        
        folds = validator._generate_folds(
            start_date="2024-01-01",
            end_date="2025-06-30",
            train_months=12,
            test_months=3,
            step_months=3,
        )
        
        # Should have at least 1 fold
        assert len(folds) >= 1
        
        # Each fold should have 4 elements
        for fold in folds:
            assert len(fold) == 4
            train_start, train_end, test_start, test_end = fold
            assert train_start < train_end
            assert test_start < test_end
            assert train_end < test_start
    
    def test_generate_folds_short_period(self, temp_store):
        """Test fold generation with too short period."""
        validator = WalkForwardValidator(data_store=temp_store)
        
        folds = validator._generate_folds(
            start_date="2025-01-01",
            end_date="2025-06-01",  # Only 5 months
            train_months=12,
            test_months=3,
            step_months=3,
        )
        
        # Should have no folds (period too short)
        assert len(folds) == 0
    
    def test_generate_folds_multiple(self, temp_store):
        """Test generating multiple folds."""
        validator = WalkForwardValidator(data_store=temp_store)
        
        folds = validator._generate_folds(
            start_date="2022-01-01",
            end_date="2025-12-31",
            train_months=6,
            test_months=3,
            step_months=3,
        )
        
        # 4 years = 48 months, 6+3=9 per fold, step 3 = many folds
        assert len(folds) >= 5
    
    def test_empty_result(self, temp_store):
        """Test empty result for insufficient data."""
        validator = WalkForwardValidator(data_store=temp_store)
        
        result = validator._empty_result(
            start_date="2025-01-01",
            end_date="2025-12-31",
            train_months=12,
            test_months=3,
        )
        
        assert result.total_folds == 0
        assert result.overfitting_assessment == "insufficient_data"


class TestFoldResult:
    """Tests for FoldResult dataclass."""
    
    def test_fold_result_creation(self):
        """Test creating a fold result."""
        fold = FoldResult(
            fold_number=1,
            train_start="2024-01-01",
            train_end="2024-12-31",
            test_start="2025-01-01",
            test_end="2025-03-31",
            is_total_return=0.15,
            is_sharpe=1.5,
            is_max_drawdown=-0.10,
            oos_total_return=0.08,
            oos_sharpe=0.9,
            oos_max_drawdown=-0.12,
            return_degradation=0.07,
            sharpe_degradation=0.6,
        )
        
        assert fold.fold_number == 1
        assert fold.is_total_return == 0.15
        assert fold.oos_total_return == 0.08
    
    def test_fold_result_to_dict(self):
        """Test converting fold result to dict."""
        fold = FoldResult(
            fold_number=1,
            train_start="2024-01-01",
            train_end="2024-12-31",
            test_start="2025-01-01",
            test_end="2025-03-31",
            is_total_return=0.15,
            is_sharpe=1.5,
            is_max_drawdown=-0.10,
            oos_total_return=0.08,
            oos_sharpe=0.9,
            oos_max_drawdown=-0.12,
            return_degradation=0.07,
            sharpe_degradation=0.6,
        )
        
        d = fold.to_dict()
        
        assert d["fold_number"] == 1
        assert d["return_degradation"] == 0.07


class TestWalkForwardResult:
    """Tests for WalkForwardResult dataclass."""
    
    def test_result_creation(self):
        """Test creating a walk-forward result."""
        result = WalkForwardResult(
            train_months=12,
            test_months=3,
            total_folds=4,
            oos_total_return=0.08,
            oos_cagr=0.35,
            oos_sharpe=1.0,
            oos_max_drawdown=-0.15,
            oos_win_rate=0.75,
            is_total_return=0.15,
            is_sharpe=1.5,
            avg_return_degradation=0.07,
            avg_sharpe_degradation=0.5,
            overfitting_score=33.3,
            overfitting_assessment="moderate",
            folds=[],
            start_date="2022-01-01",
            end_date="2025-12-31",
        )
        
        assert result.total_folds == 4
        assert result.oos_sharpe == 1.0
        assert result.overfitting_assessment == "moderate"
    
    def test_result_to_dict(self):
        """Test converting result to dict."""
        result = WalkForwardResult(
            train_months=12,
            test_months=3,
            total_folds=2,
            oos_total_return=0.05,
            oos_cagr=0.22,
            oos_sharpe=0.8,
            oos_max_drawdown=-0.10,
            oos_win_rate=0.5,
            is_total_return=0.10,
            is_sharpe=1.2,
            avg_return_degradation=0.05,
            avg_sharpe_degradation=0.4,
            overfitting_score=33.3,
            overfitting_assessment="moderate",
            folds=[],
            start_date="2024-01-01",
            end_date="2025-06-30",
        )
        
        d = result.to_dict()
        
        assert d["total_folds"] == 2
        assert d["oos_sharpe"] == 0.8
        assert isinstance(d["folds"], list)


class TestOverfittingAssessment:
    """Tests for overfitting assessment logic."""
    
    def test_low_overfitting(self, temp_store):
        """Test low overfitting assessment."""
        validator = WalkForwardValidator(data_store=temp_store)
        
        # Create folds with small IS/OOS gap
        folds = [
            FoldResult(
                fold_number=1,
                train_start="2024-01-01", train_end="2024-12-31",
                test_start="2025-01-01", test_end="2025-03-31",
                is_total_return=0.10, is_sharpe=1.0, is_max_drawdown=-0.10,
                oos_total_return=0.09, oos_sharpe=0.95, oos_max_drawdown=-0.11,
                return_degradation=0.01, sharpe_degradation=0.05,
            ),
        ]
        
        result = validator._aggregate_results(
            folds, "2024-01-01", "2025-03-31", 12, 3
        )
        
        # Small gap should result in low overfitting
        assert result.overfitting_score < 20
        assert result.overfitting_assessment == "low"
    
    def test_high_overfitting(self, temp_store):
        """Test high overfitting assessment."""
        validator = WalkForwardValidator(data_store=temp_store)
        
        # Create folds with large IS/OOS gap
        folds = [
            FoldResult(
                fold_number=1,
                train_start="2024-01-01", train_end="2024-12-31",
                test_start="2025-01-01", test_end="2025-03-31",
                is_total_return=0.30, is_sharpe=2.0, is_max_drawdown=-0.05,
                oos_total_return=0.02, oos_sharpe=0.3, oos_max_drawdown=-0.20,
                return_degradation=0.28, sharpe_degradation=1.7,
            ),
        ]
        
        result = validator._aggregate_results(
            folds, "2024-01-01", "2025-03-31", 12, 3
        )
        
        # Large gap should result in high overfitting
        assert result.overfitting_score > 50
        assert result.overfitting_assessment in ["high", "severe"]


class TestAggregation:
    """Tests for result aggregation."""
    
    def test_aggregate_multiple_folds(self, temp_store):
        """Test aggregating multiple folds."""
        validator = WalkForwardValidator(data_store=temp_store)
        
        folds = [
            FoldResult(
                fold_number=1,
                train_start="2024-01-01", train_end="2024-06-30",
                test_start="2024-07-01", test_end="2024-09-30",
                is_total_return=0.10, is_sharpe=1.2, is_max_drawdown=-0.08,
                oos_total_return=0.05, oos_sharpe=0.8, oos_max_drawdown=-0.10,
                return_degradation=0.05, sharpe_degradation=0.4,
            ),
            FoldResult(
                fold_number=2,
                train_start="2024-04-01", train_end="2024-09-30",
                test_start="2024-10-01", test_end="2024-12-31",
                is_total_return=0.12, is_sharpe=1.4, is_max_drawdown=-0.06,
                oos_total_return=0.07, oos_sharpe=1.0, oos_max_drawdown=-0.08,
                return_degradation=0.05, sharpe_degradation=0.4,
            ),
        ]
        
        result = validator._aggregate_results(
            folds, "2024-01-01", "2024-12-31", 6, 3
        )
        
        # Should average the folds
        assert result.total_folds == 2
        assert result.oos_total_return == 0.06  # (0.05 + 0.07) / 2
        assert result.oos_sharpe == 0.9  # (0.8 + 1.0) / 2
        
    def test_win_rate_calculation(self, temp_store):
        """Test win rate calculation."""
        validator = WalkForwardValidator(data_store=temp_store)
        
        folds = [
            FoldResult(
                fold_number=1,
                train_start="", train_end="",
                test_start="", test_end="",
                is_total_return=0.10, is_sharpe=1.0, is_max_drawdown=-0.10,
                oos_total_return=0.05, oos_sharpe=0.8, oos_max_drawdown=-0.12,  # Win
                return_degradation=0.05, sharpe_degradation=0.2,
            ),
            FoldResult(
                fold_number=2,
                train_start="", train_end="",
                test_start="", test_end="",
                is_total_return=0.08, is_sharpe=0.9, is_max_drawdown=-0.08,
                oos_total_return=-0.02, oos_sharpe=-0.3, oos_max_drawdown=-0.15,  # Loss
                return_degradation=0.10, sharpe_degradation=1.2,
            ),
        ]
        
        result = validator._aggregate_results(
            folds, "2024-01-01", "2024-12-31", 6, 3
        )
        
        # 1 win out of 2 = 50%
        assert result.oos_win_rate == 0.5
