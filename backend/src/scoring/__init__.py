"""
F2.x Scoring System

Modules:
- fundamental_score: F2.1 - Score based on fundamentals (P/E, ROE, margins)
- sentiment_score: F2.2 - Score based on news sentiment
- technical_score: F2.3 - Score based on price momentum/RSI/trends
- macro_score: F2.4 - Score based on macro environment alignment
- composite_score: F2.5 - Combined weighted score with signals
- explainer: F2.6 - Human-readable explanations
"""

from .fundamental_score import (
    calculate_fundamental_scores,
    get_fundamental_score,
    FundamentalScoreResult,
)

from .sentiment_score import (
    calculate_sentiment_scores,
    get_sentiment_score,
    SentimentScoreResult,
)

from .technical_score import (
    calculate_technical_scores,
    get_technical_score,
    TechnicalScoreResult,
)

from .macro_score import (
    calculate_macro_scores,
    get_macro_score,
    MacroScoreResult,
)

from .composite_score import (
    calculate_composite_scores,
    get_top_stocks,
    get_score,
    CompositeScoreResult,
    Signal,
    WEIGHTS,
    save_composite_scores,
    load_composite_scores,
)

from .explainer import (
    explain_score,
    explain_score_simple,
    format_explanation_markdown,
    ScoreExplanation,
)

__all__ = [
    # F2.1
    "calculate_fundamental_scores",
    "get_fundamental_score", 
    "FundamentalScoreResult",
    # F2.2
    "calculate_sentiment_scores",
    "get_sentiment_score",
    "SentimentScoreResult",
    # F2.3
    "calculate_technical_scores",
    "get_technical_score",
    "TechnicalScoreResult",
    # F2.4
    "calculate_macro_scores",
    "get_macro_score",
    "MacroScoreResult",
    # F2.5
    "calculate_composite_scores",
    "get_top_stocks",
    "get_score",
    "CompositeScoreResult",
    "Signal",
    "WEIGHTS",
    # F2.6
    "explain_score",
    "explain_score_simple",
    "format_explanation_markdown",
    "ScoreExplanation",
]
