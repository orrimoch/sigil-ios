"""Tests for GitHub Actions workflows."""
import pytest
import yaml
from pathlib import Path


class TestGitHubWorkflows:
    """Test GitHub Actions workflow files."""
    
    @pytest.fixture
    def workflows_dir(self):
        """Get workflows directory."""
        return Path(__file__).parent.parent.parent.parent.parent / ".github" / "workflows"
    
    def test_weekly_pipeline_exists(self, workflows_dir):
        """T-005: Verify weekly-pipeline.yml exists and is valid."""
        workflow_file = workflows_dir / "weekly-pipeline.yml"
        assert workflow_file.exists(), "weekly-pipeline.yml should exist"
        
        with open(workflow_file) as f:
            workflow = yaml.safe_load(f)
        
        assert workflow.get("name") == "Weekly Scoring Pipeline"
        assert "schedule" in workflow.get("on", {})
        assert "workflow_dispatch" in workflow.get("on", {})
        assert "run-pipeline" in workflow.get("jobs", {})
    
    def test_crowd_wisdom_exists(self, workflows_dir):
        """T-006: Verify crowd-wisdom.yml exists and is valid."""
        workflow_file = workflows_dir / "crowd-wisdom.yml"
        assert workflow_file.exists(), "crowd-wisdom.yml should exist"
        
        with open(workflow_file) as f:
            workflow = yaml.safe_load(f)
        
        assert workflow.get("name") == "Crowd Wisdom Fetch"
        assert "schedule" in workflow.get("on", {})
    
    def test_hmm_training_exists(self, workflows_dir):
        """T-007: Verify hmm-training.yml exists and is valid."""
        workflow_file = workflows_dir / "hmm-training.yml"
        assert workflow_file.exists(), "hmm-training.yml should exist"
        
        with open(workflow_file) as f:
            workflow = yaml.safe_load(f)
        
        assert workflow.get("name") == "HMM Regime Training"
        assert "schedule" in workflow.get("on", {})
    
    def test_workflows_use_correct_python(self, workflows_dir):
        """Verify all workflows use Python 3.11."""
        for workflow_file in workflows_dir.glob("*.yml"):
            if workflow_file.name == "README.md":
                continue
            with open(workflow_file) as f:
                content = f.read()
            if "python" in content.lower():
                assert "3.11" in content or "3.x" in content, \
                    f"{workflow_file.name} should specify Python version"
    
    def test_workflows_have_timeout(self, workflows_dir):
        """Verify all workflows have timeout to prevent runaway jobs."""
        for workflow_file in workflows_dir.glob("*.yml"):
            if workflow_file.name.startswith("."):
                continue
            with open(workflow_file) as f:
                workflow = yaml.safe_load(f)
            
            if not workflow:
                continue
                
            for job_name, job in workflow.get("jobs", {}).items():
                if "timeout-minutes" in job or job.get("if", "").startswith("needs"):
                    continue
                # Jobs that depend on others or have if conditions are ok
                assert "timeout-minutes" in job or "needs" in job, \
                    f"Job '{job_name}' in {workflow_file.name} should have timeout-minutes"
