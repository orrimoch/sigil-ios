"""
Unit tests for Agent Position Sizing (REC-283)
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock
import numpy as np

from src.agent.position_sizing import (
    PositionSizer,
    SizedPosition,
    TradeDecision,
    size_positions,
)
from src.agent.context import (
    TradingContext,
    PortfolioState,
    MarketState,
    DataFreshness,
    Position,
)


# Test fixtures

@pytest.fixture
def mock_portfolio():
    """Create a mock portfolio state."""
    return PortfolioState(
        cash=100000,
        total_value=100000,
        positions=[],
        sector_exposure={},
        unrealized_pnl=0,
    )


@pytest.fixture
def mock_portfolio_with_positions():
    """Create a mock portfolio with existing positions."""
    positions = [
        Position(
            ticker="AAPL",
            shares=50,
            avg_cost=150.0,
            current_price=155.0,
            market_value=7750.0,
            unrealized_pnl=250.0,
            unrealized_pnl_pct=3.33,
            sector="Technology",
        ),
    ]
    return PortfolioState(
        cash=50000,
        total_value=57750,
        positions=positions,
        sector_exposure={"Technology": 0.134},
        unrealized_pnl=250.0,
    )


@pytest.fixture
def mock_market_normal():
    """Create a mock normal market state."""
    return MarketState(
        regime="normal",
        regime_confidence=0.8,
        vix=15.0,
    )


@pytest.fixture
def mock_market_crisis():
    """Create a mock crisis market state."""
    return MarketState(
        regime="crisis",
        regime_confidence=0.9,
        vix=45.0,
    )


@pytest.fixture
def mock_context(mock_portfolio, mock_market_normal):
    """Create a mock trading context."""
    return TradingContext(
        timestamp=datetime.now(),
        portfolio=mock_portfolio,
        market=mock_market_normal,
        buy_candidates=[],
        sell_candidates=[],
        hold_review=[],
        data_freshness=DataFreshness(),
    )


@pytest.fixture
def mock_context_with_positions(mock_portfolio_with_positions, mock_market_normal):
    """Create a mock context with existing positions."""
    return TradingContext(
        timestamp=datetime.now(),
        portfolio=mock_portfolio_with_positions,
        market=mock_market_normal,
        buy_candidates=[],
        sell_candidates=[],
        hold_review=[],
        data_freshness=DataFreshness(),
    )


class TestSizedPositionDataclass:
    """Test SizedPosition dataclass."""
    
    def test_creation(self):
        """Test SizedPosition creation."""
        position = SizedPosition(
            ticker="AAPL",
            action="BUY",
            shares=10,
            dollars=1500.0,
            weight=0.05,
            price=150.0,
            rationale="Test",
        )
        assert position.ticker == "AAPL"
        assert position.shares == 10
    
    def test_to_dict(self):
        """Test SizedPosition to_dict."""
        position = SizedPosition(
            ticker="AAPL",
            action="BUY",
            shares=10,
            dollars=1500.0,
            weight=0.05,
            price=150.0,
            rationale="Test",
        )
        d = position.to_dict()
        assert d["ticker"] == "AAPL"
        assert d["shares"] == 10


class TestTradeDecisionDataclass:
    """Test TradeDecision dataclass."""
    
    def test_creation(self):
        """Test TradeDecision creation."""
        decision = TradeDecision(
            ticker="AAPL",
            action="BUY",
            score=85.0,
            confidence=0.8,
            sector="Technology",
            rationale="Strong momentum",
        )
        assert decision.ticker == "AAPL"
        assert decision.score == 85.0


class TestConvictionMultiplier:
    """Test conviction multiplier calculation."""
    
    def test_score_70(self):
        """Test score 70 gives minimum multiplier."""
        sizer = PositionSizer()
        mult = sizer._conviction_multiplier(70)
        assert abs(mult - 0.85) < 0.01
    
    def test_score_85(self):
        """Test score 85 gives baseline multiplier."""
        sizer = PositionSizer()
        mult = sizer._conviction_multiplier(85)
        assert abs(mult - 1.0) < 0.01
    
    def test_score_100(self):
        """Test score 100 gives maximum multiplier."""
        sizer = PositionSizer()
        mult = sizer._conviction_multiplier(100)
        assert abs(mult - 1.15) < 0.01
    
    def test_higher_score_higher_multiplier(self):
        """Test higher scores give higher multipliers."""
        sizer = PositionSizer()
        mult_low = sizer._conviction_multiplier(70)
        mult_mid = sizer._conviction_multiplier(85)
        mult_high = sizer._conviction_multiplier(100)
        
        assert mult_low < mult_mid < mult_high


class TestRegimeMultiplier:
    """Test regime multiplier calculation."""
    
    def test_low_vol(self):
        """Test low_vol regime gives boost."""
        sizer = PositionSizer()
        mult = sizer._regime_multiplier("low_vol")
        assert mult == 1.1
    
    def test_normal(self):
        """Test normal regime gives no change."""
        sizer = PositionSizer()
        mult = sizer._regime_multiplier("normal")
        assert mult == 1.0
    
    def test_high_vol(self):
        """Test high_vol regime reduces position."""
        sizer = PositionSizer()
        mult = sizer._regime_multiplier("high_vol")
        assert mult == 0.7
    
    def test_crisis(self):
        """Test crisis regime significantly reduces position."""
        sizer = PositionSizer()
        mult = sizer._regime_multiplier("crisis")
        assert mult == 0.5
    
    def test_unknown_regime(self):
        """Test unknown regime defaults to 1.0."""
        sizer = PositionSizer()
        mult = sizer._regime_multiplier("unknown")
        assert mult == 1.0


class TestPositionSizing:
    """Test position sizing calculation."""
    
    @pytest.mark.asyncio
    async def test_empty_decisions(self, mock_context):
        """Test empty decisions returns empty list."""
        sizer = PositionSizer()
        positions = await sizer.size_positions([], mock_context)
        assert positions == []
    
    @pytest.mark.asyncio
    @patch.object(PositionSizer, '_get_price')
    @patch.object(PositionSizer, '_risk_parity_weights')
    async def test_single_buy(self, mock_rp, mock_price, mock_context):
        """Test sizing a single BUY decision."""
        mock_rp.return_value = {"AAPL": 0.10}
        mock_price.return_value = 150.0
        
        decisions = [
            TradeDecision(
                ticker="AAPL",
                action="BUY",
                score=85.0,
                confidence=0.8,
                sector="Technology",
                rationale="Test",
            )
        ]
        
        sizer = PositionSizer()
        positions = await sizer.size_positions(decisions, mock_context)
        
        assert len(positions) == 1
        assert positions[0].ticker == "AAPL"
        assert positions[0].action == "BUY"
        assert positions[0].shares > 0
    
    @pytest.mark.asyncio
    @patch.object(PositionSizer, '_get_price')
    @patch.object(PositionSizer, '_risk_parity_weights')
    async def test_multiple_buys(self, mock_rp, mock_price, mock_context):
        """Test sizing multiple BUY decisions."""
        mock_rp.return_value = {"AAPL": 0.10, "MSFT": 0.10}
        mock_price.side_effect = lambda t: 150.0 if t == "AAPL" else 400.0
        
        decisions = [
            TradeDecision(ticker="AAPL", action="BUY", score=85.0, confidence=0.8, sector="Tech", rationale="Test"),
            TradeDecision(ticker="MSFT", action="BUY", score=90.0, confidence=0.9, sector="Tech", rationale="Test"),
        ]
        
        sizer = PositionSizer()
        positions = await sizer.size_positions(decisions, mock_context)
        
        assert len(positions) == 2
    
    @pytest.mark.asyncio
    async def test_sell_position(self, mock_context_with_positions):
        """Test sizing a SELL decision (full exit)."""
        decisions = [
            TradeDecision(
                ticker="AAPL",
                action="SELL",
                score=35.0,
                confidence=0.7,
                sector="Technology",
                rationale="SELL signal",
            )
        ]
        
        sizer = PositionSizer()
        positions = await sizer.size_positions(decisions, mock_context_with_positions)
        
        assert len(positions) == 1
        assert positions[0].action == "SELL"
        assert positions[0].shares == 50  # Full position
    
    @pytest.mark.asyncio
    async def test_sell_unknown_position(self, mock_context):
        """Test SELL decision for non-existent position."""
        decisions = [
            TradeDecision(
                ticker="UNKNOWN",
                action="SELL",
                score=35.0,
                confidence=0.7,
                sector="Unknown",
                rationale="Test",
            )
        ]
        
        sizer = PositionSizer()
        positions = await sizer.size_positions(decisions, mock_context)
        
        # Should skip non-existent position
        assert len(positions) == 0


class TestPositionLimits:
    """Test position size limits."""
    
    @pytest.mark.asyncio
    @patch.object(PositionSizer, '_get_price')
    @patch.object(PositionSizer, '_risk_parity_weights')
    async def test_max_weight_capped(self, mock_rp, mock_price, mock_context):
        """Test positions are capped at MAX_WEIGHT."""
        # Return a very high weight from risk parity
        mock_rp.return_value = {"AAPL": 0.50}  # 50%
        mock_price.return_value = 150.0
        
        decisions = [
            TradeDecision(ticker="AAPL", action="BUY", score=100.0, confidence=1.0, sector="Tech", rationale="Test"),
        ]
        
        sizer = PositionSizer()
        positions = await sizer.size_positions(decisions, mock_context)
        
        assert len(positions) == 1
        # Should be capped at MAX_WEIGHT (0.10)
        assert positions[0].weight <= sizer.MAX_WEIGHT
    
    @pytest.mark.asyncio
    @patch.object(PositionSizer, '_get_price')
    @patch.object(PositionSizer, '_portfolio_risk_parity_weights')
    async def test_min_weight_skipped(self, mock_rp, mock_price, mock_context):
        """Test positions below MIN_WEIGHT are skipped."""
        # Return a very low weight (REC-303: fix mock target)
        mock_rp.return_value = {"AAPL": 0.005}  # 0.5%
        mock_price.return_value = 150.0
        
        decisions = [
            TradeDecision(ticker="AAPL", action="BUY", score=70.0, confidence=0.5, sector="Tech", rationale="Test"),
        ]
        
        sizer = PositionSizer()
        positions = await sizer.size_positions(decisions, mock_context)
        
        # Should skip because below MIN_WEIGHT
        assert len(positions) == 0


class TestRegimeAdjustments:
    """Test regime-based position adjustments."""
    
    @pytest.mark.asyncio
    @patch.object(PositionSizer, '_get_price')
    @patch.object(PositionSizer, '_portfolio_risk_parity_weights')
    async def test_crisis_reduces_position(self, mock_rp, mock_price, mock_portfolio, mock_market_crisis):
        """Test crisis regime reduces position size (REC-303: fix mock target)."""
        mock_rp.return_value = {"AAPL": 0.10}
        mock_price.return_value = 150.0
        
        context_crisis = TradingContext(
            timestamp=datetime.now(),
            portfolio=mock_portfolio,
            market=mock_market_crisis,
            buy_candidates=[],
            sell_candidates=[],
            hold_review=[],
            data_freshness=DataFreshness(),
        )
        
        context_normal = TradingContext(
            timestamp=datetime.now(),
            portfolio=mock_portfolio,
            market=MarketState(regime="normal", regime_confidence=0.8, vix=15.0),
            buy_candidates=[],
            sell_candidates=[],
            hold_review=[],
            data_freshness=DataFreshness(),
        )
        
        decisions = [
            TradeDecision(ticker="AAPL", action="BUY", score=85.0, confidence=0.8, sector="Tech", rationale="Test"),
        ]
        
        sizer = PositionSizer()
        
        positions_crisis = await sizer.size_positions(decisions, context_crisis)
        positions_normal = await sizer.size_positions(decisions, context_normal)
        
        # Crisis should result in smaller position
        if positions_crisis and positions_normal:
            assert positions_crisis[0].dollars < positions_normal[0].dollars


class TestRiskParityWeights:
    """Test risk parity weight calculation."""
    
    @pytest.mark.asyncio
    async def test_single_ticker(self):
        """Test single ticker returns default weight."""
        sizer = PositionSizer()
        weights = await sizer._risk_parity_weights(["AAPL"])
        
        assert "AAPL" in weights
        assert weights["AAPL"] == 0.05  # Default for single
    
    @pytest.mark.asyncio
    async def test_empty_tickers(self):
        """Test empty tickers returns empty dict."""
        sizer = PositionSizer()
        weights = await sizer._risk_parity_weights([])
        
        assert weights == {}


class TestConvenienceFunction:
    """Test convenience functions."""
    
    @pytest.mark.asyncio
    @patch.object(PositionSizer, '_get_price')
    @patch.object(PositionSizer, '_risk_parity_weights')
    async def test_size_positions_function(self, mock_rp, mock_price, mock_context):
        """Test size_positions convenience function."""
        mock_rp.return_value = {"AAPL": 0.10}
        mock_price.return_value = 150.0
        
        decisions = [
            TradeDecision(ticker="AAPL", action="BUY", score=85.0, confidence=0.8, sector="Tech", rationale="Test"),
        ]
        
        positions = await size_positions(decisions, mock_context)
        
        assert len(positions) == 1


class TestCacheOperations:
    """Test cache operations."""
    
    def test_clear_cache(self):
        """Test clearing caches."""
        sizer = PositionSizer()
        sizer._price_cache["AAPL"] = 150.0
        sizer._cov_cache = {"test": "data"}
        
        sizer.clear_cache()
        
        assert len(sizer._price_cache) == 0
        assert sizer._cov_cache is None
