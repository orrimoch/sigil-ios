"""
Unit tests for F12.5 IC Decay Analyzer (ic_decay.py)
"""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime, timedelta

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from backtest.ic_decay import (
    ICDecayAnalyzer,
    ICDecayResult,
    RollingICResult,
)
from backtest.data_store import (
    BacktestDataStore,
    HistoricalScore,
)


@pytest.fixture
def temp_store():
    """Create a temporary data store with sample scores."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = BacktestDataStore(data_dir=Path(tmpdir))
        
        # Add sample scores for a few weeks
        scores = []
        base_date = datetime(2025, 1, 6)  # Monday
        
        tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "JPM", "JNJ", "XOM",
                   "PG", "UNH", "V", "HD", "MA", "DIS", "PYPL", "ADBE", "NFLX", "CRM"]
        
        for week in range(8):
            date = (base_date + timedelta(weeks=week)).strftime("%Y-%m-%d")
            
            for i, ticker in enumerate(tickers):
                # Create scores with some variation
                base_score = 50 + (i % 10) * 5 + (week % 3) * 2
                
                scores.append(HistoricalScore(
                    date=date,
                    ticker=ticker,
                    composite_score=base_score,
                    signal="BUY" if base_score >= 70 else "HOLD" if base_score >= 40 else "SELL",
                    fundamental_score=base_score + 5,
                    sentiment_score=50,
                    technical_score=base_score - 5,
                    macro_score=50,
                    sector="Technology" if i < 10 else "Other",
                ))
        
        store.save_historical_scores(scores)
        yield store


class TestICDecayAnalyzer:
    """Tests for IC decay analysis."""
    
    def test_analyzer_creation(self, temp_store):
        """Test creating an analyzer."""
        analyzer = ICDecayAnalyzer(data_store=temp_store)
        assert analyzer is not None
    
    def test_empty_analysis(self, temp_store):
        """Test analysis with no data in range."""
        analyzer = ICDecayAnalyzer(data_store=temp_store)
        
        result = analyzer.analyze_ic_decay(
            start_date="2020-01-01",
            end_date="2020-12-31"
        )
        
        assert result.weeks_analyzed == 0
        assert result.recommended_refresh_freq == "weekly"
    
    def test_ic_by_day_structure(self, temp_store):
        """Test IC by day has correct structure."""
        analyzer = ICDecayAnalyzer(data_store=temp_store)
        
        result = analyzer.analyze_ic_decay(
            start_date="2025-01-01",
            end_date="2025-03-01"
        )
        
        # Should have 5 days
        assert len(result.ic_by_day) == 5
        assert 1 in result.ic_by_day
        assert 5 in result.ic_by_day
        
        # Should have corresponding std and count
        assert len(result.ic_by_day_std) == 5
        assert len(result.ic_by_day_count) == 5


class TestICDecayResult:
    """Tests for ICDecayResult dataclass."""
    
    def test_to_dict(self):
        """Test converting result to dict."""
        result = ICDecayResult(
            ic_by_day={1: 0.08, 2: 0.06, 3: 0.05, 4: 0.04, 5: 0.03},
            ic_by_day_std={1: 0.02, 2: 0.02, 3: 0.02, 4: 0.02, 5: 0.02},
            ic_by_day_count={1: 10, 2: 10, 3: 10, 4: 10, 5: 10},
            ic_t_stats={1: 2.5, 2: 2.0, 3: 1.5, 4: 1.0, 5: 0.5},
            ic_p_values={1: 0.01, 2: 0.03, 3: 0.07, 4: 0.15, 5: 0.30},
            decay_rate=0.0125,
            half_life_days=3.2,
            recommended_refresh_freq="mid-week",
            refresh_reason="IC drops below threshold after day 3",
            start_date="2025-01-01",
            end_date="2025-03-01",
            weeks_analyzed=8,
        )
        
        d = result.to_dict()
        
        assert d["decay_rate"] == 0.0125
        assert d["half_life_days"] == 3.2
        assert d["recommended_refresh_freq"] == "mid-week"
        assert 1 in d["ic_by_day"]


class TestRollingICResult:
    """Tests for RollingICResult dataclass."""
    
    def test_to_dict(self):
        """Test converting rolling IC result to dict."""
        result = RollingICResult(
            dates=["2025-01-06", "2025-01-13", "2025-01-20"],
            ic_values=[0.05, 0.06, 0.07],
            ic_moving_avg=[0.05, 0.055, 0.06],
            trend="improving",
            trend_slope=0.01,
        )
        
        d = result.to_dict()
        
        assert len(d["dates"]) == 3
        assert d["trend"] == "improving"
        assert d["trend_slope"] == 0.01


class TestDecayMetrics:
    """Tests for decay calculation methods."""
    
    def test_decay_rate_positive(self):
        """Test decay rate calculation with declining IC."""
        analyzer = ICDecayAnalyzer()
        
        ic_by_day = {1: 0.10, 2: 0.08, 3: 0.06, 4: 0.04, 5: 0.02}
        
        decay_rate, half_life = analyzer._calculate_decay_metrics(ic_by_day)
        
        # IC drops from 0.10 to 0.02 over 4 days = 0.02 per day
        assert decay_rate == 0.02
        # Half of 0.10 is 0.05, at 0.02/day takes 2.5 days
        assert half_life == 2.5
    
    def test_decay_rate_flat(self):
        """Test decay rate with flat IC."""
        analyzer = ICDecayAnalyzer()
        
        ic_by_day = {1: 0.05, 2: 0.05, 3: 0.05, 4: 0.05, 5: 0.05}
        
        decay_rate, half_life = analyzer._calculate_decay_metrics(ic_by_day)
        
        assert decay_rate == 0
        assert half_life == float('inf')


class TestRefreshRecommendation:
    """Tests for refresh frequency recommendation."""
    
    def test_daily_recommendation(self):
        """Test daily recommendation for fast decay."""
        analyzer = ICDecayAnalyzer()
        
        ic_by_day = {1: 0.06, 2: 0.02, 3: 0.01, 4: 0.005, 5: 0.001}
        p_values = {1: 0.01, 2: 0.10, 3: 0.30, 4: 0.50, 5: 0.80}
        
        freq, reason = analyzer._recommend_refresh_frequency(ic_by_day, p_values)
        
        assert freq == "daily"
    
    def test_weekly_recommendation(self):
        """Test weekly recommendation for slow decay."""
        analyzer = ICDecayAnalyzer()
        
        ic_by_day = {1: 0.08, 2: 0.07, 3: 0.06, 4: 0.05, 5: 0.04}
        p_values = {1: 0.001, 2: 0.005, 3: 0.01, 4: 0.02, 5: 0.03}
        
        freq, reason = analyzer._recommend_refresh_frequency(ic_by_day, p_values)
        
        assert freq == "weekly"


class TestHelperMethods:
    """Tests for helper methods."""
    
    def test_add_trading_days(self):
        """Test adding trading days."""
        analyzer = ICDecayAnalyzer()
        
        # Friday + 1 trading day = Monday
        result = analyzer._add_trading_days("2025-01-03", 1)
        assert result == "2025-01-06"
        
        # Monday + 5 trading days = Monday
        result = analyzer._add_trading_days("2025-01-06", 5)
        assert result == "2025-01-13"
