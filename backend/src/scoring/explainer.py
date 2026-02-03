"""
F2.6 Score Explainability

Generate human-readable explanation for each score.
Component breakdown, plain English summary, week-over-week drivers.
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
from loguru import logger

from scoring.composite_score import CompositeScoreResult, Signal, WEIGHTS


@dataclass
class ScoreExplanation:
    """Human-readable score explanation."""
    ticker: str
    summary: str  # One-line summary
    signal_reason: str  # Why this signal
    component_breakdown: List[str]  # Bullet points for each component
    strengths: List[str]
    weaknesses: List[str]
    change_drivers: Optional[List[str]]  # Week-over-week drivers


def _get_strength_level(score: float) -> str:
    """Convert score to strength descriptor."""
    if score >= 80:
        return "very strong"
    elif score >= 65:
        return "strong"
    elif score >= 50:
        return "moderate"
    elif score >= 35:
        return "weak"
    else:
        return "very weak"


def _get_component_summary(name: str, score: float, weight: float, details: Dict) -> str:
    """Generate summary for a component."""
    level = _get_strength_level(score)
    weight_pct = int(weight * 100)
    
    if name == "fundamental":
        # Pull specific metrics
        pe = details.get("pe_ratio")
        roe = details.get("roe")
        
        metrics = []
        if pe:
            metrics.append(f"P/E {pe:.1f}")
        if roe:
            metrics.append(f"ROE {roe*100:.1f}%")
        
        metric_str = f" ({', '.join(metrics)})" if metrics else ""
        return f"**Fundamentals** ({weight_pct}%): {level.capitalize()} at {score:.0f}/100{metric_str}"
    
    elif name == "sentiment":
        article_count = details.get("top_articles", [])
        count = len(article_count) if isinstance(article_count, list) else 0
        return f"**Sentiment** ({weight_pct}%): {level.capitalize()} at {score:.0f}/100 ({count} articles analyzed)"
    
    elif name == "technical":
        momentum = details.get("momentum", {})
        ret_3m = momentum.get("return_3m", 0)
        rsi = details.get("rsi", 50)
        
        trend = "bullish" if details.get("trend", {}).get("golden_cross") else "bearish"
        return f"**Technical** ({weight_pct}%): {level.capitalize()} at {score:.0f}/100 (RSI {rsi:.0f}, {trend} trend, 3M return {ret_3m:+.1f}%)"
    
    elif name == "macro":
        regime = details.get("regime", "neutral")
        return f"**Macro** ({weight_pct}%): {level.capitalize()} at {score:.0f}/100 ({regime} environment)"
    
    return f"**{name.title()}** ({weight_pct}%): {score:.0f}/100"


def _identify_strengths_weaknesses(result: CompositeScoreResult) -> tuple:
    """Identify key strengths and weaknesses."""
    strengths = []
    weaknesses = []
    
    # Check each component
    components = [
        ("Fundamentals", result.fundamental_score, result.details.get("fundamental", {})),
        ("Sentiment", result.sentiment_score, result.details.get("sentiment", {})),
        ("Technical", result.technical_score, result.details.get("technical", {})),
        ("Macro alignment", result.macro_score, result.details.get("macro", {})),
    ]
    
    for name, score, details in components:
        if score >= 70:
            if name == "Fundamentals":
                roe = details.get("roe")
                if roe and roe > 0.15:
                    strengths.append(f"Strong profitability (ROE {roe*100:.1f}%)")
                else:
                    strengths.append(f"Solid fundamental profile")
            elif name == "Sentiment":
                strengths.append(f"Positive news sentiment")
            elif name == "Technical":
                if details.get("trend", {}).get("golden_cross"):
                    strengths.append("Bullish technical trend (golden cross)")
                else:
                    strengths.append("Strong price momentum")
            elif name == "Macro alignment":
                strengths.append(f"Sector well-positioned for current macro")
        
        elif score < 40:
            if name == "Fundamentals":
                pe = details.get("pe_ratio")
                if pe and pe > 40:
                    weaknesses.append(f"High valuation (P/E {pe:.0f})")
                else:
                    weaknesses.append("Weak fundamental metrics")
            elif name == "Sentiment":
                weaknesses.append("Negative news sentiment")
            elif name == "Technical":
                rsi = details.get("rsi", 50)
                if rsi > 70:
                    weaknesses.append(f"Overbought (RSI {rsi:.0f})")
                else:
                    weaknesses.append("Bearish technical indicators")
            elif name == "Macro alignment":
                weaknesses.append("Sector headwinds in current macro environment")
    
    return strengths, weaknesses


def _generate_signal_reason(result: CompositeScoreResult) -> str:
    """Generate reason for the signal."""
    score = result.total_score
    signal = result.signal
    
    if signal == Signal.BUY:
        if score >= 80:
            return f"Strong BUY with {score:.0f}/100 score. Multiple factors align favorably."
        else:
            return f"BUY signal at {score:.0f}/100. Above 70 threshold with favorable outlook."
    
    elif signal == Signal.HOLD:
        if score >= 55:
            return f"HOLD (leaning positive) at {score:.0f}/100. Solid but not compelling enough for BUY."
        elif score >= 45:
            return f"Neutral HOLD at {score:.0f}/100. Mixed signals across factors."
        else:
            return f"HOLD (leaning negative) at {score:.0f}/100. Approaching SELL territory."
    
    else:  # SELL
        if score < 25:
            return f"Strong SELL at {score:.0f}/100. Multiple warning signs present."
        else:
            return f"SELL signal at {score:.0f}/100. Below 40 threshold with concerning outlook."


def _generate_change_drivers(result: CompositeScoreResult) -> Optional[List[str]]:
    """Generate explanation for week-over-week changes."""
    if result.score_change is None:
        return None
    
    drivers = []
    change = result.score_change
    
    if abs(change) < 2:
        drivers.append(f"Score essentially unchanged ({change:+.1f} pts)")
    elif change > 0:
        drivers.append(f"Score improved by {change:+.1f} points")
    else:
        drivers.append(f"Score declined by {change:.1f} points")
    
    if result.signal_change:
        drivers.append(f"Signal changed: {result.signal_change}")
    
    return drivers


def explain_score(result: CompositeScoreResult) -> ScoreExplanation:
    """
    Generate comprehensive explanation for a score.
    
    Args:
        result: CompositeScoreResult to explain
    
    Returns:
        ScoreExplanation with human-readable text
    """
    # Generate one-line summary
    level = _get_strength_level(result.total_score)
    summary = f"{result.ticker} scores {result.total_score:.0f}/100 ({result.signal.value}) — {level} overall rating"
    
    # Signal reason
    signal_reason = _generate_signal_reason(result)
    
    # Component breakdown
    breakdown = [
        _get_component_summary("fundamental", result.fundamental_score, WEIGHTS["fundamental"], 
                              result.details.get("fundamental", {})),
        _get_component_summary("sentiment", result.sentiment_score, WEIGHTS["sentiment"],
                              result.details.get("sentiment", {})),
        _get_component_summary("technical", result.technical_score, WEIGHTS["technical"],
                              result.details.get("technical", {})),
        _get_component_summary("macro", result.macro_score, WEIGHTS["macro"],
                              result.details.get("macro", {})),
    ]
    
    # Strengths and weaknesses
    strengths, weaknesses = _identify_strengths_weaknesses(result)
    
    # Change drivers
    change_drivers = _generate_change_drivers(result)
    
    return ScoreExplanation(
        ticker=result.ticker,
        summary=summary,
        signal_reason=signal_reason,
        component_breakdown=breakdown,
        strengths=strengths or ["No significant strengths identified"],
        weaknesses=weaknesses or ["No significant weaknesses identified"],
        change_drivers=change_drivers,
    )


def explain_score_simple(result: CompositeScoreResult) -> str:
    """
    Generate a simple one-paragraph explanation.
    
    Good for API responses and quick views.
    """
    explanation = explain_score(result)
    
    parts = [explanation.summary, explanation.signal_reason]
    
    if explanation.strengths and explanation.strengths[0] != "No significant strengths identified":
        parts.append(f"Key strength: {explanation.strengths[0]}.")
    
    if explanation.weaknesses and explanation.weaknesses[0] != "No significant weaknesses identified":
        parts.append(f"Watch out for: {explanation.weaknesses[0]}.")
    
    return " ".join(parts)


def format_explanation_markdown(explanation: ScoreExplanation) -> str:
    """Format explanation as Markdown (for reports/UI)."""
    lines = [
        f"## {explanation.ticker} Score Analysis",
        "",
        f"**{explanation.summary}**",
        "",
        f"### Signal",
        explanation.signal_reason,
        "",
        "### Component Breakdown",
    ]
    
    for comp in explanation.component_breakdown:
        lines.append(f"- {comp}")
    
    lines.extend([
        "",
        "### Strengths",
    ])
    for s in explanation.strengths:
        lines.append(f"- ✅ {s}")
    
    lines.extend([
        "",
        "### Weaknesses",
    ])
    for w in explanation.weaknesses:
        lines.append(f"- ⚠️ {w}")
    
    if explanation.change_drivers:
        lines.extend([
            "",
            "### Week-over-Week Changes",
        ])
        for d in explanation.change_drivers:
            lines.append(f"- {d}")
    
    return "\n".join(lines)


# CLI for testing
if __name__ == "__main__":
    from scoring.composite_score import calculate_composite_scores
    
    print("\n=== Score Explainability Test ===\n")
    
    # Calculate scores for a few stocks
    tickers = ["AAPL", "TSLA", "JPM"]
    scores = calculate_composite_scores(tickers=tickers)
    
    for ticker in tickers:
        result = scores.get(ticker)
        if result:
            print("=" * 60)
            explanation = explain_score(result)
            print(format_explanation_markdown(explanation))
            print()
            print("Simple version:")
            print(explain_score_simple(result))
            print()
    
    print("✅ Score explainability working!")
