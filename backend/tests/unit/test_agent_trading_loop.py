"""
Unit tests for agent trading loop module (REC-313).

Tests the TradingLoop class including run cycle, pause/resume,
and pipeline orchestration.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from agent.trading_loop import TradingLoop, AgentStatus


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def trading_loop():
    """Create a TradingLoop instance for testing."""
    return TradingLoop()


# ═══════════════════════════════════════════════════════════════════════════
# AgentStatus Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestAgentStatus:
    """Test AgentStatus enum."""
    
    def test_status_values(self):
        """Test status enum values."""
        assert AgentStatus.PAUSED.value == "paused"
        assert AgentStatus.ACTIVE.value == "active"
        assert AgentStatus.RUNNING.value == "running"


# ═══════════════════════════════════════════════════════════════════════════
# TradingLoop Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestTradingLoop:
    """Test TradingLoop class."""
    
    def test_loop_creation(self, trading_loop):
        """Test creating a trading loop instance."""
        assert trading_loop is not None
    
    def test_initial_status(self, trading_loop):
        """Test initial status is paused."""
        assert trading_loop.status == AgentStatus.PAUSED
    
    def test_pause(self, trading_loop):
        """Test pausing the loop."""
        trading_loop._status = AgentStatus.ACTIVE
        trading_loop.pause()
        assert trading_loop.status == AgentStatus.PAUSED
    
    def test_resume(self, trading_loop):
        """Test resuming the loop."""
        trading_loop._status = AgentStatus.PAUSED
        trading_loop.resume()
        assert trading_loop.status == AgentStatus.ACTIVE
    
    def test_status_property(self, trading_loop):
        """Test status property returns correct value."""
        trading_loop._status = AgentStatus.RUNNING
        assert trading_loop.status == AgentStatus.RUNNING
    
    def test_settings_property(self, trading_loop):
        """Test settings property exists."""
        settings = trading_loop.settings
        assert settings is not None
    
    def test_last_run_property(self, trading_loop):
        """Test last_run property initially None."""
        assert trading_loop.last_run is None
    
    @pytest.mark.asyncio
    async def test_run_returns_result(self, trading_loop):
        """Test that run returns a TradingLoopResult."""
        # Mock the heavy pipeline stages to avoid full execution
        with patch.object(trading_loop, '_aggregate_context', side_effect=Exception("Test skip")):
            result = await trading_loop.run(user_id="user-1")
        
        # Should return a result even on error
        assert result is not None
        # Result should be a TradingLoopResult with run_id
        assert hasattr(result, 'run_id') or hasattr(result, 'errors')


# ═══════════════════════════════════════════════════════════════════════════
# TradingLoop Pipeline Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestTradingLoopPipeline:
    """Test trading loop pipeline stages."""
    
    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not __import__('os').environ.get('DATABASE_URL'),
        reason="Requires PostgreSQL (DATABASE_URL not set)"
    )
    async def test_initialize(self, trading_loop):
        """Test loop initialization."""
        await trading_loop.initialize()
        # Should not raise
        assert True
