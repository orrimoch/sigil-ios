"""
Unit tests for Risk Validator (REC-286)
"""

import pytest
import pytest_asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch, MagicMock

from src.agent.risk_validator import (
    RiskValidator,
    RiskValidation,
    validate_trades,
)
from src.agent.position_sizing import SizedPosition
from src.agent.context import (
    TradingContext,
    PortfolioState,
    MarketState,
    Position,
    DataFreshness,
)


# Test fixtures

@pytest.fixture
def mock_context():
    """Create a mock trading context."""
    return TradingContext(
        timestamp=datetime.now(timezone.utc),
        portfolio=PortfolioState(
            cash=50000,
            total_value=100000,
            positions=[],
            sector_exposure={"Technology": 0.25},
            unrealized_pnl=1000,
            realized_pnl_today=0,
        ),
        market=MarketState(
            regime="normal",
            regime_confidence=0.8,
            vix=15.0,
        ),
        buy_candidates=[],
        sell_candidates=[],
        hold_review=[],
        data_freshness=DataFreshness(),
    )


@pytest.fixture
def mock_context_with_loss():
    """Create context with daily loss."""
    return TradingContext(
        timestamp=datetime.now(timezone.utc),
        portfolio=PortfolioState(
            cash=45000,
            total_value=95000,
            positions=[],
            sector_exposure={},
            unrealized_pnl=-5000,
            realized_pnl_today=-4000,  # 4% loss on $100k
        ),
        market=MarketState(regime="normal", regime_confidence=0.8, vix=20.0),
        buy_candidates=[],
        sell_candidates=[],
        hold_review=[],
        data_freshness=DataFreshness(),
    )


@pytest.fixture
def mock_context_high_sector():
    """Create context with high sector exposure."""
    return TradingContext(
        timestamp=datetime.now(timezone.utc),
        portfolio=PortfolioState(
            cash=30000,
            total_value=100000,
            positions=[],
            sector_exposure={"Technology": 0.28},  # Already 28%
            unrealized_pnl=0,
        ),
        market=MarketState(regime="normal", regime_confidence=0.8, vix=15.0),
        buy_candidates=[],
        sell_candidates=[],
        hold_review=[],
        data_freshness=DataFreshness(),
    )


@pytest.fixture
def small_trade():
    """Create a small valid trade."""
    return SizedPosition(
        ticker="AAPL",
        action="BUY",
        shares=10,
        dollars=1500,  # 1.5% of $100k
        weight=0.015,
        price=150.0,
        rationale="Test trade",
    )


@pytest.fixture
def large_trade():
    """Create a large trade that exceeds limits."""
    return SizedPosition(
        ticker="AAPL",
        action="BUY",
        shares=100,
        dollars=15000,  # 15% of $100k - exceeds 10% limit
        weight=0.15,
        price=150.0,
        rationale="Large trade",
    )


@pytest.fixture
def sell_trade():
    """Create a sell trade."""
    return SizedPosition(
        ticker="AAPL",
        action="SELL",
        shares=50,
        dollars=7500,
        weight=0.075,
        price=150.0,
        rationale="Exit position",
    )


class TestRiskValidation:
    """Test RiskValidation dataclass."""
    
    def test_was_reduced(self):
        """Test was_reduced property."""
        validation = RiskValidation(
            passed=True,
            original_shares=100,
            adjusted_shares=80,
            original_dollars=10000,
            adjusted_dollars=8000,
        )
        assert validation.was_reduced is True
    
    def test_was_not_reduced(self):
        """Test was_reduced when not reduced."""
        validation = RiskValidation(
            passed=True,
            original_shares=100,
            adjusted_shares=100,
            original_dollars=10000,
            adjusted_dollars=10000,
        )
        assert validation.was_reduced is False
    
    def test_was_blocked(self):
        """Test was_blocked property."""
        validation = RiskValidation(
            passed=False,
            original_shares=100,
            adjusted_shares=0,
            original_dollars=10000,
            adjusted_dollars=0,
            violations=["Daily loss limit exceeded"],
        )
        assert validation.was_blocked is True


class TestRiskValidatorInit:
    """Test RiskValidator initialization."""
    
    def test_default_limits(self):
        """Test default risk limits."""
        validator = RiskValidator()
        assert validator.max_position_pct == 0.10
        assert validator.max_sector_pct == 0.30
        assert validator.max_var == 0.02
        assert validator.max_correlation == 0.80
        assert validator.daily_loss_limit == -0.03
    
    def test_custom_limits(self):
        """Test custom risk limits."""
        validator = RiskValidator(
            max_position_pct=0.05,
            max_sector_pct=0.25,
        )
        assert validator.max_position_pct == 0.05
        assert validator.max_sector_pct == 0.25


class TestPositionLimit:
    """Test position limit validation."""
    
    @pytest.mark.asyncio
    async def test_valid_position(self, small_trade, mock_context):
        """Test trade within position limit passes."""
        validator = RiskValidator()
        result = await validator.validate(small_trade, mock_context)
        
        assert result.passed is True
        assert len(result.violations) == 0
        assert result.adjusted_shares == small_trade.shares
    
    @pytest.mark.asyncio
    async def test_exceeds_position_limit(self, large_trade, mock_context):
        """Test trade exceeding position limit is reduced."""
        validator = RiskValidator()
        result = await validator.validate(large_trade, mock_context)
        
        # Should be reduced to 10% max
        assert result.adjusted_shares < large_trade.shares
        assert any("Position exceeds" in v for v in result.violations)
    
    @pytest.mark.asyncio
    async def test_custom_position_limit(self, small_trade, mock_context):
        """Test custom position limit."""
        # Small trade is 1.5%, set limit to 1%
        validator = RiskValidator(max_position_pct=0.01)
        result = await validator.validate(small_trade, mock_context)
        
        assert result.adjusted_shares < small_trade.shares


class TestSectorLimit:
    """Test sector limit validation."""
    
    @pytest.mark.asyncio
    @patch.object(RiskValidator, '_get_sector')
    async def test_exceeds_sector_limit(self, mock_sector, mock_context_high_sector):
        """Test trade that would exceed sector limit."""
        mock_sector.return_value = "Technology"
        
        # Trade that would push Tech from 28% to 33%
        trade = SizedPosition(
            ticker="NVDA",
            action="BUY",
            shares=50,
            dollars=5000,  # 5% - would make Tech 33%
            weight=0.05,
            price=100.0,
            rationale="Tech trade",
        )
        
        validator = RiskValidator()
        result = await validator.validate(trade, mock_context_high_sector)
        
        # Should be reduced or violated
        assert any("Sector" in v for v in result.violations) or result.adjusted_shares < 50


class TestDailyLossLimit:
    """Test daily loss limit validation."""
    
    @pytest.mark.asyncio
    async def test_blocks_when_loss_exceeded(self, small_trade, mock_context_with_loss):
        """Test trading is blocked when daily loss limit exceeded."""
        validator = RiskValidator()
        result = await validator.validate(small_trade, mock_context_with_loss)
        
        assert result.passed is False
        assert result.adjusted_shares == 0
        assert any("Daily loss" in v for v in result.violations)
    
    @pytest.mark.asyncio
    async def test_allows_when_within_loss_limit(self, small_trade, mock_context):
        """Test trading allowed when within loss limit."""
        validator = RiskValidator()
        result = await validator.validate(small_trade, mock_context)
        
        # Should pass (no daily loss)
        assert not any("Daily loss" in v for v in result.violations)


class TestSellTrades:
    """Test SELL trade validation."""
    
    @pytest.mark.asyncio
    async def test_sell_always_passes(self, sell_trade, mock_context):
        """Test SELL trades bypass risk checks."""
        validator = RiskValidator()
        result = await validator.validate(sell_trade, mock_context)
        
        assert result.passed is True
        assert result.adjusted_shares == sell_trade.shares
    
    @pytest.mark.asyncio
    async def test_sell_passes_even_with_loss(self, sell_trade, mock_context_with_loss):
        """Test SELL trades pass even with daily loss limit."""
        validator = RiskValidator()
        result = await validator.validate(sell_trade, mock_context_with_loss)
        
        # SELL should still pass - we want to allow exits
        assert result.passed is True


class TestCorrelation:
    """Test correlation validation."""
    
    @pytest.mark.asyncio
    @patch.object(RiskValidator, '_get_correlation')
    async def test_high_correlation_reduces(self, mock_corr, mock_context):
        """Test high correlation reduces position."""
        mock_corr.return_value = 0.90  # 90% correlated
        
        # Add existing position
        mock_context.portfolio.positions = [
            Position(
                ticker="MSFT", shares=50, avg_cost=400,
                current_price=410, market_value=20500,
                unrealized_pnl=500, unrealized_pnl_pct=2.5, sector="Technology"
            )
        ]
        
        trade = SizedPosition(
            ticker="AAPL", action="BUY", shares=100, dollars=10000,
            weight=0.10, price=100.0, rationale="Test"
        )
        
        validator = RiskValidator()
        result = await validator.validate(trade, mock_context)
        
        assert any("correlation" in w.lower() for w in result.warnings)
        assert result.adjusted_shares < 100


class TestBatchValidation:
    """Test batch validation."""
    
    @pytest.mark.asyncio
    async def test_validate_batch(self, small_trade, large_trade, mock_context):
        """Test validating multiple trades."""
        trades = [small_trade, large_trade]
        
        validator = RiskValidator()
        results = await validator.validate_batch(trades, mock_context)
        
        assert len(results) == 2
        assert all(isinstance(r[1], RiskValidation) for r in results)


class TestConvenienceFunction:
    """Test convenience functions."""
    
    @pytest.mark.asyncio
    async def test_validate_trades(self, small_trade, mock_context):
        """Test validate_trades convenience function."""
        results = await validate_trades([small_trade], mock_context)
        
        assert len(results) == 1
        assert isinstance(results[0][1], RiskValidation)


class TestEdgeCases:
    """Test edge cases."""
    
    @pytest.mark.asyncio
    async def test_zero_portfolio_value(self, small_trade):
        """Test handling of zero portfolio value."""
        context = TradingContext(
            timestamp=datetime.now(timezone.utc),
            portfolio=PortfolioState(
                cash=0, total_value=0, positions=[],
                sector_exposure={}, unrealized_pnl=0
            ),
            market=MarketState(regime="normal", regime_confidence=0.8, vix=15.0),
            buy_candidates=[],
            sell_candidates=[],
            hold_review=[],
            data_freshness=DataFreshness(),
        )
        
        validator = RiskValidator()
        result = await validator.validate(small_trade, context)
        
        # Should handle gracefully
        assert result.passed is False or result.adjusted_shares == 0
    
    @pytest.mark.asyncio
    async def test_zero_price_trade(self, mock_context):
        """Test handling of zero price trade."""
        trade = SizedPosition(
            ticker="TEST", action="BUY", shares=100, dollars=0,
            weight=0, price=0, rationale="Invalid trade"
        )
        
        validator = RiskValidator()
        result = await validator.validate(trade, mock_context)
        
        # Should handle gracefully
        assert isinstance(result, RiskValidation)
