"""
Unit tests for Episode data model.
"""
import pytest
import numpy as np
from datetime import datetime, timezone

from emata.episode import (
    Episode, DecisionRecord, ContextSnapshot,
    OutcomeRecord, RetrievedEpisode,
)


class TestDecisionRecord:
    def test_creation(self):
        d = DecisionRecord(ticker="AAPL", action="BUY", score=75.0)
        assert d.ticker == "AAPL"
        assert d.action == "BUY"
        assert d.score == 75.0

    def test_to_dict(self):
        d = DecisionRecord(ticker="NVDA", action="SELL", shares=20, price=890.0, score=35.0)
        data = d.to_dict()
        assert data["ticker"] == "NVDA"
        assert data["shares"] == 20
        assert data["price"] == 890.0


class TestContextSnapshot:
    def test_to_feature_vector_dimensions(self, sample_context):
        vec = sample_context.to_feature_vector()
        assert vec.shape == (10,)
        assert all(0 <= v <= 1 for v in vec)

    def test_feature_vector_regime_encoding(self):
        low_vol = ContextSnapshot(regime="low_vol")
        crisis = ContextSnapshot(regime="crisis")
        
        low_vec = low_vol.to_feature_vector()
        crisis_vec = crisis.to_feature_vector()
        
        # Crisis should have higher regime dimension
        assert crisis_vec[0] > low_vec[0]

    def test_feature_vector_vix_normalization(self):
        low_vix = ContextSnapshot(vix=10.0)
        high_vix = ContextSnapshot(vix=60.0)
        
        assert low_vix.to_feature_vector()[2] < high_vix.to_feature_vector()[2]

    def test_feature_vector_scores(self):
        high_scores = ContextSnapshot(
            fundamental_score=90, sentiment_score=85,
            technical_score=80, macro_score=75,
        )
        low_scores = ContextSnapshot(
            fundamental_score=20, sentiment_score=15,
            technical_score=25, macro_score=30,
        )
        
        high_vec = high_scores.to_feature_vector()
        low_vec = low_scores.to_feature_vector()
        
        # Score dimensions [5:9] should be higher for high_scores
        for i in range(5, 9):
            assert high_vec[i] > low_vec[i]

    def test_to_dict_roundtrip(self, sample_context):
        data = sample_context.to_dict()
        assert data["regime"] == "normal"
        assert data["vix"] == 17.5
        assert "Technology" in data["sector_exposure"]


class TestOutcomeRecord:
    def test_quality_score_positive(self):
        o = OutcomeRecord(pct_return=10.0)
        assert o.quality_score > 0
        assert o.quality_score < 1.0
        assert o.is_positive

    def test_quality_score_negative(self):
        o = OutcomeRecord(pct_return=-10.0)
        assert o.quality_score < 0
        assert o.quality_score > -1.0
        assert not o.is_positive

    def test_quality_score_zero(self):
        o = OutcomeRecord(pct_return=0.0)
        assert abs(o.quality_score) < 0.01

    def test_quality_score_bounded(self):
        extreme_win = OutcomeRecord(pct_return=100.0)
        extreme_loss = OutcomeRecord(pct_return=-100.0)
        
        assert extreme_win.quality_score < 1.0
        assert extreme_loss.quality_score > -1.0


class TestEpisode:
    def test_auto_id(self):
        ep = Episode(
            decision=DecisionRecord(ticker="AAPL", action="BUY"),
        )
        assert ep.id  # Non-empty
        assert len(ep.id) == 16  # SHA256 truncated

    def test_deterministic_id(self):
        ep1 = Episode(
            timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc),
            decision=DecisionRecord(ticker="AAPL", action="BUY"),
        )
        ep2 = Episode(
            timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc),
            decision=DecisionRecord(ticker="AAPL", action="BUY"),
        )
        assert ep1.id == ep2.id

    def test_is_complete(self, make_episode):
        ep = make_episode()
        assert ep.is_complete  # Has outcome and lesson
        
        ep2 = Episode(decision=DecisionRecord(ticker="AAPL", action="BUY"))
        assert not ep2.is_complete

    def test_to_dict_roundtrip(self, make_episode):
        ep = make_episode(ticker="NVDA", score=85, outcome_pct=12.5)
        data = ep.to_dict()
        
        ep2 = Episode.from_dict(data)
        assert ep2.decision.ticker == "NVDA"
        assert ep2.decision.score == 85
        assert ep2.outcome.pct_return == 12.5

    def test_to_embedding_text(self, make_episode):
        ep = make_episode(ticker="AAPL", score=75, regime="normal")
        text = ep.to_embedding_text()
        
        assert "AAPL" in text
        assert "BUY" in text
        assert "75" in text
        assert "normal" in text

    def test_from_dict_missing_outcome(self):
        data = {
            "id": "test",
            "timestamp": "2025-01-01T00:00:00+00:00",
            "decision": {"ticker": "AAPL", "action": "BUY", "score": 75.0,
                         "shares": 0, "price": 0.0, "confidence": 0.0, "rationale": ""},
            "context": {"regime": "normal", "regime_confidence": 0.7, "vix": 15.0,
                        "vix_regime": "calm", "trend": "sideways", "cash_pct": 0.5,
                        "position_count": 0, "fundamental_score": 50.0,
                        "sentiment_score": 50.0, "technical_score": 50.0,
                        "macro_score": 50.0, "sector": "Unknown"},
            "outcome": None,
            "lesson": "",
        }
        ep = Episode.from_dict(data)
        assert ep.outcome is None
        assert not ep.is_complete


class TestRetrievedEpisode:
    def test_creation(self, make_episode):
        ep = make_episode()
        re = RetrievedEpisode(
            episode=ep,
            embedding_similarity=0.85,
            context_similarity=0.72,
            regime_match=True,
            sector_match=True,
            combined_score=0.80,
            outcome_weight=1.2,
            final_score=0.96,
        )
        assert re.final_score == 0.96
        assert re.regime_match

    def test_to_dict(self, make_episode):
        ep = make_episode()
        re = RetrievedEpisode(
            episode=ep,
            embedding_similarity=0.9,
            context_similarity=0.8,
            combined_score=0.85,
            final_score=0.90,
        )
        data = re.to_dict()
        assert "episode" in data
        assert data["embedding_similarity"] == 0.9
