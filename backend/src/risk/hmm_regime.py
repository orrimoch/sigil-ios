"""
HMM Volatility Regime Detection - REC-243

Uses Hidden Markov Model to detect market regimes:
- LOW_VOL: Calm market, low volatility
- NORMAL: Average volatility
- HIGH_VOL: Elevated volatility
- CRISIS: Extreme volatility (rare)

The regime affects scoring thresholds and risk recommendations.

API Endpoint: GET /api/v1/market/regime
"""

import numpy as np
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Tuple
from enum import Enum
import logging
import pickle
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# Try to import hmmlearn, fall back to rule-based if not available
try:
    from hmmlearn import hmm
    HMM_AVAILABLE = True
except ImportError:
    logger.warning("hmmlearn not installed, using rule-based regime detection")
    HMM_AVAILABLE = False


class MarketRegime(str, Enum):
    """Market volatility regime."""
    LOW_VOL = "low_vol"
    NORMAL = "normal"
    HIGH_VOL = "high_vol"
    CRISIS = "crisis"


# Regime to threshold adjustment mapping
REGIME_ADJUSTMENTS = {
    MarketRegime.LOW_VOL: -2.0,   # Lower thresholds in calm markets
    MarketRegime.NORMAL: 0.0,     # No adjustment
    MarketRegime.HIGH_VOL: 3.0,   # Higher thresholds in volatile markets
    MarketRegime.CRISIS: 7.0,     # Much higher thresholds in crisis
}


@dataclass
class RegimeResult:
    """Result of regime detection."""
    regime: MarketRegime
    confidence: float              # 0-1 confidence in detection
    probabilities: Dict[str, float]  # Probability of each regime
    vix_value: Optional[float]
    volatility_20d: Optional[float]
    detected_at: datetime
    method: str                    # "hmm" or "rule_based"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "regime": self.regime.value,
            "confidence": round(self.confidence, 3),
            "probabilities": {k: round(v, 3) for k, v in self.probabilities.items()},
            "vix_value": round(self.vix_value, 2) if self.vix_value else None,
            "volatility_20d": round(self.volatility_20d, 4) if self.volatility_20d else None,
            "detected_at": self.detected_at.isoformat(),
            "method": self.method,
            "threshold_adjustment": REGIME_ADJUSTMENTS[self.regime],
        }


class HMMRegimeDetector:
    """
    Hidden Markov Model for market regime detection.
    
    Uses a 4-state Gaussian HMM trained on:
    - Daily returns volatility (20-day rolling)
    - VIX level
    - Return magnitude
    
    Falls back to rule-based detection if HMM unavailable or fails.
    """
    
    # Model persistence - new trained model with metadata
    MODEL_PATH = Path(__file__).parent.parent.parent / "data" / "models" / "hmm_regime_model.pkl"
    
    # HMM parameters
    N_STATES = 4  # LOW_VOL, NORMAL, HIGH_VOL, CRISIS
    N_FEATURES = 2  # volatility, VIX
    
    # Rule-based thresholds (fallback)
    VOL_THRESHOLDS = {
        MarketRegime.LOW_VOL: 0.008,    # Daily vol < 0.8%
        MarketRegime.NORMAL: 0.015,      # Daily vol < 1.5%
        MarketRegime.HIGH_VOL: 0.025,    # Daily vol < 2.5%
        MarketRegime.CRISIS: float('inf'),  # Daily vol >= 2.5%
    }
    
    VIX_THRESHOLDS = {
        MarketRegime.LOW_VOL: 12,
        MarketRegime.NORMAL: 20,
        MarketRegime.HIGH_VOL: 30,
        MarketRegime.CRISIS: float('inf'),
    }
    
    def __init__(self):
        self.model: Optional[hmm.GaussianHMM] = None
        self.scaler = None
        self.state_mapping = None
        self._load_model()
    
    def _load_model(self) -> None:
        """Load pre-trained HMM model if available."""
        if not HMM_AVAILABLE:
            return
        
        if self.MODEL_PATH.exists():
            try:
                with open(self.MODEL_PATH, 'rb') as f:
                    model_data = pickle.load(f)
                
                # Handle new format with metadata
                if isinstance(model_data, dict):
                    self.model = model_data.get('model')
                    self.scaler = model_data.get('scaler')
                    self.state_mapping = model_data.get('state_mapping')
                    trained_at = model_data.get('trained_at', 'unknown')
                    logger.info(f"Loaded HMM model from {self.MODEL_PATH} (trained: {trained_at})")
                else:
                    # Legacy format - just the model
                    self.model = model_data
                    logger.info(f"Loaded legacy HMM model from {self.MODEL_PATH}")
            except Exception as e:
                logger.warning(f"Failed to load HMM model: {e}")
                self.model = None
    
    def save_model(self) -> None:
        """Save trained HMM model to disk."""
        if self.model is None:
            return
        
        self.MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(self.MODEL_PATH, 'wb') as f:
            pickle.dump(self.model, f)
        logger.info(f"Saved HMM model to {self.MODEL_PATH}")
    
    def train(self, returns: np.ndarray, vix_values: np.ndarray) -> None:
        """
        Train HMM on historical data.
        
        Args:
            returns: Array of daily returns
            vix_values: Array of VIX values (same length as returns)
        """
        if not HMM_AVAILABLE:
            logger.warning("hmmlearn not available, cannot train HMM")
            return
        
        if len(returns) < 100:
            logger.warning("Insufficient data for HMM training (need 100+ days)")
            return
        
        # Calculate rolling volatility (20-day)
        vol_20d = self._rolling_volatility(returns, window=20)
        
        # Prepare features (volatility, VIX)
        # Align lengths (vol_20d is shorter due to rolling window)
        n = len(vol_20d)
        vix_aligned = vix_values[-n:]
        
        features = np.column_stack([vol_20d, vix_aligned])
        
        # Normalize features
        self._feature_mean = features.mean(axis=0)
        self._feature_std = features.std(axis=0)
        features_normalized = (features - self._feature_mean) / self._feature_std
        
        # Train HMM
        self.model = hmm.GaussianHMM(
            n_components=self.N_STATES,
            covariance_type="full",
            n_iter=200,
            random_state=42
        )
        
        self.model.fit(features_normalized)
        
        # Map states to regimes based on mean volatility of each state
        self._map_states_to_regimes(features)
        
        logger.info(f"Trained HMM on {len(features)} samples")
        self.save_model()
    
    def _rolling_volatility(self, returns: np.ndarray, window: int = 20) -> np.ndarray:
        """Calculate rolling standard deviation of returns."""
        if len(returns) < window:
            return np.array([np.std(returns)])
        
        vol = np.zeros(len(returns) - window + 1)
        for i in range(len(vol)):
            vol[i] = np.std(returns[i:i + window])
        return vol
    
    def _map_states_to_regimes(self, features: np.ndarray) -> None:
        """Map HMM states to regime labels based on state means."""
        # Get mean volatility for each state
        state_means = self.model.means_[:, 0]  # First feature is volatility
        
        # Sort states by volatility (low to high)
        sorted_indices = np.argsort(state_means)
        
        # Map: lowest vol -> LOW_VOL, highest vol -> CRISIS
        self._state_to_regime = {
            sorted_indices[0]: MarketRegime.LOW_VOL,
            sorted_indices[1]: MarketRegime.NORMAL,
            sorted_indices[2]: MarketRegime.HIGH_VOL,
            sorted_indices[3]: MarketRegime.CRISIS,
        }
    
    def detect(
        self,
        returns: np.ndarray,
        vix_value: Optional[float] = None,
    ) -> RegimeResult:
        """
        Detect current market regime.
        
        Args:
            returns: Recent daily returns (at least 20 days)
            vix_value: Current VIX value (optional, improves accuracy)
            
        Returns:
            RegimeResult with detected regime and confidence
        """
        # Calculate current volatility
        if len(returns) >= 20:
            volatility = float(np.std(returns[-20:]))
        else:
            volatility = float(np.std(returns))
        
        # Try HMM detection first
        if self.model is not None and HMM_AVAILABLE:
            try:
                return self._detect_hmm(returns, vix_value, volatility)
            except Exception as e:
                logger.warning(f"HMM detection failed, falling back to rules: {e}")
        
        # Fallback to rule-based detection
        return self._detect_rule_based(volatility, vix_value)
    
    def _detect_hmm(
        self,
        returns: np.ndarray,
        vix_value: Optional[float],
        volatility: float,
    ) -> RegimeResult:
        """Detect regime using HMM."""
        # Prepare features
        vix = vix_value if vix_value is not None else 20.0  # Default VIX
        features = np.array([[volatility, vix]])
        
        # Normalize using scaler if available, otherwise use legacy method
        if self.scaler is not None:
            features_normalized = self.scaler.transform(features)
        elif hasattr(self, '_feature_mean') and hasattr(self, '_feature_std'):
            features_normalized = (features - self._feature_mean) / self._feature_std
        else:
            # Fallback to simple normalization
            features_normalized = features
        
        # Predict state and probabilities
        state = self.model.predict(features_normalized)[0]
        proba = self.model.predict_proba(features_normalized)[0]
        
        # Map state to regime using state_mapping if available
        if self.state_mapping is not None:
            regime_str = self.state_mapping.get(state, 'normal')
            regime = MarketRegime(regime_str)
            
            # Build probabilities dict using state_mapping
            probabilities = {}
            for s, regime_name in self.state_mapping.items():
                probabilities[regime_name] = float(proba[s])
        else:
            # Legacy: use _state_to_regime
            regime = self._state_to_regime[state]
            probabilities = {}
            for s, r in self._state_to_regime.items():
                probabilities[r.value] = float(proba[s])
        
        confidence = float(proba[state])
        
        return RegimeResult(
            regime=regime,
            confidence=confidence,
            probabilities=probabilities,
            vix_value=vix_value,
            volatility_20d=volatility,
            detected_at=datetime.now(timezone.utc),
            method="hmm",
        )
    
    def _detect_rule_based(
        self,
        volatility: float,
        vix_value: Optional[float],
    ) -> RegimeResult:
        """Detect regime using simple rules (fallback)."""
        # Determine regime from volatility
        vol_regime = MarketRegime.CRISIS
        for regime, threshold in self.VOL_THRESHOLDS.items():
            if volatility < threshold:
                vol_regime = regime
                break
        
        # If VIX available, also consider it
        vix_regime = None
        if vix_value is not None:
            vix_regime = MarketRegime.CRISIS
            for regime, threshold in self.VIX_THRESHOLDS.items():
                if vix_value < threshold:
                    vix_regime = regime
                    break
        
        # Combine: take the more severe regime
        if vix_regime is not None:
            regime_order = [MarketRegime.LOW_VOL, MarketRegime.NORMAL, 
                          MarketRegime.HIGH_VOL, MarketRegime.CRISIS]
            vol_idx = regime_order.index(vol_regime)
            vix_idx = regime_order.index(vix_regime)
            regime = regime_order[max(vol_idx, vix_idx)]
        else:
            regime = vol_regime
        
        # Calculate confidence (higher if vol and VIX agree)
        if vix_regime == vol_regime:
            confidence = 0.85
        elif vix_regime is not None:
            confidence = 0.65
        else:
            confidence = 0.70
        
        # Build probabilities (approximate)
        probabilities = {r.value: 0.05 for r in MarketRegime}
        probabilities[regime.value] = confidence
        remaining = 1.0 - confidence
        for r in MarketRegime:
            if r != regime:
                probabilities[r.value] = remaining / 3
        
        return RegimeResult(
            regime=regime,
            confidence=confidence,
            probabilities=probabilities,
            vix_value=vix_value,
            volatility_20d=volatility,
            detected_at=datetime.now(timezone.utc),
            method="rule_based",
        )
    
    def get_threshold_adjustment(self, regime: MarketRegime) -> float:
        """Get scoring threshold adjustment for a regime."""
        return REGIME_ADJUSTMENTS.get(regime, 0.0)


# Singleton instance
_detector: Optional[HMMRegimeDetector] = None


def get_regime_detector() -> HMMRegimeDetector:
    """Get or create the regime detector singleton."""
    global _detector
    if _detector is None:
        _detector = HMMRegimeDetector()
    return _detector


async def detect_current_regime(
    use_cache: bool = True,
    cache_ttl_seconds: int = 3600,
) -> RegimeResult:
    """
    Detect current market regime using SPY returns and VIX.
    
    Cached for 1 hour by default.
    """
    import yfinance as yf
    from .vix_service import fetch_vix
    
    # Simple in-memory cache
    cache_key = "current_regime"
    if use_cache and hasattr(detect_current_regime, '_cache'):
        cached = detect_current_regime._cache.get(cache_key)
        if cached:
            result, timestamp = cached
            if datetime.now(timezone.utc) - timestamp < timedelta(seconds=cache_ttl_seconds):
                return result
    
    # Fetch SPY returns (last 60 days for rolling window)
    try:
        spy = yf.Ticker("SPY")
        hist = spy.history(period="3mo")
        if len(hist) < 20:
            raise ValueError("Insufficient SPY data")
        
        returns = hist['Close'].pct_change().dropna().values
    except Exception as e:
        logger.warning(f"Failed to fetch SPY data: {e}")
        # Use dummy returns
        returns = np.random.normal(0.0005, 0.01, 60)
    
    # Fetch VIX
    try:
        vix_data = await fetch_vix(use_cache=True)
        vix_value = vix_data.value
    except Exception:
        vix_value = None
    
    # Detect regime
    detector = get_regime_detector()
    result = detector.detect(returns, vix_value)
    
    # Cache result
    if not hasattr(detect_current_regime, '_cache'):
        detect_current_regime._cache = {}
    detect_current_regime._cache[cache_key] = (result, datetime.now(timezone.utc))
    
    return result


def train_regime_model_from_history(
    start_date: str = "2018-01-01",
    end_date: Optional[str] = None,
) -> None:
    """
    Train HMM model on historical SPY and VIX data.
    
    Should be run periodically (e.g., monthly) to update the model.
    """
    import yfinance as yf
    
    # Fetch SPY
    spy = yf.Ticker("SPY")
    spy_hist = spy.history(start=start_date, end=end_date)
    returns = spy_hist['Close'].pct_change().dropna().values
    
    # Fetch VIX
    vix = yf.Ticker("^VIX")
    vix_hist = vix.history(start=start_date, end=end_date)
    vix_values = vix_hist['Close'].values
    
    # Align lengths
    min_len = min(len(returns), len(vix_values))
    returns = returns[-min_len:]
    vix_values = vix_values[-min_len:]
    
    # Train
    detector = get_regime_detector()
    detector.train(returns, vix_values)
    
    logger.info(f"Trained HMM on {min_len} days of data")
