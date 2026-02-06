"""
Unit tests for F12.4 Performance Metrics Calculator (metrics.py)
"""

import pytest
import numpy as np
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from backtest.metrics import (
    MetricsCalculator,
    PerformanceMetrics,
    ScoreValidationMetrics,
)
from backtest.data_store import EquityPoint


class TestPerformanceMetrics:
    """Tests for performance metric calculations."""
    
    @pytest.fixture
    def sample_equity_curve(self):
        """Sample equity curve for testing."""
        # 10 days of data with some volatility
        navs = [100000, 100500, 101000, 100200, 100800, 101500, 102000, 101800, 102500, 103000]
        dates = [f"2025-01-{i+1:02d}" for i in range(10)]
        
        curve = []
        for i, (date, nav) in enumerate(zip(dates, navs)):
            prev_nav = navs[i-1] if i > 0 else 100000
            daily_return = (nav - prev_nav) / prev_nav
            curve.append(EquityPoint(
                date=date,
                nav=nav,
                cash=10000,
                positions_value=nav - 10000,
                daily_return=daily_return,
                cumulative_return=(nav / 100000) - 1,
                drawdown=0,
            ))
        return curve
    
    def test_total_return(self, sample_equity_curve):
        """Test total return calculation."""
        calc = MetricsCalculator()
        
        metrics = calc.calculate_performance_metrics(
            equity_curve=sample_equity_curve,
            trades=[],
            initial_capital=100000,
            start_date="2025-01-01",
            end_date="2025-01-10",
        )
        
        # 103000 / 100000 - 1 = 0.03 = 3%
        assert abs(metrics.total_return - 0.03) < 0.001
    
    def test_volatility_positive(self, sample_equity_curve):
        """Test that volatility is positive."""
        calc = MetricsCalculator()
        
        metrics = calc.calculate_performance_metrics(
            equity_curve=sample_equity_curve,
            trades=[],
            initial_capital=100000,
            start_date="2025-01-01",
            end_date="2025-01-10",
        )
        
        assert metrics.volatility > 0
    
    def test_sharpe_ratio(self, sample_equity_curve):
        """Test Sharpe ratio calculation."""
        calc = MetricsCalculator()
        
        metrics = calc.calculate_performance_metrics(
            equity_curve=sample_equity_curve,
            trades=[],
            initial_capital=100000,
            start_date="2025-01-01",
            end_date="2025-01-10",
        )
        
        # Should be a reasonable number (high Sharpe possible with low vol)
        assert metrics.sharpe_ratio > 0  # Positive returns should give positive Sharpe
    
    def test_max_drawdown_calculation(self):
        """Test max drawdown calculation."""
        # Create curve with known drawdown
        navs = [100000, 105000, 100000, 95000, 98000]  # 10% drawdown from 105k to 95k
        dates = [f"2025-01-{i+1:02d}" for i in range(5)]
        
        curve = []
        for i, (date, nav) in enumerate(zip(dates, navs)):
            prev_nav = navs[i-1] if i > 0 else 100000
            daily_return = (nav - prev_nav) / prev_nav
            curve.append(EquityPoint(
                date=date,
                nav=nav,
                cash=10000,
                positions_value=nav - 10000,
                daily_return=daily_return,
                cumulative_return=(nav / 100000) - 1,
                drawdown=0,
            ))
        
        calc = MetricsCalculator()
        metrics = calc.calculate_performance_metrics(
            equity_curve=curve,
            trades=[],
            initial_capital=100000,
            start_date="2025-01-01",
            end_date="2025-01-05",
        )
        
        # Max drawdown should be about -9.5% (from 105k peak to 95k trough)
        assert metrics.max_drawdown < -0.08
        assert metrics.max_drawdown > -0.15


class TestTradeMetrics:
    """Tests for trade-based metrics."""
    
    def test_win_rate_all_wins(self):
        """Test win rate with all winning trades."""
        trades = [
            {"ticker": "AAPL", "side": "buy", "date": "2025-01-01", "price": 100, "quantity": 10},
            {"ticker": "AAPL", "side": "sell", "date": "2025-01-10", "price": 110, "quantity": 10},
            {"ticker": "MSFT", "side": "buy", "date": "2025-01-05", "price": 200, "quantity": 5},
            {"ticker": "MSFT", "side": "sell", "date": "2025-01-15", "price": 220, "quantity": 5},
        ]
        
        calc = MetricsCalculator()
        win_rate, profit_factor, _ = calc._calculate_trade_metrics(trades)
        
        assert win_rate == 1.0
        assert profit_factor > 1.0
    
    def test_win_rate_all_losses(self):
        """Test win rate with all losing trades."""
        trades = [
            {"ticker": "AAPL", "side": "buy", "date": "2025-01-01", "price": 110, "quantity": 10},
            {"ticker": "AAPL", "side": "sell", "date": "2025-01-10", "price": 100, "quantity": 10},
        ]
        
        calc = MetricsCalculator()
        win_rate, profit_factor, _ = calc._calculate_trade_metrics(trades)
        
        assert win_rate == 0.0
    
    def test_win_rate_mixed(self):
        """Test win rate with mixed trades."""
        trades = [
            {"ticker": "AAPL", "side": "buy", "date": "2025-01-01", "price": 100, "quantity": 10},
            {"ticker": "AAPL", "side": "sell", "date": "2025-01-10", "price": 110, "quantity": 10},  # Win
            {"ticker": "MSFT", "side": "buy", "date": "2025-01-05", "price": 200, "quantity": 5},
            {"ticker": "MSFT", "side": "sell", "date": "2025-01-15", "price": 190, "quantity": 5},  # Loss
        ]
        
        calc = MetricsCalculator()
        win_rate, _, _ = calc._calculate_trade_metrics(trades)
        
        assert win_rate == 0.5
    
    def test_empty_trades(self):
        """Test with no trades."""
        calc = MetricsCalculator()
        win_rate, profit_factor, avg_holding = calc._calculate_trade_metrics([])
        
        assert win_rate == 0.5  # Default
        assert profit_factor == 1.0


class TestHelperMethods:
    """Tests for helper methods."""
    
    def test_add_trading_days(self):
        """Test adding trading days."""
        calc = MetricsCalculator()
        
        # Friday + 5 trading days = next Friday
        result = calc._add_trading_days("2025-01-03", 5)  # Friday
        assert result == "2025-01-10"  # Next Friday
        
        # Monday + 1 = Tuesday
        result = calc._add_trading_days("2025-01-06", 1)  # Monday
        assert result == "2025-01-07"  # Tuesday
    
    def test_add_trading_days_weekend(self):
        """Test adding trading days skips weekends."""
        calc = MetricsCalculator()
        
        # Thursday + 2 = Monday (skip weekend)
        result = calc._add_trading_days("2025-01-02", 2)  # Thursday
        assert result == "2025-01-06"  # Monday


class TestMetricsBoundaries:
    """Test edge cases and boundaries."""
    
    def test_single_day_equity_curve(self):
        """Test with single day (should handle gracefully)."""
        curve = [EquityPoint(
            date="2025-01-01",
            nav=100000,
            cash=10000,
            positions_value=90000,
        )]
        
        calc = MetricsCalculator()
        metrics = calc.calculate_performance_metrics(
            equity_curve=curve,
            trades=[],
            initial_capital=100000,
            start_date="2025-01-01",
            end_date="2025-01-01",
        )
        
        # Should return empty/default metrics without crashing
        assert metrics is not None
    
    def test_zero_volatility(self):
        """Test with flat equity curve (zero volatility)."""
        # Flat NAV
        navs = [100000, 100000, 100000, 100000, 100000]
        dates = [f"2025-01-{i+1:02d}" for i in range(5)]
        
        curve = [EquityPoint(
            date=date,
            nav=nav,
            cash=10000,
            positions_value=nav - 10000,
            daily_return=0,
            cumulative_return=0,
            drawdown=0,
        ) for date, nav in zip(dates, navs)]
        
        calc = MetricsCalculator()
        metrics = calc.calculate_performance_metrics(
            equity_curve=curve,
            trades=[],
            initial_capital=100000,
            start_date="2025-01-01",
            end_date="2025-01-05",
        )
        
        assert metrics.total_return == 0
        assert metrics.volatility == 0


class TestScoreValidationMetrics:
    """Tests for score validation metrics."""
    
    def test_empty_validation_metrics(self):
        """Test getting empty validation metrics."""
        calc = MetricsCalculator()
        metrics = calc._empty_validation_metrics()
        
        assert metrics.score_ic == 0
        assert metrics.hit_rate == 0.5
        assert metrics.quintile_spread == 0


class TestPerformanceMetricsDataclass:
    """Tests for PerformanceMetrics dataclass."""
    
    def test_to_dict(self):
        """Test converting metrics to dict."""
        metrics = PerformanceMetrics(
            total_return=0.15,
            cagr=0.12,
            volatility=0.18,
            sharpe_ratio=1.2,
            sortino_ratio=1.5,
            max_drawdown=-0.10,
            calmar_ratio=1.2,
            win_rate=0.55,
            profit_factor=1.8,
            total_trades=50,
            avg_holding_period_days=7.5,
            benchmark_return=0.10,
            alpha=0.05,
            beta=0.9,
            tracking_error=0.08,
            information_ratio=0.6,
        )
        
        d = metrics.to_dict()
        
        assert d["total_return"] == 0.15
        assert d["sharpe_ratio"] == 1.2
        assert d["total_trades"] == 50


class TestScoreValidationMetricsDataclass:
    """Tests for ScoreValidationMetrics dataclass."""
    
    def test_to_dict(self):
        """Test converting validation metrics to dict."""
        metrics = ScoreValidationMetrics(
            score_ic=0.08,
            score_ic_t_stat=2.5,
            score_ic_p_value=0.01,
            hit_rate=0.58,
            hit_rate_by_score_bucket={"70-80": 0.55, "80-90": 0.62},
            quintile_returns={"Q1": 0.10, "Q5": 0.02},
            quintile_spread=0.08,
            avg_score_change=3.5,
            signal_flip_rate=0.15,
        )
        
        d = metrics.to_dict()
        
        assert d["score_ic"] == 0.08
        assert d["hit_rate"] == 0.58
        assert "70-80" in d["hit_rate_by_score_bucket"]
