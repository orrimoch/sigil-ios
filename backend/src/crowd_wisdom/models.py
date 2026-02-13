"""
REC-266: Crowd Wisdom Storage Schema (Reddit-based)

SQLite models for storing Reddit mentions and viral scores.
Replaces the previous insider-based schema.
"""

import aiosqlite
from datetime import date, datetime
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
import json
import logging

logger = logging.getLogger(__name__)

DB_PATH = "data/crowd_wisdom.db"


@dataclass
class RedditMentionModel:
    """Stored Reddit mention of a ticker."""
    id: Optional[int]
    ticker: str
    subreddit: str
    post_id: str
    post_title: str
    post_body: Optional[str]
    upvotes: int
    comments: int
    sentiment: Optional[str]  # bullish/neutral/bearish
    sentiment_score: Optional[float]  # 0.0 to 1.0
    is_comment: bool
    post_created_at: str  # ISO format
    fetched_at: Optional[str] = None


@dataclass
class RedditViralScore:
    """Weekly viral score for a stock based on Reddit activity."""
    id: Optional[int]
    ticker: str
    company_name: str
    week_start: str  # ISO format (Monday of the week)
    
    # Reddit metrics
    mention_count: int
    total_upvotes: int
    total_comments: int
    unique_posts: int
    subreddits: str  # JSON array of subreddits
    
    # Sentiment
    avg_sentiment: Optional[float]  # -1.0 (bearish) to 1.0 (bullish)
    sentiment_label: Optional[str]  # VERY_BULLISH, BULLISH, NEUTRAL, BEARISH, VERY_BEARISH
    
    # Velocity
    trending_velocity: Optional[float]  # mentions_today / mentions_yesterday
    
    # Calculated score
    viral_score: float  # 0-100
    
    # Quality filter data (from fundamentals)
    current_price: Optional[float]
    revenue_ttm: Optional[float]
    eps_latest: Optional[float]
    earnings_growth: Optional[float]
    
    # Filter results
    passes_filters: bool
    filter_reason: Optional[str]  # If fails, why?
    
    # Signal
    signal: str  # VERY_HOT, HOT, TRENDING, NEUTRAL
    
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


async def init_db():
    """Initialize the crowd wisdom database with Reddit-based schema."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Reddit mentions table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS reddit_mentions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                subreddit TEXT NOT NULL,
                post_id TEXT NOT NULL,
                post_title TEXT,
                post_body TEXT,
                upvotes INTEGER DEFAULT 0,
                comments INTEGER DEFAULT 0,
                sentiment TEXT,
                sentiment_score REAL,
                is_comment INTEGER DEFAULT 0,
                post_created_at TEXT,
                fetched_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(ticker, post_id)
            )
        """)
        
        # Indexes for reddit_mentions
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_reddit_mentions_ticker 
            ON reddit_mentions(ticker)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_reddit_mentions_created 
            ON reddit_mentions(post_created_at)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_reddit_mentions_subreddit 
            ON reddit_mentions(subreddit)
        """)
        
        # Reddit viral scores table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS reddit_viral_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                company_name TEXT,
                week_start TEXT NOT NULL,
                mention_count INTEGER DEFAULT 0,
                total_upvotes INTEGER DEFAULT 0,
                total_comments INTEGER DEFAULT 0,
                unique_posts INTEGER DEFAULT 0,
                subreddits TEXT,
                avg_sentiment REAL,
                sentiment_label TEXT,
                trending_velocity REAL,
                viral_score REAL,
                current_price REAL,
                revenue_ttm REAL,
                eps_latest REAL,
                earnings_growth REAL,
                passes_filters INTEGER DEFAULT 0,
                filter_reason TEXT,
                signal TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(ticker, week_start)
            )
        """)
        
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_viral_scores_week 
            ON reddit_viral_scores(week_start)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_viral_scores_score 
            ON reddit_viral_scores(viral_score DESC)
        """)
        
        # Weekly top picks table (Reddit-based)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS reddit_top_picks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                week_start TEXT NOT NULL,
                rank INTEGER NOT NULL,
                ticker TEXT NOT NULL,
                company_name TEXT,
                viral_score REAL,
                mention_count INTEGER,
                total_upvotes INTEGER,
                sentiment_label TEXT,
                trending_velocity REAL,
                current_price REAL,
                signal TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(week_start, rank)
            )
        """)
        
        await db.commit()
        logger.info("Crowd wisdom database initialized (Reddit schema)")


async def save_reddit_mentions(mentions: List[Dict[str, Any]]) -> int:
    """
    Save Reddit mentions to database.
    
    Args:
        mentions: List of mention dicts from RedditFetcher
        
    Returns:
        Number of new mentions saved
    """
    async with aiosqlite.connect(DB_PATH) as db:
        saved = 0
        for m in mentions:
            try:
                await db.execute("""
                    INSERT OR IGNORE INTO reddit_mentions
                    (ticker, subreddit, post_id, post_title, post_body,
                     upvotes, comments, sentiment, sentiment_score,
                     is_comment, post_created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    m['ticker'],
                    m['subreddit'],
                    m['post_id'],
                    m.get('post_title', ''),
                    m.get('post_body', ''),
                    m.get('upvotes', 0),
                    m.get('comments', 0),
                    m.get('sentiment'),
                    m.get('sentiment_score'),
                    1 if m.get('is_comment') else 0,
                    m.get('post_created_at', '')
                ))
                saved += 1
            except Exception as e:
                logger.debug(f"Failed to save mention: {e}")
                continue
        
        await db.commit()
        logger.info(f"Saved {saved} Reddit mentions")
        return saved


async def get_mentions_by_ticker(ticker: str, days: int = 7) -> List[Dict]:
    """Get recent Reddit mentions for a ticker."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT * FROM reddit_mentions
            WHERE ticker = ? 
            AND date(post_created_at) >= date('now', ?)
            ORDER BY post_created_at DESC
        """, (ticker.upper(), f'-{days} days'))
        
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def save_viral_scores(scores: List[Dict[str, Any]], week_start: str) -> int:
    """Save weekly viral scores."""
    async with aiosqlite.connect(DB_PATH) as db:
        saved = 0
        for score in scores:
            try:
                subreddits_json = json.dumps(score.get('subreddits', []))
                await db.execute("""
                    INSERT OR REPLACE INTO reddit_viral_scores
                    (ticker, company_name, week_start, mention_count, total_upvotes,
                     total_comments, unique_posts, subreddits, avg_sentiment,
                     sentiment_label, trending_velocity, viral_score, current_price,
                     revenue_ttm, eps_latest, earnings_growth, passes_filters,
                     filter_reason, signal, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (
                    score['ticker'],
                    score.get('company_name', ''),
                    week_start,
                    score.get('mention_count', 0),
                    score.get('total_upvotes', 0),
                    score.get('total_comments', 0),
                    score.get('unique_posts', 0),
                    subreddits_json,
                    score.get('avg_sentiment'),
                    score.get('sentiment_label', 'NEUTRAL'),
                    score.get('trending_velocity'),
                    score['viral_score'],
                    score.get('current_price'),
                    score.get('revenue_ttm'),
                    score.get('eps_latest'),
                    score.get('earnings_growth'),
                    1 if score.get('passes_filters') else 0,
                    score.get('filter_reason'),
                    score.get('signal', 'NEUTRAL')
                ))
                saved += 1
            except Exception as e:
                logger.error(f"Failed to save viral score for {score.get('ticker')}: {e}")
                continue
        
        await db.commit()
        return saved


async def save_top_picks(picks: List[Dict[str, Any]], week_start: str):
    """Save weekly top 5 picks (Reddit-based)."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Clear existing picks for this week
        await db.execute(
            "DELETE FROM reddit_top_picks WHERE week_start = ?",
            (week_start,)
        )
        
        for i, pick in enumerate(picks[:5], 1):
            await db.execute("""
                INSERT INTO reddit_top_picks
                (week_start, rank, ticker, company_name, viral_score,
                 mention_count, total_upvotes, sentiment_label,
                 trending_velocity, current_price, signal)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                week_start,
                i,
                pick['ticker'],
                pick.get('company_name', ''),
                pick.get('viral_score', 0),
                pick.get('mention_count', 0),
                pick.get('total_upvotes', 0),
                pick.get('sentiment_label', 'NEUTRAL'),
                pick.get('trending_velocity', 1.0),
                pick.get('current_price', 0),
                pick.get('signal', 'TRENDING')
            ))
        
        await db.commit()
        logger.info(f"Saved top {len(picks[:5])} Reddit picks for week {week_start}")


async def get_top_picks(week_start: Optional[str] = None) -> List[Dict]:
    """
    Get top 5 picks for a week.
    If week_start is None, returns the latest week's picks.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        
        if week_start:
            cursor = await db.execute("""
                SELECT * FROM reddit_top_picks
                WHERE week_start = ?
                ORDER BY rank
            """, (week_start,))
        else:
            cursor = await db.execute("""
                SELECT * FROM reddit_top_picks
                WHERE week_start = (SELECT MAX(week_start) FROM reddit_top_picks)
                ORDER BY rank
            """)
        
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_viral_scores(
    week_start: Optional[str] = None,
    passes_filters_only: bool = False,
    limit: int = 50
) -> List[Dict]:
    """Get viral scores for a week."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        
        query = """
            SELECT * FROM reddit_viral_scores
            WHERE week_start = COALESCE(?, (SELECT MAX(week_start) FROM reddit_viral_scores))
        """
        params = [week_start]
        
        if passes_filters_only:
            query += " AND passes_filters = 1"
        
        query += " ORDER BY viral_score DESC LIMIT ?"
        params.append(limit)
        
        cursor = await db.execute(query, params)
        
        rows = await cursor.fetchall()
        scores = []
        for row in rows:
            score = dict(row)
            # Parse subreddits JSON
            if score.get('subreddits'):
                try:
                    score['subreddits'] = json.loads(score['subreddits'])
                except:
                    score['subreddits'] = []
            scores.append(score)
        
        return scores


async def get_viral_score_by_ticker(ticker: str, week_start: Optional[str] = None) -> Optional[Dict]:
    """Get viral score for a specific ticker."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        
        cursor = await db.execute("""
            SELECT * FROM reddit_viral_scores
            WHERE ticker = ?
            AND week_start = COALESCE(?, (SELECT MAX(week_start) FROM reddit_viral_scores))
        """, (ticker.upper(), week_start))
        
        row = await cursor.fetchone()
        if not row:
            return None
        
        score = dict(row)
        if score.get('subreddits'):
            try:
                score['subreddits'] = json.loads(score['subreddits'])
            except:
                score['subreddits'] = []
        
        return score


async def get_trending_tickers(limit: int = 20) -> List[Dict]:
    """Get all trending tickers (unfiltered) sorted by viral score."""
    return await get_viral_scores(passes_filters_only=False, limit=limit)


# Initialize on import
import asyncio
import os

# Ensure data directory exists
os.makedirs(os.path.dirname(DB_PATH) if os.path.dirname(DB_PATH) else "data", exist_ok=True)
