"""
Episodic Retriever — Multi-Dimensional Memory Retrieval

This is the core EMATA innovation over Sigil's current approach.

Current Sigil (memory.py):
    retrieve_similar(context, k=10) → pure embedding cosine similarity

EMATA retriever:
    retrieve(query_context, k=10) → weighted combination of:
    1. Embedding similarity (semantic similarity of decision context)
    2. Structured context similarity (regime, VIX, scores feature vector)
    3. Regime match bonus (same regime → higher relevance)
    4. Sector match bonus (same sector → higher relevance)
    5. Outcome quality weighting (informative outcomes rank higher)
    6. Meta-learning utility (episodes that helped before rank higher)

The retriever replaces the single pgvector query with a multi-stage
retrieval pipeline that produces better-ranked episodes for the
DecisionEngine prompt.

Integration point: Slots between memory.retrieve_similar() and
decision_engine._build_prompt() in trading_loop.py Step 2.
"""

import numpy as np
from dataclasses import dataclass
from typing import List, Optional, Dict, Any

from .episode import Episode, ContextSnapshot, RetrievedEpisode
from .episode_store import EpisodeStore


@dataclass
class RetrieverConfig:
    """
    Weights for multi-dimensional retrieval scoring.
    
    These are the hyperparameters that control retrieval behavior.
    Tunable via the evaluation framework.
    """
    # Similarity dimension weights (must sum to 1.0)
    w_embedding: float = 0.40     # Semantic similarity weight
    w_context: float = 0.25       # Structured feature similarity weight
    w_regime_bonus: float = 0.15  # Regime match bonus weight
    w_sector_bonus: float = 0.10  # Sector match bonus weight
    w_utility: float = 0.10       # Meta-learning utility weight
    
    # Outcome weighting
    outcome_informativeness_weight: float = 0.3  # How much outcome magnitude matters
    prefer_diverse_outcomes: bool = True  # Include both wins and losses?
    
    # Retrieval parameters
    candidate_pool_multiplier: int = 3  # Fetch 3x k candidates, then re-rank
    min_similarity_threshold: float = 0.1  # Minimum combined score to include
    
    # Diversity controls
    max_same_ticker: int = 2  # Max episodes from same ticker
    max_same_regime: int = -1  # -1 = no limit
    
    def validate(self):
        """Ensure weights sum to 1.0."""
        total = (
            self.w_embedding + self.w_context + 
            self.w_regime_bonus + self.w_sector_bonus + self.w_utility
        )
        assert abs(total - 1.0) < 1e-6, f"Weights sum to {total}, expected 1.0"


class EpisodicRetriever:
    """
    Multi-dimensional episodic memory retriever.
    
    Replaces AgentMemory.retrieve_similar() with a richer retrieval
    pipeline that considers multiple dimensions of similarity.
    
    Usage:
        store = EpisodeStore()
        retriever = EpisodicRetriever(store)
        
        # At decision time (in TradingLoop.run, Step 2):
        query_context = ContextSnapshot.from_trading_context(context)
        episodes = retriever.retrieve(query_context, k=10)
        
        # Feed to DecisionEngine via ContextAugmenter
    """
    
    def __init__(
        self,
        store: EpisodeStore,
        config: Optional[RetrieverConfig] = None,
    ):
        self.store = store
        self.config = config or RetrieverConfig()
        self.config.validate()
    
    def retrieve(
        self,
        query_context: ContextSnapshot,
        query_embedding: Optional[np.ndarray] = None,
        k: int = 10,
        regime_filter: Optional[str] = None,
        sector_filter: Optional[str] = None,
    ) -> List[RetrievedEpisode]:
        """
        Retrieve the k most relevant episodes for a given context.
        
        Multi-stage pipeline:
        1. Candidate generation: Fetch candidate_pool_multiplier * k by embedding
        2. Multi-dimensional scoring: Score each candidate on all dimensions
        3. Outcome weighting: Adjust for outcome informativeness
        4. Diversity filtering: Ensure result diversity
        5. Final ranking: Return top k
        
        Args:
            query_context: Current trading context snapshot
            query_embedding: Pre-computed embedding (or auto-generated)
            k: Number of episodes to return
            regime_filter: Only return episodes from this regime
            sector_filter: Only return episodes from this sector
            
        Returns:
            List of RetrievedEpisode with all similarity dimensions
        """
        cfg = self.config
        
        # Generate query embedding if not provided
        if query_embedding is None:
            query_embedding = self.store._hash_embedding(
                self._context_to_embedding_text(query_context)
            )
        
        # Stage 1: Candidate generation via embedding similarity
        pool_size = k * cfg.candidate_pool_multiplier
        candidates = self.store.find_nearest(
            query_embedding,
            k=pool_size,
            only_complete=True,
            regime_filter=regime_filter,
            sector_filter=sector_filter,
        )
        
        if not candidates:
            return []
        
        # Stage 2: Multi-dimensional scoring
        query_features = query_context.to_feature_vector()
        scored = []
        
        for episode_id, emb_similarity in candidates:
            episode = self.store.get(episode_id)
            if episode is None:
                continue
            
            # Compute structured context similarity
            ep_features = episode.context.to_feature_vector()
            context_sim = self._feature_similarity(query_features, ep_features)
            
            # Regime and sector match
            regime_match = query_context.regime == episode.context.regime
            sector_match = query_context.sector == episode.context.sector
            
            # Utility score (meta-learning)
            utility = episode.utility_score if episode.times_retrieved > 0 else 0.5  # Prior
            
            # Combined score
            combined = (
                cfg.w_embedding * emb_similarity +
                cfg.w_context * context_sim +
                cfg.w_regime_bonus * (1.0 if regime_match else 0.0) +
                cfg.w_sector_bonus * (1.0 if sector_match else 0.0) +
                cfg.w_utility * utility
            )
            
            # Stage 3: Outcome weighting
            outcome_weight = 1.0
            if episode.outcome:
                # Informative outcomes (large |return|) are more useful
                informativeness = min(abs(episode.outcome.pct_return) / 20.0, 1.0)
                outcome_weight = 1.0 + cfg.outcome_informativeness_weight * informativeness
            
            final_score = combined * outcome_weight
            
            scored.append(RetrievedEpisode(
                episode=episode,
                embedding_similarity=emb_similarity,
                context_similarity=context_sim,
                regime_match=regime_match,
                sector_match=sector_match,
                combined_score=combined,
                outcome_weight=outcome_weight,
                final_score=final_score,
            ))
        
        # Filter by minimum threshold
        scored = [s for s in scored if s.final_score >= cfg.min_similarity_threshold]
        
        # Stage 4: Diversity filtering
        scored = self._apply_diversity(scored)
        
        # Stage 5: Final ranking
        scored.sort(key=lambda x: x.final_score, reverse=True)
        
        # Optionally ensure outcome diversity (mix of wins and losses)
        if cfg.prefer_diverse_outcomes:
            scored = self._ensure_outcome_diversity(scored, k)
        
        return scored[:k]
    
    def _feature_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """
        Compute similarity between two feature vectors.
        Uses 1 - normalized Euclidean distance.
        """
        diff = a - b
        dist = np.sqrt(np.sum(diff ** 2))
        # Normalize: max possible distance for 10-dim [0,1] vectors is sqrt(10) ≈ 3.16
        max_dist = np.sqrt(len(a))
        return max(0.0, 1.0 - dist / max_dist)
    
    def _context_to_embedding_text(self, ctx: ContextSnapshot) -> str:
        """Convert context to text for embedding generation."""
        return (
            f"Regime: {ctx.regime} | VIX: {ctx.vix:.1f} | Trend: {ctx.trend} | "
            f"Cash: {ctx.cash_pct:.0%} | Positions: {ctx.position_count} | "
            f"Fundamental: {ctx.fundamental_score:.0f} | "
            f"Sentiment: {ctx.sentiment_score:.0f} | "
            f"Technical: {ctx.technical_score:.0f} | "
            f"Macro: {ctx.macro_score:.0f} | "
            f"Sector: {ctx.sector}"
        )
    
    def _apply_diversity(
        self, scored: List[RetrievedEpisode]
    ) -> List[RetrievedEpisode]:
        """
        Apply diversity constraints to prevent retrieval of too many
        similar episodes (e.g., all AAPL trades in normal regime).
        """
        cfg = self.config
        
        ticker_counts: Dict[str, int] = {}
        regime_counts: Dict[str, int] = {}
        filtered = []
        
        # Sort by final_score first so we keep the best ones
        scored.sort(key=lambda x: x.final_score, reverse=True)
        
        for s in scored:
            ticker = s.episode.decision.ticker
            regime = s.episode.context.regime
            
            # Check ticker limit
            if cfg.max_same_ticker > 0:
                if ticker_counts.get(ticker, 0) >= cfg.max_same_ticker:
                    continue
            
            # Check regime limit
            if cfg.max_same_regime > 0:
                if regime_counts.get(regime, 0) >= cfg.max_same_regime:
                    continue
            
            ticker_counts[ticker] = ticker_counts.get(ticker, 0) + 1
            regime_counts[regime] = regime_counts.get(regime, 0) + 1
            filtered.append(s)
        
        return filtered
    
    def _ensure_outcome_diversity(
        self,
        scored: List[RetrievedEpisode],
        k: int,
    ) -> List[RetrievedEpisode]:
        """
        Ensure mix of positive and negative outcomes in results.
        
        This prevents retrieval bias: if all retrieved memories are
        wins, the agent might be overconfident. Including losses
        provides balanced evidence.
        
        Target: at least 20% of results should be the minority outcome.
        """
        if len(scored) < 4:
            return scored
        
        positive = [s for s in scored if s.episode.outcome and s.episode.outcome.is_positive]
        negative = [s for s in scored if s.episode.outcome and not s.episode.outcome.is_positive]
        
        if not positive or not negative:
            return scored  # Can't diversify if all same sign
        
        # Target: at least 20% minority
        min_minority = max(1, k // 5)
        
        # Determine majority/minority
        if len(positive) >= len(negative):
            majority, minority = positive, negative
        else:
            majority, minority = negative, positive
        
        # If minority is already well-represented, no change needed
        minority_in_top_k = sum(1 for s in scored[:k] if s in minority)
        if minority_in_top_k >= min_minority:
            return scored
        
        # Interleave: take top majority, insert top minority
        result = []
        maj_idx = 0
        min_idx = 0
        minority_placed = 0
        
        for i in range(min(k, len(scored))):
            # Place minority at evenly spaced positions
            if (minority_placed < min_minority and 
                min_idx < len(minority) and
                (i + 1) % (k // min_minority) == 0):
                result.append(minority[min_idx])
                min_idx += 1
                minority_placed += 1
            elif maj_idx < len(majority):
                result.append(majority[maj_idx])
                maj_idx += 1
            elif min_idx < len(minority):
                result.append(minority[min_idx])
                min_idx += 1
        
        return result
