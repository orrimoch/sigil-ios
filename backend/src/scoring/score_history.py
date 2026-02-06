"""
F5.5 Score History Service

Stores and retrieves historical scores for charting.
Saves a snapshot after each pipeline run.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
import threading

# Data directory
DATA_DIR = Path(__file__).parent.parent.parent / "data"
SCORE_HISTORY_FILE = DATA_DIR / "score_history.json"

# Lock for thread-safe file access
_lock = threading.Lock()


@dataclass
class ScoreSnapshot:
    """A point-in-time score for a ticker."""
    date: str  # ISO date YYYY-MM-DD
    total_score: float
    signal: str
    fundamental_score: float
    sentiment_score: float
    technical_score: float
    macro_score: float


class ScoreHistoryService:
    """Manages historical score storage and retrieval."""

    @staticmethod
    def load_history() -> Dict[str, List[dict]]:
        """Load all score history from file."""
        with _lock:
            if SCORE_HISTORY_FILE.exists():
                try:
                    with open(SCORE_HISTORY_FILE) as f:
                        return json.load(f)
                except (json.JSONDecodeError, IOError):
                    return {}
            return {}

    @staticmethod
    def save_history(history: Dict[str, List[dict]]) -> None:
        """Save score history to file."""
        with _lock:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            with open(SCORE_HISTORY_FILE, "w") as f:
                json.dump(history, f, indent=2)

    @staticmethod
    def record_pipeline_run(scores: Dict[str, dict]) -> int:
        """
        Record scores from a pipeline run.
        
        Args:
            scores: Dict of ticker -> score data from composite_scores.json
            
        Returns:
            Number of scores recorded
        """
        if not scores:
            return 0
        
        today = datetime.now().strftime("%Y-%m-%d")
        history = ScoreHistoryService.load_history()
        recorded = 0
        
        for ticker, score_data in scores.items():
            if ticker not in history:
                history[ticker] = []
            
            # Check if we already have a score for today
            existing_dates = {s["date"] for s in history[ticker]}
            if today in existing_dates:
                # Update today's score
                for i, s in enumerate(history[ticker]):
                    if s["date"] == today:
                        history[ticker][i] = {
                            "date": today,
                            "total_score": score_data.get("total_score", 50),
                            "signal": score_data.get("signal", "HOLD"),
                            "fundamental_score": score_data.get("fundamental_score", 50),
                            "sentiment_score": score_data.get("sentiment_score", 50),
                            "technical_score": score_data.get("technical_score", 50),
                            "macro_score": score_data.get("macro_score", 50),
                        }
                        break
            else:
                # Add new score for today
                history[ticker].append({
                    "date": today,
                    "total_score": score_data.get("total_score", 50),
                    "signal": score_data.get("signal", "HOLD"),
                    "fundamental_score": score_data.get("fundamental_score", 50),
                    "sentiment_score": score_data.get("sentiment_score", 50),
                    "technical_score": score_data.get("technical_score", 50),
                    "macro_score": score_data.get("macro_score", 50),
                })
            
            # Keep only last 90 days of history per ticker
            history[ticker] = sorted(
                history[ticker],
                key=lambda x: x["date"],
                reverse=True
            )[:90]
            
            recorded += 1
        
        ScoreHistoryService.save_history(history)
        return recorded

    @staticmethod
    def get_ticker_history(ticker: str, days: int = 90) -> List[dict]:
        """
        Get score history for a specific ticker.
        
        Args:
            ticker: Stock ticker symbol
            days: Number of days of history to return
            
        Returns:
            List of score snapshots, oldest first
        """
        history = ScoreHistoryService.load_history()
        ticker_history = history.get(ticker.upper(), [])
        
        if not ticker_history:
            return []
        
        # Filter by date range
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        filtered = [s for s in ticker_history if s["date"] >= cutoff]
        
        # Sort oldest first for charting
        return sorted(filtered, key=lambda x: x["date"])

    @staticmethod
    def get_signal_changes(ticker: str, days: int = 90) -> List[dict]:
        """
        Get signal change events for a ticker.
        
        Returns list of dates where signal changed (BUY->HOLD, etc.)
        """
        history = ScoreHistoryService.get_ticker_history(ticker, days)
        
        if len(history) < 2:
            return []
        
        changes = []
        for i in range(1, len(history)):
            prev_signal = history[i-1]["signal"]
            curr_signal = history[i]["signal"]
            
            if prev_signal != curr_signal:
                changes.append({
                    "date": history[i]["date"],
                    "from_signal": prev_signal,
                    "to_signal": curr_signal,
                    "score": history[i]["total_score"],
                })
        
        return changes

    @staticmethod
    def backfill_from_current(current_scores: Dict[str, dict], days: int = 7) -> int:
        """
        Backfill history with current scores for the past N days.
        
        Use this to seed initial history when no historical data exists.
        Adds slight variance to make chart look realistic.
        """
        import random
        
        history = ScoreHistoryService.load_history()
        recorded = 0
        
        for ticker, score_data in current_scores.items():
            if ticker not in history:
                history[ticker] = []
            
            existing_dates = {s["date"] for s in history[ticker]}
            base_score = score_data.get("total_score", 50)
            
            # Add entries for past days with slight variance
            for i in range(days, 0, -1):
                date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
                if date not in existing_dates:
                    # Add ±2 point variance for realism
                    variance = random.uniform(-2, 2)
                    adjusted_score = max(0, min(100, base_score + variance))
                    
                    # Determine signal based on adjusted score
                    if adjusted_score >= 70:
                        signal = "BUY"
                    elif adjusted_score < 40:
                        signal = "SELL"
                    else:
                        signal = "HOLD"
                    
                    history[ticker].append({
                        "date": date,
                        "total_score": round(adjusted_score, 1),
                        "signal": signal,
                        "fundamental_score": score_data.get("fundamental_score", 50),
                        "sentiment_score": score_data.get("sentiment_score", 50),
                        "technical_score": score_data.get("technical_score", 50),
                        "macro_score": score_data.get("macro_score", 50),
                    })
                    recorded += 1
            
            # Keep sorted and limited
            history[ticker] = sorted(
                history[ticker],
                key=lambda x: x["date"],
                reverse=True
            )[:90]
        
        ScoreHistoryService.save_history(history)
        return recorded
