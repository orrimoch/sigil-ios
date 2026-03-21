"""
Tests for PortfolioHistoryService — snapshot-based portfolio history.

Covers:
- Snapshot retrieval from cache
- Live computation fallback
- Batch price fetching
- Performance calculation (All period uses starting_cash)
- take_snapshot() for daily cron
- Edge cases: no snapshots, partial data, missing prices
"""

import pytest
from datetime import datetime, timezone, timedelta, date
from unittest.mock import patch, MagicMock, AsyncMock
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from db.portfolio_history_service import PortfolioHistoryService
from db.models import PortfolioSnapshot


# ══════════════════════════════════════════════════════════════
# Fixtures / Helpers
# ══════════════════════════════════════════════════════════════

def _make_portfolio(starting_cash=100000.0, cash_balance=5500.0, portfolio_id="test-portfolio"):
    """Create a mock portfolio object."""
    mock = MagicMock()
    mock.starting_cash = starting_cash
    mock.cash_balance = cash_balance
    mock.id = portfolio_id
    return mock


def _make_order(ticker, side, qty, price, filled_at_str):
    """Create a mock order object."""
    mock = MagicMock()
    mock.ticker = ticker
    mock.side = side
    mock.filled_quantity = qty
    mock.filled_price = price
    mock.filled_at = datetime.fromisoformat(filled_at_str)
    return mock


def _make_snapshot_row(dt_str, total_value, cash, positions_value, pnl, pnl_pct):
    """Create a tuple like what SQLite returns."""
    return (dt_str, total_value, cash, positions_value, pnl, pnl_pct)


# ══════════════════════════════════════════════════════════════
# Snapshot Retrieval Tests
# ══════════════════════════════════════════════════════════════

class TestSnapshotRetrieval:
    """Test _get_snapshots reads from portfolio_snapshots table."""

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_snapshots(self):
        """No rows in table → empty list."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await PortfolioHistoryService._get_snapshots(
            mock_db, "user-1", "portfolio-1", 30
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_formatted_snapshots(self):
        """Snapshots are returned in expected format."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            _make_snapshot_row("2026-02-05", 101000.0, 50000.0, 51000.0, 1000.0, 1.0),
            _make_snapshot_row("2026-02-06", 102000.0, 50000.0, 52000.0, 2000.0, 2.0),
        ]
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await PortfolioHistoryService._get_snapshots(
            mock_db, "user-1", "portfolio-1", 30
        )
        assert len(result) == 2
        assert result[0]["total_value"] == 101000.0
        assert result[0]["cash"] == 50000.0
        assert result[0]["positions_value"] == 51000.0
        assert result[0]["total_pnl"] == 1000.0
        assert result[0]["total_pnl_percent"] == 1.0
        assert "timestamp" in result[0]

    @pytest.mark.asyncio
    async def test_snapshot_timestamp_format(self):
        """Timestamp is ISO format."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            _make_snapshot_row("2026-02-05", 100000.0, 100000.0, 0.0, 0.0, 0.0),
        ]
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await PortfolioHistoryService._get_snapshots(
            mock_db, "user-1", "portfolio-1", 30
        )
        assert result[0]["timestamp"] == "2026-02-05T00:00:00"


# ══════════════════════════════════════════════════════════════
# get_real_history — snapshot-first logic
# ══════════════════════════════════════════════════════════════

class TestGetRealHistory:
    """Test get_real_history prefers snapshots, falls back to live."""

    @pytest.mark.asyncio
    async def test_no_portfolio_returns_empty(self):
        """No portfolio → empty list."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await PortfolioHistoryService.get_real_history(mock_db, "nonexistent", 30)
        assert result == []

    @pytest.mark.asyncio
    async def test_uses_snapshots_when_available(self):
        """When snapshots exist, returns them directly without live computation."""
        mock_db = AsyncMock()
        portfolio = _make_portfolio()

        # First call: portfolio lookup
        portfolio_result = MagicMock()
        portfolio_result.scalar_one_or_none.return_value = portfolio

        # Second call: snapshots query
        snapshot_result = MagicMock()
        snapshot_result.fetchall.return_value = [
            _make_snapshot_row("2026-02-05", 164000.0, 5500.0, 158500.0, 64000.0, 64.0),
        ]

        mock_db.execute = AsyncMock(side_effect=[portfolio_result, snapshot_result])

        with patch.object(PortfolioHistoryService, '_compute_live_history') as mock_live:
            result = await PortfolioHistoryService.get_real_history(mock_db, "user-1", 365)
            # Should NOT call live computation
            mock_live.assert_not_called()

        assert len(result) == 1
        assert result[0]["total_value"] == 164000.0

    @pytest.mark.asyncio
    async def test_falls_back_to_live_when_no_snapshots(self):
        """When no snapshots, falls back to live computation."""
        mock_db = AsyncMock()
        portfolio = _make_portfolio()

        portfolio_result = MagicMock()
        portfolio_result.scalar_one_or_none.return_value = portfolio

        # Empty snapshots
        snapshot_result = MagicMock()
        snapshot_result.fetchall.return_value = []

        mock_db.execute = AsyncMock(side_effect=[portfolio_result, snapshot_result])

        with patch.object(
            PortfolioHistoryService, '_compute_live_history',
            new_callable=AsyncMock, return_value=[{"total_value": 100000.0}]
        ) as mock_live:
            result = await PortfolioHistoryService.get_real_history(mock_db, "user-1", 30)
            mock_live.assert_called_once()

        assert result == [{"total_value": 100000.0}]


# ══════════════════════════════════════════════════════════════
# Performance calculation
# ══════════════════════════════════════════════════════════════

class TestGetPerformance:
    """Test performance metrics calculation."""

    @pytest.mark.asyncio
    async def test_all_period_uses_starting_cash(self):
        """
        For 'All' period (days >= 365), start_value = starting_cash ($100K),
        NOT the first day's computed value.
        """
        mock_db = AsyncMock()
        portfolio = _make_portfolio(starting_cash=100000.0)

        # Portfolio lookup
        portfolio_result = MagicMock()
        portfolio_result.scalar_one_or_none.return_value = portfolio

        mock_db.execute = AsyncMock(return_value=portfolio_result)

        with patch.object(
            PortfolioHistoryService,
            'get_real_history',
            new_callable=AsyncMock,
            return_value=[
                {"total_value": 150000.0},  # first day (would be wrong start if used)
                {"total_value": 164000.0},  # last day
            ],
        ):
            result = await PortfolioHistoryService.get_performance(mock_db, "user-1", 365)

        assert result["start_value"] == 100000.0  # starting_cash, not 150000
        assert result["end_value"] == 164000.0
        assert result["change"] == 64000.0
        assert result["change_percent"] == 64.0

    @pytest.mark.asyncio
    async def test_short_period_uses_first_day(self):
        """For shorter periods (< 365), start_value = first day's value."""
        mock_db = AsyncMock()
        portfolio = _make_portfolio(starting_cash=100000.0)

        portfolio_result = MagicMock()
        portfolio_result.scalar_one_or_none.return_value = portfolio
        mock_db.execute = AsyncMock(return_value=portfolio_result)

        with patch.object(
            PortfolioHistoryService,
            'get_real_history',
            new_callable=AsyncMock,
            return_value=[
                {"total_value": 160000.0},
                {"total_value": 164000.0},
            ],
        ):
            result = await PortfolioHistoryService.get_performance(mock_db, "user-1", 30)

        assert result["start_value"] == 160000.0  # first day's value, not starting_cash
        assert result["change"] == 4000.0
        assert result["change_percent"] == 2.5

    @pytest.mark.asyncio
    async def test_insufficient_data(self):
        """Less than 2 data points → null values."""
        mock_db = AsyncMock()
        portfolio_result = MagicMock()
        portfolio_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=portfolio_result)

        # get_real_history returns empty
        with patch.object(
            PortfolioHistoryService,
            'get_real_history',
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await PortfolioHistoryService.get_performance(mock_db, "user-1", 7)

        assert result["start_value"] is None
        assert result["end_value"] is None
        assert result["change"] is None

    @pytest.mark.asyncio
    async def test_zero_starting_cash(self):
        """Handle edge case of zero starting cash."""
        mock_db = AsyncMock()
        portfolio = _make_portfolio(starting_cash=0.0)

        portfolio_result = MagicMock()
        portfolio_result.scalar_one_or_none.return_value = portfolio
        mock_db.execute = AsyncMock(return_value=portfolio_result)

        with patch.object(
            PortfolioHistoryService,
            'get_real_history',
            new_callable=AsyncMock,
            return_value=[
                {"total_value": 0.0},
                {"total_value": 100.0},
            ],
        ):
            result = await PortfolioHistoryService.get_performance(mock_db, "user-1", 365)

        assert result["change_percent"] == 0  # avoid division by zero


# ══════════════════════════════════════════════════════════════
# Batch price fetching
# ══════════════════════════════════════════════════════════════

class TestBatchPriceFetching:
    """Test batch yfinance download."""

    def test_empty_tickers_returns_empty(self):
        """No tickers → empty dict."""
        result = PortfolioHistoryService._fetch_prices_batch_sync([], date(2026, 2, 1), date(2026, 2, 5))
        assert result == {}

    def test_single_ticker_error_handling(self):
        """When yfinance fails, return empty dict per ticker."""
        with patch('db.portfolio_history_service.yf') as mock_yf:
            mock_yf.download.side_effect = Exception("API error")
            result = PortfolioHistoryService._fetch_prices_batch_sync(
                ["AAPL"], date(2026, 2, 1), date(2026, 2, 5)
            )
            assert result == {"AAPL": {}}

    def test_legacy_method_redirects_to_batch(self):
        """_fetch_prices_sync redirects to _fetch_prices_batch_sync."""
        with patch.object(
            PortfolioHistoryService,
            '_fetch_prices_batch_sync',
            return_value={"AAPL": {date(2026, 2, 5): 150.0}},
        ) as mock_batch:
            result = PortfolioHistoryService._fetch_prices_sync(
                ["AAPL"], date(2026, 2, 1), date(2026, 2, 5)
            )
            mock_batch.assert_called_once()
            assert "AAPL" in result


# ══════════════════════════════════════════════════════════════
# Nearest price lookup
# ══════════════════════════════════════════════════════════════

class TestNearestPrice:
    """Test _get_nearest_price for weekends, holidays, missing data."""

    def test_exact_match(self):
        prices = {date(2026, 2, 5): 100.0, date(2026, 2, 6): 101.0}
        assert PortfolioHistoryService._get_nearest_price(prices, date(2026, 2, 6)) == 101.0

    def test_weekend_finds_friday(self):
        prices = {date(2026, 2, 6): 100.0}  # Friday
        # Saturday should find Friday's price
        assert PortfolioHistoryService._get_nearest_price(prices, date(2026, 2, 7)) == 100.0

    def test_empty_prices_returns_none(self):
        assert PortfolioHistoryService._get_nearest_price({}, date(2026, 2, 5)) is None

    def test_none_prices_returns_none(self):
        assert PortfolioHistoryService._get_nearest_price(None, date(2026, 2, 5)) is None

    def test_fallback_to_last_value(self):
        """When no price within 7 days, falls back to last available."""
        prices = {date(2026, 1, 15): 99.0}
        result = PortfolioHistoryService._get_nearest_price(prices, date(2026, 2, 5))
        assert result == 99.0


# ══════════════════════════════════════════════════════════════
# Live computation fallback
# ══════════════════════════════════════════════════════════════

class TestLiveComputation:
    """Test _compute_live_history when no snapshots exist."""

    @pytest.mark.asyncio
    async def test_no_orders_returns_flat_history(self):
        """Portfolio with no trades → flat line at starting cash."""
        mock_db = AsyncMock()
        portfolio = _make_portfolio(starting_cash=100000.0, cash_balance=100000.0)

        # Orders query returns empty
        orders_result = MagicMock()
        orders_result.scalars.return_value = MagicMock(all=MagicMock(return_value=[]))
        mock_db.execute = AsyncMock(return_value=orders_result)

        result = await PortfolioHistoryService._compute_live_history(
            mock_db, "user-1", portfolio, 7
        )

        assert len(result) == 8  # 7 days + today
        for point in result:
            assert point["total_value"] == 100000.0
            assert point["positions_value"] == 0.0

    @pytest.mark.asyncio
    async def test_applies_orders_correctly(self):
        """Buy order reduces cash, increases positions."""
        mock_db = AsyncMock()
        portfolio = _make_portfolio(starting_cash=100000.0, cash_balance=90000.0)

        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        order = _make_order("AAPL", "BUY", 100, 100.0, yesterday.isoformat())

        orders_result = MagicMock()
        orders_result.scalars.return_value = MagicMock(all=MagicMock(return_value=[order]))
        mock_db.execute = AsyncMock(return_value=orders_result)

        with patch.object(
            PortfolioHistoryService,
            '_fetch_historical_prices_batch',
            new_callable=AsyncMock,
            return_value={"AAPL": {yesterday.date(): 105.0, datetime.now(timezone.utc).date(): 110.0}},
        ):
            result = await PortfolioHistoryService._compute_live_history(
                mock_db, "user-1", portfolio, 1
            )

        # Should have at least 1 point where AAPL is held
        last = result[-1]
        assert last["cash"] == 90000.0
        assert last["positions_value"] > 0


# ══════════════════════════════════════════════════════════════
# take_snapshot (daily cron)
# ══════════════════════════════════════════════════════════════

class TestTakeSnapshot:
    """Test the daily snapshot creation."""

    @pytest.mark.asyncio
    async def test_no_portfolio_returns_none(self):
        """No portfolio → None."""
        mock_db = AsyncMock()
        portfolio_result = MagicMock()
        portfolio_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=portfolio_result)

        result = await PortfolioHistoryService.take_snapshot(mock_db, "nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_snapshot_creation_with_positions(self):
        """Creates snapshot with correct values."""
        mock_db = AsyncMock()
        portfolio = _make_portfolio(starting_cash=100000.0, cash_balance=50000.0, portfolio_id="p1")

        # Position mock
        position = MagicMock()
        position.ticker = "AAPL"
        position.quantity = 100
        position.avg_cost = 150.0

        portfolio_result = MagicMock()
        portfolio_result.scalar_one_or_none.return_value = portfolio

        positions_result = MagicMock()
        positions_result.scalars.return_value = MagicMock(all=MagicMock(return_value=[position]))

        mock_db.execute = AsyncMock(side_effect=[portfolio_result, positions_result, MagicMock()])
        mock_db.commit = AsyncMock()

        with patch.object(
            PortfolioHistoryService,
            '_fetch_current_prices_sync',
            return_value={"AAPL": 200.0},
        ):
            result = await PortfolioHistoryService.take_snapshot(mock_db, "user-1")

        assert result is not None
        assert result["cash"] == 50000.0
        assert result["positions_value"] == 20000.0  # 100 * 200
        assert result["total_value"] == 70000.0
        assert result["total_pnl"] == -30000.0  # 70K - 100K
        assert result["total_pnl_percent"] == -30.0

    @pytest.mark.asyncio
    async def test_snapshot_empty_portfolio(self):
        """Portfolio with no positions → cash only."""
        mock_db = AsyncMock()
        portfolio = _make_portfolio(starting_cash=100000.0, cash_balance=100000.0, portfolio_id="p1")

        portfolio_result = MagicMock()
        portfolio_result.scalar_one_or_none.return_value = portfolio

        positions_result = MagicMock()
        positions_result.scalars.return_value = MagicMock(all=MagicMock(return_value=[]))

        mock_db.execute = AsyncMock(side_effect=[portfolio_result, positions_result, MagicMock()])
        mock_db.commit = AsyncMock()

        result = await PortfolioHistoryService.take_snapshot(mock_db, "user-1")

        assert result is not None
        assert result["positions_value"] == 0
        assert result["total_value"] == 100000.0
        assert result["total_pnl"] == 0.0


# ══════════════════════════════════════════════════════════════
# PortfolioSnapshot model
# ══════════════════════════════════════════════════════════════

class TestPortfolioSnapshotModel:
    """Test the SQLAlchemy model exists and has correct fields."""

    def test_model_has_required_fields(self):
        """PortfolioSnapshot has all required columns."""
        columns = [c.name for c in PortfolioSnapshot.__table__.columns]
        expected = [
            "id", "user_id", "portfolio_id", "date",
            "total_value", "cash", "positions_value",
            "total_pnl", "total_pnl_percent", "created_at",
        ]
        for field in expected:
            assert field in columns, f"Missing column: {field}"

    def test_table_name(self):
        assert PortfolioSnapshot.__tablename__ == "portfolio_snapshots"


# ══════════════════════════════════════════════════════════════
# No mock/synthetic data
# ══════════════════════════════════════════════════════════════

class TestNoMockData:
    """Verify no mock/synthetic data generation."""

    def test_no_random_import(self):
        import inspect
        from db import portfolio_history_service
        source = inspect.getsource(portfolio_history_service)
        assert "import random" not in source
        assert "random.uniform" not in source

    def test_no_synthetic_generation(self):
        import inspect
        from db import portfolio_history_service
        source = inspect.getsource(portfolio_history_service)
        assert "generate_synthetic" not in source.lower()
        assert "daily_var" not in source
