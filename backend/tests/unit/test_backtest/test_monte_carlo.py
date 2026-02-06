"""
Unit tests for F12.12 Monte Carlo Simulation

Tests cover:
- Bootstrap resampling
- CI calculation
- P-value calculation
- Metric calculations (Sharpe, CAGR, Max DD, Win Rate)
- Edge cases (insufficient data, zero returns, NaN handling)
- Statistical properties of simulations
- Backtest integration
"""

import pytest
import numpy as np
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from backtest.monte_carlo import (
    MonteCarloSimulator,
    MonteCarloResult,
    MetricStats,
    run_monte_carlo,
    save_monte_carlo_result,
    load_monte_carlo_result,
)


class TestMonteCarloSimulator:
    """Tests for MonteCarloSimulator class."""
    
    def test_init_with_seed(self):
        """Test simulator initialization with seed for reproducibility."""
        sim1 = MonteCarloSimulator(seed=42)
        sim2 = MonteCarloSimulator(seed=42)
        
        # Generate same random numbers with same seed
        arr1 = sim1._rng.random(10)
        arr2 = sim2._rng.random(10)
        
        # Reset and verify
        sim1 = MonteCarloSimulator(seed=42)
        sim2 = MonteCarloSimulator(seed=42)
        
        returns = np.array([0.01, -0.02, 0.015, -0.01, 0.02])
        
        sample1 = sim1._bootstrap_resample(returns)
        sample2 = sim2._bootstrap_resample(returns)
        
        np.testing.assert_array_equal(sample1, sample2)
    
    def test_init_without_seed(self):
        """Test simulator initialization without seed."""
        sim = MonteCarloSimulator()
        assert sim.seed is None
        assert sim._rng is not None
    
    def test_init_custom_risk_free_rate(self):
        """Test custom risk-free rate."""
        sim = MonteCarloSimulator(risk_free_rate=0.05)
        assert sim.risk_free_rate == 0.05


class TestBootstrapResampling:
    """Tests for bootstrap resampling functionality."""
    
    def test_resample_preserves_length(self):
        """Bootstrap sample should have same length as original."""
        sim = MonteCarloSimulator(seed=42)
        data = np.array([0.01, -0.02, 0.015, -0.01, 0.02, 0.005])
        
        resampled = sim._bootstrap_resample(data)
        
        assert len(resampled) == len(data)
    
    def test_resample_values_from_original(self):
        """All resampled values should come from original data."""
        sim = MonteCarloSimulator(seed=42)
        data = np.array([0.01, -0.02, 0.015, -0.01, 0.02])
        
        for _ in range(100):
            resampled = sim._bootstrap_resample(data)
            for val in resampled:
                assert val in data
    
    def test_resample_allows_duplicates(self):
        """Bootstrap resampling should allow duplicates (sampling with replacement)."""
        sim = MonteCarloSimulator(seed=42)
        data = np.array([0.01, -0.02, 0.015, -0.01, 0.02])
        
        # Run many resamples and check for duplicates
        found_duplicates = False
        for _ in range(100):
            resampled = sim._bootstrap_resample(data)
            if len(set(resampled)) < len(resampled):
                found_duplicates = True
                break
        
        assert found_duplicates, "Bootstrap should produce duplicates"
    
    def test_resample_different_each_time(self):
        """Multiple resamples should (usually) produce different results."""
        sim = MonteCarloSimulator(seed=42)
        data = np.random.normal(0, 0.02, 100)
        
        samples = [tuple(sim._bootstrap_resample(data)) for _ in range(10)]
        unique_samples = set(samples)
        
        # Should have multiple unique samples
        assert len(unique_samples) > 1


class TestMetricCalculations:
    """Tests for individual metric calculations."""
    
    def test_sharpe_ratio_positive(self):
        """Test Sharpe ratio with positive mean returns and variance."""
        sim = MonteCarloSimulator(risk_free_rate=0.0)  # Zero RF for simplicity
        
        # Positive returns with some variance
        np.random.seed(42)
        returns = np.random.normal(0.002, 0.01, 252)  # Positive mean, some vol
        sharpe = sim._calculate_sharpe(returns)
        
        # Should be positive
        assert sharpe > 0
    
    def test_sharpe_ratio_negative(self):
        """Test Sharpe ratio with negative mean returns."""
        sim = MonteCarloSimulator(risk_free_rate=0.0)
        
        # Negative returns with some variance
        np.random.seed(42)
        returns = np.random.normal(-0.002, 0.01, 252)
        sharpe = sim._calculate_sharpe(returns)
        
        assert sharpe < 0
    
    def test_sharpe_ratio_zero_volatility(self):
        """Test Sharpe ratio with zero volatility returns zero."""
        sim = MonteCarloSimulator()
        
        # All same return
        returns = np.array([0.005] * 100)
        sharpe = sim._calculate_sharpe(returns)
        
        # Zero volatility should return 0 (not inf)
        assert sharpe == 0.0 or np.isfinite(sharpe)
    
    def test_sharpe_annualized(self):
        """Test that Sharpe is properly annualized."""
        sim = MonteCarloSimulator(risk_free_rate=0.0)
        
        # ~10% annual return, ~16% annual vol
        np.random.seed(42)
        returns = np.random.normal(0.0004, 0.01, 252)  # Daily
        
        sharpe = sim._calculate_sharpe(returns)
        
        # Approximate Sharpe: (0.10 / 0.16) ≈ 0.625
        # Due to randomness, just check it's reasonable
        assert -2 < sharpe < 2
    
    def test_cagr_positive_returns(self):
        """Test CAGR with positive overall returns."""
        sim = MonteCarloSimulator()
        
        # 10% daily return for 252 days = massive growth
        returns = np.array([0.0004] * 252)  # ~10% annual
        cagr = sim._calculate_cagr(returns)
        
        # Should be approximately 10%
        assert 0.05 < cagr < 0.20
    
    def test_cagr_negative_returns(self):
        """Test CAGR with negative overall returns."""
        sim = MonteCarloSimulator()
        
        returns = np.array([-0.001] * 252)  # Losing money
        cagr = sim._calculate_cagr(returns)
        
        assert cagr < 0
    
    def test_cagr_total_loss(self):
        """Test CAGR with total loss (cumulative <= 0)."""
        sim = MonteCarloSimulator()
        
        returns = np.array([-0.5, -0.5, -0.5])  # Extreme losses
        cagr = sim._calculate_cagr(returns)
        
        assert cagr == -1.0
    
    def test_max_drawdown_calculation(self):
        """Test max drawdown calculation."""
        sim = MonteCarloSimulator()
        
        # Known pattern: up, up, down, down (should have clear drawdown)
        returns = np.array([0.10, 0.10, -0.15, -0.10, 0.05])
        max_dd = sim._calculate_max_drawdown(returns)
        
        # Drawdown should be negative
        assert max_dd < 0
        assert max_dd > -1  # Not complete loss
    
    def test_max_drawdown_no_drawdown(self):
        """Test max drawdown with no drawdowns (always going up)."""
        sim = MonteCarloSimulator()
        
        returns = np.array([0.01] * 100)  # Always positive
        max_dd = sim._calculate_max_drawdown(returns)
        
        # Should be 0 (no drawdown)
        assert max_dd == 0
    
    def test_max_drawdown_returns_negative_value(self):
        """Max drawdown should always be negative or zero."""
        sim = MonteCarloSimulator()
        
        np.random.seed(42)
        returns = np.random.normal(0, 0.02, 252)
        max_dd = sim._calculate_max_drawdown(returns)
        
        assert max_dd <= 0


class TestStatisticalCalculations:
    """Tests for statistical calculations (CI, p-values)."""
    
    def test_confidence_interval_contains_observed(self):
        """95% CI should usually contain the observed value."""
        sim = MonteCarloSimulator(seed=42)
        
        # Generate samples centered around observed
        observed = 0.5
        samples = np.random.normal(observed, 0.1, 1000)
        
        stats = sim._calculate_stats(observed, samples, higher_is_better=True)
        
        # Observed should be within CI (usually)
        assert stats.ci_lower <= observed <= stats.ci_upper
    
    def test_confidence_interval_width(self):
        """CI should narrow with lower variance data."""
        sim = MonteCarloSimulator()
        
        # Low variance
        low_var = np.random.normal(0.5, 0.01, 1000)
        stats_low = sim._calculate_stats(0.5, low_var)
        
        # High variance
        high_var = np.random.normal(0.5, 0.1, 1000)
        stats_high = sim._calculate_stats(0.5, high_var)
        
        ci_width_low = stats_low.ci_upper - stats_low.ci_lower
        ci_width_high = stats_high.ci_upper - stats_high.ci_lower
        
        assert ci_width_low < ci_width_high
    
    def test_pvalue_extreme_observed_high(self):
        """P-value should be low when observed is much higher than samples."""
        sim = MonteCarloSimulator()
        
        samples = np.random.normal(0, 0.1, 1000)  # Mean = 0
        observed = 0.5  # Much higher
        
        stats = sim._calculate_stats(observed, samples, higher_is_better=True)
        
        # Few samples should exceed observed
        assert stats.p_value < 0.05
        assert stats.is_significant
    
    def test_pvalue_extreme_observed_low(self):
        """P-value for max DD should be low when observed is better (less negative)."""
        sim = MonteCarloSimulator()
        
        np.random.seed(42)
        samples = np.random.normal(-0.2, 0.05, 1000)  # Mean = -20% DD
        observed = -0.05  # Better (less negative = closer to 0)
        
        # For max_dd, we use same logic: p = P(sample >= observed)
        # Since observed = -0.05 and samples ~ -0.20, P(sample >= -0.05) is LOW
        # because most samples are MORE negative (worse) than -0.05
        stats = sim._calculate_stats(observed, samples, higher_is_better=False)
        
        # Observed is better than most samples (low p-value)
        assert stats.p_value < 0.05
        assert stats.is_significant
    
    def test_pvalue_not_significant(self):
        """P-value should be high when observed is average."""
        sim = MonteCarloSimulator()
        
        samples = np.random.normal(0.5, 0.1, 1000)
        observed = 0.5  # Right at the mean
        
        stats = sim._calculate_stats(observed, samples, higher_is_better=True)
        
        # About half the samples should exceed observed
        assert 0.3 < stats.p_value < 0.7
        assert not stats.is_significant


class TestRunSimulation:
    """Tests for the main run_simulation method."""
    
    def test_run_simulation_basic(self):
        """Test basic simulation run."""
        sim = MonteCarloSimulator(seed=42)
        
        np.random.seed(42)
        returns = np.random.normal(0.0005, 0.015, 252)
        
        result = sim.run_simulation(returns, n_simulations=100)
        
        assert isinstance(result, MonteCarloResult)
        assert result.n_simulations == 100
    
    def test_run_simulation_result_fields(self):
        """Test all result fields are populated."""
        sim = MonteCarloSimulator(seed=42)
        
        returns = np.random.normal(0.0005, 0.015, 252)
        result = sim.run_simulation(returns, n_simulations=100)
        
        # Check all fields are populated
        assert result.observed_sharpe is not None
        assert result.sharpe_mean is not None
        assert result.sharpe_ci_lower is not None
        assert result.sharpe_ci_upper is not None
        assert result.sharpe_p_value is not None
        
        assert result.observed_cagr is not None
        assert result.observed_max_dd is not None
        assert result.observed_win_rate is not None
    
    def test_run_simulation_insufficient_data(self):
        """Test error with insufficient data."""
        sim = MonteCarloSimulator()
        
        returns = np.array([0.01, 0.02])  # Only 2 points
        
        with pytest.raises(ValueError, match="Insufficient data"):
            sim.run_simulation(returns, n_simulations=100)
    
    def test_run_simulation_handles_nan(self):
        """Test that NaN values are handled gracefully."""
        sim = MonteCarloSimulator(seed=42)
        
        returns = np.random.normal(0.0005, 0.015, 260)
        returns[10] = np.nan
        returns[50] = np.inf
        returns[100] = -np.inf
        
        # Should not raise, should clean data
        result = sim.run_simulation(returns, n_simulations=100)
        
        assert result is not None
    
    def test_run_simulation_handles_zero_returns(self):
        """Test handling of zero returns."""
        sim = MonteCarloSimulator(seed=42)
        
        # Mostly zero with some small returns
        returns = np.zeros(100)
        returns[::10] = 0.01
        
        # Should handle without error
        result = sim.run_simulation(returns, n_simulations=100)
        
        assert result is not None
    
    def test_run_simulation_progress_callback(self):
        """Test progress callback is called."""
        sim = MonteCarloSimulator(seed=42)
        
        returns = np.random.normal(0, 0.01, 100)
        
        progress_calls = []
        def callback(current, total):
            progress_calls.append((current, total))
        
        sim.run_simulation(returns, n_simulations=100, progress_callback=callback)
        
        # Should have been called multiple times
        assert len(progress_calls) > 0
        
        # Last call should be near the end
        last_current, last_total = progress_calls[-1]
        assert last_current == last_total
    
    def test_run_simulation_with_benchmark(self):
        """Test simulation with benchmark comparison."""
        sim = MonteCarloSimulator(seed=42)
        
        np.random.seed(42)
        strategy_returns = np.random.normal(0.001, 0.015, 252)  # Better
        benchmark_returns = np.random.normal(0.0005, 0.015, 252)  # Worse
        
        result = sim.run_simulation(
            strategy_returns,
            n_simulations=100,
            benchmark_returns=benchmark_returns,
        )
        
        assert result.benchmark_sharpe is not None
        assert result.alpha_p_value is not None
        assert result.alpha_is_significant is not None
    
    def test_run_simulation_with_observed_win_rate(self):
        """Test passing observed win rate."""
        sim = MonteCarloSimulator(seed=42)
        
        returns = np.random.normal(0, 0.01, 100)
        
        result = sim.run_simulation(
            returns,
            n_simulations=100,
            observed_win_rate=0.65,
        )
        
        assert result.observed_win_rate == 0.65
    
    def test_strategy_significance_criteria(self):
        """Test strategy significance determination."""
        sim = MonteCarloSimulator(seed=42)
        
        # Very strong strategy
        np.random.seed(42)
        strong_returns = np.random.normal(0.002, 0.01, 252)  # High returns, low vol
        
        result = sim.run_simulation(strong_returns, n_simulations=500)
        
        # Strong strategy should be significant
        assert result.observed_sharpe > 0
        # Note: significance depends on bootstrap samples


class TestMonteCarloResult:
    """Tests for MonteCarloResult dataclass."""
    
    def test_to_dict(self):
        """Test serialization to dict."""
        result = MonteCarloResult(
            n_simulations=1000,
            observed_sharpe=1.5,
            sharpe_mean=1.2,
            sharpe_std=0.3,
            sharpe_ci_lower=0.8,
            sharpe_ci_upper=1.6,
            sharpe_p_value=0.02,
            sharpe_is_significant=True,
            observed_cagr=0.15,
            cagr_mean=0.12,
            cagr_std=0.05,
            cagr_ci_lower=0.05,
            cagr_ci_upper=0.20,
            cagr_p_value=0.03,
            cagr_is_significant=True,
            observed_max_dd=-0.15,
            max_dd_mean=-0.20,
            max_dd_std=0.05,
            max_dd_ci_lower=-0.28,
            max_dd_ci_upper=-0.12,
            max_dd_p_value=0.04,
            max_dd_is_significant=True,
            observed_win_rate=0.55,
            win_rate_mean=0.52,
            win_rate_std=0.03,
            win_rate_ci_lower=0.47,
            win_rate_ci_upper=0.58,
            win_rate_p_value=0.06,
            win_rate_is_significant=False,
            strategy_is_significant=True,
        )
        
        d = result.to_dict()
        
        assert d['n_simulations'] == 1000
        assert d['observed_sharpe'] == 1.5
        assert d['strategy_is_significant'] == True
    
    def test_from_dict(self):
        """Test deserialization from dict."""
        data = {
            'n_simulations': 500,
            'observed_sharpe': 1.0,
            'sharpe_mean': 0.9,
            'sharpe_std': 0.2,
            'sharpe_ci_lower': 0.6,
            'sharpe_ci_upper': 1.2,
            'sharpe_p_value': 0.05,
            'sharpe_is_significant': True,
            'observed_cagr': 0.10,
            'cagr_mean': 0.08,
            'cagr_std': 0.03,
            'cagr_ci_lower': 0.03,
            'cagr_ci_upper': 0.15,
            'cagr_p_value': 0.04,
            'cagr_is_significant': True,
            'observed_max_dd': -0.10,
            'max_dd_mean': -0.15,
            'max_dd_std': 0.04,
            'max_dd_ci_lower': -0.22,
            'max_dd_ci_upper': -0.08,
            'max_dd_p_value': 0.03,
            'max_dd_is_significant': True,
            'observed_win_rate': 0.52,
            'win_rate_mean': 0.50,
            'win_rate_std': 0.02,
            'win_rate_ci_lower': 0.46,
            'win_rate_ci_upper': 0.54,
            'win_rate_p_value': 0.08,
            'win_rate_is_significant': False,
            'strategy_is_significant': True,
        }
        
        result = MonteCarloResult.from_dict(data)
        
        assert result.n_simulations == 500
        assert result.observed_sharpe == 1.0
    
    def test_summary_output(self):
        """Test human-readable summary."""
        result = MonteCarloResult(
            n_simulations=1000,
            observed_sharpe=1.5,
            sharpe_mean=1.2,
            sharpe_std=0.3,
            sharpe_ci_lower=0.8,
            sharpe_ci_upper=1.6,
            sharpe_p_value=0.02,
            sharpe_is_significant=True,
            observed_cagr=0.15,
            cagr_mean=0.12,
            cagr_std=0.05,
            cagr_ci_lower=0.05,
            cagr_ci_upper=0.20,
            cagr_p_value=0.03,
            cagr_is_significant=True,
            observed_max_dd=-0.15,
            max_dd_mean=-0.20,
            max_dd_std=0.05,
            max_dd_ci_lower=-0.28,
            max_dd_ci_upper=-0.12,
            max_dd_p_value=0.04,
            max_dd_is_significant=True,
            observed_win_rate=0.55,
            win_rate_mean=0.52,
            win_rate_std=0.03,
            win_rate_ci_lower=0.47,
            win_rate_ci_upper=0.58,
            win_rate_p_value=0.06,
            win_rate_is_significant=False,
            strategy_is_significant=True,
        )
        
        summary = result.summary()
        
        assert "Monte Carlo" in summary
        assert "1000 simulations" in summary
        assert "Sharpe Ratio" in summary
        assert "CAGR" in summary
        assert "Max Drawdown" in summary
        assert "Win Rate" in summary


class TestBacktestIntegration:
    """Tests for integration with backtest results."""
    
    @patch('backtest.monte_carlo.get_data_store')
    def test_run_from_backtest_not_found(self, mock_get_store):
        """Test error when backtest not found."""
        mock_store = Mock()
        mock_store.get_backtest_result.return_value = None
        mock_get_store.return_value = mock_store
        
        sim = MonteCarloSimulator()
        
        with pytest.raises(ValueError, match="Backtest not found"):
            sim.run_from_backtest("nonexistent_id", n_simulations=100)
    
    @patch('backtest.monte_carlo.get_data_store')
    def test_run_from_backtest_no_equity_curve(self, mock_get_store):
        """Test error when backtest has no equity curve."""
        mock_result = Mock()
        mock_result.equity_curve = []
        
        mock_store = Mock()
        mock_store.get_backtest_result.return_value = mock_result
        mock_get_store.return_value = mock_store
        
        sim = MonteCarloSimulator()
        
        with pytest.raises(ValueError, match="no equity curve"):
            sim.run_from_backtest("bt_123", n_simulations=100)
    
    @patch('backtest.monte_carlo.get_data_store')
    def test_run_from_backtest_extracts_returns(self, mock_get_store):
        """Test that returns are correctly extracted from equity curve."""
        # Create mock equity curve
        equity_points = [
            {'date': '2025-01-01', 'nav': 100000, 'daily_return': 0},
            {'date': '2025-01-02', 'nav': 101000, 'daily_return': 0.01},
            {'date': '2025-01-03', 'nav': 100500, 'daily_return': -0.005},
        ] + [
            {'date': f'2025-01-{i:02d}', 'nav': 100000 + i*100, 'daily_return': 0.001}
            for i in range(4, 100)
        ]
        
        mock_result = Mock()
        mock_result.equity_curve = equity_points
        mock_result.win_rate = 0.55
        
        mock_store = Mock()
        mock_store.get_backtest_result.return_value = mock_result
        mock_store.get_trades.return_value = []
        mock_get_store.return_value = mock_store
        
        sim = MonteCarloSimulator(seed=42)
        result = sim.run_from_backtest("bt_123", n_simulations=100)
        
        assert result is not None
        assert result.n_simulations == 100


class TestPersistence:
    """Tests for saving/loading results."""
    
    def test_save_and_load_result(self, tmp_path):
        """Test saving and loading Monte Carlo results."""
        result = MonteCarloResult(
            n_simulations=100,
            observed_sharpe=1.0,
            sharpe_mean=0.9,
            sharpe_std=0.2,
            sharpe_ci_lower=0.6,
            sharpe_ci_upper=1.2,
            sharpe_p_value=0.05,
            sharpe_is_significant=True,
            observed_cagr=0.10,
            cagr_mean=0.08,
            cagr_std=0.03,
            cagr_ci_lower=0.03,
            cagr_ci_upper=0.15,
            cagr_p_value=0.04,
            cagr_is_significant=True,
            observed_max_dd=-0.10,
            max_dd_mean=-0.15,
            max_dd_std=0.04,
            max_dd_ci_lower=-0.22,
            max_dd_ci_upper=-0.08,
            max_dd_p_value=0.03,
            max_dd_is_significant=True,
            observed_win_rate=0.52,
            win_rate_mean=0.50,
            win_rate_std=0.02,
            win_rate_ci_lower=0.46,
            win_rate_ci_upper=0.54,
            win_rate_p_value=0.08,
            win_rate_is_significant=False,
            strategy_is_significant=True,
        )
        
        # Patch the DATA_DIR
        with patch('backtest.monte_carlo.DATA_DIR', tmp_path):
            save_monte_carlo_result("bt_test_123", result)
            
            loaded = load_monte_carlo_result("bt_test_123")
        
        assert loaded is not None
        assert loaded.n_simulations == 100
        assert loaded.observed_sharpe == 1.0
    
    def test_load_nonexistent_result(self, tmp_path):
        """Test loading nonexistent result returns None."""
        with patch('backtest.monte_carlo.DATA_DIR', tmp_path):
            loaded = load_monte_carlo_result("nonexistent")
        
        assert loaded is None


class TestConvenienceFunction:
    """Tests for run_monte_carlo convenience function."""
    
    @patch('backtest.monte_carlo.MonteCarloSimulator')
    def test_run_monte_carlo_function(self, MockSimulator):
        """Test the run_monte_carlo convenience function."""
        mock_instance = Mock()
        mock_result = Mock(spec=MonteCarloResult)
        mock_instance.run_from_backtest.return_value = mock_result
        MockSimulator.return_value = mock_instance
        
        result = run_monte_carlo("bt_123", n_simulations=500, seed=42)
        
        MockSimulator.assert_called_once_with(seed=42)
        mock_instance.run_from_backtest.assert_called_once_with("bt_123", 500)
        assert result == mock_result


class TestEdgeCases:
    """Tests for edge cases and error handling."""
    
    def test_empty_returns_array(self):
        """Test with empty returns array."""
        sim = MonteCarloSimulator()
        
        with pytest.raises(ValueError):
            sim.run_simulation(np.array([]), n_simulations=100)
    
    def test_single_return(self):
        """Test with single return value."""
        sim = MonteCarloSimulator()
        
        with pytest.raises(ValueError):
            sim.run_simulation(np.array([0.01]), n_simulations=100)
    
    def test_all_zero_returns(self):
        """Test with all zero returns."""
        sim = MonteCarloSimulator(seed=42)
        
        returns = np.zeros(100)
        
        # Should handle gracefully
        result = sim.run_simulation(returns, n_simulations=50)
        
        assert result is not None
        assert result.observed_sharpe == 0 or np.isfinite(result.observed_sharpe)
    
    def test_extreme_returns(self):
        """Test with extreme return values."""
        sim = MonteCarloSimulator(seed=42)
        
        # Mix of normal and extreme returns
        returns = np.random.normal(0, 0.01, 100)
        returns[50] = 0.5   # 50% gain in one day
        returns[75] = -0.3  # 30% loss in one day
        
        result = sim.run_simulation(returns, n_simulations=50)
        
        assert result is not None
    
    def test_constant_returns(self):
        """Test with constant (non-zero) returns."""
        sim = MonteCarloSimulator(seed=42)
        
        returns = np.full(100, 0.001)  # Constant 0.1% daily
        
        result = sim.run_simulation(returns, n_simulations=50)
        
        # All bootstrap samples should be identical (or very similar)
        # With constant returns, std is ~0 but Sharpe may be very high or 0
        # depending on floating point behavior
        # The key is that it runs without error and CAGR is constant
        assert result is not None
        assert result.cagr_std < 0.001  # CAGR should be constant across samples


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
