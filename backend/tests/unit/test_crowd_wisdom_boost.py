"""
Tests for REC-263: Crowd Wisdom Score Boost Integration
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from scoring.composite_score import (
    get_crowd_wisdom_boost,
    CROWD_WISDOM_CONFIG,
)


class TestCrowdWisdomBoost:
    """Tests for crowd wisdom score boost calculation."""
    
    def test_boost_high_viral_score(self):
        """High viral score (>70) should get positive boost."""
        # Viral score of 100 should get max boost
        boost = get_crowd_wisdom_boost(100)
        assert boost == CROWD_WISDOM_CONFIG["max_boost"]
        
        # Viral score of 85 (halfway between 70 and 100) should get ~5 boost
        boost = get_crowd_wisdom_boost(85)
        assert 4 <= boost <= 6
        
        # Viral score of 70 should get minimal boost
        boost = get_crowd_wisdom_boost(70)
        assert boost >= 0
    
    def test_penalty_low_viral_score(self):
        """Low viral score (<30) should get penalty if in CW data."""
        # Viral score of 0 should get max penalty
        # But 0 means not in CW data, so no penalty
        boost = get_crowd_wisdom_boost(0)
        assert boost == 0
        
        # Viral score of 10 should get penalty
        boost = get_crowd_wisdom_boost(10)
        assert boost < 0
        assert boost >= -CROWD_WISDOM_CONFIG["max_penalty"]
        
        # Viral score of 29 should get minimal penalty
        boost = get_crowd_wisdom_boost(29)
        assert boost < 0
    
    def test_neutral_viral_score(self):
        """Viral scores between 30-70 should get no adjustment."""
        for score in [30, 40, 50, 60, 69]:
            boost = get_crowd_wisdom_boost(score)
            assert boost == 0, f"Score {score} should have no boost, got {boost}"
    
    def test_boost_is_linear(self):
        """Boost should increase linearly with viral score above threshold."""
        boost_75 = get_crowd_wisdom_boost(75)
        boost_85 = get_crowd_wisdom_boost(85)
        boost_95 = get_crowd_wisdom_boost(95)
        
        # Should be roughly linear
        assert boost_85 > boost_75
        assert boost_95 > boost_85
    
    def test_boost_capped_at_max(self):
        """Boost should never exceed max_boost."""
        # Even extremely high viral scores
        boost = get_crowd_wisdom_boost(150)  # Invalid but test anyway
        assert boost <= CROWD_WISDOM_CONFIG["max_boost"]
    
    def test_penalty_capped_at_max(self):
        """Penalty should never exceed max_penalty."""
        boost = get_crowd_wisdom_boost(1)
        assert abs(boost) <= CROWD_WISDOM_CONFIG["max_penalty"]


class TestCrowdWisdomConfig:
    """Tests for crowd wisdom configuration."""
    
    def test_config_has_required_keys(self):
        """Config should have all required keys."""
        required_keys = [
            "enabled",
            "boost_threshold",
            "penalty_threshold",
            "max_boost",
            "max_penalty",
        ]
        for key in required_keys:
            assert key in CROWD_WISDOM_CONFIG, f"Missing config key: {key}"
    
    def test_config_values_are_sensible(self):
        """Config values should be within reasonable ranges."""
        assert 50 <= CROWD_WISDOM_CONFIG["boost_threshold"] <= 90
        assert 10 <= CROWD_WISDOM_CONFIG["penalty_threshold"] <= 50
        assert 0 < CROWD_WISDOM_CONFIG["max_boost"] <= 15
        assert 0 < CROWD_WISDOM_CONFIG["max_penalty"] <= 10
