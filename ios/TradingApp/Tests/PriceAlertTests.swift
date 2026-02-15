import XCTest
@testable import Sigil

/// Unit tests for Price Alert models and functionality
final class PriceAlertTests: XCTestCase {
    
    // MARK: - PriceAlertCondition Tests
    
    func testPriceAlertConditionAboveRawValue() {
        let condition = PriceAlertCondition.above
        XCTAssertEqual(condition.rawValue, "ABOVE")
    }
    
    func testPriceAlertConditionBelowRawValue() {
        let condition = PriceAlertCondition.below
        XCTAssertEqual(condition.rawValue, "BELOW")
    }
    
    func testPriceAlertConditionDisplayName() {
        XCTAssertEqual(PriceAlertCondition.above.displayName, "Above")
        XCTAssertEqual(PriceAlertCondition.below.displayName, "Below")
    }
    
    func testPriceAlertConditionIcon() {
        XCTAssertEqual(PriceAlertCondition.above.icon, "arrow.up.circle.fill")
        XCTAssertEqual(PriceAlertCondition.below.icon, "arrow.down.circle.fill")
    }
    
    func testPriceAlertConditionAllCases() {
        XCTAssertEqual(PriceAlertCondition.allCases.count, 2)
        XCTAssertTrue(PriceAlertCondition.allCases.contains(.above))
        XCTAssertTrue(PriceAlertCondition.allCases.contains(.below))
    }
    
    // MARK: - PriceAlert Model Tests
    
    func testPriceAlertDecoding() throws {
        let json = """
        {
            "id": "abc123",
            "user_id": "user1",
            "ticker": "AAPL",
            "condition": "ABOVE",
            "target_price": 200.0,
            "created_at": "2026-02-15T12:00:00Z",
            "triggered_at": null,
            "is_active": true
        }
        """
        
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        
        let alert = try decoder.decode(PriceAlert.self, from: json.data(using: .utf8)!)
        
        XCTAssertEqual(alert.id, "abc123")
        XCTAssertEqual(alert.userId, "user1")
        XCTAssertEqual(alert.ticker, "AAPL")
        XCTAssertEqual(alert.condition, "ABOVE")
        XCTAssertEqual(alert.targetPrice, 200.0)
        XCTAssertTrue(alert.isActive)
        XCTAssertNil(alert.triggeredAt)
    }
    
    func testPriceAlertConditionType() throws {
        let json = """
        {
            "id": "abc123",
            "user_id": "user1",
            "ticker": "AAPL",
            "condition": "BELOW",
            "target_price": 150.0,
            "created_at": "2026-02-15T12:00:00Z",
            "triggered_at": null,
            "is_active": true
        }
        """
        
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        
        let alert = try decoder.decode(PriceAlert.self, from: json.data(using: .utf8)!)
        XCTAssertEqual(alert.conditionType, .below)
    }
    
    func testPriceAlertTriggered() throws {
        let json = """
        {
            "id": "abc123",
            "user_id": "user1",
            "ticker": "AAPL",
            "condition": "ABOVE",
            "target_price": 200.0,
            "created_at": "2026-02-15T12:00:00Z",
            "triggered_at": "2026-02-15T14:30:00Z",
            "is_active": false
        }
        """
        
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        
        let alert = try decoder.decode(PriceAlert.self, from: json.data(using: .utf8)!)
        
        XCTAssertFalse(alert.isActive)
        XCTAssertNotNil(alert.triggeredAt)
        XCTAssertNotNil(alert.triggeredDate)
    }
    
    // MARK: - CreatePriceAlertRequest Tests
    
    func testCreatePriceAlertRequestEncoding() throws {
        let request = CreatePriceAlertRequest(
            ticker: "AAPL",
            condition: "ABOVE",
            targetPrice: 200.0
        )
        
        let encoder = JSONEncoder()
        let data = try encoder.encode(request)
        let json = try JSONSerialization.jsonObject(with: data) as! [String: Any]
        
        XCTAssertEqual(json["ticker"] as? String, "AAPL")
        XCTAssertEqual(json["condition"] as? String, "ABOVE")
        XCTAssertEqual(json["target_price"] as? Double, 200.0)
    }
    
    // MARK: - PriceAlertsResponse Tests
    
    func testPriceAlertsResponseDecoding() throws {
        let json = """
        {
            "success": true,
            "count": 2,
            "data": [
                {
                    "id": "alert1",
                    "user_id": "user1",
                    "ticker": "AAPL",
                    "condition": "ABOVE",
                    "target_price": 200.0,
                    "created_at": "2026-02-15T12:00:00Z",
                    "triggered_at": null,
                    "is_active": true
                },
                {
                    "id": "alert2",
                    "user_id": "user1",
                    "ticker": "MSFT",
                    "condition": "BELOW",
                    "target_price": 300.0,
                    "created_at": "2026-02-15T13:00:00Z",
                    "triggered_at": null,
                    "is_active": true
                }
            ]
        }
        """
        
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        
        let response = try decoder.decode(PriceAlertsResponse.self, from: json.data(using: .utf8)!)
        
        XCTAssertTrue(response.success)
        XCTAssertEqual(response.count, 2)
        XCTAssertEqual(response.data.count, 2)
        XCTAssertEqual(response.data[0].ticker, "AAPL")
        XCTAssertEqual(response.data[1].ticker, "MSFT")
    }
}
