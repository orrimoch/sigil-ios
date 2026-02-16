"""
Agent Memory System (REC-281, REC-282)

Three-tier memory for agent learning:
1. Working Memory: Current session context (RAM)
2. Short-Term Memory: Recent decisions (SQLite/PostgreSQL)
3. Long-Term Memory: Historical patterns with embeddings (pgvector ready)

Dev mode: Uses SQLite with JSON embeddings + numpy similarity
Prod mode: Uses PostgreSQL with pgvector for efficient similarity search
"""

import json
import numpy as np
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Any
from pathlib import Path
from loguru import logger
import aiosqlite
import hashlib

# Add src to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))


# Embedding dimension (OpenAI text-embedding-3-small = 1536)
EMBEDDING_DIM = 1536


@dataclass
class Decision:
    """A trading decision made by the agent."""
    id: Optional[int] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    ticker: str = ""
    action: str = ""  # BUY, SELL
    shares: int = 0
    price: float = 0.0
    score: float = 0.0
    regime: str = "normal"
    sector: str = "Unknown"
    rationale: str = ""
    confidence: float = 0.0
    context_json: str = "{}"
    
    # Outcome (filled later)
    outcome_pct: Optional[float] = None  # e.g., +12.5 or -3.2
    outcome_date: Optional[datetime] = None
    lesson_learned: Optional[str] = None
    
    # Embedding for similarity search
    embedding: Optional[List[float]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "ticker": self.ticker,
            "action": self.action,
            "shares": self.shares,
            "price": self.price,
            "score": self.score,
            "regime": self.regime,
            "sector": self.sector,
            "rationale": self.rationale,
            "confidence": self.confidence,
            "outcome_pct": self.outcome_pct,
            "outcome_date": self.outcome_date.isoformat() if self.outcome_date else None,
            "lesson_learned": self.lesson_learned,
        }


@dataclass
class Memory:
    """A retrieved memory from the long-term store."""
    ticker: str
    action: str
    score: float
    regime: str
    outcome_pct: float
    rationale: str
    lesson_learned: Optional[str]
    similarity: float  # 0-1, higher = more similar


class AgentMemory:
    """
    Three-tier memory system for the trading agent.
    
    Working Memory: In-RAM context for current session
    Short-Term Memory: Last 50 decisions (full context)
    Long-Term Memory: All decisions with embeddings for similarity search
    
    Usage:
        memory = AgentMemory()
        await memory.initialize()
        
        # Store a decision
        await memory.store_decision(decision, context)
        
        # Retrieve similar situations
        similar = await memory.retrieve_similar(context, k=10)
        
        # Update outcome
        await memory.update_outcome(decision_id, outcome_pct=12.5)
    """
    
    DB_PATH = Path(__file__).parent.parent.parent / "data" / "agent_memory.db"
    
    def __init__(self, db_path: Path = None, embedding_model: str = "text-embedding-3-small"):
        self.db_path = db_path or self.DB_PATH
        self.embedding_model = embedding_model
        self._embedding_client = None
        
        # Working memory (current session)
        self.working_memory: Dict[str, Any] = {}
    
    async def initialize(self):
        """Initialize database tables."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    action TEXT NOT NULL,
                    shares INTEGER NOT NULL,
                    price REAL NOT NULL,
                    score REAL NOT NULL,
                    regime TEXT NOT NULL,
                    sector TEXT,
                    rationale TEXT,
                    confidence REAL,
                    context_json TEXT,
                    
                    -- Outcome (filled 1-4 weeks later)
                    outcome_pct REAL,
                    outcome_date TEXT,
                    lesson_learned TEXT,
                    
                    -- Embedding stored as JSON array
                    embedding_json TEXT,
                    
                    -- Indexes
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_decisions_ticker ON decisions(ticker)
            """)
            
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_decisions_outcome ON decisions(outcome_pct)
            """)
            
            await db.commit()
            
        logger.info(f"Agent memory initialized at {self.db_path}")
    
    async def store_decision(
        self, 
        decision: Decision,
        context: Optional[Any] = None
    ) -> int:
        """
        Store a decision in memory.
        
        Returns the decision ID for later outcome update.
        """
        # Generate embedding
        embedding = await self._generate_embedding(decision, context)
        
        # Serialize context
        context_json = "{}"
        if context:
            try:
                context_json = json.dumps(context.to_dict() if hasattr(context, 'to_dict') else context)
            except:
                context_json = "{}"
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO decisions 
                (timestamp, ticker, action, shares, price, score, regime, 
                 sector, rationale, confidence, context_json, embedding_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                context_json,
                json.dumps(embedding) if embedding else None,
            ))
            
            await db.commit()
            decision_id = cursor.lastrowid
        
        logger.info(f"Stored decision {decision_id}: {decision.action} {decision.ticker}")
        return decision_id
    
    async def retrieve_similar(
        self, 
        context: Any, 
        k: int = 10,
        only_with_outcomes: bool = True
    ) -> List[Memory]:
        """
        Retrieve similar past situations using embedding similarity.
        
        Args:
            context: Current trading context
            k: Number of similar decisions to return
            only_with_outcomes: Only return decisions with known outcomes
            
        Returns:
            List of Memory objects sorted by similarity
        """
        # Generate embedding for current context
        query_embedding = await self._embed_context(context)
        
        if query_embedding is None:
            logger.warning("Could not generate query embedding, returning empty")
            return []
        
        # Fetch all decisions with embeddings
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            query = """
                SELECT id, ticker, action, score, regime, outcome_pct, 
                       rationale, lesson_learned, embedding_json
                FROM decisions
                WHERE embedding_json IS NOT NULL
            """
            
            if only_with_outcomes:
                query += " AND outcome_pct IS NOT NULL"
            
            cursor = await db.execute(query)
            rows = await cursor.fetchall()
        
        if not rows:
            return []
        
        # Calculate similarities
        similarities = []
        query_vec = np.array(query_embedding)
        
        for row in rows:
            embedding = json.loads(row['embedding_json'])
            row_vec = np.array(embedding)
            
            # Cosine similarity
            similarity = np.dot(query_vec, row_vec) / (
                np.linalg.norm(query_vec) * np.linalg.norm(row_vec) + 1e-8
            )
            
            similarities.append((row, float(similarity)))
        
        # Sort by similarity (descending)
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        # Return top k
        results = []
        for row, similarity in similarities[:k]:
            results.append(Memory(
                ticker=row['ticker'],
                action=row['action'],
                score=row['score'],
                regime=row['regime'],
                outcome_pct=row['outcome_pct'] or 0.0,
                rationale=row['rationale'] or "",
                lesson_learned=row['lesson_learned'],
                similarity=similarity,
            ))
        
        return results
    
    async def update_outcome(
        self, 
        decision_id: int, 
        outcome_pct: float,
        lesson_learned: Optional[str] = None
    ):
        """
        Update the outcome of a past decision.
        
        Called after the trade is closed (1-4 weeks later).
        """
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE decisions
                SET outcome_pct = ?,
                    outcome_date = ?,
                    lesson_learned = ?
                WHERE id = ?
            """, (
                outcome_pct,
                datetime.now(timezone.utc).isoformat(),
                lesson_learned,
                decision_id,
            ))
            
            await db.commit()
        
        logger.info(f"Updated decision {decision_id} outcome: {outcome_pct:+.2f}%")
    
    async def get_pending_outcomes(self, min_age_days: int = 14) -> List[Dict]:
        """
        Get decisions that need outcome tracking.
        
        Returns decisions older than min_age_days without an outcome.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=min_age_days)
        
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            cursor = await db.execute("""
                SELECT id, timestamp, ticker, action, shares, price, score
                FROM decisions
                WHERE outcome_pct IS NULL
                  AND timestamp < ?
                ORDER BY timestamp ASC
            """, (cutoff.isoformat(),))
            
            rows = await cursor.fetchall()
        
        return [dict(row) for row in rows]
    
    async def get_recent_decisions(self, limit: int = 50) -> List[Decision]:
        """Get most recent decisions (short-term memory)."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            cursor = await db.execute("""
                SELECT * FROM decisions
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))
            
            rows = await cursor.fetchall()
        
        decisions = []
        for row in rows:
            decisions.append(Decision(
                id=row['id'],
                timestamp=datetime.fromisoformat(row['timestamp']) if row['timestamp'] else None,
                ticker=row['ticker'],
                action=row['action'],
                shares=row['shares'],
                price=row['price'],
                score=row['score'],
                regime=row['regime'],
                sector=row['sector'],
                rationale=row['rationale'],
                confidence=row['confidence'],
                outcome_pct=row['outcome_pct'],
                outcome_date=datetime.fromisoformat(row['outcome_date']) if row['outcome_date'] else None,
                lesson_learned=row['lesson_learned'],
            ))
        
        return decisions
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get memory statistics."""
        async with aiosqlite.connect(self.db_path) as db:
            # Total decisions
            cursor = await db.execute("SELECT COUNT(*) FROM decisions")
            total = (await cursor.fetchone())[0]
            
            # With outcomes
            cursor = await db.execute("SELECT COUNT(*) FROM decisions WHERE outcome_pct IS NOT NULL")
            with_outcomes = (await cursor.fetchone())[0]
            
            # Win rate
            cursor = await db.execute("""
                SELECT COUNT(*) FROM decisions 
                WHERE outcome_pct IS NOT NULL AND outcome_pct > 0
            """)
            wins = (await cursor.fetchone())[0]
            
            # Average outcome
            cursor = await db.execute("""
                SELECT AVG(outcome_pct) FROM decisions 
                WHERE outcome_pct IS NOT NULL
            """)
            avg_outcome = (await cursor.fetchone())[0] or 0
            
            # By action
            cursor = await db.execute("""
                SELECT action, COUNT(*), AVG(outcome_pct)
                FROM decisions
                WHERE outcome_pct IS NOT NULL
                GROUP BY action
            """)
            by_action = await cursor.fetchall()
        
        return {
            "total_decisions": total,
            "with_outcomes": with_outcomes,
            "pending_outcomes": total - with_outcomes,
            "win_rate": wins / with_outcomes if with_outcomes > 0 else 0,
            "avg_outcome_pct": avg_outcome,
            "by_action": {row[0]: {"count": row[1], "avg_pct": row[2]} for row in by_action},
        }
    
    # Embedding generation
    
    async def _generate_embedding(
        self, 
        decision: Decision, 
        context: Optional[Any]
    ) -> Optional[List[float]]:
        """Generate embedding for a decision."""
        text = self._decision_to_text(decision, context)
        return await self._embed_text(text)
    
    async def _embed_context(self, context: Any) -> Optional[List[float]]:
        """Generate embedding for a trading context."""
        text = self._context_to_text(context)
        return await self._embed_text(text)
    
    async def _embed_text(self, text: str) -> Optional[List[float]]:
        """
        Generate embedding for text.
        
        Uses OpenAI embeddings if available, otherwise generates
        a deterministic hash-based pseudo-embedding for development.
        """
        try:
            # Try OpenAI
            import openai
            
            if self._embedding_client is None:
                import os
                self._embedding_client = openai.AsyncOpenAI(
                    api_key=os.environ.get("OPENAI_API_KEY")
                )
            
            response = await self._embedding_client.embeddings.create(
                model=self.embedding_model,
                input=text
            )
            
            return response.data[0].embedding
            
        except Exception as e:
            logger.debug(f"OpenAI embedding failed: {e}, using hash-based fallback")
            return self._hash_embedding(text)
    
    def _hash_embedding(self, text: str) -> List[float]:
        """
        Generate deterministic pseudo-embedding from text hash.
        
        NOT for production - just for development/testing.
        Same text always produces same embedding.
        """
        # Hash the text
        hash_bytes = hashlib.sha256(text.encode()).digest()
        
        # Expand to EMBEDDING_DIM using repeated hashing
        embeddings = []
        seed = hash_bytes
        
        while len(embeddings) < EMBEDDING_DIM:
            # Hash again with counter
            for i in range(32):
                if len(embeddings) >= EMBEDDING_DIM:
                    break
                # Convert byte to float in [-1, 1]
                val = (seed[i % len(seed)] - 128) / 128.0
                embeddings.append(val)
            seed = hashlib.sha256(seed).digest()
        
        # Normalize to unit length
        arr = np.array(embeddings[:EMBEDDING_DIM])
        arr = arr / (np.linalg.norm(arr) + 1e-8)
        
        return arr.tolist()
    
    def _decision_to_text(self, decision: Decision, context: Optional[Any]) -> str:
        """Convert decision + context to text for embedding."""
        parts = [
            f"Action: {decision.action} {decision.ticker}",
            f"Score: {decision.score:.0f}",
            f"Regime: {decision.regime}",
            f"Sector: {decision.sector}",
        ]
        
        if context:
            if hasattr(context, 'market'):
                parts.append(f"VIX: {context.market.vix:.1f}")
                parts.append(f"Trend: {context.market.trend}")
            if hasattr(context, 'portfolio'):
                cash_pct = context.portfolio.cash / context.portfolio.total_value * 100
                parts.append(f"Cash: {cash_pct:.0f}%")
        
        if decision.rationale:
            parts.append(f"Rationale: {decision.rationale}")
        
        return " | ".join(parts)
    
    def _context_to_text(self, context: Any) -> str:
        """Convert trading context to text for embedding."""
        if hasattr(context, 'market') and hasattr(context, 'portfolio'):
            parts = [
                f"Regime: {context.market.regime}",
                f"VIX: {context.market.vix:.1f}",
                f"Trend: {context.market.trend}",
                f"Positions: {context.portfolio.position_count}",
            ]
            
            # Add top candidates
            if context.buy_candidates:
                top_buys = [c.ticker for c in context.buy_candidates[:3]]
                parts.append(f"Top BUY: {', '.join(top_buys)}")
            
            return " | ".join(parts)
        
        # Fallback for dict-like context
        if isinstance(context, dict):
            return json.dumps(context, sort_keys=True)[:500]
        
        return str(context)[:500]


# Convenience function
async def get_agent_memory() -> AgentMemory:
    """Get initialized agent memory instance."""
    memory = AgentMemory()
    await memory.initialize()
    return memory


# CLI
if __name__ == "__main__":
    import asyncio
    import argparse
    
    parser = argparse.ArgumentParser(description="Agent Memory System")
    parser.add_argument("--stats", action="store_true", help="Show memory statistics")
    parser.add_argument("--recent", type=int, default=0, help="Show N recent decisions")
    parser.add_argument("--pending", action="store_true", help="Show pending outcomes")
    
    args = parser.parse_args()
    
    async def main():
        memory = await get_agent_memory()
        
        if args.stats:
            stats = await memory.get_statistics()
            print("\n=== Agent Memory Statistics ===")
            print(f"Total decisions: {stats['total_decisions']}")
            print(f"With outcomes: {stats['with_outcomes']}")
            print(f"Pending: {stats['pending_outcomes']}")
            print(f"Win rate: {stats['win_rate']:.1%}")
            print(f"Avg outcome: {stats['avg_outcome_pct']:+.2f}%")
        
        elif args.recent > 0:
            decisions = await memory.get_recent_decisions(args.recent)
            print(f"\n=== Last {len(decisions)} Decisions ===")
            for d in decisions:
                outcome = f"{d.outcome_pct:+.1f}%" if d.outcome_pct else "pending"
                print(f"{d.timestamp.strftime('%Y-%m-%d')}: {d.action} {d.ticker} @ ${d.price:.2f} → {outcome}")
        
        elif args.pending:
            pending = await memory.get_pending_outcomes()
            print(f"\n=== Pending Outcomes ({len(pending)}) ===")
            for p in pending:
                print(f"ID {p['id']}: {p['action']} {p['ticker']} ({p['timestamp'][:10]})")
        
        else:
            parser.print_help()
    
    asyncio.run(main())
