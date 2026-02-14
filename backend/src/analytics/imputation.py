"""
Missing Score Imputation Module (REC-271)

Handles missing score data by imputing with sector averages.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import statistics


@dataclass
class ImputationStats:
    """Statistics about imputation performed."""
    total_stocks: int
    missing_count: int
    imputed_count: int
    imputation_rate: float  # % of scores that were imputed
    sector_averages: Dict[str, float]  # sector -> average score used
    
    def to_dict(self) -> dict:
        return {
            "total_stocks": self.total_stocks,
            "missing_count": self.missing_count,
            "imputed_count": self.imputed_count,
            "imputation_rate": round(self.imputation_rate, 2),
            "sector_averages": self.sector_averages
        }


def impute_missing_scores(
    scores: Dict[str, Optional[float]],
    sector_mapping: Dict[str, str],
    sector_scores: Optional[Dict[str, List[float]]] = None
) -> Tuple[Dict[str, float], ImputationStats]:
    """
    Impute missing scores using sector averages.
    
    Args:
        scores: Dict of ticker -> score (None for missing)
        sector_mapping: Dict of ticker -> sector name
        sector_scores: Optional pre-computed sector scores
        
    Returns:
        Tuple of (imputed_scores, imputation_stats)
    """
    # Calculate sector averages from available scores
    if sector_scores is None:
        sector_scores = {}
        for ticker, score in scores.items():
            if score is not None:
                sector = sector_mapping.get(ticker, "Unknown")
                if sector not in sector_scores:
                    sector_scores[sector] = []
                sector_scores[sector].append(score)
    
    sector_averages = {}
    for sector, score_list in sector_scores.items():
        if score_list:
            sector_averages[sector] = statistics.mean(score_list)
        else:
            sector_averages[sector] = 50.0  # Default neutral score
    
    # Global fallback average
    all_scores = [s for s in scores.values() if s is not None]
    global_average = statistics.mean(all_scores) if all_scores else 50.0
    
    # Impute missing scores
    imputed_scores = {}
    missing_count = 0
    imputed_count = 0
    
    for ticker, score in scores.items():
        if score is not None:
            imputed_scores[ticker] = score
        else:
            missing_count += 1
            sector = sector_mapping.get(ticker, "Unknown")
            
            # Use sector average, or global average if sector has no data
            imputed_value = sector_averages.get(sector, global_average)
            imputed_scores[ticker] = imputed_value
            imputed_count += 1
    
    total_stocks = len(scores)
    imputation_rate = (imputed_count / total_stocks * 100) if total_stocks > 0 else 0
    
    stats = ImputationStats(
        total_stocks=total_stocks,
        missing_count=missing_count,
        imputed_count=imputed_count,
        imputation_rate=imputation_rate,
        sector_averages={k: round(v, 2) for k, v in sector_averages.items()}
    )
    
    return imputed_scores, stats


def calculate_imputation_confidence(imputation_rate: float) -> str:
    """
    Calculate confidence level based on imputation rate.
    
    Args:
        imputation_rate: Percentage of imputed scores
        
    Returns:
        Confidence level string
    """
    if imputation_rate <= 5:
        return "HIGH"
    elif imputation_rate <= 15:
        return "MEDIUM"
    elif imputation_rate <= 30:
        return "LOW"
    else:
        return "VERY LOW"


def get_imputation_warning(imputation_rate: float) -> Optional[str]:
    """
    Get warning message if imputation rate is concerning.
    
    Args:
        imputation_rate: Percentage of imputed scores
        
    Returns:
        Warning message or None
    """
    if imputation_rate <= 15:
        return None
    elif imputation_rate <= 30:
        return f"⚠️ {imputation_rate:.1f}% of scores were imputed with sector averages. Results may be less reliable."
    else:
        return f"⚠️ WARNING: {imputation_rate:.1f}% of scores were imputed. Analysis reliability is significantly reduced."
