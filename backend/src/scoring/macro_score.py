"""
F2.4 Macro Score

Score sector alignment with macro environment.
Maps sectors to macro sensitivity and adjusts scores based on current regime.
"""

import numpy as np
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path
import json
from loguru import logger
from dataclasses import dataclass

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from data.macro_fetcher import (
    get_macro_summary,
    calculate_macro_score as get_macro_environment_score,
    get_sector_macro_sensitivity,
)
from data.stock_universe import get_universe


# Cache directory
CACHE_DIR = Path(__file__).parent.parent.parent / "data"
MACRO_SCORES_CACHE = CACHE_DIR / "macro_scores.json"


@dataclass
class MacroScoreResult:
    """Result of macro score calculation."""
    ticker: str
    sector: str
    total_score: float  # 0-100
    environment_score: float  # Overall macro environment
    sector_alignment: float  # How well sector fits current macro
    details: Dict


def calculate_sector_macro_score(
    sector: str,
    macro_data: Dict = None
) -> Dict:
    """
    Calculate macro score for a sector based on current conditions.
    
    Args:
        sector: GICS sector name
        macro_data: Pre-loaded macro data (if None, fetches)
    
    Returns:
        Dict with score and breakdown
    """
    if macro_data is None:
        macro_data = get_macro_summary()
    
    indicators = macro_data.get("indicators", {})
    sensitivity = get_sector_macro_sensitivity().get(sector, {})
    
    if not sensitivity:
        return {
            "score": 50.0,
            "alignment": 0,
            "details": {"error": f"Unknown sector: {sector}"}
        }
    
    # Get current macro values
    fed_rate = indicators.get("fed_funds_rate", {}).get("value", 4.5)
    vix = indicators.get("vix", {}).get("value", 20)
    gdp_growth = indicators.get("gdp_growth", {}).get("value", 2.0)
    unemployment = indicators.get("unemployment_rate", {}).get("value", 4.0)
    
    # Calculate alignment scores for each factor
    # Rate sensitivity: negative = hurt by high rates
    rate_impact = 0
    if sensitivity.get("rate_sensitivity", 0) < 0:
        # Sector hurt by high rates
        if fed_rate < 3:
            rate_impact = 20  # Low rates = good
        elif fed_rate < 4:
            rate_impact = 10
        elif fed_rate < 5:
            rate_impact = 0
        else:
            rate_impact = -15  # High rates = bad
    else:
        # Sector benefits from high rates (e.g., Financials)
        if fed_rate > 5:
            rate_impact = 15
        elif fed_rate > 4:
            rate_impact = 10
        elif fed_rate > 3:
            rate_impact = 5
        else:
            rate_impact = -5
    
    # Scale by sensitivity magnitude
    rate_impact *= abs(sensitivity.get("rate_sensitivity", 0.5))
    
    # VIX sensitivity: negative = hurt by high volatility
    vix_impact = 0
    if sensitivity.get("vix_sensitivity", 0) < 0:
        if vix < 15:
            vix_impact = 15
        elif vix < 20:
            vix_impact = 5
        elif vix < 25:
            vix_impact = -5
        else:
            vix_impact = -15
    else:
        # Defensive sectors benefit from volatility
        if vix > 25:
            vix_impact = 10
        elif vix > 20:
            vix_impact = 5
        else:
            vix_impact = 0
    
    vix_impact *= abs(sensitivity.get("vix_sensitivity", 0.3))
    
    # GDP sensitivity
    gdp_impact = 0
    if sensitivity.get("gdp_sensitivity", 0.5) > 0.5:
        # Cyclical sector - benefits from growth
        if gdp_growth > 3:
            gdp_impact = 15
        elif gdp_growth > 2:
            gdp_impact = 10
        elif gdp_growth > 1:
            gdp_impact = 0
        else:
            gdp_impact = -15
    else:
        # Defensive sector
        gdp_impact = 5  # Stable regardless
    
    gdp_impact *= sensitivity.get("gdp_sensitivity", 0.5)
    
    # Combine impacts
    alignment = rate_impact + vix_impact + gdp_impact
    
    # Convert to 0-100 score centered at 50
    score = 50 + alignment
    score = max(0, min(100, score))
    
    return {
        "score": round(score, 2),
        "alignment": round(alignment, 2),
        "details": {
            "rate_impact": round(rate_impact, 2),
            "vix_impact": round(vix_impact, 2),
            "gdp_impact": round(gdp_impact, 2),
            "current_conditions": {
                "fed_rate": fed_rate,
                "vix": vix,
                "gdp_growth": gdp_growth,
            },
            "sensitivity": sensitivity,
        }
    }


def calculate_macro_score_for_ticker(
    ticker: str,
    sector: str = None,
    macro_data: Dict = None
) -> MacroScoreResult:
    """
    Calculate macro score for a single stock.
    
    Args:
        ticker: Stock ticker
        sector: Stock sector (if None, looks up)
        macro_data: Pre-loaded macro data
    
    Returns:
        MacroScoreResult
    """
    # Get sector if not provided
    if sector is None:
        universe = get_universe()
        for stock in universe:
            if stock["ticker"].upper() == ticker.upper():
                sector = stock["sector"]
                break
    
    if sector is None:
        return MacroScoreResult(
            ticker=ticker,
            sector="Unknown",
            total_score=50.0,
            environment_score=50.0,
            sector_alignment=0.0,
            details={"error": "Sector not found"}
        )
    
    # Get overall macro environment score
    env_score = get_macro_environment_score()
    environment_score = env_score.get("score", 50)
    
    # Get sector-specific score
    sector_result = calculate_sector_macro_score(sector, macro_data)
    
    # Combine: 60% sector alignment, 40% overall environment
    total_score = (
        sector_result["score"] * 0.60 +
        environment_score * 0.40
    )
    
    return MacroScoreResult(
        ticker=ticker,
        sector=sector,
        total_score=round(total_score, 2),
        environment_score=round(environment_score, 2),
        sector_alignment=sector_result["alignment"],
        details={
            "regime": env_score.get("regime", "neutral"),
            "sector_details": sector_result["details"],
        }
    )


def calculate_macro_scores(
    tickers: List[str] = None,
) -> Dict[str, MacroScoreResult]:
    """
    Calculate macro scores for all stocks.
    
    Args:
        tickers: List of tickers (if None, uses universe)
    
    Returns:
        Dict mapping ticker to MacroScoreResult
    """
    universe = get_universe()
    
    if tickers is None:
        tickers = [s["ticker"] for s in universe]
    
    # Build ticker -> sector mapping
    ticker_sectors = {s["ticker"].upper(): s["sector"] for s in universe}
    
    logger.info(f"Calculating macro scores for {len(tickers)} stocks...")
    
    # Load macro data once
    macro_data = get_macro_summary()
    
    results = {}
    for ticker in tickers:
        sector = ticker_sectors.get(ticker.upper())
        result = calculate_macro_score_for_ticker(ticker, sector, macro_data)
        results[ticker] = result
    
    # Log by sector
    sector_scores = {}
    for result in results.values():
        sector = result.sector
        if sector not in sector_scores:
            sector_scores[sector] = []
        sector_scores[sector].append(result.total_score)
    
    logger.info("Macro scores by sector:")
    for sector, scores in sorted(sector_scores.items(), key=lambda x: -np.mean(x[1])):
        avg = np.mean(scores)
        logger.info(f"  {sector}: {avg:.1f}")
    
    return results


def get_macro_score(ticker: str) -> Optional[MacroScoreResult]:
    """Get macro score for a single stock."""
    return calculate_macro_score_for_ticker(ticker)


def save_macro_scores(scores: Dict[str, MacroScoreResult], path: Path = MACRO_SCORES_CACHE) -> None:
    """Save scores to JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    
    data = {
        "updated_at": datetime.now().isoformat(),
        "count": len(scores),
        "scores": {
            ticker: {
                "ticker": r.ticker,
                "sector": r.sector,
                "total_score": r.total_score,
                "environment_score": r.environment_score,
                "sector_alignment": r.sector_alignment,
                "regime": r.details.get("regime"),
            }
            for ticker, r in scores.items()
        }
    }
    
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)
    
    logger.info(f"Saved macro scores to {path}")


def load_macro_scores(path: Path = MACRO_SCORES_CACHE) -> Optional[Dict]:
    """Load scores from JSON."""
    if not path.exists():
        return None
    
    with open(path, 'r') as f:
        return json.load(f)


# CLI for testing
if __name__ == "__main__":
    import sys
    logger.add(sys.stderr, level="INFO")
    
    print("\n=== Macro Score Test ===\n")
    
    # Test single stock
    print("Calculating AAPL macro score...")
    aapl = calculate_macro_score_for_ticker("AAPL")
    print(f"  Sector: {aapl.sector}")
    print(f"  Total Score: {aapl.total_score:.1f}/100")
    print(f"  Environment: {aapl.environment_score:.1f}")
    print(f"  Sector Alignment: {aapl.sector_alignment:+.1f}")
    print(f"  Regime: {aapl.details.get('regime')}")
    
    # Test different sectors
    print("\nScores by sector:")
    test_stocks = [
        ("AAPL", "Technology"),
        ("JPM", "Financials"),
        ("JNJ", "Healthcare"),
        ("XOM", "Energy"),
        ("PG", "Consumer Staples"),
    ]
    for ticker, expected_sector in test_stocks:
        result = calculate_macro_score_for_ticker(ticker)
        print(f"  {ticker} ({result.sector}): {result.total_score:.1f}")
    
    print("\n✅ Macro scoring working!")
