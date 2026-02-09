"""
Historical Sentiment Scorer (REC-209)

Uses Claude Haiku to score historical news headlines.
Same agentic approach as live Sigil pipeline for consistency.

Features:
- Batch processing with progress tracking
- Resume support (checkpointing)
- Cost tracking
- Weekly aggregation
"""

import json
import time
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
from collections import defaultdict
from loguru import logger
import math

from .news_provider import NewsArticle, NewsProvider
from .kaggle_provider import KaggleNewsProvider

# Import from live pipeline for consistency
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from scoring.agentic_sentiment import (
    sanitize_headline,
    SentimentLabel,
)
from scoring.claude_client import get_claude_client, ClaudeClient


# Haiku-specific system prompt (simplified for single-headline scoring)
HISTORICAL_SENTIMENT_PROMPT = """You are a financial sentiment analyst. Score news headlines on a 0-100 scale:

Scoring Guide:
- 0-15: Very bearish (major problems, investigations, significant losses)
- 16-30: Bearish (negative developments, missed expectations)
- 31-44: Slightly bearish (minor concerns, headwinds)
- 45-54: Neutral (routine news, mixed signals)
- 55-69: Slightly bullish (cautious optimism, minor positives)
- 70-84: Bullish (positive news, beat expectations)
- 85-100: Very bullish (major wins, strong growth)

Consider:
- Is this specific to the company or general market noise?
- Magnitude of the impact (earnings beat by 1% vs 20%)
- Source credibility implied by the headline

Respond with ONLY a number 0-100. No explanation."""


@dataclass
class ScoredHeadline:
    """A single scored headline."""
    ticker: str
    headline: str
    published: datetime
    score: float  # 0-100
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "headline": self.headline,
            "published": self.published.isoformat(),
            "score": self.score,
        }


@dataclass
class WeeklySentiment:
    """Aggregated weekly sentiment for a ticker."""
    ticker: str
    week_start: date
    week_end: date
    score: float  # 0-100
    article_count: int
    scores: List[float] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "week_start": self.week_start.isoformat(),
            "week_end": self.week_end.isoformat(),
            "score": round(self.score, 2),
            "article_count": self.article_count,
        }


@dataclass
class ScoringProgress:
    """Tracks scoring progress for resume support."""
    total_headlines: int = 0
    scored_headlines: int = 0
    failed_headlines: int = 0
    total_cost_usd: float = 0.0
    start_time: str = ""
    last_checkpoint: str = ""
    last_processed_index: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> "ScoringProgress":
        return cls(**data)


class HistoricalSentimentScorer:
    """
    Scores historical headlines using Claude Haiku.
    
    Consistent with live Sigil pipeline:
    - Same 0-100 scoring scale
    - Same sentiment label thresholds
    - Headline sanitization
    - Result caching
    """
    
    # Claude Haiku pricing (per 1M tokens)
    HAIKU_INPUT_COST = 0.25
    HAIKU_OUTPUT_COST = 1.25
    
    # Estimated tokens per headline
    AVG_INPUT_TOKENS = 80
    AVG_OUTPUT_TOKENS = 5
    
    def __init__(
        self,
        client: Optional[ClaudeClient] = None,
        output_dir: Optional[Path] = None,
        batch_size: int = 50,
        checkpoint_interval: int = 100,
    ):
        """
        Initialize the scorer.
        
        Args:
            client: ClaudeClient (uses global if None)
            output_dir: Directory for output files
            batch_size: Headlines per batch for progress logging
            checkpoint_interval: Save checkpoint every N headlines
        """
        self.client = client or get_claude_client()
        self.output_dir = output_dir or Path(__file__).parent.parent.parent / "data"
        self.batch_size = batch_size
        self.checkpoint_interval = checkpoint_interval
        
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    @property
    def is_available(self) -> bool:
        """Check if Claude is available."""
        return self.client.is_available
    
    def estimate_cost(self, headline_count: int) -> float:
        """Estimate API cost for scoring headlines."""
        input_tokens = headline_count * self.AVG_INPUT_TOKENS
        output_tokens = headline_count * self.AVG_OUTPUT_TOKENS
        
        input_cost = (input_tokens / 1_000_000) * self.HAIKU_INPUT_COST
        output_cost = (output_tokens / 1_000_000) * self.HAIKU_OUTPUT_COST
        
        return round(input_cost + output_cost, 2)
    
    def score_headline(self, ticker: str, headline: str) -> Optional[float]:
        """
        Score a single headline using Claude Haiku.
        
        Args:
            ticker: Stock symbol
            headline: News headline text
        
        Returns:
            Score 0-100 or None if failed
        """
        # Sanitize headline
        clean_headline = sanitize_headline(headline)
        
        if not clean_headline:
            return None
        
        # Build prompt
        user_message = f"Stock: {ticker}\nHeadline: {clean_headline}"
        
        try:
            # Use a JSON-friendly prompt that returns structured data
            json_prompt = f"""Analyze this headline for stock {ticker} and return sentiment score.

Headline: {clean_headline}

Return JSON: {{"score": <number 0-100>}}"""
            
            response = self.client.analyze(
                system_prompt=HISTORICAL_SENTIMENT_PROMPT,
                user_message=json_prompt,
            )
            
            if response is None:
                return None
            
            # Parse score from JSON response
            if isinstance(response, dict):
                score = response.get("score", response.get("sentiment_score"))
                if score is not None:
                    return min(100, max(0, float(score)))
            
            # Try to extract number from string response
            if isinstance(response, str):
                import re
                match = re.search(r'\b(\d{1,3})\b', response)
                if match:
                    score = int(match.group(1))
                    return min(100, max(0, score))
            
            return None
            
        except Exception as e:
            logger.warning(f"Failed to score headline: {e}")
            return None
    
    def score_headlines_batch(self, items: List[tuple]) -> List[Optional[float]]:
        """
        Score multiple headlines in a single API call.
        
        Args:
            items: List of (ticker, headline) tuples
        
        Returns:
            List of scores (or None for failed items)
        """
        if not items:
            return []
        
        # Sanitize all headlines
        cleaned = []
        for i, (ticker, headline) in enumerate(items):
            clean = sanitize_headline(headline)
            if clean:
                cleaned.append((i, ticker, clean))
        
        if not cleaned:
            return [None] * len(items)
        
        # Build batch prompt
        lines = []
        for idx, (i, ticker, headline) in enumerate(cleaned):
            lines.append(f"{idx+1}. [{ticker}] {headline}")
        
        batch_prompt = f"""Score these {len(cleaned)} headlines. Return JSON array of scores.

Headlines:
{chr(10).join(lines)}

Return: {{"scores": [<score1>, <score2>, ...]}}
Each score is 0-100. Use null for unclear sentiment."""
        
        try:
            response = self.client.analyze(
                system_prompt=HISTORICAL_SENTIMENT_PROMPT,
                user_message=batch_prompt,
            )
            
            if response is None:
                return [None] * len(items)
            
            # Parse scores from response
            scores_list = None
            if isinstance(response, dict):
                scores_list = response.get("scores", [])
            elif isinstance(response, str):
                import json
                import re
                # Try to extract JSON from response
                match = re.search(r'\{[^}]*"scores"\s*:\s*\[([^\]]+)\]', response)
                if match:
                    try:
                        scores_str = match.group(1)
                        scores_list = json.loads(f"[{scores_str}]")
                    except:
                        pass
            
            if not scores_list or len(scores_list) != len(cleaned):
                return [None] * len(items)
            
            # Map back to original indices
            results = [None] * len(items)
            for (orig_idx, _, _), score in zip(cleaned, scores_list):
                if score is not None:
                    try:
                        results[orig_idx] = min(100, max(0, float(score)))
                    except:
                        pass
            
            return results
            
        except Exception as e:
            logger.warning(f"Failed to score batch: {e}")
            return [None] * len(items)
    
    def score_articles(
        self,
        articles: List[NewsArticle],
        resume: bool = True,
        batch_size: int = 20,
    ) -> List[ScoredHeadline]:
        """
        Score a list of articles using batch processing.
        
        Args:
            articles: List of NewsArticle objects
            resume: Whether to resume from checkpoint
            batch_size: Number of headlines per API call (default 20)
        
        Returns:
            List of ScoredHeadline objects
        """
        if not self.is_available:
            raise RuntimeError("Claude API not available")
        
        # Load checkpoint if resuming
        progress = self._load_checkpoint() if resume else None
        start_index = progress.last_processed_index if progress else 0
        
        if progress and start_index > 0:
            logger.info(f"Resuming from index {start_index}")
        
        # Initialize progress
        if not progress:
            progress = ScoringProgress(
                total_headlines=len(articles),
                start_time=datetime.now().isoformat(),
            )
        
        scored = self._load_partial_results() if resume else []
        remaining = articles[start_index:]
        
        logger.info(f"Scoring {len(remaining)} headlines in batches of {batch_size}...")
        
        # Process in batches
        for batch_start in range(0, len(remaining), batch_size):
            batch = remaining[batch_start:batch_start + batch_size]
            batch_items = [(a.ticker, a.headline) for a in batch]
            
            # Score batch
            scores = self.score_headlines_batch(batch_items)
            
            # Process results
            for article, score in zip(batch, scores):
                if score is not None:
                    scored.append(ScoredHeadline(
                        ticker=article.ticker,
                        headline=article.headline,
                        published=article.published,
                        score=score,
                    ))
                    progress.scored_headlines += 1
                    progress.total_cost_usd += 0.00005  # Amortized per headline
                else:
                    progress.failed_headlines += 1
            
            # Update progress
            i = start_index + batch_start + len(batch)
            progress.last_processed_index = i
            
            # Checkpoint every 100 headlines
            if i % 100 < batch_size:
                logger.info(f"Progress: {i}/{len(articles)} ({100*i/len(articles):.1f}%) - Cost: ${progress.total_cost_usd:.2f}")
                self._save_checkpoint(progress, scored)
        
        # Final save
        self._save_checkpoint(progress, scored)
        
        logger.info(f"Completed: {progress.scored_headlines} scored, {progress.failed_headlines} failed")
        return scored
    
    def _score_articles_single(
        self,
        articles: List[NewsArticle],
        resume: bool = True,
    ) -> List[ScoredHeadline]:
        """
        Score articles one at a time (slower fallback).
        """
        if not self.is_available:
            raise RuntimeError("Claude API not available")
        
        progress = self._load_checkpoint() if resume else None
        start_index = progress.last_processed_index if progress else 0
        
        if progress and start_index > 0:
            logger.info(f"Resuming from index {start_index}")
        
        if not progress:
            progress = ScoringProgress(
                total_headlines=len(articles),
                start_time=datetime.now().isoformat(),
            )
        
        scored = self._load_partial_results() if resume else []
        
        logger.info(f"Scoring {len(articles) - start_index} headlines...")
        
        for i, article in enumerate(articles[start_index:], start=start_index):
            score = self.score_headline(article.ticker, article.headline)
            
            if score is not None:
                scored.append(ScoredHeadline(
                    ticker=article.ticker,
                    headline=article.headline,
                    published=article.published,
                    score=score,
                ))
                progress.scored_headlines += 1
            else:
                progress.failed_headlines += 1
            
            # Update progress
            progress.last_processed_index = i + 1
            progress.total_cost_usd = self.estimate_cost(progress.scored_headlines)
            
            # Progress logging
            if (i + 1) % self.batch_size == 0:
                pct = (i + 1) / len(articles) * 100
                logger.info(
                    f"Progress: {i + 1}/{len(articles)} ({pct:.1f}%) - "
                    f"Cost: ${progress.total_cost_usd:.2f}"
                )
            
            # Checkpoint
            if (i + 1) % self.checkpoint_interval == 0:
                self._save_checkpoint(progress, scored)
            
            # Rate limiting (small delay to avoid hitting limits)
            time.sleep(0.1)
        
        # Final save
        progress.last_checkpoint = datetime.now().isoformat()
        self._save_checkpoint(progress, scored)
        
        logger.info(
            f"Scoring complete: {progress.scored_headlines} scored, "
            f"{progress.failed_headlines} failed, "
            f"${progress.total_cost_usd:.2f} estimated cost"
        )
        
        return scored
    
    def aggregate_weekly(
        self,
        scored: List[ScoredHeadline],
    ) -> Dict[str, List[WeeklySentiment]]:
        """
        Aggregate scored headlines into weekly sentiment per ticker.
        
        Uses recency-weighted averaging (newer articles get more weight).
        
        Args:
            scored: List of scored headlines
        
        Returns:
            Dict mapping ticker -> list of WeeklySentiment
        """
        # Group by ticker and week
        weekly_data: Dict[str, Dict[date, List[Tuple[float, datetime]]]] = defaultdict(
            lambda: defaultdict(list)
        )
        
        for s in scored:
            # Get Monday of the week
            week_start = s.published.date() - timedelta(days=s.published.weekday())
            weekly_data[s.ticker][week_start].append((s.score, s.published))
        
        # Calculate weekly averages with recency weighting
        result: Dict[str, List[WeeklySentiment]] = {}
        
        for ticker, weeks in weekly_data.items():
            ticker_weeks = []
            
            for week_start, scores_dates in sorted(weeks.items()):
                week_end = week_start + timedelta(days=6)
                
                # Calculate recency-weighted average
                weighted_sum = 0.0
                weight_total = 0.0
                
                for score, dt in scores_dates:
                    # Weight: newer = higher (within the week)
                    days_old = (week_end - dt.date()).days
                    weight = 1.0 - (days_old / 7) * 0.3
                    weight = max(0.1, weight)
                    
                    weighted_sum += score * weight
                    weight_total += weight
                
                avg_score = weighted_sum / weight_total if weight_total > 0 else 50.0
                
                ticker_weeks.append(WeeklySentiment(
                    ticker=ticker,
                    week_start=week_start,
                    week_end=week_end,
                    score=avg_score,
                    article_count=len(scores_dates),
                    scores=[s for s, _ in scores_dates],
                ))
            
            result[ticker] = ticker_weeks
        
        return result
    
    def save_results(
        self,
        scored: List[ScoredHeadline],
        weekly: Dict[str, List[WeeklySentiment]],
        output_path: Optional[Path] = None,
    ) -> Path:
        """
        Save results to JSON file.
        
        Args:
            scored: Raw scored headlines
            weekly: Weekly aggregated scores
            output_path: Output file path
        
        Returns:
            Path to saved file
        """
        if output_path is None:
            output_path = self.output_dir / "historical_sentiment.json"
        
        data = {
            "generated_at": datetime.now().isoformat(),
            "headline_count": len(scored),
            "ticker_count": len(weekly),
            "weekly_scores": {
                ticker: [w.to_dict() for w in weeks]
                for ticker, weeks in weekly.items()
            },
            "raw_scores": [s.to_dict() for s in scored],
        }
        
        output_path.write_text(json.dumps(data, indent=2))
        logger.info(f"Saved results to {output_path}")
        
        return output_path
    
    def _checkpoint_path(self) -> Path:
        return self.output_dir / "sentiment_scoring_checkpoint.json"
    
    def _partial_results_path(self) -> Path:
        return self.output_dir / "sentiment_scoring_partial.json"
    
    def _save_checkpoint(
        self,
        progress: ScoringProgress,
        scored: List[ScoredHeadline],
    ):
        """Save checkpoint for resume support."""
        # Save progress
        self._checkpoint_path().write_text(
            json.dumps(progress.to_dict(), indent=2)
        )
        
        # Save partial results
        self._partial_results_path().write_text(
            json.dumps([s.to_dict() for s in scored], indent=2)
        )
    
    def _load_checkpoint(self) -> Optional[ScoringProgress]:
        """Load checkpoint if exists."""
        path = self._checkpoint_path()
        if path.exists():
            try:
                data = json.loads(path.read_text())
                return ScoringProgress.from_dict(data)
            except:
                return None
        return None
    
    def _load_partial_results(self) -> List[ScoredHeadline]:
        """Load partial results if exist."""
        path = self._partial_results_path()
        if path.exists():
            try:
                data = json.loads(path.read_text())
                return [
                    ScoredHeadline(
                        ticker=d["ticker"],
                        headline=d["headline"],
                        published=datetime.fromisoformat(d["published"]),
                        score=d["score"],
                    )
                    for d in data
                ]
            except:
                return []
        return []
    
    def clear_checkpoints(self):
        """Clear checkpoint files."""
        for path in [self._checkpoint_path(), self._partial_results_path()]:
            if path.exists():
                path.unlink()
        logger.info("Cleared checkpoints")


def run_historical_scoring(
    start_date: date,
    end_date: date,
    output_path: Optional[Path] = None,
    resume: bool = True,
) -> Path:
    """
    Convenience function to run full historical scoring pipeline.
    
    Args:
        start_date: Start date for articles
        end_date: End date for articles
        output_path: Output file path
        resume: Whether to resume from checkpoint
    
    Returns:
        Path to output file
    """
    from .kaggle_provider import create_kaggle_provider
    
    # Load articles
    logger.info(f"Loading articles for {start_date} to {end_date}...")
    provider = create_kaggle_provider()
    articles = provider.get_articles_for_universe(start_date, end_date)
    
    logger.info(f"Found {len(articles)} articles to score")
    
    # Score
    scorer = HistoricalSentimentScorer()
    
    if not resume:
        scorer.clear_checkpoints()
    
    estimated_cost = scorer.estimate_cost(len(articles))
    logger.info(f"Estimated cost: ${estimated_cost:.2f}")
    
    scored = scorer.score_articles(articles, resume=resume)
    
    # Aggregate
    weekly = scorer.aggregate_weekly(scored)
    
    # Save
    return scorer.save_results(scored, weekly, output_path)


# CLI
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Score historical headlines")
    parser.add_argument("--start", type=str, default="2019-06-01", help="Start date")
    parser.add_argument("--end", type=str, default="2019-11-30", help="End date")
    parser.add_argument("--no-resume", action="store_true", help="Start fresh")
    parser.add_argument("--output", type=str, help="Output file path")
    
    args = parser.parse_args()
    
    logger.add(sys.stderr, level="INFO")
    
    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    output = Path(args.output) if args.output else None
    
    result_path = run_historical_scoring(
        start_date=start,
        end_date=end,
        output_path=output,
        resume=not args.no_resume,
    )
    
    print(f"\n✅ Results saved to: {result_path}")
