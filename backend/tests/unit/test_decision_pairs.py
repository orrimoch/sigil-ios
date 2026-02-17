"""
Unit tests for Decision Pair Logging (REC-298)

Tests:
- Decision logging
- Outcome recording
- Training pair generation
- Export functionality
"""

import pytest
import asyncio
import json
import tempfile
from pathlib import Path
from datetime import datetime, timezone

from src.agent.decision_pairs import (
    DecisionPairLogger,
    DecisionContext,
    DecisionRecord,
    DecisionPair,
)


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_pairs.db"
        yield db_path


@pytest.fixture
def sample_context():
    """Sample decision context for testing."""
    return DecisionContext(
        timestamp=datetime.now(timezone.utc).isoformat(),
        regime="normal",
        vix_level=15.5,
        portfolio_value=100000,
        cash_available=25000,
        positions_count=5,
        sector_exposure={"Technology": 0.3, "Healthcare": 0.2},
        ticker="AAPL",
        ticker_score=82.5,
        ticker_sector="Technology",
        ticker_price=175.50,
        ticker_market_cap=2800000000000,
        ticker_sentiment=72.0,
        ticker_technical=78.5,
        ticker_fundamental=88.0,
        top_candidates=[
            {"ticker": "AAPL", "score": 82.5},
            {"ticker": "MSFT", "score": 79.3},
            {"ticker": "GOOGL", "score": 76.8},
        ],
        recent_trades=[],
        recent_outcomes=[5.2, -2.1, 8.5],
    )


class TestDecisionContext:
    """Tests for DecisionContext."""
    
    def test_to_prompt(self, sample_context):
        """Test context to prompt conversion."""
        prompt = sample_context.to_prompt()
        
        assert "Market Context:" in prompt
        assert "Regime: normal" in prompt
        assert "VIX: 15.5" in prompt
        assert "Portfolio: $100,000" in prompt
        assert "Candidate Stock: AAPL" in prompt
        assert "Composite Score: 82.5" in prompt
    
    def test_context_serialization(self, sample_context):
        """Test context can be serialized to JSON."""
        from dataclasses import asdict
        
        data = asdict(sample_context)
        json_str = json.dumps(data, default=str)
        
        assert len(json_str) > 0
        parsed = json.loads(json_str)
        assert parsed["ticker"] == "AAPL"
        assert parsed["regime"] == "normal"


class TestDecisionPairLogger:
    """Tests for DecisionPairLogger."""
    
    @pytest.mark.asyncio
    async def test_initialize(self, temp_db):
        """Test logger initialization creates tables."""
        logger = DecisionPairLogger(db_path=temp_db)
        await logger.initialize()
        
        assert temp_db.exists()
    
    @pytest.mark.asyncio
    async def test_log_decision(self, temp_db, sample_context):
        """Test logging a decision."""
        logger = DecisionPairLogger(db_path=temp_db)
        await logger.initialize()
        
        record_id = await logger.log_decision(
            user_id="test_user",
            context=sample_context,
            action="BUY",
            shares=100,
            rationale="Strong score and momentum",
            confidence=0.85,
        )
        
        assert record_id > 0
    
    @pytest.mark.asyncio
    async def test_record_outcome(self, temp_db, sample_context):
        """Test recording outcome for a decision."""
        logger = DecisionPairLogger(db_path=temp_db)
        await logger.initialize()
        
        # Log decision
        record_id = await logger.log_decision(
            user_id="test_user",
            context=sample_context,
            action="BUY",
            shares=100,
            rationale="Test trade",
            confidence=0.80,
        )
        
        # Record outcome
        await logger.record_outcome(
            record_id=record_id,
            outcome_pct=12.5,
            lesson="Good timing on entry",
        )
        
        # Verify
        decisions = await logger.get_decisions_with_outcomes()
        assert len(decisions) == 1
        assert decisions[0].outcome_pct == 12.5
        assert decisions[0].preference == 1  # Good outcome
    
    @pytest.mark.asyncio
    async def test_preference_labels(self, temp_db, sample_context):
        """Test preference labeling based on outcome."""
        logger = DecisionPairLogger(db_path=temp_db)
        await logger.initialize()
        
        # Good outcome (> +5%)
        id1 = await logger.log_decision(
            user_id="test_user",
            context=sample_context,
            action="BUY",
            shares=100,
            rationale="Test",
            confidence=0.8,
        )
        await logger.record_outcome(id1, outcome_pct=8.0)
        
        # Bad outcome (< -3%)
        id2 = await logger.log_decision(
            user_id="test_user",
            context=sample_context,
            action="BUY",
            shares=100,
            rationale="Test",
            confidence=0.8,
        )
        await logger.record_outcome(id2, outcome_pct=-5.0)
        
        # Neutral outcome (-3% to +5%)
        id3 = await logger.log_decision(
            user_id="test_user",
            context=sample_context,
            action="BUY",
            shares=100,
            rationale="Test",
            confidence=0.8,
        )
        await logger.record_outcome(id3, outcome_pct=2.0)
        
        decisions = await logger.get_decisions_with_outcomes()
        prefs = {d.id: d.preference for d in decisions}
        
        assert prefs[id1] == 1   # Good
        assert prefs[id2] == -1  # Bad
        assert prefs[id3] == 0   # Neutral
    
    @pytest.mark.asyncio
    async def test_get_stats(self, temp_db, sample_context):
        """Test getting statistics."""
        logger = DecisionPairLogger(db_path=temp_db)
        await logger.initialize()
        
        # Log some decisions
        # Preference thresholds: >5% = preferred, <-3% = dispreferred
        for i, outcome in enumerate([10.0, 6.0, -2.0, -8.0, 3.0]):
            record_id = await logger.log_decision(
                user_id="test_user",
                context=sample_context,
                action="BUY",
                shares=100,
                rationale=f"Test {i}",
                confidence=0.8,
            )
            await logger.record_outcome(record_id, outcome_pct=outcome)
        
        stats = await logger.get_stats()
        
        assert stats["total_decisions"] == 5
        assert stats["with_outcomes"] == 5
        assert stats["preferred"] == 2  # 10.0 and 6.0 (> 5%)
        assert stats["dispreferred"] == 1  # -8.0 (< -3%)
        assert stats["neutral"] == 2  # -2.0 and 3.0


class TestTrainingPairGeneration:
    """Tests for DPO training pair generation."""
    
    @pytest.mark.asyncio
    async def test_generate_pairs_insufficient_data(self, temp_db, sample_context):
        """Test that insufficient data returns empty list."""
        logger = DecisionPairLogger(db_path=temp_db)
        await logger.initialize()
        
        # Only one decision - not enough for pairs
        record_id = await logger.log_decision(
            user_id="test_user",
            context=sample_context,
            action="BUY",
            shares=100,
            rationale="Single trade",
            confidence=0.8,
        )
        await logger.record_outcome(record_id, outcome_pct=5.0)
        
        pairs = await logger.generate_training_pairs()
        assert len(pairs) == 0
    
    @pytest.mark.asyncio
    async def test_generate_pairs_basic(self, temp_db, sample_context):
        """Test basic pair generation with clear winners and losers."""
        logger = DecisionPairLogger(db_path=temp_db)
        await logger.initialize()
        
        # Create decisions with varying outcomes
        outcomes = [15.0, 12.0, 8.0, 3.0, -2.0, -5.0, -10.0, -15.0]
        for i, outcome in enumerate(outcomes):
            record_id = await logger.log_decision(
                user_id="test_user",
                context=sample_context,
                action="BUY",
                shares=100,
                rationale=f"Trade {i} with outcome {outcome}",
                confidence=0.8,
            )
            await logger.record_outcome(record_id, outcome_pct=outcome)
        
        pairs = await logger.generate_training_pairs(min_outcome_diff=10.0)
        
        # Should have pairs where diff >= 10%
        assert len(pairs) > 0
        
        for pair in pairs:
            assert pair.chosen_outcome_pct > pair.rejected_outcome_pct
            assert pair.chosen_outcome_pct - pair.rejected_outcome_pct >= 10.0
    
    @pytest.mark.asyncio
    async def test_pair_dpo_format(self, temp_db, sample_context):
        """Test pair conversion to DPO format."""
        pair = DecisionPair(
            context_prompt="Market Context: normal\nTicker: AAPL",
            chosen_response="BUY 100 shares. Rationale: Strong momentum",
            rejected_response="SELL 50 shares. Rationale: Taking profits",
            chosen_outcome_pct=12.5,
            rejected_outcome_pct=-5.0,
            regime="normal",
        )
        
        dpo = pair.to_dpo_format()
        
        assert "prompt" in dpo
        assert "chosen" in dpo
        assert "rejected" in dpo
        assert "Market Context" in dpo["prompt"]
        assert "BUY 100" in dpo["chosen"]


class TestExport:
    """Tests for export functionality."""
    
    @pytest.mark.asyncio
    async def test_export_to_jsonl(self, temp_db, sample_context):
        """Test exporting pairs to JSONL."""
        logger = DecisionPairLogger(db_path=temp_db)
        await logger.initialize()
        
        # Create enough data for pairs
        for i, outcome in enumerate([15.0, 10.0, -5.0, -12.0]):
            record_id = await logger.log_decision(
                user_id="test_user",
                context=sample_context,
                action="BUY",
                shares=100,
                rationale=f"Trade {i}",
                confidence=0.8,
            )
            await logger.record_outcome(record_id, outcome_pct=outcome)
        
        # Export
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            output_path = f.name
        
        count = await logger.export_to_jsonl(output_path, min_outcome_diff=10.0)
        
        # Verify file
        with open(output_path) as f:
            lines = f.readlines()
        
        assert len(lines) == count
        if lines:
            first_pair = json.loads(lines[0])
            assert "prompt" in first_pair
            assert "chosen" in first_pair
            assert "rejected" in first_pair
    
    @pytest.mark.asyncio
    async def test_export_all_decisions(self, temp_db, sample_context):
        """Test exporting all decisions to JSON."""
        logger = DecisionPairLogger(db_path=temp_db)
        await logger.initialize()
        
        # Log decisions
        for i in range(3):
            record_id = await logger.log_decision(
                user_id="test_user",
                context=sample_context,
                action="BUY",
                shares=100,
                rationale=f"Trade {i}",
                confidence=0.8,
            )
            await logger.record_outcome(record_id, outcome_pct=i * 5)
        
        # Export
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            output_path = f.name
        
        count = await logger.export_all_decisions(output_path)
        
        # Verify
        with open(output_path) as f:
            data = json.load(f)
        
        assert len(data) == 3
        assert count == 3


class TestDecisionRecord:
    """Tests for DecisionRecord."""
    
    def test_to_dict(self):
        """Test record serialization."""
        record = DecisionRecord(
            id=1,
            user_id="test",
            action="BUY",
            shares=100,
            rationale="Test trade",
            confidence=0.85,
            outcome_pct=7.5,
            preference=1,
        )
        
        d = record.to_dict()
        
        assert d["id"] == 1
        assert d["action"] == "BUY"
        assert d["shares"] == 100
        assert d["outcome_pct"] == 7.5
        assert d["preference"] == 1
    
    def test_get_ticker(self):
        """Test ticker extraction from context."""
        record = DecisionRecord(
            context_json='{"ticker": "GOOGL", "regime": "normal"}'
        )
        
        assert record.get_ticker() == "GOOGL"
    
    def test_get_ticker_invalid_json(self):
        """Test ticker extraction with invalid JSON."""
        record = DecisionRecord(context_json="invalid")
        
        assert record.get_ticker() == ""
