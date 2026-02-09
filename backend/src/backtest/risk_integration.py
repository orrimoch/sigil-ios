"""
Backtest Risk Integration - REC-248

Wire Phase 3 risk features into the backtest engine:
- Regime-aware threshold adjustments
- Sector concentration limits
- Pattern memory logging for analysis
"""

import numpy as np
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class BacktestRiskIntegration:
    """
    Integrates Phase 3 risk features into backtesting.
    
    Features:
    - Adjust thresholds based on historical VIX/regime
    - Apply sector concentration limits
    - Log trades for pattern analysis
    """
    
    def __init__(
        self,
        enable_regime_adjustment: bool = True,
        enable_sector_limits: bool = True,
        sector_limit_pct: float = 0.30,
    ):
        self.enable_regime_adjustment = enable_regime_adjustment
        self.enable_sector_limits = enable_sector_limits
        self.sector_limit_pct = sector_limit_pct
        
        # Cache for VIX data
        self._vix_cache: Dict[str, float] = {}
        self._regime_cache: Dict[str, str] = {}
        
        # Sector mapping cache
        self._sector_cache: Dict[str, str] = {}
    
    def load_historical_vix(self, start_date: str, end_date: str) -> None:
        """Load historical VIX data for the backtest period."""
        try:
            import yfinance as yf
            
            vix = yf.Ticker("^VIX")
            hist = vix.history(start=start_date, end=end_date)
            
            for date, row in hist.iterrows():
                date_str = date.strftime("%Y-%m-%d")
                self._vix_cache[date_str] = float(row['Close'])
            
            logger.info(f"Loaded {len(self._vix_cache)} days of VIX data")
            
        except Exception as e:
            logger.warning(f"Could not load VIX data: {e}")
    
    def get_vix_for_date(self, date: str) -> Optional[float]:
        """Get VIX value for a specific date."""
        return self._vix_cache.get(date)
    
    def detect_regime_for_date(
        self,
        date: str,
        returns_20d: Optional[np.ndarray] = None,
    ) -> str:
        """
        Detect market regime for a specific date.
        
        Uses rule-based detection for backtest (HMM would be too slow).
        """
        if date in self._regime_cache:
            return self._regime_cache[date]
        
        vix = self.get_vix_for_date(date)
        
        # Rule-based regime detection
        if vix is not None:
            if vix < 12:
                regime = "low_vol"
            elif vix < 20:
                regime = "normal"
            elif vix < 30:
                regime = "high_vol"
            else:
                regime = "crisis"
        else:
            regime = "normal"  # Default if no VIX data
        
        self._regime_cache[date] = regime
        return regime
    
    def get_threshold_adjustment(self, regime: str) -> float:
        """Get threshold adjustment for a regime."""
        adjustments = {
            "low_vol": -2.0,
            "normal": 0.0,
            "high_vol": 3.0,
            "crisis": 7.0,
        }
        return adjustments.get(regime, 0.0)
    
    def adjust_thresholds(
        self,
        date: str,
        buy_threshold: float,
        sell_threshold: float,
    ) -> Tuple[float, float]:
        """
        Adjust buy/sell thresholds based on market regime.
        
        In high-vol regimes, raise thresholds to be more conservative.
        """
        if not self.enable_regime_adjustment:
            return buy_threshold, sell_threshold
        
        regime = self.detect_regime_for_date(date)
        adjustment = self.get_threshold_adjustment(regime)
        
        adjusted_buy = buy_threshold + adjustment
        adjusted_sell = sell_threshold + adjustment
        
        return adjusted_buy, adjusted_sell
    
    def load_sector_mapping(self) -> None:
        """Load sector mapping from stocks.json."""
        try:
            import json
            stocks_path = Path(__file__).parent.parent.parent / "data" / "stocks.json"
            
            if stocks_path.exists():
                with open(stocks_path) as f:
                    stocks = json.load(f)
                
                for stock in stocks:
                    self._sector_cache[stock.get("ticker", "")] = stock.get("sector", "Unknown")
                
                logger.info(f"Loaded sector mapping for {len(self._sector_cache)} stocks")
        except Exception as e:
            logger.warning(f"Could not load sector mapping: {e}")
    
    def get_sector(self, ticker: str) -> str:
        """Get sector for a ticker."""
        return self._sector_cache.get(ticker.upper(), "Unknown")
    
    def check_sector_limit(
        self,
        ticker: str,
        trade_value: float,
        portfolio_positions: Dict[str, Any],
        portfolio_value: float,
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if adding a position would exceed sector limits.
        
        Returns:
            (allowed, warning_message)
        """
        if not self.enable_sector_limits:
            return True, None
        
        if portfolio_value <= 0:
            return True, None
        
        trade_sector = self.get_sector(ticker)
        
        # Calculate current sector exposure
        sector_value = 0.0
        for pos_ticker, pos in portfolio_positions.items():
            if self.get_sector(pos_ticker) == trade_sector:
                sector_value += pos.get("current_value", 0)
        
        # Post-trade exposure
        new_sector_value = sector_value + trade_value
        new_sector_pct = new_sector_value / (portfolio_value + trade_value)
        
        if new_sector_pct > self.sector_limit_pct:
            return False, f"Would exceed {trade_sector} limit ({new_sector_pct:.1%} > {self.sector_limit_pct:.0%})"
        
        return True, None
    
    def calculate_sector_exposure(
        self,
        portfolio_positions: Dict[str, Any],
    ) -> Dict[str, float]:
        """Calculate current exposure by sector."""
        exposure = {}
        
        for ticker, pos in portfolio_positions.items():
            sector = self.get_sector(ticker)
            value = pos.get("current_value", 0)
            exposure[sector] = exposure.get(sector, 0) + value
        
        return exposure
    
    def get_backtest_summary(self) -> Dict[str, Any]:
        """Get summary of risk integration for backtest report."""
        return {
            "regime_adjustment_enabled": self.enable_regime_adjustment,
            "sector_limits_enabled": self.enable_sector_limits,
            "sector_limit_pct": self.sector_limit_pct,
            "vix_data_points": len(self._vix_cache),
            "regime_detections": len(self._regime_cache),
            "sectors_mapped": len(self._sector_cache),
        }


def create_risk_integration(
    enable_regime: bool = True,
    enable_sectors: bool = True,
    sector_limit: float = 0.30,
) -> BacktestRiskIntegration:
    """Factory function to create risk integration with loaded data."""
    integration = BacktestRiskIntegration(
        enable_regime_adjustment=enable_regime,
        enable_sector_limits=enable_sectors,
        sector_limit_pct=sector_limit,
    )
    
    # Pre-load data
    integration.load_sector_mapping()
    
    return integration


# ========== Backtest Engine Integration ==========

def apply_regime_to_backtest(
    engine: Any,
    start_date: str,
    end_date: str,
) -> None:
    """
    Apply regime-aware thresholds to a backtest engine.
    
    Monkey-patches the engine to use adjusted thresholds.
    """
    integration = create_risk_integration()
    integration.load_historical_vix(start_date, end_date)
    
    # Store integration on engine for access
    engine._risk_integration = integration


def get_regime_adjusted_thresholds(
    engine: Any,
    date: str,
    params: Any,
) -> Tuple[float, float]:
    """Get regime-adjusted thresholds for a backtest date."""
    if hasattr(engine, '_risk_integration'):
        return engine._risk_integration.adjust_thresholds(
            date,
            params.entry_threshold,
            params.exit_threshold,
        )
    return params.entry_threshold, params.exit_threshold
