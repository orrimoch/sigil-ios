"""
REC-266: Reddit Fetcher for Crowd Wisdom

Fetches stock mentions from Reddit using PRAW (Python Reddit API Wrapper).
Extracts tickers from r/wallstreetbets, r/stocks, r/investing.
"""

import praw
import re
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

# Common ticker exclusions (common words that look like tickers)
TICKER_EXCLUSIONS = {
    "A", "I", "DD", "CEO", "CFO", "IPO", "ETF", "USA", "GDP", "CPI", 
    "FBI", "SEC", "NYSE", "NASDAQ", "HODL", "YOLO", "FOMO", "ATH", "ATL",
    "IMO", "FYI", "AMA", "EPS", "PE", "RSI", "MACD", "SMA", "EMA", "EOD",
    "ITM", "OTM", "ATM", "IV", "DTE", "LEAP", "FD", "WSB", "TLDR", "TL",
    "DR", "PT", "TA", "DD", "DD", "RH", "WTF", "LOL", "OMG", "IDK", "IMO",
    "EDIT", "LINK", "POST", "NOW", "GO", "NEW", "TOP", "ALL", "FOR", "BY",
    "THE", "AND", "ARE", "WAS", "HAS", "HAD", "NOT", "BUT", "CAN", "MAY",
    "USD", "EUR", "GBP", "JPY", "CAD", "AUD", "NZD", "CHF", "CNY", "HKD",
    "OC", "PM", "AM", "EST", "PST", "UTC", "GMT", "UK", "US", "EU", "CA"
}

# Valid ticker pattern: 1-5 uppercase letters
TICKER_PATTERN = re.compile(r'\b([A-Z]{1,5})\b')

# Cashtag pattern: $TICKER
CASHTAG_PATTERN = re.compile(r'\$([A-Z]{1,5})\b')


@dataclass
class RedditMention:
    """A single Reddit post/comment mentioning a stock."""
    ticker: str
    subreddit: str
    post_id: str
    post_title: str
    post_body: Optional[str]
    upvotes: int
    comments: int
    post_created_at: datetime
    is_comment: bool = False
    parent_post_id: Optional[str] = None


class RedditFetcher:
    """
    Fetches stock mentions from Reddit subreddits.
    
    Usage:
        fetcher = RedditFetcher()
        mentions = fetcher.fetch_mentions(days_back=7)
    """
    
    DEFAULT_SUBREDDITS = ["wallstreetbets", "stocks", "investing"]
    
    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        user_agent: Optional[str] = None,
        subreddits: Optional[List[str]] = None
    ):
        """
        Initialize Reddit fetcher with PRAW credentials.
        
        Args:
            client_id: Reddit API client ID (env: REDDIT_CLIENT_ID)
            client_secret: Reddit API client secret (env: REDDIT_CLIENT_SECRET)
            user_agent: User agent string (env: REDDIT_USER_AGENT)
            subreddits: List of subreddits to fetch from
        """
        self.client_id = client_id or os.getenv("REDDIT_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("REDDIT_CLIENT_SECRET")
        self.user_agent = user_agent or os.getenv("REDDIT_USER_AGENT", "Sigil/1.0")
        self.subreddits = subreddits or self.DEFAULT_SUBREDDITS
        
        self._reddit = None
        self._valid_tickers: Optional[Set[str]] = None
    
    @property
    def reddit(self) -> praw.Reddit:
        """Lazy-load Reddit client."""
        if self._reddit is None:
            if not self.client_id or not self.client_secret:
                raise ValueError(
                    "Reddit credentials not configured. "
                    "Set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET env vars."
                )
            
            self._reddit = praw.Reddit(
                client_id=self.client_id,
                client_secret=self.client_secret,
                user_agent=self.user_agent
            )
            logger.info(f"Initialized Reddit client with user_agent: {self.user_agent}")
        
        return self._reddit
    
    def set_valid_tickers(self, tickers: Set[str]):
        """Set the list of valid tickers to filter against."""
        self._valid_tickers = {t.upper() for t in tickers}
        logger.info(f"Set {len(self._valid_tickers)} valid tickers for filtering")
    
    def extract_tickers(self, text: str) -> Set[str]:
        """
        Extract stock tickers from text.
        
        Looks for:
        1. Cashtags: $AAPL, $MSFT
        2. Uppercase words that match ticker pattern
        
        Filters out common words and invalid tickers.
        """
        if not text:
            return set()
        
        tickers = set()
        
        # Extract cashtags first (higher confidence)
        cashtags = CASHTAG_PATTERN.findall(text)
        tickers.update(cashtags)
        
        # Extract potential tickers from uppercase words
        matches = TICKER_PATTERN.findall(text)
        for match in matches:
            if match not in TICKER_EXCLUSIONS and len(match) >= 2:
                tickers.add(match)
        
        # Filter to valid tickers if we have a list
        if self._valid_tickers:
            tickers = tickers & self._valid_tickers
        
        return tickers
    
    def fetch_mentions(
        self,
        days_back: int = 7,
        limit_per_sub: int = 500,
        include_comments: bool = True,
        comment_depth: int = 50
    ) -> List[RedditMention]:
        """
        Fetch stock mentions from configured subreddits.
        
        Args:
            days_back: Number of days to look back
            limit_per_sub: Maximum posts per subreddit
            include_comments: Whether to also scan top comments
            comment_depth: Number of top comments to scan per post
            
        Returns:
            List of RedditMention objects
        """
        cutoff_time = datetime.utcnow() - timedelta(days=days_back)
        cutoff_timestamp = cutoff_time.timestamp()
        
        all_mentions: List[RedditMention] = []
        
        for subreddit_name in self.subreddits:
            try:
                logger.info(f"Fetching from r/{subreddit_name}...")
                subreddit = self.reddit.subreddit(subreddit_name)
                
                # Fetch hot and new posts
                for post in subreddit.hot(limit=limit_per_sub):
                    if post.created_utc < cutoff_timestamp:
                        continue
                    
                    mentions = self._process_post(post, subreddit_name)
                    all_mentions.extend(mentions)
                    
                    # Process top comments
                    if include_comments:
                        comment_mentions = self._process_comments(
                            post, subreddit_name, comment_depth
                        )
                        all_mentions.extend(comment_mentions)
                
                # Also fetch new posts (might catch different content)
                for post in subreddit.new(limit=limit_per_sub // 2):
                    if post.created_utc < cutoff_timestamp:
                        continue
                    
                    # Skip if we already processed this post in hot
                    if any(m.post_id == post.id for m in all_mentions):
                        continue
                    
                    mentions = self._process_post(post, subreddit_name)
                    all_mentions.extend(mentions)
                
                logger.info(
                    f"Found {len([m for m in all_mentions if m.subreddit == subreddit_name])} "
                    f"mentions from r/{subreddit_name}"
                )
                
            except Exception as e:
                logger.error(f"Error fetching from r/{subreddit_name}: {e}")
                continue
        
        logger.info(f"Total mentions fetched: {len(all_mentions)}")
        return all_mentions
    
    def _process_post(self, post, subreddit_name: str) -> List[RedditMention]:
        """Extract ticker mentions from a single post."""
        mentions = []
        
        # Combine title and body for ticker extraction
        full_text = f"{post.title} {post.selftext or ''}"
        tickers = self.extract_tickers(full_text)
        
        for ticker in tickers:
            mentions.append(RedditMention(
                ticker=ticker,
                subreddit=subreddit_name,
                post_id=post.id,
                post_title=post.title[:500],  # Truncate long titles
                post_body=(post.selftext or "")[:2000],  # Truncate long bodies
                upvotes=post.score,
                comments=post.num_comments,
                post_created_at=datetime.utcfromtimestamp(post.created_utc),
                is_comment=False
            ))
        
        return mentions
    
    def _process_comments(
        self, post, subreddit_name: str, limit: int
    ) -> List[RedditMention]:
        """Extract ticker mentions from top comments."""
        mentions = []
        
        try:
            post.comments.replace_more(limit=0)  # Don't expand "more comments"
            top_comments = list(post.comments)[:limit]
            
            for comment in top_comments:
                if not hasattr(comment, 'body'):
                    continue
                
                tickers = self.extract_tickers(comment.body)
                
                for ticker in tickers:
                    mentions.append(RedditMention(
                        ticker=ticker,
                        subreddit=subreddit_name,
                        post_id=comment.id,
                        post_title=post.title[:500],
                        post_body=comment.body[:2000],
                        upvotes=comment.score,
                        comments=0,  # Comments don't have comment counts
                        post_created_at=datetime.utcfromtimestamp(comment.created_utc),
                        is_comment=True,
                        parent_post_id=post.id
                    ))
        except Exception as e:
            logger.debug(f"Error processing comments for post {post.id}: {e}")
        
        return mentions
    
    def aggregate_by_ticker(
        self, mentions: List[RedditMention]
    ) -> Dict[str, Dict]:
        """
        Aggregate mentions by ticker.
        
        Returns:
            Dict mapping ticker to aggregated data:
            {
                "AAPL": {
                    "ticker": "AAPL",
                    "mention_count": 50,
                    "total_upvotes": 1500,
                    "total_comments": 300,
                    "subreddits": ["wallstreetbets", "stocks"],
                    "posts": [...]  # List of unique posts
                }
            }
        """
        aggregated: Dict[str, Dict] = {}
        
        for mention in mentions:
            ticker = mention.ticker
            
            if ticker not in aggregated:
                aggregated[ticker] = {
                    "ticker": ticker,
                    "mention_count": 0,
                    "total_upvotes": 0,
                    "total_comments": 0,
                    "subreddits": set(),
                    "post_ids": set(),
                    "earliest_mention": mention.post_created_at,
                    "latest_mention": mention.post_created_at
                }
            
            agg = aggregated[ticker]
            agg["mention_count"] += 1
            agg["subreddits"].add(mention.subreddit)
            
            # Only count upvotes/comments once per unique post
            if mention.post_id not in agg["post_ids"]:
                agg["total_upvotes"] += mention.upvotes
                agg["total_comments"] += mention.comments
                agg["post_ids"].add(mention.post_id)
            
            # Track time range
            if mention.post_created_at < agg["earliest_mention"]:
                agg["earliest_mention"] = mention.post_created_at
            if mention.post_created_at > agg["latest_mention"]:
                agg["latest_mention"] = mention.post_created_at
        
        # Convert sets to lists for JSON serialization
        for ticker, data in aggregated.items():
            data["subreddits"] = list(data["subreddits"])
            data["unique_posts"] = len(data["post_ids"])
            del data["post_ids"]  # Remove set (not JSON serializable)
        
        return aggregated


# Convenience function for quick fetching
def fetch_reddit_mentions(
    days_back: int = 7,
    subreddits: Optional[List[str]] = None,
    valid_tickers: Optional[Set[str]] = None
) -> Dict[str, Dict]:
    """
    Convenience function to fetch and aggregate Reddit mentions.
    
    Args:
        days_back: Days to look back
        subreddits: List of subreddits (default: wsb, stocks, investing)
        valid_tickers: Set of valid ticker symbols to filter against
        
    Returns:
        Dict of aggregated ticker data
    """
    fetcher = RedditFetcher(subreddits=subreddits)
    
    if valid_tickers:
        fetcher.set_valid_tickers(valid_tickers)
    
    mentions = fetcher.fetch_mentions(days_back=days_back)
    return fetcher.aggregate_by_ticker(mentions)
