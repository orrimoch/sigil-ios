"""
F2.5 Composite Score

Combine all scores into final 0-100 score.
Weights: Fundamental 35%, Sentiment 25%, Macro 20%, Technical 20%
Signals: BUY (≥70), HOLD (40-69), SELL (<40)
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from pathlib import Path
import json
from loguru import logger
from dataclasses import dataclass
from enum import Enum

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from scoring.fundamental_score import (
    calculate_fundamental_scores,
    FundamentalScoreResult,
)
from scoring.sentiment_score import (
    calculate_sentiment_scores,
    SentimentScoreResult,
)
from scoring.technical_score import (
    calculate_technical_scores,
    TechnicalScoreResult,
)
from scoring.macro_score import (
    calculate_macro_scores,
    MacroScoreResult,
)
from scoring.relative_scoring import (
    transform_sentiment_scores,
    transform_fundamental_scores,
    transform_technical_scores,
    transform_macro_scores,
)
from data.stock_universe import get_universe


# Relative scoring configuration
RELATIVE_SCORING_ENABLED = True  # Toggle for A/B testing
PRIOR_STRENGTH = 5  # k value for Bayesian shrinkage


# Cache directory
CACHE_DIR = Path(__file__).parent.parent.parent / "data"
COMPOSITE_CACHE = CACHE_DIR / "composite_scores.json"

# Score weights (per PRD)
WEIGHTS = {
    "fundamental": 0.35,
    "sentiment": 0.25,
    "macro": 0.20,
    "technical": 0.20,
}

# REC-263: Crowd Wisdom Score Boost Configuration
CROWD_WISDOM_CONFIG = {
    "enabled": True,
    "boost_threshold": 70,      # Viral score above this gets boost
    "penalty_threshold": 30,    # Viral score below this gets penalty (if stock is in CW data)
    "max_boost": 10,            # Maximum points to add
    "max_penalty": 3,           # Maximum points to subtract
    "boost_curve": "linear",    # linear | sqrt | log
}

# Signal thresholds (default: moderate risk)
SIGNAL_THRESHOLDS = {
    "BUY": 70,
    "HOLD_UPPER": 70,
    "HOLD_LOWER": 40,
    "SELL": 40,
}

