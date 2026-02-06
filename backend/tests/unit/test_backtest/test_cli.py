"""
Unit tests for Backtest CLI (__main__.py)
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
from io import StringIO

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from backtest.__main__ import main, cmd_stats, cmd_list


class TestCLIHelp:
    """Tests for CLI help and argument parsing."""
    
    def test_main_no_args(self):
        """Test main with no arguments shows help."""
        with patch('sys.argv', ['backtest']):
            result = main()
            assert result == 0
    
    def test_help_flag(self):
        """Test --help flag."""
        with patch('sys.argv', ['backtest', '--help']):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0


class TestCLICommands:
    """Tests for CLI commands."""
    
    def test_stats_command(self, capsys):
        """Test stats command runs."""
        args = MagicMock()
        result = cmd_stats(args)
        
        assert result == 0
        
        captured = capsys.readouterr()
        assert "BACKTEST STORAGE STATISTICS" in captured.out
    
    def test_list_command(self, capsys):
        """Test list command runs."""
        args = MagicMock()
        args.limit = 10
        
        result = cmd_list(args)
        
        assert result == 0


class TestCLIArgumentParsing:
    """Tests for argument parsing."""
    
    def test_run_default_args(self):
        """Test run command has correct defaults."""
        with patch('sys.argv', ['backtest', 'run', '--help']):
            with pytest.raises(SystemExit):
                main()
    
    def test_optimize_default_args(self):
        """Test optimize command has correct defaults."""
        with patch('sys.argv', ['backtest', 'optimize', '--help']):
            with pytest.raises(SystemExit):
                main()


class TestCLIOutputFormat:
    """Tests for CLI output formatting."""
    
    def test_stats_output_format(self, capsys):
        """Test stats output has expected sections."""
        args = MagicMock()
        cmd_stats(args)
        
        captured = capsys.readouterr()
        
        assert "Historical Scores:" in captured.out
        assert "Backtests:" in captured.out
        assert "Data Directory:" in captured.out
    
    def test_list_output_format(self, capsys):
        """Test list output has expected columns."""
        args = MagicMock()
        args.limit = 5
        
        cmd_list(args)
        
        captured = capsys.readouterr()
        
        # Should have header
        assert "ID" in captured.out
        assert "Status" in captured.out
