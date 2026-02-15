import XCTest
@testable import Sigil

/// Unit tests for WatchlistService
final class WatchlistServiceTests: XCTestCase {
    
    var watchlistService: WatchlistService!
    
    override func setUp() async throws {
        // Get the shared instance and clear it for testing
        watchlistService = await WatchlistService.shared
        await MainActor.run {
            // Clear watchlist for clean test state
            for ticker in watchlistService.watchedTickers {
                watchlistService.removeFromWatchlist(ticker)
            }
        }
    }
    
    override func tearDown() async throws {
        // Clean up after tests
        await MainActor.run {
            for ticker in watchlistService.watchedTickers {
                watchlistService.removeFromWatchlist(ticker)
            }
        }
    }
    
    // MARK: - Add/Remove Tests
    
    @MainActor
    func testAddToWatchlist() {
        watchlistService.addToWatchlist("AAPL")
        XCTAssertTrue(watchlistService.isWatched("AAPL"))
        XCTAssertTrue(watchlistService.watchedTickers.contains("AAPL"))
    }
    
    @MainActor
    func testAddToWatchlistUppercases() {
        watchlistService.addToWatchlist("aapl")
        XCTAssertTrue(watchlistService.isWatched("AAPL"))
        XCTAssertTrue(watchlistService.isWatched("aapl"))  // Case-insensitive check
    }
    
    @MainActor
    func testRemoveFromWatchlist() {
        watchlistService.addToWatchlist("AAPL")
        XCTAssertTrue(watchlistService.isWatched("AAPL"))
        
        watchlistService.removeFromWatchlist("AAPL")
        XCTAssertFalse(watchlistService.isWatched("AAPL"))
    }
    
    @MainActor
    func testRemoveNonExistent() {
        // Should not crash when removing a ticker that doesn't exist
        watchlistService.removeFromWatchlist("NONEXISTENT")
        XCTAssertFalse(watchlistService.isWatched("NONEXISTENT"))
    }
    
    // MARK: - Toggle Tests
    
    @MainActor
    func testToggleWatchlistAdd() {
        XCTAssertFalse(watchlistService.isWatched("MSFT"))
        watchlistService.toggleWatchlist("MSFT")
        XCTAssertTrue(watchlistService.isWatched("MSFT"))
    }
    
    @MainActor
    func testToggleWatchlistRemove() {
        watchlistService.addToWatchlist("MSFT")
        XCTAssertTrue(watchlistService.isWatched("MSFT"))
        
        watchlistService.toggleWatchlist("MSFT")
        XCTAssertFalse(watchlistService.isWatched("MSFT"))
    }
    
    @MainActor
    func testToggleWatchlistCaseInsensitive() {
        watchlistService.addToWatchlist("googl")
        XCTAssertTrue(watchlistService.isWatched("GOOGL"))
        
        watchlistService.toggleWatchlist("GOOGL")
        XCTAssertFalse(watchlistService.isWatched("googl"))
    }
    
    // MARK: - isWatched Tests
    
    @MainActor
    func testIsWatchedCaseInsensitive() {
        watchlistService.addToWatchlist("AAPL")
        
        XCTAssertTrue(watchlistService.isWatched("AAPL"))
        XCTAssertTrue(watchlistService.isWatched("aapl"))
        XCTAssertTrue(watchlistService.isWatched("Aapl"))
    }
    
    @MainActor
    func testIsWatchedFalseForUnwatched() {
        XCTAssertFalse(watchlistService.isWatched("UNKNOWN"))
    }
    
    // MARK: - Multiple Tickers Tests
    
    @MainActor
    func testMultipleTickers() {
        watchlistService.addToWatchlist("AAPL")
        watchlistService.addToWatchlist("MSFT")
        watchlistService.addToWatchlist("GOOGL")
        
        XCTAssertEqual(watchlistService.watchedTickers.count, 3)
        XCTAssertTrue(watchlistService.isWatched("AAPL"))
        XCTAssertTrue(watchlistService.isWatched("MSFT"))
        XCTAssertTrue(watchlistService.isWatched("GOOGL"))
    }
    
    @MainActor
    func testAddDuplicate() {
        watchlistService.addToWatchlist("AAPL")
        watchlistService.addToWatchlist("AAPL")  // Add again
        
        // Set should not have duplicates
        let count = watchlistService.watchedTickers.filter { $0 == "AAPL" }.count
        XCTAssertEqual(count, 1)
    }
}
