#!/usr/bin/env python3
"""
REC-262: Weekly Crowd Wisdom Cron Job

Runs Sunday 5pm EST (before main scoring pipeline).
Fetches Reddit trending data, calculates viral scores, stores results.
Target runtime: < 20 min

Usage:
    python scripts/weekly_crowd_wisdom.py

Cron (Sunday 5pm EST = 10pm UTC, adjust for daylight savings):
    0 22 * * 0 cd /path/to/backend && python scripts/weekly_crowd_wisdom.py >> logs/crowd_wisdom.log 2>&1
"""

import sys
import asyncio
from pathlib import Path
from datetime import datetime
import logging

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from loguru import logger
from crowd_wisdom.free_reddit_fetcher import FreeRedditFetcher
from crowd_wisdom.models import init_db, save_crowd_wisdom_scores
from data.stock_universe import get_universe


async def run_weekly_crowd_wisdom():
    """Main weekly crowd wisdom job."""
    start_time = datetime.now()
    logger.info("=" * 60)
    logger.info("WEEKLY CROWD WISDOM JOB STARTED")
    logger.info(f"Time: {start_time.isoformat()}")
    logger.info("=" * 60)
    
    try:
        # Initialize database
        logger.info("\n[1/4] Initializing database...")
        await init_db()
        
        # Fetch Reddit trending data
        logger.info("\n[2/4] Fetching Reddit trending data...")
        fetcher = FreeRedditFetcher()
        trending = await fetcher.fetch_trending()
        logger.info(f"Fetched {len(trending)} trending tickers")
        
        # Get our stock universe for filtering
        logger.info("\n[3/4] Filtering against stock universe...")
        universe = get_universe()
        universe_tickers = {s["ticker"].upper() for s in universe}
        
        # Separate in-universe and discovery candidates
        in_universe = []
        discovery_candidates = []
        
        for ticker_data in trending:
            ticker = ticker_data.ticker.upper()
            if ticker in universe_tickers:
                in_universe.append(ticker_data)
            else:
                discovery_candidates.append(ticker_data)
        
        logger.info(f"In universe: {len(in_universe)} | Discovery candidates: {len(discovery_candidates)}")
        
        # Save scores for in-universe stocks
        logger.info("\n[4/4] Saving crowd wisdom scores...")
        saved_count = await save_crowd_wisdom_scores(in_universe)
        logger.info(f"Saved {saved_count} crowd wisdom scores")
        
        # REC-264: Flag discovery candidates (stocks outside universe)
        if discovery_candidates:
            logger.info("\n--- DISCOVERY CANDIDATES (Outside Universe) ---")
            tech_candidates = [
                t for t in discovery_candidates
                if t.passes_filters and t.viral_score >= 50
            ]
            for candidate in tech_candidates[:10]:  # Top 10 max
                logger.info(
                    f"  {candidate.ticker}: viral={candidate.viral_score:.1f}, "
                    f"mentions={candidate.mention_count}, signal={candidate.signal}"
                )
            
            # Save discovery candidates to file for review
            discovery_file = Path(__file__).parent.parent / "data" / "discovery_candidates.json"
            import json
            discovery_data = {
                "generated_at": datetime.now().isoformat(),
                "count": len(tech_candidates),
                "candidates": [
                    {
                        "ticker": t.ticker,
                        "company_name": t.company_name,
                        "viral_score": t.viral_score,
                        "mention_count": t.mention_count,
                        "total_upvotes": t.total_upvotes,
                        "sentiment_label": t.sentiment_label,
                        "signal": t.signal,
                        "current_price": t.current_price,
                        "revenue_ttm": t.revenue_ttm,
                    }
                    for t in tech_candidates[:10]
                ]
            }
            with open(discovery_file, 'w') as f:
                json.dump(discovery_data, f, indent=2)
            logger.info(f"Saved {len(tech_candidates)} discovery candidates to {discovery_file}")
        
        # Calculate runtime
        end_time = datetime.now()
        runtime = (end_time - start_time).total_seconds()
        
        logger.info("\n" + "=" * 60)
        logger.info("WEEKLY CROWD WISDOM JOB COMPLETE")
        logger.info(f"Runtime: {runtime:.1f} seconds ({runtime/60:.1f} minutes)")
        logger.info(f"Scores saved: {saved_count}")
        logger.info("=" * 60)
        
        return {
            "success": True,
            "runtime_seconds": runtime,
            "scores_saved": saved_count,
            "discovery_candidates": len(discovery_candidates),
        }
        
    except Exception as e:
        logger.error(f"Weekly crowd wisdom job failed: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e),
        }


async def save_crowd_wisdom_scores(trending_data):
    """Save crowd wisdom scores to database."""
    import sqlite3
    from datetime import date
    
    db_path = Path(__file__).parent.parent / "data" / "crowd_wisdom.db"
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Get week start (Monday)
    today = date.today()
    week_start = today - __import__('datetime').timedelta(days=today.weekday())
    week_start_str = week_start.isoformat()
    
    saved = 0
    for data in trending_data:
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO crowd_wisdom_scores (
                    ticker, company_name, week_start,
                    mention_count, total_upvotes, total_comments, unique_posts, subreddits,
                    avg_sentiment, sentiment_label, trending_velocity,
                    viral_score, current_price, revenue_ttm, eps_latest, earnings_growth,
                    passes_filters, filter_reason, signal, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data.ticker,
                data.company_name,
                week_start_str,
                data.mention_count,
                data.total_upvotes,
                data.total_comments,
                data.unique_posts,
                ','.join(data.subreddits) if data.subreddits else '',
                data.avg_sentiment,
                data.sentiment_label,
                data.trending_velocity,
                data.viral_score,
                data.current_price,
                data.revenue_ttm,
                data.eps_latest,
                getattr(data, 'earnings_growth', None),
                data.passes_filters,
                data.filter_reason,
                data.signal,
                datetime.now().isoformat(),
            ))
            saved += 1
        except Exception as e:
            logger.warning(f"Failed to save score for {data.ticker}: {e}")
    
    conn.commit()
    conn.close()
    return saved


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    logger.add(
        Path(__file__).parent.parent / "logs" / "crowd_wisdom_{time}.log",
        rotation="1 week",
        retention="4 weeks",
    )
    
    # Run the job
    result = asyncio.run(run_weekly_crowd_wisdom())
    
    # Exit with appropriate code
    sys.exit(0 if result.get("success") else 1)
