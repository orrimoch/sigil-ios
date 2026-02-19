"""
REC-323: Memory Builder for Memory Evaluation

Builds a memory database from training period decisions.
Generates embeddings and stores with outcomes for retrieval.
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
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from loguru import logger

# Try to import sentence-transformers for embeddings
try:
    from sentence_transformers import SentenceTransformer
    EMBED_MODEL = SentenceTransformer('all-MiniLM-L6-v2')
    EMBEDDING_DIM = EMBED_MODEL.get_sentence_embedding_dimension()
    logger.info(f"Loaded embedding model: all-MiniLM-L6-v2 (dim={EMBEDDING_DIM})")
except ImportError:
    logger.warning("sentence-transformers not installed, using random embeddings")
    EMBED_MODEL = None
    EMBEDDING_DIM = 384


# Paths
ANALYSIS_DATA_DIR = ANALYSIS_DIR / "data"
EVALUATION_DB_PATH = ANALYSIS_DATA_DIR / "evaluation_data.db"
MEMORY_DB_PATH = ANALYSIS_DATA_DIR / "memory.db"


@dataclass
class MemoryEntry:
    """A decision stored in memory with multi-horizon returns."""
    id: Optional[int]
    ticker: str
    week_start: str
    action: str  # BUY or SELL
    score: float
    sector: str
    regime: str  # low_vol, normal, high_vol, crisis
    rationale: str
    # Multi-horizon returns
    return_1w: Optional[float]   # 1 week
    return_1m: Optional[float]   # 1 month (4 weeks)
    return_3m: Optional[float]   # 3 months (12 weeks)
    lesson_learned: Optional[str]
    embedding: np.ndarray
    
    def to_text(self) -> str:
        """Convert to text for embedding."""
        # Build outcome string with all available horizons
        outcomes = []
        if self.return_1w is not None:
            outcomes.append(f"1W: {self.return_1w:+.1f}%")
        if self.return_1m is not None:
            outcomes.append(f"1M: {self.return_1m:+.1f}%")
        if self.return_3m is not None:
            outcomes.append(f"3M: {self.return_3m:+.1f}%")
        outcome_str = ", ".join(outcomes) if outcomes else "unknown"
        
        return f"""
Ticker: {self.ticker}
Sector: {self.sector}
Action: {self.action}
Score: {self.score:.1f}
Regime: {self.regime}
Rationale: {self.rationale}
Returns: {outcome_str}
Lesson: {self.lesson_learned or 'N/A'}
        """.strip()


def embed_text(text: str) -> np.ndarray:
    """Generate embedding for text."""
    if EMBED_MODEL is not None:
        return EMBED_MODEL.encode(text)
    else:
        # Fallback: random embedding for testing
        np.random.seed(hash(text) % 2**32)
        return np.random.randn(EMBEDDING_DIM).astype(np.float32)


def infer_regime(macro_score: float) -> str:
    """Infer market regime from macro score."""
    if macro_score >= 75:
        return "low_vol"
    elif macro_score >= 50:
        return "normal"
    elif macro_score >= 25:
        return "high_vol"
    else:
        return "crisis"


def generate_rationale(ticker: str, score: float, sector: str, action: str) -> str:
    """Generate a simple rationale for the decision."""
    if action == "BUY":
        if score >= 85:
            return f"Strong buy signal: {ticker} ({sector}) with score {score:.1f}, significantly above threshold"
        elif score >= 75:
            return f"Buy signal: {ticker} ({sector}) with solid score {score:.1f}"
        else:
            return f"Buy signal: {ticker} ({sector}) at score {score:.1f}, above buy threshold"
    else:
        if score <= 30:
            return f"Strong sell signal: {ticker} ({sector}) with score {score:.1f}, well below threshold"
        else:
            return f"Sell signal: {ticker} ({sector}) at score {score:.1f}, below sell threshold"


def generate_lesson(
    ticker: str, sector: str, regime: str, score: float,
    return_1w: Optional[float], return_1m: Optional[float], return_3m: Optional[float]
) -> str:
    """Generate a lesson learned from multi-horizon outcomes."""
    # Use 1M as primary, fallback to 3M, then 1W
    primary_return = return_1m if return_1m is not None else (return_3m if return_3m is not None else return_1w)
    
    if primary_return is None:
        return "Outcome pending"
    
    # Build horizon-specific insights
    insights = []
    
    # Analyze trajectory (1W → 1M → 3M)
    if return_1w is not None and return_1m is not None:
        if return_1w < 0 and return_1m > 0:
            insights.append("recovered from initial dip")
        elif return_1w > 0 and return_1m < return_1w:
            insights.append("early gains faded")
        elif return_1w > 0 and return_1m > return_1w:
            insights.append("momentum continued")
    
    if return_1m is not None and return_3m is not None:
        if return_3m > return_1m * 1.5:
            insights.append("strong long-term trend")
        elif return_3m < return_1m * 0.5:
            insights.append("trend reversed")
    
    trajectory = f" ({', '.join(insights)})" if insights else ""
    
    # Generate lesson based on primary return
    if primary_return > 10:
        return f"Strong winner: {sector} with score {score:.0f}+ in {regime} regime{trajectory}"
    elif primary_return > 5:
        return f"Solid gain: {sector} in {regime} conditions performed well{trajectory}"
    elif primary_return > 0:
        return f"Modest gain: {ticker} in {regime} regime{trajectory}"
    elif primary_return > -5:
        return f"Small loss: {sector} in {regime} regime had limited downside{trajectory}"
    elif primary_return > -10:
        return f"Loss: {sector} underperformed in {regime} regime{trajectory}"
    else:
        return f"Significant loss: Avoid {sector} in {regime} regime{trajectory}"


class MemoryBuilder:
    """
    Builds a memory database from training period decisions.
    """
    
    def __init__(
        self,
        evaluation_db: Path = EVALUATION_DB_PATH,
        memory_db: Path = MEMORY_DB_PATH,
        train_end_date: str = "2021-12-31",
    ):
        self.evaluation_db = evaluation_db
        self.memory_db = memory_db
        self.train_end_date = train_end_date
        
        # Ensure output directory exists
        self.memory_db.parent.mkdir(parents=True, exist_ok=True)
    
    def load_training_data(self) -> List[Dict]:
        """Load scores and outcomes for training period."""
        if not self.evaluation_db.exists():
            raise FileNotFoundError(f"Evaluation DB not found: {self.evaluation_db}")
        
        conn = sqlite3.connect(self.evaluation_db)
        conn.row_factory = sqlite3.Row
        
        # Load scores with multi-horizon outcomes
        query = """
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
                o.return_1w,
                o.return_1m,
                o.return_3m
            FROM weekly_scores s
            LEFT JOIN trade_outcomes o 
                ON s.ticker = o.ticker AND s.week_start = o.entry_week
            WHERE s.week_start <= ?
            ORDER BY s.week_start, s.ticker
        """
        
        cursor = conn.execute(query, (self.train_end_date,))
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        logger.info(f"Loaded {len(rows)} training records")
        return rows
    
    def build_memories(self, training_data: List[Dict], require_real_sentiment: bool = True) -> List[MemoryEntry]:
        """Convert training data to memory entries with embeddings.
        
        Args:
            training_data: List of score records with outcomes
            require_real_sentiment: If True, skip records with fallback sentiment (50.0)
        """
        memories = []
        skipped_sentiment = 0
        
        for i, row in enumerate(training_data):
            if i % 100 == 0:
                logger.info(f"Processing {i}/{len(training_data)}...")
            
            # Only create memories for BUY signals (main focus)
            if row["signal"] != "BUY":
                continue
            
            # Skip if no outcome at any horizon
            has_outcome = (row.get("return_1w") is not None or 
                          row.get("return_1m") is not None or 
                          row.get("return_3m") is not None)
            if not has_outcome:
                continue
            
            # Skip fallback sentiment (50.0) - these have no real sentiment data
            # Real sentiment from Kaggle/Claude has much higher signal quality
            if require_real_sentiment and row.get("sentiment_score") == 50.0:
                skipped_sentiment += 1
                continue
            
            # Infer regime
            regime = infer_regime(row["macro_score"])
            
            # Generate rationale
            rationale = generate_rationale(
                row["ticker"],
                row["composite_score"],
                row["sector"],
                row["signal"],
            )
            
            # Generate lesson with multi-horizon returns
            lesson = generate_lesson(
                row["ticker"],
                row["sector"],
                regime,
                row["composite_score"],
                row.get("return_1w"),
                row.get("return_1m"),
                row.get("return_3m"),
            )
            
            # Create memory entry with multi-horizon returns
            entry = MemoryEntry(
                id=None,
                ticker=row["ticker"],
                week_start=row["week_start"],
                action=row["signal"],
                score=row["composite_score"],
                sector=row["sector"],
                regime=regime,
                rationale=rationale,
                return_1w=row.get("return_1w"),
                return_1m=row.get("return_1m"),
                return_3m=row.get("return_3m"),
                lesson_learned=lesson,
                embedding=np.zeros(EMBEDDING_DIM),  # Placeholder
            )
            
            # Generate embedding
            entry.embedding = embed_text(entry.to_text())
            
            memories.append(entry)
        
        if require_real_sentiment:
            logger.info(f"Skipped {skipped_sentiment} records with fallback sentiment (50.0)")
        logger.info(f"Built {len(memories)} memory entries")
        return memories
    
    def save_memories(self, memories: List[MemoryEntry]):
        """Save memories to SQLite database."""
        conn = sqlite3.connect(self.memory_db)
        
        # Create table with multi-horizon returns
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT,
                week_start TEXT,
                action TEXT,
                score REAL,
                sector TEXT,
                regime TEXT,
                rationale TEXT,
                return_1w REAL,
                return_1m REAL,
                return_3m REAL,
                lesson_learned TEXT,
                embedding BLOB,
                UNIQUE(ticker, week_start)
            )
        """)
        
        # Create index for efficient retrieval
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_memories_sector 
            ON memories(sector)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_memories_regime 
            ON memories(regime)
        """)
        
        # Insert memories
        for mem in memories:
            embedding_blob = mem.embedding.tobytes()
            conn.execute("""
                INSERT OR REPLACE INTO memories
                (ticker, week_start, action, score, sector, regime, 
                 rationale, return_1w, return_1m, return_3m, lesson_learned, embedding)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                mem.ticker, mem.week_start, mem.action, mem.score,
                mem.sector, mem.regime, mem.rationale, 
                mem.return_1w, mem.return_1m, mem.return_3m,
                mem.lesson_learned, embedding_blob,
            ))
        
        conn.commit()
        conn.close()
        logger.info(f"Saved {len(memories)} memories to {self.memory_db}")
    
    def run(self, require_real_sentiment: bool = True) -> List[MemoryEntry]:
        """Run the full memory building pipeline.
        
        Args:
            require_real_sentiment: If True, only use records with real sentiment data
        """
        logger.info("Starting memory builder...")
        logger.info(f"Sentiment filter: {'real only' if require_real_sentiment else 'all (including fallback)'}")
        
        # Load training data
        training_data = self.load_training_data()
        
        # Build memories
        memories = self.build_memories(training_data, require_real_sentiment=require_real_sentiment)
        
        # Save to DB
        self.save_memories(memories)
        
        return memories


class MemoryRetriever:
    """
    Retrieves similar memories for a given context.
    """
    
    def __init__(self, memory_db: Path = MEMORY_DB_PATH):
        self.memory_db = memory_db
        self._memories: Optional[List[MemoryEntry]] = None
    
    def load_memories(self) -> List[MemoryEntry]:
        """Load all memories from database."""
        if self._memories is not None:
            return self._memories
        
        conn = sqlite3.connect(self.memory_db)
        conn.row_factory = sqlite3.Row
        
        cursor = conn.execute("SELECT * FROM memories")
        rows = cursor.fetchall()
        conn.close()
        
        memories = []
        for row in rows:
            embedding = np.frombuffer(row["embedding"], dtype=np.float32)
            memories.append(MemoryEntry(
                id=row["id"],
                ticker=row["ticker"],
                week_start=row["week_start"],
                action=row["action"],
                score=row["score"],
                sector=row["sector"],
                regime=row["regime"],
                rationale=row["rationale"],
                return_1w=row["return_1w"],
                return_1m=row["return_1m"],
                return_3m=row["return_3m"],
                lesson_learned=row["lesson_learned"],
                embedding=embedding,
            ))
        
        self._memories = memories
        logger.info(f"Loaded {len(memories)} memories")
        return memories
    
    def retrieve(
        self,
        query_text: str,
        top_k: int = 5,
        min_similarity: float = 0.0,
        sector_filter: Optional[str] = None,
        regime_filter: Optional[str] = None,
    ) -> List[Tuple[MemoryEntry, float]]:
        """
        Retrieve top-k most similar memories.
        
        Returns list of (memory, similarity_score) tuples.
        """
        memories = self.load_memories()
        
        # Generate query embedding
        query_embedding = embed_text(query_text)
        
        # Calculate similarities
        results = []
        for mem in memories:
            # Apply filters
            if sector_filter and mem.sector != sector_filter:
                continue
            if regime_filter and mem.regime != regime_filter:
                continue
            
            # Cosine similarity
            similarity = np.dot(query_embedding, mem.embedding) / (
                np.linalg.norm(query_embedding) * np.linalg.norm(mem.embedding) + 1e-10
            )
            
            if similarity >= min_similarity:
                results.append((mem, float(similarity)))
        
        # Sort by similarity descending
        results.sort(key=lambda x: x[1], reverse=True)
        
        return results[:top_k]
    
    def format_memories_for_prompt(
        self,
        memories: List[Tuple[MemoryEntry, float]],
    ) -> str:
        """Format retrieved memories for inclusion in LLM prompt."""
        if not memories:
            return "No relevant past decisions found."
        
        lines = []
        for i, (mem, sim) in enumerate(memories, 1):
            # Build multi-horizon outcome string
            outcomes = []
            if mem.return_1w is not None:
                outcomes.append(f"1W: {mem.return_1w:+.1f}%")
            if mem.return_1m is not None:
                outcomes.append(f"1M: {mem.return_1m:+.1f}%")
            if mem.return_3m is not None:
                outcomes.append(f"3M: {mem.return_3m:+.1f}%")
            outcome_str = ", ".join(outcomes) if outcomes else "N/A"
            
            lines.append(f"""
Memory {i} (similarity: {sim:.2f}):
- Ticker: {mem.ticker} ({mem.sector})
- Date: {mem.week_start}
- Action: {mem.action} at score {mem.score:.1f}
- Regime: {mem.regime}
- Returns: {outcome_str}
- Lesson: {mem.lesson_learned}
""".strip())
        
        return "\n\n".join(lines)


def export_for_production(memory_db: Path = MEMORY_DB_PATH, output_path: Path = None) -> Path:
    """
    Export memories as JSON for production import (no embeddings).
    
    Format aligns with production AgentMemory.import_memories() expectations.
    Embeddings are generated server-side with OpenAI on import.
    Includes multi-horizon returns (1W, 1M, 3M).
    """
    if output_path is None:
        output_path = ANALYSIS_DATA_DIR / "memory_export.json"
    
    conn = sqlite3.connect(memory_db)
    conn.row_factory = sqlite3.Row
    
    cursor = conn.execute("""
        SELECT ticker, week_start, action, score, sector, regime,
               rationale, return_1w, return_1m, return_3m, lesson_learned
        FROM memories
        WHERE return_1w IS NOT NULL OR return_1m IS NOT NULL OR return_3m IS NOT NULL
    """)
    
    memories = []
    for row in cursor.fetchall():
        # Use 1M as primary outcome, fallback to others
        primary_return = row["return_1m"] if row["return_1m"] is not None else (
            row["return_3m"] if row["return_3m"] is not None else row["return_1w"]
        )
        
        memories.append({
            "ticker": row["ticker"],
            "timestamp": row["week_start"] + "T09:30:00Z",  # Market open
            "action": row["action"],
            "score": row["score"],
            "sector": row["sector"],
            "regime": row["regime"],
            "rationale": row["rationale"],
            # Multi-horizon returns
            "return_1w": row["return_1w"],
            "return_1m": row["return_1m"],
            "return_3m": row["return_3m"],
            "outcome_pct": primary_return,  # Primary for backward compat
            "lesson_learned": row["lesson_learned"],
            # Production-specific fields
            "shares": 0,  # Unknown from historical
            "price": 0.0,  # Not stored in evaluation
            "confidence": 0.8 if (primary_return or 0) > 0 else 0.6,
        })
    
    conn.close()
    
    # Sort by date for deterministic output
    memories.sort(key=lambda m: m["timestamp"])
    
    export_data = {
        "version": "1.0",
        "exported_at": datetime.utcnow().isoformat() + "Z",
        "source": "memory_evaluation_experiment",
        "train_period": "2019-2021",
        "memory_count": len(memories),
        "memories": memories,
    }
    
    with open(output_path, 'w') as f:
        json.dump(export_data, f, indent=2)
    
    logger.info(f"Exported {len(memories)} memories to {output_path}")
    return output_path


def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Memory Builder for Evaluation")
    parser.add_argument("--train-end", default="2021-12-31", help="Training period end date")
    parser.add_argument("--eval-db", type=Path, default=EVALUATION_DB_PATH)
    parser.add_argument("--memory-db", type=Path, default=MEMORY_DB_PATH)
    parser.add_argument("--export", action="store_true", help="Export for production import")
    parser.add_argument("--export-path", type=Path, help="Output path for export")
    parser.add_argument("--include-fallback-sentiment", action="store_true", 
                        help="Include records with fallback sentiment (50.0). Default: only real sentiment")
    args = parser.parse_args()
    
    if args.export:
        # Export existing memory DB for production
        output = export_for_production(args.memory_db, args.export_path)
        print(f"Exported memories to: {output}")
        return
    
    builder = MemoryBuilder(
        evaluation_db=args.eval_db,
        memory_db=args.memory_db,
        train_end_date=args.train_end,
    )
    memories = builder.run(require_real_sentiment=not args.include_fallback_sentiment)
    
    print(f"\nMemory builder complete:")
    print(f"  Memories: {len(memories)}")
    print(f"  Database: {args.memory_db}")
    
    # Test retrieval
    print("\nTesting retrieval...")
    retriever = MemoryRetriever(args.memory_db)
    test_query = "Technology stock with high score in normal market conditions"
    results = retriever.retrieve(test_query, top_k=3)
    print(f"Query: '{test_query}'")
    print(f"Results: {len(results)}")
    for mem, sim in results:
        print(f"  - {mem.ticker} ({mem.sector}): {sim:.3f}")
    
    # Also export for production
    print("\nExporting for production...")
    export_path = export_for_production(args.memory_db)
    print(f"Exported to: {export_path}")


if __name__ == "__main__":
    main()
