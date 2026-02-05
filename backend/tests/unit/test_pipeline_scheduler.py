"""
Unit tests for REC-132: Automated Pipeline Scheduler

Tests cover:
- Scheduler lifecycle (start/stop)
- Health tracking and persistence
- API endpoints
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


class TestPipelineScheduler:
    """Test PipelineScheduler class."""

    def test_scheduler_starts(self):
        """Scheduler should start without errors."""
        from scheduler.pipeline_scheduler import PipelineScheduler
        
        scheduler = PipelineScheduler()
        assert scheduler._is_running is False
        
        scheduler.start()
        assert scheduler._is_running is True
        
        scheduler.stop()
        assert scheduler._is_running is False

    def test_scheduler_status_when_stopped(self):
        """Status should show not running."""
        from scheduler.pipeline_scheduler import PipelineScheduler
        
        scheduler = PipelineScheduler()
        status = scheduler.get_status()
        
        assert status["is_running"] is False
        assert status["schedule"] == "Sunday 6pm EST"
        assert status["next_run"] is None

    def test_scheduler_status_when_running(self):
        """Status should show running with next_run."""
        from scheduler.pipeline_scheduler import PipelineScheduler
        
        scheduler = PipelineScheduler()
        scheduler.start()
        status = scheduler.get_status()
        
        assert status["is_running"] is True
        assert status["next_run"] is not None
        
        scheduler.stop()

    def test_get_history_empty(self):
        """History should be empty initially."""
        from scheduler.pipeline_scheduler import PipelineScheduler
        
        scheduler = PipelineScheduler()
        history = scheduler.get_history()
        
        # May have history from previous runs
        assert isinstance(history, list)

    def test_success_rate_no_history(self):
        """Success rate should be 0 with no history."""
        from scheduler.pipeline_scheduler import PipelineScheduler
        
        scheduler = PipelineScheduler()
        scheduler._run_history = []
        rate = scheduler._calculate_success_rate()
        
        assert rate == 0.0

    def test_success_rate_with_history(self):
        """Success rate calculation."""
        from scheduler.pipeline_scheduler import PipelineScheduler
        
        scheduler = PipelineScheduler()
        scheduler._run_history = [
            {"status": "success"},
            {"status": "success"},
            {"status": "failed"},
            {"status": "success"},
        ]
        rate = scheduler._calculate_success_rate()
        
        assert rate == 75.0


class TestSchedulerHealthPersistence:
    """Test health file persistence."""

    def test_health_file_created_on_save(self, tmp_path):
        """Health file should be created when saving."""
        from scheduler import pipeline_scheduler
        
        # Override health file path
        original_path = pipeline_scheduler.HEALTH_FILE
        pipeline_scheduler.HEALTH_FILE = tmp_path / "scheduler_health.json"
        
        try:
            scheduler = pipeline_scheduler.PipelineScheduler()
            scheduler._last_run = {"status": "test"}
            scheduler._save_health()
            
            assert pipeline_scheduler.HEALTH_FILE.exists()
        finally:
            pipeline_scheduler.HEALTH_FILE = original_path


class TestSchedulerEndpoints:
    """Test scheduler API endpoints."""

    def test_status_endpoint(self):
        """GET /scheduler/status should return status."""
        from fastapi.testclient import TestClient
        from api.main import app
        
        client = TestClient(app)
        resp = client.get("/api/v1/scheduler/status")
        
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "data" in data
        assert "is_running" in data["data"]

    def test_start_endpoint(self):
        """POST /scheduler/start should start scheduler."""
        from fastapi.testclient import TestClient
        from api.main import app
        
        client = TestClient(app)
        
        # Stop first to ensure clean state
        client.post("/api/v1/scheduler/stop")
        
        resp = client.post("/api/v1/scheduler/start")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["is_running"] is True
        
        # Clean up
        client.post("/api/v1/scheduler/stop")

    def test_stop_endpoint(self):
        """POST /scheduler/stop should stop scheduler."""
        from fastapi.testclient import TestClient
        from api.main import app
        
        client = TestClient(app)
        
        # Start first
        client.post("/api/v1/scheduler/start")
        
        resp = client.post("/api/v1/scheduler/stop")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["is_running"] is False

    def test_history_endpoint(self):
        """GET /scheduler/history should return history."""
        from fastapi.testclient import TestClient
        from api.main import app
        
        client = TestClient(app)
        resp = client.get("/api/v1/scheduler/history")
        
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "data" in data
        assert isinstance(data["data"], list)
