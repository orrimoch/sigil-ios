#!/usr/bin/env python3
"""
HMM Regime Model Training Script

Trains a 4-state Gaussian HMM on S&P 500 and VIX data.
Run daily via cron to keep the model fresh.

Usage:
    python3 scripts/train_hmm.py
"""

import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import pickle
import os
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

def train_hmm_model(days: int = 730, output_dir: str = "data/models") -> dict:
    """
    Train HMM regime model on historical data.
    
    Args:
        days: Number of days of history to use (default: 730 = 2 years)
        output_dir: Directory to save model
        
    Returns:
        Dict with training results
    """
    print(f"📊 HMM Training Started: {datetime.now().isoformat()}")
    print(f"   Training window: {days} days")
    
    # Fetch data
    print("\n📥 Fetching historical data...")
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    try:
        spy = yf.download("SPY", start=start_date, end=end_date, progress=False)
        vix = yf.download("^VIX", start=start_date, end=end_date, progress=False)
    except Exception as e:
        print(f"❌ Failed to fetch data: {e}")
        return {"success": False, "error": str(e)}
    
    if len(spy) < 100:
        print(f"❌ Insufficient data: {len(spy)} days (need 100+)")
        return {"success": False, "error": "Insufficient data"}
    
    print(f"   SPY: {len(spy)} days")
    print(f"   VIX: {len(vix)} days")
    
    # Calculate features
    spy['returns'] = spy['Close'].pct_change()
    spy['volatility_20d'] = spy['returns'].rolling(20).std()
    
    # Align VIX
    vix_aligned = vix['Close'].reindex(spy.index).ffill()
    
    # Prepare features
    valid_idx = spy['volatility_20d'].dropna().index
    features = np.column_stack([
        spy.loc[valid_idx, 'volatility_20d'].values,
        vix_aligned.loc[valid_idx].values
    ])
    
    print(f"   Features: {features.shape}")
    
    # Train HMM
    print("\n🔧 Training 4-state HMM...")
    
    try:
        from hmmlearn import hmm
        from sklearn.preprocessing import StandardScaler
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        return {"success": False, "error": f"Missing dependency: {e}"}
    
    # Normalize
    scaler = StandardScaler()
    features_normalized = scaler.fit_transform(features)
    
    # Train
    model = hmm.GaussianHMM(
        n_components=4,
        covariance_type="diag",
        n_iter=100,
        random_state=42
    )
    model.fit(features_normalized)
    
    print(f"   Converged: {model.monitor_.converged}")
    print(f"   Log-likelihood: {model.score(features_normalized):.2f}")
    
    # Predict states and create mapping
    states = model.predict(features_normalized)
    
    # Map states by VIX level
    state_vix_means = {}
    for state in range(4):
        mask = states == state
        if mask.any():
            state_vix_means[state] = features[mask, 1].mean()
    
    sorted_states = sorted(state_vix_means.items(), key=lambda x: x[1])
    regime_names = ['low_vol', 'normal', 'high_vol', 'crisis']
    state_mapping = {state: regime_names[i] for i, (state, _) in enumerate(sorted_states)}
    
    print(f"\n📋 State Mapping:")
    for state, vix_mean in sorted_states:
        print(f"   State {state} → {state_mapping[state]} (avg VIX: {vix_mean:.1f})")
    
    # Save model
    os.makedirs(output_dir, exist_ok=True)
    model_path = f"{output_dir}/hmm_regime_model.pkl"
    
    model_data = {
        'model': model,
        'scaler': scaler,
        'state_mapping': state_mapping,
        'trained_at': datetime.now().isoformat(),
        'training_samples': len(features),
        'training_days': days,
        'converged': model.monitor_.converged,
        'log_likelihood': model.score(features_normalized),
    }
    
    with open(model_path, 'wb') as f:
        pickle.dump(model_data, f)
    
    print(f"\n✅ Model saved: {model_path}")
    
    # Test current prediction
    current_features = scaler.transform([features[-1]])
    current_state = model.predict(current_features)[0]
    current_probs = model.predict_proba(current_features)[0]
    
    result = {
        "success": True,
        "model_path": model_path,
        "training_samples": len(features),
        "converged": model.monitor_.converged,
        "current_regime": state_mapping[current_state],
        "current_confidence": float(current_probs[current_state]),
        "trained_at": model_data['trained_at'],
    }
    
    print(f"\n🎯 Current Regime: {result['current_regime']} ({result['current_confidence']*100:.0f}%)")
    print(f"\n📊 HMM Training Complete: {datetime.now().isoformat()}")
    
    return result


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Train HMM regime model")
    parser.add_argument("--days", type=int, default=730, help="Days of history (default: 730)")
    parser.add_argument("--output", type=str, default="data/models", help="Output directory")
    args = parser.parse_args()
    
    # Change to backend directory
    backend_dir = Path(__file__).parent.parent
    os.chdir(backend_dir)
    
    result = train_hmm_model(days=args.days, output_dir=args.output)
    
    if result["success"]:
        print("\n✅ Training successful!")
        sys.exit(0)
    else:
        print(f"\n❌ Training failed: {result.get('error')}")
        sys.exit(1)
