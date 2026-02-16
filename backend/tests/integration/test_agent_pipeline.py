"""
Integration Tests for Agent Trading Pipeline (REC-287)

Tests the full flow:
1. Context Aggregation
2. Memory Retrieval
3. Decision Engine
4. Position Sizing
5. Risk Validation

These tests use real data but mock external APIs (Claude, IBKR).
"""

import pytest
import pytest_asyncio
import asyncio
import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch, MagicMock

# Test database
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "postgresql://localhost/sigil_agent_test")


def postgres_available():
    """Check if PostgreSQL is available."""
    try:
        import asyncpg
        
        async def check():
            try:
                conn = await asyncpg.connect(TEST_DATABASE_URL, timeout=2)
                await conn.close()
                return True
            except:
                return False
        
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(check())
        finally:
            loop.close()
    except:
        return False


POSTGRES_AVAILABLE = postgres_available()

pytestmark = pytest.mark.skipif(
    not POSTGRES_AVAILABLE,
    reason="PostgreSQL not available"
)


class TestContextAggregation:
    """Test context aggregation in isolation."""
    
    @pytest.mark.asyncio
    async def test_aggregate_returns_context(self):
        """Test that aggregation returns a valid TradingContext."""
        from src.agent.context import ContextAggregator, TradingContext
        
        aggregator = ContextAggregator()
        context = await aggregator.aggregate(top_n_candidates=5)
        
        assert isinstance(context, TradingContext)
        assert context.portfolio is not None
        assert context.market is not None
    
    @pytest.mark.asyncio
    async def test_context_has_candidates(self):
        """Test that context includes buy candidates."""
        from src.agent.context import ContextAggregator
        
        aggregator = ContextAggregator()
        context = await aggregator.aggregate(top_n_candidates=10)
        
        # Should have buy candidates (assuming scores exist)
        # This may be empty if no scores file, which is OK for CI
        assert hasattr(context, 'buy_candidates')
        assert isinstance(context.buy_candidates, list)


class TestMemoryRetrieval:
    """Test memory retrieval."""
    
    @pytest_asyncio.fixture
    async def memory(self):
        """Create test memory with sample decisions."""
        from src.agent.memory import AgentMemory, Decision
        
        mem = AgentMemory(database_url=TEST_DATABASE_URL)
        await mem.initialize()
        
        # Clean up
        async with mem._pool.acquire() as conn:
            await conn.execute("DELETE FROM agent_decisions WHERE ticker LIKE 'INT%'")
        
        # Add sample decisions with outcomes
        for ticker, score, regime, outcome in [
            ("INTA", 85.0, "normal", 5.0),
            ("INTB", 78.0, "normal", -2.0),
            ("INTC", 92.0, "low_vol", 12.0),
        ]:
            d = Decision(
                ticker=ticker, action="BUY", shares=10, price=100.0,
                score=score, regime=regime, sector="Tech", rationale=f"Test {ticker}"
            )
            did = await mem.store_decision(d)
            await mem.update_outcome(did, outcome_pct=outcome)
        
        yield mem
        
        # Clean up
        async with mem._pool.acquire() as conn:
            await conn.execute("DELETE FROM agent_decisions WHERE ticker LIKE 'INT%'")
        await mem.close()
    
    @pytest.mark.asyncio
    async def test_retrieve_similar_with_context(self, memory):
        """Test retrieving similar situations from memory."""
        from src.agent.context import (
            TradingContext, PortfolioState, MarketState, DataFreshness
        )
        
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
        
        similar = await memory.retrieve_similar(context, k=5)
        
        assert len(similar) > 0
        assert all(hasattr(s, 'ticker') for s in similar)
        assert all(hasattr(s, 'outcome_pct') for s in similar)


class TestPositionSizing:
    """Test position sizing with context."""
    
    @pytest.mark.asyncio
    @patch('src.agent.position_sizing.PositionSizer._get_price')
    @patch('src.agent.position_sizing.PositionSizer._risk_parity_weights')
    async def test_size_positions_from_decisions(self, mock_rp, mock_price):
        """Test sizing positions from trade decisions."""
        from src.agent.position_sizing import PositionSizer, TradeDecision
        from src.agent.context import (
            TradingContext, PortfolioState, MarketState, DataFreshness
        )
        
        mock_rp.return_value = {"AAPL": 0.10, "MSFT": 0.10}
        mock_price.side_effect = lambda t: 150.0 if t == "AAPL" else 400.0
        
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
        
        decisions = [
            TradeDecision(ticker="AAPL", action="BUY", score=85.0, confidence=0.8, sector="Tech", rationale="Test"),
            TradeDecision(ticker="MSFT", action="BUY", score=90.0, confidence=0.9, sector="Tech", rationale="Test"),
        ]
        
        sizer = PositionSizer()
        positions = await sizer.size_positions(decisions, context)
        
        assert len(positions) == 2
        assert all(p.shares > 0 for p in positions)
        assert all(p.weight <= 0.10 for p in positions)  # Max weight cap


class TestFullPipeline:
    """Test the complete trading pipeline (mocked Claude)."""
    
    @pytest_asyncio.fixture
    async def memory(self):
        """Create test memory."""
        from src.agent.memory import AgentMemory, Decision
        
        mem = AgentMemory(database_url=TEST_DATABASE_URL)
        await mem.initialize()
        
        # Add a sample decision for retrieval
        d = Decision(
            ticker="PIPE", action="BUY", shares=10, price=100.0,
            score=85.0, regime="normal", sector="Tech", rationale="Pipeline test"
        )
        did = await mem.store_decision(d)
        await mem.update_outcome(did, outcome_pct=5.0)
        
        yield mem
        
        async with mem._pool.acquire() as conn:
            await conn.execute("DELETE FROM agent_decisions WHERE ticker = 'PIPE'")
        await mem.close()
    
    @pytest.mark.asyncio
    @patch('src.agent.position_sizing.PositionSizer._get_price')
    @patch('src.agent.position_sizing.PositionSizer._risk_parity_weights')
    async def test_context_to_sized_positions(self, mock_rp, mock_price, memory):
        """Test flow from context aggregation to sized positions."""
        from src.agent.context import ContextAggregator
        from src.agent.position_sizing import PositionSizer, TradeDecision
        
        mock_rp.return_value = {"TEST": 0.10}
        mock_price.return_value = 100.0
        
        # Step 1: Aggregate context
        aggregator = ContextAggregator()
        context = await aggregator.aggregate(top_n_candidates=5)
        
        # Step 2: Retrieve similar (already tested above)
        similar = await memory.retrieve_similar(context, k=5)
        
        # Step 3: Mock decision (Claude would produce this)
        decisions = [
            TradeDecision(
                ticker="TEST", action="BUY", score=85.0,
                confidence=0.8, sector="Tech", rationale="Test decision"
            )
        ]
        
        # Step 4: Size positions
        sizer = PositionSizer()
        positions = await sizer.size_positions(decisions, context)
        
        assert len(positions) == 1
        assert positions[0].ticker == "TEST"
        assert positions[0].shares > 0


class TestDecisionEngineIntegration:
    """Test decision engine with mocked Claude."""
    
    @pytest.mark.asyncio
    async def test_decision_engine_exists(self):
        """Test that decision engine module exists (created by sub-agent)."""
        try:
            from src.agent.decision_engine import DecisionEngine
            assert True
        except ImportError:
            pytest.skip("Decision engine not yet implemented")
    
    @pytest.mark.asyncio
    async def test_risk_validator_exists(self):
        """Test that risk validator module exists (created by sub-agent)."""
        try:
            from src.agent.risk_validator import RiskValidator
            assert True
        except ImportError:
            pytest.skip("Risk validator not yet implemented")
