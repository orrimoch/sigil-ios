"""
Episode Data Model

Maps directly to Sigil's existing types:
- Decision (memory.py) → Episode.decision
- TradingContext (context.py) → Episode.context_snapshot  
- TradeOutcome (learning.py) → Episode.outcome
- LessonLearned (learning.py) → Episode.lesson

An Episode is the atomic unit of episodic memory: a complete
decision-context-outcome-lesson tuple that can be retrieved,
compared, and learned from.
"""

import hashlib
import json
import numpy as np
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List


@dataclass
class DecisionRecord:
    """
    The decision component of an episode.
    Maps to: memory.Decision + position_sizing.TradeDecision
    """
    ticker: str
    action: str  # BUY, SELL
    shares: int = 0
    price: float = 0.0
    score: float = 0.0
    confidence: float = 0.0
    rationale: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "action": self.action,
            "shares": self.shares,
            "price": self.price,
            "score": self.score,
            "confidence": self.confidence,
            "rationale": self.rationale,
        }


@dataclass
class ContextSnapshot:
    """
    Frozen context at decision time.
    Maps to: context.TradingContext (flattened for storage/comparison)
    
    These are the dimensions we use for multi-dimensional retrieval.
    """
    regime: str = "normal"  # low_vol, normal, high_vol, crisis
    regime_confidence: float = 0.7
    vix: float = 15.0
    vix_regime: str = "calm"  # calm, elevated, fear, panic
    trend: str = "sideways"  # up, down, sideways
    
    # Portfolio state (normalized)
    cash_pct: float = 0.5  # cash / total_value
    position_count: int = 0
    sector_exposure: Dict[str, float] = field(default_factory=dict)
    
    # Score components for the traded ticker
    fundamental_score: float = 50.0
    sentiment_score: float = 50.0
    technical_score: float = 50.0
    macro_score: float = 50.0
    
    # Sector of the traded ticker
    sector: str = "Unknown"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "regime": self.regime,
            "regime_confidence": self.regime_confidence,
            "vix": self.vix,
            "vix_regime": self.vix_regime,
            "trend": self.trend,
            "cash_pct": self.cash_pct,
            "position_count": self.position_count,
            "sector_exposure": self.sector_exposure,
            "fundamental_score": self.fundamental_score,
            "sentiment_score": self.sentiment_score,
            "technical_score": self.technical_score,
            "macro_score": self.macro_score,
            "sector": self.sector,
        }

    def to_feature_vector(self) -> np.ndarray:
        """
        Convert to numeric feature vector for structured similarity.
        
        Used alongside embedding similarity to compute multi-dimensional
        episode distance. Dimensions chosen to match Sigil's scoring axes.
        """
        regime_map = {"low_vol": 0.0, "normal": 0.33, "high_vol": 0.66, "crisis": 1.0}
        trend_map = {"up": 0.0, "sideways": 0.5, "down": 1.0}
        
        return np.array([
            regime_map.get(self.regime, 0.33),
            self.regime_confidence,
            min(self.vix / 80.0, 1.0),  # Normalize VIX to [0, 1]
            self.cash_pct,
            min(self.position_count / 20.0, 1.0),  # Normalize to [0, 1]
            self.fundamental_score / 100.0,
            self.sentiment_score / 100.0,
            self.technical_score / 100.0,
            self.macro_score / 100.0,
            trend_map.get(self.trend, 0.5),
        ], dtype=np.float64)


@dataclass
class OutcomeRecord:
    """
    The outcome of a decision.
    Maps to: learning.TradeOutcome
    """
    pct_return: float = 0.0
    holding_days: int = 0
    exit_price: float = 0.0
    tag: str = "neutral"  # strong_win, win, small_win, neutral, loss, strong_loss
    pnl_dollars: float = 0.0
    recorded_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pct_return": self.pct_return,
            "holding_days": self.holding_days,
            "exit_price": self.exit_price,
            "tag": self.tag,
            "pnl_dollars": self.pnl_dollars,
            "recorded_at": self.recorded_at.isoformat() if self.recorded_at else None,
        }

    @property
    def is_positive(self) -> bool:
        return self.pct_return > 0

    @property
    def quality_score(self) -> float:
        """
        Normalized quality score [-1, 1] for outcome weighting.
        Maps outcome percentage to a bounded quality signal.
        """
        # Sigmoid-like mapping: ±20% maps to ±0.95
        return np.tanh(self.pct_return / 10.0)


@dataclass
class Episode:
    """
    A complete episodic memory unit.
    
    This is the core EMATA data structure. It captures everything about
    a single trading decision: what the world looked like (context),
    what we decided (decision), what happened (outcome), and what we
    learned (lesson).
    
    Sigil integration point:
        Created in TradingLoop._store_decisions() after execution,
        with outcome filled by LearningLoop.run_weekly_update().
    """
    id: str = ""  # Unique ID (auto-generated if empty)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    decision: DecisionRecord = field(default_factory=DecisionRecord)
    context: ContextSnapshot = field(default_factory=ContextSnapshot)
    outcome: Optional[OutcomeRecord] = None
    lesson: str = ""
    
    # Embedding (matches Sigil's EMBEDDING_DIM = 1536)
    embedding: Optional[np.ndarray] = None
    
    # Meta-learning: how useful was this episode when retrieved?
    times_retrieved: int = 0
    times_helpful: int = 0  # When the decision using this memory succeeded
    utility_score: float = 0.0  # Running average of usefulness
    
    def __post_init__(self):
        if not self.id:
            self.id = self._generate_id()
    
    def _generate_id(self) -> str:
        """Generate deterministic ID from key fields."""
        key = f"{self.timestamp.isoformat()}:{self.decision.ticker}:{self.decision.action}"
        return hashlib.sha256(key.encode()).hexdigest()[:16]
    
    @property
    def has_outcome(self) -> bool:
        return self.outcome is not None
    
    @property
    def has_embedding(self) -> bool:
        return self.embedding is not None
    
    @property
    def is_complete(self) -> bool:
        """An episode is complete when it has outcome + lesson."""
        return self.has_outcome and bool(self.lesson)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "decision": self.decision.to_dict(),
            "context": self.context.to_dict(),
            "outcome": self.outcome.to_dict() if self.outcome else None,
            "lesson": self.lesson,
            "times_retrieved": self.times_retrieved,
            "times_helpful": self.times_helpful,
            "utility_score": self.utility_score,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Episode":
        """Reconstruct from dict (for JSON deserialization)."""
        ep = cls(
            id=data.get("id", ""),
            timestamp=datetime.fromisoformat(data["timestamp"]) if data.get("timestamp") else datetime.now(timezone.utc),
            decision=DecisionRecord(**data.get("decision", {})),
            context=ContextSnapshot(**{k: v for k, v in data.get("context", {}).items() if k != "sector_exposure"}) if data.get("context") else ContextSnapshot(),
            lesson=data.get("lesson", ""),
            times_retrieved=data.get("times_retrieved", 0),
            times_helpful=data.get("times_helpful", 0),
            utility_score=data.get("utility_score", 0.0),
        )
        # Handle sector_exposure separately (dict field)
        if data.get("context", {}).get("sector_exposure"):
            ep.context.sector_exposure = data["context"]["sector_exposure"]
        # Handle outcome
        if data.get("outcome"):
            outcome_data = data["outcome"].copy()
            if outcome_data.get("recorded_at"):
                outcome_data["recorded_at"] = datetime.fromisoformat(outcome_data["recorded_at"])
            ep.outcome = OutcomeRecord(**outcome_data)
        return ep
    
    def to_embedding_text(self) -> str:
        """
        Generate text for embedding.
        
        Matches the format used by AgentMemory._decision_to_text() but
        enriched with more context dimensions for better retrieval.
        """
        parts = [
            f"Action: {self.decision.action} {self.decision.ticker}",
            f"Score: {self.decision.score:.0f}",
            f"Regime: {self.context.regime}",
            f"Sector: {self.context.sector}",
            f"VIX: {self.context.vix:.1f}",
            f"Trend: {self.context.trend}",
            f"Cash: {self.context.cash_pct:.0%}",
            f"Positions: {self.context.position_count}",
            f"Fundamental: {self.context.fundamental_score:.0f}",
            f"Sentiment: {self.context.sentiment_score:.0f}",
            f"Technical: {self.context.technical_score:.0f}",
            f"Macro: {self.context.macro_score:.0f}",
        ]
        if self.decision.rationale:
            parts.append(f"Rationale: {self.decision.rationale[:200]}")
        return " | ".join(parts)


@dataclass
class RetrievedEpisode:
    """
    An episode with retrieval metadata.
    
    Returned by EpisodicRetriever with all similarity dimensions
    so the ContextAugmenter can format it intelligently.
    """
    episode: Episode
    
    # Multi-dimensional similarity scores
    embedding_similarity: float = 0.0  # Cosine similarity [0, 1]
    context_similarity: float = 0.0    # Feature vector distance [0, 1]
    regime_match: bool = False          # Same regime?
    sector_match: bool = False          # Same sector?
    
    # Combined score (weighted blend)
    combined_score: float = 0.0
    
    # Outcome-adjusted relevance
    outcome_weight: float = 1.0  # Higher for informative outcomes
    final_score: float = 0.0     # combined_score * outcome_weight * utility
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "episode": self.episode.to_dict(),
            "embedding_similarity": self.embedding_similarity,
            "context_similarity": self.context_similarity,
            "regime_match": self.regime_match,
            "sector_match": self.sector_match,
            "combined_score": self.combined_score,
            "outcome_weight": self.outcome_weight,
            "final_score": self.final_score,
        }
