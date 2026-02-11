"""
REC-252: Insider Transactions Storage Schema

SQLite models for storing insider transactions and crowd wisdom scores.
"""

import aiosqlite
from datetime import date, datetime
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, asdict
import json
import logging

logger = logging.getLogger(__name__)

DB_PATH = "data/crowd_wisdom.db"


@dataclass
class InsiderTransactionModel:
    """Stored insider transaction."""
    id: Optional[int]
    ticker: str
    company_name: str
    insider_name: str
    insider_title: str
    trade_type: str
    price: float
    quantity: int
    shares_owned: int
    ownership_change_pct: float
    value: float
    trade_date: str  # ISO format
    filing_date: str  # ISO format
    created_at: Optional[str] = None


@dataclass
class CrowdWisdomScore:
    """Weekly crowd wisdom score for a stock."""
    id: Optional[int]
    ticker: str
    company_name: str
    sector: str
    current_price: float
    market_cap: Optional[float]
    
    # Insider metrics
    insider_score: float  # 0-100
    insider_buy_count: int
    insider_buy_value: float
    insider_cluster: bool  # 3+ insiders bought
    executive_buys: int  # C-suite buys
    
    # Notable events
    notable_events: str  # JSON array
    discovery_reason: str
    
    # Signal
    signal: str  # STRONG_BUY, BUY, NEUTRAL
    
    week_start: str  # ISO format (Monday of the week)
    created_at: Optional[str] = None


async def init_db():
    """Initialize the crowd wisdom database."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Insider transactions table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS insider_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                company_name TEXT,
                insider_name TEXT NOT NULL,
                insider_title TEXT,
                trade_type TEXT,
                price REAL,
                quantity INTEGER,
                shares_owned INTEGER,
                ownership_change_pct REAL,
                value REAL,
                trade_date TEXT,
                filing_date TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(ticker, insider_name, trade_date, quantity)
            )
        """)
        
        # Create indexes
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_insider_ticker_date 
            ON insider_transactions(ticker, trade_date)
        """)
        
        # Crowd wisdom scores table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS crowd_wisdom_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                company_name TEXT,
                sector TEXT,
                current_price REAL,
                market_cap REAL,
                insider_score REAL,
                insider_buy_count INTEGER,
                insider_buy_value REAL,
                insider_cluster INTEGER,
                executive_buys INTEGER,
                notable_events TEXT,
                discovery_reason TEXT,
                signal TEXT,
                week_start TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(ticker, week_start)
            )
        """)
        
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_scores_week 
            ON crowd_wisdom_scores(week_start)
        """)
        
        # Top 5 weekly picks table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS weekly_top_picks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                week_start TEXT NOT NULL,
                rank INTEGER NOT NULL,
                ticker TEXT NOT NULL,
                company_name TEXT,
                insider_score REAL,
                insider_buy_count INTEGER,
                insider_buy_value REAL,
                notable_events TEXT,
                current_price REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(week_start, rank)
            )
        """)
        
        await db.commit()
        logger.info("Crowd wisdom database initialized")


async def save_transactions(transactions: List[Dict[str, Any]]) -> int:
    """
    Save insider transactions to database.
    
    Args:
        transactions: List of transaction dicts
        
    Returns:
        Number of new transactions saved
    """
    async with aiosqlite.connect(DB_PATH) as db:
        saved = 0
        for txn in transactions:
            try:
                await db.execute("""
                    INSERT OR IGNORE INTO insider_transactions
                    (ticker, company_name, insider_name, insider_title, trade_type,
                     price, quantity, shares_owned, ownership_change_pct, value,
                     trade_date, filing_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    txn['ticker'],
                    txn.get('company_name', ''),
                    txn['insider_name'],
                    txn.get('insider_title', ''),
                    txn.get('trade_type', 'P'),
                    txn.get('price', 0),
                    txn.get('quantity', 0),
                    txn.get('shares_owned', 0),
                    txn.get('ownership_change_pct', 0),
                    txn.get('value', 0),
                    txn.get('trade_date', ''),
                    txn.get('filing_date', '')
                ))
                if db.total_changes > 0:
                    saved += 1
            except Exception as e:
                logger.debug(f"Failed to save transaction: {e}")
                continue
        
        await db.commit()
        logger.info(f"Saved {saved} new insider transactions")
        return saved


async def get_transactions_by_ticker(ticker: str, days: int = 30) -> List[Dict]:
    """Get recent transactions for a ticker."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT * FROM insider_transactions
            WHERE ticker = ? 
            AND date(trade_date) >= date('now', ?)
            ORDER BY trade_date DESC
        """, (ticker, f'-{days} days'))
        
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def save_weekly_scores(scores: List[Dict[str, Any]], week_start: str) -> int:
    """Save weekly crowd wisdom scores."""
    async with aiosqlite.connect(DB_PATH) as db:
        saved = 0
        for score in scores:
            try:
                await db.execute("""
                    INSERT OR REPLACE INTO crowd_wisdom_scores
                    (ticker, company_name, sector, current_price, market_cap,
                     insider_score, insider_buy_count, insider_buy_value, 
                     insider_cluster, executive_buys, notable_events,
                     discovery_reason, signal, week_start)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    score['ticker'],
                    score.get('company_name', ''),
                    score.get('sector', 'Technology'),
                    score.get('current_price', 0),
                    score.get('market_cap'),
                    score['insider_score'],
                    score.get('insider_buy_count', 0),
                    score.get('insider_buy_value', 0),
                    1 if score.get('insider_cluster') else 0,
                    score.get('executive_buys', 0),
                    json.dumps(score.get('notable_events', [])),
                    score.get('discovery_reason', ''),
                    score.get('signal', 'NEUTRAL'),
                    week_start
                ))
                saved += 1
            except Exception as e:
                logger.error(f"Failed to save score for {score.get('ticker')}: {e}")
                continue
        
        await db.commit()
        return saved


async def save_top_picks(picks: List[Dict[str, Any]], week_start: str):
    """Save weekly top 5 picks."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Clear existing picks for this week
        await db.execute(
            "DELETE FROM weekly_top_picks WHERE week_start = ?",
            (week_start,)
        )
        
        for i, pick in enumerate(picks[:5], 1):
            await db.execute("""
                INSERT INTO weekly_top_picks
                (week_start, rank, ticker, company_name, insider_score,
                 insider_buy_count, insider_buy_value, notable_events, current_price)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                week_start,
                i,
                pick['ticker'],
                pick.get('company_name', ''),
                pick.get('insider_score', 0),
                pick.get('insider_buy_count', 0),
                pick.get('insider_buy_value', 0),
                json.dumps(pick.get('notable_events', [])),
                pick.get('current_price', 0)
            ))
        
        await db.commit()
        logger.info(f"Saved top {len(picks[:5])} picks for week {week_start}")


async def get_top_picks(week_start: Optional[str] = None) -> List[Dict]:
    """
    Get top 5 picks for a week.
    If week_start is None, returns the latest week's picks.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        
        if week_start:
            cursor = await db.execute("""
                SELECT * FROM weekly_top_picks
                WHERE week_start = ?
                ORDER BY rank
            """, (week_start,))
        else:
            cursor = await db.execute("""
                SELECT * FROM weekly_top_picks
                WHERE week_start = (SELECT MAX(week_start) FROM weekly_top_picks)
                ORDER BY rank
            """)
        
        rows = await cursor.fetchall()
        picks = []
        for row in rows:
            pick = dict(row)
            # Parse notable_events JSON
            if pick.get('notable_events'):
                try:
                    pick['notable_events'] = json.loads(pick['notable_events'])
                except:
                    pick['notable_events'] = []
            picks.append(pick)
        
        return picks


async def get_all_scores(week_start: Optional[str] = None) -> List[Dict]:
    """Get all crowd wisdom scores for a week."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        
        if week_start:
            cursor = await db.execute("""
                SELECT * FROM crowd_wisdom_scores
                WHERE week_start = ?
                ORDER BY insider_score DESC
            """, (week_start,))
        else:
            cursor = await db.execute("""
                SELECT * FROM crowd_wisdom_scores
                WHERE week_start = (SELECT MAX(week_start) FROM crowd_wisdom_scores)
                ORDER BY insider_score DESC
            """)
        
        rows = await cursor.fetchall()
        scores = []
        for row in rows:
            score = dict(row)
            if score.get('notable_events'):
                try:
                    score['notable_events'] = json.loads(score['notable_events'])
                except:
                    score['notable_events'] = []
            scores.append(score)
        
        return scores


# Initialize on import
import asyncio
import os

# Ensure data directory exists
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
