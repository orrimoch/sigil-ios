"""
Integration tests for agent API endpoints (REC-314).

Tests all agent endpoints for correct response structure and status codes.
Uses the async client from conftest.py.
"""

import pytest


# ═══════════════════════════════════════════════════════════════════════════
# Context Endpoints
# ═══════════════════════════════════════════════════════════════════════════

class TestContextEndpoints:
    """Test /api/v1/agent/context endpoints."""
    
    @pytest.mark.asyncio
    async def test_get_context(self, client):
        """Test GET /agent/context."""
        response = await client.get("/api/v1/agent/context")
        
        assert response.status_code == 200
        data = response.json()
        assert "portfolio" in data or "context" in data or "timestamp" in data
    
    @pytest.mark.asyncio
    async def test_get_context_ticker(self, client):
        """Test GET /agent/context/{ticker}."""
        response = await client.get("/api/v1/agent/context/AAPL")
        
        assert response.status_code == 200
        data = response.json()
        assert "ticker" in data or "score" in data or "signal" in str(data)
    
    @pytest.mark.asyncio
    async def test_health(self, client):
        """Test GET /agent/health."""
        response = await client.get("/api/v1/agent/health")
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data or "healthy" in data


# ═══════════════════════════════════════════════════════════════════════════
# Agent Status Endpoints
# ═══════════════════════════════════════════════════════════════════════════

class TestAgentStatusEndpoints:
    """Test agent status and control endpoints."""
    
    @pytest.mark.asyncio
    async def test_get_status(self, client):
        """Test GET /agent/status."""
        response = await client.get("/api/v1/agent/status")
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data or "agent_status" in data or "mode" in data
    
    @pytest.mark.asyncio
    async def test_get_settings(self, client):
        """Test agent settings are included in status."""
        response = await client.get("/api/v1/agent/status")
        
        assert response.status_code == 200
        data = response.json()
        assert "settings" in data or "mode" in data


# ═══════════════════════════════════════════════════════════════════════════
# Trading Endpoints
# ═══════════════════════════════════════════════════════════════════════════

class TestTradingEndpoints:
    """Test trading-related endpoints."""
    
    @pytest.mark.asyncio
    async def test_get_pending(self, client):
        """Test GET /agent/pending."""
        response = await client.get("/api/v1/agent/pending")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list) or "pending" in data or "trades" in data
    
    @pytest.mark.asyncio
    async def test_get_executions(self, client):
        """Test GET /agent/executions."""
        response = await client.get("/api/v1/agent/executions")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list) or "executions" in data


# ═══════════════════════════════════════════════════════════════════════════
# Decision Endpoints
# ═══════════════════════════════════════════════════════════════════════════

class TestDecisionEndpoints:
    """Test decision-related endpoints."""
    
    @pytest.mark.asyncio
    async def test_get_decisions(self, client):
        """Test GET /agent/decisions."""
        response = await client.get("/api/v1/agent/decisions")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list) or "decisions" in data
    
    @pytest.mark.asyncio
    async def test_get_history(self, client):
        """Test GET /agent/history."""
        response = await client.get("/api/v1/agent/history")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list) or "history" in data or "runs" in data


# ═══════════════════════════════════════════════════════════════════════════
# Learning Endpoints
# ═══════════════════════════════════════════════════════════════════════════

class TestLearningEndpoints:
    """Test learning-related endpoints."""
    
    @pytest.mark.asyncio
    async def test_get_lessons(self, client):
        """Test GET /agent/lessons."""
        response = await client.get("/api/v1/agent/lessons")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list) or "lessons" in data
    
    @pytest.mark.asyncio
    async def test_get_stats(self, client):
        """Test GET /agent/stats."""
        response = await client.get("/api/v1/agent/stats")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)


# ═══════════════════════════════════════════════════════════════════════════
# Training Endpoints
# ═══════════════════════════════════════════════════════════════════════════

class TestTrainingEndpoints:
    """Test training data endpoints."""
    
    @pytest.mark.asyncio
    async def test_get_training_stats(self, client):
        """Test GET /agent/training/stats."""
        response = await client.get("/api/v1/agent/training/stats")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
    
    @pytest.mark.asyncio
    async def test_get_training_decisions(self, client):
        """Test GET /agent/training/decisions."""
        response = await client.get("/api/v1/agent/training/decisions")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, (list, dict))


# ═══════════════════════════════════════════════════════════════════════════
# Error Handling
# ═══════════════════════════════════════════════════════════════════════════

class TestErrorHandling:
    """Test error handling for invalid requests."""
    
    @pytest.mark.asyncio
    async def test_invalid_ticker(self, client):
        """Test context with invalid ticker."""
        response = await client.get("/api/v1/agent/context/INVALID_TICKER_XYZ")
        
        # Should return 404 or empty response, not 500
        assert response.status_code in [200, 404, 422]
    
    @pytest.mark.asyncio
    async def test_approve_invalid_pending(self, client):
        """Test approve with invalid pending ID."""
        response = await client.post("/api/v1/agent/pending/nonexistent-id/approve")
        
        # Should handle gracefully - either error status or success=false in body
        if response.status_code == 200:
            data = response.json()
            assert data.get("success") is False or "not found" in str(data).lower() or "error" in str(data).lower()
        else:
            assert response.status_code in [400, 404, 422]
    
    @pytest.mark.asyncio
    async def test_reject_invalid_pending(self, client):
        """Test reject with invalid pending ID."""
        response = await client.post(
            "/api/v1/agent/pending/nonexistent-id/reject",
            json={"reason": "test"},
        )
        
        # Should return 404 or 400, not 500
        assert response.status_code in [400, 404, 422]
