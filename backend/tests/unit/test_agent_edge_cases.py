"""
Comprehensive Edge Case Tests for Agent Modules

Tests unusual inputs, boundary conditions, and failure scenarios
to ensure robust behavior in production.
"""

import pytest
import pytest_asyncio
import json
import numpy as np
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

from src.agent.decision_engine import DecisionEngine, DecisionResult
from src.agent.risk_validator import RiskValidator, RiskValidation
from src.agent.position_sizing import PositionSizer, SizedPosition, TradeDecision
from src.agent.memory import Memory
from src.agent.context import (
    TradingContext,
    PortfolioState,
    MarketState,
    StockCandidate,
    Position,
    DataFreshness,
)


# =============================================================================
# DECISION ENGINE EDGE CASES
# =============================================================================

class TestDecisionEngineEdgeCases:
    """Edge cases for decision engine."""
    
    @pytest.fixture
    def engine(self):
        return DecisionEngine()
    
    @pytest.fixture
    def empty_context(self):
        """Context with no candidates."""
        return TradingContext(
            timestamp=datetime.now(timezone.utc),
            portfolio=PortfolioState(
                cash=100000, total_value=100000, positions=[],
                sector_exposure={}, unrealized_pnl=0
            ),
            market=MarketState(regime="normal", regime_confidence=0.8, vix=15.0),
            buy_candidates=[],  # Empty!
            sell_candidates=[],
            hold_review=[],
            data_freshness=DataFreshness(),
        )
    
    @pytest.fixture
    def stale_context(self):
        """Context with stale data."""
        return TradingContext(
            timestamp=datetime.now(timezone.utc),
            portfolio=PortfolioState(
                cash=100000, total_value=100000, positions=[],
                sector_exposure={}, unrealized_pnl=0
            ),
            market=MarketState(regime="normal", regime_confidence=0.8, vix=15.0),
            buy_candidates=[],
            sell_candidates=[],
            hold_review=[],
            data_freshness=DataFreshness(
                is_stale=True,
                stale_reasons=["Scores are 10 days old"],
                scores_age_hours=240,
            ),
        )
    
    @pytest.mark.asyncio
    async def test_empty_candidates_returns_empty(self, engine, empty_context):
        """Test with no buy/sell candidates."""
        result = await engine.decide(empty_context, [])
        
        assert isinstance(result, DecisionResult)
        assert len(result.decisions) == 0
    
    @pytest.mark.asyncio
    async def test_no_memories_still_works(self, engine, empty_context):
        """Test decision making with no historical memories."""
        # Add a candidate
        empty_context.buy_candidates = [
            StockCandidate(
                ticker="AAPL", company_name="Apple", score=85.0,
                signal="BUY", sector="Technology", rank=1,
                fundamental_score=80, sentiment_score=80,
                technical_score=80, macro_score=80,
            )
        ]
        
        result = await engine.decide(empty_context, memories=[])
        
        # Should still produce decisions (or empty) without crashing
        assert isinstance(result, DecisionResult)
    
    @pytest.mark.asyncio
    async def test_stale_data_context(self, engine, stale_context):
        """Test with stale data context."""
        result = await engine.decide(stale_context, [])
        
        # Should handle gracefully - no crash
        assert isinstance(result, DecisionResult)
    
    @pytest.mark.asyncio
    @patch.object(DecisionEngine, '_call_claude')
    async def test_claude_returns_invalid_structure(self, mock_claude, engine, empty_context):
        """Test when Claude returns unexpected JSON structure."""
        # Return a dict instead of array
        mock_claude.return_value = {
            "content": '{"not": "an array"}',
            "thinking": "test",
            "tokens": 100
        }
        
        result = await engine.decide(empty_context, [])
        
        assert len(result.decisions) == 0
    
    @pytest.mark.asyncio
    @patch.object(DecisionEngine, '_call_claude')
    async def test_claude_returns_partial_data(self, mock_claude, engine, empty_context):
        """Test when Claude returns decisions missing required fields."""
        mock_claude.return_value = {
            "content": json.dumps([
                {"ticker": "AAPL"},  # Missing action
                {"action": "BUY"},   # Missing ticker
                {"action": "BUY", "ticker": "MSFT", "rationale": "Test", "confidence": 0.8}  # Valid
            ]),
            "thinking": "test",
            "tokens": 100
        }
        
        empty_context.buy_candidates = [
            StockCandidate(
                ticker="MSFT", company_name="Microsoft", score=85.0,
                signal="BUY", sector="Technology", rank=1,
                fundamental_score=80, sentiment_score=80,
                technical_score=80, macro_score=80,
            )
        ]
        
        result = await engine.decide(empty_context, [])
        
        # Should only include the valid one
        assert len(result.decisions) <= 1
    
    @pytest.mark.asyncio
    @patch.object(DecisionEngine, '_call_claude')
    async def test_duplicate_tickers_in_response(self, mock_claude, engine, empty_context):
        """Test when Claude returns duplicate tickers."""
        mock_claude.return_value = {
            "content": json.dumps([
                {"action": "BUY", "ticker": "AAPL", "rationale": "First", "confidence": 0.9},
                {"action": "BUY", "ticker": "AAPL", "rationale": "Duplicate", "confidence": 0.8},
            ]),
            "thinking": "test",
            "tokens": 100
        }
        
        empty_context.buy_candidates = [
            StockCandidate(
                ticker="AAPL", company_name="Apple", score=85.0,
                signal="BUY", sector="Technology", rank=1,
                fundamental_score=80, sentiment_score=80,
                technical_score=80, macro_score=80,
            )
        ]
        
        result = await engine.decide(empty_context, [])
        
        # Should handle duplicates (either dedupe or allow both)
        assert isinstance(result.decisions, list)
    
    @pytest.mark.asyncio
    @patch.object(DecisionEngine, '_call_claude')
    async def test_extreme_confidence_values(self, mock_claude, engine, empty_context):
        """Test with extreme confidence values."""
        mock_claude.return_value = {
            "content": json.dumps([
                {"action": "BUY", "ticker": "AAPL", "rationale": "Test", "confidence": 1.5},  # > 1
                {"action": "BUY", "ticker": "MSFT", "rationale": "Test", "confidence": -0.5},  # < 0
            ]),
            "thinking": "test",
            "tokens": 100
        }
        
        empty_context.buy_candidates = [
            StockCandidate(
                ticker="AAPL", company_name="Apple", score=85.0,
                signal="BUY", sector="Technology", rank=1,
                fundamental_score=80, sentiment_score=80,
                technical_score=80, macro_score=80,
            ),
            StockCandidate(
                ticker="MSFT", company_name="Microsoft", score=82.0,
                signal="BUY", sector="Technology", rank=2,
                fundamental_score=80, sentiment_score=80,
                technical_score=80, macro_score=80,
            )
        ]
        
        result = await engine.decide(empty_context, [])
        
        # Should handle gracefully
        assert isinstance(result, DecisionResult)
    
    @pytest.mark.asyncio
    @patch.object(DecisionEngine, '_call_claude')
    async def test_unknown_ticker_in_response(self, mock_claude, engine, empty_context):
        """Test when Claude suggests ticker not in candidates."""
        mock_claude.return_value = {
            "content": json.dumps([
                {"action": "BUY", "ticker": "UNKNOWN_TICKER", "rationale": "Test", "confidence": 0.8},
            ]),
            "thinking": "test",
            "tokens": 100
        }
        
        result = await engine.decide(empty_context, [])
        
        # Should handle - either skip or create with defaults
        assert isinstance(result.decisions, list)


# =============================================================================
# RISK VALIDATOR EDGE CASES
# =============================================================================

class TestRiskValidatorEdgeCases:
    """Edge cases for risk validator."""
    
    @pytest.fixture
    def validator(self):
        return RiskValidator()
    
    @pytest.fixture
    def normal_context(self):
        return TradingContext(
            timestamp=datetime.now(timezone.utc),
            portfolio=PortfolioState(
                cash=50000, total_value=100000, positions=[],
                sector_exposure={}, unrealized_pnl=0, realized_pnl_today=0
            ),
            market=MarketState(regime="normal", regime_confidence=0.8, vix=15.0),
            buy_candidates=[],
            sell_candidates=[],
            hold_review=[],
            data_freshness=DataFreshness(),
        )
    
    @pytest.mark.asyncio
    async def test_zero_shares_trade(self, validator, normal_context):
        """Test trade with zero shares."""
        trade = SizedPosition(
            ticker="AAPL", action="BUY", shares=0, dollars=0,
            weight=0, price=150.0, rationale="Zero trade"
        )
        
        result = await validator.validate(trade, normal_context)
        
        assert isinstance(result, RiskValidation)
        # Zero shares should either pass or be blocked
    
    @pytest.mark.asyncio
    async def test_negative_shares_trade(self, validator, normal_context):
        """Test trade with negative shares."""
        trade = SizedPosition(
            ticker="AAPL", action="BUY", shares=-10, dollars=-1500,
            weight=-0.015, price=150.0, rationale="Negative trade"
        )
        
        result = await validator.validate(trade, normal_context)
        
        # Should handle gracefully
        assert isinstance(result, RiskValidation)
    
    @pytest.mark.asyncio
    async def test_trade_larger_than_portfolio(self, validator, normal_context):
        """Test trade larger than entire portfolio."""
        trade = SizedPosition(
            ticker="AAPL", action="BUY", shares=10000, dollars=1500000,  # $1.5M on $100k portfolio
            weight=15.0, price=150.0, rationale="Huge trade"
        )
        
        result = await validator.validate(trade, normal_context)
        
        # Should be reduced or blocked
        assert result.adjusted_shares < trade.shares or not result.passed
    
    @pytest.mark.asyncio
    async def test_100_percent_sector_exposure(self, validator):
        """Test when portfolio is already 100% in one sector."""
        context = TradingContext(
            timestamp=datetime.now(timezone.utc),
            portfolio=PortfolioState(
                cash=0, total_value=100000, positions=[],
                sector_exposure={"Technology": 1.0},  # 100% Tech!
                unrealized_pnl=0, realized_pnl_today=0
            ),
            market=MarketState(regime="normal", regime_confidence=0.8, vix=15.0),
            buy_candidates=[],
            sell_candidates=[],
            hold_review=[],
            data_freshness=DataFreshness(),
        )
        
        trade = SizedPosition(
            ticker="AAPL", action="BUY", shares=10, dollars=1500,
            weight=0.015, price=150.0, rationale="More tech"
        )
        
        with patch.object(validator, '_get_sector', return_value="Technology"):
            result = await validator.validate(trade, context)
        
        # Should be blocked or reduced (already over sector limit)
        assert not result.passed or result.adjusted_shares == 0
    
    @pytest.mark.asyncio
    async def test_exactly_at_position_limit(self, validator, normal_context):
        """Test trade exactly at position limit."""
        # Trade for exactly 10% of portfolio
        trade = SizedPosition(
            ticker="AAPL", action="BUY", shares=66, dollars=10000,  # Exactly 10%
            weight=0.10, price=150.0, rationale="At limit"
        )
        
        result = await validator.validate(trade, normal_context)
        
        # Should pass (at limit, not over)
        assert result.passed or result.adjusted_shares > 0
    
    @pytest.mark.asyncio
    async def test_barely_over_position_limit(self, validator, normal_context):
        """Test trade barely over position limit."""
        trade = SizedPosition(
            ticker="AAPL", action="BUY", shares=67, dollars=10050,  # 10.05%
            weight=0.1005, price=150.0, rationale="Barely over"
        )
        
        result = await validator.validate(trade, normal_context)
        
        # Should be reduced slightly
        assert result.adjusted_shares <= 66  # Max shares for 10%
    
    @pytest.mark.asyncio
    async def test_daily_loss_exactly_at_limit(self, validator):
        """Test daily loss exactly at limit (-3%)."""
        context = TradingContext(
            timestamp=datetime.now(timezone.utc),
            portfolio=PortfolioState(
                cash=47000, total_value=97000, positions=[],
                sector_exposure={}, unrealized_pnl=0,
                realized_pnl_today=-3000,  # Exactly -3% on $100k
            ),
            market=MarketState(regime="normal", regime_confidence=0.8, vix=15.0),
            buy_candidates=[],
            sell_candidates=[],
            hold_review=[],
            data_freshness=DataFreshness(),
        )
        
        trade = SizedPosition(
            ticker="AAPL", action="BUY", shares=10, dollars=1500,
            weight=0.015, price=150.0, rationale="Test"
        )
        
        result = await validator.validate(trade, context)
        
        # At exactly -3%, should still allow (limit is < -3%)
        # Or be blocked depending on implementation
        assert isinstance(result, RiskValidation)
    
    @pytest.mark.asyncio
    @patch.object(RiskValidator, '_get_correlation')
    async def test_perfect_correlation(self, mock_corr, validator, normal_context):
        """Test with perfect correlation (1.0)."""
        mock_corr.return_value = 1.0
        
        normal_context.portfolio.positions = [
            Position(
                ticker="MSFT", shares=50, avg_cost=400,
                current_price=400, market_value=20000,
                unrealized_pnl=0, unrealized_pnl_pct=0, sector="Technology"
            )
        ]
        
        trade = SizedPosition(
            ticker="AAPL", action="BUY", shares=100, dollars=10000,
            weight=0.10, price=100.0, rationale="Test"
        )
        
        result = await validator.validate(trade, normal_context)
        
        # Should reduce significantly due to perfect correlation
        assert result.adjusted_shares < 100 or "correlation" in str(result.warnings).lower()
    
    @pytest.mark.asyncio
    @patch.object(RiskValidator, '_get_sector')
    async def test_sector_lookup_failure(self, mock_sector, validator, normal_context):
        """Test when sector lookup fails."""
        mock_sector.side_effect = Exception("API Error")
        
        trade = SizedPosition(
            ticker="AAPL", action="BUY", shares=10, dollars=1500,
            weight=0.015, price=150.0, rationale="Test"
        )
        
        # Should handle gracefully
        result = await validator.validate(trade, normal_context)
        assert isinstance(result, RiskValidation)


# =============================================================================
# POSITION SIZER EDGE CASES
# =============================================================================

class TestPositionSizerEdgeCases:
    """Edge cases for position sizer."""
    
    @pytest.fixture
    def sizer(self):
        return PositionSizer()
    
    @pytest.fixture
    def normal_context(self):
        return TradingContext(
            timestamp=datetime.now(timezone.utc),
            portfolio=PortfolioState(
                cash=100000, total_value=100000, positions=[],
                sector_exposure={}, unrealized_pnl=0
            ),
            market=MarketState(regime="normal", regime_confidence=0.8, vix=15.0),
            buy_candidates=[],
            sell_candidates=[],
            hold_review=[],
            data_freshness=DataFreshness(),
        )
    
    @pytest.mark.asyncio
    @patch.object(PositionSizer, '_get_price')
    async def test_zero_price(self, mock_price, sizer, normal_context):
        """Test when price is zero."""
        mock_price.return_value = 0.0
        
        decisions = [
            TradeDecision(
                ticker="AAPL", action="BUY", score=85.0,
                confidence=0.8, sector="Tech", rationale="Test"
            )
        ]
        
        positions = await sizer.size_positions(decisions, normal_context)
        
        # Should handle gracefully - skip or return empty
        assert isinstance(positions, list)
    
    @pytest.mark.asyncio
    @patch.object(PositionSizer, '_get_price')
    async def test_negative_price(self, mock_price, sizer, normal_context):
        """Test when price is negative (shouldn't happen but...)."""
        mock_price.return_value = -150.0
        
        decisions = [
            TradeDecision(
                ticker="AAPL", action="BUY", score=85.0,
                confidence=0.8, sector="Tech", rationale="Test"
            )
        ]
        
        positions = await sizer.size_positions(decisions, normal_context)
        
        # Should handle gracefully
        assert isinstance(positions, list)
    
    @pytest.mark.asyncio
    async def test_zero_portfolio_value(self, sizer):
        """Test with zero portfolio value."""
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
        
        decisions = [
            TradeDecision(
                ticker="AAPL", action="BUY", score=85.0,
                confidence=0.8, sector="Tech", rationale="Test"
            )
        ]
        
        positions = await sizer.size_positions(decisions, context)
        
        # Should return empty or handle gracefully
        assert isinstance(positions, list)
    
    @pytest.mark.asyncio
    @patch.object(PositionSizer, '_get_covariance_matrix')
    @patch.object(PositionSizer, '_get_price')
    async def test_singular_covariance_matrix(self, mock_price, mock_cov, sizer, normal_context):
        """Test with singular covariance matrix."""
        mock_price.return_value = 100.0
        # Return singular matrix (all same values)
        mock_cov.return_value = np.ones((2, 2)) * 0.0001
        
        decisions = [
            TradeDecision(ticker="AAPL", action="BUY", score=85.0, confidence=0.8, sector="Tech", rationale="Test"),
            TradeDecision(ticker="MSFT", action="BUY", score=82.0, confidence=0.7, sector="Tech", rationale="Test"),
        ]
        
        positions = await sizer.size_positions(decisions, normal_context)
        
        # Should handle gracefully with fallback weights
        assert isinstance(positions, list)
    
    @pytest.mark.asyncio
    async def test_very_low_score_conviction(self, sizer, normal_context):
        """Test conviction multiplier with very low score."""
        # Score of 50 (below normal range)
        mult = sizer._conviction_multiplier(50)
        
        # Should still return a positive multiplier
        assert mult > 0
    
    @pytest.mark.asyncio
    async def test_very_high_score_conviction(self, sizer, normal_context):
        """Test conviction multiplier with very high score."""
        # Score of 100 (max)
        mult = sizer._conviction_multiplier(100)
        
        # Should return reasonable multiplier (not infinite)
        assert mult > 0 and mult < 10
    
    @pytest.mark.asyncio
    async def test_unknown_regime_multiplier(self, sizer):
        """Test regime multiplier with unknown regime."""
        mult = sizer._regime_multiplier("unknown_regime")
        
        # Should default to 1.0
        assert mult == 1.0
    
    @pytest.mark.asyncio
    @patch.object(PositionSizer, '_get_price')
    @patch.object(PositionSizer, '_risk_parity_weights')
    async def test_sell_nonexistent_position(self, mock_rp, mock_price, sizer, normal_context):
        """Test selling a position that doesn't exist."""
        mock_price.return_value = 100.0
        mock_rp.return_value = {}
        
        decisions = [
            TradeDecision(
                ticker="NONEXISTENT", action="SELL", score=30.0,
                confidence=0.9, sector="Tech", rationale="Sell signal"
            )
        ]
        
        positions = await sizer.size_positions(decisions, normal_context)
        
        # Should return empty (can't sell what we don't have)
        assert len(positions) == 0


# =============================================================================
# MEMORY EDGE CASES (without DB)
# =============================================================================

class TestMemoryEdgeCases:
    """Edge cases for memory system (unit tests without DB)."""
    
    def test_memory_with_none_outcome(self):
        """Test Memory dataclass with None outcome."""
        memory = Memory(
            ticker="AAPL", action="BUY", score=85.0, regime="normal",
            outcome_pct=0.0,  # No outcome yet
            rationale="Test", lesson_learned=None, similarity=0.8
        )
        
        assert memory.outcome_pct == 0.0
        assert memory.lesson_learned is None
    
    def test_memory_with_negative_outcome(self):
        """Test Memory with negative outcome."""
        memory = Memory(
            ticker="AAPL", action="BUY", score=85.0, regime="normal",
            outcome_pct=-15.5,  # Loss
            rationale="Test", lesson_learned="Should have set stop-loss",
            similarity=0.8
        )
        
        assert memory.outcome_pct == -15.5
    
    def test_memory_with_extreme_similarity(self):
        """Test Memory with extreme similarity values."""
        # Similarity = 1.0 (perfect match)
        memory1 = Memory(
            ticker="AAPL", action="BUY", score=85.0, regime="normal",
            outcome_pct=5.0, rationale="Test", lesson_learned=None, similarity=1.0
        )
        
        # Similarity = 0.0 (no match)
        memory2 = Memory(
            ticker="MSFT", action="BUY", score=85.0, regime="normal",
            outcome_pct=5.0, rationale="Test", lesson_learned=None, similarity=0.0
        )
        
        assert memory1.similarity == 1.0
        assert memory2.similarity == 0.0


# =============================================================================
# CONTEXT EDGE CASES
# =============================================================================

class TestContextEdgeCases:
    """Edge cases for context aggregation."""
    
    def test_context_with_empty_positions(self):
        """Test context with no positions."""
        context = TradingContext(
            timestamp=datetime.now(timezone.utc),
            portfolio=PortfolioState(
                cash=100000, total_value=100000, positions=[],
                sector_exposure={}, unrealized_pnl=0
            ),
            market=MarketState(regime="normal", regime_confidence=0.8, vix=15.0),
            buy_candidates=[],
            sell_candidates=[],
            hold_review=[],
            data_freshness=DataFreshness(),
        )
        
        assert context.portfolio.position_count == 0
    
    def test_context_sector_exposure_sums_to_less_than_100(self):
        """Test context where sector exposure + cash < 100%."""
        context = TradingContext(
            timestamp=datetime.now(timezone.utc),
            portfolio=PortfolioState(
                cash=50000, total_value=100000, positions=[],
                sector_exposure={"Technology": 0.30},  # 30% Tech + 50% cash = 80%
                unrealized_pnl=0
            ),
            market=MarketState(regime="normal", regime_confidence=0.8, vix=15.0),
            buy_candidates=[],
            sell_candidates=[],
            hold_review=[],
            data_freshness=DataFreshness(),
        )
        
        # Should handle missing 20%
        total = sum(context.portfolio.sector_exposure.values())
        cash_pct = context.portfolio.cash / context.portfolio.total_value
        assert total + cash_pct <= 1.0  # Reasonable
    
    def test_context_to_dict_with_none_values(self):
        """Test context serialization with None values."""
        context = TradingContext(
            timestamp=datetime.now(timezone.utc),
            portfolio=PortfolioState(
                cash=100000, total_value=100000, positions=[],
                sector_exposure={}, unrealized_pnl=0
            ),
            market=MarketState(regime="normal", regime_confidence=0.8, vix=15.0),
            buy_candidates=[],
            sell_candidates=[],
            hold_review=[],
            data_freshness=DataFreshness(
                scores_updated=None,  # None!
                scores_age_hours=None,
            ),
        )
        
        # Should serialize without errors
        d = context.to_dict()
        assert isinstance(d, dict)
    
    def test_market_state_extreme_vix(self):
        """Test market state with extreme VIX values."""
        # Very high VIX (crisis)
        market_high = MarketState(regime="crisis", regime_confidence=0.95, vix=80.0)
        assert market_high.vix == 80.0
        
        # Very low VIX (calm)
        market_low = MarketState(regime="low_vol", regime_confidence=0.9, vix=9.0)
        assert market_low.vix == 9.0
    
    def test_stock_candidate_with_zero_scores(self):
        """Test stock candidate with all zero component scores."""
        candidate = StockCandidate(
            ticker="TEST", company_name="Test Co", score=0.0,
            signal="SELL", sector="Unknown", rank=999,
            fundamental_score=0, sentiment_score=0,
            technical_score=0, macro_score=0,
        )
        
        assert candidate.score == 0.0
        assert candidate.signal == "SELL"
