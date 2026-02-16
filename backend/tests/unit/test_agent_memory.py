"""
Unit tests for Agent Memory System (REC-281, REC-282)
"""

import pytest
import pytest_asyncio
import asyncio
import tempfile
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

from src.agent.memory import (
    AgentMemory,
    Decision,
    Memory,
    get_agent_memory,
    EMBEDDING_DIM,
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
    async def test_initialize_creates_db(self):
        """Test that initialize creates database file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_memory.db"
            memory = AgentMemory(db_path=db_path)
            
            await memory.initialize()
            
            assert db_path.exists()
    
    @pytest.mark.asyncio
    async def test_initialize_creates_tables(self):
        """Test that initialize creates required tables."""
        with tempfile.TemporaryDirectory() as tmpdir:
            import aiosqlite
            
            db_path = Path(tmpdir) / "test_memory.db"
            memory = AgentMemory(db_path=db_path)
            await memory.initialize()
            
            async with aiosqlite.connect(db_path) as db:
                cursor = await db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
                tables = [row[0] for row in await cursor.fetchall()]
            
            assert "decisions" in tables


class TestAgentMemoryOperations:
    """Test AgentMemory CRUD operations."""
    
    @pytest_asyncio.fixture
    async def memory(self, tmp_path):
        """Create a test memory instance."""
        db_path = tmp_path / "test_memory.db"
        mem = AgentMemory(db_path=db_path)
        await mem.initialize()
        return mem
    
    @pytest.mark.asyncio
    async def test_store_decision(self, memory):
        """Test storing a decision."""
        decision = Decision(
            ticker="AAPL",
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
        for ticker in ["AAPL", "MSFT", "GOOGL"]:
            decision = Decision(ticker=ticker, action="BUY", shares=10, price=100.0, score=80.0)
            await memory.store_decision(decision)
        
        stats = await memory.get_statistics()
        assert stats["total_decisions"] == 3
    
    @pytest.mark.asyncio
    async def test_update_outcome(self, memory):
        """Test updating a decision outcome."""
        decision = Decision(ticker="AAPL", action="BUY", shares=10, price=150.0, score=85.0)
        decision_id = await memory.store_decision(decision)
        
        await memory.update_outcome(decision_id, outcome_pct=7.5, lesson_learned="Good timing")
        
        decisions = await memory.get_recent_decisions(limit=1)
        assert len(decisions) == 1
        assert decisions[0].outcome_pct == 7.5
        assert decisions[0].lesson_learned == "Good timing"
    
    @pytest.mark.asyncio
    async def test_get_recent_decisions(self, memory):
        """Test getting recent decisions."""
        for i, ticker in enumerate(["AAPL", "MSFT", "GOOGL"]):
            decision = Decision(ticker=ticker, action="BUY", shares=10, price=100.0, score=80.0)
            await memory.store_decision(decision)
        
        recent = await memory.get_recent_decisions(limit=2)
        
        assert len(recent) == 2
        # Most recent first
        assert recent[0].ticker == "GOOGL"
    
    @pytest.mark.asyncio
    async def test_get_pending_outcomes(self, memory):
        """Test getting decisions needing outcome updates."""
        # Store a decision with old timestamp
        old_decision = Decision(
            ticker="AAPL",
            action="BUY",
            shares=10,
            price=150.0,
            score=85.0,
            timestamp=datetime.now(timezone.utc) - timedelta(days=20),
        )
        await memory.store_decision(old_decision)
        
        # Store a recent decision
        new_decision = Decision(
            ticker="MSFT",
            action="BUY",
            shares=5,
            price=400.0,
            score=90.0,
        )
        await memory.store_decision(new_decision)
        
        pending = await memory.get_pending_outcomes(min_age_days=14)
        
        # Only the old one should be pending
        assert len(pending) == 1
        assert pending[0]["ticker"] == "AAPL"


class TestAgentMemoryStatistics:
    """Test AgentMemory statistics."""
    
    @pytest_asyncio.fixture
    async def memory_with_data(self, tmp_path):
        """Create memory with test data."""
        db_path = tmp_path / "test_memory.db"
        mem = AgentMemory(db_path=db_path)
        await mem.initialize()
        
        # Add some decisions with outcomes
        for ticker, outcome in [("AAPL", 5.0), ("MSFT", -2.0), ("GOOGL", 8.0)]:
            decision = Decision(ticker=ticker, action="BUY", shares=10, price=100.0, score=80.0)
            decision_id = await mem.store_decision(decision)
            await mem.update_outcome(decision_id, outcome_pct=outcome)
        
        return mem
    
    @pytest.mark.asyncio
    async def test_total_decisions(self, memory_with_data):
        """Test total decisions count."""
        stats = await memory_with_data.get_statistics()
        assert stats["total_decisions"] == 3
    
    @pytest.mark.asyncio
    async def test_with_outcomes(self, memory_with_data):
        """Test outcomes count."""
        stats = await memory_with_data.get_statistics()
        assert stats["with_outcomes"] == 3
    
    @pytest.mark.asyncio
    async def test_win_rate(self, memory_with_data):
        """Test win rate calculation."""
        stats = await memory_with_data.get_statistics()
        # 2 wins (AAPL +5, GOOGL +8) out of 3 = 66.7%
        assert abs(stats["win_rate"] - 0.667) < 0.01
    
    @pytest.mark.asyncio
    async def test_avg_outcome(self, memory_with_data):
        """Test average outcome calculation."""
        stats = await memory_with_data.get_statistics()
        # (5 - 2 + 8) / 3 = 3.67%
        assert abs(stats["avg_outcome_pct"] - 3.67) < 0.1


class TestEmbeddings:
    """Test embedding generation."""
    
    @pytest_asyncio.fixture
    async def memory(self, tmp_path):
        """Create a test memory instance."""
        db_path = tmp_path / "test_memory.db"
        mem = AgentMemory(db_path=db_path)
        await mem.initialize()
        return mem
    
    @pytest.mark.asyncio
    async def test_hash_embedding_dimension(self, memory):
        """Test hash embedding has correct dimension."""
        embedding = memory._hash_embedding("test text")
        assert len(embedding) == EMBEDDING_DIM
    
    @pytest.mark.asyncio
    async def test_hash_embedding_deterministic(self, memory):
        """Test hash embedding is deterministic."""
        embedding1 = memory._hash_embedding("same text")
        embedding2 = memory._hash_embedding("same text")
        assert embedding1 == embedding2
    
    @pytest.mark.asyncio
    async def test_hash_embedding_different_inputs(self, memory):
        """Test different inputs produce different embeddings."""
        embedding1 = memory._hash_embedding("text one")
        embedding2 = memory._hash_embedding("text two")
        assert embedding1 != embedding2
    
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
    async def memory_with_decisions(self, tmp_path):
        """Create memory with varied decisions."""
        db_path = tmp_path / "test_memory.db"
        mem = AgentMemory(db_path=db_path)
        await mem.initialize()
        
        # Add decisions with different characteristics
        for ticker, regime, outcome in [
            ("AAPL", "normal", 5.0),
            ("MSFT", "normal", 3.0),
            ("TSLA", "high_vol", -5.0),
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
        
        return mem
    
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
        # This tests the actual default path
        memory = await get_agent_memory()
        assert memory is not None
        assert isinstance(memory, AgentMemory)
