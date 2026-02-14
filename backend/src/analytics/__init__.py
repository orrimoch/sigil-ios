"""
Sector Performance Analysis Module (REC-271)

Provides sector-level analysis of Sigil scores:
- Score aggregation by sector/industry
- Temporal trend analysis
- Missing data imputation
- Publication-quality visualizations

CLI Usage:
    python3 -m src.analytics sector-scores [OPTIONS]
    python3 -m src.analytics sector-trends [OPTIONS]
    python3 -m src.analytics sector-report [OPTIONS]
"""

from .sector_analysis import (
    SectorClassification,
    SectorScore,
    SectorTimeSeries,
    SectorAnalyzer,
    get_sector_scores,
    get_sector_trends,
)

from .imputation import (
    impute_missing_scores,
    ImputationStats,
)

from .visualization import (
    plot_sector_trends,
    plot_sector_heatmap,
    plot_score_distribution,
    plot_signal_distribution,
    SIGIL_COLORS,
)

__all__ = [
    # Core analysis
    "SectorClassification",
    "SectorScore",
    "SectorTimeSeries",
    "SectorAnalyzer",
    "get_sector_scores",
    "get_sector_trends",
    # Imputation
    "impute_missing_scores",
    "ImputationStats",
    # Visualization
    "plot_sector_trends",
    "plot_sector_heatmap",
    "plot_score_distribution",
    "plot_signal_distribution",
    "SIGIL_COLORS",
]
