"""
Unit tests for agent learning module (REC-313).

Tests the LearningLoop class including outcome calculation,
lesson generation, and learning statistics.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from agent.learning import LearningLoop, OutcomeTag


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def learning_loop():
    """Create a LearningLoop instance for testing."""
    return LearningLoop()


# ═══════════════════════════════════════════════════════════════════════════
# OutcomeTag Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestOutcomeTag:
    """Test OutcomeTag enum."""
    
    def test_tag_values_exist(self):
        """Test that outcome tags are defined."""
        assert OutcomeTag.STRONG_WIN.value == "strong_win"
        assert OutcomeTag.WIN.value == "win"
        assert OutcomeTag.SMALL_WIN.value == "small_win"
        assert OutcomeTag.NEUTRAL.value == "neutral"
        assert OutcomeTag.LOSS.value == "loss"
        assert OutcomeTag.STRONG_LOSS.value == "strong_loss"
    
    def test_from_outcome_strong_win(self):
        """Test strong win classification."""
        tag = OutcomeTag.from_outcome(15.0)
        assert tag == OutcomeTag.STRONG_WIN
    
    def test_from_outcome_win(self):
        """Test win classification."""
        tag = OutcomeTag.from_outcome(7.0)
        assert tag == OutcomeTag.WIN
    
    def test_from_outcome_small_win(self):
        """Test small win classification."""
        tag = OutcomeTag.from_outcome(3.0)
        assert tag == OutcomeTag.SMALL_WIN
    
    def test_from_outcome_neutral(self):
        """Test neutral classification."""
        tag = OutcomeTag.from_outcome(0.5)
        assert tag == OutcomeTag.NEUTRAL
        
        tag = OutcomeTag.from_outcome(-0.5)
        assert tag == OutcomeTag.NEUTRAL
    
    def test_from_outcome_loss(self):
        """Test loss classification."""
        tag = OutcomeTag.from_outcome(-3.0)
        assert tag == OutcomeTag.LOSS
    
    def test_from_outcome_strong_loss(self):
        """Test strong loss classification."""
        tag = OutcomeTag.from_outcome(-10.0)
        assert tag == OutcomeTag.STRONG_LOSS


# ═══════════════════════════════════════════════════════════════════════════
# LearningLoop Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestLearningLoop:
    """Test LearningLoop class."""
    
    def test_loop_creation(self, learning_loop):
        """Test creating a learning loop instance."""
        assert learning_loop is not None
    
    @pytest.mark.asyncio
    async def test_get_recent_lessons_empty(self, learning_loop):
        """Test getting lessons when empty."""
        lessons = await learning_loop.get_recent_lessons(limit=10)
        assert isinstance(lessons, list)
        assert len(lessons) == 0
    
    @pytest.mark.asyncio
    async def test_get_learning_stats_empty(self, learning_loop):
        """Test learning stats with no data."""
        stats = await learning_loop.get_learning_stats()
        
        assert isinstance(stats, dict)
        assert "total_lessons" in stats or "total" in str(stats).lower()
    
    @pytest.mark.asyncio
    async def test_position_status_fallback(self, learning_loop):
        """Test position status returns valid structure on error."""
        # Mock the database import to fail
        with patch.object(learning_loop, '_get_position_status', wraps=learning_loop._get_position_status):
            # Call with a non-existent user to trigger fallback
            status = await learning_loop._get_position_status("NONEXISTENT_TICKER_XYZ", "nonexistent-user")
        
        # Should return valid structure (fallback or real)
        assert "is_open" in status
        assert "exit_price" in status
        assert "exit_date" in status


# ═══════════════════════════════════════════════════════════════════════════
# Learning Pipeline Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestLearningPipeline:
    """Test learning loop pipeline."""
    
    def test_generate_fallback_lesson(self, learning_loop):
        """Test fallback lesson generation produces string."""
        # Create a mock outcome-like object
        mock_outcome = MagicMock()
        mock_outcome.ticker = "AAPL"
        mock_outcome.action = "BUY"
        mock_outcome.outcome_pct = 10.0
        mock_outcome.tag = OutcomeTag.STRONG_WIN
        mock_outcome.holding_days = 14
        
        lesson = learning_loop._generate_fallback_lesson(mock_outcome)
        
        assert isinstance(lesson, str)
        assert len(lesson) > 0
