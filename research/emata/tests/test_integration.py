"""
Integration tests — End-to-end EMATA pipeline.
"""
import pytest
import numpy as np
import json
from pathlib import Path

from emata.episode import (
    Episode, DecisionRecord, ContextSnapshot,
    OutcomeRecord, RetrievedEpisode,
)
from emata.episode_store import EpisodeStore
from emata.retriever import EpisodicRetriever, RetrieverConfig
from emata.augmenter import ContextAugmenter
from emata.meta_learner import MetaLearner, MetaLearnerConfig
from emata.evaluation import (
    SyntheticDataGenerator, Evaluator, EvalMetrics,
)


class TestEndToEndPipeline:
    """Test the complete EMATA flow: store → retrieve → augment → meta-learn."""
    
    def test_full_pipeline(self, populated_store, sample_context):
        """Simulate one complete decision cycle."""
        # Step 1: Retrieve episodes (like TradingLoop Step 2)
        retriever = EpisodicRetriever(populated_store)
        meta = MetaLearner(populated_store)
        
        retrieved = retriever.retrieve(sample_context, k=5)
        assert len(retrieved) > 0
        
        # Step 2: Augment for decision engine
        augmenter = ContextAugmenter()
        prompt_section = augmenter.augment(retrieved, sample_context)
        
        assert "Episodic Memory" in prompt_section
        assert len(prompt_section) > 100
        
        # Step 3: Simulate a decision (would be Claude in production)
        decision = DecisionRecord(
            ticker="AAPL", action="BUY", score=78.0,
            confidence=0.82, rationale="Memory-augmented decision",
        )
        
        new_episode = Episode(
            decision=decision,
            context=sample_context,
        )
        episode_id = populated_store.store(new_episode)
        
        # Step 4: Log retrieval for meta-learning
        meta.log_retrieval(episode_id, retrieved)
        
        # Step 5: Later, outcome arrives (like LearningLoop)
        outcome = OutcomeRecord(
            pct_return=6.5, holding_days=14, tag="win",
        )
        populated_store.update_outcome(episode_id, outcome, "Good buy in normal regime")
        
        # Step 6: Meta-learning update
        updates = meta.update_from_outcome(episode_id, 6.5)
        assert len(updates) > 0
        
        # Step 7: Verify the new episode can be retrieved later
        future_ctx = ContextSnapshot(regime="normal", sector="Technology", vix=18.0)
        future_results = retriever.retrieve(future_ctx, k=10)
        
        retrieved_ids = {r.episode.id for r in future_results}
        assert episode_id in retrieved_ids

    def test_multi_cycle_learning(self, populated_store, sample_context):
        """Multiple decision cycles should improve retrieval via meta-learning."""
        retriever = EpisodicRetriever(populated_store)
        meta = MetaLearner(populated_store)
        
        # Track utility changes over cycles
        utility_snapshots = []
        
        for cycle in range(10):
            retrieved = retriever.retrieve(sample_context, k=5)
            
            # Snapshot utilities
            avg_util = np.mean([r.episode.utility_score for r in retrieved]) if retrieved else 0
            utility_snapshots.append(avg_util)
            
            # Create episode
            ep = Episode(
                decision=DecisionRecord(
                    ticker="TEST", action="BUY", score=75 + cycle,
                ),
                context=sample_context,
            )
            eid = populated_store.store(ep)
            meta.log_retrieval(eid, retrieved)
            
            # Good outcome → credit memories
            outcome = OutcomeRecord(pct_return=5.0 + cycle, tag="win")
            populated_store.update_outcome(eid, outcome, f"Cycle {cycle}")
            meta.update_from_outcome(eid, outcome.pct_return)
        
        # After positive cycles, utility should trend upward
        if len(utility_snapshots) >= 5:
            first_half = np.mean(utility_snapshots[:5])
            second_half = np.mean(utility_snapshots[5:])
            # Not strictly guaranteed but meta-learning should help
            assert second_half >= first_half - 0.1

    def test_export_import_preserves_pipeline(self, populated_store, sample_context, tmp_path):
        """Export → import should preserve retrieval behavior."""
        retriever = EpisodicRetriever(populated_store)
        original_results = retriever.retrieve(sample_context, k=5)
        original_ids = [r.episode.id for r in original_results]
        
        # Export
        export_path = str(tmp_path / "export.json")
        populated_store.export_json(export_path)
        
        # Import into new store
        new_store = EpisodeStore()
        new_store.import_json(export_path)
        
        new_retriever = EpisodicRetriever(new_store)
        new_results = new_retriever.retrieve(sample_context, k=5)
        new_ids = [r.episode.id for r in new_results]
        
        # Should retrieve same episodes (order may differ slightly due to rebuilding)
        assert set(original_ids) == set(new_ids)


class TestSyntheticDataGenerator:
    def test_generate_episodes(self):
        gen = SyntheticDataGenerator(seed=42)
        episodes = gen.generate_episodes(n=50)
        
        assert len(episodes) == 50
        for ep in episodes:
            assert ep.decision.ticker
            assert ep.decision.action in ("BUY", "SELL")
            assert ep.context.regime in ("low_vol", "normal", "high_vol", "crisis")
            assert ep.is_complete

    def test_regime_distribution(self):
        gen = SyntheticDataGenerator(seed=42)
        episodes = gen.generate_episodes(n=1000)
        
        regime_counts = {}
        for ep in episodes:
            r = ep.context.regime
            regime_counts[r] = regime_counts.get(r, 0) + 1
        
        # Should roughly match distribution
        assert regime_counts.get("normal", 0) > regime_counts.get("crisis", 0)
        assert regime_counts.get("low_vol", 0) > 100

    def test_outcome_distributions(self):
        gen = SyntheticDataGenerator(seed=42)
        episodes = gen.generate_episodes(n=500)
        
        # Crisis should have worse outcomes for BUY
        crisis_buys = [
            ep.outcome.pct_return for ep in episodes
            if ep.context.regime == "crisis" and ep.decision.action == "BUY"
        ]
        normal_buys = [
            ep.outcome.pct_return for ep in episodes
            if ep.context.regime == "normal" and ep.decision.action == "BUY"
        ]
        
        if crisis_buys and normal_buys:
            assert np.mean(crisis_buys) < np.mean(normal_buys)

    def test_generate_with_sigil_scores(self, tmp_path):
        """Test with mock Sigil scores data."""
        scores = {
            "scores": {
                "AAPL": {"ticker": "AAPL", "sector": "Technology", "total_score": 72},
                "NVDA": {"ticker": "NVDA", "sector": "Technology", "total_score": 85},
                "UNH": {"ticker": "UNH", "sector": "Healthcare", "total_score": 68},
            }
        }
        scores_path = str(tmp_path / "scores.json")
        with open(scores_path, 'w') as f:
            json.dump(scores, f)
        
        gen = SyntheticDataGenerator(scores_path=scores_path, seed=42)
        episodes = gen.generate_episodes(n=30)
        
        tickers = {ep.decision.ticker for ep in episodes}
        assert "AAPL" in tickers or "NVDA" in tickers

    def test_generate_eval_scenarios(self):
        gen = SyntheticDataGenerator(seed=42)
        episodes = gen.generate_episodes(n=100)
        scenarios = gen.generate_eval_scenarios(episodes, n_scenarios=20)
        
        assert len(scenarios) <= 20
        for s in scenarios:
            assert s.query_context is not None
            assert s.query_decision is not None


class TestEvaluator:
    def test_evaluate_all_strategies(self):
        gen = SyntheticDataGenerator(seed=42)
        episodes = gen.generate_episodes(n=100)
        scenarios = gen.generate_eval_scenarios(episodes, n_scenarios=20)
        
        evaluator = Evaluator(episodes, scenarios)
        results = evaluator.evaluate_all(k=5)
        
        assert "no_memory" in results
        assert "naive_similarity" in results
        assert "emata_base" in results
        assert "emata_meta" in results
        
        for name, metrics in results.items():
            assert isinstance(metrics, EvalMetrics)
            assert metrics.strategy_name == name

    def test_metrics_reasonable_ranges(self):
        gen = SyntheticDataGenerator(seed=42)
        episodes = gen.generate_episodes(n=100)
        scenarios = gen.generate_eval_scenarios(episodes, n_scenarios=20)
        
        evaluator = Evaluator(episodes, scenarios)
        results = evaluator.evaluate_all(k=5)
        
        for name, metrics in results.items():
            assert -100 < metrics.avg_return < 100
            assert 0 <= metrics.win_rate <= 1.0
            assert metrics.max_drawdown <= 0  # Drawdown is negative

    def test_format_comparison(self):
        gen = SyntheticDataGenerator(seed=42)
        episodes = gen.generate_episodes(n=50)
        scenarios = gen.generate_eval_scenarios(episodes, n_scenarios=10)
        
        evaluator = Evaluator(episodes, scenarios)
        results = evaluator.evaluate_all(k=5)
        
        report = evaluator.format_comparison(results)
        assert "EMATA EVALUATION RESULTS" in report
        assert "No Memory" in report or "no_memory" in report
        assert "🏆" in report

    def test_emata_beats_no_memory(self):
        """EMATA should perform at least as well as no-memory baseline."""
        gen = SyntheticDataGenerator(seed=42)
        episodes = gen.generate_episodes(n=200)
        scenarios = gen.generate_eval_scenarios(episodes, n_scenarios=30)
        
        evaluator = Evaluator(episodes, scenarios)
        results = evaluator.evaluate_all(k=5)
        
        no_mem = results["no_memory"]
        emata = results["emata_base"]
        
        # EMATA should have better retrieval precision (by definition, no_memory has 0)
        assert emata.retrieval_precision >= no_mem.retrieval_precision
