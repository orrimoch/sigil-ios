import XCTest
@testable import Sigil

/// Unit tests for WatchlistService (F9.3)
/// Tests add/remove watched stocks, persistence, toggle behavior
@MainActor
final class WatchlistServiceTests: XCTestCase {
    
    var service: WatchlistService!
    
    override func setUp() async throws {
        service = WatchlistService.shared
        // Clear watchlist
        UserDefaults.standard.removeObject(forKey: "sigil_watchlist")
        service.watchedTickers = []
    }
    
    override func tearDown() async throws {
        UserDefaults.standard.removeObject(forKey: "sigil_watchlist")
    }
    
    // MARK: - Singleton Tests
    
    func testSharedInstanceExists() {
        XCTAssertNotNil(WatchlistService.shared)
    }
    
    func testSharedInstanceIsSingleton() {
        let a = WatchlistService.shared
        let b = WatchlistService.shared
        XCTAssertTrue(a === b)
    }
    
    // MARK: - Add/Remove Tests
    
    func testAddToWatchlist() {
        service.addToWatchlist("AAPL")
        
        XCTAssertTrue(service.isWatched("AAPL"))
        XCTAssertTrue(service.watchedTickers.contains("AAPL"))
    }
    
    func testAddDuplicateIsIdempotent() {
        service.addToWatchlist("AAPL")
        service.addToWatchlist("AAPL")
        
        XCTAssertTrue(service.isWatched("AAPL"))
        XCTAssertEqual(service.watchedTickers.count, 1)
    }
    
    func testRemoveFromWatchlist() {
        service.addToWatchlist("AAPL")
        service.removeFromWatchlist("AAPL")
        
        XCTAssertFalse(service.isWatched("AAPL"))
    }
    
    func testRemoveNonexistentIsNoop() {
        service.removeFromWatchlist("TSLA")
        XCTAssertFalse(service.isWatched("TSLA"))
    }
    
    func testToggleAdds() {
        service.toggleWatchlist("MSFT")
        XCTAssertTrue(service.isWatched("MSFT"))
    }
    
    func testToggleRemoves() {
        service.addToWatchlist("MSFT")
        service.toggleWatchlist("MSFT")
        XCTAssertFalse(service.isWatched("MSFT"))
    }
    
    // MARK: - Case Handling
    
    func testUppercasesOnAdd() {
        service.addToWatchlist("aapl")
        XCTAssertTrue(service.isWatched("AAPL"))
        XCTAssertTrue(service.isWatched("aapl"))
    }
    
    func testIsWatchedCaseInsensitive() {
        service.addToWatchlist("AAPL")
        XCTAssertTrue(service.isWatched("aapl"))
        XCTAssertTrue(service.isWatched("Aapl"))
    }
    
    // MARK: - Persistence Tests
    
    func testPersistsToUserDefaults() {
        service.addToWatchlist("AAPL")
        service.addToWatchlist("MSFT")
        
        let stored = UserDefaults.standard.stringArray(forKey: "sigil_watchlist") ?? []
        XCTAssertTrue(stored.contains("AAPL"))
        XCTAssertTrue(stored.contains("MSFT"))
    }
    
    func testRemovePersists() {
        service.addToWatchlist("AAPL")
        service.removeFromWatchlist("AAPL")
        
        let stored = UserDefaults.standard.stringArray(forKey: "sigil_watchlist") ?? []
        XCTAssertFalse(stored.contains("AAPL"))
    }
    
    // MARK: - Multiple Stocks
    
    func testMultipleStocks() {
        service.addToWatchlist("AAPL")
        service.addToWatchlist("MSFT")
        service.addToWatchlist("GOOGL")
        
        XCTAssertEqual(service.watchedTickers.count, 3)
        XCTAssertTrue(service.isWatched("AAPL"))
        XCTAssertTrue(service.isWatched("MSFT"))
        XCTAssertTrue(service.isWatched("GOOGL"))
    }
    
    // MARK: - Response Model Tests
    
    func testSignalChangeDecoding() throws {
        let json = """
        {
            "ticker": "AAPL",
            "old_signal": "HOLD",
            "new_signal": "BUY",
            "old_score": 55.0,
            "new_score": 75.0,
            "score_change": 20.0
        }
        """.data(using: .utf8)!
        
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        let change = try decoder.decode(SignalChange.self, from: json)
        
        XCTAssertEqual(change.ticker, "AAPL")
        XCTAssertEqual(change.oldSignal, "HOLD")
        XCTAssertEqual(change.newSignal, "BUY")
        XCTAssertEqual(change.scoreChange, 20.0)
    }
    
    func testScoreChangesResponseDecoding() throws {
        let json = """
        {
            "success": true,
            "count": 1,
            "data": [
                {
                    "ticker": "TSLA",
                    "old_signal": "BUY",
                    "new_signal": "SELL",
                    "old_score": 72.0,
                    "new_score": 35.0,
                    "score_change": -37.0
                }
            ]
        }
        """.data(using: .utf8)!
        
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        let response = try decoder.decode(ScoreChangesResponse.self, from: json)
        
        XCTAssertTrue(response.success)
        XCTAssertEqual(response.count, 1)
        XCTAssertEqual(response.data[0].ticker, "TSLA")
    }
}
