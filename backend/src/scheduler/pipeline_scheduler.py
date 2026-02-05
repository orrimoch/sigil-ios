"""
REC-132: Pipeline Scheduler

Automated scoring pipeline that runs weekly with:
- Configurable schedule (default: Sunday 6pm EST)
- Health tracking and metrics
- Retry logic for failures
- Notification triggers after completion
"""

import logging
from datetime import datetime, timezone
from typing import Optional, Dict, List
from pathlib import Path
import json

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

# Scheduler health file
HEALTH_FILE = Path(__file__).parent.parent.parent / "data" / "scheduler_health.json"


class PipelineScheduler:
    """
    Manages automated pipeline runs on a schedule.
    
    Default schedule: Sunday 6pm EST (23:00 UTC)
    """
    
    def __init__(self):
        self.scheduler = BackgroundScheduler(timezone="US/Eastern")
        self._is_running = False
        self._last_run: Optional[Dict] = None
        self._run_history: List[Dict] = []
        self._max_retries = 3
        self._load_health()
    
    def _load_health(self):
        """Load scheduler health from disk."""
        if HEALTH_FILE.exists():
            try:
                with open(HEALTH_FILE) as f:
                    data = json.load(f)
                    self._last_run = data.get("last_run")
                    self._run_history = data.get("history", [])[-50:]  # Keep last 50
            except Exception as e:
                logger.warning(f"Failed to load scheduler health: {e}")
    
    def _save_health(self):
        """Persist scheduler health to disk."""
        try:
            HEALTH_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(HEALTH_FILE, "w") as f:
                json.dump({
                    "last_run": self._last_run,
                    "history": self._run_history[-50:],
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save scheduler health: {e}")
    
    def start(self):
        """Start the scheduler."""
        if self._is_running:
            logger.info("Scheduler already running")
            return
        
        # Add weekly pipeline job: Sunday 6pm EST
        self.scheduler.add_job(
            self._run_pipeline_job,
            trigger=CronTrigger(
                day_of_week="sun",
                hour=18,
                minute=0,
                timezone="US/Eastern"
            ),
            id="weekly_pipeline",
            name="Weekly Scoring Pipeline",
            replace_existing=True,
        )
        
        self.scheduler.start()
        self._is_running = True
        logger.info("Pipeline scheduler started (Sunday 6pm EST)")
    
    def stop(self):
        """Stop the scheduler."""
        if self._is_running:
            self.scheduler.shutdown(wait=False)
            self._is_running = False
            logger.info("Pipeline scheduler stopped")
    
    def _run_pipeline_job(self):
        """Execute the pipeline with retries."""
        run_start = datetime.now(timezone.utc)
        run_result = {
            "started_at": run_start.isoformat(),
            "status": "running",
            "attempt": 1,
        }
        
        logger.info("Starting scheduled pipeline run")
        
        for attempt in range(1, self._max_retries + 1):
            run_result["attempt"] = attempt
            try:
                from data.pipeline import Pipeline
                
                pipeline = Pipeline()
                result = pipeline.run(
                    include_fundamentals=True,
                    include_sentiment=True,
                    include_technical=True,
                    include_macro=True,
                )
                
                run_result.update({
                    "status": "success",
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                    "stocks_processed": result.stocks_processed if hasattr(result, 'stocks_processed') else None,
                    "duration_seconds": (datetime.now(timezone.utc) - run_start).total_seconds(),
                })
                
                logger.info(f"Pipeline completed successfully (attempt {attempt})")
                
                # Trigger post-run notifications
                self._trigger_notifications(result)
                break
                
            except Exception as e:
                logger.error(f"Pipeline failed (attempt {attempt}/{self._max_retries}): {e}")
                run_result["error"] = str(e)
                
                if attempt < self._max_retries:
                    import time
                    time.sleep(30)  # Wait 30s before retry
                else:
                    run_result["status"] = "failed"
                    run_result["completed_at"] = datetime.now(timezone.utc).isoformat()
                    self._alert_failure(run_result)
        
        # Update health
        self._last_run = run_result
        self._run_history.append(run_result)
        self._save_health()
    
    def _trigger_notifications(self, result):
        """Send notifications after successful pipeline run."""
        try:
            # This would integrate with push notification service
            # For now, just log
            logger.info("Pipeline notifications triggered")
            
            # Future: Call notification service to send weekly score updates
            # from notifications.push_service import send_weekly_scores
            # send_weekly_scores(result)
        except Exception as e:
            logger.error(f"Failed to trigger notifications: {e}")
    
    def _alert_failure(self, run_result: Dict):
        """Alert on pipeline failure after max retries."""
        logger.error(f"Pipeline failed after {self._max_retries} attempts: {run_result}")
        
        # Future: Send alert to admins
        # from notifications.alerts import send_admin_alert
        # send_admin_alert("Pipeline Failure", run_result)
    
    def run_now(self) -> Dict:
        """Trigger an immediate pipeline run (manual trigger)."""
        logger.info("Manual pipeline run triggered")
        self._run_pipeline_job()
        return self._last_run or {"status": "unknown"}
    
    def get_status(self) -> Dict:
        """Get scheduler status and health."""
        next_run = None
        if self._is_running:
            job = self.scheduler.get_job("weekly_pipeline")
            if job and job.next_run_time:
                next_run = job.next_run_time.isoformat()
        
        return {
            "is_running": self._is_running,
            "schedule": "Sunday 6pm EST",
            "next_run": next_run,
            "last_run": self._last_run,
            "total_runs": len(self._run_history),
            "success_rate": self._calculate_success_rate(),
        }
    
    def get_history(self, limit: int = 10) -> List[Dict]:
        """Get recent run history."""
        return list(reversed(self._run_history[-limit:]))
    
    def _calculate_success_rate(self) -> float:
        """Calculate success rate from history."""
        if not self._run_history:
            return 0.0
        successes = sum(1 for r in self._run_history if r.get("status") == "success")
        return round(successes / len(self._run_history) * 100, 1)


# Singleton instance
scheduler_instance = PipelineScheduler()
