"""
Shared fixtures for EMATA tests.
"""
import sys
from pathlib import Path

# Add emata package to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import numpy as np
from datetime import datetime, timezone, timedelta

from emata.episode import (
    Episode, DecisionRecord, ContextSnapshot,
    OutcomeRecord, RetrievedEpisode,
)
from emata.episode_store import EpisodeStore
from emata.retriever import EpisodicRetriever, RetrieverConfig
from emata.augmenter import ContextAugmenter
from emata.meta_learner import MetaLearner, MetaLearnerConfig


@pytest.fixture
def base_time():
    return datetime(2025, 6, 1, tzinfo=timezone.utc)


@pytest.fixture
def sample_context():
    """A typical normal-regime context."""
    return ContextSnapshot(
        regime="normal",
        regime_confidence=0.82,
        vix=17.5,
        vix_regime="calm",
        trend="up",
        cash_pct=0.35,
        position_count=8,
        sector_exposure={"Technology": 0.25, "Healthcare": 0.15},
        fundamental_score=75.0,
        sentiment_score=68.0,
        technical_score=72.0,
        macro_score=65.0,
        sector="Technology",
    )


@pytest.fixture
def crisis_context():
    """A crisis-regime context."""
    return ContextSnapshot(
        regime="crisis",
        regime_confidence=0.91,
        vix=45.0,
        vix_regime="panic",
        trend="down",
        cash_pct=0.55,
        position_count=3,
        sector_exposure={"Technology": 0.10, "Utilities": 0.20},
        fundamental_score=40.0,
        sentiment_score=25.0,
        technical_score=30.0,
        macro_score=35.0,
        sector="Technology",
    )


@pytest.fixture
def make_episode(base_time):
    """Factory for creating episodes."""
    counter = [0]
    
    def _make(
        ticker="AAPL",
        action="BUY",
        score=75.0,
        regime="normal",
        sector="Technology",
        vix=17.0,
        outcome_pct=5.0,
        lesson="Test lesson",
        days_offset=0,
        confidence=0.8,
    ):
        counter[0] += 1
        return Episode(
            timestamp=base_time + timedelta(days=days_offset),
            decision=DecisionRecord(
                ticker=ticker,
                action=action,
                shares=10,
                price=150.0,
                score=score,
                confidence=confidence,
                rationale=f"{action} {ticker} with score {score:.0f}",
            ),
            context=ContextSnapshot(
                regime=regime,
                regime_confidence=0.8,
                vix=vix,
                vix_regime="calm" if vix < 20 else "elevated",
                trend="up" if regime in ("low_vol", "normal") else "down",
                cash_pct=0.35,
                position_count=8,
                sector_exposure={sector: 0.2},
                fundamental_score=score * 0.9,
                sentiment_score=score * 0.7,
                technical_score=score * 0.85,
                macro_score=65.0,
                sector=sector,
            ),
            outcome=OutcomeRecord(
                pct_return=outcome_pct,
                holding_days=14,
                exit_price=150.0 * (1 + outcome_pct / 100),
                tag="win" if outcome_pct > 5 else "small_win" if outcome_pct > 0 else "loss",
                pnl_dollars=outcome_pct * 15,
            ),
            lesson=lesson,
        )
    
    return _make


@pytest.fixture
def populated_store(make_episode):
    """Store with 20 diverse episodes."""
    store = EpisodeStore()
    
    episodes = [
        # Normal regime, Technology
        make_episode(ticker="AAPL", score=80, regime="normal", sector="Technology", outcome_pct=8.5, days_offset=0),
        make_episode(ticker="MSFT", score=72, regime="normal", sector="Technology", outcome_pct=3.2, days_offset=2),
        make_episode(ticker="NVDA", score=85, regime="normal", sector="Technology", outcome_pct=12.1, days_offset=4),
        make_episode(ticker="AMD", score=65, regime="normal", sector="Technology", outcome_pct=-2.3, days_offset=6),
        
        # Normal regime, other sectors
        make_episode(ticker="UNH", score=78, regime="normal", sector="Healthcare", outcome_pct=6.0, days_offset=8),
        make_episode(ticker="JPM", score=70, regime="normal", sector="Finance", outcome_pct=4.5, days_offset=10),
        make_episode(ticker="XOM", score=60, regime="normal", sector="Energy", outcome_pct=-1.5, days_offset=12),
        
        # High vol regime
        make_episode(ticker="AAPL", score=72, regime="high_vol", sector="Technology", vix=28, outcome_pct=-4.2, days_offset=14),
        make_episode(ticker="GOOGL", score=68, regime="high_vol", sector="Technology", vix=30, outcome_pct=-6.1, days_offset=16),
        make_episode(ticker="UNH", score=75, regime="high_vol", sector="Healthcare", vix=26, outcome_pct=2.0, days_offset=18),
        
        # Low vol regime
        make_episode(ticker="MSFT", score=82, regime="low_vol", sector="Technology", vix=12, outcome_pct=9.3, days_offset=20),
        make_episode(ticker="V", score=76, regime="low_vol", sector="Finance", vix=11, outcome_pct=5.8, days_offset=22),
        
        # Crisis regime
        make_episode(ticker="AAPL", score=45, regime="crisis", sector="Technology", vix=42, outcome_pct=-12.5, days_offset=24),
        make_episode(ticker="JPM", score=38, regime="crisis", sector="Finance", vix=50, outcome_pct=-8.3, days_offset=26),
        make_episode(ticker="NEE", score=55, regime="crisis", sector="Utilities", vix=38, outcome_pct=1.5, days_offset=28),
        
        # SELL decisions
        make_episode(ticker="TSLA", action="SELL", score=35, regime="normal", sector="Technology", outcome_pct=7.0, days_offset=30, lesson="Selling low-score worked"),
        make_episode(ticker="XOM", action="SELL", score=42, regime="high_vol", sector="Energy", vix=25, outcome_pct=3.5, days_offset=32),
        
        # More variety
        make_episode(ticker="CRM", score=88, regime="normal", sector="Technology", outcome_pct=15.0, days_offset=34, lesson="High-conviction worked well"),
        make_episode(ticker="AVGO", score=77, regime="normal", sector="Technology", outcome_pct=7.2, days_offset=36),
        make_episode(ticker="CMI", score=71, regime="normal", sector="Industrials", outcome_pct=4.8, days_offset=38),
    ]
    
    store.store_batch(episodes)
    return store
