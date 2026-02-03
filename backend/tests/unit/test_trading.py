"""
Tests for F6.x Trading Module

Tests portfolio management and order execution.
"""

import pytest
import json
from pathlib import Path
from datetime import datetime
import tempfile
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from trading.portfolio import Portfolio, Position, PortfolioSummary, PortfolioSnapshot, PortfolioHistory, DEFAULT_CASH
from trading.orders import Order, OrderType, OrderSide, OrderStatus, OrderManager


# ========== Portfolio Tests ==========

class TestPosition:
    """Tests for Position class."""
    
    def test_position_creation(self):
        """Test basic position creation."""
        pos = Position(ticker="AAPL", shares=10, avg_cost=150.0)
        
        assert pos.ticker == "AAPL"
        assert pos.shares == 10
        assert pos.avg_cost == 150.0
    
    def test_cost_basis(self):
        """Test cost basis calculation."""
        pos = Position(ticker="AAPL", shares=10, avg_cost=150.0)
        assert pos.cost_basis == 1500.0
    
    def test_market_value(self):
        """Test market value calculation."""
        pos = Position(ticker="AAPL", shares=10, avg_cost=150.0)
        assert pos.market_value(160.0) == 1600.0
    
    def test_unrealized_pnl_profit(self):
        """Test unrealized P&L with profit."""
        pos = Position(ticker="AAPL", shares=10, avg_cost=150.0)
        
        pnl = pos.unrealized_pnl(160.0)
        assert pnl == 100.0  # 1600 - 1500
        
        pnl_pct = pos.unrealized_pnl_percent(160.0)
        assert abs(pnl_pct - 6.67) < 0.01  # ~6.67%
    
    def test_unrealized_pnl_loss(self):
        """Test unrealized P&L with loss."""
        pos = Position(ticker="AAPL", shares=10, avg_cost=150.0)
        
        pnl = pos.unrealized_pnl(140.0)
        assert pnl == -100.0  # 1400 - 1500
    
    def test_position_serialization(self):
        """Test position to/from dict."""
        pos = Position(ticker="AAPL", shares=10, avg_cost=150.0)
        
        data = pos.to_dict()
        restored = Position.from_dict(data)
        
        assert restored.ticker == pos.ticker
        assert restored.shares == pos.shares
        assert restored.avg_cost == pos.avg_cost


class TestPortfolio:
    """Tests for Portfolio class."""
    
    def test_portfolio_creation(self):
        """Test portfolio initialization."""
        portfolio = Portfolio(starting_cash=50000.0)
        
        assert portfolio.cash == 50000.0
        assert portfolio.starting_cash == 50000.0
        assert portfolio.is_paper is True
        assert len(portfolio.positions) == 0
    
    def test_add_position(self):
        """Test buying a stock."""
        portfolio = Portfolio(starting_cash=10000.0)
        
        portfolio.add_position("AAPL", shares=10, price=150.0)
        
        assert portfolio.cash == 8500.0  # 10000 - 1500
        assert "AAPL" in portfolio.positions
        assert portfolio.positions["AAPL"].shares == 10
        assert portfolio.positions["AAPL"].avg_cost == 150.0
    
    def test_add_to_existing_position(self):
        """Test adding to existing position updates avg cost."""
        portfolio = Portfolio(starting_cash=10000.0)
        
        portfolio.add_position("AAPL", shares=10, price=100.0)
        portfolio.add_position("AAPL", shares=10, price=200.0)
        
        pos = portfolio.positions["AAPL"]
        assert pos.shares == 20
        assert pos.avg_cost == 150.0  # (1000 + 2000) / 20
    
    def test_insufficient_cash_buy(self):
        """Test buying with insufficient cash."""
        portfolio = Portfolio(starting_cash=1000.0)
        
        with pytest.raises(ValueError, match="Insufficient cash"):
            portfolio.add_position("AAPL", shares=100, price=150.0)
    
    def test_reduce_position(self):
        """Test selling shares."""
        portfolio = Portfolio(starting_cash=10000.0)
        portfolio.add_position("AAPL", shares=10, price=100.0)
        
        # Sell at profit
        pnl = portfolio.reduce_position("AAPL", shares=5, price=120.0)
        
        assert pnl == 100.0  # (120 - 100) * 5
        assert portfolio.positions["AAPL"].shares == 5
        assert portfolio.cash == 9600.0  # 9000 + 600
        assert portfolio.realized_pnl == 100.0
    
    def test_close_position(self):
        """Test closing entire position."""
        portfolio = Portfolio(starting_cash=10000.0)
        portfolio.add_position("AAPL", shares=10, price=100.0)
        
        pnl = portfolio.close_position("AAPL", price=110.0)
        
        assert pnl == 100.0
        assert "AAPL" not in portfolio.positions
    
    def test_sell_more_than_owned(self):
        """Test selling more shares than owned."""
        portfolio = Portfolio(starting_cash=10000.0)
        portfolio.add_position("AAPL", shares=10, price=100.0)
        
        with pytest.raises(ValueError, match="Cannot sell"):
            portfolio.reduce_position("AAPL", shares=20, price=100.0)
    
    def test_sell_nonexistent_position(self):
        """Test selling stock not owned."""
        portfolio = Portfolio(starting_cash=10000.0)
        
        with pytest.raises(ValueError, match="No position"):
            portfolio.reduce_position("AAPL", shares=10, price=100.0)
    
    def test_portfolio_reset(self):
        """Test portfolio reset."""
        portfolio = Portfolio(starting_cash=10000.0)
        portfolio.add_position("AAPL", shares=10, price=100.0)
        
        portfolio.reset(starting_cash=50000.0)
        
        assert portfolio.cash == 50000.0
        assert len(portfolio.positions) == 0
        assert portfolio.realized_pnl == 0.0
    
    def test_portfolio_summary(self):
        """Test portfolio summary calculation."""
        portfolio = Portfolio(starting_cash=10000.0)
        portfolio.add_position("AAPL", shares=10, price=100.0)
        
        # Provide mock prices
        prices = {"AAPL": 110.0}
        summary = portfolio.get_summary(prices)
        
        assert summary.cash == 9000.0
        assert summary.positions_value == 1100.0
        assert summary.total_value == 10100.0
        assert summary.total_pnl == 100.0
        assert summary.positions_count == 1
    
    def test_portfolio_serialization(self):
        """Test portfolio to/from dict."""
        portfolio = Portfolio(starting_cash=10000.0)
        portfolio.add_position("AAPL", shares=10, price=100.0)
        portfolio.add_position("MSFT", shares=5, price=200.0)
        
        data = portfolio.to_dict()
        restored = Portfolio.from_dict(data)
        
        assert restored.cash == portfolio.cash
        assert len(restored.positions) == 2
        assert restored.positions["AAPL"].shares == 10
    
    def test_portfolio_save_load(self):
        """Test portfolio file persistence."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "portfolio.json"
            
            portfolio = Portfolio(starting_cash=10000.0)
            portfolio.add_position("AAPL", shares=10, price=100.0)
            portfolio.save(path)
            
            loaded = Portfolio.load(path)
            
            assert loaded is not None
            assert loaded.cash == portfolio.cash
            assert "AAPL" in loaded.positions


# ========== Order Tests ==========

class TestOrder:
    """Tests for Order class."""
    
    def test_order_creation(self):
        """Test basic order creation."""
        order = Order(
            order_id="test123",
            ticker="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=10,
        )
        
        assert order.order_id == "test123"
        assert order.ticker == "AAPL"
        assert order.side == OrderSide.BUY
        assert order.status == OrderStatus.PENDING
    
    def test_limit_order(self):
        """Test limit order creation."""
        order = Order(
            order_id="test123",
            ticker="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=10,
            limit_price=150.0,
        )
        
        assert order.order_type == OrderType.LIMIT
        assert order.limit_price == 150.0
    
    def test_order_is_complete(self):
        """Test order completion detection."""
        order = Order(
            order_id="test123",
            ticker="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=10,
        )
        
        assert order.is_complete is False
        
        order.status = OrderStatus.FILLED
        assert order.is_complete is True
        
        order.status = OrderStatus.CANCELLED
        assert order.is_complete is True
    
    def test_remaining_quantity(self):
        """Test remaining quantity calculation."""
        order = Order(
            order_id="test123",
            ticker="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=10,
        )
        
        assert order.remaining_quantity == 10
        
        order.filled_quantity = 5
        assert order.remaining_quantity == 5
    
    def test_order_serialization(self):
        """Test order to/from dict."""
        order = Order(
            order_id="test123",
            ticker="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=10,
            limit_price=150.0,
        )
        
        data = order.to_dict()
        restored = Order.from_dict(data)
        
        assert restored.order_id == order.order_id
        assert restored.side == OrderSide.BUY
        assert restored.order_type == OrderType.LIMIT


class TestOrderManager:
    """Tests for OrderManager class."""
    
    @pytest.fixture
    def manager(self):
        """Create a fresh order manager with test portfolio."""
        portfolio = Portfolio(starting_cash=100000.0)
        return OrderManager(portfolio=portfolio)
    
    def test_create_buy_order(self, manager):
        """Test creating a buy order."""
        # Add some cash position
        order = manager.create_order(
            ticker="AAPL",
            side=OrderSide.BUY,
            quantity=1,
            order_type=OrderType.MARKET,
        )
        
        assert order.ticker == "AAPL"
        assert order.side == OrderSide.BUY
        # For paper trading, market orders execute immediately
        # Status depends on whether we can fetch price
    
    def test_create_sell_order_no_position(self, manager):
        """Test selling without position gets rejected."""
        order = manager.create_order(
            ticker="AAPL",
            side=OrderSide.SELL,
            quantity=10,
        )
        
        assert order.status == OrderStatus.REJECTED
        assert "Insufficient shares" in order.reject_reason
    
    def test_invalid_quantity(self, manager):
        """Test invalid quantity raises error."""
        with pytest.raises(ValueError, match="Quantity must be positive"):
            manager.create_order(
                ticker="AAPL",
                side=OrderSide.BUY,
                quantity=-10,
            )
    
    def test_limit_order_requires_price(self, manager):
        """Test limit order requires limit price."""
        with pytest.raises(ValueError, match="Limit price required"):
            manager.create_order(
                ticker="AAPL",
                side=OrderSide.BUY,
                quantity=10,
                order_type=OrderType.LIMIT,
            )
    
    def test_cancel_order(self, manager):
        """Test cancelling a pending order."""
        # Create a limit order (won't execute immediately)
        order = manager.create_order(
            ticker="AAPL",
            side=OrderSide.BUY,
            quantity=10,
            order_type=OrderType.LIMIT,
            limit_price=100.0,
        )
        
        # Only cancel if pending
        if order.status == OrderStatus.PENDING:
            cancelled = manager.cancel_order(order.order_id)
            assert cancelled.status == OrderStatus.CANCELLED
    
    def test_get_orders(self, manager):
        """Test getting orders list."""
        orders = manager.get_orders()
        assert isinstance(orders, list)
    
    def test_get_order_not_found(self, manager):
        """Test getting non-existent order."""
        order = manager.get_order("nonexistent")
        assert order is None


# ========== F7.2 Portfolio History Tests ==========

class TestPortfolioSnapshot:
    """Tests for PortfolioSnapshot class."""
    
    def test_snapshot_creation(self):
        """Test snapshot creation."""
        snapshot = PortfolioSnapshot(
            timestamp="2026-02-03T12:00:00",
            total_value=100000.0,
            cash=50000.0,
            positions_value=50000.0,
            total_pnl=0.0,
            total_pnl_percent=0.0,
        )
        
        assert snapshot.total_value == 100000.0
        assert snapshot.cash == 50000.0
    
    def test_snapshot_serialization(self):
        """Test snapshot to/from dict."""
        snapshot = PortfolioSnapshot(
            timestamp="2026-02-03T12:00:00",
            total_value=105000.0,
            cash=50000.0,
            positions_value=55000.0,
            total_pnl=5000.0,
            total_pnl_percent=5.0,
        )
        
        data = snapshot.to_dict()
        restored = PortfolioSnapshot.from_dict(data)
        
        assert restored.total_value == snapshot.total_value
        assert restored.total_pnl == snapshot.total_pnl


class TestPortfolioHistory:
    """Tests for PortfolioHistory class."""
    
    @pytest.fixture
    def history(self):
        """Create fresh history (in memory only)."""
        h = PortfolioHistory()
        h.snapshots = []  # Clear any loaded data
        return h
    
    def test_record_snapshot(self, history):
        """Test recording a snapshot."""
        portfolio = Portfolio(starting_cash=100000.0)
        history.record_snapshot(portfolio, prices={})
        
        assert len(history.snapshots) == 1
        assert history.snapshots[0].total_value == 100000.0
    
    def test_get_history(self, history):
        """Test getting history."""
        portfolio = Portfolio(starting_cash=100000.0)
        
        # Record a few snapshots
        for _ in range(5):
            history.record_snapshot(portfolio, prices={})
        
        data = history.get_history(days=30)
        assert len(data) == 5
    
    def test_get_performance(self, history):
        """Test performance calculation."""
        # Create snapshots with different values
        history.snapshots = [
            PortfolioSnapshot(
                timestamp="2026-02-01T12:00:00",
                total_value=100000.0,
                cash=100000.0,
                positions_value=0.0,
                total_pnl=0.0,
                total_pnl_percent=0.0,
            ),
            PortfolioSnapshot(
                timestamp="2026-02-03T12:00:00",
                total_value=105000.0,
                cash=50000.0,
                positions_value=55000.0,
                total_pnl=5000.0,
                total_pnl_percent=5.0,
            ),
        ]
        
        perf = history.get_performance(days=30)
        
        assert perf["start_value"] == 100000.0
        assert perf["end_value"] == 105000.0
        assert perf["change"] == 5000.0
        assert perf["change_percent"] == 5.0
    
    def test_history_clear(self, history):
        """Test clearing history."""
        portfolio = Portfolio(starting_cash=100000.0)
        history.record_snapshot(portfolio, prices={})
        
        history.clear()
        assert len(history.snapshots) == 0


# ========== F7.3 Sector Allocation Tests ==========

class TestSectorAllocation:
    """Tests for sector allocation."""
    
    def test_empty_portfolio_allocation(self):
        """Test allocation for empty portfolio."""
        portfolio = Portfolio(starting_cash=100000.0)
        allocation = portfolio.get_sector_allocation(prices={})
        
        assert allocation == []
    
    def test_allocation_calculation(self):
        """Test allocation calculation with positions."""
        portfolio = Portfolio(starting_cash=100000.0)
        
        # Add positions (mock prices)
        portfolio.add_position("AAPL", shares=10, price=150.0)
        portfolio.add_position("MSFT", shares=10, price=350.0)
        
        # Calculate with mock prices
        prices = {"AAPL": 150.0, "MSFT": 350.0}
        allocation = portfolio.get_sector_allocation(prices=prices)
        
        # Should have allocation entries
        assert len(allocation) >= 1
        
        # Total should be ~100%
        total_pct = sum(a["percentage"] for a in allocation)
        assert abs(total_pct - 100.0) < 0.1


# ========== Run Tests ==========

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
