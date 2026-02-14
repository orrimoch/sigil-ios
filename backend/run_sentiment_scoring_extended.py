#!/usr/bin/env python3
"""
Run historical sentiment scoring for Jun 2018 - May 2019 (additional year).
"""

import os
import sys
from pathlib import Path
from datetime import date

# Set API key FIRST before any imports
# API key should be set in environment or .env file
if not os.getenv('ANTHROPIC_API_KEY'):
    print('Warning: ANTHROPIC_API_KEY not set')

from loguru import logger

# Setup logging
logger.remove()
logger.add(
    '/Users/blazeneon/Desktop/Cool_Apps/TradingApp_iOS/backend/data/sentiment_scoring_extended.log', 
    level='INFO',
    format='{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}',
    rotation="10 MB"
)
logger.add(sys.stderr, level='INFO', format='{time:HH:mm:ss} | {level} | {message}')

# Import after env is set
from src.sentiment_historical.kaggle_provider import create_kaggle_provider
from src.sentiment_historical.sentiment_scorer import HistoricalSentimentScorer

def main():
    logger.info('='*60)
    logger.info('STARTING HISTORICAL SENTIMENT SCORING (EXTENDED)')
    logger.info('='*60)
    logger.info('Period: 2018-06-01 to 2019-05-31')
    
    try:
        # Load articles
        logger.info("Loading articles from Kaggle dataset...")
        provider = create_kaggle_provider(
            project_root=Path('/Users/blazeneon/Desktop/Cool_Apps/TradingApp_iOS')
        )
        
        start_date = date(2018, 6, 1)
        end_date = date(2019, 5, 31)
        articles = provider.get_articles_for_universe(start_date, end_date)
        
        logger.info(f"Found {len(articles):,} articles to score")
        
        if not articles:
            logger.error("No articles found!")
            return
        
        # Show sample
        logger.info("Sample articles:")
        for a in articles[:3]:
            logger.info(f"  {a.published.date()} {a.ticker}: {a.headline[:50]}...")
        
        # Initialize scorer
        logger.info("Initializing scorer...")
        scorer = HistoricalSentimentScorer(
            output_dir=Path('/Users/blazeneon/Desktop/Cool_Apps/TradingApp_iOS/backend/data')
        )
        
        # Score all articles
        logger.info("Starting scoring...")
        logger.info("This will take ~30-60 min for 47k headlines (batched 20/call)")
        
        result = scorer.score_articles(
            articles,
            batch_size=20
        )
        
        logger.info('='*60)
        logger.info('SCORING COMPLETE')
        logger.info('='*60)
        logger.info(f"Total scored: {result.get('scored', 0):,}")
        logger.info(f"Failed: {result.get('failed', 0):,}")
        logger.info(f"Cached: {result.get('cached', 0):,}")
        
    except Exception as e:
        logger.exception(f"Scoring failed: {e}")
        raise

if __name__ == '__main__':
    main()
