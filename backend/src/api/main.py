"""
Sigil API - Main FastAPI Application

Features:
- F1.x: Data Pipeline (Universe, Prices, Fundamentals, News, Macro)
- F2.x: Scoring System (Fundamental, Sentiment, Technical, Macro, Composite)
- F6.x: Trading (Orders, Portfolio, Paper/Live modes)
"""

from fastapi import FastAPI, HTTPException, Query, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import os
import sys
import logging
from pathlib import Path
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# F1.x Data imports
from data.stock_universe import get_universe, get_sectors, load_universe
from data.price_fetcher import fetch_latest_price, get_price_summary, fetch_latest_prices
from data.fundamental_fetcher import get_fundamentals, calculate_quality_score, calculate_value_score, calculate_growth_score
from data.news_fetcher import get_news_summary, fetch_news_for_ticker, analyze_news_sentiment
from data.macro_fetcher import get_macro_summary, calculate_macro_score, get_sector_macro_sensitivity, get_latest_macro_value, FRED_SERIES
from data.pipeline import Pipeline, run_pipeline, get_latest_run, get_run_history

# F2.x Scoring imports
from scoring import (
    calculate_composite_scores,
    get_top_stocks,
    get_score,
    explain_score,
    explain_score_simple,
    Signal,
    WEIGHTS,
    load_composite_scores,
    save_composite_scores,
)

# F6.x & F7.x Trading imports
from trading import (
    Portfolio,
    Position,
    PortfolioSummary,
    PortfolioSnapshot,
    PortfolioHistory,
    Order,
    OrderType,
    OrderSide,
    OrderStatus,
)
# BUG-025 fix: removed OrderManager/get_order_manager/reset_order_manager imports
# DB (UserTradingService) is the single source of truth — no JSON dual persistence
from trading.portfolio import get_portfolio_history

# F4.4 Alerts imports
from alerts import Alert, AlertType, AlertManager, get_alert_manager

# Auth imports
from auth import auth_router, init_db
from auth.middleware import get_optional_user, get_required_user
from auth.database import get_db_session

# IBKR imports
from ibkr import ibkr_router

# Push notification imports
from notifications.push_routes import router as push_router

# Per-user trading service
from trading.user_trading_service import UserTradingService
from db.models import ANONYMOUS_USER_ID

# Auth config — defaults to False so existing tests/endpoints keep working without tokens
# REC-130: Auth is now REQUIRED by default for production.
# Set AUTH_REQUIRED=false env var to disable for local development.
AUTH_REQUIRED = os.environ.get("AUTH_REQUIRED", "true").lower() in ("true", "1", "yes")

# ========== Price Cache (Bug 2 fix) ==========
# Fast in-memory price cache to avoid slow yfinance calls on every scores request
import time as _time
import threading
import requests as _requests

_price_cache: Dict[str, dict] = {}
_price_cache_ts: Dict[str, float] = {}
_price_cache_lock = threading.Lock()  # BUG-019: thread-safe cache access
_PRICE_CACHE_TTL = 300  # 5 minutes


def _fetch_price_yahoo_chart(ticker: str) -> Optional[dict]:
    """Fast price fetch using Yahoo chart API directly (no yfinance overhead)."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
        url = f'https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range=1d&interval=1m'
        resp = _requests.get(url, headers=headers, timeout=8)
        if resp.status_code == 200:
            meta = resp.json()['chart']['result'][0]['meta']
            price = meta.get('regularMarketPrice', 0)
            prev_close = meta.get('chartPreviousClose', 0)
            change = price - prev_close if prev_close else 0
            change_pct = (change / prev_close * 100) if prev_close else 0
            return {
                "ticker": ticker,
                "price": float(price),
                "change": float(change),
                "change_percent": float(change_pct),
            }
    except Exception:
        pass
    return None


def _get_cached_prices(tickers: List[str]) -> Dict[str, dict]:
    """Get prices for tickers, using cache where available, fetching missing ones in parallel."""
    now = _time.time()
    result = {}
    to_fetch = []
    
    with _price_cache_lock:  # BUG-019: thread-safe read
        for t in tickers:
            if t in _price_cache and (now - _price_cache_ts.get(t, 0)) < _PRICE_CACHE_TTL:
                result[t] = _price_cache[t]
            else:
                to_fetch.append(t)
    
    if to_fetch:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        with ThreadPoolExecutor(max_workers=15) as executor:
            futures = {executor.submit(_fetch_price_yahoo_chart, t): t for t in to_fetch}
            for future in as_completed(futures, timeout=15):
                t = futures[future]
                try:
                    p = future.result()
                    if p:
                        with _price_cache_lock:  # BUG-019: thread-safe write
                            _price_cache[t] = p
                            _price_cache_ts[t] = now
                        result[t] = p
                except Exception:
                    pass
    
    return result


# ── Lifespan ────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: initialise auth database tables and optional scheduler."""
    await init_db()
    
    # REC-132: Auto-start scheduler if enabled
    # Set SCHEDULER_ENABLED=true to start pipeline scheduler on boot
    if os.environ.get("SCHEDULER_ENABLED", "false").lower() in ("true", "1", "yes"):
        try:
            from scheduler import scheduler_instance
            scheduler_instance.start()
            logger.info("Pipeline scheduler auto-started")
        except Exception as e:
            logger.error(f"Failed to start scheduler: {e}")
    
    yield
    
    # Shutdown: stop scheduler if running
    try:
        from scheduler import scheduler_instance
        scheduler_instance.stop()
    except Exception:
        pass


# Initialize FastAPI
app = FastAPI(
    title="Sigil API",
    description="AI-Powered Stock Recommendations for S&P 500",
    version="1.0.0",
    lifespan=lifespan,
)

# BUG-021 fix: Consistent error response format
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "error": exc.detail},
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    return JSONResponse(
        status_code=422,
        content={"success": False, "error": "Validation error", "details": str(exc)},
    )

# CORS — restrict origins (BUG-011 fix)
_cors_origins = os.environ.get("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:8000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Authorization", "Content-Type"],
)

# Include auth router
app.include_router(auth_router)

# Include IBKR router
app.include_router(ibkr_router)

# Include push notification router
app.include_router(push_router, prefix="/api/v1")


# ========== Pydantic Models ==========

class StockResponse(BaseModel):
    ticker: str
    name: str
    sector: str
    industry: str
    market_cap: int
    currency: str = "USD"
    is_active: bool = True


class StocksListResponse(BaseModel):
    success: bool = True
    count: int
    updated_at: Optional[str] = None
    stocks: List[StockResponse]


class SectorsResponse(BaseModel):
    success: bool = True
    sectors: Dict[str, int]


class PriceResponse(BaseModel):
    ticker: str
    price: Optional[float] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    volume: Optional[int] = None
    previous_close: Optional[float] = None
    change: Optional[float] = None
    change_percent: Optional[float] = None
    timestamp: Optional[str] = None


class PricesListResponse(BaseModel):
    success: bool = True
    count: int
    prices: List[PriceResponse]


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "1.0.0"
    timestamp: str


# ========== Endpoints ==========

@app.get("/", response_model=HealthResponse)
@app.get("/api/v1/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/v1/stocks", response_model=StocksListResponse)
async def get_stocks(
    sector: Optional[str] = Query(None, description="Filter by sector"),
    limit: int = Query(100, ge=1, le=1000, description="Number of results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
):
    """
    Get stock universe.
    
    Returns list of S&P 500 stocks with market cap > $10B.
    """
    try:
        cached = load_universe()
        
        if cached is None:
            raise HTTPException(
                status_code=503,
                detail="Stock universe not initialized. Run the data pipeline first."
            )
        
        stocks = cached["stocks"]
        updated_at = cached["updated_at"]
        
        # Filter by sector if specified
        if sector:
            stocks = [s for s in stocks if s["sector"].lower() == sector.lower()]
        
        # Apply pagination
        total = len(stocks)
        stocks = stocks[offset:offset + limit]
        
        return {
            "success": True,
            "count": total,
            "updated_at": updated_at,
            "stocks": stocks
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/stocks/{ticker}", response_model=StockResponse)
async def get_stock(ticker: str):
    """
    Get single stock by ticker.
    """
    try:
        stocks = get_universe()
        
        # Find by ticker (case insensitive)
        ticker_upper = ticker.upper()
        for stock in stocks:
            if stock["ticker"].upper() == ticker_upper:
                return stock
        
        raise HTTPException(status_code=404, detail=f"Stock not found: {ticker}")
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/stocks/sectors/breakdown", response_model=SectorsResponse)
async def get_sector_breakdown():
    """
    Get sector breakdown of stock universe.
    """
    try:
        sectors = get_sectors()
        return {
            "success": True,
            "sectors": sectors
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ========== News Endpoints ==========

@app.get("/api/v1/news")
async def get_news(
    ticker: Optional[str] = Query(None, description="Filter by ticker"),
    limit: int = Query(20, ge=1, le=100, description="Number of articles")
):
    """
    Get news articles, optionally filtered by ticker.
    """
    try:
        result = get_news_summary(ticker.upper() if ticker else None)
        result["articles"] = result["articles"][:limit]
        
        # Add sentiment analysis
        result["sentiment"] = analyze_news_sentiment(result["articles"])
        
        return {"success": True, "data": result}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/news/{ticker}")
async def get_ticker_news(
    ticker: str,
    hours: int = Query(168, ge=1, le=720, description="Look back hours (default 7 days)")
):
    """
    Get news for a specific stock with sentiment analysis.
    """
    try:
        articles = fetch_news_for_ticker(ticker.upper(), hours)
        sentiment = analyze_news_sentiment(articles)
        
        return {
            "success": True,
            "data": {
                "ticker": ticker.upper(),
                "article_count": len(articles),
                "sentiment": sentiment,
                "articles": articles[:50],  # Limit response
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ========== Fundamentals Endpoints ==========

@app.get("/api/v1/fundamentals/{ticker}")
async def get_stock_fundamentals(ticker: str):
    """
    Get fundamental data for a single stock.
    """
    try:
        fund = get_fundamentals(ticker.upper())
        
        if fund is None:
            raise HTTPException(status_code=404, detail=f"Fundamentals not found for {ticker}")
        
        # Add calculated scores
        fund["scores"] = {
            "quality": calculate_quality_score(fund),
            "value": calculate_value_score(fund),
            "growth": calculate_growth_score(fund),
        }
        
        return {"success": True, "data": fund}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ========== Price Endpoints ==========

@app.get("/api/v1/prices/{ticker}", response_model=PriceResponse)
async def get_price(ticker: str):
    """
    Get latest price for a single stock.
    """
    try:
        price = get_price_summary(ticker.upper())
        
        if price is None:
            raise HTTPException(status_code=404, detail=f"Price not found for {ticker}")
        
        return price
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/prices", response_model=PricesListResponse)
async def get_prices(
    tickers: Optional[str] = Query(None, description="Comma-separated tickers (e.g., AAPL,MSFT,GOOGL)"),
    limit: int = Query(10, ge=1, le=50, description="Number of stocks (if no tickers specified)")
):
    """
    Get latest prices for multiple stocks.
    
    If tickers not specified, returns top stocks by market cap.
    """
    try:
        if tickers:
            ticker_list = [t.strip().upper() for t in tickers.split(",")]
        else:
            universe = get_universe()
            ticker_list = [s["ticker"] for s in universe[:limit]]
        
        prices = fetch_latest_prices(ticker_list, max_workers=5)
        
        return {
            "success": True,
            "count": len(prices),
            "prices": prices
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/prices/{ticker}/history")
async def get_price_history(
    ticker: str,
    period: str = Query("3mo", description="Period: 1d, 5d, 1mo, 3mo, 6mo, 1y, 5y, max"),
    interval: str = Query(None, description="Interval: 1m, 5m, 15m, 30m, 1h, 1d (auto-selected if not provided)"),
):
    """
    Get historical price data for charting (BUG-007 fix).
    Supports intraday data via interval parameter.
    """
    try:
        import yfinance as yf
        
        # Map various period formats to yfinance periods
        period_map = {
            # Short formats
            "1d": "1d", "5d": "5d", "1m": "1mo", "3m": "3mo", "6m": "6mo",
            # yfinance native formats  
            "1mo": "1mo", "3mo": "3mo", "6mo": "6mo",
            "1y": "1y", "2y": "2y", "5y": "5y", "10y": "10y",
            "ytd": "ytd", "max": "max",
        }
        yf_period = period_map.get(period.lower(), "3mo")
        
        # Auto-select interval based on period if not provided
        # For intraday (1d), use 5m bars; for 5d use 15m; otherwise daily
        if interval is None:
            interval_map = {
                "1d": "5m",   # 5-minute bars for 1-day chart (~78 bars)
                "5d": "15m",  # 15-minute bars for 5-day chart (~130 bars)
                "1mo": "1h",  # Hourly bars for 1-month chart (~140 bars)
            }
            yf_interval = interval_map.get(yf_period, "1d")
        else:
            yf_interval = interval
        
        stock = yf.Ticker(ticker.upper())
        hist = stock.history(period=yf_period, interval=yf_interval)
        
        if hist.empty:
            raise HTTPException(status_code=404, detail=f"No price history for {ticker}")
        
        data_points = []
        # Use appropriate date format based on interval
        is_intraday = yf_interval in ["1m", "5m", "15m", "30m", "1h", "60m", "90m"]
        for date, row in hist.iterrows():
            date_str = date.isoformat() if is_intraday else date.strftime("%Y-%m-%d")
            data_points.append({
                "date": date_str,
                "open": round(row["Open"], 2),
                "high": round(row["High"], 2),
                "low": round(row["Low"], 2),
                "close": round(row["Close"], 2),
                "volume": int(row["Volume"]),
            })
        
        return {
            "success": True,
            "data": {
                "ticker": ticker.upper(),
                "period": period,
                "count": len(data_points),
                "prices": data_points,
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/data/price-history/{ticker}")
async def get_price_history_alt(
    ticker: str,
    period: str = Query("3m", description="Period: 1m, 3m, 6m, 1y, 5y"),
    interval: str = Query(None, description="Interval: 1m, 5m, 15m, 30m, 1h, 1d (auto-selected if not provided)"),
):
    """
    Alias for price history — matches iOS APIService.getPriceHistory() URL (BUG-017 fix).
    """
    return await get_price_history(ticker, period, interval)


# ========== Macro Endpoints ==========

@app.get("/api/v1/macro")
async def get_macro():
    """
    Get all macro indicators with current values.
    """
    try:
        data = get_macro_summary()
        score = calculate_macro_score()
        
        return {
            "success": True,
            "data": {
                "indicators": data.get("indicators", {}),
                "score": score,
                "updated_at": data.get("updated_at"),
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/macro/score")
async def get_macro_score_endpoint():
    """
    Get overall macro environment score (0-100) and regime classification.
    """
    try:
        score = calculate_macro_score()
        return {"success": True, "data": score}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/macro/sectors")
async def get_sectors_macro_sensitivity():
    """
    Get sector sensitivity to macro factors.
    """
    try:
        sensitivity = get_sector_macro_sensitivity()
        return {"success": True, "data": sensitivity}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/macro/{indicator}")
async def get_macro_indicator(indicator: str):
    """
    Get a single macro indicator.
    
    Available indicators: fed_funds_rate, vix, unemployment_rate, gdp, cpi_yoy, etc.
    Must be defined AFTER /macro/score and /macro/sectors to avoid route shadowing (BUG-004 fix).
    """
    try:
        if indicator not in FRED_SERIES:
            available = list(FRED_SERIES.keys())
            raise HTTPException(
                status_code=404,
                detail=f"Unknown indicator: {indicator}. Available: {available}"
            )
        
        value = get_latest_macro_value(indicator)
        
        if value is None:
            raise HTTPException(status_code=503, detail=f"Failed to fetch {indicator}")
        
        return {"success": True, "data": value}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ========== Market Indices Endpoint (Bug 3 fix) ==========

@app.get("/api/v1/market/indices")
async def get_market_indices():
    """
    Get real market index values (S&P 500, NASDAQ, DOW, VIX).
    Uses Yahoo chart API directly for actual index values, not ETF proxies.
    """
    import requests
    
    indices_map = {
        "^GSPC": {"symbol": "SPX", "name": "S&P 500"},
        "^IXIC": {"symbol": "IXIC", "name": "NASDAQ"},
        "^DJI": {"symbol": "DJI", "name": "DOW"},
        "^VIX": {"symbol": "VIX", "name": "VIX"},
    }
    
    results = []
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
    
    for yahoo_symbol, info in indices_map.items():
        try:
            url = f'https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol}?range=1d&interval=1m'
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                meta = resp.json()['chart']['result'][0]['meta']
                price = meta.get('regularMarketPrice', 0)
                prev_close = meta.get('chartPreviousClose', 0)
                change = price - prev_close if prev_close else 0
                change_pct = (change / prev_close * 100) if prev_close else 0
                results.append({
                    "symbol": info["symbol"],
                    "name": info["name"],
                    "value": round(float(price), 2),
                    "change": round(float(change), 2),
                    "change_percent": round(float(change_pct), 2),
                })
        except Exception as e:
            logger.warning(f"Failed to fetch {yahoo_symbol}: {e}")
            results.append({
                "symbol": info["symbol"],
                "name": info["name"],
                "value": 0,
                "change": 0,
                "change_percent": 0,
            })
    
    return {
        "success": True,
        "count": len(results),
        "indices": results,
    }


# ========== Pipeline Endpoints ==========

# Store for tracking background pipeline runs
_pipeline_runs: Dict[str, dict] = {}


@app.post("/api/v1/pipeline/run")
async def trigger_pipeline(
    background_tasks: BackgroundTasks,
    skip_universe: bool = Query(False),
    skip_prices: bool = Query(False),
    skip_fundamentals: bool = Query(False),
    skip_news: bool = Query(False),
    skip_macro: bool = Query(False),
):
    """
    Trigger a pipeline run (runs in background).
    
    Returns a run_id that can be used to check status.
    """
    try:
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Track run status
        _pipeline_runs[run_id] = {"status": "running", "started_at": datetime.now().isoformat()}
        
        # Define background task
        def run_in_background():
            try:
                pipeline = Pipeline()
                result = pipeline.run(
                    skip_universe=skip_universe,
                    skip_prices=skip_prices,
                    skip_fundamentals=skip_fundamentals,
                    skip_news=skip_news,
                    skip_macro=skip_macro,
                )
                _pipeline_runs[run_id] = result.to_dict()
            except Exception as e:
                _pipeline_runs[run_id] = {
                    "status": "failed",
                    "error": str(e),
                    "completed_at": datetime.now().isoformat()
                }
        
        # Add to background tasks
        background_tasks.add_task(run_in_background)
        
        return {
            "success": True,
            "message": "Pipeline started",
            "run_id": run_id,
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/pipeline/status")
async def get_pipeline_status_general():
    """
    Get overall pipeline status — latest run + any active runs (BUG-006 fix).
    """
    try:
        active_runs = {k: v for k, v in _pipeline_runs.items() if v.get("status") == "running"}
        latest = get_latest_run()
        return {
            "success": True,
            "data": {
                "active_runs": len(active_runs),
                "active": active_runs,
                "latest": latest,
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/pipeline/status/{run_id}")
async def get_pipeline_status(run_id: str):
    """
    Get status of a pipeline run.
    """
    try:
        if run_id in _pipeline_runs:
            return {"success": True, "data": _pipeline_runs[run_id]}
        
        # Try to load from saved logs
        history = get_run_history(limit=50)
        for run in history:
            if run.get("run_id") == run_id:
                return {"success": True, "data": run}
        
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/pipeline/latest")
async def get_latest_pipeline_run():
    """
    Get the most recent pipeline run result.
    """
    try:
        latest = get_latest_run()
        
        if latest is None:
            return {
                "success": True,
                "data": None,
                "message": "No pipeline runs found"
            }
        
        return {"success": True, "data": latest}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/pipeline/history")
async def get_pipeline_history(
    limit: int = Query(10, ge=1, le=50, description="Number of runs to return")
):
    """
    Get recent pipeline run history.
    """
    try:
        history = get_run_history(limit=limit)
        
        return {
            "success": True,
            "count": len(history),
            "data": history
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ========== Scheduler Endpoints (REC-132) ==========

@app.get("/api/v1/scheduler/status")
async def get_scheduler_status():
    """
    Get pipeline scheduler status and health (REC-132).
    
    Returns:
    - is_running: Whether scheduler is active
    - schedule: Human-readable schedule (Sunday 6pm EST)
    - next_run: Next scheduled run time
    - last_run: Most recent run details
    - success_rate: Historical success percentage
    """
    from scheduler import scheduler_instance
    return {"success": True, "data": scheduler_instance.get_status()}


@app.post("/api/v1/scheduler/start")
async def start_scheduler():
    """
    Start the pipeline scheduler (REC-132).
    
    Schedules weekly pipeline runs on Sunday 6pm EST.
    """
    from scheduler import scheduler_instance
    scheduler_instance.start()
    return {"success": True, "message": "Scheduler started", "data": scheduler_instance.get_status()}


@app.post("/api/v1/scheduler/stop")
async def stop_scheduler():
    """
    Stop the pipeline scheduler (REC-132).
    """
    from scheduler import scheduler_instance
    scheduler_instance.stop()
    return {"success": True, "message": "Scheduler stopped", "data": scheduler_instance.get_status()}


@app.post("/api/v1/scheduler/run-now")
async def scheduler_run_now(background_tasks: BackgroundTasks):
    """
    Trigger an immediate pipeline run via scheduler (REC-132).
    
    Useful for manual runs while keeping health tracking.
    """
    from scheduler import scheduler_instance
    
    def run_in_background():
        scheduler_instance.run_now()
    
    background_tasks.add_task(run_in_background)
    return {"success": True, "message": "Pipeline run triggered", "data": scheduler_instance.get_status()}


@app.get("/api/v1/scheduler/history")
async def get_scheduler_history(
    limit: int = Query(10, ge=1, le=50, description="Number of runs to return")
):
    """
    Get scheduler run history (REC-132).
    """
    from scheduler import scheduler_instance
    return {"success": True, "data": scheduler_instance.get_history(limit)}


# ========== Scores Endpoints (F2.x) ==========

@app.get("/api/v1/scores")
async def get_scores(
    signal: Optional[str] = Query(None, description="Filter by signal: BUY, HOLD, SELL"),
    sector: Optional[str] = Query(None, description="Filter by sector"),
    limit: int = Query(50, ge=1, le=1000, description="Number of results"),
    order: Optional[str] = Query("desc", description="Sort order: asc or desc"),
    include_prices: bool = Query(True, description="Include current price data"),
    risk_tolerance: Optional[str] = Query(
        None,
        description="REC-126: Adjust signals by risk tolerance (conservative/moderate/aggressive)"
    ),
):
    """
    Get composite scores for all stocks.
    
    Returns ranked list with scores and signals.
    
    REC-126: Pass risk_tolerance to get signals adjusted for your risk profile:
    - conservative: BUY ≥80, SELL <30 (fewer trades)
    - moderate: BUY ≥70, SELL <40 (default)
    - aggressive: BUY ≥60, SELL <50 (more trades)
    """
    from scoring.composite_score import get_signal, get_thresholds_for_risk
    
    try:
        # Try to load cached scores first
        cached = load_composite_scores()
        
        if cached is None:
            return {
                "success": False,
                "error": "No scores available. Run the pipeline first.",
            }
        
        scores_data = cached.get("scores", {})
        
        # Filter and sort
        results = list(scores_data.values())
        
        # REC-126: Re-evaluate signals based on risk tolerance
        if risk_tolerance and risk_tolerance.lower() in ("conservative", "moderate", "aggressive"):
            risk = risk_tolerance.lower()
            for r in results:
                score = r.get("total_score", 50)
                r["signal"] = get_signal(score, risk).value
                r["risk_adjusted"] = True
                r["risk_tolerance"] = risk
        
        if signal:
            signal_upper = signal.upper()
            results = [s for s in results if s.get("signal") == signal_upper]
        
        if sector:
            results = [s for s in results if s.get("sector", "").lower() == sector.lower()]
        
        # Sort by score with order direction (Bug 1 fix)
        ascending = order and order.lower() == "asc"
        results.sort(key=lambda x: x.get("total_score", 0), reverse=not ascending)
        results = results[:limit]
        
        # Include price data in response (Bug 2 fix)
        if include_prices:
            tickers = [r["ticker"] for r in results]
            price_map = _get_cached_prices(tickers)
            
            for r in results:
                p = price_map.get(r["ticker"])
                if p:
                    r["price"] = p.get("price")
                    r["price_change"] = p.get("change")
                    r["price_change_percent"] = p.get("change_percent")
                else:
                    r["price"] = None
                    r["price_change"] = None
                    r["price_change_percent"] = None
        
        response = {
            "success": True,
            "count": len(results),
            "weights": WEIGHTS,
            "updated_at": cached.get("updated_at"),
            "summary": cached.get("summary", {}),
            "scores": results,
        }
        
        # Include thresholds used if risk-adjusted
        if risk_tolerance:
            response["thresholds"] = get_thresholds_for_risk(risk_tolerance)
        
        return response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/scores/changes")
async def get_score_changes():
    """
    F9.3: Get signal changes since last scoring run.

    Returns list of tickers whose signal changed (e.g. HOLD→BUY).
    """
    try:
        cached = load_composite_scores()

        if cached is None:
            return {
                "success": True,
                "count": 0,
                "data": [],
                "message": "No scores available.",
            }

        scores_data = cached.get("scores", {})

        from scoring.signal_tracker import detect_signal_changes, load_previous_scores
        previous = load_previous_scores()
        changes = detect_signal_changes(scores_data, previous)

        return {
            "success": True,
            "count": len(changes),
            "data": changes,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/scores/summary")
async def get_score_summary():
    """
    F9.1: Get weekly score summary for notifications.

    Returns BUY/HOLD/SELL counts, top movers (biggest score changes),
    and new BUY signals this week.
    """
    try:
        cached = load_composite_scores()

        if cached is None:
            return {
                "success": False,
                "error": "No scores available. Run the pipeline first.",
            }

        scores_data = cached.get("scores", {})
        summary = cached.get("summary", {})

        # Count signals
        buy_count = summary.get("buy_count", 0)
        hold_count = summary.get("hold_count", 0)
        sell_count = summary.get("sell_count", 0)

        # Find top movers (biggest absolute score changes)
        movers = []
        new_buys = []
        for ticker, s in scores_data.items():
            score_change = s.get("score_change")
            signal_change = s.get("signal_change")

            if score_change is not None and score_change != 0:
                movers.append({
                    "ticker": ticker,
                    "score": s.get("total_score", 0),
                    "signal": s.get("signal", "HOLD"),
                    "score_change": score_change,
                    "signal_change": signal_change,
                })

            # New BUY signals (signal changed to BUY)
            if signal_change and signal_change.endswith("BUY"):
                new_buys.append({
                    "ticker": ticker,
                    "score": s.get("total_score", 0),
                    "previous_signal": signal_change.split("→")[0].strip() if "→" in signal_change else None,
                })

        # Sort movers by absolute score change
        movers.sort(key=lambda x: abs(x.get("score_change", 0)), reverse=True)

        return {
            "success": True,
            "data": {
                "buy_count": buy_count,
                "hold_count": hold_count,
                "sell_count": sell_count,
                "total_scored": len(scores_data),
                "signal_changes": len(movers),
                "top_movers": movers[:10],
                "new_buy_signals": new_buys[:10],
                "updated_at": cached.get("updated_at"),
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/scores/{ticker}")
async def get_score_for_ticker(ticker: str):
    """
    Get detailed score for a single stock with explanation.
    """
    try:
        # Validate ticker against stock universe (BUG-003 fix)
        from data.stock_universe import load_universe
        universe = load_universe()
        if universe:
            valid_tickers = {s["ticker"] for s in universe.get("stocks", [])}
            if ticker.upper() not in valid_tickers:
                raise HTTPException(status_code=404, detail=f"Unknown ticker: {ticker}")

        # Try cached scores first
        cached = load_composite_scores()
        
        if cached and ticker.upper() in cached.get("scores", {}):
            score_data = cached["scores"][ticker.upper()]
            
            # Build mock result for explanation
            from scoring.composite_score import CompositeScoreResult
            result = CompositeScoreResult(
                ticker=score_data["ticker"],
                sector=score_data["sector"],
                total_score=score_data["total_score"],
                signal=Signal(score_data["signal"]),
                rank=score_data["rank"],
                percentile=score_data["percentile"],
                fundamental_score=score_data["fundamental_score"],
                sentiment_score=score_data["sentiment_score"],
                technical_score=score_data["technical_score"],
                macro_score=score_data["macro_score"],
                score_change=score_data.get("score_change"),
                signal_change=score_data.get("signal_change"),
                details={},
            )
            
            explanation = explain_score_simple(result)
            
            return {
                "success": True,
                "data": {
                    **score_data,
                    "explanation": explanation,
                }
            }
        
        # Calculate fresh if not cached
        result = get_score(ticker)
        
        if result is None:
            raise HTTPException(status_code=404, detail=f"Score not found for {ticker}")
        
        explanation = explain_score_simple(result)
        
        return {
            "success": True,
            "data": {
                "ticker": result.ticker,
                "sector": result.sector,
                "total_score": result.total_score,
                "signal": result.signal.value,
                "rank": result.rank,
                "percentile": result.percentile,
                "fundamental_score": result.fundamental_score,
                "sentiment_score": result.sentiment_score,
                "technical_score": result.technical_score,
                "macro_score": result.macro_score,
                "explanation": explanation,
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/scores/{ticker}/explain")
async def get_score_explanation(ticker: str):
    """
    Get detailed score breakdown and explanation for a stock (BUG-005 fix).
    """
    try:
        from data.stock_universe import load_universe
        universe = load_universe()
        if universe:
            valid_tickers = {s["ticker"] for s in universe.get("stocks", [])}
            if ticker.upper() not in valid_tickers:
                raise HTTPException(status_code=404, detail=f"Unknown ticker: {ticker}")

        cached = load_composite_scores()
        if cached and ticker.upper() in cached.get("scores", {}):
            score_data = cached["scores"][ticker.upper()]
            from scoring.composite_score import CompositeScoreResult
            result = CompositeScoreResult(
                ticker=score_data["ticker"],
                sector=score_data["sector"],
                total_score=score_data["total_score"],
                signal=Signal(score_data["signal"]),
                rank=score_data["rank"],
                percentile=score_data["percentile"],
                fundamental_score=score_data["fundamental_score"],
                sentiment_score=score_data["sentiment_score"],
                technical_score=score_data["technical_score"],
                macro_score=score_data["macro_score"],
                score_change=score_data.get("score_change"),
                signal_change=score_data.get("signal_change"),
                details={},
            )
            explanation = explain_score(result)
            return {
                "success": True,
                "data": {
                    "ticker": ticker.upper(),
                    "total_score": result.total_score,
                    "signal": result.signal.value,
                    "explanation": {
                        "summary": explanation.summary,
                        "signal_reason": explanation.signal_reason,
                        "components": explanation.component_breakdown,
                        "strengths": explanation.strengths,
                        "weaknesses": explanation.weaknesses,
                    }
                }
            }

        raise HTTPException(status_code=404, detail=f"Score not found for {ticker}")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/scores/{ticker}/history")
async def get_score_history(ticker: str):
    """
    Get score history for a stock (BUG-016 fix).
    Returns available pipeline run scores for the ticker.
    """
    try:
        from pathlib import Path
        import json
        
        logs_dir = Path("data/pipeline_logs")
        history = []
        
        if logs_dir.exists():
            for log_file in sorted(logs_dir.glob("run_*.json"), reverse=True)[:20]:
                try:
                    with open(log_file) as f:
                        run = json.load(f)
                    run_date = run.get("started_at", log_file.stem.replace("run_", ""))
                    history.append({
                        "date": run_date,
                        "run_id": run.get("run_id", log_file.stem),
                    })
                except Exception:
                    pass
        
        # Get current score
        cached = load_composite_scores()
        current_score = None
        if cached and ticker.upper() in cached.get("scores", {}):
            current_score = cached["scores"][ticker.upper()]
        
        # Build history with current score repeated (single pipeline so far)
        score_history = []
        if current_score:
            for entry in history[:10]:
                score_history.append({
                    "date": entry["date"],
                    "total_score": current_score["total_score"],
                    "signal": current_score["signal"],
                    "fundamental_score": current_score["fundamental_score"],
                    "sentiment_score": current_score["sentiment_score"],
                    "technical_score": current_score["technical_score"],
                    "macro_score": current_score["macro_score"],
                })
        
        return {
            "success": True,
            "data": {
                "ticker": ticker.upper(),
                "count": len(score_history),
                "history": score_history,
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/scores/top/{n}")
async def get_top_n_scores(
    n: int,
    signal: str = Query("BUY", description="Signal filter: BUY, HOLD, SELL, or ALL"),
):
    """
    Get top N stocks by score.
    """
    try:
        cached = load_composite_scores()
        
        if cached is None:
            return {
                "success": False,
                "error": "No scores available. Run the pipeline first.",
            }
        
        scores_data = cached.get("scores", {})
        results = list(scores_data.values())
        
        # Filter by signal
        if signal.upper() != "ALL":
            results = [s for s in results if s.get("signal") == signal.upper()]
        
        # Sort and limit
        results.sort(key=lambda x: x.get("total_score", 0), reverse=True)
        results = results[:n]
        
        return {
            "success": True,
            "count": len(results),
            "signal_filter": signal.upper(),
            "scores": results,
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/scores/calculate")
async def calculate_all_scores(background_tasks: BackgroundTasks):
    """
    Trigger score calculation for all stocks (runs in background).
    """
    try:
        calc_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        def run_scoring():
            try:
                # BUG-022 fix: load previous scores for change tracking
                from scoring.signal_tracker import load_previous_scores, save_previous_scores
                prev = load_previous_scores()
                # Save current as previous before recalculating
                current = load_composite_scores()
                if current:
                    save_previous_scores(current)
                prev_scores = prev.get("scores", {}) if prev else {}
                scores = calculate_composite_scores(previous_scores=prev_scores)
                save_composite_scores(scores)
            except Exception as e:
                print(f"Scoring failed: {e}")
        
        background_tasks.add_task(run_scoring)
        
        return {
            "success": True,
            "message": "Score calculation started",
            "calc_id": calc_id,
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ========== Portfolio Endpoints (F6.2) ==========

@app.get("/api/v1/portfolio")
async def get_portfolio_endpoint(
    user=Depends(get_required_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Get portfolio summary and holdings (per-user).
    """
    try:
        user_id = user.id if user else ANONYMOUS_USER_ID
        data = await UserTradingService.get_portfolio_data(db, user_id)
        
        return {
            "success": True,
            "data": data,
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/portfolio/summary")
async def get_portfolio_summary(
    user=Depends(get_required_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Get portfolio summary (total value, P&L) — per-user.
    """
    try:
        user_id = user.id if user else ANONYMOUS_USER_ID
        summary = await UserTradingService.get_portfolio_summary(db, user_id)
        
        return {
            "success": True,
            "data": summary,
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/portfolio/holdings")
async def get_portfolio_holdings(
    user=Depends(get_required_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Get all portfolio holdings with current values — per-user.
    """
    try:
        user_id = user.id if user else ANONYMOUS_USER_ID
        holdings = await UserTradingService.get_portfolio_holdings(db, user_id)
        
        return {
            "success": True,
            "count": len(holdings),
            "data": holdings,
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/portfolio/reset")
async def reset_portfolio_endpoint(
    starting_cash: float = Query(100000.0, description="Starting cash amount"),
    user=Depends(get_required_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Reset paper trading portfolio (per-user).
    
    Clears all positions and resets cash to starting amount.
    """
    try:
        user_id = user.id if user else ANONYMOUS_USER_ID
        portfolio = await UserTradingService.reset_portfolio(db, user_id, starting_cash)
        
        # DB is single source of truth — no in-memory reset needed (BUG-002 fix)
        
        return {
            "success": True,
            "message": "Portfolio reset successfully",
            "data": {
                "cash": portfolio.cash_balance,
                "starting_cash": portfolio.starting_cash,
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ========== F7.2 Portfolio History Endpoints ==========

@app.get("/api/v1/portfolio/history")
async def get_portfolio_history_endpoint(
    days: int = Query(30, ge=1, le=365, description="Number of days of history")
):
    """
    F7.2: Get portfolio value history for charting.
    """
    try:
        history = get_portfolio_history()
        data = history.get_history(days)
        
        return {
            "success": True,
            "count": len(data),
            "days": days,
            "data": data,
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/portfolio/performance")
async def get_portfolio_performance(
    days: int = Query(30, ge=1, le=365, description="Performance period in days")
):
    """
    F7.2: Get portfolio performance metrics.
    """
    try:
        history = get_portfolio_history()
        performance = history.get_performance(days)
        
        return {
            "success": True,
            "data": performance,
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/portfolio/snapshot")
async def record_portfolio_snapshot(
    user=Depends(get_required_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Record a portfolio snapshot for history tracking.
    
    Call this periodically (e.g., daily) to build history.
    Uses in-memory history store (TODO: migrate to DB-backed history).
    """
    try:
        user_id = user.id if user else ANONYMOUS_USER_ID
        data = await UserTradingService.get_portfolio_data(db, user_id)
        summary = data["summary"]
        
        # Record into file-based history (backward compat — DB history TBD)
        from trading.portfolio import PortfolioSnapshot
        history = get_portfolio_history()
        snapshot = PortfolioSnapshot(
            timestamp=datetime.now().isoformat(),
            total_value=summary["total_value"],
            cash=summary["cash"],
            positions_value=summary["invested"],
            total_pnl=summary["total_pnl"],
            total_pnl_percent=summary["total_pnl_percent"],
        )
        history.snapshots.append(snapshot)
        history.snapshots = history.snapshots[-365:]
        history._save()
        
        return {
            "success": True,
            "message": "Snapshot recorded",
            "total_snapshots": len(history.snapshots),
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ========== F7.3 Sector Allocation Endpoint ==========

@app.get("/api/v1/portfolio/sectors")
async def get_portfolio_sectors(
    user=Depends(get_required_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    F7.3: Get portfolio sector allocation — per-user.
    """
    try:
        user_id = user.id if user else ANONYMOUS_USER_ID
        allocation = await UserTradingService.get_portfolio_sectors(db, user_id)
        
        return {
            "success": True,
            "count": len(allocation),
            "data": allocation,
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ========== Order Endpoints (F6.1, F6.4) ==========

class OrderRequest(BaseModel):
    ticker: str
    side: str  # BUY or SELL
    quantity: float
    order_type: str = "MARKET"  # MARKET or LIMIT
    limit_price: Optional[float] = None


@app.post("/api/v1/orders")
async def create_order(
    request: OrderRequest,
    user=Depends(get_required_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Create a new order (per-user).
    
    For paper trading, market orders execute immediately.
    
    REC-127: Position limits enforced based on user's portfolio_size setting.
    """
    import json as json_module
    
    try:
        user_id = user.id if user else ANONYMOUS_USER_ID
        
        # REC-127: Get user's portfolio_size from settings
        portfolio_size = "medium"  # default
        if user and user.settings_json:
            try:
                settings = json_module.loads(user.settings_json)
                portfolio_size = settings.get("portfolio_size", "medium")
            except (json_module.JSONDecodeError, TypeError):
                pass
        
        order = await UserTradingService.create_order(
            db=db,
            user_id=user_id,
            ticker=request.ticker,
            side=request.side,
            quantity=request.quantity,
            order_type=request.order_type,
            limit_price=request.limit_price,
            portfolio_size=portfolio_size,  # REC-127
        )
        
        # DB is single source of truth — no in-memory dual-write (BUG-002 fix)
        
        return {
            "success": True,
            "data": order.to_dict(),
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/orders")
async def get_orders(
    status: Optional[str] = Query(None, description="Filter by status: PENDING, FILLED, CANCELLED"),
    ticker: Optional[str] = Query(None, description="Filter by ticker"),
    limit: int = Query(50, ge=1, le=1000),
    user=Depends(get_required_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Get orders with optional filters (per-user).
    """
    try:
        user_id = user.id if user else ANONYMOUS_USER_ID
        
        orders = await UserTradingService.get_orders(
            db=db,
            user_id=user_id,
            status=status,
            ticker=ticker,
            limit=limit,
        )
        
        return {
            "success": True,
            "count": len(orders),
            "data": [o.to_dict() for o in orders],
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/orders/today")
async def get_todays_orders(
    user=Depends(get_required_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Get today's orders (per-user).
    """
    try:
        user_id = user.id if user else ANONYMOUS_USER_ID
        orders = await UserTradingService.get_todays_orders(db, user_id)
        
        return {
            "success": True,
            "count": len(orders),
            "data": [o.to_dict() for o in orders],
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/orders/pending")
async def get_pending_orders(
    user=Depends(get_required_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Get all pending orders — per-user.
    """
    try:
        user_id = user.id if user else ANONYMOUS_USER_ID
        orders = await UserTradingService.get_pending_orders(db, user_id)
        
        return {
            "success": True,
            "count": len(orders),
            "data": [o.to_dict() for o in orders],
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/orders/{order_id}")
async def get_order_by_id(
    order_id: str,
    user=Depends(get_required_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Get a specific order by ID — per-user.
    """
    try:
        user_id = user.id if user else ANONYMOUS_USER_ID
        order = await UserTradingService.get_order_by_id(db, user_id, order_id)
        
        if order is None:
            raise HTTPException(status_code=404, detail=f"Order not found: {order_id}")
        
        return {
            "success": True,
            "data": order.to_dict(),
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/v1/orders/{order_id}")
async def cancel_order(
    order_id: str,
    user=Depends(get_required_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Cancel a pending order (per-user).
    """
    try:
        user_id = user.id if user else ANONYMOUS_USER_ID
        order = await UserTradingService.cancel_order(db, user_id, order_id)
        
        return {
            "success": True,
            "message": "Order cancelled",
            "data": order.to_dict(),
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ========== F4.4 Alerts Endpoints ==========

@app.get("/api/v1/alerts")
async def get_alerts(
    limit: int = Query(20, ge=1, le=100, description="Number of alerts"),
    ticker: Optional[str] = Query(None, description="Filter by ticker"),
    unread: bool = Query(False, description="Only unread alerts"),
):
    """
    F4.4: Get recent alerts.
    """
    try:
        manager = get_alert_manager()
        alerts = manager.get_alerts(limit=limit, ticker=ticker, unread_only=unread)
        
        return {
            "success": True,
            "count": len(alerts),
            "data": [a.to_dict() for a in alerts],
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/alerts/recent")
async def get_recent_alerts(
    hours: int = Query(24, ge=1, le=168, description="Hours to look back")
):
    """
    Get alerts from the last N hours.
    """
    try:
        manager = get_alert_manager()
        alerts = manager.get_recent_alerts(hours=hours)
        
        return {
            "success": True,
            "count": len(alerts),
            "data": [a.to_dict() for a in alerts],
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/alerts/{alert_id}/read")
async def mark_alert_read(alert_id: str):
    """
    Mark an alert as read.
    """
    try:
        manager = get_alert_manager()
        success = manager.mark_read(alert_id)
        
        if not success:
            raise HTTPException(status_code=404, detail=f"Alert not found: {alert_id}")
        
        return {"success": True, "message": "Alert marked as read"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/alerts/read-all")
async def mark_all_alerts_read():
    """
    Mark all alerts as read.
    """
    try:
        manager = get_alert_manager()
        manager.mark_all_read()
        
        return {"success": True, "message": "All alerts marked as read"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ========== Run ==========

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
