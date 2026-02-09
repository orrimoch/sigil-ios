"""
Sector Correlation Limits - REC-245

Warn when portfolio has too much exposure to a single sector.
Default threshold: 30% in any one sector.

Sector mapping uses GICS classification from stock metadata.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)


# Sector mapping (GICS sectors)
SECTORS = [
    "Technology",
    "Healthcare",
    "Financials",
    "Consumer Discretionary",
    "Consumer Staples",
    "Industrials",
    "Energy",
    "Materials",
    "Utilities",
    "Real Estate",
    "Communication Services",
]


@dataclass
class SectorExposure:
    """Exposure to a single sector."""
    sector: str
    value: float           # Dollar value
    percentage: float      # Percentage of portfolio
    tickers: List[str]     # Tickers in this sector
    exceeds_limit: bool    # True if above threshold


@dataclass
class SectorAnalysisResult:
    """Result of sector exposure analysis."""
    exposures: List[SectorExposure]
    warnings: List[Dict[str, Any]]
    total_value: float
    most_concentrated: Optional[str]
    concentration_pct: float
    diversification_score: float  # 0-100, higher is more diversified
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "exposures": [
                {
                    "sector": e.sector,
                    "value": round(e.value, 2),
                    "percentage": round(e.percentage * 100, 2),
                    "tickers": e.tickers,
                    "exceeds_limit": e.exceeds_limit,
                }
                for e in self.exposures
            ],
            "warnings": self.warnings,
            "total_value": round(self.total_value, 2),
            "most_concentrated": self.most_concentrated,
            "concentration_pct": round(self.concentration_pct * 100, 2),
            "diversification_score": round(self.diversification_score, 1),
        }


async def get_sector_for_ticker(ticker: str) -> str:
    """Get sector for a ticker from database or API."""
    try:
        # Try to get from local stock data first
        import json
        from pathlib import Path
        
        stocks_path = Path(__file__).parent.parent.parent / "data" / "stocks.json"
        if stocks_path.exists():
            with open(stocks_path) as f:
                stocks = json.load(f)
            
            for stock in stocks:
                if stock.get("ticker") == ticker.upper():
                    return stock.get("sector", "Unknown")
        
        # Fallback: fetch from yfinance
        import yfinance as yf
        stock = yf.Ticker(ticker)
        info = stock.info
        return info.get("sector", "Unknown")
        
    except Exception as e:
        logger.warning(f"Could not get sector for {ticker}: {e}")
        return "Unknown"


async def analyze_sector_exposure(
    positions: List[Dict[str, Any]],
    warn_threshold: float = 0.30,
) -> Dict[str, Any]:
    """
    Analyze portfolio sector concentration.
    
    Args:
        positions: List of positions with ticker, quantity, market_value
        warn_threshold: Warning threshold (0.30 = 30%)
        
    Returns:
        Analysis result with exposures and warnings
    """
    if not positions:
        return {
            "exposures": [],
            "warnings": [],
            "total_value": 0,
            "most_concentrated": None,
            "concentration_pct": 0,
            "diversification_score": 100,
            "message": "No positions in portfolio",
        }
    
    # Calculate total portfolio value
    total_value = sum(p.get("market_value", 0) for p in positions)
    
    if total_value == 0:
        return {
            "exposures": [],
            "warnings": [],
            "total_value": 0,
            "most_concentrated": None,
            "concentration_pct": 0,
            "diversification_score": 100,
            "message": "Portfolio has no value",
        }
    
    # Group positions by sector
    sector_values: Dict[str, float] = {}
    sector_tickers: Dict[str, List[str]] = {}
    
    for position in positions:
        ticker = position.get("ticker", "")
        value = position.get("market_value", 0)
        sector = await get_sector_for_ticker(ticker)
        
        if sector not in sector_values:
            sector_values[sector] = 0
            sector_tickers[sector] = []
        
        sector_values[sector] += value
        sector_tickers[sector].append(ticker)
    
    # Build exposures list
    exposures: List[SectorExposure] = []
    warnings: List[Dict[str, Any]] = []
    
    for sector, value in sorted(sector_values.items(), key=lambda x: -x[1]):
        pct = value / total_value
        exceeds = pct > warn_threshold
        
        exposure = SectorExposure(
            sector=sector,
            value=value,
            percentage=pct,
            tickers=sector_tickers[sector],
            exceeds_limit=exceeds,
        )
        exposures.append(exposure)
        
        if exceeds:
            warnings.append({
                "type": "sector_concentration",
                "severity": "high" if pct > 0.40 else "medium",
                "message": f"{sector} sector is {pct*100:.1f}% of portfolio (threshold: {warn_threshold*100:.0f}%)",
                "sector": sector,
                "percentage": pct,
            })
    
    # Calculate diversification score (Herfindahl-Hirschman Index inverse)
    # HHI = sum of squared percentages, range 0-1
    # Lower HHI = more diversified
    hhi = sum((e.percentage ** 2) for e in exposures)
    
    # Convert to 0-100 score where 100 = perfectly diversified
    # If all in one sector, HHI = 1, score = 0
    # If equally split across 10 sectors, HHI = 0.1, score = 90
    diversification_score = (1 - hhi) * 100
    
    # Find most concentrated
    most_concentrated = exposures[0].sector if exposures else None
    concentration_pct = exposures[0].percentage if exposures else 0
    
    result = SectorAnalysisResult(
        exposures=exposures,
        warnings=warnings,
        total_value=total_value,
        most_concentrated=most_concentrated,
        concentration_pct=concentration_pct,
        diversification_score=diversification_score,
    )
    
    return result.to_dict()


def validate_trade_sector_impact(
    ticker: str,
    trade_value: float,
    portfolio_positions: List[Dict[str, Any]],
    warn_threshold: float = 0.30,
) -> Dict[str, Any]:
    """
    Check if a trade would cause sector concentration.
    
    Called before executing a trade to warn user.
    """
    import asyncio
    
    # Get sector for the trade ticker
    loop = asyncio.new_event_loop()
    sector = loop.run_until_complete(get_sector_for_ticker(ticker))
    loop.close()
    
    # Calculate current sector exposure
    total_value = sum(p.get("market_value", 0) for p in portfolio_positions)
    sector_value = sum(
        p.get("market_value", 0) 
        for p in portfolio_positions 
        if p.get("sector") == sector
    )
    
    # Calculate post-trade exposure
    new_total = total_value + trade_value
    new_sector_value = sector_value + trade_value
    new_sector_pct = new_sector_value / new_total if new_total > 0 else 0
    
    warnings = []
    if new_sector_pct > warn_threshold:
        warnings.append({
            "type": "sector_concentration",
            "message": f"This trade would put {sector} at {new_sector_pct*100:.1f}% of portfolio",
            "sector": sector,
            "current_pct": sector_value / total_value if total_value > 0 else 0,
            "post_trade_pct": new_sector_pct,
        })
    
    return {
        "sector": sector,
        "current_exposure_pct": sector_value / total_value if total_value > 0 else 0,
        "post_trade_exposure_pct": new_sector_pct,
        "exceeds_threshold": new_sector_pct > warn_threshold,
        "warnings": warnings,
    }
