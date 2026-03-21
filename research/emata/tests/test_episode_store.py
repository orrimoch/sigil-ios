"""
Unit tests for EpisodeStore.
"""
import pytest
import numpy as np
import json
import tempfile
from pathlib import Path

from emata.episode import Episode, DecisionRecord, ContextSnapshot, OutcomeRecord
from emata.episode_store import EpisodeStore, EMBEDDING_DIM


class TestEpisodeStore:
    def test_empty_store(self):
        store = EpisodeStore()
        assert store.size == 0
        assert store.complete_count == 0

    def test_store_episode(self, make_episode):
        store = EpisodeStore()
        ep = make_episode()
        eid = store.store(ep)
        
        assert store.size == 1
        assert store.get(eid) is ep

    def test_store_generates_embedding(self, make_episode):
        store = EpisodeStore()
        ep = make_episode()
        assert ep.embedding is None
        
        store.store(ep)
        assert ep.embedding is not None
        assert ep.embedding.shape == (EMBEDDING_DIM,)

    def test_store_batch(self, make_episode):
        store = EpisodeStore()
        episodes = [make_episode(ticker=t) for t in ["AAPL", "NVDA", "MSFT"]]
        ids = store.store_batch(episodes)
        
        assert len(ids) == 3
        assert store.size == 3

    def test_get_all(self, make_episode):
        store = EpisodeStore()
        store.store_batch([make_episode(ticker=t) for t in ["AAPL", "NVDA"]])
        
        all_eps = store.get_all()
        assert len(all_eps) == 2

    def test_get_complete(self, make_episode):
        store = EpisodeStore()
        complete_ep = make_episode()
        incomplete_ep = Episode(decision=DecisionRecord(ticker="TEST", action="BUY"))
        
        store.store(complete_ep)
        store.store(incomplete_ep)
        
        complete = store.get_complete()
        assert len(complete) == 1
        assert complete[0].decision.ticker != "TEST"

    def test_update_outcome(self, make_episode):
        store = EpisodeStore()
        ep = Episode(decision=DecisionRecord(ticker="AAPL", action="BUY"))
        eid = store.store(ep)
        
        assert not ep.is_complete
        
        outcome = OutcomeRecord(pct_return=5.2, holding_days=14, tag="win")
        store.update_outcome(eid, outcome, lesson="Good trade")
        
        updated = store.get(eid)
        assert updated.is_complete
        assert updated.outcome.pct_return == 5.2
        assert updated.lesson == "Good trade"

    def test_update_outcome_nonexistent(self):
        store = EpisodeStore()
        outcome = OutcomeRecord(pct_return=5.0)
        assert not store.update_outcome("nonexistent", outcome)


class TestEpisodeStoreRetrieval:
    def test_find_nearest_empty_store(self):
        store = EpisodeStore()
        query = np.random.randn(EMBEDDING_DIM)
        results = store.find_nearest(query, k=5)
        assert results == []

    def test_find_nearest_basic(self, populated_store):
        # Query with a known episode's embedding
        ep = populated_store.get_all()[0]
        results = populated_store.find_nearest(ep.embedding, k=5)
        
        assert len(results) > 0
        # The episode itself should be the most similar
        assert results[0][0] == ep.id
        assert results[0][1] > 0.99  # Near-perfect self-similarity

    def test_find_nearest_respects_k(self, populated_store):
        query = np.random.randn(EMBEDDING_DIM)
        query = query / np.linalg.norm(query)
        
        results_5 = populated_store.find_nearest(query, k=5)
        results_10 = populated_store.find_nearest(query, k=10)
        
        assert len(results_5) <= 5
        assert len(results_10) <= 10
        assert len(results_10) >= len(results_5)

    def test_find_nearest_regime_filter(self, populated_store):
        query = np.random.randn(EMBEDDING_DIM)
        query = query / np.linalg.norm(query)
        
        results = populated_store.find_nearest(query, k=20, regime_filter="crisis")
        
        for eid, sim in results:
            ep = populated_store.get(eid)
            assert ep.context.regime == "crisis"

    def test_find_nearest_sector_filter(self, populated_store):
        query = np.random.randn(EMBEDDING_DIM)
        query = query / np.linalg.norm(query)
        
        results = populated_store.find_nearest(query, k=20, sector_filter="Healthcare")
        
        for eid, sim in results:
            ep = populated_store.get(eid)
            assert ep.context.sector == "Healthcare"

    def test_find_nearest_only_complete(self, make_episode):
        store = EpisodeStore()
        complete = make_episode(ticker="AAPL", outcome_pct=5.0)
        incomplete = Episode(decision=DecisionRecord(ticker="TEST", action="BUY"))
        
        store.store(complete)
        store.store(incomplete)
        
        results = store.find_nearest(complete.embedding, k=10, only_complete=True)
        result_ids = {eid for eid, _ in results}
        
        assert complete.id in result_ids
        assert incomplete.id not in result_ids

    def test_similarity_scores_bounded(self, populated_store):
        query = np.random.randn(EMBEDDING_DIM)
        query = query / np.linalg.norm(query)
        
        results = populated_store.find_nearest(query, k=10)
        for _, sim in results:
            assert -1.0 <= sim <= 1.0


class TestEpisodeStoreMetaLearning:
    def test_record_retrieval_helpful(self, make_episode):
        store = EpisodeStore()
        ep = make_episode()
        store.store(ep)
        
        store.record_retrieval(ep.id, was_helpful=True)
        
        assert ep.times_retrieved == 1
        assert ep.times_helpful == 1
        assert ep.utility_score > 0

    def test_record_retrieval_not_helpful(self, make_episode):
        store = EpisodeStore()
        ep = make_episode()
        store.store(ep)
        
        # Several unhelpful retrievals
        for _ in range(5):
            store.record_retrieval(ep.id, was_helpful=False)
        
        assert ep.times_retrieved == 5
        assert ep.times_helpful == 0
        assert ep.utility_score < 0.5

    def test_utility_converges(self, make_episode):
        store = EpisodeStore()
        ep = make_episode()
        store.store(ep)
        
        # Consistently helpful → utility approaches 1
        for _ in range(20):
            store.record_retrieval(ep.id, was_helpful=True)
        
        assert ep.utility_score > 0.8


class TestEpisodeStoreExport:
    def test_export_import_roundtrip(self, populated_store, tmp_path):
        export_path = str(tmp_path / "episodes.json")
        populated_store.export_json(export_path)
        
        # Import into new store
        new_store = EpisodeStore()
        stats = new_store.import_json(export_path)
        
        assert stats["imported"] == populated_store.size
        assert stats["skipped"] == 0
        assert new_store.size == populated_store.size

    def test_import_skips_duplicates(self, populated_store, tmp_path):
        export_path = str(tmp_path / "episodes.json")
        original_size = populated_store.size
        populated_store.export_json(export_path)
        
        # Import again into same store — all should be skipped
        stats = populated_store.import_json(export_path)
        assert stats["skipped"] == original_size
        assert stats["imported"] == 0

    def test_export_json_structure(self, populated_store, tmp_path):
        export_path = str(tmp_path / "episodes.json")
        populated_store.export_json(export_path)
        
        with open(export_path) as f:
            data = json.load(f)
        
        assert data["version"] == "1.0"
        assert data["format"] == "emata_episodes"
        assert data["episode_count"] == populated_store.size
        assert len(data["episodes"]) == populated_store.size


class TestEpisodeStoreStatistics:
    def test_statistics_empty(self):
        store = EpisodeStore()
        stats = store.get_statistics()
        assert stats["total"] == 0
        assert stats["win_rate"] == 0.0

    def test_statistics_populated(self, populated_store):
        stats = populated_store.get_statistics()
        
        assert stats["total"] == 20
        assert stats["complete"] > 0
        assert 0 <= stats["win_rate"] <= 1
        assert "by_regime" in stats
        assert "by_sector" in stats
        assert "by_action" in stats

    def test_statistics_by_regime(self, populated_store):
        stats = populated_store.get_statistics()
        by_regime = stats["by_regime"]
        
        assert "normal" in by_regime
        assert by_regime["normal"]["count"] > 0


class TestHashEmbedding:
    def test_deterministic(self):
        store = EpisodeStore()
        emb1 = store._hash_embedding("test text")
        emb2 = store._hash_embedding("test text")
        np.testing.assert_array_equal(emb1, emb2)

    def test_different_texts(self):
        store = EpisodeStore()
        emb1 = store._hash_embedding("text one")
        emb2 = store._hash_embedding("text two")
        # Should be different
        assert not np.allclose(emb1, emb2)

    def test_normalized(self):
        store = EpisodeStore()
        emb = store._hash_embedding("some text")
        norm = np.linalg.norm(emb)
        assert abs(norm - 1.0) < 1e-6

    def test_correct_dimension(self):
        store = EpisodeStore()
        emb = store._hash_embedding("test")
        assert emb.shape == (EMBEDDING_DIM,)
