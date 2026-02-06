"""
Unit tests for F12.1 Historical Data Persistence (data_store.py)
"""

import pytest
import json
import tempfile
from pathlib import Path
from datetime import datetime

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from backtest.data_store import (
    BacktestDataStore,
    BacktestParameters,
    BacktestResult,
    BacktestStatus,
    BacktestTrade,
    EquityPoint,
    HistoricalScore,
)


@pytest.fixture
def temp_store():
    """Create a temporary data store for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = BacktestDataStore(data_dir=Path(tmpdir))
        yield store


class TestHistoricalScores:
    """Tests for historical score storage."""
    
    def test_save_and_retrieve_scores(self, temp_store):
        """Test saving and retrieving historical scores."""
        scores = [
            HistoricalScore(
                date="2025-01-06",
                ticker="AAPL",
                composite_score=75.0,
                signal="BUY",
                fundamental_score=80.0,
                sentiment_score=70.0,
                technical_score=75.0,
                macro_score=72.0,
                sector="Technology",
            ),
            HistoricalScore(
                date="2025-01-06",
                ticker="MSFT",
                composite_score=72.0,
                signal="BUY",
                fundamental_score=75.0,
                sentiment_score=68.0,
                technical_score=73.0,
                macro_score=72.0,
                sector="Technology",
            ),
        ]
        
        saved = temp_store.save_historical_scores(scores)
        assert saved == 2
        
        # Retrieve
        retrieved = temp_store.get_historical_scores("2025-01-01", "2025-01-31")
        assert "2025-01-06" in retrieved
        assert "AAPL" in retrieved["2025-01-06"]
        assert retrieved["2025-01-06"]["AAPL"].composite_score == 75.0
    
    def test_get_score_on_date(self, temp_store):
        """Test getting a specific score by ticker and date."""
        score = HistoricalScore(
            date="2025-02-01",
            ticker="GOOGL",
            composite_score=68.0,
            signal="HOLD",
            fundamental_score=70.0,
            sentiment_score=65.0,
            technical_score=70.0,
            macro_score=68.0,
        )
        temp_store.save_historical_scores([score])
        
        result = temp_store.get_score_on_date("GOOGL", "2025-02-01")
        assert result is not None
        assert result.composite_score == 68.0
        assert result.signal == "HOLD"
    
    def test_date_range(self, temp_store):
        """Test getting available date range."""
        scores = [
            HistoricalScore(date="2025-01-01", ticker="A", composite_score=50, signal="HOLD",
                          fundamental_score=50, sentiment_score=50, technical_score=50, macro_score=50),
            HistoricalScore(date="2025-03-15", ticker="B", composite_score=50, signal="HOLD",
                          fundamental_score=50, sentiment_score=50, technical_score=50, macro_score=50),
        ]
        temp_store.save_historical_scores(scores)
        
        min_date, max_date = temp_store.get_available_date_range()
        assert min_date == "2025-01-01"
        assert max_date == "2025-03-15"
    
    def test_empty_date_range(self, temp_store):
        """Test date range when no data."""
        min_date, max_date = temp_store.get_available_date_range()
        assert min_date is None
        assert max_date is None
    
    def test_score_count(self, temp_store):
        """Test counting historical scores."""
        scores = [
            HistoricalScore(date="2025-01-01", ticker="A", composite_score=50, signal="HOLD",
                          fundamental_score=50, sentiment_score=50, technical_score=50, macro_score=50),
            HistoricalScore(date="2025-01-01", ticker="B", composite_score=50, signal="HOLD",
                          fundamental_score=50, sentiment_score=50, technical_score=50, macro_score=50),
            HistoricalScore(date="2025-01-08", ticker="A", composite_score=50, signal="HOLD",
                          fundamental_score=50, sentiment_score=50, technical_score=50, macro_score=50),
        ]
        temp_store.save_historical_scores(scores)
        
        count = temp_store.get_historical_score_count()
        assert count == 3


class TestBacktestResults:
    """Tests for backtest result storage."""
    
    def test_create_backtest(self, temp_store):
        """Test creating a new backtest."""
        params = BacktestParameters(
            start_date="2021-01-01",
            end_date="2025-12-31",
            initial_capital=100000,
            entry_threshold=70,
            exit_threshold=50,
            max_positions=10,
        )
        
        result = temp_store.create_backtest(params)
        
        assert result.backtest_id.startswith("bt_")
        assert result.status == BacktestStatus.PENDING
        assert result.parameters.initial_capital == 100000
    
    def test_save_and_get_result(self, temp_store):
        """Test saving and retrieving backtest results."""
        params = BacktestParameters(
            start_date="2021-01-01",
            end_date="2021-12-31",
            initial_capital=50000,
        )
        
        result = temp_store.create_backtest(params)
        result.status = BacktestStatus.COMPLETED
        result.total_return = 0.15
        result.sharpe_ratio = 1.2
        result.max_drawdown = -0.12
        
        temp_store.save_backtest_result(result)
        
        retrieved = temp_store.get_backtest_result(result.backtest_id)
        assert retrieved is not None
        assert retrieved.status == BacktestStatus.COMPLETED
        assert retrieved.total_return == 0.15
        assert retrieved.sharpe_ratio == 1.2
    
    def test_list_backtests(self, temp_store):
        """Test listing backtest results."""
        # Create multiple backtests
        for i in range(5):
            params = BacktestParameters(
                start_date=f"202{i}-01-01",
                end_date=f"202{i}-12-31",
                initial_capital=100000,
            )
            temp_store.create_backtest(params)
        
        results = temp_store.list_backtests(limit=3)
        assert len(results) == 3
    
    def test_delete_backtest(self, temp_store):
        """Test deleting a backtest."""
        params = BacktestParameters(
            start_date="2021-01-01",
            end_date="2021-12-31",
            initial_capital=100000,
        )
        
        result = temp_store.create_backtest(params)
        backtest_id = result.backtest_id
        
        # Delete
        deleted = temp_store.delete_backtest(backtest_id)
        assert deleted is True
        
        # Verify deleted
        retrieved = temp_store.get_backtest_result(backtest_id)
        assert retrieved is None
    
    def test_filter_by_status(self, temp_store):
        """Test filtering backtests by status."""
        params = BacktestParameters(
            start_date="2021-01-01",
            end_date="2021-12-31",
            initial_capital=100000,
        )
        
        # Create pending
        pending = temp_store.create_backtest(params)
        
        # Create completed
        completed = temp_store.create_backtest(params)
        completed.status = BacktestStatus.COMPLETED
        temp_store.save_backtest_result(completed)
        
        # Filter
        pending_results = temp_store.list_backtests(status=BacktestStatus.PENDING)
        completed_results = temp_store.list_backtests(status=BacktestStatus.COMPLETED)
        
        assert len(pending_results) == 1
        assert len(completed_results) == 1


class TestBacktestTrades:
    """Tests for backtest trade storage."""
    
    def test_save_and_get_trades(self, temp_store):
        """Test saving and retrieving trades."""
        trades = [
            BacktestTrade(
                trade_id="t1",
                backtest_id="bt_test",
                date="2021-01-15",
                ticker="AAPL",
                side="buy",
                quantity=10,
                price=150.0,
                value=1500.0,
                score_at_trade=75.0,
                signal_at_trade="BUY",
            ),
            BacktestTrade(
                trade_id="t2",
                backtest_id="bt_test",
                date="2021-02-01",
                ticker="AAPL",
                side="sell",
                quantity=10,
                price=165.0,
                value=1650.0,
                score_at_trade=45.0,
                signal_at_trade="HOLD",
            ),
        ]
        
        saved = temp_store.save_trades("bt_test", trades)
        assert saved == 2
        
        retrieved = temp_store.get_trades("bt_test")
        assert len(retrieved) == 2
        assert retrieved[0].ticker == "AAPL"
        assert retrieved[1].price == 165.0


class TestEquityPoint:
    """Tests for equity point data class."""
    
    def test_equity_point_creation(self):
        """Test creating an equity point."""
        ep = EquityPoint(
            date="2021-01-15",
            nav=105000,
            cash=5000,
            positions_value=100000,
            daily_return=0.005,
            cumulative_return=0.05,
            drawdown=-0.02,
        )
        
        assert ep.nav == 105000
        assert ep.daily_return == 0.005
    
    def test_equity_point_to_dict(self):
        """Test converting equity point to dict."""
        ep = EquityPoint(
            date="2021-01-15",
            nav=100000,
            cash=10000,
            positions_value=90000,
        )
        
        d = ep.to_dict()
        assert d["date"] == "2021-01-15"
        assert d["nav"] == 100000


class TestStorageStats:
    """Tests for storage statistics."""
    
    def test_get_stats(self, temp_store):
        """Test getting storage statistics."""
        # Add some data
        scores = [
            HistoricalScore(date="2025-01-01", ticker="A", composite_score=50, signal="HOLD",
                          fundamental_score=50, sentiment_score=50, technical_score=50, macro_score=50),
        ]
        temp_store.save_historical_scores(scores)
        
        params = BacktestParameters(
            start_date="2021-01-01",
            end_date="2021-12-31",
            initial_capital=100000,
        )
        temp_store.create_backtest(params)
        
        stats = temp_store.get_storage_stats()
        
        assert "historical_scores_count" in stats
        assert "backtest_count" in stats
        assert stats["historical_scores_count"] == 1
        assert stats["backtest_count"] == 1


class TestDataCleanup:
    """Tests for data cleanup functionality."""
    
    def test_cleanup_old_data(self, temp_store):
        """Test cleaning up old data."""
        # Add old and recent scores
        old_score = HistoricalScore(
            date="2020-01-01",  # Very old
            ticker="OLD",
            composite_score=50,
            signal="HOLD",
            fundamental_score=50,
            sentiment_score=50,
            technical_score=50,
            macro_score=50,
        )
        recent_score = HistoricalScore(
            date=datetime.now().strftime("%Y-%m-%d"),  # Today
            ticker="NEW",
            composite_score=50,
            signal="HOLD",
            fundamental_score=50,
            sentiment_score=50,
            technical_score=50,
            macro_score=50,
        )
        
        temp_store.save_historical_scores([old_score, recent_score])
        
        # Cleanup data older than 30 days
        removed = temp_store.cleanup_old_data(days_to_keep=30)
        
        assert removed >= 1
        
        # Verify old data removed
        min_date, _ = temp_store.get_available_date_range()
        assert min_date != "2020-01-01"
