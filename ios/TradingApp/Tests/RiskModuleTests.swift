import XCTest
@testable import Sigil

/// REC-230, REC-231: Risk Module Tests
/// Tests for Portfolio Risk Badge and Position Stop Distance functionality
final class RiskModuleTests: XCTestCase {
    
    /// Decoder for API responses that use snake_case keys
    /// Note: Models with explicit CodingKeys handle their own key mapping
    private let decoder: JSONDecoder = {
        let d = JSONDecoder()
        d.keyDecodingStrategy = .convertFromSnakeCase
        return d
    }()
    
    /// Raw decoder for models with explicit CodingKeys (like RiskSettingsData)
    private let rawDecoder = JSONDecoder()
    
    // MARK: - Helpers
    
    private func decode<T: Decodable>(_ type: T.Type, from json: String, file: StaticString = #file, line: UInt = #line) throws -> T {
        let data = json.data(using: .utf8)!
        return try decoder.decode(type, from: data)
    }
    
    /// Decode using raw decoder (for models with explicit CodingKeys)
    private func decodeRaw<T: Decodable>(_ type: T.Type, from json: String, file: StaticString = #file, line: UInt = #line) throws -> T {
        let data = json.data(using: .utf8)!
        return try rawDecoder.decode(type, from: data)
    }
    
    // MARK: - REC-230: Portfolio Risk Score Tests
    
    func testRiskScoreEnum() throws {
        // Test enum raw values and colors
        XCTAssertEqual(RiskScore.low.rawValue, "low")
        XCTAssertEqual(RiskScore.medium.rawValue, "medium")
        XCTAssertEqual(RiskScore.high.rawValue, "high")
        
        // Labels
        XCTAssertEqual(RiskScore.low.label, "Low")
        XCTAssertEqual(RiskScore.medium.label, "Medium")
        XCTAssertEqual(RiskScore.high.label, "High")
    }
    
    func testPortfolioRiskResponseDecode_LowRisk() throws {
        // Note: PortfolioRiskData uses explicit CodingKeys, so use rawDecoder
        let json = """
        {
            "success": true,
            "data": {
                "total_value": 50000.0,
                "var_95_daily": 1500.0,
                "var_95_pct": 0.03,
                "var_99_daily": 2000.0,
                "var_99_pct": 0.04,
                "risk_score": "low",
                "position_vars": [],
                "correlation_benefit": 0.2,
                "calculated_at": "2026-02-10T12:00:00"
            }
        }
        """
        let response = try decodeRaw(PortfolioRiskAPIResponse.self, from: json)
        XCTAssertTrue(response.success)
        XCTAssertNotNil(response.data)
        XCTAssertEqual(response.data?.riskScore, "low")
        XCTAssertEqual(response.data?.var95Pct, 0.03)
        XCTAssertEqual(response.data?.totalValue, 50000.0)
    }
    
    func testPortfolioRiskResponseDecode_HighRisk() throws {
        // Note: PortfolioRiskData uses explicit CodingKeys, so use rawDecoder
        let json = """
        {
            "success": true,
            "data": {
                "total_value": 50000.0,
                "var_95_daily": 6000.0,
                "var_95_pct": 0.12,
                "var_99_daily": 8000.0,
                "var_99_pct": 0.16,
                "risk_score": "high",
                "position_vars": [
                    {
                        "ticker": "TSLA",
                        "position_value": 25000.0,
                        "var_95_daily": 4000.0,
                        "var_95_pct": 0.16,
                        "daily_volatility": 0.03,
                        "annualized_volatility": 0.48
                    }
                ],
                "correlation_benefit": 0.1,
                "calculated_at": "2026-02-10T12:00:00"
            }
        }
        """
        let response = try decodeRaw(PortfolioRiskAPIResponse.self, from: json)
        XCTAssertTrue(response.success)
        XCTAssertEqual(response.data?.riskScore, "high")
        XCTAssertEqual(response.data?.positionVars?.count, 1)
        XCTAssertEqual(response.data?.positionVars?.first?.ticker, "TSLA")
    }
    
    func testPortfolioRiskResponseDecode_EmptyPortfolio() throws {
        // Note: PortfolioRiskData uses explicit CodingKeys, so use rawDecoder
        let json = """
        {
            "success": true,
            "data": {
                "total_value": 0,
                "var_95_daily": 0,
                "var_95_pct": 0,
                "var_99_daily": 0,
                "var_99_pct": 0,
                "risk_score": "low",
                "position_vars": [],
                "correlation_benefit": 0,
                "calculated_at": "2026-02-10T12:00:00",
                "message": "No positions in portfolio"
            }
        }
        """
        let response = try decodeRaw(PortfolioRiskAPIResponse.self, from: json)
        XCTAssertTrue(response.success)
        XCTAssertEqual(response.data?.riskScore, "low")
        XCTAssertEqual(response.data?.message, "No positions in portfolio")
    }
    
    // MARK: - REC-231: Risk Settings Tests
    
    func testRiskSettingsResponseDecode() throws {
        // Note: RiskSettingsData uses .convertFromSnakeCase decoder
        let json = """
        {
            "success": true,
            "data": {
                "user_id": "user-123",
                "hard_stop": {
                    "enabled": true,
                    "threshold_pct": -0.08
                },
                "trailing_stop": {
                    "enabled": true,
                    "distance_pct": -0.10
                },
                "vix_adjustment": {
                    "enabled": false
                },
                "position_limit": {
                    "enabled": true,
                    "max_pct": 0.15
                }
            }
        }
        """
        let response = try decode(RiskSettingsAPIResponse.self, from: json)
        XCTAssertTrue(response.success)
        XCTAssertNotNil(response.data)
        XCTAssertEqual(response.data?.hardStop.enabled, true)
        XCTAssertEqual(response.data?.hardStop.thresholdPct, -0.08)
        XCTAssertEqual(response.data?.trailingStop.enabled, true)
        XCTAssertEqual(response.data?.trailingStop.distancePct, -0.10)
        XCTAssertEqual(response.data?.vixAdjustment.enabled, false)
        XCTAssertEqual(response.data?.positionLimit.enabled, true)
        XCTAssertEqual(response.data?.positionLimit.maxPct, 0.15)
    }
    
    func testRiskSettingsResponseDecode_AllDefaults() throws {
        // Note: RiskSettingsData uses .convertFromSnakeCase decoder
        let json = """
        {
            "success": true,
            "data": {
                "hard_stop": {
                    "enabled": false,
                    "threshold_pct": -0.08
                },
                "trailing_stop": {
                    "enabled": false,
                    "distance_pct": -0.10
                },
                "vix_adjustment": {
                    "enabled": false
                },
                "position_limit": {
                    "enabled": false,
                    "max_pct": 0.15
                }
            }
        }
        """
        let response = try decode(RiskSettingsAPIResponse.self, from: json)
        XCTAssertTrue(response.success)
        XCTAssertEqual(response.data?.hardStop.enabled, false)
        XCTAssertEqual(response.data?.trailingStop.enabled, false)
    }
    
    // MARK: - Stop Distance Calculation Tests
    
    func testStopDistanceColorThresholds() {
        // Test StopDistanceView colors based on distance
        // Within 1% = red, within 2% = yellow, > 2% = green
        
        // Distance of -0.5% (within 1%) should be red
        let closeStop = StopDistanceView(
            stopPrice: 99.5,
            stopDistancePercent: -0.5,
            stopType: .hard
        )
        XCTAssertEqual(closeStop.distanceColor, .Signal.sell)
        
        // Distance of -1.5% (within 2%) should be yellow  
        let mediumStop = StopDistanceView(
            stopPrice: 98.5,
            stopDistancePercent: -1.5,
            stopType: .hard
        )
        XCTAssertEqual(mediumStop.distanceColor, .Accent.gold)
        
        // Distance of -5% (far) should be green
        let farStop = StopDistanceView(
            stopPrice: 95.0,
            stopDistancePercent: -5.0,
            stopType: .trailing
        )
        XCTAssertEqual(farStop.distanceColor, .Signal.buy)
    }
    
    // MARK: - Integration: PositionVar Decode
    
    func testPositionVarDataDecode() throws {
        // Note: PositionVarData uses explicit CodingKeys, so use rawDecoder
        let json = """
        {
            "ticker": "AAPL",
            "position_value": 10000.0,
            "var_95_daily": 250.0,
            "var_95_pct": 0.025,
            "daily_volatility": 0.015,
            "annualized_volatility": 0.24
        }
        """
        let posVar = try decodeRaw(PositionVarData.self, from: json)
        XCTAssertEqual(posVar.ticker, "AAPL")
        XCTAssertEqual(posVar.positionValue, 10000.0)
        XCTAssertEqual(posVar.var95Daily, 250.0)
        XCTAssertEqual(posVar.var95Pct, 0.025)
    }
}
