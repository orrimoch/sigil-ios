"""
Unit tests for ContextAugmenter.
"""
import pytest
from emata.augmenter import ContextAugmenter
from emata.episode import RetrievedEpisode, ContextSnapshot
from emata.retriever import EpisodicRetriever, RetrieverConfig
from emata.episode_store import EpisodeStore


class TestContextAugmenter:
    def test_augment_empty(self):
        aug = ContextAugmenter()
        result = aug.augment([])
        assert "No similar past situations" in result

    def test_augment_produces_sections(self, populated_store, sample_context):
        retriever = EpisodicRetriever(populated_store)
        episodes = retriever.retrieve(sample_context, k=5)
        
        aug = ContextAugmenter()
        result = aug.augment(episodes, sample_context)
        
        assert "## Episodic Memory" in result
        assert "Most Relevant Past Decisions" in result
        assert "Outcome Summary" in result

    def test_augment_includes_lessons(self, populated_store, sample_context):
        retriever = EpisodicRetriever(populated_store)
        episodes = retriever.retrieve(sample_context, k=5)
        
        aug = ContextAugmenter()
        result = aug.augment(episodes, sample_context)
        
        # Should include at least one lesson
        assert "💡 Lesson:" in result or "lesson" in result.lower()

    def test_augment_includes_scores(self, populated_store, sample_context):
        retriever = EpisodicRetriever(populated_store)
        episodes = retriever.retrieve(sample_context, k=5)
        
        aug = ContextAugmenter()
        result = aug.augment(episodes, sample_context)
        
        # Should show score components
        assert "F=" in result  # Fundamental
        assert "S=" in result  # Sentiment

    def test_augment_minimal_matches_sigil_format(self, populated_store, sample_context):
        """augment_minimal should match current Sigil format."""
        retriever = EpisodicRetriever(populated_store)
        episodes = retriever.retrieve(sample_context, k=3)
        
        aug = ContextAugmenter()
        result = aug.augment_minimal(episodes)
        
        # Format: "- TICKER (ACTION): Score X, Regime Y → Z% (similarity: N%)"
        assert "Score" in result
        assert "Regime" in result
        assert "similarity:" in result

    def test_regime_guidance_generated(self, populated_store, sample_context):
        retriever = EpisodicRetriever(populated_store)
        episodes = retriever.retrieve(sample_context, k=10)
        
        aug = ContextAugmenter(include_regime_guidance=True)
        result = aug.augment(episodes, sample_context)
        
        # Should have regime section if enough episodes match
        if any(r.regime_match for r in episodes):
            assert "Regime Guidance" in result or "regime" in result.lower()

    def test_confidence_calibration(self, populated_store, sample_context):
        retriever = EpisodicRetriever(populated_store)
        episodes = retriever.retrieve(sample_context, k=10)
        
        aug = ContextAugmenter(include_confidence_calibration=True)
        result = aug.augment(episodes, sample_context)
        
        assert "Memory Confidence" in result
        assert any(level in result for level in ["HIGH", "MEDIUM", "LOW"])

    def test_outcome_summary_win_loss(self, populated_store, sample_context):
        retriever = EpisodicRetriever(populated_store)
        episodes = retriever.retrieve(sample_context, k=10)
        
        aug = ContextAugmenter()
        result = aug.augment(episodes, sample_context)
        
        # Should show win/loss categories
        assert "Successful" in result or "Unsuccessful" in result or "win rate" in result.lower()

    def test_pattern_detection(self, populated_store, sample_context):
        retriever = EpisodicRetriever(populated_store)
        episodes = retriever.retrieve(sample_context, k=10)
        
        aug = ContextAugmenter(include_pattern_analysis=True)
        result = aug.augment(episodes, sample_context)
        
        # Patterns section may or may not appear depending on data
        # Just verify it doesn't crash
        assert isinstance(result, str)

    def test_augment_disabled_sections(self, populated_store, sample_context):
        retriever = EpisodicRetriever(populated_store)
        episodes = retriever.retrieve(sample_context, k=5)
        
        aug = ContextAugmenter(
            include_pattern_analysis=False,
            include_regime_guidance=False,
            include_confidence_calibration=False,
        )
        result = aug.augment(episodes, sample_context)
        
        assert "Patterns" not in result
        assert "Memory Confidence" not in result


class TestAugmenterEdgeCases:
    def test_single_episode(self, make_episode):
        store = EpisodeStore()
        ep = make_episode()
        store.store(ep)
        
        retriever = EpisodicRetriever(store)
        sample_ctx = ContextSnapshot(regime="normal", sector="Technology")
        episodes = retriever.retrieve(sample_ctx, k=1)
        
        aug = ContextAugmenter()
        result = aug.augment(episodes, sample_ctx)
        assert isinstance(result, str)
        assert "Episodic Memory" in result

    def test_all_losses(self, make_episode):
        store = EpisodeStore()
        for i in range(5):
            ep = make_episode(
                ticker=f"STOCK{i}", outcome_pct=-(i + 1) * 2,
                lesson=f"Loss lesson {i}",
            )
            store.store(ep)
        
        retriever = EpisodicRetriever(store)
        ctx = ContextSnapshot(regime="normal", sector="Technology")
        episodes = retriever.retrieve(ctx, k=5)
        
        aug = ContextAugmenter()
        result = aug.augment(episodes, ctx)
        assert "Unsuccessful" in result or "❌" in result
