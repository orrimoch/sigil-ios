"""
Pattern Memory (SQLite) - REC-246

Store risk events, stop triggers, and outcomes for pattern analysis.
Foundation for learning from past decisions.

Tables:
- risk_events: All risk-related events (stop triggers, regime changes, etc.)
- trade_outcomes: Trades with their eventual P&L outcome
- patterns: Detected patterns and their success rate
"""

import sqlite3
import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from enum import Enum
import logging

logger = logging.getLogger(__name__)

# Database path
DB_PATH = Path(__file__).parent.parent.parent / "data" / "pattern_memory.db"


class EventType(str, Enum):
    """Types of risk events to track."""
    HARD_STOP_TRIGGERED = "hard_stop_triggered"
    TRAILING_STOP_TRIGGERED = "trailing_stop_triggered"
    REGIME_CHANGE = "regime_change"
    SECTOR_WARNING = "sector_warning"
    VAR_THRESHOLD = "var_threshold"
    POSITION_LIMIT = "position_limit"
    TRADE_OPENED = "trade_opened"
    TRADE_CLOSED = "trade_closed"
    MANUAL_EXIT = "manual_exit"


class OutcomeType(str, Enum):
    """Outcome classification for trades."""
    PROFIT = "profit"
    LOSS = "loss"
    BREAKEVEN = "breakeven"
    STOPPED_OUT = "stopped_out"
    STILL_OPEN = "still_open"


@dataclass
class RiskEvent:
    """A risk event to store in memory."""
    event_type: EventType
    ticker: Optional[str]
    details: Dict[str, Any]
    timestamp: datetime
    user_id: str = "default"
    id: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "event_type": self.event_type.value,
            "ticker": self.ticker,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
            "user_id": self.user_id,
        }


@dataclass
class TradeOutcome:
    """A trade with its outcome for pattern analysis."""
    ticker: str
    entry_date: datetime
    entry_price: float
    exit_date: Optional[datetime]
    exit_price: Optional[float]
    quantity: float
    side: str  # BUY or SELL
    outcome: OutcomeType
    pnl: float
    pnl_pct: float
    exit_reason: Optional[str]  # stop_loss, trailing_stop, manual, target
    regime_at_entry: Optional[str]
    vix_at_entry: Optional[float]
    holding_days: Optional[int]
    user_id: str = "default"
    id: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "ticker": self.ticker,
            "entry_date": self.entry_date.isoformat(),
            "entry_price": self.entry_price,
            "exit_date": self.exit_date.isoformat() if self.exit_date else None,
            "exit_price": self.exit_price,
            "quantity": self.quantity,
            "side": self.side,
            "outcome": self.outcome.value,
            "pnl": round(self.pnl, 2),
            "pnl_pct": round(self.pnl_pct, 4),
            "exit_reason": self.exit_reason,
            "regime_at_entry": self.regime_at_entry,
            "vix_at_entry": self.vix_at_entry,
            "holding_days": self.holding_days,
            "user_id": self.user_id,
        }


class PatternMemory:
    """
    SQLite-backed pattern memory for risk analysis.
    
    Stores events and outcomes, provides pattern queries.
    """
    
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_PATH
        self._init_db()
    
    def _get_conn(self) -> sqlite3.Connection:
        """Get database connection."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_db(self) -> None:
        """Initialize database schema."""
        conn = self._get_conn()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS risk_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    ticker TEXT,
                    details TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    user_id TEXT NOT NULL DEFAULT 'default',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE INDEX IF NOT EXISTS idx_events_type ON risk_events(event_type);
                CREATE INDEX IF NOT EXISTS idx_events_ticker ON risk_events(ticker);
                CREATE INDEX IF NOT EXISTS idx_events_timestamp ON risk_events(timestamp);
                CREATE INDEX IF NOT EXISTS idx_events_user ON risk_events(user_id);
                
                CREATE TABLE IF NOT EXISTS trade_outcomes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    entry_date TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    exit_date TEXT,
                    exit_price REAL,
                    quantity REAL NOT NULL,
                    side TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    pnl REAL NOT NULL DEFAULT 0,
                    pnl_pct REAL NOT NULL DEFAULT 0,
                    exit_reason TEXT,
                    regime_at_entry TEXT,
                    vix_at_entry REAL,
                    holding_days INTEGER,
                    user_id TEXT NOT NULL DEFAULT 'default',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE INDEX IF NOT EXISTS idx_outcomes_ticker ON trade_outcomes(ticker);
                CREATE INDEX IF NOT EXISTS idx_outcomes_outcome ON trade_outcomes(outcome);
                CREATE INDEX IF NOT EXISTS idx_outcomes_user ON trade_outcomes(user_id);
                
                CREATE TABLE IF NOT EXISTS patterns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pattern_type TEXT NOT NULL,
                    description TEXT NOT NULL,
                    conditions TEXT NOT NULL,
                    success_rate REAL,
                    sample_size INTEGER DEFAULT 0,
                    avg_pnl_pct REAL,
                    last_updated TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE INDEX IF NOT EXISTS idx_patterns_type ON patterns(pattern_type);
            """)
            conn.commit()
        finally:
            conn.close()
    
    # ========== Event Storage ==========
    
    def log_event(self, event: RiskEvent) -> int:
        """Store a risk event and return its ID."""
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                """
                INSERT INTO risk_events (event_type, ticker, details, timestamp, user_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    event.event_type.value,
                    event.ticker,
                    json.dumps(event.details),
                    event.timestamp.isoformat(),
                    event.user_id,
                )
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()
    
    def get_events(
        self,
        event_type: Optional[EventType] = None,
        ticker: Optional[str] = None,
        user_id: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[RiskEvent]:
        """Query events with filters."""
        conn = self._get_conn()
        try:
            query = "SELECT * FROM risk_events WHERE 1=1"
            params = []
            
            if event_type:
                query += " AND event_type = ?"
                params.append(event_type.value)
            if ticker:
                query += " AND ticker = ?"
                params.append(ticker)
            if user_id:
                query += " AND user_id = ?"
                params.append(user_id)
            if since:
                query += " AND timestamp >= ?"
                params.append(since.isoformat())
            
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            
            rows = conn.execute(query, params).fetchall()
            
            events = []
            for row in rows:
                events.append(RiskEvent(
                    id=row["id"],
                    event_type=EventType(row["event_type"]),
                    ticker=row["ticker"],
                    details=json.loads(row["details"]),
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    user_id=row["user_id"],
                ))
            return events
        finally:
            conn.close()
    
    # ========== Trade Outcome Storage ==========
    
    def log_trade_outcome(self, outcome: TradeOutcome) -> int:
        """Store a trade outcome and return its ID."""
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                """
                INSERT INTO trade_outcomes (
                    ticker, entry_date, entry_price, exit_date, exit_price,
                    quantity, side, outcome, pnl, pnl_pct, exit_reason,
                    regime_at_entry, vix_at_entry, holding_days, user_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    outcome.ticker,
                    outcome.entry_date.isoformat(),
                    outcome.entry_price,
                    outcome.exit_date.isoformat() if outcome.exit_date else None,
                    outcome.exit_price,
                    outcome.quantity,
                    outcome.side,
                    outcome.outcome.value,
                    outcome.pnl,
                    outcome.pnl_pct,
                    outcome.exit_reason,
                    outcome.regime_at_entry,
                    outcome.vix_at_entry,
                    outcome.holding_days,
                    outcome.user_id,
                )
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()
    
    def get_trade_outcomes(
        self,
        ticker: Optional[str] = None,
        outcome: Optional[OutcomeType] = None,
        exit_reason: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[TradeOutcome]:
        """Query trade outcomes with filters."""
        conn = self._get_conn()
        try:
            query = "SELECT * FROM trade_outcomes WHERE 1=1"
            params = []
            
            if ticker:
                query += " AND ticker = ?"
                params.append(ticker)
            if outcome:
                query += " AND outcome = ?"
                params.append(outcome.value)
            if exit_reason:
                query += " AND exit_reason = ?"
                params.append(exit_reason)
            if user_id:
                query += " AND user_id = ?"
                params.append(user_id)
            
            query += " ORDER BY entry_date DESC LIMIT ?"
            params.append(limit)
            
            rows = conn.execute(query, params).fetchall()
            
            outcomes = []
            for row in rows:
                outcomes.append(TradeOutcome(
                    id=row["id"],
                    ticker=row["ticker"],
                    entry_date=datetime.fromisoformat(row["entry_date"]),
                    entry_price=row["entry_price"],
                    exit_date=datetime.fromisoformat(row["exit_date"]) if row["exit_date"] else None,
                    exit_price=row["exit_price"],
                    quantity=row["quantity"],
                    side=row["side"],
                    outcome=OutcomeType(row["outcome"]),
                    pnl=row["pnl"],
                    pnl_pct=row["pnl_pct"],
                    exit_reason=row["exit_reason"],
                    regime_at_entry=row["regime_at_entry"],
                    vix_at_entry=row["vix_at_entry"],
                    holding_days=row["holding_days"],
                    user_id=row["user_id"],
                ))
            return outcomes
        finally:
            conn.close()
    
    # ========== Pattern Analysis ==========
    
    def analyze_stop_effectiveness(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Analyze how effective stop-losses have been.
        
        Returns stats on trades that were stopped out vs manual exits.
        """
        conn = self._get_conn()
        try:
            base_query = "SELECT * FROM trade_outcomes WHERE outcome != 'still_open'"
            if user_id:
                base_query += f" AND user_id = '{user_id}'"
            
            rows = conn.execute(base_query).fetchall()
            
            if not rows:
                return {"message": "No closed trades to analyze"}
            
            stopped_out = [r for r in rows if r["exit_reason"] in ("stop_loss", "trailing_stop")]
            manual_exits = [r for r in rows if r["exit_reason"] == "manual"]
            
            def calc_stats(trades):
                if not trades:
                    return {"count": 0, "avg_pnl_pct": 0, "win_rate": 0}
                pnls = [t["pnl_pct"] for t in trades]
                wins = sum(1 for p in pnls if p > 0)
                return {
                    "count": len(trades),
                    "avg_pnl_pct": round(sum(pnls) / len(pnls) * 100, 2),
                    "win_rate": round(wins / len(trades) * 100, 1),
                    "total_pnl": round(sum(t["pnl"] for t in trades), 2),
                }
            
            return {
                "stopped_out": calc_stats(stopped_out),
                "manual_exits": calc_stats(manual_exits),
                "all_trades": calc_stats(rows),
                "stop_saved_from_worse": self._estimate_stop_savings(stopped_out),
            }
        finally:
            conn.close()
    
    def _estimate_stop_savings(self, stopped_trades: List[sqlite3.Row]) -> Dict[str, Any]:
        """Estimate how much worse losses could have been without stops."""
        # This would require price data after stop trigger
        # For now, return placeholder
        return {
            "message": "Requires post-stop price data for analysis",
            "trades_analyzed": len(stopped_trades),
        }
    
    def analyze_regime_performance(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Analyze trade performance by market regime at entry.
        """
        conn = self._get_conn()
        try:
            query = """
                SELECT regime_at_entry, 
                       COUNT(*) as count,
                       AVG(pnl_pct) as avg_pnl_pct,
                       SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins
                FROM trade_outcomes 
                WHERE regime_at_entry IS NOT NULL
            """
            if user_id:
                query += f" AND user_id = '{user_id}'"
            query += " GROUP BY regime_at_entry"
            
            rows = conn.execute(query).fetchall()
            
            results = {}
            for row in rows:
                results[row["regime_at_entry"]] = {
                    "count": row["count"],
                    "avg_pnl_pct": round(row["avg_pnl_pct"] * 100, 2) if row["avg_pnl_pct"] else 0,
                    "win_rate": round(row["wins"] / row["count"] * 100, 1) if row["count"] > 0 else 0,
                }
            
            return results
        finally:
            conn.close()
    
    def get_similar_situations(
        self,
        ticker: str,
        regime: str,
        vix_range: Tuple[float, float] = (15, 25),
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Find similar past situations for pattern matching.
        """
        conn = self._get_conn()
        try:
            query = """
                SELECT * FROM trade_outcomes
                WHERE ticker = ?
                  AND regime_at_entry = ?
                  AND vix_at_entry BETWEEN ? AND ?
                  AND outcome != 'still_open'
                ORDER BY entry_date DESC
                LIMIT ?
            """
            rows = conn.execute(query, (ticker, regime, vix_range[0], vix_range[1], limit)).fetchall()
            
            return [
                {
                    "entry_date": row["entry_date"],
                    "outcome": row["outcome"],
                    "pnl_pct": round(row["pnl_pct"] * 100, 2),
                    "holding_days": row["holding_days"],
                    "exit_reason": row["exit_reason"],
                }
                for row in rows
            ]
        finally:
            conn.close()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get overall memory statistics."""
        conn = self._get_conn()
        try:
            events_count = conn.execute("SELECT COUNT(*) FROM risk_events").fetchone()[0]
            trades_count = conn.execute("SELECT COUNT(*) FROM trade_outcomes").fetchone()[0]
            
            return {
                "total_events": events_count,
                "total_trades": trades_count,
                "db_path": str(self.db_path),
            }
        finally:
            conn.close()


# Singleton instance
_memory: Optional[PatternMemory] = None


def get_pattern_memory() -> PatternMemory:
    """Get or create the pattern memory singleton."""
    global _memory
    if _memory is None:
        _memory = PatternMemory()
    return _memory


# ========== Convenience Functions ==========

def log_stop_trigger(
    ticker: str,
    stop_type: str,  # "hard" or "trailing"
    entry_price: float,
    trigger_price: float,
    loss_pct: float,
    user_id: str = "default",
) -> int:
    """Log a stop-loss trigger event."""
    memory = get_pattern_memory()
    event = RiskEvent(
        event_type=EventType.HARD_STOP_TRIGGERED if stop_type == "hard" else EventType.TRAILING_STOP_TRIGGERED,
        ticker=ticker,
        details={
            "entry_price": entry_price,
            "trigger_price": trigger_price,
            "loss_pct": loss_pct,
        },
        timestamp=datetime.now(timezone.utc),
        user_id=user_id,
    )
    return memory.log_event(event)


def log_regime_change(
    old_regime: str,
    new_regime: str,
    vix_value: Optional[float] = None,
    user_id: str = "default",
) -> int:
    """Log a market regime change event."""
    memory = get_pattern_memory()
    event = RiskEvent(
        event_type=EventType.REGIME_CHANGE,
        ticker=None,
        details={
            "old_regime": old_regime,
            "new_regime": new_regime,
            "vix_value": vix_value,
        },
        timestamp=datetime.now(timezone.utc),
        user_id=user_id,
    )
    return memory.log_event(event)


def log_trade_closed(
    ticker: str,
    entry_date: datetime,
    entry_price: float,
    exit_price: float,
    quantity: float,
    side: str,
    exit_reason: str,
    regime_at_entry: Optional[str] = None,
    vix_at_entry: Optional[float] = None,
    user_id: str = "default",
) -> int:
    """Log a closed trade with outcome."""
    memory = get_pattern_memory()
    
    # Calculate P&L
    if side == "BUY":
        pnl = (exit_price - entry_price) * quantity
        pnl_pct = (exit_price - entry_price) / entry_price
    else:
        pnl = (entry_price - exit_price) * quantity
        pnl_pct = (entry_price - exit_price) / entry_price
    
    # Determine outcome
    if exit_reason in ("stop_loss", "trailing_stop"):
        outcome = OutcomeType.STOPPED_OUT
    elif pnl > 0:
        outcome = OutcomeType.PROFIT
    elif pnl < 0:
        outcome = OutcomeType.LOSS
    else:
        outcome = OutcomeType.BREAKEVEN
    
    exit_date = datetime.now(timezone.utc)
    holding_days = (exit_date - entry_date).days
    
    trade = TradeOutcome(
        ticker=ticker,
        entry_date=entry_date,
        entry_price=entry_price,
        exit_date=exit_date,
        exit_price=exit_price,
        quantity=quantity,
        side=side,
        outcome=outcome,
        pnl=pnl,
        pnl_pct=pnl_pct,
        exit_reason=exit_reason,
        regime_at_entry=regime_at_entry,
        vix_at_entry=vix_at_entry,
        holding_days=holding_days,
        user_id=user_id,
    )
    return memory.log_trade_outcome(trade)
