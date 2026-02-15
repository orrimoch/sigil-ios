"""Tests for CLI entry point."""
import pytest
import subprocess
import sys
from pathlib import Path


class TestCLI:
    """Test CLI commands."""
    
    @pytest.fixture
    def cli_module(self):
        """Get CLI module path."""
        return "src.cli.run_pipeline"
    
    def test_cli_help(self, cli_module):
        """REC-275: Verify CLI --help works."""
        result = subprocess.run(
            [sys.executable, "-m", cli_module, "--help"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent.parent
        )
        assert result.returncode == 0
        assert "Sigil Data Pipeline CLI" in result.stdout
        assert "full" in result.stdout
        assert "scores-only" in result.stdout
        assert "crowd-wisdom" in result.stdout
        assert "train-hmm" in result.stdout
        assert "validate" in result.stdout
    
    def test_cli_validate(self, cli_module):
        """REC-275: Verify validate command works."""
        result = subprocess.run(
            [sys.executable, "-m", cli_module, "validate"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent.parent
        )
        assert result.returncode == 0
        assert "Validation passed" in result.stdout
    
    def test_cli_invalid_command(self, cli_module):
        """REC-275: Verify invalid command fails gracefully."""
        result = subprocess.run(
            [sys.executable, "-m", cli_module, "invalid-command"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent.parent
        )
        assert result.returncode != 0
    
    def test_cli_module_exists(self):
        """REC-275: Verify CLI module structure."""
        cli_dir = Path(__file__).parent.parent.parent.parent / "src" / "cli"
        assert cli_dir.exists(), "CLI directory should exist"
        assert (cli_dir / "__init__.py").exists(), "CLI __init__.py should exist"
        assert (cli_dir / "run_pipeline.py").exists(), "run_pipeline.py should exist"
        assert (cli_dir / "__main__.py").exists(), "__main__.py should exist"
