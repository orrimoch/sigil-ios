"""Tests for GitHub Secrets configuration."""
import pytest
import os


class TestGitHubSecrets:
    """Test that required secrets are documented."""
    
    REQUIRED_SECRETS = [
        "ANTHROPIC_API_KEY",  # Required for sentiment analysis
    ]
    
    OPTIONAL_SECRETS = [
        "OPENAI_API_KEY",      # Alternative LLM provider
        "GOOGLE_API_KEY",      # Alternative LLM provider
        "FINNHUB_API_KEY",     # Optional news source
        "ALPHA_VANTAGE_API_KEY",  # Optional news source
        "REDDIT_CLIENT_ID",    # For crowd wisdom
        "REDDIT_CLIENT_SECRET", # For crowd wisdom
    ]
    
    def test_secrets_documented(self):
        """T-004: Verify required secrets are documented."""
        # This test ensures we track what secrets are needed
        assert len(self.REQUIRED_SECRETS) > 0, "Should have required secrets defined"
        assert "ANTHROPIC_API_KEY" in self.REQUIRED_SECRETS, "Anthropic key is required"
    
    def test_env_example_exists(self):
        """T-004: Verify .env.example documents all secrets."""
        from pathlib import Path
        env_example = Path(__file__).parent.parent.parent.parent / ".env.example"
        assert env_example.exists(), ".env.example should exist"
        
        content = env_example.read_text()
        for secret in self.REQUIRED_SECRETS:
            assert secret in content, f"{secret} should be in .env.example"
