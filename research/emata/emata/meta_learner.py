"""
Meta-Learner — Learning Which Memories Help

Extends Sigil's LearningLoop (learning.py) to track not just
"what happened after a trade" but "which retrieved memories
contributed to good decisions."

This closes the loop:
1. Episodes retrieved → fed to DecisionEngine → decision made
2. Outcome recorded → lesson generated (existing LearningLoop)
3. Meta-learner: Was this a good decision? Which memories helped?
4. Update utility scores of contributing memories

Over time, this creates a self-improving memory system: episodes
that consistently contribute to good decisions get higher utility
scores and are retrieved more often.

Integration point: After LearningLoop.run_weekly_update() in
TradingLoop.run() Step 8.
"""

import numpy as np
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple, Any

from .episode import Episode, RetrievedEpisode, OutcomeRecord
from .episode_store import EpisodeStore


@dataclass
class RetrievalRecord:
    """
    Records which episodes were retrieved for a decision.
    
    Created when EpisodicRetriever.retrieve() is called,
    used later by MetaLearner to credit/penalize memories.
    """
    decision_episode_id: str  # The episode of the decision that was made
    retrieved_episode_ids: List[str]  # Episodes that were retrieved
    retrieval_scores: Dict[str, float]  # episode_id → final_score
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Filled later when outcome is known
    decision_outcome: Optional[float] = None  # pct_return
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_episode_id": self.decision_episode_id,
            "retrieved_episode_ids": self.retrieved_episode_ids,
            "retrieval_scores": self.retrieval_scores,
            "timestamp": self.timestamp.isoformat(),
            "decision_outcome": self.decision_outcome,
        }


@dataclass
class MetaLearnerConfig:
    """Configuration for the meta-learning system."""
    # Credit assignment
    utility_learning_rate: float = 0.2   # EMA alpha for utility updates
    outcome_threshold: float = 1.0       # |return| > this counts as informative
    
    # Attribution model
    attribution_mode: str = "proportional"  # "proportional" | "uniform" | "top_k"
    top_k_for_credit: int = 3              # Only credit top-k if mode="top_k"
    
    # Decay
    utility_decay_rate: float = 0.01  # Slow decay for unused episodes per update
    min_utility: float = 0.05         # Floor for utility scores
    max_utility: float = 0.95         # Ceiling for utility scores


class MetaLearner:
    """
    Tracks and learns which retrieved memories contribute to good decisions.
    
    The meta-learner maintains a log of retrieval records (which memories
    were used for which decisions) and updates utility scores when outcomes
    become known.
    
    Usage:
        meta = MetaLearner(store)
        
        # At retrieval time (in TradingLoop Step 2):
        episodes = retriever.retrieve(context)
        record = meta.log_retrieval(new_episode_id, episodes)
        
        # At learning time (in TradingLoop Step 8):
        meta.update_from_outcome(new_episode_id, outcome_pct=5.2)
    """
    
    def __init__(
        self,
        store: EpisodeStore,
        config: Optional[MetaLearnerConfig] = None,
    ):
        self.store = store
        self.config = config or MetaLearnerConfig()
        self._retrieval_log: Dict[str, RetrievalRecord] = {}  # decision_episode_id → record
    
    def log_retrieval(
        self,
        decision_episode_id: str,
        retrieved: List[RetrievedEpisode],
    ) -> RetrievalRecord:
        """
        Log which episodes were retrieved for a decision.
        Call this right after EpisodicRetriever.retrieve().
        """
        record = RetrievalRecord(
            decision_episode_id=decision_episode_id,
            retrieved_episode_ids=[re.episode.id for re in retrieved],
            retrieval_scores={re.episode.id: re.final_score for re in retrieved},
        )
        self._retrieval_log[decision_episode_id] = record
        return record
    
    def update_from_outcome(
        self,
        decision_episode_id: str,
        outcome_pct: float,
    ) -> Dict[str, float]:
        """
        Update utility scores of retrieved memories based on decision outcome.
        
        Credit assignment logic:
        - If outcome is good (> threshold): retrieved memories get credit
        - If outcome is bad (< -threshold): retrieved memories get penalized
        - If outcome is neutral: no significant update
        
        Returns dict of episode_id → new utility score.
        """
        record = self._retrieval_log.get(decision_episode_id)
        if not record:
            return {}
        
        record.decision_outcome = outcome_pct
        cfg = self.config
        
        # Determine credit signal
        if abs(outcome_pct) < cfg.outcome_threshold:
            # Neutral outcome — weak signal
            signal = 0.5
        elif outcome_pct > 0:
            # Good outcome — credit memories
            signal = min(0.5 + outcome_pct / 20.0, 1.0)
        else:
            # Bad outcome — penalize memories
            signal = max(0.5 + outcome_pct / 20.0, 0.0)
        
        # Compute attribution weights
        attribution = self._compute_attribution(record)
        
        # Update utility scores
        updates = {}
        for ep_id, weight in attribution.items():
            episode = self.store.get(ep_id)
            if episode is None:
                continue
            
            # Weighted signal: higher-ranked memories get more credit/blame
            weighted_signal = signal * weight + 0.5 * (1 - weight)
            
            # EMA update
            was_helpful = outcome_pct > cfg.outcome_threshold
            self.store.record_retrieval(ep_id, was_helpful)
            
            # Additional utility update (beyond record_retrieval's binary signal)
            old_utility = episode.utility_score
            new_utility = (
                cfg.utility_learning_rate * weighted_signal +
                (1 - cfg.utility_learning_rate) * old_utility
            )
            new_utility = np.clip(new_utility, cfg.min_utility, cfg.max_utility)
            episode.utility_score = new_utility
            updates[ep_id] = new_utility
        
        return updates
    
    def _compute_attribution(
        self, record: RetrievalRecord
    ) -> Dict[str, float]:
        """
        Compute how much credit/blame each retrieved memory gets.
        
        Three modes:
        - proportional: Credit proportional to retrieval score
        - uniform: Equal credit to all retrieved memories
        - top_k: Only credit the top-k most relevant memories
        """
        cfg = self.config
        scores = record.retrieval_scores
        
        if not scores:
            return {}
        
        if cfg.attribution_mode == "uniform":
            weight = 1.0 / len(scores)
            return {ep_id: weight for ep_id in scores}
        
        elif cfg.attribution_mode == "top_k":
            # Only credit top-k
            sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
            top_ids = sorted_ids[:cfg.top_k_for_credit]
            total = sum(scores[eid] for eid in top_ids)
            if total == 0:
                return {eid: 1.0 / len(top_ids) for eid in top_ids}
            return {eid: scores[eid] / total for eid in top_ids}
        
        else:  # proportional (default)
            total = sum(scores.values())
            if total == 0:
                return {ep_id: 1.0 / len(scores) for ep_id in scores}
            return {ep_id: s / total for ep_id, s in scores.items()}
    
    def decay_unused(self):
        """
        Apply slow utility decay to episodes not retrieved recently.
        
        Called periodically (e.g., weekly) to prevent stale episodes
        from maintaining artificially high utility.
        """
        cfg = self.config
        recently_retrieved = set()
        for record in self._retrieval_log.values():
            recently_retrieved.update(record.retrieved_episode_ids)
        
        for episode in self.store.get_all():
            if episode.id not in recently_retrieved:
                episode.utility_score = max(
                    cfg.min_utility,
                    episode.utility_score * (1 - cfg.utility_decay_rate)
                )
    
    def get_utility_distribution(self) -> Dict[str, Any]:
        """Get statistics about utility score distribution."""
        utilities = [
            ep.utility_score for ep in self.store.get_all()
            if ep.times_retrieved > 0
        ]
        
        if not utilities:
            return {"count": 0}
        
        return {
            "count": len(utilities),
            "mean": float(np.mean(utilities)),
            "median": float(np.median(utilities)),
            "std": float(np.std(utilities)),
            "min": float(np.min(utilities)),
            "max": float(np.max(utilities)),
            "high_utility_count": sum(1 for u in utilities if u > 0.7),
            "low_utility_count": sum(1 for u in utilities if u < 0.3),
        }
    
    def get_most_useful_episodes(self, k: int = 10) -> List[Episode]:
        """Get episodes with highest utility scores."""
        episodes = [ep for ep in self.store.get_all() if ep.times_retrieved > 0]
        episodes.sort(key=lambda e: e.utility_score, reverse=True)
        return episodes[:k]
    
    def get_retrieval_log_stats(self) -> Dict[str, Any]:
        """Get statistics about the retrieval log."""
        records = list(self._retrieval_log.values())
        
        if not records:
            return {"total_records": 0}
        
        with_outcomes = [r for r in records if r.decision_outcome is not None]
        
        return {
            "total_records": len(records),
            "with_outcomes": len(with_outcomes),
            "avg_retrieved_per_decision": float(
                np.mean([len(r.retrieved_episode_ids) for r in records])
            ),
            "avg_outcome": float(
                np.mean([r.decision_outcome for r in with_outcomes])
            ) if with_outcomes else 0.0,
        }
