"""
Unit tests for Agent Memory System (REC-281, REC-282)

Note: These tests require PostgreSQL with pgvector extension.
Set DATABASE_URL env var or use default local PostgreSQL.
Tests use a separate test database: sigil_agent_test
"""

import pytest
import pytest_asyncio
import asyncio
import os
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Use test database
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "postgresql://localhost/sigil_agent_test")

from src.agent.memory import (
    AgentMemory,
    Decision,
    Memory,
    get_agent_memory,
    EMBEDDING_DIM,
)


# Skip all tests if PostgreSQL is not available
def postgres_available():
    """Check if PostgreSQL is available."""
    try:
        import asyncpg
        import asyncio
        
        async def check():
            try:
                conn = await asyncpg.connect(TEST_DATABASE_URL, timeout=2)
                await conn.close()
                return True
            except:
                return False
        
        # Create new event loop for check
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(check())
        finally:
            loop.close()
    except:
        return False


# Check if PostgreSQL is available
POSTGRES_AVAILABLE = postgres_available()

pytestmark = pytest.mark.skipif(
    not POSTGRES_AVAILABLE,
    reason="PostgreSQL not available - run: createdb sigil_agent_test && psql -d sigil_agent_test -c 'CREATE EXTENSION vector'"
)


class TestDecisionDataclass:
    """Test Decision dataclass."""
    
    def test_creation(self):
        """Test Decision creation with defaults."""
        decision = Decision()
        assert decision.ticker == ""
        assert decision.action == ""
        assert decision.outcome_pct is None
    
    def test_creation_with_values(self):
        """Test Decision creation with values."""
        decision = Decision(
            ticker="AAPL",
            action="BUY",
            shares=10,
            price=150.0,
            score=85.0,
        )
        assert decision.ticker == "AAPL"
        assert decision.shares == 10
    
    def test_to_dict(self):
        """Test Decision to_dict method."""
        decision = Decision(ticker="MSFT", action="BUY", score=90.0)
        d = decision.to_dict()
        assert d["ticker"] == "MSFT"
        assert d["score"] == 90.0
        assert "timestamp" in d


class TestMemoryDataclass:
    """Test Memory dataclass."""
    
    def test_creation(self):
        """Test Memory creation."""
        memory = Memory(
            ticker="AAPL",
            action="BUY",
            score=85.0,
            regime="normal",
            outcome_pct=5.2,
            rationale="Test",
            lesson_learned="Hold through vol",
            similarity=0.85,
        )
        assert memory.ticker == "AAPL"
        assert memory.similarity == 0.85


class TestAgentMemoryInitialization:
    """Test AgentMemory initialization."""
    
    @pytest.mark.asyncio
    async def test_initialize_connects(self):
        """Test that initialize connects to PostgreSQL."""
        memory = AgentMemory(database_url=TEST_DATABASE_URL)
        await memory.initialize()
        
        assert memory._pool is not None
        
        await memory.close()
    
    @pytest.mark.asyncio
    async def test_initialize_can_query(self):
        """Test that we can query after initialization."""
        memory = AgentMemory(database_url=TEST_DATABASE_URL)
        await memory.initialize()
        
        # Should not raise
        stats = await memory.get_statistics()
        assert "total_decisions" in stats
        
        await memory.close()


class TestAgentMemoryOperations:
    """Test AgentMemory CRUD operations."""
    
    @pytest_asyncio.fixture
    async def memory(self):
        """Create a test memory instance."""
        mem = AgentMemory(database_url=TEST_DATABASE_URL)
        await mem.initialize()
        
        # Clean up test data before test
        async with mem._pool.acquire() as conn:
            await conn.execute("DELETE FROM agent_decisions WHERE ticker LIKE 'TEST%'")
        
        yield mem
        
        # Clean up after test
        async with mem._pool.acquire() as conn:
            await conn.execute("DELETE FROM agent_decisions WHERE ticker LIKE 'TEST%'")
        
        await mem.close()
    
    @pytest.mark.asyncio
    async def test_store_decision(self, memory):
        """Test storing a decision."""
        decision = Decision(
            ticker="TESTA",
            action="BUY",
            shares=10,
            price=150.0,
            score=85.0,
            regime="normal",
        )
        
        decision_id = await memory.store_decision(decision)
        
        assert decision_id > 0
    
    @pytest.mark.asyncio
    async def test_store_multiple_decisions(self, memory):
        """Test storing multiple decisions."""
        for ticker in ["TESTB", "TESTC", "TESTD"]:
            decision = Decision(ticker=ticker, action="BUY", shares=10, price=100.0, score=80.0, regime="normal")
            await memory.store_decision(decision)
        
        decisions = await memory.get_recent_decisions(limit=100)
        test_decisions = [d for d in decisions if d.ticker.startswith("TEST")]
        assert len(test_decisions) >= 3
    
    @pytest.mark.asyncio
    async def test_update_outcome(self, memory):
        """Test updating a decision outcome."""
        decision = Decision(ticker="TESTE", action="BUY", shares=10, price=150.0, score=85.0, regime="normal")
        decision_id = await memory.store_decision(decision)
        
        await memory.update_outcome(decision_id, outcome_pct=7.5, lesson_learned="Good timing")
        
        decisions = await memory.get_recent_decisions(limit=100)
        test_decision = next((d for d in decisions if d.ticker == "TESTE"), None)
        assert test_decision is not None
        assert test_decision.outcome_pct == 7.5
        assert test_decision.lesson_learned == "Good timing"
    
    @pytest.mark.asyncio
    async def test_get_recent_decisions(self, memory):
        """Test getting recent decisions."""
        import time
        for ticker in ["TESTF", "TESTG", "TESTH"]:
            decision = Decision(ticker=ticker, action="BUY", shares=10, price=100.0, score=80.0, regime="normal")
            await memory.store_decision(decision)
            time.sleep(0.01)  # Ensure different timestamps
        
        recent = await memory.get_recent_decisions(limit=100)
        test_recent = [d for d in recent if d.ticker.startswith("TEST")]
        
        assert len(test_recent) >= 3
        # Most recent first - TESTH should be first among test tickers
        test_tickers = [d.ticker for d in test_recent[:3]]
        assert "TESTH" in test_tickers
    
    @pytest.mark.asyncio
    async def test_get_pending_outcomes(self, memory):
        """Test getting decisions needing outcome updates."""
        # Store a decision with old timestamp
        old_decision = Decision(
            ticker="TESTI",
            action="BUY",
            shares=10,
            price=150.0,
            score=85.0,
            regime="normal",
            timestamp=datetime.now(timezone.utc) - timedelta(days=20),
        )
        await memory.store_decision(old_decision)
        
        # Store a recent decision
        new_decision = Decision(
            ticker="TESTJ",
            action="BUY",
            shares=5,
            price=400.0,
            score=90.0,
            regime="normal",
        )
        await memory.store_decision(new_decision)
        
        pending = await memory.get_pending_outcomes(min_age_days=14)
        
        # The old one should be in pending
        test_pending = [p for p in pending if p["ticker"].startswith("TEST")]
        assert len(test_pending) >= 1
        assert any(p["ticker"] == "TESTI" for p in test_pending)


class TestAgentMemoryStatistics:
    """Test AgentMemory statistics."""
    
    @pytest_asyncio.fixture
    async def memory_with_data(self):
        """Create memory with test data."""
        mem = AgentMemory(database_url=TEST_DATABASE_URL)
        await mem.initialize()
        
        # Clean up test data
        async with mem._pool.acquire() as conn:
            await conn.execute("DELETE FROM agent_decisions WHERE ticker LIKE 'STATS%'")
        
        # Add some decisions with outcomes
        for ticker, outcome in [("STATSA", 5.0), ("STATSB", -2.0), ("STATSC", 8.0)]:
            decision = Decision(ticker=ticker, action="BUY", shares=10, price=100.0, score=80.0, regime="normal")
            decision_id = await mem.store_decision(decision)
            await mem.update_outcome(decision_id, outcome_pct=outcome)
        
        yield mem
        
        # Clean up
        async with mem._pool.acquire() as conn:
            await conn.execute("DELETE FROM agent_decisions WHERE ticker LIKE 'STATS%'")
        
        await mem.close()
    
    @pytest.mark.asyncio
    async def test_total_decisions(self, memory_with_data):
        """Test total decisions count includes our test data."""
        stats = await memory_with_data.get_statistics()
        assert stats["total_decisions"] >= 3  # At least our 3 test decisions
    
    @pytest.mark.asyncio
    async def test_with_outcomes(self, memory_with_data):
        """Test outcomes count includes our test data."""
        stats = await memory_with_data.get_statistics()
        assert stats["with_outcomes"] >= 3  # At least our 3 test decisions
    
    @pytest.mark.asyncio
    async def test_win_rate(self, memory_with_data):
        """Test win rate calculation."""
        stats = await memory_with_data.get_statistics()
        # Should have positive win rate (at least 2 of 3 test decisions are wins)
        assert stats["win_rate"] > 0
    
    @pytest.mark.asyncio
    async def test_avg_outcome(self, memory_with_data):
        """Test average outcome calculation."""
        stats = await memory_with_data.get_statistics()
        # Should return a number (our test data averages to 3.67%)
        assert isinstance(stats["avg_outcome_pct"], float)


class TestEmbeddings:
    """Test embedding generation."""
    
    @pytest_asyncio.fixture
    async def memory(self):
        """Create a test memory instance."""
        mem = AgentMemory(database_url=TEST_DATABASE_URL)
        await mem.initialize()
        yield mem
        await mem.close()
    
    @pytest.mark.asyncio
    async def test_hash_embedding_dimension(self, memory):
        """Test hash embedding has correct dimension."""
        embedding = memory._hash_embedding("test text")
        assert len(embedding) == EMBEDDING_DIM
    
    @pytest.mark.asyncio
    async def test_hash_embedding_deterministic(self, memory):
        """Test hash embedding is deterministic."""
        import numpy as np
        embedding1 = memory._hash_embedding("same text")
        embedding2 = memory._hash_embedding("same text")
        assert np.allclose(embedding1, embedding2)
    
    @pytest.mark.asyncio
    async def test_hash_embedding_different_inputs(self, memory):
        """Test different inputs produce different embeddings."""
        import numpy as np
        embedding1 = memory._hash_embedding("text one")
        embedding2 = memory._hash_embedding("text two")
        assert not np.allclose(embedding1, embedding2)
    
    @pytest.mark.asyncio
    async def test_hash_embedding_normalized(self, memory):
        """Test hash embedding is unit normalized."""
        import numpy as np
        embedding = memory._hash_embedding("test text")
        norm = np.linalg.norm(embedding)
        assert abs(norm - 1.0) < 0.01


class TestSimilaritySearch:
    """Test similarity search functionality."""
    
    @pytest_asyncio.fixture
    async def memory_with_decisions(self):
        """Create memory with varied decisions."""
        mem = AgentMemory(database_url=TEST_DATABASE_URL)
        await mem.initialize()
        
        # Clean up test data
        async with mem._pool.acquire() as conn:
            await conn.execute("DELETE FROM agent_decisions WHERE ticker LIKE 'SIM%'")
        
        # Add decisions with different characteristics
        for ticker, regime, outcome in [
            ("SIMA", "normal", 5.0),
            ("SIMB", "normal", 3.0),
            ("SIMC", "high_vol", -5.0),
        ]:
            decision = Decision(
                ticker=ticker,
                action="BUY",
                shares=10,
                price=100.0,
                score=80.0,
                regime=regime,
            )
            decision_id = await mem.store_decision(decision)
            await mem.update_outcome(decision_id, outcome_pct=outcome)
        
        yield mem
        
        # Clean up
        async with mem._pool.acquire() as conn:
            await conn.execute("DELETE FROM agent_decisions WHERE ticker LIKE 'SIM%'")
        
        await mem.close()
    
    @pytest.mark.asyncio
    async def test_retrieve_similar_returns_results(self, memory_with_decisions):
        """Test retrieve_similar returns results."""
        from src.agent.context import TradingContext, PortfolioState, MarketState, DataFreshness
        
        context = TradingContext(
            timestamp=datetime.now(),
            portfolio=PortfolioState(cash=100000, total_value=100000, positions=[], sector_exposure={}, unrealized_pnl=0),
            market=MarketState(regime="normal", regime_confidence=0.8, vix=15.0),
            buy_candidates=[],
            sell_candidates=[],
            hold_review=[],
            data_freshness=DataFreshness(),
        )
        
        similar = await memory_with_decisions.retrieve_similar(context, k=5)
        
        assert len(similar) > 0
    
    @pytest.mark.asyncio
    async def test_retrieve_similar_sorted_by_similarity(self, memory_with_decisions):
        """Test results are sorted by similarity."""
        from src.agent.context import TradingContext, PortfolioState, MarketState, DataFreshness
        
        context = TradingContext(
            timestamp=datetime.now(),
            portfolio=PortfolioState(cash=100000, total_value=100000, positions=[], sector_exposure={}, unrealized_pnl=0),
            market=MarketState(regime="normal", regime_confidence=0.8, vix=15.0),
            buy_candidates=[],
            sell_candidates=[],
            hold_review=[],
            data_freshness=DataFreshness(),
        )
        
        similar = await memory_with_decisions.retrieve_similar(context, k=5)
        
        # Check sorted descending
        for i in range(len(similar) - 1):
            assert similar[i].similarity >= similar[i + 1].similarity
    
    @pytest.mark.asyncio
    async def test_retrieve_similar_k_limit(self, memory_with_decisions):
        """Test k parameter limits results."""
        from src.agent.context import TradingContext, PortfolioState, MarketState, DataFreshness
        
        context = TradingContext(
            timestamp=datetime.now(),
            portfolio=PortfolioState(cash=100000, total_value=100000, positions=[], sector_exposure={}, unrealized_pnl=0),
            market=MarketState(regime="normal", regime_confidence=0.8, vix=15.0),
            buy_candidates=[],
            sell_candidates=[],
            hold_review=[],
            data_freshness=DataFreshness(),
        )
        
        similar = await memory_with_decisions.retrieve_similar(context, k=1)
        
        assert len(similar) <= 1


class TestConvenienceFunction:
    """Test convenience functions."""
    
    @pytest.mark.asyncio
    async def test_get_agent_memory(self):
        """Test get_agent_memory convenience function."""
        memory = await get_agent_memory(database_url=TEST_DATABASE_URL)
        assert memory is not None
        assert isinstance(memory, AgentMemory)
        await memory.close()
