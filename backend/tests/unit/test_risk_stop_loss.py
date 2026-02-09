"""
Unit tests for Risk Module Stop-Loss Logic

REC-217: Hard Stop-Loss Logic
REC-218: Trailing Stop-Loss Logic
REC-220: High-Water-Mark Tracking
"""

import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from risk.stop_loss import (
    check_hard_stop,
    check_trailing_stop,
    calculate_stop_price,
    calculate_trailing_stop_price,
    check_stop_with_details,
    update_high_water_mark,
)


class TestCheckHardStop:
    """Tests for check_hard_stop function (REC-217)."""
    
    def test_not_triggered_above_threshold(self):
        """Should NOT trigger when loss is above threshold."""
        # Entry $100, current $93 = -7% (threshold -8%)
        assert check_hard_stop(100.0, 93.0, -0.08) is False
        
        # Entry $100, current $95 = -5%
        assert check_hard_stop(100.0, 95.0, -0.08) is False
        
        # Entry $100, current $100 = 0%
        assert check_hard_stop(100.0, 100.0, -0.08) is False
        
        # Entry $100, current $110 = +10%
        assert check_hard_stop(100.0, 110.0, -0.08) is False
    
    def test_triggered_at_threshold(self):
        """Should trigger when loss equals threshold."""
        # Entry $100, current $92 = exactly -8%
        assert check_hard_stop(100.0, 92.0, -0.08) is True
    
    def test_triggered_below_threshold(self):
        """Should trigger when loss exceeds threshold."""
        # Entry $100, current $91 = -9%
        assert check_hard_stop(100.0, 91.0, -0.08) is True
        
        # Entry $100, current $80 = -20%
        assert check_hard_stop(100.0, 80.0, -0.08) is True
        
        # Entry $100, current $50 = -50%
        assert check_hard_stop(100.0, 50.0, -0.08) is True
    
    def test_various_thresholds(self):
        """Should respect different threshold values."""
        # -5% threshold
        assert check_hard_stop(100.0, 95.5, -0.05) is False
        assert check_hard_stop(100.0, 95.0, -0.05) is True
        assert check_hard_stop(100.0, 94.0, -0.05) is True
        
        # -10% threshold
        assert check_hard_stop(100.0, 91.0, -0.10) is False
        assert check_hard_stop(100.0, 90.0, -0.10) is True
        
        # -20% threshold
        assert check_hard_stop(100.0, 81.0, -0.20) is False
        assert check_hard_stop(100.0, 80.0, -0.20) is True
    
    def test_positive_threshold_converted(self):
        """Should convert positive threshold to negative."""
        # 0.08 should be treated as -0.08
        assert check_hard_stop(100.0, 93.0, 0.08) is False
        assert check_hard_stop(100.0, 92.0, 0.08) is True
    
    def test_invalid_entry_price(self):
        """Should raise error for invalid entry price."""
        with pytest.raises(ValueError):
            check_hard_stop(0.0, 92.0, -0.08)
        
        with pytest.raises(ValueError):
            check_hard_stop(-100.0, 92.0, -0.08)
    
    def test_invalid_current_price(self):
        """Should raise error for negative current price."""
        with pytest.raises(ValueError):
            check_hard_stop(100.0, -10.0, -0.08)


class TestCheckTrailingStop:
    """Tests for check_trailing_stop function (REC-218)."""
    
    def test_not_triggered_above_distance(self):
        """Should NOT trigger when drawdown is above distance."""
        # Peak $100, current $91 = -9% (distance -10%)
        assert check_trailing_stop(91.0, 100.0, -0.10) is False
        
        # Peak $100, current $95 = -5%
        assert check_trailing_stop(95.0, 100.0, -0.10) is False
        
        # Peak $100, current $100 = 0%
        assert check_trailing_stop(100.0, 100.0, -0.10) is False
    
    def test_triggered_at_distance(self):
        """Should trigger when drawdown equals distance."""
        # Peak $100, current $90 = exactly -10%
        assert check_trailing_stop(90.0, 100.0, -0.10) is True
    
    def test_triggered_below_distance(self):
        """Should trigger when drawdown exceeds distance."""
        # Peak $100, current $89 = -11%
        assert check_trailing_stop(89.0, 100.0, -0.10) is True
        
        # Peak $100, current $80 = -20%
        assert check_trailing_stop(80.0, 100.0, -0.10) is True
    
    def test_various_distances(self):
        """Should respect different distance values."""
        # -5% distance
        assert check_trailing_stop(96.0, 100.0, -0.05) is False
        assert check_trailing_stop(95.0, 100.0, -0.05) is True
        
        # -15% distance
        assert check_trailing_stop(86.0, 100.0, -0.15) is False
        assert check_trailing_stop(85.0, 100.0, -0.15) is True
        
        # -25% distance
        assert check_trailing_stop(76.0, 100.0, -0.25) is False
        assert check_trailing_stop(75.0, 100.0, -0.25) is True
    
    def test_higher_peak(self):
        """Should work with various peak values."""
        # Peak $150, current $135 = -10%
        assert check_trailing_stop(135.0, 150.0, -0.10) is True
        
        # Peak $200, current $180 = -10%
        assert check_trailing_stop(180.0, 200.0, -0.10) is True
    
    def test_positive_distance_converted(self):
        """Should convert positive distance to negative."""
        assert check_trailing_stop(91.0, 100.0, 0.10) is False
        assert check_trailing_stop(90.0, 100.0, 0.10) is True
    
    def test_invalid_high_water_mark(self):
        """Should raise error for invalid high-water-mark."""
        with pytest.raises(ValueError):
            check_trailing_stop(90.0, 0.0, -0.10)
        
        with pytest.raises(ValueError):
            check_trailing_stop(90.0, -100.0, -0.10)


class TestCalculateStopPrice:
    """Tests for calculate_stop_price function."""
    
    def test_basic_calculation(self):
        """Should calculate correct stop price."""
        # Entry $100, -8% stop = $92
        assert calculate_stop_price(100.0, -0.08) == 92.0
        
        # Entry $100, -10% stop = $90
        assert calculate_stop_price(100.0, -0.10) == 90.0
        
        # Entry $200, -8% stop = $184
        assert calculate_stop_price(200.0, -0.08) == 184.0
    
    def test_positive_threshold_converted(self):
        """Should handle positive threshold."""
        assert calculate_stop_price(100.0, 0.08) == 92.0
    
    def test_invalid_entry_price(self):
        """Should raise error for invalid entry price."""
        with pytest.raises(ValueError):
            calculate_stop_price(0.0, -0.08)


class TestCalculateTrailingStopPrice:
    """Tests for calculate_trailing_stop_price function."""
    
    def test_basic_calculation(self):
        """Should calculate correct trailing stop price."""
        # Peak $100, -10% distance = $90
        assert calculate_trailing_stop_price(100.0, -0.10) == 90.0
        
        # Peak $150, -10% distance = $135
        assert calculate_trailing_stop_price(150.0, -0.10) == 135.0
        
        # Peak $150, -15% distance = $127.5
        assert calculate_trailing_stop_price(150.0, -0.15) == 127.5


class TestCheckStopWithDetails:
    """Tests for check_stop_with_details function."""
    
    def test_no_stops_enabled(self):
        """Should return None when no stops enabled."""
        result = check_stop_with_details(
            entry_price=100.0,
            current_price=80.0,  # -20% loss
            high_water_mark=110.0,
            hard_stop_pct=None,
            trailing_stop_pct=None,
        )
        assert result is None
    
    def test_hard_stop_triggered(self):
        """Should return hard stop details when triggered."""
        result = check_stop_with_details(
            entry_price=100.0,
            current_price=90.0,  # -10% loss
            high_water_mark=110.0,
            hard_stop_pct=-0.08,
            trailing_stop_pct=None,
        )
        
        assert result is not None
        assert result.triggered is True
        assert result.stop_type == "hard"
        assert result.trigger_price == 92.0
        assert "Hard stop-loss triggered" in result.reason
    
    def test_trailing_stop_triggered(self):
        """Should return trailing stop details when triggered."""
        result = check_stop_with_details(
            entry_price=100.0,
            current_price=99.0,  # -1% from entry (OK for hard stop)
            high_water_mark=110.0,  # -10% from peak
            hard_stop_pct=-0.08,
            trailing_stop_pct=-0.10,
        )
        
        assert result is not None
        assert result.triggered is True
        assert result.stop_type == "trailing"
    
    def test_hard_stop_takes_priority(self):
        """Hard stop should trigger before trailing stop."""
        result = check_stop_with_details(
            entry_price=100.0,
            current_price=80.0,  # -20% from entry AND peak
            high_water_mark=100.0,
            hard_stop_pct=-0.08,
            trailing_stop_pct=-0.10,
        )
        
        assert result is not None
        assert result.stop_type == "hard"  # Hard stop takes priority


class TestUpdateHighWaterMark:
    """Tests for update_high_water_mark function (REC-220)."""
    
    def test_initial_hwm(self):
        """Should set initial HWM to current price."""
        hwm = update_high_water_mark(100.0, None)
        assert hwm == 100.0
    
    def test_update_higher(self):
        """Should update HWM when price is higher."""
        hwm = update_high_water_mark(110.0, 100.0)
        assert hwm == 110.0
    
    def test_no_update_lower(self):
        """Should NOT update HWM when price is lower."""
        hwm = update_high_water_mark(90.0, 100.0)
        assert hwm == 100.0
    
    def test_no_update_equal(self):
        """Should keep HWM when price is equal."""
        hwm = update_high_water_mark(100.0, 100.0)
        assert hwm == 100.0
    
    def test_invalid_current_price(self):
        """Should raise error for negative price."""
        with pytest.raises(ValueError):
            update_high_water_mark(-10.0, 100.0)


class TestEdgeCases:
    """Edge case tests for stop-loss functions."""
    
    def test_very_small_prices(self):
        """Should handle penny stocks."""
        # Entry $0.50, stop at -8% = $0.46
        # At $0.45 = -10%, should trigger
        assert check_hard_stop(0.50, 0.45, -0.08) is True  # -10% (below -8%)
        assert check_hard_stop(0.50, 0.47, -0.08) is False  # -6% (above -8%)
    
    def test_very_large_prices(self):
        """Should handle high-priced stocks."""
        assert check_hard_stop(50000.0, 46000.0, -0.08) is True  # -8%
        assert check_hard_stop(50000.0, 47000.0, -0.08) is False  # -6%
    
    def test_zero_current_price(self):
        """Should trigger stop at zero price (bankruptcy)."""
        assert check_hard_stop(100.0, 0.0, -0.08) is True
    
    def test_floating_point_precision(self):
        """Should handle floating point edge cases."""
        # Exactly at boundary
        entry = 100.0
        stop_pct = -0.08
        stop_price = entry * (1 + stop_pct)  # 92.0
        
        # At stop price
        assert check_hard_stop(entry, stop_price, stop_pct) is True
        
        # Just above stop price (should NOT trigger)
        assert check_hard_stop(entry, stop_price + 0.01, stop_pct) is False
