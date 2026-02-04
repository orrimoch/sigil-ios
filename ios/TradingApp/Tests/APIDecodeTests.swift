import XCTest
@testable import Sigil

/// Tests that iOS Codable models can decode real API responses.
/// Feeds actual JSON (matching backend output) into Swift decoders.
/// Catches field mismatches, missing keys, and type errors BEFORE they hit users.
final class APIDecodeTests: XCTestCase {

    private let decoder: JSONDecoder = {
        let d = JSONDecoder()
        d.keyDecodingStrategy = .convertFromSnakeCase
        return d
    }()

    // MARK: - Helpers

    private func decode<T: Decodable>(_ type: T.Type, from json: String, file: StaticString = #file, line: UInt = #line) throws -> T {
        let data = json.data(using: .utf8)!
        return try decoder.decode(type, from: data)
    }

    // MARK: - Portfolio (the one that broke)

    func testPortfolioResponseDecode() throws {
        let json = """
        {
            "success": true,
            "data": {
                "summary": {
                    "total_value": 100000.0,
                    "cash": 97307.9,
                    "invested": 2692.1,
                    "positions_value": 2692.1,
                    "total_pnl": 0.0,
                    "total_pnl_percent": 0.0,
                    "daily_pnl": 0.0,
                    "daily_pnl_percent": 0.0,
                    "starting_cash": 100000.0,
                    "position_count": 1,
                    "positions_count": 1
                },
                "holdings": [
                    {
                        "id": "abc-123",
                        "portfolio_id": "port-1",
                        "ticker": "AAPL",
                        "quantity": 10.0,
                        "shares": 10.0,
                        "avg_cost": 269.21,
                        "cost_basis": 2692.1,
                        "opened_at": "2026-02-04T09:38:45.545619",
                        "current_price": 269.21,
                        "market_value": 2692.1,
                        "unrealized_pnl": 0.0,
                        "unrealized_pnl_percent": 0.0
                    }
                ],
                "is_paper": true,
                "realized_pnl": 0.0
            }
        }
        """
        let response = try decode(PortfolioResponse.self, from: json)
        XCTAssertTrue(response.success)
        XCTAssertEqual(response.data.holdings.count, 1)
        XCTAssertEqual(response.data.holdings[0].ticker, "AAPL")
        XCTAssertEqual(response.data.holdings[0].shares, 10.0)
        XCTAssertEqual(response.data.holdings[0].currentPrice, 269.21)
        XCTAssertEqual(response.data.holdings[0].costBasis, 2692.1)
        XCTAssertEqual(response.data.summary.positionsCount, 1)
        XCTAssertEqual(response.data.summary.positionsValue, 2692.1)
        XCTAssertTrue(response.data.isPaper)
    }

    func testPortfolioHoldingNullFieldsCrash() throws {
        // This is the EXACT scenario that caused the bug:
        // A holding with null current_price/market_value
        let json = """
        {
            "success": true,
            "data": {
                "summary": {
                    "total_value": 100000.0,
                    "cash": 99000.0,
                    "invested": 1000.0,
                    "positions_value": 1000.0,
                    "total_pnl": 0.0,
                    "total_pnl_percent": 0.0,
                    "daily_pnl": 0.0,
                    "daily_pnl_percent": 0.0,
                    "starting_cash": 100000.0,
                    "position_count": 1,
                    "positions_count": 1
                },
                "holdings": [
                    {
                        "id": "bad-id",
                        "portfolio_id": "port-1",
                        "ticker": "INVALID",
                        "quantity": 10.0,
                        "shares": 10.0,
                        "avg_cost": 100.0,
                        "cost_basis": 1000.0,
                        "opened_at": "2026-02-04T09:38:48",
                        "current_price": null,
                        "market_value": null,
                        "unrealized_pnl": null,
                        "unrealized_pnl_percent": null
                    }
                ],
                "is_paper": true,
                "realized_pnl": 0.0
            }
        }
        """
        // This SHOULD fail because Holding has non-optional Double fields
        XCTAssertThrowsError(try decode(PortfolioResponse.self, from: json)) { error in
            // Confirm it's a decode error, not a runtime crash
            XCTAssertTrue(error is DecodingError, "Expected DecodingError, got \(type(of: error))")
        }
    }

    func testPortfolioEmptyHoldings() throws {
        let json = """
        {
            "success": true,
            "data": {
                "summary": {
                    "total_value": 100000.0,
                    "cash": 100000.0,
                    "invested": 0.0,
                    "positions_value": 0.0,
                    "total_pnl": 0.0,
                    "total_pnl_percent": 0.0,
                    "daily_pnl": 0.0,
                    "daily_pnl_percent": 0.0,
                    "starting_cash": 100000.0,
                    "position_count": 0,
                    "positions_count": 0
                },
                "holdings": [],
                "is_paper": true,
                "realized_pnl": 0.0
            }
        }
        """
        let response = try decode(PortfolioResponse.self, from: json)
        XCTAssertEqual(response.data.holdings.count, 0)
        XCTAssertEqual(response.data.summary.cash, 100000.0)
    }

    // MARK: - Scores

    func testScoresResponseDecode() throws {
        let json = """
        {
            "success": true,
            "count": 1,
            "scores": [
                {
                    "ticker": "MCHP",
                    "company_name": "Microchip Technology",
                    "sector": "Technology",
                    "total_score": 92.32,
                    "signal": "BUY",
                    "rank": 1,
                    "percentile": 100.0,
                    "fundamental_score": 71.06,
                    "sentiment_score": 53.4,
                    "technical_score": 77.13,
                    "macro_score": 69.7,
                    "score_change": null,
                    "signal_change": null,
                    "price": 77.98,
                    "price_change": 1.32,
                    "price_change_percent": 1.73
                }
            ]
        }
        """
        let response = try decode(ScoresResponse.self, from: json)
        XCTAssertEqual(response.count, 1)
        XCTAssertEqual(response.scores[0].ticker, "MCHP")
        XCTAssertEqual(response.scores[0].totalScore, 92.32)
        XCTAssertEqual(response.scores[0].signal, "BUY")
        XCTAssertEqual(response.scores[0].companyName, "Microchip Technology")
    }

    func testScoreWithNullPriceFields() throws {
        // price, priceChange, priceChangePercent can be null
        let json = """
        {
            "success": true,
            "count": 1,
            "scores": [
                {
                    "ticker": "TEST",
                    "company_name": null,
                    "sector": "Tech",
                    "total_score": 50.0,
                    "signal": "HOLD",
                    "rank": 100,
                    "percentile": 50.0,
                    "fundamental_score": 50.0,
                    "sentiment_score": 50.0,
                    "technical_score": 50.0,
                    "macro_score": 50.0,
                    "score_change": null,
                    "signal_change": null,
                    "price": null,
                    "price_change": null,
                    "price_change_percent": null
                }
            ]
        }
        """
        let response = try decode(ScoresResponse.self, from: json)
        XCTAssertNil(response.scores[0].price)
        XCTAssertNil(response.scores[0].companyName)
    }

    // MARK: - Orders

    func testOrdersResponseDecode() throws {
        let json = """
        {
            "success": true,
            "count": 1,
            "data": [
                {
                    "order_id": "abc123",
                    "ticker": "AAPL",
                    "side": "BUY",
                    "order_type": "MARKET",
                    "quantity": 10.0,
                    "limit_price": null,
                    "status": "FILLED",
                    "filled_quantity": 10.0,
                    "filled_price": 269.21,
                    "created_at": "2026-02-04T09:38:45",
                    "updated_at": "2026-02-04T09:38:45",
                    "filled_at": "2026-02-04T09:38:45",
                    "reject_reason": null,
                    "is_paper": true
                }
            ]
        }
        """
        let response = try decode(OrdersResponse.self, from: json)
        XCTAssertEqual(response.count, 1)
        XCTAssertEqual(response.data[0].ticker, "AAPL")
        XCTAssertEqual(response.data[0].status, "FILLED")
        XCTAssertEqual(response.data[0].orderId, "abc123")
    }

    // MARK: - Alerts

    func testAlertsResponseDecode() throws {
        let json = """
        {
            "success": true,
            "count": 1,
            "data": [
                {
                    "id": "alert-1",
                    "type": "score_change",
                    "ticker": "AAPL",
                    "title": "Score increased +5 pts",
                    "subtitle": "Now rated BUY (85)",
                    "timestamp": "2026-02-04T10:00:00",
                    "read": false
                }
            ]
        }
        """
        let response = try decode(AlertsResponse.self, from: json)
        XCTAssertEqual(response.data[0].title, "Score increased +5 pts")
    }

    // MARK: - Market Indices

    func testMarketIndicesResponseDecode() throws {
        let json = """
        {
            "success": true,
            "count": 4,
            "indices": [
                {"symbol": "SPX", "name": "S&P 500", "value": 6881.01, "change": -36.8, "change_percent": -0.53},
                {"symbol": "IXIC", "name": "NASDAQ", "value": 22890.15, "change": -365.04, "change_percent": -1.57},
                {"symbol": "DJI", "name": "DOW", "value": 49492.4, "change": 251.41, "change_percent": 0.51},
                {"symbol": "VIX", "name": "VIX", "value": 19.43, "change": 1.43, "change_percent": 7.94}
            ]
        }
        """
        let response = try decode(MarketIndicesResponse.self, from: json)
        XCTAssertEqual(response.count, 4)
        XCTAssertEqual(response.indices[0].symbol, "SPX")
    }

    // MARK: - Portfolio History

    func testPortfolioHistoryDecode() throws {
        let json = """
        {
            "success": true,
            "count": 0,
            "days": 30,
            "data": []
        }
        """
        let response = try decode(PortfolioHistoryResponse.self, from: json)
        XCTAssertEqual(response.days, 30)
        XCTAssertEqual(response.data.count, 0)
    }

    // MARK: - Portfolio Performance

    func testPortfolioPerformanceDecode() throws {
        let json = """
        {
            "success": true,
            "data": {
                "period_days": 30,
                "start_value": null,
                "end_value": null,
                "change": null,
                "change_percent": null,
                "data_points": null
            }
        }
        """
        let response = try decode(PortfolioPerformanceResponse.self, from: json)
        XCTAssertEqual(response.data.periodDays, 30)
        XCTAssertNil(response.data.startValue)
    }

    // MARK: - Sector Allocation

    func testSectorAllocationDecode() throws {
        let json = """
        {
            "success": true,
            "count": 1,
            "data": [
                {"sector": "Technology", "value": 2692.1, "percentage": 100.0}
            ]
        }
        """
        let response = try decode(SectorAllocationResponse.self, from: json)
        XCTAssertEqual(response.data[0].sector, "Technology")
    }

    // MARK: - ISO8601 Date Parsing (BUG-027)

    func testISO8601DateParsingVariants() {
        let formatter = ISO8601DateFormatter()

        // With fractional seconds
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        XCTAssertNotNil(formatter.date(from: "2026-02-04T09:38:45.545619+00:00"))

        // Without fractional seconds — this used to fail
        formatter.formatOptions = [.withInternetDateTime]
        XCTAssertNotNil(formatter.date(from: "2026-02-04T09:38:45+00:00"))

        // Basic format from Python datetime.isoformat() without timezone
        let basic = DateFormatter()
        basic.dateFormat = "yyyy-MM-dd'T'HH:mm:ss"
        basic.timeZone = TimeZone(identifier: "UTC")
        XCTAssertNotNil(basic.date(from: "2026-02-04T09:38:45"))
    }
}
