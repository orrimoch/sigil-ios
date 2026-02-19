"""
Tests for operational stability scripts (REC-320).
Tests script existence, permissions, and basic functionality.
"""

import os
import subprocess
import pytest
from pathlib import Path
from datetime import datetime

SCRIPTS_DIR = Path(__file__).parent.parent.parent / "scripts"
DATA_DIR = Path(__file__).parent.parent.parent / "data"
BACKUP_DIR = Path(__file__).parent.parent.parent / "backups"


class TestScriptExistence:
    """Verify all required scripts exist and are executable."""
    
    REQUIRED_SCRIPTS = [
        "start_backend.sh",
        "stop_backend.sh",
        "backup_databases.sh",
        "health_monitor.sh",
    ]
    
    @pytest.mark.parametrize("script_name", REQUIRED_SCRIPTS)
    def test_script_exists(self, script_name: str):
        """Each operational script should exist."""
        script_path = SCRIPTS_DIR / script_name
        assert script_path.exists(), f"Script {script_name} not found at {script_path}"
    
    @pytest.mark.parametrize("script_name", REQUIRED_SCRIPTS)
    def test_script_executable(self, script_name: str):
        """Each script should have executable permissions."""
        script_path = SCRIPTS_DIR / script_name
        assert os.access(script_path, os.X_OK), f"Script {script_name} is not executable"
    
    @pytest.mark.parametrize("script_name", REQUIRED_SCRIPTS)
    def test_script_has_shebang(self, script_name: str):
        """Each script should start with a proper shebang."""
        script_path = SCRIPTS_DIR / script_name
        with open(script_path, 'r') as f:
            first_line = f.readline().strip()
        assert first_line.startswith("#!/bin/bash"), f"Script {script_name} missing bash shebang"


class TestLaunchAgent:
    """Verify LaunchAgent configuration."""
    
    PLIST_PATH = Path.home() / "Library/LaunchAgents/com.sigil.backend.plist"
    
    def test_plist_exists(self):
        """LaunchAgent plist should exist."""
        assert self.PLIST_PATH.exists(), f"LaunchAgent not found at {self.PLIST_PATH}"
    
    def test_plist_valid_xml(self):
        """LaunchAgent plist should be valid XML."""
        result = subprocess.run(
            ["plutil", "-lint", str(self.PLIST_PATH)],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"Invalid plist: {result.stderr}"
    
    def test_plist_references_start_script(self):
        """LaunchAgent should reference start_backend.sh."""
        with open(self.PLIST_PATH, 'r') as f:
            content = f.read()
        assert "start_backend.sh" in content, "LaunchAgent doesn't reference start_backend.sh"


class TestBackupScript:
    """Test backup script functionality."""
    
    def test_backup_script_syntax(self):
        """Backup script should have valid bash syntax."""
        script_path = SCRIPTS_DIR / "backup_databases.sh"
        result = subprocess.run(
            ["bash", "-n", str(script_path)],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"Syntax error in backup script: {result.stderr}"
    
    def test_backup_creates_directory(self, tmp_path: Path):
        """Backup script should create backup directory if missing."""
        # This is a unit test - we verify the mkdir -p logic exists in script
        script_path = SCRIPTS_DIR / "backup_databases.sh"
        with open(script_path, 'r') as f:
            content = f.read()
        assert 'mkdir -p' in content, "Backup script should create directories"
    
    def test_backup_handles_all_databases(self):
        """Backup script should handle all database files."""
        script_path = SCRIPTS_DIR / "backup_databases.sh"
        with open(script_path, 'r') as f:
            content = f.read()
        
        expected_dbs = [
            "agent_memory.db",
            "scores.db",
            "sigil.db",
            "trading.db",
            "pipeline.db",
        ]
        for db in expected_dbs:
            assert db in content, f"Backup script should handle {db}"
    
    def test_backup_has_retention_policy(self):
        """Backup script should implement retention cleanup."""
        script_path = SCRIPTS_DIR / "backup_databases.sh"
        with open(script_path, 'r') as f:
            content = f.read()
        assert 'RETENTION_DAYS' in content, "Backup script should have retention policy"
        assert 'find' in content and '-mtime' in content, "Backup script should clean old backups"


class TestHealthMonitor:
    """Test health monitor script."""
    
    def test_health_monitor_syntax(self):
        """Health monitor should have valid bash syntax."""
        script_path = SCRIPTS_DIR / "health_monitor.sh"
        result = subprocess.run(
            ["bash", "-n", str(script_path)],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"Syntax error in health monitor: {result.stderr}"
    
    def test_health_monitor_checks_health_endpoint(self):
        """Health monitor should check the /health endpoint."""
        script_path = SCRIPTS_DIR / "health_monitor.sh"
        with open(script_path, 'r') as f:
            content = f.read()
        assert '/api/v1/health' in content, "Should check health endpoint"
    
    def test_health_monitor_has_retry_logic(self):
        """Health monitor should retry before giving up."""
        script_path = SCRIPTS_DIR / "health_monitor.sh"
        with open(script_path, 'r') as f:
            content = f.read()
        assert 'MAX_RETRIES' in content, "Should have retry configuration"
        assert 'for' in content or 'while' in content, "Should have retry loop"
    
    def test_health_monitor_calls_restart_scripts(self):
        """Health monitor should use start/stop scripts."""
        script_path = SCRIPTS_DIR / "health_monitor.sh"
        with open(script_path, 'r') as f:
            content = f.read()
        assert 'stop_backend.sh' in content, "Should call stop script"
        assert 'start_backend.sh' in content, "Should call start script"


class TestStartStopScripts:
    """Test start and stop scripts."""
    
    def test_start_script_syntax(self):
        """Start script should have valid bash syntax."""
        script_path = SCRIPTS_DIR / "start_backend.sh"
        result = subprocess.run(
            ["bash", "-n", str(script_path)],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"Syntax error in start script: {result.stderr}"
    
    def test_stop_script_syntax(self):
        """Stop script should have valid bash syntax."""
        script_path = SCRIPTS_DIR / "stop_backend.sh"
        result = subprocess.run(
            ["bash", "-n", str(script_path)],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"Syntax error in stop script: {result.stderr}"
    
    def test_start_script_uses_pid_file(self):
        """Start script should track PID for clean shutdown."""
        script_path = SCRIPTS_DIR / "start_backend.sh"
        with open(script_path, 'r') as f:
            content = f.read()
        assert 'PID_FILE' in content, "Should use PID file"
        assert '/tmp/' in content, "PID file should be in /tmp"
    
    def test_start_script_verifies_startup(self):
        """Start script should verify backend started successfully."""
        script_path = SCRIPTS_DIR / "start_backend.sh"
        with open(script_path, 'r') as f:
            content = f.read()
        assert 'curl' in content, "Should verify with curl"
        assert '/health' in content, "Should check health endpoint"
    
    def test_stop_script_handles_missing_pid(self):
        """Stop script should handle missing PID file gracefully."""
        script_path = SCRIPTS_DIR / "stop_backend.sh"
        with open(script_path, 'r') as f:
            content = f.read()
        assert 'if' in content and 'PID_FILE' in content, "Should check if PID file exists"
        assert 'pkill' in content, "Should have fallback pkill"


class TestDatabasesExist:
    """Verify databases that backup script expects exist."""
    
    CRITICAL_DBS = ["scores.db", "sigil.db", "trading.db"]
    
    @pytest.mark.parametrize("db_name", CRITICAL_DBS)
    def test_critical_database_exists(self, db_name: str):
        """Critical databases should exist for backup."""
        db_path = DATA_DIR / db_name
        assert db_path.exists(), f"Critical database {db_name} not found"
