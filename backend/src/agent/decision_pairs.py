"""
Decision Pair Logging Module (REC-298)

Automated logging of decision pairs for potential DPO training.

Logs:
- Full context at decision time (market state, scores, positions)
- Decision made (action, ticker, rationale)
- Outcome (P&L%, timing)
- Generated lesson

Target: 500+ pairs over 6 months of operation.

Export formats:
- JSONL for DPO training (context, chosen, rejected)
- CSV for analysis
- JSON for backup

The pairing logic creates training pairs by:
1. Grouping decisions by similar context (same regime, similar sector mix)
2. Pairing high-outcome decisions with low-outcome ones
3. Using the context as prompt, outcome as preference signal
"""

import json
import asyncio
import aiosqlite
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Any, Tuple
from pathlib import Path
from loguru import logger

# Database path
DB_PATH = Path(__file__).parent.parent.parent / "data" / "decision_pairs.db"


@dataclass
class DecisionContext:
    """Full context at decision time - serves as the 'prompt' for training."""
    timestamp: str
    
    # Market regime
    regime: str  # low_vol, normal, high_vol, crisis
    vix_level: float
    
    # Portfolio state
    portfolio_value: float
    cash_available: float
    positions_count: int
    sector_exposure: Dict[str, float]  # {sector: allocation %}
    
    # Candidate info
    ticker: str
    ticker_score: float
    ticker_sector: str
    ticker_price: float
    ticker_market_cap: float
    ticker_sentiment: float
    ticker_technical: float
    ticker_fundamental: float
    
    # Top alternatives (for context)
    top_candidates: List[Dict[str, Any]] = field(default_factory=list)
    
    # Recent history
    recent_trades: List[Dict[str, Any]] = field(default_factory=list)
    recent_outcomes: List[float] = field(default_factory=list)  # Last 5 P&L%
    
    def to_prompt(self) -> str:
        """Convert context to natural language prompt for training."""
        return f"""Market Context:
- Regime: {self.regime} (VIX: {self.vix_level:.1f})
- Portfolio: ${self.portfolio_value:,.0f} ({self.positions_count} positions, ${self.cash_available:,.0f} cash)
- Sector Exposure: {', '.join(f'{s}: {p:.1%}' for s, p in self.sector_exposure.items())}
- Recent Performance: {', '.join(f'{p:+.1f}%' for p in self.recent_outcomes) if self.recent_outcomes else 'None'}

Candidate Stock: {self.ticker}
- Composite Score: {self.ticker_score:.1f}/100
- Sector: {self.ticker_sector}
- Price: ${self.ticker_price:.2f}
- Sentiment: {self.ticker_sentiment:.1f}, Technical: {self.ticker_technical:.1f}, Fundamental: {self.ticker_fundamental:.1f}

Top Alternatives: {', '.join(f"{c['ticker']} ({c['score']:.0f})" for c in self.top_candidates[:3]) if self.top_candidates else 'None'}

Decision: Should we BUY, SELL, or HOLD {self.ticker}? If trading, how many shares?"""


@dataclass
class DecisionRecord:
    """Complete record of a decision for logging."""
    id: Optional[int] = None
    user_id: str = ""
    
    # Context at decision time
    context: Optional[DecisionContext] = None
    context_json: str = "{}"
    
    # The decision made
    action: str = ""  # BUY, SELL, HOLD
    shares: int = 0
    rationale: str = ""
    confidence: float = 0.0
    
    # Execution details (filled after trade)
    executed: bool = False
    fill_price: Optional[float] = None
    fill_timestamp: Optional[str] = None
    order_id: Optional[str] = None
    
    # Outcome (filled later by learning loop)
    outcome_pct: Optional[float] = None
    outcome_timestamp: Optional[str] = None
    lesson_learned: Optional[str] = None
    
    # Preference label (for DPO)
    # 1 = preferred (good outcome), 0 = neutral, -1 = dispreferred (bad outcome)
    preference: int = 0
    
    # Timestamps
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "context_json": self.context_json,
            "action": self.action,
            "shares": self.shares,
            "rationale": self.rationale,
            "confidence": self.confidence,
            "executed": self.executed,
            "fill_price": self.fill_price,
            "fill_timestamp": self.fill_timestamp,
            "order_id": self.order_id,
            "outcome_pct": self.outcome_pct,
            "outcome_timestamp": self.outcome_timestamp,
            "lesson_learned": self.lesson_learned,
            "preference": self.preference,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
    
    def get_ticker(self) -> str:
        """Extract ticker from context."""
        try:
            ctx = json.loads(self.context_json)
            return ctx.get("ticker", "")
        except:
            return ""


@dataclass
class DecisionPair:
    """A pair of decisions for DPO training."""
    context_prompt: str
    chosen_response: str  # Better outcome
    rejected_response: str  # Worse outcome
    chosen_outcome_pct: float
    rejected_outcome_pct: float
    regime: str
    
    def to_dpo_format(self) -> Dict[str, str]:
        """Convert to standard DPO training format."""
        return {
            "prompt": self.context_prompt,
            "chosen": self.chosen_response,
            "rejected": self.rejected_response,
        }


class DecisionPairLogger:
    """
    Logs and manages decision pairs for training data collection.
    
    Usage:
        logger = DecisionPairLogger()
        await logger.initialize()
        
        # Log a decision
        record_id = await logger.log_decision(context, action, rationale, ...)
        
        # Update with outcome
        await logger.record_outcome(record_id, outcome_pct, lesson)
        
        # Export for training
        pairs = await logger.generate_training_pairs()
        await logger.export_to_jsonl("training_data.jsonl")
    """
    
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._initialized = False
    
    async def initialize(self):
        """Initialize database tables."""
        if self._initialized:
            return
        
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        async with aiosqlite.connect(self.db_path) as db:
            # Decision records table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS decision_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    context_json TEXT NOT NULL,
                    action TEXT NOT NULL,
                    shares INTEGER DEFAULT 0,
                    rationale TEXT,
                    confidence REAL DEFAULT 0.0,
                    executed INTEGER DEFAULT 0,
                    fill_price REAL,
                    fill_timestamp TEXT,
                    order_id TEXT,
                    outcome_pct REAL,
                    outcome_timestamp TEXT,
                    lesson_learned TEXT,
                    preference INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            
            # Indexes for efficient querying
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_decision_user 
                ON decision_records(user_id)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_decision_created 
                ON decision_records(created_at)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_decision_outcome 
                ON decision_records(outcome_pct)
            """)
            
            # Generated pairs table (for caching)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS training_pairs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chosen_id INTEGER NOT NULL,
                    rejected_id INTEGER NOT NULL,
                    context_prompt TEXT NOT NULL,
                    chosen_response TEXT NOT NULL,
                    rejected_response TEXT NOT NULL,
                    chosen_outcome REAL NOT NULL,
                    rejected_outcome REAL NOT NULL,
                    regime TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (chosen_id) REFERENCES decision_records(id),
                    FOREIGN KEY (rejected_id) REFERENCES decision_records(id),
                    UNIQUE(chosen_id, rejected_id)
                )
            """)
            
            await db.commit()
        
        self._initialized = True
        logger.info(f"Decision pair logger initialized at {self.db_path}")
    
    async def log_decision(
        self,
        user_id: str,
        context: DecisionContext,
        action: str,
        shares: int = 0,
        rationale: str = "",
        confidence: float = 0.0,
    ) -> int:
        """
        Log a new decision with its full context.
        
        Returns the record ID for later outcome tracking.
        """
        await self.initialize()
        
        now = datetime.now(timezone.utc).isoformat()
        context_json = json.dumps(asdict(context), default=str)
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                INSERT INTO decision_records 
                (user_id, context_json, action, shares, rationale, confidence, 
                 created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, context_json, action, shares, rationale, confidence, now, now)
            )
            await db.commit()
            record_id = cursor.lastrowid
        
        logger.debug(f"Logged decision {record_id}: {action} for context ticker")
        return record_id
    
    async def record_execution(
        self,
        record_id: int,
        fill_price: float,
        order_id: str,
    ):
        """Record that a decision was executed."""
        await self.initialize()
        
        now = datetime.now(timezone.utc).isoformat()
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                UPDATE decision_records 
                SET executed = 1, fill_price = ?, fill_timestamp = ?, 
                    order_id = ?, updated_at = ?
                WHERE id = ?
                """,
                (fill_price, now, order_id, now, record_id)
            )
            await db.commit()
    
    async def record_outcome(
        self,
        record_id: int,
        outcome_pct: float,
        lesson: Optional[str] = None,
    ):
        """
        Record the outcome of a decision.
        
        Also sets the preference label:
        - outcome > +5%: preference = 1 (good)
        - outcome < -3%: preference = -1 (bad)
        - else: preference = 0 (neutral)
        """
        await self.initialize()
        
        now = datetime.now(timezone.utc).isoformat()
        
        # Determine preference
        if outcome_pct > 5.0:
            preference = 1
        elif outcome_pct < -3.0:
            preference = -1
        else:
            preference = 0
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                UPDATE decision_records 
                SET outcome_pct = ?, outcome_timestamp = ?, lesson_learned = ?,
                    preference = ?, updated_at = ?
                WHERE id = ?
                """,
                (outcome_pct, now, lesson, preference, now, record_id)
            )
            await db.commit()
        
        logger.debug(f"Recorded outcome for {record_id}: {outcome_pct:+.2f}% (pref={preference})")
    
    async def get_decisions_with_outcomes(
        self,
        user_id: Optional[str] = None,
        min_outcome: Optional[float] = None,
        max_outcome: Optional[float] = None,
        limit: int = 1000,
    ) -> List[DecisionRecord]:
        """Get decisions that have recorded outcomes."""
        await self.initialize()
        
        query = """
            SELECT * FROM decision_records 
            WHERE outcome_pct IS NOT NULL
        """
        params = []
        
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        
        if min_outcome is not None:
            query += " AND outcome_pct >= ?"
            params.append(min_outcome)
        
        if max_outcome is not None:
            query += " AND outcome_pct <= ?"
            params.append(max_outcome)
        
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()
        
        return [self._row_to_record(row) for row in rows]
    
    async def generate_training_pairs(
        self,
        min_outcome_diff: float = 5.0,
        max_pairs: int = 500,
    ) -> List[DecisionPair]:
        """
        Generate DPO training pairs from logged decisions.
        
        Pairing strategy:
        1. Get all decisions with outcomes
        2. Group by regime (similar market conditions)
        3. Within each group, pair high-outcome with low-outcome decisions
        4. Require minimum outcome difference for clear preference signal
        """
        await self.initialize()
        
        # Get all decisions with outcomes
        decisions = await self.get_decisions_with_outcomes(limit=2000)
        
        if len(decisions) < 2:
            logger.warning("Not enough decisions with outcomes for pairing")
            return []
        
        # Group by regime
        by_regime: Dict[str, List[DecisionRecord]] = {}
        for d in decisions:
            try:
                ctx = json.loads(d.context_json)
                regime = ctx.get("regime", "normal")
            except:
                regime = "normal"
            
            if regime not in by_regime:
                by_regime[regime] = []
            by_regime[regime].append(d)
        
        pairs = []
        
        for regime, group in by_regime.items():
            # Sort by outcome
            sorted_group = sorted(
                [d for d in group if d.outcome_pct is not None],
                key=lambda x: x.outcome_pct or 0,
                reverse=True
            )
            
            # Pair top half with bottom half
            n = len(sorted_group)
            for i in range(n // 4):  # Top quarter
                chosen = sorted_group[i]
                for j in range(n - 1, n - n // 4 - 1, -1):  # Bottom quarter
                    rejected = sorted_group[j]
                    
                    if chosen.outcome_pct is None or rejected.outcome_pct is None:
                        continue
                    
                    diff = chosen.outcome_pct - rejected.outcome_pct
                    if diff >= min_outcome_diff:
                        # Build context prompt from chosen decision
                        try:
                            ctx = json.loads(chosen.context_json)
                            context_obj = DecisionContext(**ctx)
                            prompt = context_obj.to_prompt()
                        except:
                            prompt = f"[Context unavailable for decision {chosen.id}]"
                        
                        pair = DecisionPair(
                            context_prompt=prompt,
                            chosen_response=f"{chosen.action} {chosen.shares} shares. Rationale: {chosen.rationale}",
                            rejected_response=f"{rejected.action} {rejected.shares} shares. Rationale: {rejected.rationale}",
                            chosen_outcome_pct=chosen.outcome_pct,
                            rejected_outcome_pct=rejected.outcome_pct,
                            regime=regime,
                        )
                        pairs.append(pair)
                        
                        if len(pairs) >= max_pairs:
                            break
                
                if len(pairs) >= max_pairs:
                    break
            
            if len(pairs) >= max_pairs:
                break
        
        logger.info(f"Generated {len(pairs)} training pairs from {len(decisions)} decisions")
        return pairs
    
    async def export_to_jsonl(
        self,
        output_path: str,
        min_outcome_diff: float = 5.0,
    ) -> int:
        """
        Export training pairs to JSONL format for DPO training.
        
        Returns number of pairs exported.
        """
        pairs = await self.generate_training_pairs(min_outcome_diff=min_outcome_diff)
        
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w') as f:
            for pair in pairs:
                f.write(json.dumps(pair.to_dpo_format()) + "\n")
        
        logger.info(f"Exported {len(pairs)} pairs to {output_path}")
        return len(pairs)
    
    async def export_all_decisions(
        self,
        output_path: str,
        with_outcomes_only: bool = True,
    ) -> int:
        """Export all decisions to JSON for backup/analysis."""
        await self.initialize()
        
        query = "SELECT * FROM decision_records"
        if with_outcomes_only:
            query += " WHERE outcome_pct IS NOT NULL"
        query += " ORDER BY created_at DESC"
        
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(query)
            rows = await cursor.fetchall()
        
        decisions = [self._row_to_record(row).to_dict() for row in rows]
        
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w') as f:
            json.dump(decisions, f, indent=2, default=str)
        
        logger.info(f"Exported {len(decisions)} decisions to {output_path}")
        return len(decisions)
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get statistics about logged decisions."""
        await self.initialize()
        
        async with aiosqlite.connect(self.db_path) as db:
            # Total decisions
            cursor = await db.execute("SELECT COUNT(*) FROM decision_records")
            total = (await cursor.fetchone())[0]
            
            # With outcomes
            cursor = await db.execute(
                "SELECT COUNT(*) FROM decision_records WHERE outcome_pct IS NOT NULL"
            )
            with_outcomes = (await cursor.fetchone())[0]
            
            # By preference
            cursor = await db.execute("""
                SELECT preference, COUNT(*) 
                FROM decision_records 
                WHERE outcome_pct IS NOT NULL
                GROUP BY preference
            """)
            by_pref = {row[0]: row[1] for row in await cursor.fetchall()}
            
            # Average outcome
            cursor = await db.execute(
                "SELECT AVG(outcome_pct) FROM decision_records WHERE outcome_pct IS NOT NULL"
            )
            avg_outcome = (await cursor.fetchone())[0] or 0.0
            
            # Date range
            cursor = await db.execute(
                "SELECT MIN(created_at), MAX(created_at) FROM decision_records"
            )
            date_range = await cursor.fetchone()
        
        return {
            "total_decisions": total,
            "with_outcomes": with_outcomes,
            "preferred": by_pref.get(1, 0),
            "neutral": by_pref.get(0, 0),
            "dispreferred": by_pref.get(-1, 0),
            "avg_outcome_pct": round(avg_outcome, 2),
            "first_decision": date_range[0],
            "last_decision": date_range[1],
            "ready_for_training": with_outcomes >= 50,  # Minimum for useful training
        }
    
    def _row_to_record(self, row: aiosqlite.Row) -> DecisionRecord:
        """Convert database row to DecisionRecord."""
        return DecisionRecord(
            id=row["id"],
            user_id=row["user_id"],
            context_json=row["context_json"],
            action=row["action"],
            shares=row["shares"],
            rationale=row["rationale"],
            confidence=row["confidence"],
            executed=bool(row["executed"]),
            fill_price=row["fill_price"],
            fill_timestamp=row["fill_timestamp"],
            order_id=row["order_id"],
            outcome_pct=row["outcome_pct"],
            outcome_timestamp=row["outcome_timestamp"],
            lesson_learned=row["lesson_learned"],
            preference=row["preference"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


# Module-level singleton
_pair_logger: Optional[DecisionPairLogger] = None


def get_decision_pair_logger() -> DecisionPairLogger:
    """Get or create the global decision pair logger."""
    global _pair_logger
    if _pair_logger is None:
        _pair_logger = DecisionPairLogger()
    return _pair_logger
