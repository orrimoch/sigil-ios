"""
Relative Scoring Module

Implements Bayesian Shrinkage + Percentile Ranking for all score components.
This ensures scores are relative (compared to population) rather than absolute.

Formula:
1. Bayesian Shrinkage: adjusted = (n × raw + k × mean) / (n + k)
   - n = sample size (article count, data points, etc.)
   - k = prior strength (default 5)
   - mean = population mean of raw scores
   
2. Percentile Rank: final = percentile position among all stocks (0-100)
   - Rank 1 (best) → 100
   - Rank last (worst) → 0
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from loguru import logger


# Configuration
DEFAULT_PRIOR_STRENGTH = 5  # k value for Bayesian shrinkage


@dataclass
class RelativeScoreResult:
    """Result of relative scoring transformation."""
    ticker: str
    raw_score: float
    sample_size: int
    shrunk_score: float
    percentile_score: float
    rank: int
    total_stocks: int


def bayesian_shrink(
    raw_score: float,
    sample_size: int,
    population_mean: float,
    k: int = DEFAULT_PRIOR_STRENGTH
) -> float:
    """
    Apply Bayesian shrinkage to a raw score.
    
    Scores with small sample sizes are pulled toward the population mean.
    Scores with large sample sizes stay close to their raw value.
    
    Args:
        raw_score: Original score (0-100)
        sample_size: Number of data points (articles, metrics, etc.)
        population_mean: Mean of all raw scores in population
        k: Prior strength - higher = more shrinkage for small samples
        
    Returns:
        Shrunk score (0-100)
    """
    if sample_size <= 0:
        return population_mean
    
    shrunk = (sample_size * raw_score + k * population_mean) / (sample_size + k)
    return shrunk


def percentile_rank(scores: Dict[str, float], higher_is_better: bool = True) -> Dict[str, float]:
    """
    Convert scores to percentile ranks (0-100).
    
    Args:
        scores: Dict mapping ticker to score
        higher_is_better: If True, highest score = 100. If False, lowest = 100.
        
    Returns:
        Dict mapping ticker to percentile (0-100)
    """
    if not scores:
        return {}
    
    n = len(scores)
    if n == 1:
        # Single stock gets 50 (middle)
        return {ticker: 50.0 for ticker in scores}
    
    # Sort by score
    sorted_items = sorted(scores.items(), key=lambda x: x[1], reverse=higher_is_better)
    
    # Assign percentiles
    # Rank 1 → 100, Rank n → 0
    result = {}
    for rank, (ticker, score) in enumerate(sorted_items, start=1):
        # Linear interpolation: rank 1 = 100, rank n = 0
        percentile = 100 * (n - rank) / (n - 1) if n > 1 else 50
        result[ticker] = round(percentile, 2)
    
    return result


def apply_relative_scoring(
    raw_scores: Dict[str, Tuple[float, int]],
    k: int = DEFAULT_PRIOR_STRENGTH,
    higher_is_better: bool = True
) -> Dict[str, RelativeScoreResult]:
    """
    Apply full relative scoring pipeline: Shrinkage + Percentile.
    
    Args:
        raw_scores: Dict mapping ticker to (raw_score, sample_size)
        k: Prior strength for Bayesian shrinkage
        higher_is_better: Direction for percentile ranking
        
    Returns:
        Dict mapping ticker to RelativeScoreResult
    """
    if not raw_scores:
        return {}
    
    # Filter out None scores
    valid_scores = {t: (s, n) for t, (s, n) in raw_scores.items() if s is not None}
    
    if not valid_scores:
        return {}
    
    # Step 1: Calculate population mean
    raw_values = [score for score, _ in valid_scores.values()]
    population_mean = np.mean(raw_values)
    
    logger.debug(f"Population mean: {population_mean:.2f} (n={len(valid_scores)})")
    
    # Step 2: Apply Bayesian shrinkage
    shrunk_scores = {}
    for ticker, (raw_score, sample_size) in valid_scores.items():
        shrunk = bayesian_shrink(raw_score, sample_size, population_mean, k)
        shrunk_scores[ticker] = shrunk
    
    # Step 3: Apply percentile ranking
    percentile_scores = percentile_rank(shrunk_scores, higher_is_better)
    
    # Step 4: Build results with all metadata
    sorted_by_percentile = sorted(percentile_scores.items(), key=lambda x: x[1], reverse=True)
    results = {}
    
    for rank, (ticker, percentile) in enumerate(sorted_by_percentile, start=1):
        raw_score, sample_size = valid_scores[ticker]
        results[ticker] = RelativeScoreResult(
            ticker=ticker,
            raw_score=round(raw_score, 2),
            sample_size=sample_size,
            shrunk_score=round(shrunk_scores[ticker], 2),
            percentile_score=percentile,
            rank=rank,
            total_stocks=len(valid_scores)
        )
    
    return results


def transform_component_scores(
    scores_with_samples: Dict[str, Tuple[Optional[float], int]],
    component_name: str,
    k: int = DEFAULT_PRIOR_STRENGTH
) -> Dict[str, float]:
    """
    Transform a component's raw scores to relative percentile scores.
    
    Convenience function that returns just the final percentile scores.
    
    Args:
        scores_with_samples: Dict mapping ticker to (raw_score, sample_size)
                            raw_score can be None (will use population mean)
        component_name: Name for logging (e.g., "Sentiment", "Fundamental")
        k: Prior strength
        
    Returns:
        Dict mapping ticker to final percentile score (0-100)
    """
    # Separate valid and missing scores
    valid = {t: (s, n) for t, (s, n) in scores_with_samples.items() if s is not None}
    missing = [t for t, (s, _) in scores_with_samples.items() if s is None]
    
    if not valid:
        logger.warning(f"{component_name}: No valid scores, returning 50 for all")
        return {t: 50.0 for t in scores_with_samples}
    
    # Apply relative scoring to valid scores
    results = apply_relative_scoring(valid, k=k)
    
    # Convert to simple dict
    final_scores = {t: r.percentile_score for t, r in results.items()}
    
    # Handle missing scores - assign median percentile (50)
    for ticker in missing:
        final_scores[ticker] = 50.0
    
    # Log summary
    if results:
        scores_list = [r.percentile_score for r in results.values()]
        logger.info(
            f"{component_name} relative scoring: "
            f"n={len(valid)}, k={k}, "
            f"min={min(scores_list):.0f}, max={max(scores_list):.0f}, "
            f"missing={len(missing)}"
        )
    
    return final_scores


# Convenience functions for each component

def transform_sentiment_scores(
    sentiment_results: Dict,  # ticker -> SentimentScoreResult
    k: int = DEFAULT_PRIOR_STRENGTH
) -> Dict[str, float]:
    """Transform sentiment scores using article count as sample size."""
    scores_with_samples = {}
    for ticker, result in sentiment_results.items():
        if result is None:
            scores_with_samples[ticker] = (None, 0)
        else:
            scores_with_samples[ticker] = (result.total_score, result.article_count)
    
    return transform_component_scores(scores_with_samples, "Sentiment", k)


def transform_fundamental_scores(
    fundamental_results: Dict,  # ticker -> FundamentalScoreResult
    k: int = DEFAULT_PRIOR_STRENGTH
) -> Dict[str, float]:
    """Transform fundamental scores using metric count as sample size."""
    scores_with_samples = {}
    for ticker, result in fundamental_results.items():
        if result is None:
            scores_with_samples[ticker] = (None, 0)
        else:
            # Count non-null metrics as sample size
            details = result.details or {}
            metrics_count = sum(1 for v in details.values() if v is not None and v != 0)
            # Minimum sample size of 1 if we have a score
            n = max(metrics_count, 1) if result.total_score is not None else 0
            scores_with_samples[ticker] = (result.total_score, n)
    
    return transform_component_scores(scores_with_samples, "Fundamental", k)


def transform_technical_scores(
    technical_results: Dict,  # ticker -> TechnicalScoreResult  
    k: int = DEFAULT_PRIOR_STRENGTH
) -> Dict[str, float]:
    """Transform technical scores using indicator count as sample size."""
    scores_with_samples = {}
    for ticker, result in technical_results.items():
        if result is None:
            scores_with_samples[ticker] = (None, 0)
        else:
            # Technical typically has 3-4 indicators
            details = result.details or {}
            n = len([v for v in details.values() if v is not None])
            n = max(n, 1)
            scores_with_samples[ticker] = (result.total_score, n)
    
    return transform_component_scores(scores_with_samples, "Technical", k)


def transform_macro_scores(
    macro_results: Dict,  # ticker -> MacroScoreResult
    k: int = DEFAULT_PRIOR_STRENGTH  
) -> Dict[str, float]:
    """Transform macro scores. Macro is sector-based so all have similar sample size."""
    scores_with_samples = {}
    for ticker, result in macro_results.items():
        if result is None:
            scores_with_samples[ticker] = (None, 0)
        else:
            # Macro uses same data sources for all, so n is consistent
            # Use 3 as standard (VIX, HMM, sector trend)
            scores_with_samples[ticker] = (result.total_score, 3)
    
    return transform_component_scores(scores_with_samples, "Macro", k)
