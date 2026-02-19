"""
Memory Adapter for Evaluation

Uses the same interface as backend/src/agent/memory.py but with SQLite storage.
This allows the notebook to use the exact same logic as production,
just with a different data source (Kaggle historical vs Finnhub live).
"""

import sys
from pathlib import Path

# Add backend to path
ANALYSIS_DIR = Path(__file__).parent
PROJECT_ROOT = ANALYSIS_DIR.parent
BACKEND_SRC = PROJECT_ROOT / "backend" / "src"
sys.path.insert(0, str(BACKEND_SRC))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

import json
import sqlite3
import numpy as np
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from loguru import logger

# Import the actual Decision class from the app
from agent.memory import Decision, Memory, EMBEDDING_DIM

# Try to import sentence-transformers for local embeddings
try:
    from sentence_transformers import SentenceTransformer
    LOCAL_EMBED_MODEL = SentenceTransformer('all-MiniLM-L6-v2')
    LOCAL_EMBEDDING_DIM = LOCAL_EMBED_MODEL.get_sentence_embedding_dimension()
    USE_LOCAL_EMBEDDINGS = True
    logger.info(f"Using local embeddings: all-MiniLM-L6-v2 (dim={LOCAL_EMBEDDING_DIM})")
except ImportError:
    LOCAL_EMBED_MODEL = None
    LOCAL_EMBEDDING_DIM = 384
    USE_LOCAL_EMBEDDINGS = False
    logger.warning("sentence-transformers not installed, using random embeddings")


# Paths
ANALYSIS_DATA_DIR = ANALYSIS_DIR / "data"
MEMORY_DB_PATH = ANALYSIS_DATA_DIR / "memory_aligned.db"


class AgentMemoryAdapter:
    """
    SQLite-based memory adapter that mirrors AgentMemory interface.
    
    Same interface as production AgentMemory but uses:
    - SQLite instead of PostgreSQL
    - Local embeddings (sentence-transformers) instead of OpenAI
    
    This allows A/B testing with exact same logic, different storage.
    """
    
    def __init__(
        self,
        db_path: Path = MEMORY_DB_PATH,
        use_openai: bool = False,  # Set True to use OpenAI embeddings like production
    ):
        self.db_path = db_path
        self.use_openai = use_openai
        self._conn: Optional[sqlite3.Connection] = None
        
        # Working memory (current session) - same as production
        self.working_memory: Dict[str, Any] = {}
        
        # Ensure data directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
    
    async def initialize(self):
        """Initialize database (SQLite version)."""
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        
        # Create tables matching production schema
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                ticker TEXT NOT NULL,
                action TEXT NOT NULL,
                shares INTEGER DEFAULT 0,
                price REAL DEFAULT 0.0,
                score REAL NOT NULL,
                regime TEXT DEFAULT 'normal',
                sector TEXT DEFAULT 'Unknown',
                rationale TEXT,
                confidence REAL DEFAULT 0.0,
                context_json TEXT DEFAULT '{}',
                outcome_pct REAL,
                outcome_date TEXT,
                lesson_learned TEXT,
                embedding BLOB,
                user_id TEXT,
                UNIQUE(ticker, timestamp)
            );
            
            CREATE INDEX IF NOT EXISTS idx_decisions_ticker ON decisions(ticker);
            CREATE INDEX IF NOT EXISTS idx_decisions_timestamp ON decisions(timestamp);
            CREATE INDEX IF NOT EXISTS idx_decisions_sector ON decisions(sector);
            CREATE INDEX IF NOT EXISTS idx_decisions_regime ON decisions(regime);
        """)
        self._conn.commit()
        logger.info(f"Memory adapter initialized: {self.db_path}")
    
    def close(self):
        """Close database connection."""
        if self._conn:
            self._conn.close()
    
    def _generate_embedding(self, decision: Decision, context: Optional[Dict] = None) -> np.ndarray:
        """Generate embedding for a decision (same logic as production)."""
        # Build text representation (same format as production)
        text_parts = [
            f"Ticker: {decision.ticker}",
            f"Action: {decision.action}",
            f"Score: {decision.score:.1f}",
            f"Sector: {decision.sector}",
            f"Regime: {decision.regime}",
            f"Rationale: {decision.rationale}",
        ]
        
        if decision.outcome_pct is not None:
            text_parts.append(f"Outcome: {decision.outcome_pct:+.1f}%")
        
        if decision.lesson_learned:
            text_parts.append(f"Lesson: {decision.lesson_learned}")
        
        if context:
            text_parts.append(f"Context: {json.dumps(context)[:500]}")
        
        text = "\n".join(text_parts)
        
        # Generate embedding
        if USE_LOCAL_EMBEDDINGS and LOCAL_EMBED_MODEL is not None:
            embedding = LOCAL_EMBED_MODEL.encode(text)
        else:
            # Fallback: deterministic pseudo-embedding based on text hash
            np.random.seed(hash(text) % 2**32)
            embedding = np.random.randn(LOCAL_EMBEDDING_DIM).astype(np.float32)
        
        return embedding
    
    async def store_decision(
        self,
        decision: Decision,
        context: Optional[Dict] = None,
        user_id: Optional[str] = None,
    ) -> int:
        """Store a decision in memory. Returns decision ID."""
        # Generate embedding
        embedding = self._generate_embedding(decision, context)
        
        # Insert into database
        cursor = self._conn.execute("""
            INSERT OR REPLACE INTO decisions
            (timestamp, ticker, action, shares, price, score, regime, sector,
             rationale, confidence, context_json, outcome_pct, outcome_date,
             lesson_learned, embedding, user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            decision.timestamp.isoformat() if decision.timestamp else datetime.now(timezone.utc).isoformat(),
            decision.ticker,
            decision.action,
            decision.shares,
            decision.price,
            decision.score,
            decision.regime,
            decision.sector,
            decision.rationale,
            decision.confidence,
            decision.context_json,
            decision.outcome_pct,
            decision.outcome_date.isoformat() if decision.outcome_date else None,
            decision.lesson_learned,
            embedding.tobytes(),
            user_id,
        ))
        self._conn.commit()
        
        return cursor.lastrowid
    
    async def update_outcome(
        self,
        decision_id: int,
        outcome_pct: float,
        lesson_learned: Optional[str] = None,
    ):
        """Update outcome for a decision (called after holding period)."""
        outcome_date = datetime.now(timezone.utc).isoformat()
        
        self._conn.execute("""
            UPDATE decisions
            SET outcome_pct = ?, outcome_date = ?, lesson_learned = ?
            WHERE id = ?
        """, (outcome_pct, outcome_date, lesson_learned, decision_id))
        self._conn.commit()
    
    async def retrieve_similar(
        self,
        query_text: str = None,
        query_embedding: np.ndarray = None,
        k: int = 5,
        sector_filter: Optional[str] = None,
        regime_filter: Optional[str] = None,
        min_similarity: float = 0.0,
    ) -> List[Memory]:
        """
        Retrieve k most similar past decisions.
        
        Same interface as production AgentMemory.retrieve_similar()
        """
        # Generate query embedding if text provided
        if query_embedding is None and query_text:
            if USE_LOCAL_EMBEDDINGS and LOCAL_EMBED_MODEL is not None:
                query_embedding = LOCAL_EMBED_MODEL.encode(query_text)
            else:
                np.random.seed(hash(query_text) % 2**32)
                query_embedding = np.random.randn(LOCAL_EMBEDDING_DIM).astype(np.float32)
        
        if query_embedding is None:
            return []
        
        # Build query with filters
        query = "SELECT * FROM decisions WHERE outcome_pct IS NOT NULL"
        params = []
        
        if sector_filter:
            query += " AND sector = ?"
            params.append(sector_filter)
        
        if regime_filter:
            query += " AND regime = ?"
            params.append(regime_filter)
        
        cursor = self._conn.execute(query, params)
        rows = cursor.fetchall()
        
        # Calculate similarities
        results = []
        for row in rows:
            embedding = np.frombuffer(row["embedding"], dtype=np.float32)
            
            # Cosine similarity
            similarity = np.dot(query_embedding, embedding) / (
                np.linalg.norm(query_embedding) * np.linalg.norm(embedding) + 1e-10
            )
            
            if similarity >= min_similarity:
                results.append((Memory(
                    ticker=row["ticker"],
                    action=row["action"],
                    score=row["score"],
                    regime=row["regime"],
                    outcome_pct=row["outcome_pct"],
                    rationale=row["rationale"],
                    lesson_learned=row["lesson_learned"],
                    similarity=float(similarity),
                ), float(similarity)))
        
        # Sort by similarity descending
        results.sort(key=lambda x: x[1], reverse=True)
        
        return [mem for mem, _ in results[:k]]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics."""
        cursor = self._conn.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN outcome_pct IS NOT NULL THEN 1 END) as with_outcomes,
                COUNT(DISTINCT ticker) as unique_tickers,
                COUNT(DISTINCT sector) as unique_sectors,
                AVG(outcome_pct) as avg_outcome
            FROM decisions
        """)
        row = cursor.fetchone()
        
        return {
            "total_decisions": row["total"],
            "with_outcomes": row["with_outcomes"],
            "unique_tickers": row["unique_tickers"],
            "unique_sectors": row["unique_sectors"],
            "avg_outcome_pct": row["avg_outcome"] or 0,
        }


async def build_memory_from_evaluation_data(
    memory: AgentMemoryAdapter,
    evaluation_db_path: Path,
    train_end_date: str = "2024-12-31",
) -> int:
    """
    Build memory from evaluation data (same as production learning loop).
    
    This simulates what would happen in production:
    - Agent makes decisions based on scores
    - Outcomes are recorded after holding period
    - Lessons are generated from outcomes
    """
    conn = sqlite3.connect(evaluation_db_path)
    conn.row_factory = sqlite3.Row
    
    # Load scores with outcomes from training period
    cursor = conn.execute("""
        SELECT 
            s.ticker,
            s.week_start,
            s.composite_score,
            s.fundamental_score,
            s.sentiment_score,
            s.technical_score,
            s.macro_score,
            s.signal,
            s.price,
            s.sector,
            o.return_pct,
            o.holding_weeks
        FROM weekly_scores s
        JOIN trade_outcomes o 
            ON s.ticker = o.ticker AND s.week_start = o.entry_week
        WHERE s.week_start <= ?
        AND s.signal = 'BUY'
        ORDER BY s.week_start
    """, (train_end_date,))
    
    rows = cursor.fetchall()
    conn.close()
    
    logger.info(f"Building memory from {len(rows)} training decisions...")
    
    count = 0
    for row in rows:
        # Infer regime from macro score
        macro = row["macro_score"]
        if macro >= 75:
            regime = "low_vol"
        elif macro >= 50:
            regime = "normal"
        elif macro >= 25:
            regime = "high_vol"
        else:
            regime = "crisis"
        
        # Generate lesson (same logic as production learning loop)
        outcome = row["return_pct"]
        sector = row["sector"]
        score = row["composite_score"]
        
        if outcome > 10:
            lesson = f"Strong winner: {sector} with score {score:.0f}+ in {regime} → +{outcome:.1f}%"
        elif outcome > 5:
            lesson = f"Solid gain: {sector} in {regime} performed well → +{outcome:.1f}%"
        elif outcome > 0:
            lesson = f"Modest gain: {sector} in {regime} → +{outcome:.1f}%"
        elif outcome > -5:
            lesson = f"Small loss: {sector} in {regime} had limited downside → {outcome:.1f}%"
        else:
            lesson = f"Avoid: {sector} in {regime} even with high scores → {outcome:.1f}%"
        
        # Create Decision (same as production)
        decision = Decision(
            timestamp=datetime.fromisoformat(row["week_start"]),
            ticker=row["ticker"],
            action="BUY",
            shares=0,
            price=row["price"],
            score=score,
            regime=regime,
            sector=sector,
            rationale=f"Score {score:.1f} above threshold, {regime} regime",
            confidence=min(1.0, score / 100),
            outcome_pct=outcome,
            lesson_learned=lesson,
        )
        
        await memory.store_decision(decision)
        count += 1
    
    logger.info(f"Stored {count} decisions in memory")
    return count


def format_memories_for_prompt(memories: List[Memory]) -> str:
    """Format memories for LLM prompt (same as production)."""
    if not memories:
        return "No relevant past decisions found."
    
    lines = []
    for i, mem in enumerate(memories, 1):
        lines.append(f"""
Past Decision {i} (similarity: {mem.similarity:.2f}):
- Ticker: {mem.ticker}
- Action: {mem.action} at score {mem.score:.1f}
- Regime: {mem.regime}
- Outcome: {mem.outcome_pct:+.1f}%
- Lesson: {mem.lesson_learned}
""".strip())
    
    return "\n\n".join(lines)
