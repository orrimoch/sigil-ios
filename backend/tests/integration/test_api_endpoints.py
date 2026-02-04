"""
Integration tests: Hit every API endpoint and validate responses match iOS Codable models.

These tests require the backend to be running on localhost:8000.
They verify:
1. Every endpoint returns 200 (or expected status)
2. Response JSON has all fields the iOS app expects
3. Field types match (int, float, string, bool, list, null/optional)
4. snake_case keys convert correctly to camelCase for iOS

Run: cd backend && python3 -m pytest tests/integration/ -v --tb=short
Requires: Backend running on http://127.0.0.1:8000
"""

import pytest
import requests
import json
from typing import Any, Optional

BASE_URL = "http://127.0.0.1:8000/api/v1"


def _get(path: str, params: dict = None) -> dict:
    """GET request, return parsed JSON."""
    url = f"{BASE_URL}{path}"
    resp = requests.get(url, params=params, timeout=15)
    assert resp.status_code == 200, f"{path} returned {resp.status_code}: {resp.text[:200]}"
    return resp.json()


def _post(path: str, json_body: dict = None, params: dict = None) -> tuple:
    """POST request, return (status_code, parsed JSON)."""
    url = f"{BASE_URL}{path}"
    resp = requests.post(url, json=json_body, params=params, timeout=15)
    return resp.status_code, resp.json()


def _assert_fields(data: dict, required: dict, context: str = ""):
    """
    Validate that `data` has all required fields with correct types.
    required: {"field_name": type} where type is int, float, str, bool, list, dict, or None for optional.
    Field names should be snake_case (as returned by the API).
    """
    for field, expected_type in required.items():
        assert field in data, f"{context}: missing field '{field}'. Keys: {list(data.keys())}"
        if expected_type is not None and data[field] is not None:
            if expected_type == float:
                # Accept int or float for numeric fields
                assert isinstance(data[field], (int, float)), \
                    f"{context}: '{field}' expected number, got {type(data[field]).__name__} = {data[field]}"
            else:
                assert isinstance(data[field], expected_type), \
                    f"{context}: '{field}' expected {expected_type.__name__}, got {type(data[field]).__name__} = {data[field]}"


# ========== Health ==========

class TestHealth:
    def test_health(self):
        data = _get("/health")
        assert data["status"] == "ok"

    def test_health_alias(self):
        """iOS hits /health for connectivity check."""
        data = _get("/health")
        _assert_fields(data, {"status": str}, "health")


# ========== Stocks ==========

class TestStocks:
    """iOS: StocksResponse { success, count, stocks: [Stock] }"""

    def test_stocks_list(self):
        data = _get("/stocks", {"limit": 5})
        _assert_fields(data, {"success": bool, "count": int, "stocks": list}, "stocks")
        assert len(data["stocks"]) > 0

    def test_stock_fields(self):
        """iOS Stock: ticker, name, sector, industry, marketCap"""
        data = _get("/stocks", {"limit": 1})
        stock = data["stocks"][0]
        _assert_fields(stock, {
            "ticker": str,
            "name": str,
            "sector": str,
            "industry": str,
            "market_cap": int,
        }, "Stock")


# ========== Scores ==========

class TestScores:
    """iOS: ScoresResponse { success, count, scores: [StockScore] }"""

    def test_scores_list(self):
        data = _get("/scores", {"limit": 5})
        _assert_fields(data, {"success": bool, "count": int, "scores": list}, "scores")
        assert len(data["scores"]) > 0

    def test_score_fields(self):
        """iOS StockScore: ticker, sector, totalScore, signal, rank, percentile, 4 sub-scores"""
        data = _get("/scores", {"limit": 1})
        score = data["scores"][0]
        _assert_fields(score, {
            "ticker": str,
            "sector": str,
            "total_score": float,
            "signal": str,
            "rank": int,
            "percentile": float,
            "fundamental_score": float,
            "sentiment_score": float,
            "technical_score": float,
            "macro_score": float,
        }, "StockScore")
        # Optional price fields (may be null but must exist)
        assert "price" in score, "StockScore missing 'price'"
        assert "price_change" in score, "StockScore missing 'price_change'"
        assert "price_change_percent" in score, "StockScore missing 'price_change_percent'"

    def test_score_single(self):
        """iOS: ScoreDetailResponse — GET /scores/{ticker}"""
        data = _get("/scores", {"limit": 1})
        ticker = data["scores"][0]["ticker"]
        detail = _get(f"/scores/{ticker}")
        _assert_fields(detail, {"success": bool, "data": dict}, f"scores/{ticker}")
        _assert_fields(detail["data"], {
            "ticker": str,
            "total_score": float,
            "signal": str,
        }, "ScoreDetail")

    def test_score_invalid_ticker_404(self):
        """BUG-003: Invalid ticker should return 404, not 200."""
        resp = requests.get(f"{BASE_URL}/scores/ZZZZINVALID", timeout=10)
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"

    def test_score_explain(self):
        """BUG-005: /scores/{ticker}/explain must exist."""
        data = _get("/scores", {"limit": 1})
        ticker = data["scores"][0]["ticker"]
        explain = _get(f"/scores/{ticker}/explain")
        _assert_fields(explain, {"success": bool, "data": dict}, "explain")

    def test_score_history(self):
        """BUG-016: /scores/{ticker}/history must exist."""
        data = _get("/scores", {"limit": 1})
        ticker = data["scores"][0]["ticker"]
        hist = _get(f"/scores/{ticker}/history")
        _assert_fields(hist, {"success": bool, "data": dict}, "score_history")
        _assert_fields(hist["data"], {"ticker": str, "count": int, "history": list}, "score_history.data")

    def test_top_scores(self):
        data = _get("/scores/top/5")
        _assert_fields(data, {"success": bool, "count": int, "scores": list}, "top_scores")


# ========== Prices ==========

class TestPrices:
    """iOS: PriceResponse"""

    def test_price_single(self):
        data = _get("/prices/AAPL")
        _assert_fields(data, {"ticker": str, "price": float}, "price")

    def test_price_history(self):
        """BUG-007: /prices/{ticker}/history must exist."""
        data = _get("/prices/AAPL/history", {"period": "1m"})
        _assert_fields(data, {"success": bool, "data": dict}, "price_history")
        _assert_fields(data["data"], {
            "ticker": str,
            "period": str,
            "count": int,
            "prices": list,
        }, "price_history.data")
        if data["data"]["count"] > 0:
            point = data["data"]["prices"][0]
            _assert_fields(point, {
                "date": str,
                "open": float,
                "high": float,
                "low": float,
                "close": float,
                "volume": int,
            }, "PricePoint")

    def test_price_history_alias(self):
        """BUG-017: /data/price-history/{ticker} alias for iOS."""
        data = _get("/data/price-history/AAPL", {"period": "1m"})
        _assert_fields(data, {"success": bool, "data": dict}, "price_history_alias")


# ========== Portfolio ==========

class TestPortfolio:
    """
    iOS: PortfolioResponse { success, data: PortfolioData }
    PortfolioData { summary, holdings, isPaper, realizedPnl }
    This is the critical path that was broken.
    """

    def test_portfolio_response_structure(self):
        data = _get("/portfolio")
        _assert_fields(data, {"success": bool, "data": dict}, "portfolio")

    def test_portfolio_data_fields(self):
        """PortfolioData: summary, holdings, is_paper, realized_pnl"""
        data = _get("/portfolio")["data"]
        _assert_fields(data, {
            "summary": dict,
            "holdings": list,
            "is_paper": bool,
            "realized_pnl": float,
        }, "PortfolioData")

    def test_portfolio_summary_fields(self):
        """PortfolioSummary: all fields iOS expects (non-optional)."""
        summary = _get("/portfolio")["data"]["summary"]
        _assert_fields(summary, {
            "total_value": float,
            "cash": float,
            "positions_value": float,
            "total_pnl": float,
            "total_pnl_percent": float,
            "daily_pnl": float,
            "daily_pnl_percent": float,
            "positions_count": int,
        }, "PortfolioSummary")

    def test_holding_fields_all_present(self):
        """
        Holding: ALL fields must be non-null.
        This catches the exact bug we had — INVALID ticker with null current_price.
        """
        holdings = _get("/portfolio")["data"]["holdings"]
        for h in holdings:
            _assert_fields(h, {
                "ticker": str,
                "shares": float,
                "avg_cost": float,
                "current_price": float,
                "market_value": float,
                "cost_basis": float,
                "unrealized_pnl": float,
                "unrealized_pnl_percent": float,
                "opened_at": str,
            }, f"Holding({h.get('ticker', '?')})")
            # Critical: none of these can be null (iOS model is non-optional)
            for field in ["current_price", "market_value", "cost_basis",
                          "unrealized_pnl", "unrealized_pnl_percent"]:
                assert h[field] is not None, \
                    f"Holding({h['ticker']}).{field} is null — iOS will crash on decode"

    def test_portfolio_history(self):
        """PortfolioHistoryResponse: success, count, days, data: [PortfolioSnapshot]"""
        data = _get("/portfolio/history", {"days": 30})
        _assert_fields(data, {
            "success": bool,
            "count": int,
            "days": int,
            "data": list,
        }, "PortfolioHistory")

    def test_portfolio_performance(self):
        """PortfolioPerformanceResponse: success, data: PortfolioPerformance"""
        data = _get("/portfolio/performance", {"days": 30})
        _assert_fields(data, {"success": bool, "data": dict}, "PortfolioPerformance")

    def test_portfolio_sectors(self):
        """SectorAllocationResponse: success, count, data: [SectorAllocation]"""
        data = _get("/portfolio/sectors")
        _assert_fields(data, {"success": bool, "count": int, "data": list}, "SectorAllocation")


# ========== Orders ==========

class TestOrders:
    """iOS: OrdersResponse { success, count, data: [OrderData] }"""

    def test_orders_list(self):
        data = _get("/orders")
        _assert_fields(data, {"success": bool, "count": int, "data": list}, "orders")

    def test_order_fields(self):
        """OrderData: all non-optional fields must be present."""
        data = _get("/orders")
        if data["count"] > 0:
            order = data["data"][0]
            # iOS OrderData uses orderId (mapped from order_id)
            _assert_fields(order, {
                "ticker": str,
                "side": str,
                "order_type": str,
                "quantity": float,
                "status": str,
                "filled_quantity": float,
                "created_at": str,
                "updated_at": str,
                "is_paper": bool,
            }, "OrderData")

    def test_create_order_invalid_ticker_rejected(self):
        """BUG-001: Invalid ticker orders must be rejected."""
        status, data = _post("/orders", {
            "ticker": "ZZZZFAKE",
            "side": "BUY",
            "quantity": 1,
            "order_type": "MARKET",
        })
        assert status == 400, f"Expected 400 for invalid ticker, got {status}: {data}"


# ========== Alerts ==========

class TestAlerts:
    """iOS: AlertsResponse { success, count, data: [AlertData] }"""

    def test_alerts_list(self):
        data = _get("/alerts")
        _assert_fields(data, {"success": bool, "count": int, "data": list}, "alerts")

    def test_alert_fields(self):
        """AlertData: id, type, ticker, title, subtitle, timestamp, read"""
        data = _get("/alerts")
        if data["count"] > 0:
            alert = data["data"][0]
            _assert_fields(alert, {
                "id": str,
                "type": str,
                "ticker": str,
                "title": str,
                "subtitle": str,
                "timestamp": str,
                "read": bool,
            }, "AlertData")
            # No placeholder titles
            assert alert["title"] != "Title", \
                f"Alert has placeholder title 'Title' — ticker: {alert['ticker']}"


# ========== Market Indices ==========

class TestMarketIndices:
    """iOS: MarketIndicesResponse { success, count, indices: [MarketIndexData] }"""

    def test_indices(self):
        data = _get("/market/indices")
        _assert_fields(data, {"success": bool, "count": int, "indices": list}, "indices")
        assert data["count"] >= 4, f"Expected at least 4 indices, got {data['count']}"

    def test_index_fields(self):
        data = _get("/market/indices")
        idx = data["indices"][0]
        _assert_fields(idx, {
            "symbol": str,
            "name": str,
            "value": float,
            "change": float,
            "change_percent": float,
        }, "MarketIndexData")


# ========== Macro ==========

class TestMacro:
    """iOS: MacroResponse"""

    def test_macro(self):
        data = _get("/macro")
        _assert_fields(data, {"success": bool, "data": dict}, "macro")

    def test_macro_score_not_shadowed(self):
        """BUG-004: /macro/score must not be shadowed by /macro/{indicator}."""
        data = _get("/macro/score")
        _assert_fields(data, {"success": bool, "data": dict}, "macro_score")


# ========== Pipeline ==========

class TestPipeline:
    """BUG-006: /pipeline/status general endpoint."""

    def test_pipeline_status(self):
        data = _get("/pipeline/status")
        _assert_fields(data, {"success": bool, "data": dict}, "pipeline_status")

    def test_pipeline_latest(self):
        data = _get("/pipeline/latest")
        _assert_fields(data, {"success": bool}, "pipeline_latest")


# ========== Auth ==========

class TestAuth:
    """BUG-008: Password reset must not expose code."""

    def test_password_reset_no_code_leak(self):
        status, data = _post("/auth/password-reset/request", {
            "email": "test@example.com"
        })
        # Should succeed but NOT contain the code
        assert "code" not in data, \
            f"Password reset response leaks the code! Keys: {list(data.keys())}"


# ========== Error Format ==========

class TestErrorFormat:
    """BUG-021: All errors must return consistent {success: false, error: string}."""

    def test_404_format(self):
        resp = requests.get(f"{BASE_URL}/scores/ZZZZINVALID", timeout=10)
        data = resp.json()
        _assert_fields(data, {"success": bool, "error": str}, "404 error")
        assert data["success"] is False

    def test_400_format(self):
        status, data = _post("/orders", {
            "ticker": "ZZZZFAKE",
            "side": "BUY",
            "quantity": 1,
            "order_type": "MARKET",
        })
        _assert_fields(data, {"success": bool, "error": str}, "400 error")
        assert data["success"] is False
