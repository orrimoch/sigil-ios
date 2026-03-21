"""
Episode Store — In-Memory Episodic Memory Backend

Research implementation using in-memory storage with numpy.
Production Sigil integration would extend AgentMemory (memory.py)
with PostgreSQL + pgvector.

This is the storage layer. It handles:
1. Episode storage with embedding generation
2. Fast nearest-neighbor retrieval via numpy (no DB dependency)
3. Outcome tracking and lesson attachment
4. Import/export for evaluation

Design decisions:
- In-memory for research speed (no PostgreSQL dependency)
- Hash-based pseudo-embeddings for testing (matches memory.py's _hash_embedding)
- Numpy cosine similarity (matches pgvector's <=> operator semantics)
"""

import json
import hashlib
import numpy as np
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any, Tuple

from .episode import Episode, DecisionRecord, ContextSnapshot, OutcomeRecord

# Match Sigil's embedding dimension
EMBEDDING_DIM = 1536


class EpisodeStore:
    """
    In-memory episode store for research.
    
    Production equivalent: Extends AgentMemory with episode-aware
    storage and retrieval. Would use:
    - PostgreSQL + pgvector for embeddings (already in memory.py)
    - Additional columns for context snapshot features
    - Materialized views for regime/sector filtering
    """
    
    def __init__(self, embedding_dim: int = EMBEDDING_DIM):
        self.embedding_dim = embedding_dim
        self._episodes: Dict[str, Episode] = {}  # id → Episode
        self._embeddings: Optional[np.ndarray] = None  # N x dim matrix
        self._episode_ids: List[str] = []  # Ordered list of IDs matching _embeddings rows
        self._dirty = True  # Embeddings matrix needs rebuild
    
    @property
    def size(self) -> int:
        return len(self._episodes)
    
    @property
    def complete_count(self) -> int:
        """Episodes with outcomes."""
        return sum(1 for e in self._episodes.values() if e.is_complete)
    
    def store(self, episode: Episode) -> str:
        """
        Store an episode, generating embedding if missing.
        
        Returns the episode ID.
        """
        if not episode.has_embedding:
            episode.embedding = self._generate_embedding(episode)
        
        self._episodes[episode.id] = episode
        self._dirty = True
        return episode.id
    
    def store_batch(self, episodes: List[Episode]) -> List[str]:
        """Store multiple episodes efficiently."""
        ids = []
        for ep in episodes:
            ids.append(self.store(ep))
        return ids
    
    def get(self, episode_id: str) -> Optional[Episode]:
        """Get episode by ID."""
        return self._episodes.get(episode_id)
    
    def get_all(self) -> List[Episode]:
        """Get all episodes."""
        return list(self._episodes.values())
    
    def get_complete(self) -> List[Episode]:
        """Get episodes with outcomes."""
        return [e for e in self._episodes.values() if e.is_complete]
    
    def update_outcome(
        self,
        episode_id: str,
        outcome: OutcomeRecord,
        lesson: str = "",
    ) -> bool:
        """
        Update episode with outcome and lesson.
        
        Maps to: AgentMemory.update_outcome() + AgentMemory.store_lesson()
        """
        episode = self._episodes.get(episode_id)
        if not episode:
            return False
        
        episode.outcome = outcome
        if lesson:
            episode.lesson = lesson
        return True
    
    def record_retrieval(
        self,
        episode_id: str,
        was_helpful: bool,
    ):
        """
        Record that an episode was retrieved and whether it helped.
        
        This is the meta-learning signal: over time, episodes that
        consistently help decisions get boosted in retrieval ranking.
        """
        episode = self._episodes.get(episode_id)
        if not episode:
            return
        
        episode.times_retrieved += 1
        if was_helpful:
            episode.times_helpful += 1
        
        # Update utility score (exponential moving average)
        alpha = 0.3  # Learning rate for utility updates
        signal = 1.0 if was_helpful else 0.0
        episode.utility_score = (
            alpha * signal + (1 - alpha) * episode.utility_score
        )
    
    def find_nearest(
        self,
        query_embedding: np.ndarray,
        k: int = 10,
        only_complete: bool = True,
        regime_filter: Optional[str] = None,
        sector_filter: Optional[str] = None,
    ) -> List[Tuple[str, float]]:
        """
        Find k nearest episodes by embedding cosine similarity.
        
        Returns list of (episode_id, similarity_score) tuples.
        
        Maps to: AgentMemory.retrieve_similar() but with optional
        pre-filtering by regime and sector.
        """
        self._rebuild_index()
        
        if self._embeddings is None or len(self._embeddings) == 0:
            return []
        
        # Get candidate IDs (pre-filter)
        candidates = self._get_candidates(only_complete, regime_filter, sector_filter)
        if not candidates:
            return []
        
        # Build filtered embedding matrix
        candidate_indices = [self._episode_ids.index(cid) for cid in candidates if cid in self._episode_ids]
        if not candidate_indices:
            return []
        
        filtered_embeddings = self._embeddings[candidate_indices]
        filtered_ids = [self._episode_ids[i] for i in candidate_indices]
        
        # Cosine similarity (matches pgvector's 1 - (embedding <=> query))
        query_norm = query_embedding / (np.linalg.norm(query_embedding) + 1e-8)
        emb_norms = filtered_embeddings / (
            np.linalg.norm(filtered_embeddings, axis=1, keepdims=True) + 1e-8
        )
        similarities = emb_norms @ query_norm
        
        # Sort by similarity (descending)
        top_indices = np.argsort(similarities)[::-1][:k]
        
        results = []
        for idx in top_indices:
            results.append((filtered_ids[idx], float(similarities[idx])))
        
        return results
    
    def _get_candidates(
        self,
        only_complete: bool,
        regime_filter: Optional[str],
        sector_filter: Optional[str],
    ) -> List[str]:
        """Get candidate episode IDs matching filters."""
        candidates = []
        for eid, ep in self._episodes.items():
            if only_complete and not ep.is_complete:
                continue
            if regime_filter and ep.context.regime != regime_filter:
                continue
            if sector_filter and ep.context.sector != sector_filter:
                continue
            candidates.append(eid)
        return candidates
    
    def _rebuild_index(self):
        """Rebuild the embedding matrix if dirty."""
        if not self._dirty:
            return
        
        self._episode_ids = []
        embeddings = []
        
        for eid, ep in self._episodes.items():
            if ep.has_embedding:
                self._episode_ids.append(eid)
                embeddings.append(ep.embedding)
        
        if embeddings:
            self._embeddings = np.stack(embeddings)
        else:
            self._embeddings = np.empty((0, self.embedding_dim))
        
        self._dirty = False
    
    def _generate_embedding(self, episode: Episode) -> np.ndarray:
        """
        Generate pseudo-embedding for testing.
        
        Uses the same hash-based approach as AgentMemory._hash_embedding()
        for consistency. In production, would use OpenAI text-embedding-3-small.
        """
        text = episode.to_embedding_text()
        return self._hash_embedding(text)
    
    def _hash_embedding(self, text: str) -> np.ndarray:
        """
        Deterministic pseudo-embedding from text.
        Matches AgentMemory._hash_embedding() exactly.
        """
        hash_bytes = hashlib.sha256(text.encode()).digest()
        
        embeddings = []
        seed = hash_bytes
        
        while len(embeddings) < self.embedding_dim:
            for i in range(32):
                if len(embeddings) >= self.embedding_dim:
                    break
                val = (seed[i % len(seed)] - 128) / 128.0
                embeddings.append(val)
            seed = hashlib.sha256(seed).digest()
        
        arr = np.array(embeddings[:self.embedding_dim])
        arr = arr / (np.linalg.norm(arr) + 1e-8)
        return arr
    
    # === Import/Export (matches AgentMemory.import_memories/export_memories) ===
    
    def export_json(self, path: str):
        """Export all episodes to JSON."""
        data = {
            "version": "1.0",
            "format": "emata_episodes",
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "episode_count": self.size,
            "complete_count": self.complete_count,
            "episodes": [ep.to_dict() for ep in self._episodes.values()],
        }
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def import_json(self, path: str) -> Dict[str, int]:
        """Import episodes from JSON. Returns import stats."""
        with open(path) as f:
            data = json.load(f)
        
        stats = {"imported": 0, "skipped": 0}
        
        for ep_data in data.get("episodes", []):
            episode = Episode.from_dict(ep_data)
            if episode.id in self._episodes:
                stats["skipped"] += 1
            else:
                self.store(episode)
                stats["imported"] += 1
        
        return stats
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get store statistics. Maps to AgentMemory.get_statistics()."""
        episodes = list(self._episodes.values())
        complete = [e for e in episodes if e.is_complete]
        
        if not complete:
            return {
                "total": self.size,
                "complete": 0,
                "pending": self.size,
                "win_rate": 0.0,
                "avg_return": 0.0,
                "avg_utility": 0.0,
            }
        
        outcomes = [e.outcome.pct_return for e in complete]
        wins = sum(1 for o in outcomes if o > 0)
        
        return {
            "total": self.size,
            "complete": len(complete),
            "pending": self.size - len(complete),
            "win_rate": wins / len(complete),
            "avg_return": float(np.mean(outcomes)),
            "median_return": float(np.median(outcomes)),
            "std_return": float(np.std(outcomes)),
            "avg_utility": float(np.mean([e.utility_score for e in complete])),
            "by_regime": self._stats_by_field(complete, lambda e: e.context.regime),
            "by_sector": self._stats_by_field(complete, lambda e: e.context.sector),
            "by_action": self._stats_by_field(complete, lambda e: e.decision.action),
        }
    
    def _stats_by_field(self, episodes: List[Episode], key_fn) -> Dict[str, Dict]:
        """Group statistics by a field."""
        groups = {}
        for ep in episodes:
            k = key_fn(ep)
            if k not in groups:
                groups[k] = []
            groups[k].append(ep.outcome.pct_return)
        
        return {
            k: {
                "count": len(v),
                "avg_return": float(np.mean(v)),
                "win_rate": sum(1 for x in v if x > 0) / len(v),
            }
            for k, v in groups.items()
        }
