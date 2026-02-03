"""
F9.3 Signal Tracker — detects signal changes between scoring runs.

Compares current signals vs previous snapshot to detect changes like HOLD→BUY.
Stores previous scores in data/previous_scores.json before each pipeline run.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

DATA_DIR = Path(__file__).parent.parent.parent / "data"
PREVIOUS_SCORES_FILE = DATA_DIR / "previous_scores.json"


def save_previous_scores(scores_data: Dict) -> None:
    """
    Snapshot current scores before a new pipeline run.

    Called before scoring runs so we can detect changes after.
    """
    PREVIOUS_SCORES_FILE.parent.mkdir(parents=True, exist_ok=True)

    snapshot = {
        "saved_at": datetime.now().isoformat(),
        "scores": {},
    }

    for ticker, score in scores_data.items():
        snapshot["scores"][ticker] = {
            "ticker": ticker,
            "total_score": score.get("total_score", 0),
            "signal": score.get("signal", "HOLD"),
        }

    with open(PREVIOUS_SCORES_FILE, "w") as f:
        json.dump(snapshot, f, indent=2)


def load_previous_scores() -> Optional[Dict]:
    """Load previous scores snapshot."""
    if not PREVIOUS_SCORES_FILE.exists():
        return None

    with open(PREVIOUS_SCORES_FILE) as f:
        return json.load(f)


def detect_signal_changes(
    current_scores: Dict,
    previous_scores: Optional[Dict] = None,
) -> List[Dict]:
    """
    Compare current scores with previous snapshot to detect signal changes.

    Returns list of changes: [{ticker, old_signal, new_signal, old_score, new_score}]
    """
    if previous_scores is None:
        previous_scores = load_previous_scores()

    if previous_scores is None:
        return []  # No previous data to compare

    prev_data = previous_scores.get("scores", {})
    changes = []

    for ticker, current in current_scores.items():
        current_signal = current.get("signal", "HOLD")
        current_score = current.get("total_score", 0)

        prev = prev_data.get(ticker)
        if prev is None:
            continue  # New stock, no previous data

        prev_signal = prev.get("signal", "HOLD")
        prev_score = prev.get("total_score", 0)

        if current_signal != prev_signal:
            changes.append({
                "ticker": ticker,
                "old_signal": prev_signal,
                "new_signal": current_signal,
                "old_score": prev_score,
                "new_score": current_score,
                "score_change": round(current_score - prev_score, 2),
            })

    # Sort by absolute score change (most significant first)
    changes.sort(key=lambda x: abs(x.get("score_change", 0)), reverse=True)

    return changes


def get_signal_changes_since_last_check(current_scores: Dict) -> List[Dict]:
    """
    Convenience function: detect changes and return formatted list.

    This is what the API endpoint calls.
    """
    return detect_signal_changes(current_scores)
