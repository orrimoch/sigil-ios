import XCTest
@testable import Sigil

/// Unit tests for IBKRService (F6.3)
/// Tests connection state management, mock account ID, persistence
@MainActor
final class IBKRServiceTests: XCTestCase {
    
    var service: IBKRService!
    
    override func setUp() async throws {
        service = IBKRService.shared
        // Reset state
        UserDefaults.standard.set(false, forKey: "sigil_ibkr_connected")
        KeychainHelper.shared.delete(key: "sigil_ibkr_account_id")
    }
    
    override func tearDown() async throws {
        UserDefaults.standard.removeObject(forKey: "sigil_ibkr_connected")
        KeychainHelper.shared.delete(key: "sigil_ibkr_account_id")
    }
    
    // MARK: - Singleton Tests
    
    func testSharedInstanceExists() {
        XCTAssertNotNil(IBKRService.shared)
    }
    
    func testSharedInstanceIsSingleton() {
        let a = IBKRService.shared
        let b = IBKRService.shared
        XCTAssertTrue(a === b, "shared should return the same instance")
    }
    
    // MARK: - Initial State Tests
    
    func testInitialPublishedProperties() {
        // isConnecting should start false
        XCTAssertFalse(service.isConnecting, "Should not be connecting initially")
    }
    
    // MARK: - Error Type Tests
    
    func testIBKRErrorDescriptions() {
        let connectionError = IBKRError.connectionFailed("test")
        XCTAssertTrue(connectionError.localizedDescription.contains("test"))
        
        let disconnectError = IBKRError.disconnectFailed
        XCTAssertNotNil(disconnectError.localizedDescription)
        
        let orderError = IBKRError.orderFailed("HTTP 400")
        XCTAssertTrue(orderError.localizedDescription.contains("400"))
        
        let notConnected = IBKRError.notConnected
        XCTAssertTrue(notConnected.localizedDescription.contains("Not connected"))
    }
    
    // MARK: - Response Model Tests
    
    func testIBKRConnectionDataDecoding() throws {
        let json = """
        {
            "user_id": "test",
            "account_id": "DU1234567",
            "state": "connected",
            "is_paper": true,
            "connected_at": "2026-02-04T00:00:00",
            "error_message": null
        }
        """.data(using: .utf8)!
        
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        let data = try decoder.decode(IBKRConnectionData.self, from: json)
        
        XCTAssertEqual(data.userId, "test")
        XCTAssertEqual(data.accountId, "DU1234567")
        XCTAssertEqual(data.state, "connected")
        XCTAssertTrue(data.isPaper)
        XCTAssertNotNil(data.connectedAt)
        XCTAssertNil(data.errorMessage)
    }
    
    func testIBKROrderResultDecoding() throws {
        let json = """
        {
            "order_id": "IBKR-abc123",
            "ticker": "AAPL",
            "side": "BUY",
            "quantity": 10.0,
            "order_type": "MARKET",
            "status": "FILLED",
            "filled_price": 150.50,
            "filled_at": "2026-02-04T00:00:00",
            "is_paper": true
        }
        """.data(using: .utf8)!
        
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        let result = try decoder.decode(IBKROrderResult.self, from: json)
        
        XCTAssertEqual(result.orderId, "IBKR-abc123")
        XCTAssertEqual(result.ticker, "AAPL")
        XCTAssertEqual(result.side, "BUY")
        XCTAssertEqual(result.quantity, 10.0)
        XCTAssertEqual(result.status, "FILLED")
        XCTAssertEqual(result.filledPrice, 150.50)
        XCTAssertTrue(result.isPaper)
    }
    
    func testIBKRConnectResponseDecoding() throws {
        let json = """
        {
            "success": true,
            "message": "Connected to IBKR",
            "data": {
                "user_id": "anonymous",
                "account_id": "DU1234567",
                "state": "connected",
                "is_paper": true,
                "connected_at": "2026-02-04T00:00:00",
                "error_message": null
            }
        }
        """.data(using: .utf8)!
        
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        let response = try decoder.decode(IBKRConnectResponse.self, from: json)
        
        XCTAssertTrue(response.success)
        XCTAssertEqual(response.message, "Connected to IBKR")
        XCTAssertEqual(response.data.state, "connected")
    }
    
    // MARK: - Keychain Persistence Tests
    
    func testKeychainStorageAndRetrieval() {
        let testKey = "sigil_ibkr_test_account"
        let testValue = "DU9999999"
        
        let saved = KeychainHelper.shared.save(key: testKey, string: testValue)
        XCTAssertTrue(saved)
        
        let loaded = KeychainHelper.shared.loadString(key: testKey)
        XCTAssertEqual(loaded, testValue)
        
        // Cleanup
        KeychainHelper.shared.delete(key: testKey)
        let afterDelete = KeychainHelper.shared.loadString(key: testKey)
        XCTAssertNil(afterDelete)
    }
}
