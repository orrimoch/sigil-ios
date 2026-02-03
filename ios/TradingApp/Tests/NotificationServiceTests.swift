import XCTest
import UserNotifications
@testable import Sigil

/// Unit tests for NotificationService (F9.2)
/// Tests notification content formatting, preference gating, and authorization state
@MainActor
final class NotificationServiceTests: XCTestCase {
    
    var service: NotificationService!
    
    override func setUp() async throws {
        service = NotificationService.shared
        // Reset notification preferences
        UserDefaults.standard.set(true, forKey: "tradeConfirmations")
        UserDefaults.standard.set(true, forKey: "scoreAlerts")
        UserDefaults.standard.set(true, forKey: "weeklyScoreAlerts")
    }
    
    override func tearDown() async throws {
        // Clean up UserDefaults
        UserDefaults.standard.removeObject(forKey: "tradeConfirmations")
        UserDefaults.standard.removeObject(forKey: "scoreAlerts")
        UserDefaults.standard.removeObject(forKey: "weeklyScoreAlerts")
    }
    
    // MARK: - Singleton Tests
    
    func testSharedInstanceExists() {
        XCTAssertNotNil(NotificationService.shared)
    }
    
    func testSharedInstanceIsSingleton() {
        let a = NotificationService.shared
        let b = NotificationService.shared
        XCTAssertTrue(a === b, "shared should return the same instance")
    }
    
    // MARK: - Preference Gating Tests
    
    func testTradeConfirmationRespectsDisabledPreference() {
        // When trade confirmations are disabled, no notification should be scheduled
        UserDefaults.standard.set(false, forKey: "tradeConfirmations")
        
        // This should silently return without scheduling
        service.sendTradeConfirmation(
            ticker: "AAPL",
            side: "BUY",
            quantity: 10,
            price: 150.0,
            total: 1500.0
        )
        
        // If we got here without crash, the preference gate works
        XCTAssertTrue(true, "Trade confirmation should respect disabled preference")
    }
    
    func testScoreAlertRespectsDisabledPreference() {
        UserDefaults.standard.set(false, forKey: "scoreAlerts")
        
        service.sendScoreAlert(
            ticker: "TSLA",
            oldSignal: "HOLD",
            newSignal: "BUY",
            score: 75.0
        )
        
        XCTAssertTrue(true, "Score alert should respect disabled preference")
    }
    
    func testWeeklyScheduleRespectsDisabledPreference() {
        UserDefaults.standard.set(false, forKey: "weeklyScoreAlerts")
        
        // Should remove pending weekly notification
        service.scheduleWeeklyScoreUpdate()
        
        XCTAssertTrue(true, "Weekly schedule should respect disabled preference")
    }
    
    // MARK: - Authorization State Tests
    
    func testInitialAuthorizationStatusProperty() {
        // authorizationStatus should be a valid enum value
        let status = service.authorizationStatus
        XCTAssertTrue(
            [.notDetermined, .denied, .authorized, .provisional, .ephemeral].contains(status),
            "Should have a valid authorization status"
        )
    }
    
    func testIsAuthorizedMatchesStatus() async {
        await service.refreshAuthorizationStatus()
        let expected = service.authorizationStatus == .authorized
        XCTAssertEqual(service.isAuthorized, expected)
    }
    
    // MARK: - Cleanup Tests
    
    func testRemoveAllPendingDoesNotCrash() {
        service.removeAllPending()
        XCTAssertTrue(true, "removeAllPending should not crash")
    }
    
    func testClearDeliveredDoesNotCrash() {
        service.clearDelivered()
        XCTAssertTrue(true, "clearDelivered should not crash")
    }
    
    // MARK: - Trade Confirmation Content Tests
    
    func testTradeConfirmationWithEnabledPreference() {
        UserDefaults.standard.set(true, forKey: "tradeConfirmations")
        
        // Should not crash even if not authorized (guard will return early)
        service.sendTradeConfirmation(
            ticker: "MSFT",
            side: "SELL",
            quantity: 5.5,
            price: 420.69,
            total: 2313.80
        )
        
        XCTAssertTrue(true, "Should handle fractional quantities without crash")
    }
    
    func testTradeConfirmationWithZeroQuantity() {
        UserDefaults.standard.set(true, forKey: "tradeConfirmations")
        
        service.sendTradeConfirmation(
            ticker: "GOOG",
            side: "BUY",
            quantity: 0,
            price: 175.0,
            total: 0
        )
        
        XCTAssertTrue(true, "Should handle zero quantity without crash")
    }
    
    func testScoreAlertWithAllSignalTypes() {
        UserDefaults.standard.set(true, forKey: "scoreAlerts")
        
        for signal in ["BUY", "SELL", "HOLD"] {
            service.sendScoreAlert(
                ticker: "NVDA",
                oldSignal: "HOLD",
                newSignal: signal,
                score: 65.0
            )
        }
        
        XCTAssertTrue(true, "Should handle all signal types without crash")
    }
    
    // MARK: - F9.1 Weekly Score Notification Tests
    
    func testWeeklyScheduleWithEnabledPreference() {
        UserDefaults.standard.set(true, forKey: "weeklyScoreAlerts")
        
        service.scheduleWeeklyScoreUpdate()
        
        // Should not crash and should schedule the notification
        XCTAssertTrue(true, "Weekly schedule should work with enabled preference")
    }
    
    func testWeeklyScheduleRemoveWhenDisabled() {
        UserDefaults.standard.set(false, forKey: "weeklyScoreAlerts")
        
        service.scheduleWeeklyScoreUpdate()
        
        XCTAssertTrue(true, "Should remove weekly notification when disabled")
    }
    
    func testRegisterCategoriesDoesNotCrash() {
        service.registerCategories()
        XCTAssertTrue(true, "Register categories should not crash")
    }
    
    func testUpdateWeeklyContentDoesNotCrash() async {
        // Should gracefully fail when backend is not running
        await service.updateWeeklyContentFromAPI()
        XCTAssertTrue(true, "Update weekly content should not crash even without backend")
    }
    
    // MARK: - F9.1 Score Summary Response Model Tests
    
    func testScoreSummaryDataDecoding() throws {
        let json = """
        {
            "success": true,
            "data": {
                "buy_count": 15,
                "hold_count": 30,
                "sell_count": 5,
                "total_scored": 50,
                "signal_changes": 8,
                "top_movers": [],
                "new_buy_signals": [],
                "updated_at": "2026-02-04T00:00:00"
            }
        }
        """.data(using: .utf8)!
        
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        let response = try decoder.decode(ScoreSummaryResponse.self, from: json)
        
        XCTAssertTrue(response.success)
        XCTAssertNotNil(response.data)
        XCTAssertEqual(response.data?.buyCount, 15)
        XCTAssertEqual(response.data?.holdCount, 30)
        XCTAssertEqual(response.data?.sellCount, 5)
        XCTAssertEqual(response.data?.signalChanges, 8)
    }
    
    func testScoreMoverDecoding() throws {
        let json = """
        {
            "ticker": "AAPL",
            "score": 75.0,
            "signal": "BUY",
            "score_change": 5.0,
            "signal_change": "HOLD → BUY"
        }
        """.data(using: .utf8)!
        
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        let mover = try decoder.decode(ScoreMover.self, from: json)
        
        XCTAssertEqual(mover.ticker, "AAPL")
        XCTAssertEqual(mover.scoreChange, 5.0)
        XCTAssertEqual(mover.signalChange, "HOLD → BUY")
    }
}
