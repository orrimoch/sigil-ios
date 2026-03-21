"""
Agent Memory System (REC-281, REC-282)

Three-tier memory for agent learning:
1. Working Memory: Current session context (RAM)
2. Short-Term Memory: Recent decisions (PostgreSQL)
3. Long-Term Memory: Historical patterns with embeddings (pgvector)

Uses PostgreSQL with pgvector for efficient vector similarity search.
"""

import json
import os
import numpy as np
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Any
from pathlib import Path
from loguru import logger
import asyncpg
from pgvector.asyncpg import register_vector

# Add src to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))


# Embedding dimension (OpenAI text-embedding-3-small = 1536)
EMBEDDING_DIM = 1536

# Default database URL (local PostgreSQL)


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
    embedding: Optional[np.ndarray] = None
    
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
    Three-tier memory system for the trading agent using PostgreSQL + pgvector.
    
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
    
    def __init__(
        self, 
        database_url: str = None,
        embedding_model: str = "text-embedding-3-small"
    ):
        self.embedding_model = embedding_model
        self._pool: Optional[asyncpg.Pool] = None
        self._embedding_client = None
        
        # Working memory (current session)
        self.working_memory: Dict[str, Any] = {}
    
    async def initialize(self):
        """Initialize database connection pool."""
        self._pool = await asyncpg.create_pool(
            self.database_url,
            min_size=2,
            max_size=10,
            init=self._init_connection
        )
        logger.info(f"Agent memory connected to PostgreSQL")
    
    async def _init_connection(self, conn):
        """Initialize each connection with pgvector support."""
        await register_vector(conn)
    
    async def close(self):
        """Close the connection pool."""
        if self._pool:
            await self._pool.close()
    
    async def store_decision(
        self, 
        decision: Any,
        context: Optional[Any] = None,
        user_id: Optional[str] = None,
    ) -> int:
        """
        Store a decision in memory.
        
        Accepts either a Decision dataclass or a DecisionResult from decision_engine.
        Returns the decision ID for later outcome update.
        """
        # Handle DecisionResult from decision_engine
        if hasattr(decision, 'ticker') and not isinstance(decision, Decision):
            # Convert DecisionResult to Decision-like
            dec = Decision(
                ticker=decision.ticker,
                action=decision.action,
                shares=getattr(decision, 'shares', 0),
                price=getattr(decision, 'price', 0.0),
                score=decision.score,
                regime=getattr(decision, 'regime', 'normal'),
                sector=decision.sector,
                rationale=decision.rationale,
                confidence=decision.confidence,
            )
        else:
            dec = decision
        
        # Generate embedding
        embedding = await self._generate_embedding(dec, context)
        
        # Serialize context
        context_json = {}
        if context:
            try:
                context_json = context.to_dict() if hasattr(context, 'to_dict') else context
            except:
                context_json = {}
        
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO agent_decisions 
                (timestamp, ticker, action, shares, price, score, regime, 
                 sector, rationale, confidence, context_json, embedding, user_id)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                RETURNING id
            """,
                dec.timestamp or datetime.now(timezone.utc),
                dec.ticker,
                dec.action,
                dec.shares,
                dec.price,
                dec.score,
                dec.regime,
                dec.sector,
                dec.rationale,
                dec.confidence,
                json.dumps(context_json),
                embedding,
                user_id,
            )
            decision_id = row['id']
        
        logger.info(f"Stored decision {decision_id}: {dec.action} {dec.ticker}")
        return decision_id
    
    async def retrieve_similar(
        self, 
        context: Any, 
        k: int = 10,
        only_with_outcomes: bool = True
    ) -> List[Memory]:
        """
        Retrieve similar past situations using pgvector similarity search.
        
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
        
        # Query using pgvector cosine similarity
        async with self._pool.acquire() as conn:
            query = """
                SELECT id, ticker, action, score, regime, outcome_pct, 
                       rationale, lesson_learned,
                       1 - (embedding <=> $1) as similarity
                FROM agent_decisions
                WHERE embedding IS NOT NULL
            """
            
            if only_with_outcomes:
                query += " AND outcome_pct IS NOT NULL"
            
            query += """
                ORDER BY embedding <=> $1
                LIMIT $2
            """
            
            rows = await conn.fetch(query, query_embedding, k)
        
        results = []
        for row in rows:
            results.append(Memory(
                ticker=row['ticker'],
                action=row['action'],
                score=float(row['score']),
                regime=row['regime'],
                outcome_pct=float(row['outcome_pct']) if row['outcome_pct'] else 0.0,
                rationale=row['rationale'] or "",
                lesson_learned=row['lesson_learned'],
                similarity=float(row['similarity']),
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
        async with self._pool.acquire() as conn:
            await conn.execute("""
                UPDATE agent_decisions
                SET outcome_pct = $1,
                    outcome_date = $2,
                    lesson_learned = $3
                WHERE id = $4
            """,
                outcome_pct,
                datetime.now(timezone.utc),
                lesson_learned,
                decision_id,
            )
        
        logger.info(f"Updated decision {decision_id} outcome: {outcome_pct:+.2f}%")
    
    async def get_pending_outcomes(self, min_age_days: int = 14) -> List[Dict]:
        """
        Get decisions that need outcome tracking.
        
        Returns decisions older than min_age_days without an outcome.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=min_age_days)
        
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT id, timestamp, ticker, action, shares, price, score
                FROM agent_decisions
                WHERE outcome_pct IS NULL
                  AND timestamp < $1
                ORDER BY timestamp ASC
            """, cutoff)
        
        return [dict(row) for row in rows]
    
    async def get_decisions_without_outcomes(
        self,
        after: datetime,
        before: datetime,
        limit: int = 10,
    ) -> List[Decision]:
        """
        Get decisions without outcomes within a date range.
        
        Used by the learning loop to find decisions needing outcome updates.
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT id, timestamp, ticker, action, shares, price, score,
                       regime, sector, rationale, confidence, user_id
                FROM agent_decisions
                WHERE outcome_pct IS NULL
                  AND timestamp BETWEEN $1 AND $2
                ORDER BY timestamp ASC
                LIMIT $3
            """, after, before, limit)
        
        decisions = []
        for row in rows:
            decisions.append(Decision(
                id=row['id'],
                timestamp=row['timestamp'],
                ticker=row['ticker'],
                action=row['action'],
                shares=row['shares'],
                price=float(row['price']),
                score=float(row['score']),
                regime=row['regime'],
                sector=row['sector'],
                rationale=row['rationale'],
                confidence=float(row['confidence']) if row['confidence'] else 0.0,
            ))
        
        return decisions
    
    async def store_lesson(self, decision_id: int, lesson: str):
        """
        Store a lesson learned for a decision.
        
        Called by the learning loop after generating a lesson from outcome.
        """
        async with self._pool.acquire() as conn:
            await conn.execute("""
                UPDATE agent_decisions
                SET lesson_learned = $1
                WHERE id = $2
            """, lesson, decision_id)
        
        logger.info(f"Stored lesson for decision {decision_id}")
    
    async def get_recent_decisions(
        self, 
        limit: int = 50,
        user_id: Optional[str] = None,
        ticker: Optional[str] = None,
        action: Optional[str] = None,
    ) -> List[Decision]:
        """
        Get most recent decisions (short-term memory).
        
        Supports optional filters for user, ticker, and action.
        """
        # Build query dynamically based on filters
        query = """
            SELECT id, timestamp, ticker, action, shares, price, score,
                   regime, sector, rationale, confidence, outcome_pct,
                   outcome_date, lesson_learned
            FROM agent_decisions
            WHERE 1=1
        """
        params = []
        param_idx = 1
        
        if user_id:
            query += f" AND user_id = ${param_idx}"
            params.append(user_id)
            param_idx += 1
        
        if ticker:
            query += f" AND ticker = ${param_idx}"
            params.append(ticker.upper())
            param_idx += 1
        
        if action:
            query += f" AND action = ${param_idx}"
            params.append(action.upper())
            param_idx += 1
        
        query += f" ORDER BY timestamp DESC LIMIT ${param_idx}"
        params.append(limit)
        
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
        
        decisions = []
        for row in rows:
            decisions.append(Decision(
                id=row['id'],
                timestamp=row['timestamp'],
                ticker=row['ticker'],
                action=row['action'],
                shares=row['shares'],
                price=float(row['price']),
                score=float(row['score']),
                regime=row['regime'],
                sector=row['sector'],
                rationale=row['rationale'],
                confidence=float(row['confidence']) if row['confidence'] else 0.0,
                outcome_pct=float(row['outcome_pct']) if row['outcome_pct'] else None,
                outcome_date=row['outcome_date'],
                lesson_learned=row['lesson_learned'],
            ))
        
        return decisions
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get memory statistics."""
        async with self._pool.acquire() as conn:
            # Total decisions
            total = await conn.fetchval("SELECT COUNT(*) FROM agent_decisions")
            
            # With outcomes
            with_outcomes = await conn.fetchval(
                "SELECT COUNT(*) FROM agent_decisions WHERE outcome_pct IS NOT NULL"
            )
            
            # Win rate
            wins = await conn.fetchval("""
                SELECT COUNT(*) FROM agent_decisions 
                WHERE outcome_pct IS NOT NULL AND outcome_pct > 0
            """)
            
            # Average outcome
            avg_outcome = await conn.fetchval("""
                SELECT AVG(outcome_pct) FROM agent_decisions 
                WHERE outcome_pct IS NOT NULL
            """) or 0
            
            # By action
            action_stats = await conn.fetch("""
                SELECT action, COUNT(*) as count, AVG(outcome_pct) as avg_pct
                FROM agent_decisions
                WHERE outcome_pct IS NOT NULL
                GROUP BY action
            """)
        
        return {
            "total_decisions": total,
            "with_outcomes": with_outcomes,
            "pending_outcomes": total - with_outcomes,
            "win_rate": wins / with_outcomes if with_outcomes > 0 else 0,
            "avg_outcome_pct": float(avg_outcome),
            "by_action": {
                row['action']: {
                    "count": row['count'], 
                    "avg_pct": float(row['avg_pct']) if row['avg_pct'] else 0
                } 
                for row in action_stats
            },
        }
    
    # Import/Export methods
    
    async def import_memories(
        self,
        import_path: str,
        skip_existing: bool = True,
        batch_size: int = 50,
    ) -> Dict[str, Any]:
        """
        Import pre-built memories from JSON file (cold start solution).
        
        Accepts memories exported from the evaluation experiment.
        Generates OpenAI embeddings for each memory on import.
        
        Args:
            import_path: Path to JSON export file
            skip_existing: Skip memories with same ticker+timestamp
            batch_size: Batch size for embedding generation
            
        Returns:
            Stats dict with imported, skipped, failed counts
        """
        import json
        from pathlib import Path
        
        logger.info(f"Importing memories from {import_path}")
        
        with open(import_path) as f:
            data = json.load(f)
        
        if data.get("version") != "1.0":
            raise ValueError(f"Unknown export format version: {data.get('version')}")
        
        memories = data.get("memories", [])
        logger.info(f"Found {len(memories)} memories to import")
        
        stats = {"imported": 0, "skipped": 0, "failed": 0}
        
        async with self._pool.acquire() as conn:
            for i, mem in enumerate(memories):
                try:
                    # Check if exists
                    if skip_existing:
                        existing = await conn.fetchval("""
                            SELECT id FROM agent_decisions
                            WHERE ticker = $1 AND timestamp = $2
                        """, mem["ticker"], mem["timestamp"])
                        
                        if existing:
                            stats["skipped"] += 1
                            continue
                    
                    # Create Decision for embedding
                    decision = Decision(
                        timestamp=datetime.fromisoformat(mem["timestamp"].replace("Z", "+00:00")),
                        ticker=mem["ticker"],
                        action=mem["action"],
                        shares=mem.get("shares", 0),
                        price=mem.get("price", 0.0),
                        score=mem["score"],
                        regime=mem["regime"],
                        sector=mem["sector"],
                        rationale=mem["rationale"],
                        confidence=mem.get("confidence", 0.7),
                        outcome_pct=mem.get("outcome_pct"),
                        lesson_learned=mem.get("lesson_learned"),
                    )
                    
                    # Generate embedding
                    embedding = await self._generate_embedding(decision, None)
                    
                    # Insert
                    await conn.execute("""
                        INSERT INTO agent_decisions
                        (timestamp, ticker, action, shares, price, score, regime,
                         sector, rationale, confidence, outcome_pct, lesson_learned,
                         embedding, context_json)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                    """,
                        decision.timestamp,
                        decision.ticker,
                        decision.action,
                        decision.shares,
                        decision.price,
                        decision.score,
                        decision.regime,
                        decision.sector,
                        decision.rationale,
                        decision.confidence,
                        decision.outcome_pct,
                        decision.lesson_learned,
                        embedding,
                        json.dumps({"source": "imported", "train_period": data.get("train_period")}),
                    )
                    
                    stats["imported"] += 1
                    
                    if (i + 1) % 50 == 0:
                        logger.info(f"Progress: {i + 1}/{len(memories)}")
                        
                except Exception as e:
                    logger.error(f"Failed to import memory {mem.get('ticker')}: {e}")
                    stats["failed"] += 1
        
        logger.info(f"Import complete: {stats}")
        return stats
    
    async def export_memories(
        self,
        output_path: str,
        only_with_outcomes: bool = True,
    ) -> Dict[str, Any]:
        """
        Export memories to JSON for backup or transfer.
        
        Args:
            output_path: Path for output JSON file
            only_with_outcomes: Only export decisions with known outcomes
            
        Returns:
            Stats dict with export count
        """
        import json
        
        query = """
            SELECT timestamp, ticker, action, shares, price, score, regime,
                   sector, rationale, confidence, outcome_pct, lesson_learned
            FROM agent_decisions
        """
        if only_with_outcomes:
            query += " WHERE outcome_pct IS NOT NULL"
        query += " ORDER BY timestamp"
        
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query)
        
        memories = []
        for row in rows:
            memories.append({
                "timestamp": row["timestamp"].isoformat(),
                "ticker": row["ticker"],
                "action": row["action"],
                "shares": row["shares"],
                "price": float(row["price"]),
                "score": float(row["score"]),
                "regime": row["regime"],
                "sector": row["sector"],
                "rationale": row["rationale"],
                "confidence": float(row["confidence"]) if row["confidence"] else 0.7,
                "outcome_pct": float(row["outcome_pct"]) if row["outcome_pct"] else None,
                "lesson_learned": row["lesson_learned"],
            })
        
        export_data = {
            "version": "1.0",
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "source": "sigil_agent_production",
            "memory_count": len(memories),
            "memories": memories,
        }
        
        with open(output_path, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        logger.info(f"Exported {len(memories)} memories to {output_path}")
        return {"exported": len(memories)}
    
    # Embedding generation
    
    async def _generate_embedding(
        self, 
        decision: Decision, 
        context: Optional[Any]
    ) -> Optional[np.ndarray]:
        """Generate embedding for a decision."""
        text = self._decision_to_text(decision, context)
        return await self._embed_text(text)
    
    async def _embed_context(self, context: Any) -> Optional[np.ndarray]:
        """Generate embedding for a trading context."""
        text = self._context_to_text(context)
        return await self._embed_text(text)
    
    async def _embed_text(self, text: str) -> Optional[np.ndarray]:
        """
        Generate embedding for text.
        
        Uses OpenAI embeddings if available, otherwise generates
        a deterministic hash-based pseudo-embedding for development.
        """
        try:
            # Try OpenAI
            import openai
            
            if self._embedding_client is None:
                self._embedding_client = openai.AsyncOpenAI(
                )
            
            response = await self._embedding_client.embeddings.create(
                model=self.embedding_model,
                input=text
            )
            
            return np.array(response.data[0].embedding)
            
        except Exception as e:
            logger.debug(f"OpenAI embedding failed: {e}, using hash-based fallback")
            return self._hash_embedding(text)
    
    def _hash_embedding(self, text: str) -> np.ndarray:
        """
        Generate deterministic pseudo-embedding from text hash.
        
        NOT for production - just for development/testing.
        Same text always produces same embedding.
        """
        import hashlib
        
        # Hash the text
        hash_bytes = hashlib.sha256(text.encode()).digest()
        
        # Expand to EMBEDDING_DIM using repeated hashing
        embeddings = []
        seed = hash_bytes
        
        while len(embeddings) < EMBEDDING_DIM:
            for i in range(32):
                if len(embeddings) >= EMBEDDING_DIM:
                    break
                val = (seed[i % len(seed)] - 128) / 128.0
                embeddings.append(val)
            seed = hashlib.sha256(seed).digest()
        
        # Normalize to unit length
        arr = np.array(embeddings[:EMBEDDING_DIM])
        arr = arr / (np.linalg.norm(arr) + 1e-8)
        
        return arr
    
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
            
            if context.buy_candidates:
                top_buys = [c.ticker for c in context.buy_candidates[:3]]
                parts.append(f"Top BUY: {', '.join(top_buys)}")
            
            return " | ".join(parts)
        
        if isinstance(context, dict):
            return json.dumps(context, sort_keys=True)[:500]
        
        return str(context)[:500]


# Convenience function
async def get_agent_memory(database_url: str = None) -> AgentMemory:
    """Get initialized agent memory instance."""
    memory = AgentMemory(database_url=database_url)
    await memory.initialize()
    return memory


# CLI
if __name__ == "__main__":
    import asyncio
    import argparse
    
    parser = argparse.ArgumentParser(description="Agent Memory System (pgvector)")
    parser.add_argument("--stats", action="store_true", help="Show memory statistics")
    parser.add_argument("--recent", type=int, default=0, help="Show N recent decisions")
    parser.add_argument("--pending", action="store_true", help="Show pending outcomes")
    parser.add_argument("--test", action="store_true", help="Run a test store/retrieve")
    parser.add_argument("--import-file", type=str, help="Import memories from JSON file (cold start)")
    parser.add_argument("--export-file", type=str, help="Export memories to JSON file")
    
    args = parser.parse_args()
    
    async def main():
        memory = await get_agent_memory()
        
        try:
            if args.stats:
                stats = await memory.get_statistics()
                print("\n=== Agent Memory Statistics (pgvector) ===")
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
                    print(f"ID {p['id']}: {p['action']} {p['ticker']} ({p['timestamp'].strftime('%Y-%m-%d')})")
            
            elif args.import_file:
                print(f"\n=== Importing Memories from {args.import_file} ===")
                stats = await memory.import_memories(args.import_file)
                print(f"✅ Imported: {stats['imported']}")
                print(f"⏭️ Skipped: {stats['skipped']}")
                print(f"❌ Failed: {stats['failed']}")
            
            elif args.export_file:
                print(f"\n=== Exporting Memories to {args.export_file} ===")
                stats = await memory.export_memories(args.export_file)
                print(f"✅ Exported: {stats['exported']} memories")
            
            elif args.test:
                print("\n=== Testing pgvector Memory ===")
                
                # Store a test decision
                decision = Decision(
                    ticker='TEST',
                    action='BUY',
                    shares=10,
                    price=100.0,
                    score=85.0,
                    regime='normal',
                    sector='Technology',
                    rationale='Test decision',
                    confidence=0.8,
                )
                
                decision_id = await memory.store_decision(decision)
                print(f"✅ Stored decision {decision_id}")
                
                # Update outcome
                await memory.update_outcome(decision_id, outcome_pct=5.0, lesson_learned="Test lesson")
                print(f"✅ Updated outcome")
                
                # Get stats
                stats = await memory.get_statistics()
                print(f"✅ Stats: {stats['total_decisions']} decisions, {stats['win_rate']:.0%} win rate")
                
                print("\n✅ pgvector memory working!")
            
            else:
                parser.print_help()
        
        finally:
            await memory.close()
    
    asyncio.run(main())
