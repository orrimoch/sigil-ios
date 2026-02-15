"""
F1.6 Weekly Pipeline Orchestration

Runs full data pipeline every Sunday 6pm EST:
- Fetches all data sources
- Calculates scores for all stocks
- Completes in < 30 minutes
- Alerts on failure
- Retry logic for transient failures
"""

import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import json
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from loguru import logger

# Import fetchers
from .stock_universe import get_universe, build_universe, save_universe
from .price_fetcher import fetch_all_prices, save_prices
from .fundamental_fetcher import fetch_all_fundamentals, save_fundamentals
from .news_fetcher import fetch_all_news, save_news
from .macro_fetcher import fetch_all_macro_data, save_macro_data

# Import scoring
from src.scoring.composite_score import calculate_composite_scores, save_composite_scores


# Directories
DATA_DIR = Path(__file__).parent.parent.parent / "data"
LOGS_DIR = DATA_DIR / "pipeline_logs"


class StepStatus(str, Enum):
    """Pipeline step status."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StepResult:
    """Result of a pipeline step."""
    name: str
    status: StepStatus
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: float = 0
    records_processed: int = 0
    error: Optional[str] = None
    retries: int = 0


@dataclass
class PipelineResult:
    """Result of full pipeline run."""
    run_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: str = "running"
    steps: List[StepResult] = field(default_factory=list)
    total_duration_seconds: float = 0
    errors: List[str] = field(default_factory=list)
    
    @property
    def success(self) -> bool:
        """Returns True if pipeline completed successfully."""
        return self.status == "success"
    
    def to_dict(self) -> Dict:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "status": self.status,
            "total_duration_seconds": self.total_duration_seconds,
            "steps": [
                {
                    "name": s.name,
                    "status": s.status.value,
                    "duration_seconds": s.duration_seconds,
                    "records_processed": s.records_processed,
                    "error": s.error,
                    "retries": s.retries,
                }
                for s in self.steps
            ]
        }


class Pipeline:
    """
    Data pipeline orchestrator.
    
    Runs all data fetching and processing steps with:
    - Configurable retry logic
    - Progress tracking
    - Error handling
    - Logging
    """
    
    def __init__(
        self,
        max_retries: int = 3,
        retry_delay: float = 30.0,
        timeout_minutes: int = 30,
        alert_callback: Optional[Callable[[str, str], None]] = None
    ):
        """
        Initialize pipeline.
        
        Args:
            max_retries: Max retries per step
            retry_delay: Seconds between retries
            timeout_minutes: Total pipeline timeout
            alert_callback: Function to call on alerts (title, message)
        """
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.timeout_minutes = timeout_minutes
        self.alert_callback = alert_callback
        self.result: Optional[PipelineResult] = None
    
    def _run_step(
        self,
        name: str,
        func: Callable,
        *args,
        **kwargs
    ) -> StepResult:
        """
        Run a single pipeline step with retries.
        """
        step = StepResult(name=name, status=StepStatus.RUNNING)
        step.started_at = datetime.now()
        
        for attempt in range(self.max_retries):
            try:
                logger.info(f"[{name}] Starting (attempt {attempt + 1}/{self.max_retries})...")
                
                result = func(*args, **kwargs)
                
                # Determine record count based on result type
                if isinstance(result, dict):
                    step.records_processed = len(result)
                elif isinstance(result, list):
                    step.records_processed = len(result)
                elif result is not None:
                    step.records_processed = 1
                
                step.status = StepStatus.SUCCESS
                step.completed_at = datetime.now()
                step.duration_seconds = (step.completed_at - step.started_at).total_seconds()
                step.retries = attempt
                
                logger.info(f"[{name}] ✓ Completed in {step.duration_seconds:.1f}s ({step.records_processed} records)")
                return step
                
            except Exception as e:
                logger.error(f"[{name}] Attempt {attempt + 1} failed: {e}")
                step.error = str(e)
                step.retries = attempt + 1
                
                if attempt < self.max_retries - 1:
                    logger.info(f"[{name}] Retrying in {self.retry_delay}s...")
                    time.sleep(self.retry_delay)
        
        # All retries exhausted
        step.status = StepStatus.FAILED
        step.completed_at = datetime.now()
        step.duration_seconds = (step.completed_at - step.started_at).total_seconds()
        
        logger.error(f"[{name}] ✗ Failed after {self.max_retries} attempts")
        return step
    
    def run(
        self,
        skip_universe: bool = False,
        skip_prices: bool = False,
        skip_fundamentals: bool = False,
        skip_news: bool = False,
        skip_macro: bool = False,
        tickers: Optional[List[str]] = None
    ) -> PipelineResult:
        """
        Run the full data pipeline.
        
        Args:
            skip_*: Skip specific steps
            tickers: Specific tickers to process (None = full universe)
        
        Returns:
            PipelineResult with status of all steps
        """
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.result = PipelineResult(
            run_id=run_id,
            started_at=datetime.now()
        )
        
        logger.info("=" * 60)
        logger.info(f"PIPELINE RUN: {run_id}")
        logger.info("=" * 60)
        
        try:
            # Step 1: Stock Universe
            if not skip_universe:
                step = self._run_step(
                    "stock_universe",
                    self._fetch_universe
                )
                self.result.steps.append(step)
                
                if step.status == StepStatus.FAILED:
                    raise Exception(f"Universe fetch failed: {step.error}")
            
            # Get tickers for remaining steps
            if tickers is None:
                universe = get_universe()
                tickers = [s["ticker"] for s in universe]
            
            # Step 2: Price Data
            if not skip_prices:
                step = self._run_step(
                    "price_data",
                    self._fetch_prices,
                    tickers
                )
                self.result.steps.append(step)
            
            # Step 3: Fundamental Data
            if not skip_fundamentals:
                step = self._run_step(
                    "fundamental_data",
                    self._fetch_fundamentals,
                    tickers
                )
                self.result.steps.append(step)
            
            # Step 4: News Data
            if not skip_news:
                step = self._run_step(
                    "news_data",
                    self._fetch_news
                )
                self.result.steps.append(step)
            
            # Step 5: Macro Data
            if not skip_macro:
                step = self._run_step(
                    "macro_data",
                    self._fetch_macro
                )
                self.result.steps.append(step)
            
            # Step 6: Calculate Composite Scores
            step = self._run_step(
                "scoring",
                self._calculate_scores,
                tickers
            )
            self.result.steps.append(step)
            
            # Determine overall status
            failed_steps = [s for s in self.result.steps if s.status == StepStatus.FAILED]
            
            if failed_steps:
                self.result.status = "partial_failure"
                self._alert(
                    "Pipeline Partial Failure",
                    f"Run {run_id}: {len(failed_steps)} steps failed"
                )
            else:
                self.result.status = "success"
            
        except Exception as e:
            logger.error(f"Pipeline error: {e}")
            logger.error(traceback.format_exc())
            self.result.status = "failed"
            self._alert(
                "Pipeline Failed",
                f"Run {run_id}: {str(e)}"
            )
        
        # Finalize
        self.result.completed_at = datetime.now()
        self.result.total_duration_seconds = (
            self.result.completed_at - self.result.started_at
        ).total_seconds()
        
        # Save run log
        self._save_run_log()
        
        logger.info("=" * 60)
        logger.info(f"PIPELINE COMPLETE: {self.result.status}")
        logger.info(f"Duration: {self.result.total_duration_seconds:.1f}s")
        logger.info("=" * 60)
        
        return self.result
    
    def _fetch_universe(self) -> Dict:
        """Fetch and save stock universe."""
        universe = build_universe()
        save_universe(universe)
        return universe
    
    def _fetch_prices(self, tickers: List[str]) -> Dict:
        """Fetch and save price data with rate-limit-safe batching."""
        prices = fetch_all_prices(
            tickers, period="5y",
            max_workers=3, delay=0.5,
            batch_size=25, batch_pause=5.0
        )
        save_prices(prices)
        return prices
    
    def _fetch_fundamentals(self, tickers: List[str]) -> Dict:
        """Fetch and save fundamental data with rate-limit-safe batching."""
        fundamentals = fetch_all_fundamentals(
            tickers,
            max_workers=2, delay=1.0,
            batch_size=20, batch_pause=10.0
        )
        save_fundamentals(fundamentals)
        return fundamentals
    
    def _fetch_news(self) -> List:
        """Fetch and save news."""
        news = fetch_all_news(hours=168)  # 7 days
        save_news(news)
        return news
    
    def _fetch_macro(self) -> Dict:
        """Fetch and save macro data."""
        macro = fetch_all_macro_data(periods=365)
        save_macro_data(macro)
        return macro
    
    def _calculate_scores(self, tickers: List[str]) -> Dict:
        """Calculate and save composite scores for all tickers."""
        logger.info(f"Calculating composite scores for {len(tickers)} tickers...")
        scores = calculate_composite_scores(tickers=tickers)
        save_composite_scores(scores)
        logger.info(f"Saved {len(scores)} composite scores")
        return {"count": len(scores)}
    
    def _alert(self, title: str, message: str):
        """Send alert notification."""
        logger.warning(f"ALERT: {title} - {message}")
        
        if self.alert_callback:
            try:
                self.alert_callback(title, message)
            except Exception as e:
                logger.error(f"Alert callback failed: {e}")
    
    def _save_run_log(self):
        """Save pipeline run log to JSON."""
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        
        log_path = LOGS_DIR / f"run_{self.result.run_id}.json"
        
        with open(log_path, 'w') as f:
            json.dump(self.result.to_dict(), f, indent=2)
        
        logger.info(f"Run log saved to {log_path}")


def run_pipeline(**kwargs) -> PipelineResult:
    """
    Convenience function to run the pipeline.
    
    Example:
        result = run_pipeline(skip_prices=True)
    """
    pipeline = Pipeline()
    return pipeline.run(**kwargs)


def run_quick_update(tickers: List[str] = None) -> PipelineResult:
    """
    Run a quick update (prices and news only).
    
    Good for daily updates between full runs.
    """
    pipeline = Pipeline(max_retries=2, retry_delay=10)
    return pipeline.run(
        skip_universe=True,
        skip_fundamentals=True,
        skip_macro=True,
        tickers=tickers
    )


def get_latest_run() -> Optional[Dict]:
    """Get the most recent pipeline run result."""
    if not LOGS_DIR.exists():
        return None
    
    logs = sorted(LOGS_DIR.glob("run_*.json"), reverse=True)
    
    if not logs:
        return None
    
    with open(logs[0], 'r') as f:
        return json.load(f)


def get_run_history(limit: int = 10) -> List[Dict]:
    """Get recent pipeline run history."""
    if not LOGS_DIR.exists():
        return []
    
    logs = sorted(LOGS_DIR.glob("run_*.json"), reverse=True)[:limit]
    
    history = []
    for log_path in logs:
        with open(log_path, 'r') as f:
            history.append(json.load(f))
    
    return history


# CLI for manual runs
if __name__ == "__main__":
    import sys
    import argparse
    
    logger.add(sys.stderr, level="INFO")
    
    parser = argparse.ArgumentParser(description="Run the Sigil data pipeline")
    parser.add_argument("--test", action="store_true", help="Test mode: only 3 stocks (AAPL, MSFT, GOOGL)")
    parser.add_argument("--full", action="store_true", help="Full pipeline including universe rebuild")
    parser.add_argument("--skip-universe", action="store_true", help="Skip universe fetch (use existing)")
    parser.add_argument("--skip-prices", action="store_true", help="Skip price fetching")
    parser.add_argument("--skip-fundamentals", action="store_true", help="Skip fundamental fetching")
    parser.add_argument("--skip-news", action="store_true", help="Skip news fetching")
    parser.add_argument("--skip-macro", action="store_true", help="Skip macro data fetching")
    parser.add_argument("--scores-only", action="store_true", help="Only recalculate scores (skip all data fetching)")
    args = parser.parse_args()
    
    print("\n=== Sigil Data Pipeline ===\n")
    
    # Determine tickers
    if args.test:
        tickers = ["AAPL", "MSFT", "GOOGL"]
        print(f"TEST MODE: Running for {len(tickers)} stocks")
        skip_universe = True
    else:
        tickers = None  # Full universe
        print("FULL MODE: Running for entire stock universe")
        skip_universe = args.skip_universe
    
    # Scores-only mode
    if args.scores_only:
        print("SCORES-ONLY: Skipping all data fetching, recalculating scores")
        universe = get_universe()
        tickers = [s["ticker"] for s in universe]
        print(f"Universe has {len(tickers)} stocks")
        
        pipeline = Pipeline(max_retries=2, retry_delay=5)
        result = pipeline.run(
            skip_universe=True,
            skip_prices=True,
            skip_fundamentals=True,
            skip_news=True,
            skip_macro=True,
            tickers=tickers
        )
    else:
        pipeline = Pipeline(max_retries=2, retry_delay=5)
        result = pipeline.run(
            skip_universe=skip_universe,
            skip_prices=args.skip_prices,
            skip_fundamentals=args.skip_fundamentals,
            skip_news=args.skip_news,
            skip_macro=args.skip_macro,
            tickers=tickers
        )
    
    print(f"\nResult: {result.status}")
    print(f"Duration: {result.total_duration_seconds:.1f}s")
    print("\nSteps:")
    for step in result.steps:
        status_icon = "✓" if step.status == StepStatus.SUCCESS else "✗"
        print(f"  {status_icon} {step.name}: {step.status.value} ({step.records_processed} records)")
    
    print("\n✅ Pipeline complete!")
