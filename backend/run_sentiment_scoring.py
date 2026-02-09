#!/usr/bin/env python3
"""
Run historical sentiment scoring for Jun-Nov 2019.
"""

import os
import sys
from pathlib import Path
from datetime import date

# Set API key FIRST before any imports
os.environ['ANTHROPIC_API_KEY'] = 'ANTHROPIC_API_KEY_REDACTED'

from loguru import logger

# Setup logging - include DEBUG
logger.remove()
logger.add(
    '/Users/blazeneon/Desktop/Cool_Apps/TradingApp_iOS/backend/data/sentiment_scoring.log', 
    level='DEBUG',  # Changed to DEBUG
    format='{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}',
    rotation="10 MB"
)
logger.add(sys.stderr, level='DEBUG', format='{time:HH:mm:ss} | {level} | {message}')

# Import after env is set
from src.sentiment_historical.kaggle_provider import create_kaggle_provider
from src.sentiment_historical.sentiment_scorer import HistoricalSentimentScorer

def main():
    logger.info('='*60)
    logger.info('STARTING HISTORICAL SENTIMENT SCORING')
    logger.info('='*60)
    logger.info('Period: 2019-06-01 to 2019-11-30')
    
    try:
        # Load articles
        logger.info("Loading articles from Kaggle dataset...")
        provider = create_kaggle_provider(
            project_root=Path('/Users/blazeneon/Desktop/Cool_Apps/TradingApp_iOS')
        )
        
        start_date = date(2019, 6, 1)
        end_date = date(2019, 11, 30)
        articles = provider.get_articles_for_universe(start_date, end_date)
        
        logger.info(f"Found {len(articles):,} articles to score")
        
        # Initialize scorer
        logger.info("Initializing scorer...")
        scorer = HistoricalSentimentScorer()
        logger.info(f"Scorer initialized, available={scorer.is_available}")
        
        if not scorer.is_available:
            logger.error("Scorer not available!")
            return 1
        
        estimated_cost = scorer.estimate_cost(len(articles))
        logger.info(f"Estimated cost: ${estimated_cost:.2f}")
        
        # Score articles - NO RESUME
        logger.info("Starting score_articles (resume=False)...")
        scored = scorer.score_articles(articles, resume=False)
        logger.info(f"Scored {len(scored)} articles")
        
        # Aggregate weekly
        logger.info("Aggregating weekly scores...")
        weekly = scorer.aggregate_weekly(scored)
        
        # Save results
        output_path = scorer.save_results(scored, weekly)
        
        logger.info(f'SUCCESS! Output: {output_path}')
        print(f'\n✅ Scoring complete! Output: {output_path}')
        return 0
        
    except Exception as e:
        logger.error(f'FAILED: {e}')
        import traceback
        logger.error(traceback.format_exc())
        print(f'\n❌ Scoring failed: {e}')
        return 1

if __name__ == '__main__':
    sys.exit(main())
