"""
Tests for PortfolioHistoryService — real portfolio history from trade data.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock, AsyncMock

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from db.portfolio_history_service import PortfolioHistoryService


class TestPortfolioHistoryService:
    """Tests for real portfolio history computation."""

    @pytest.mark.asyncio
    async def test_get_real_history_no_portfolio(self):
        """Test with no portfolio returns empty list."""
        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        
        async def mock_execute(*args, **kwargs):
            return mock_result
        mock_db.execute = mock_execute
        
        result = await PortfolioHistoryService.get_real_history(mock_db, "test-user", 7)
        assert result == []

    @pytest.mark.asyncio
    async def test_get_real_history_no_trades(self):
        """Test with portfolio but no trades returns flat history."""
        mock_db = AsyncMock()
        
        # Mock portfolio
        mock_portfolio = MagicMock()
        mock_portfolio.starting_cash = 100000.0
        mock_portfolio.cash_balance = 100000.0
        mock_portfolio.id = "test-portfolio"
        
        # Calls: 1) portfolio lookup, 2) snapshots query (empty), 3) orders query (empty)
        empty_snapshot_result = MagicMock()
        empty_snapshot_result.fetchall.return_value = []
        
        results = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=mock_portfolio)),
            empty_snapshot_result,  # snapshots query returns empty
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))),
        ]
        mock_db.execute = AsyncMock(side_effect=results)
        
        result = await PortfolioHistoryService.get_real_history(mock_db, "test-user", 7)
        
        # Should have 8 days (7 + today)
        assert len(result) == 8
        # All values should be starting cash
        for point in result:
            assert point["total_value"] == 100000.0
            assert point["positions_value"] == 0.0

    def test_get_nearest_price_exact_match(self):
        """Test finding exact price match."""
        from datetime import date
        prices = {
            date(2026, 2, 4): 100.0,
            date(2026, 2, 5): 101.0,
        }
        
        result = PortfolioHistoryService._get_nearest_price(prices, date(2026, 2, 5))
        assert result == 101.0

    def test_get_nearest_price_weekend(self):
        """Test finding price when target is weekend."""
        from datetime import date
        prices = {
            date(2026, 2, 6): 100.0,  # Friday
        }
        
        # Saturday should find Friday's price
        result = PortfolioHistoryService._get_nearest_price(prices, date(2026, 2, 7))
        assert result == 100.0

    def test_get_nearest_price_empty(self):
        """Test with no prices."""
        result = PortfolioHistoryService._get_nearest_price({}, None)
        assert result is None

    def test_fetch_prices_sync_handles_error(self):
        """Test price fetching handles ticker errors gracefully."""
        with patch('db.portfolio_history_service.yf') as mock_yf:
            mock_yf.download.side_effect = Exception("API error")
            
            from datetime import date
            result = PortfolioHistoryService._fetch_prices_sync(
                ["AAPL"],
                date(2026, 2, 1),
                date(2026, 2, 5),
            )
            
            # Should return empty dict for failed ticker
            assert result == {"AAPL": {}}

    @pytest.mark.asyncio
    async def test_get_performance_insufficient_data(self):
        """Test performance with less than 2 data points."""
        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        
        async def mock_execute(*args, **kwargs):
            return mock_result
        mock_db.execute = mock_execute
        
        result = await PortfolioHistoryService.get_performance(mock_db, "test-user", 7)
        
        assert result["period_days"] == 7
        assert result["start_value"] is None
        assert result["end_value"] is None
        assert result["change"] is None

    @pytest.mark.asyncio
    async def test_get_performance_calculates_correctly(self):
        """Test performance calculation with mocked history."""
        with patch.object(
            PortfolioHistoryService,
            'get_real_history',
            new_callable=AsyncMock
        ) as mock_history:
            mock_history.return_value = [
                {"total_value": 100000.0},
                {"total_value": 101000.0},
            ]
            
            mock_db = AsyncMock()
            # get_performance now does a portfolio lookup for starting_cash
            mock_portfolio = MagicMock()
            mock_portfolio.starting_cash = 100000.0
            portfolio_result = MagicMock()
            portfolio_result.scalar_one_or_none.return_value = mock_portfolio
            mock_db.execute = AsyncMock(return_value=portfolio_result)
            
            result = await PortfolioHistoryService.get_performance(mock_db, "test-user", 7)
            
            assert result["period_days"] == 7
            assert result["start_value"] == 100000.0
            assert result["end_value"] == 101000.0
            assert result["change"] == 1000.0
            assert result["change_percent"] == 1.0


class TestNoMockData:
    """Verify no mock/synthetic data generation."""
    
    def test_no_random_import_in_service(self):
        """Ensure no random module for fake data."""
        import inspect
        from db import portfolio_history_service
        source = inspect.getsource(portfolio_history_service)
        
        assert "import random" not in source
        assert "random.uniform" not in source
        assert "random.random" not in source

    def test_no_synthetic_generation_in_service(self):
        """Ensure no synthetic data generation (random values)."""
        import inspect
        from db import portfolio_history_service
        source = inspect.getsource(portfolio_history_service)
        
        # Check for patterns that indicate fake data generation
        assert "random.uniform" not in source
        assert "random.randint" not in source
        assert "daily_var" not in source  # Pattern from old synthetic code
        assert "generate_synthetic" not in source.lower()
