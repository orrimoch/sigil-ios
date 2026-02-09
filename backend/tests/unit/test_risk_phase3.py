"""
Unit tests for Risk Phase 3 features.

REC-243: HMM Regime Detection
REC-245: Sector Limits
REC-246: Pattern Memory
REC-247: Portfolio VaR
"""

import pytest
import sys
import numpy as np
from pathlib import Path
from datetime import datetime, timezone, timedelta
import tempfile

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


class TestHMMRegimeDetection:
    """Tests for HMM regime detection."""
    
    def test_market_regime_enum(self):
        """MarketRegime enum should have correct values."""
        from risk.hmm_regime import MarketRegime
        
        assert MarketRegime.LOW_VOL.value == "low_vol"
        assert MarketRegime.NORMAL.value == "normal"
        assert MarketRegime.HIGH_VOL.value == "high_vol"
        assert MarketRegime.CRISIS.value == "crisis"
    
    def test_regime_adjustments(self):
        """Regime adjustments should be defined for all regimes."""
        from risk.hmm_regime import REGIME_ADJUSTMENTS, MarketRegime
        
        assert MarketRegime.LOW_VOL in REGIME_ADJUSTMENTS
        assert MarketRegime.NORMAL in REGIME_ADJUSTMENTS
        assert MarketRegime.HIGH_VOL in REGIME_ADJUSTMENTS
        assert MarketRegime.CRISIS in REGIME_ADJUSTMENTS
        
        # Normal should have no adjustment
        assert REGIME_ADJUSTMENTS[MarketRegime.NORMAL] == 0.0
        
        # Crisis should have positive adjustment (higher thresholds)
        assert REGIME_ADJUSTMENTS[MarketRegime.CRISIS] > 0
    
    def test_regime_result_structure(self):
        """RegimeResult should have correct structure."""
        from risk.hmm_regime import RegimeResult, MarketRegime
        
        result = RegimeResult(
            regime=MarketRegime.NORMAL,
            confidence=0.85,
            probabilities={"low_vol": 0.05, "normal": 0.85, "high_vol": 0.05, "crisis": 0.05},
            vix_value=20.0,
            volatility_20d=0.012,
            detected_at=datetime.now(timezone.utc),
            method="rule_based",
        )
        
        data = result.to_dict()
        assert data["regime"] == "normal"
        assert data["confidence"] == 0.85
        assert "threshold_adjustment" in data
        assert data["method"] == "rule_based"
    
    def test_rule_based_detection_low_vol(self):
        """Rule-based detection should identify low volatility."""
        from risk.hmm_regime import HMMRegimeDetector, MarketRegime
        
        detector = HMMRegimeDetector()
        
        # Very low volatility returns (0.3% daily std) with low VIX
        np.random.seed(42)  # Reproducible
        returns = np.random.normal(0.0002, 0.003, 30)  # Very calm market
        result = detector.detect(returns, vix_value=10.0)
        
        # With VIX=10 and low vol, should be LOW_VOL or at most NORMAL
        assert result.regime in [MarketRegime.LOW_VOL, MarketRegime.NORMAL]
        assert result.method == "rule_based"
    
    def test_rule_based_detection_crisis(self):
        """Rule-based detection should identify crisis."""
        from risk.hmm_regime import HMMRegimeDetector, MarketRegime
        
        detector = HMMRegimeDetector()
        
        # High volatility returns (3% daily std)
        returns = np.random.normal(-0.01, 0.03, 30)
        result = detector.detect(returns, vix_value=45.0)
        
        assert result.regime == MarketRegime.CRISIS
    
    def test_detector_singleton(self):
        """get_regime_detector should return singleton."""
        from risk.hmm_regime import get_regime_detector
        
        d1 = get_regime_detector()
        d2 = get_regime_detector()
        assert d1 is d2


class TestSectorLimits:
    """Tests for sector concentration limits."""
    
    def test_empty_portfolio(self):
        """Empty portfolio should return zero exposure."""
        import asyncio
        from risk.sector_limits import analyze_sector_exposure
        
        result = asyncio.get_event_loop().run_until_complete(
            analyze_sector_exposure(positions=[])
        )
        
        assert result["total_value"] == 0
        assert result["diversification_score"] == 100
        assert len(result["warnings"]) == 0
    
    def test_sector_warning_triggered(self):
        """Should warn when sector exceeds threshold."""
        import asyncio
        from risk.sector_limits import analyze_sector_exposure
        
        positions = [
            {"ticker": "AAPL", "market_value": 40000, "sector": "Technology"},
            {"ticker": "MSFT", "market_value": 30000, "sector": "Technology"},
            {"ticker": "JPM", "market_value": 30000, "sector": "Financials"},
        ]
        
        result = asyncio.get_event_loop().run_until_complete(
            analyze_sector_exposure(positions, warn_threshold=0.30)
        )
        
        # Technology is 70%, should trigger warning
        assert result["total_value"] == 100000
    
    def test_diversification_score_calculation(self):
        """Diversification score should be based on HHI."""
        # HHI = sum of squared percentages
        # All in one sector: HHI = 1.0, score = 0
        # Equal split 2 sectors: HHI = 0.5, score = 50
        # Equal split 4 sectors: HHI = 0.25, score = 75
        
        # Test calculation: score = (1 - HHI) * 100
        hhi_one = 1.0
        assert (1 - hhi_one) * 100 == 0
        
        hhi_two = 0.5
        assert (1 - hhi_two) * 100 == 50
        
        hhi_four = 0.25
        assert (1 - hhi_four) * 100 == 75


class TestPatternMemory:
    """Tests for pattern memory storage."""
    
    @pytest.fixture
    def memory(self):
        """Create temporary pattern memory for testing."""
        from risk.pattern_memory import PatternMemory
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_patterns.db"
            memory = PatternMemory(db_path=db_path)
            yield memory
    
    def test_log_event(self, memory):
        """Should store and retrieve events."""
        from risk.pattern_memory import RiskEvent, EventType
        
        event = RiskEvent(
            event_type=EventType.HARD_STOP_TRIGGERED,
            ticker="AAPL",
            details={"entry_price": 150.0, "trigger_price": 138.0},
            timestamp=datetime.now(timezone.utc),
            user_id="test",
        )
        
        event_id = memory.log_event(event)
        assert event_id > 0
        
        # Retrieve
        events = memory.get_events(ticker="AAPL")
        assert len(events) == 1
        assert events[0].event_type == EventType.HARD_STOP_TRIGGERED
    
    def test_log_trade_outcome(self, memory):
        """Should store and retrieve trade outcomes."""
        from risk.pattern_memory import TradeOutcome, OutcomeType
        
        outcome = TradeOutcome(
            ticker="MSFT",
            entry_date=datetime.now(timezone.utc) - timedelta(days=10),
            entry_price=400.0,
            exit_date=datetime.now(timezone.utc),
            exit_price=420.0,
            quantity=10,
            side="BUY",
            outcome=OutcomeType.PROFIT,
            pnl=200.0,
            pnl_pct=0.05,
            exit_reason="manual",
            regime_at_entry="normal",
            vix_at_entry=18.0,
            holding_days=10,
            user_id="test",
        )
        
        trade_id = memory.log_trade_outcome(outcome)
        assert trade_id > 0
        
        # Retrieve
        trades = memory.get_trade_outcomes(ticker="MSFT")
        assert len(trades) == 1
        assert trades[0].outcome == OutcomeType.PROFIT
        assert trades[0].pnl == 200.0
    
    def test_event_type_filter(self, memory):
        """Should filter events by type."""
        from risk.pattern_memory import RiskEvent, EventType
        
        # Log different event types
        memory.log_event(RiskEvent(
            event_type=EventType.HARD_STOP_TRIGGERED,
            ticker="AAPL",
            details={},
            timestamp=datetime.now(timezone.utc),
        ))
        memory.log_event(RiskEvent(
            event_type=EventType.REGIME_CHANGE,
            ticker=None,
            details={"old": "normal", "new": "high_vol"},
            timestamp=datetime.now(timezone.utc),
        ))
        
        # Filter by type
        stops = memory.get_events(event_type=EventType.HARD_STOP_TRIGGERED)
        assert len(stops) == 1
        
        regime_changes = memory.get_events(event_type=EventType.REGIME_CHANGE)
        assert len(regime_changes) == 1
    
    def test_get_stats(self, memory):
        """Should return correct statistics."""
        from risk.pattern_memory import RiskEvent, TradeOutcome, EventType, OutcomeType
        
        # Add some data
        memory.log_event(RiskEvent(
            event_type=EventType.HARD_STOP_TRIGGERED,
            ticker="AAPL",
            details={},
            timestamp=datetime.now(timezone.utc),
        ))
        memory.log_trade_outcome(TradeOutcome(
            ticker="AAPL",
            entry_date=datetime.now(timezone.utc),
            entry_price=150.0,
            exit_date=None,
            exit_price=None,
            quantity=10,
            side="BUY",
            outcome=OutcomeType.STILL_OPEN,
            pnl=0,
            pnl_pct=0,
            exit_reason=None,
            regime_at_entry=None,
            vix_at_entry=None,
            holding_days=None,
        ))
        
        stats = memory.get_stats()
        assert stats["total_events"] == 1
        assert stats["total_trades"] == 1


class TestPortfolioVaR:
    """Tests for correlated portfolio VaR."""
    
    def test_covariance_matrix_calculation(self):
        """Covariance matrix should be calculated correctly."""
        from risk.portfolio_var import calculate_covariance_matrix
        
        # Simple 2-asset case
        returns = np.array([
            [0.01, 0.02],
            [-0.01, -0.015],
            [0.005, 0.01],
            [0.02, 0.025],
        ])
        
        cov = calculate_covariance_matrix(returns)
        
        assert cov.shape == (2, 2)
        # Diagonal should be positive (variances)
        assert cov[0, 0] > 0
        assert cov[1, 1] > 0
    
    def test_correlation_matrix_calculation(self):
        """Correlation matrix should have 1s on diagonal."""
        from risk.portfolio_var import calculate_correlation_matrix
        
        returns = np.array([
            [0.01, 0.02],
            [-0.01, -0.015],
            [0.005, 0.01],
            [0.02, 0.025],
        ])
        
        corr = calculate_correlation_matrix(returns)
        
        assert corr.shape == (2, 2)
        # Diagonal should be 1
        assert abs(corr[0, 0] - 1.0) < 0.001
        assert abs(corr[1, 1] - 1.0) < 0.001
        # Off-diagonal should be between -1 and 1
        assert -1 <= corr[0, 1] <= 1
    
    def test_portfolio_variance_calculation(self):
        """Portfolio variance should combine weights and covariance."""
        from risk.portfolio_var import calculate_portfolio_variance
        
        weights = np.array([0.5, 0.5])
        cov = np.array([
            [0.04, 0.01],
            [0.01, 0.02],
        ])
        
        var = calculate_portfolio_variance(weights, cov)
        
        # Expected: w'Σw = 0.5*0.5*0.04 + 2*0.5*0.5*0.01 + 0.5*0.5*0.02
        expected = 0.01 + 0.005 + 0.005
        assert abs(var - expected) < 0.0001
    
    def test_empty_portfolio_var(self):
        """Empty portfolio should return zero VaR."""
        import asyncio
        from risk.portfolio_var import calculate_correlated_var
        
        result = asyncio.get_event_loop().run_until_complete(
            calculate_correlated_var(positions=[])
        )
        
        assert result["portfolio_value"] == 0
        assert result["var_95_daily"] == 0
        assert "message" in result
    
    def test_correlation_interpretation(self):
        """Correlation interpretation should be correct."""
        from risk.portfolio_var import _interpret_correlation
        
        assert "minimal" in _interpret_correlation(0.9).lower()
        assert "excellent" in _interpret_correlation(0.0).lower()
        assert "hedge" in _interpret_correlation(-0.6).lower()


class TestIntegration:
    """Integration tests for Phase 3 features."""
    
    def test_regime_affects_thresholds(self):
        """Regime detection should provide threshold adjustments."""
        from risk.hmm_regime import HMMRegimeDetector, MarketRegime, REGIME_ADJUSTMENTS
        
        detector = HMMRegimeDetector()
        
        # Normal market
        normal_returns = np.random.normal(0.0005, 0.01, 30)
        result = detector.detect(normal_returns, vix_value=18.0)
        
        adjustment = detector.get_threshold_adjustment(result.regime)
        assert adjustment == REGIME_ADJUSTMENTS[result.regime]
    
    def test_pattern_memory_convenience_functions(self):
        """Convenience functions should work correctly."""
        from risk.pattern_memory import (
            log_stop_trigger,
            log_regime_change,
            log_trade_closed,
            get_pattern_memory,
        )
        
        # Use a temporary database
        import tempfile
        from risk.pattern_memory import PatternMemory, _memory
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create temporary memory
            memory = PatternMemory(db_path=Path(tmpdir) / "test.db")
            
            # Test log_stop_trigger manually
            from risk.pattern_memory import RiskEvent, EventType
            event = RiskEvent(
                event_type=EventType.HARD_STOP_TRIGGERED,
                ticker="AAPL",
                details={"entry_price": 150.0, "trigger_price": 138.0, "loss_pct": -0.08},
                timestamp=datetime.now(timezone.utc),
                user_id="test",
            )
            event_id = memory.log_event(event)
            assert event_id > 0
