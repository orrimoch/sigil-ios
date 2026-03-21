"""
Unit tests for MetaLearner.
"""
import pytest
import numpy as np

from emata.meta_learner import MetaLearner, MetaLearnerConfig, RetrievalRecord
from emata.episode import RetrievedEpisode, ContextSnapshot
from emata.retriever import EpisodicRetriever, RetrieverConfig
from emata.episode_store import EpisodeStore


class TestMetaLearner:
    def test_log_retrieval(self, populated_store, sample_context):
        retriever = EpisodicRetriever(populated_store)
        meta = MetaLearner(populated_store)
        
        episodes = retriever.retrieve(sample_context, k=5)
        record = meta.log_retrieval("decision_1", episodes)
        
        assert record.decision_episode_id == "decision_1"
        assert len(record.retrieved_episode_ids) == len(episodes)
        assert record.decision_outcome is None

    def test_update_positive_outcome(self, populated_store, sample_context):
        retriever = EpisodicRetriever(populated_store)
        meta = MetaLearner(populated_store)
        
        episodes = retriever.retrieve(sample_context, k=5)
        meta.log_retrieval("decision_1", episodes)
        
        # Record positive outcome
        updates = meta.update_from_outcome("decision_1", outcome_pct=8.5)
        
        assert len(updates) > 0
        # All utility scores should be updated
        for ep_id, utility in updates.items():
            assert 0 < utility < 1

    def test_update_negative_outcome(self, populated_store, sample_context):
        retriever = EpisodicRetriever(populated_store)
        meta = MetaLearner(populated_store)
        
        episodes = retriever.retrieve(sample_context, k=5)
        meta.log_retrieval("decision_1", episodes)
        
        # Record negative outcome
        updates = meta.update_from_outcome("decision_1", outcome_pct=-10.0)
        
        # Should still have updates
        assert len(updates) > 0

    def test_positive_outcome_increases_utility(self, populated_store, sample_context):
        retriever = EpisodicRetriever(populated_store)
        meta = MetaLearner(populated_store)
        
        episodes = retriever.retrieve(sample_context, k=5)
        
        # Get initial utility
        initial_utilities = {
            re.episode.id: re.episode.utility_score for re in episodes
        }
        
        meta.log_retrieval("decision_1", episodes)
        updates = meta.update_from_outcome("decision_1", outcome_pct=15.0)
        
        # Utility should increase for at least some episodes
        increased = sum(
            1 for ep_id, new_util in updates.items()
            if new_util > initial_utilities.get(ep_id, 0)
        )
        assert increased > 0

    def test_neutral_outcome_weak_signal(self, populated_store, sample_context):
        retriever = EpisodicRetriever(populated_store)
        config = MetaLearnerConfig(outcome_threshold=1.0)
        meta = MetaLearner(populated_store, config)
        
        episodes = retriever.retrieve(sample_context, k=5)
        initial = {re.episode.id: re.episode.utility_score for re in episodes}
        
        meta.log_retrieval("decision_1", episodes)
        updates = meta.update_from_outcome("decision_1", outcome_pct=0.3)
        
        # Neutral outcome should barely change utilities
        for ep_id, new_util in updates.items():
            old_util = initial.get(ep_id, 0)
            assert abs(new_util - old_util) < 0.2  # Small change

    def test_update_nonexistent_decision(self, populated_store):
        meta = MetaLearner(populated_store)
        updates = meta.update_from_outcome("nonexistent", outcome_pct=5.0)
        assert updates == {}


class TestAttributionModes:
    def test_proportional_attribution(self, populated_store, sample_context):
        retriever = EpisodicRetriever(populated_store)
        config = MetaLearnerConfig(attribution_mode="proportional")
        meta = MetaLearner(populated_store, config)
        
        episodes = retriever.retrieve(sample_context, k=5)
        meta.log_retrieval("d1", episodes)
        
        record = meta._retrieval_log["d1"]
        attribution = meta._compute_attribution(record)
        
        # Weights should sum to ~1.0
        total = sum(attribution.values())
        assert abs(total - 1.0) < 1e-6
        
        # Higher-scored episodes should get more credit
        if len(attribution) >= 2:
            sorted_items = sorted(attribution.items(), key=lambda x: x[1], reverse=True)
            assert sorted_items[0][1] >= sorted_items[-1][1]

    def test_uniform_attribution(self, populated_store, sample_context):
        retriever = EpisodicRetriever(populated_store)
        config = MetaLearnerConfig(attribution_mode="uniform")
        meta = MetaLearner(populated_store, config)
        
        episodes = retriever.retrieve(sample_context, k=5)
        meta.log_retrieval("d1", episodes)
        
        record = meta._retrieval_log["d1"]
        attribution = meta._compute_attribution(record)
        
        # All weights should be equal
        weights = list(attribution.values())
        if weights:
            expected = 1.0 / len(weights)
            for w in weights:
                assert abs(w - expected) < 1e-6

    def test_top_k_attribution(self, populated_store, sample_context):
        retriever = EpisodicRetriever(populated_store)
        config = MetaLearnerConfig(attribution_mode="top_k", top_k_for_credit=3)
        meta = MetaLearner(populated_store, config)
        
        episodes = retriever.retrieve(sample_context, k=5)
        meta.log_retrieval("d1", episodes)
        
        record = meta._retrieval_log["d1"]
        attribution = meta._compute_attribution(record)
        
        # Only top-3 should have credit
        assert len(attribution) <= 3


class TestUtilityDecay:
    def test_decay_reduces_unused(self, populated_store, sample_context):
        retriever = EpisodicRetriever(populated_store)
        meta = MetaLearner(populated_store)
        
        # Set some episodes to high utility
        for ep in populated_store.get_all()[:5]:
            ep.utility_score = 0.9
            ep.times_retrieved = 1
        
        # Retrieve only a few (others become "unused")
        episodes = retriever.retrieve(sample_context, k=3)
        meta.log_retrieval("d1", episodes)
        
        # Decay
        meta.decay_unused()
        
        # Unused episodes should have lower utility
        retrieved_ids = {re.episode.id for re in episodes}
        for ep in populated_store.get_all()[:5]:
            if ep.id not in retrieved_ids and ep.times_retrieved > 0:
                assert ep.utility_score < 0.9


class TestMetaLearnerStats:
    def test_utility_distribution_empty(self, populated_store):
        meta = MetaLearner(populated_store)
        dist = meta.get_utility_distribution()
        assert dist["count"] == 0

    def test_utility_distribution_after_updates(self, populated_store, sample_context):
        retriever = EpisodicRetriever(populated_store)
        meta = MetaLearner(populated_store)
        
        episodes = retriever.retrieve(sample_context, k=5)
        meta.log_retrieval("d1", episodes)
        meta.update_from_outcome("d1", outcome_pct=5.0)
        
        dist = meta.get_utility_distribution()
        assert dist["count"] > 0
        assert "mean" in dist
        assert "std" in dist

    def test_retrieval_log_stats(self, populated_store, sample_context):
        retriever = EpisodicRetriever(populated_store)
        meta = MetaLearner(populated_store)
        
        for i in range(5):
            eps = retriever.retrieve(sample_context, k=3)
            meta.log_retrieval(f"d{i}", eps)
            meta.update_from_outcome(f"d{i}", outcome_pct=float(i - 2) * 3)
        
        stats = meta.get_retrieval_log_stats()
        assert stats["total_records"] == 5
        assert stats["with_outcomes"] == 5
        assert stats["avg_retrieved_per_decision"] == 3

    def test_most_useful_episodes(self, populated_store, sample_context):
        retriever = EpisodicRetriever(populated_store)
        meta = MetaLearner(populated_store)
        
        # Multiple positive outcomes
        for i in range(5):
            eps = retriever.retrieve(sample_context, k=5)
            meta.log_retrieval(f"d{i}", eps)
            meta.update_from_outcome(f"d{i}", outcome_pct=10.0)
        
        useful = meta.get_most_useful_episodes(k=3)
        assert len(useful) <= 3
        # Should be sorted by utility
        if len(useful) >= 2:
            assert useful[0].utility_score >= useful[1].utility_score
