"""
F1.5 Macro Data Fetcher

Fetches macroeconomic indicators from FRED (Federal Reserve Economic Data).
Source: FRED — FREE (no API key required for basic access)
"""

import pandas as pd
import requests
from typing import Dict, Optional, List
from datetime import datetime, timedelta
from pathlib import Path
import json
from loguru import logger


# Cache directory
CACHE_DIR = Path(__file__).parent.parent.parent / "data"
MACRO_CACHE = CACHE_DIR / "macro.json"

# FRED Series IDs for key indicators
FRED_SERIES = {
    # Interest Rates
    "fed_funds_rate": "FEDFUNDS",      # Federal Funds Effective Rate
    "treasury_10y": "DGS10",           # 10-Year Treasury Constant Maturity Rate
    "treasury_2y": "DGS2",             # 2-Year Treasury Constant Maturity Rate
    
    # Inflation
    "cpi_yoy": "CPIAUCSL",             # Consumer Price Index (All Urban)
    "core_pce": "PCEPILFE",            # Core PCE Price Index
    
    # Employment
    "unemployment_rate": "UNRATE",     # Unemployment Rate
    "nonfarm_payrolls": "PAYEMS",      # Total Nonfarm Payrolls
    "initial_claims": "ICSA",          # Initial Jobless Claims
    
    # GDP & Production
    "gdp": "GDP",                       # Gross Domestic Product
    "gdp_growth": "A191RL1Q225SBEA",   # Real GDP Growth Rate
    "industrial_production": "INDPRO", # Industrial Production Index
    
    # Consumer
    "consumer_sentiment": "UMCSENT",   # University of Michigan Consumer Sentiment
    "retail_sales": "RSXFS",           # Retail Sales
    
    # Housing
    "housing_starts": "HOUST",         # Housing Starts
    "existing_home_sales": "EXHOSLUSM495S",  # Existing Home Sales
    
    # Market
    "vix": "VIXCLS",                   # CBOE Volatility Index
    "sp500": "SP500",                  # S&P 500 Index
}

# FRED base URL (no API key needed for basic FRED data via pandas)
FRED_BASE_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"


def fetch_fred_series(
    series_id: str,
    start_date: str = None,
    end_date: str = None,
    periods: int = 365
) -> Optional[pd.DataFrame]:
    """
    Fetch a single FRED series.
    
    Args:
        series_id: FRED series ID (e.g., "FEDFUNDS")
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        periods: Days of history if no start_date
    
    Returns:
        DataFrame with date and value columns
    """
    try:
        if end_date is None:
            end_date = datetime.now().strftime("%Y-%m-%d")
        
        if start_date is None:
            start = datetime.now() - timedelta(days=periods)
            start_date = start.strftime("%Y-%m-%d")
        
        # Construct URL for CSV download
        url = f"{FRED_BASE_URL}?id={series_id}&cosd={start_date}&coed={end_date}"
        
        # Read directly into pandas
        df = pd.read_csv(url)
        
        if df.empty:
            logger.warning(f"No data for FRED series {series_id}")
            return None
        
        # Standardize column names
        df.columns = ["date", "value"]
        df["date"] = pd.to_datetime(df["date"])
        df["series_id"] = series_id
        
        # Handle missing values (FRED uses "." for missing)
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df = df.dropna(subset=["value"])
        
        return df
        
    except Exception as e:
        logger.error(f"Failed to fetch FRED series {series_id}: {e}")
        return None


def fetch_all_macro_data(periods: int = 365) -> Dict[str, Dict]:
    """
    Fetch all macro indicators.
    
    Returns:
        Dict mapping indicator name to data dict
    """
    logger.info(f"Fetching {len(FRED_SERIES)} macro indicators from FRED...")
    
    results = {}
    failed = []
    
    for name, series_id in FRED_SERIES.items():
        df = fetch_fred_series(series_id, periods=periods)
        
        if df is not None and len(df) > 0:
            latest = df.iloc[-1]
            prev = df.iloc[-2] if len(df) > 1 else latest
            
            # Calculate changes
            change = float(latest["value"] - prev["value"])
            change_pct = (change / prev["value"] * 100) if prev["value"] != 0 else 0
            
            results[name] = {
                "series_id": series_id,
                "value": float(latest["value"]),
                "previous": float(prev["value"]),
                "change": round(change, 4),
                "change_percent": round(change_pct, 2),
                "date": latest["date"].strftime("%Y-%m-%d"),
                "fetched_at": datetime.now().isoformat(),
            }
            
            logger.debug(f"  {name}: {latest['value']:.2f}")
        else:
            failed.append(name)
    
    logger.info(f"Fetched {len(results)}/{len(FRED_SERIES)} indicators")
    if failed:
        logger.warning(f"Failed: {failed}")
    
    return results


def get_latest_macro_value(indicator: str) -> Optional[Dict]:
    """
    Get the latest value for a single macro indicator.
    
    Args:
        indicator: Indicator name (e.g., "fed_funds_rate", "vix")
    
    Returns:
        Dict with latest value and metadata
    """
    if indicator not in FRED_SERIES:
        logger.error(f"Unknown indicator: {indicator}")
        return None
    
    series_id = FRED_SERIES[indicator]
    df = fetch_fred_series(series_id, periods=30)
    
    if df is None or df.empty:
        return None
    
    latest = df.iloc[-1]
    
    return {
        "indicator": indicator,
        "series_id": series_id,
        "value": float(latest["value"]),
        "date": latest["date"].strftime("%Y-%m-%d"),
    }


def save_macro_data(data: Dict[str, Dict], path: Path = MACRO_CACHE) -> None:
    """Save macro data to JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    
    output = {
        "updated_at": datetime.now().isoformat(),
        "indicators": data,
    }
    
    with open(path, 'w') as f:
        json.dump(output, f, indent=2)
    
    logger.info(f"Saved macro data to {path}")


def load_macro_data(path: Path = MACRO_CACHE) -> Optional[Dict]:
    """Load macro data from JSON file."""
    if not path.exists():
        return None
    
    with open(path, 'r') as f:
        return json.load(f)


def get_macro_summary() -> Dict:
    """
    Get summary of current macro conditions.
    
    Returns cached data if available, otherwise fetches fresh.
    """
    cached = load_macro_data()
    
    if cached is None:
        data = fetch_all_macro_data()
        save_macro_data(data)
        return {"updated_at": datetime.now().isoformat(), "indicators": data}
    
    return cached


def calculate_macro_score() -> Dict:
    """
    Calculate overall macro environment score (0-100).
    
    Higher = more favorable for equities:
    - Low interest rates
    - Moderate inflation
    - Low unemployment
    - Positive GDP growth
    - Low VIX
    """
    data = get_macro_summary()
    indicators = data.get("indicators", {})
    
    score = 50  # Start neutral
    details = {}
    
    # Fed Funds Rate (lower is better for stocks) - weight: 20
    fed_rate = indicators.get("fed_funds_rate", {}).get("value")
    if fed_rate is not None:
        if fed_rate < 2:
            rate_score = 20
        elif fed_rate < 3:
            rate_score = 15
        elif fed_rate < 4:
            rate_score = 10
        elif fed_rate < 5:
            rate_score = 5
        else:
            rate_score = -5
        score += rate_score - 10  # Normalize around 0
        details["fed_rate"] = {"value": fed_rate, "contribution": rate_score - 10}
    
    # Unemployment Rate (lower is better) - weight: 15
    unemployment = indicators.get("unemployment_rate", {}).get("value")
    if unemployment is not None:
        if unemployment < 4:
            unemp_score = 15
        elif unemployment < 5:
            unemp_score = 10
        elif unemployment < 6:
            unemp_score = 5
        else:
            unemp_score = -5
        score += unemp_score - 7.5
        details["unemployment"] = {"value": unemployment, "contribution": unemp_score - 7.5}
    
    # VIX (lower is better) - weight: 20
    vix = indicators.get("vix", {}).get("value")
    if vix is not None:
        if vix < 15:
            vix_score = 20
        elif vix < 20:
            vix_score = 15
        elif vix < 25:
            vix_score = 10
        elif vix < 30:
            vix_score = 0
        else:
            vix_score = -10
        score += vix_score - 10
        details["vix"] = {"value": vix, "contribution": vix_score - 10}
    
    # Consumer Sentiment (higher is better) - weight: 15
    sentiment = indicators.get("consumer_sentiment", {}).get("value")
    if sentiment is not None:
        if sentiment > 100:
            sent_score = 15
        elif sentiment > 90:
            sent_score = 10
        elif sentiment > 80:
            sent_score = 5
        elif sentiment > 70:
            sent_score = 0
        else:
            sent_score = -10
        score += sent_score - 7.5
        details["consumer_sentiment"] = {"value": sentiment, "contribution": sent_score - 7.5}
    
    # GDP Growth (higher is better) - weight: 15
    gdp_growth = indicators.get("gdp_growth", {}).get("value")
    if gdp_growth is not None:
        if gdp_growth > 3:
            gdp_score = 15
        elif gdp_growth > 2:
            gdp_score = 10
        elif gdp_growth > 1:
            gdp_score = 5
        elif gdp_growth > 0:
            gdp_score = 0
        else:
            gdp_score = -10
        score += gdp_score - 7.5
        details["gdp_growth"] = {"value": gdp_growth, "contribution": gdp_score - 7.5}
    
    # Clamp score
    score = max(0, min(100, score))
    
    # Determine regime
    if score >= 70:
        regime = "bullish"
    elif score >= 50:
        regime = "neutral"
    elif score >= 30:
        regime = "cautious"
    else:
        regime = "bearish"
    
    return {
        "score": round(score, 1),
        "regime": regime,
        "details": details,
        "updated_at": data.get("updated_at"),
    }


def get_sector_macro_sensitivity() -> Dict[str, Dict]:
    """
    Get macro sensitivity scores by sector.
    
    Sectors react differently to macro conditions:
    - Technology: Rate sensitive, growth dependent
    - Financials: Benefit from higher rates
    - Utilities: Defensive, rate sensitive
    - Healthcare: Defensive, less cyclical
    - Consumer Discretionary: GDP/employment sensitive
    - Energy: Oil price dependent
    """
    return {
        "Technology": {
            "rate_sensitivity": -0.8,  # Higher rates hurt
            "gdp_sensitivity": 0.7,
            "vix_sensitivity": -0.5,
        },
        "Financials": {
            "rate_sensitivity": 0.6,   # Higher rates help
            "gdp_sensitivity": 0.5,
            "vix_sensitivity": -0.3,
        },
        "Healthcare": {
            "rate_sensitivity": -0.2,
            "gdp_sensitivity": 0.2,
            "vix_sensitivity": 0.3,    # Defensive in volatility
        },
        "Consumer Discretionary": {
            "rate_sensitivity": -0.5,
            "gdp_sensitivity": 0.8,
            "vix_sensitivity": -0.4,
        },
        "Consumer Staples": {
            "rate_sensitivity": -0.3,
            "gdp_sensitivity": 0.2,
            "vix_sensitivity": 0.4,
        },
        "Energy": {
            "rate_sensitivity": -0.2,
            "gdp_sensitivity": 0.6,
            "vix_sensitivity": -0.2,
        },
        "Utilities": {
            "rate_sensitivity": -0.7,
            "gdp_sensitivity": 0.1,
            "vix_sensitivity": 0.5,
        },
        "Real Estate": {
            "rate_sensitivity": -0.9,
            "gdp_sensitivity": 0.4,
            "vix_sensitivity": -0.3,
        },
        "Industrials": {
            "rate_sensitivity": -0.4,
            "gdp_sensitivity": 0.7,
            "vix_sensitivity": -0.3,
        },
        "Materials": {
            "rate_sensitivity": -0.3,
            "gdp_sensitivity": 0.6,
            "vix_sensitivity": -0.3,
        },
        "Communication Services": {
            "rate_sensitivity": -0.5,
            "gdp_sensitivity": 0.5,
            "vix_sensitivity": -0.4,
        },
    }


# Historical macro data cache
HISTORICAL_MACRO_CACHE = CACHE_DIR / "macro_historical.json"


def fetch_historical_macro_data(
    start_date: str,
    end_date: str,
    force: bool = False
) -> Dict[str, pd.DataFrame]:
    """
    Fetch historical macro data for a date range.
    
    Args:
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        force: Force re-fetch even if cached
    
    Returns:
        Dict mapping indicator name to DataFrame with date/value
    """
    cache_key = f"{start_date}_{end_date}"
    
    # Check cache
    if not force and HISTORICAL_MACRO_CACHE.exists():
        try:
            with open(HISTORICAL_MACRO_CACHE) as f:
                cached = json.load(f)
            if cache_key in cached:
                logger.info(f"Loading cached historical macro data for {start_date} to {end_date}")
                result = {}
                for name, records in cached[cache_key].items():
                    df = pd.DataFrame(records)
                    df['date'] = pd.to_datetime(df['date'])
                    result[name] = df
                return result
        except Exception as e:
            logger.warning(f"Failed to load macro cache: {e}")
    
    logger.info(f"Fetching historical macro data from FRED: {start_date} to {end_date}")
    
    result = {}
    failed = []
    
    for name, series_id in FRED_SERIES.items():
        df = fetch_fred_series(series_id, start_date=start_date, end_date=end_date)
        if df is not None and not df.empty:
            result[name] = df
            logger.debug(f"  {name}: {len(df)} observations")
        else:
            failed.append(name)
    
    if failed:
        logger.warning(f"Failed to fetch: {failed}")
    
    logger.info(f"Fetched {len(result)}/{len(FRED_SERIES)} indicators")
    
    # Cache the results
    try:
        cached = {}
        if HISTORICAL_MACRO_CACHE.exists():
            with open(HISTORICAL_MACRO_CACHE) as f:
                cached = json.load(f)
        
        cached[cache_key] = {
            name: df.to_dict('records') for name, df in result.items()
        }
        
        with open(HISTORICAL_MACRO_CACHE, 'w') as f:
            json.dump(cached, f, default=str)
        
        logger.info(f"Cached historical macro data")
    except Exception as e:
        logger.warning(f"Failed to cache macro data: {e}")
    
    return result


def get_macro_value_at_date(
    indicator: str,
    target_date: str,
    historical_data: Dict[str, pd.DataFrame]
) -> Optional[float]:
    """
    Get macro indicator value for a specific date.
    
    Uses the most recent available value on or before target_date.
    """
    if indicator not in historical_data:
        return None
    
    df = historical_data[indicator]
    target = pd.to_datetime(target_date)
    
    # Get values on or before target date
    mask = df['date'] <= target
    if not mask.any():
        return None
    
    # Get most recent value
    recent = df[mask].iloc[-1]
    return float(recent['value']) if pd.notna(recent['value']) else None


def calculate_macro_score_for_date(
    target_date: str,
    historical_data: Dict[str, pd.DataFrame]
) -> Dict:
    """
    Calculate macro score for a specific historical date.
    
    Uses same logic as calculate_macro_score() but with historical values.
    """
    score = 50  # Start neutral
    details = {}
    
    # Fed Funds Rate (lower is better for stocks) - weight: 20
    fed_rate = get_macro_value_at_date("fed_funds_rate", target_date, historical_data)
    if fed_rate is not None:
        if fed_rate < 2:
            rate_score = 20
        elif fed_rate < 3:
            rate_score = 15
        elif fed_rate < 4:
            rate_score = 10
        elif fed_rate < 5:
            rate_score = 5
        else:
            rate_score = -5
        score += rate_score - 10
        details["fed_rate"] = {"value": fed_rate, "contribution": rate_score - 10}
    
    # Unemployment Rate (lower is better) - weight: 15
    unemployment = get_macro_value_at_date("unemployment_rate", target_date, historical_data)
    if unemployment is not None:
        if unemployment < 4:
            unemp_score = 15
        elif unemployment < 5:
            unemp_score = 10
        elif unemployment < 6:
            unemp_score = 5
        else:
            unemp_score = -5
        score += unemp_score - 7.5
        details["unemployment"] = {"value": unemployment, "contribution": unemp_score - 7.5}
    
    # VIX (lower is better) - weight: 20
    vix = get_macro_value_at_date("vix", target_date, historical_data)
    if vix is not None:
        if vix < 15:
            vix_score = 20
        elif vix < 20:
            vix_score = 15
        elif vix < 25:
            vix_score = 10
        elif vix < 30:
            vix_score = 0
        else:
            vix_score = -10
        score += vix_score - 10
        details["vix"] = {"value": vix, "contribution": vix_score - 10}
    
    # Consumer Sentiment (higher is better) - weight: 15
    sentiment = get_macro_value_at_date("consumer_sentiment", target_date, historical_data)
    if sentiment is not None:
        if sentiment > 100:
            sent_score = 15
        elif sentiment > 90:
            sent_score = 10
        elif sentiment > 80:
            sent_score = 5
        elif sentiment > 70:
            sent_score = 0
        else:
            sent_score = -10
        score += sent_score - 7.5
        details["consumer_sentiment"] = {"value": sentiment, "contribution": sent_score - 7.5}
    
    # GDP Growth (higher is better) - weight: 15
    gdp_growth = get_macro_value_at_date("gdp_growth", target_date, historical_data)
    if gdp_growth is not None:
        if gdp_growth > 3:
            gdp_score = 15
        elif gdp_growth > 2:
            gdp_score = 10
        elif gdp_growth > 1:
            gdp_score = 5
        elif gdp_growth > 0:
            gdp_score = 0
        else:
            gdp_score = -10
        score += gdp_score - 7.5
        details["gdp_growth"] = {"value": gdp_growth, "contribution": gdp_score - 7.5}
    
    # Yield curve (10Y - 2Y) - weight: 15
    treasury_10y = get_macro_value_at_date("treasury_10y", target_date, historical_data)
    treasury_2y = get_macro_value_at_date("treasury_2y", target_date, historical_data)
    if treasury_10y is not None and treasury_2y is not None:
        spread = treasury_10y - treasury_2y
        if spread > 1.0:
            yield_score = 15  # Steep curve = good
        elif spread > 0.5:
            yield_score = 10
        elif spread > 0:
            yield_score = 5
        elif spread > -0.5:
            yield_score = 0  # Flat/inverted = caution
        else:
            yield_score = -10  # Deeply inverted = recession signal
        score += yield_score - 7.5
        details["yield_curve"] = {"value": spread, "contribution": yield_score - 7.5}
    
    # Clamp score
    score = max(0, min(100, score))
    
    # Determine regime
    if score >= 70:
        regime = "bullish"
    elif score >= 50:
        regime = "neutral"
    elif score >= 30:
        regime = "cautious"
    else:
        regime = "bearish"
    
    return {
        "score": round(score, 1),
        "regime": regime,
        "details": details,
        "date": target_date,
    }


# CLI for testing
if __name__ == "__main__":
    import sys
    logger.add(sys.stderr, level="INFO")
    
    print("\n=== Macro Fetcher Test ===\n")
    
    # Test single series
    print("Fetching VIX data...")
    df = fetch_fred_series("VIXCLS", periods=30)
    if df is not None:
        print(f"  Rows: {len(df)}")
        print(f"  Latest: {df.iloc[-1]['value']:.2f}")
        print(f"  Date: {df.iloc[-1]['date']}")
    
    # Test single indicator
    print("\nFetching Fed Funds Rate...")
    rate = get_latest_macro_value("fed_funds_rate")
    if rate:
        print(f"  Value: {rate['value']:.2f}%")
        print(f"  Date: {rate['date']}")
    
    # Test macro score
    print("\nCalculating macro score...")
    macro = calculate_macro_score()
    print(f"  Score: {macro['score']}/100")
    print(f"  Regime: {macro['regime']}")
    
    print("\n✅ Macro fetcher working!")
