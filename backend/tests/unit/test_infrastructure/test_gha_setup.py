"""Tests for GitHub Actions infrastructure setup."""
import os
import pytest
from pathlib import Path


class TestGitHubActionsSetup:
    """Test GitHub Actions directory structure."""
    
    @pytest.fixture
    def project_root(self):
        """Get project root directory."""
        return Path(__file__).parent.parent.parent.parent.parent
    
    def test_workflows_directory_exists(self, project_root):
        """REC-273: Verify .github/workflows directory exists."""
        workflows_dir = project_root / ".github" / "workflows"
        assert workflows_dir.exists(), f"Workflows directory not found at {workflows_dir}"
        assert workflows_dir.is_dir(), "Workflows path is not a directory"
    
    def test_workflows_readme_exists(self, project_root):
        """REC-273: Verify workflows README exists."""
        readme = project_root / ".github" / "workflows" / "README.md"
        assert readme.exists(), "Workflows README.md not found"
        content = readme.read_text()
        assert "Sigil" in content, "README should mention Sigil"
        assert "weekly-pipeline" in content, "README should document weekly-pipeline"
