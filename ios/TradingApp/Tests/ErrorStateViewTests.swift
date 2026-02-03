import XCTest
@testable import Sigil

/// Tests for REC-87: Error state views with retry UI
final class ErrorStateViewTests: XCTestCase {
    
    // MARK: - ErrorStateView Tests
    
    func testErrorStateViewInitialization() {
        // Given
        let title = "Something went wrong"
        let message = "Network error"
        
        // When
        let view = ErrorStateView(title: title, message: message)
        
        // Then — view should be created without crash
        XCTAssertNotNil(view)
    }
    
    func testErrorStateViewWithRetryAction() {
        // Given
        var retryTapped = false
        
        // When
        let view = ErrorStateView(
            title: "Error",
            message: "Please retry",
            retryAction: { retryTapped = true }
        )
        
        // Then
        XCTAssertNotNil(view)
        XCTAssertNotNil(view.retryAction)
    }
    
    func testErrorStateViewWithoutRetryAction() {
        // When
        let view = ErrorStateView(
            title: "No Data",
            message: "Data not available yet"
        )
        
        // Then
        XCTAssertNil(view.retryAction)
    }
    
    func testErrorStateViewCustomIcon() {
        // When
        let view = ErrorStateView(
            title: "Error",
            message: "Test",
            icon: "wifi.slash"
        )
        
        // Then
        XCTAssertEqual(view.icon, "wifi.slash")
    }
    
    // MARK: - HomeViewModel Error State Tests
    
    @MainActor
    func testHomeViewModelErrorMessageInitiallyNil() {
        let vm = HomeViewModel()
        XCTAssertNil(vm.errorMessage)
    }
    
    // MARK: - ScoresViewModel Error State Tests
    
    @MainActor
    func testScoresViewModelErrorMessageInitiallyNil() {
        let vm = ScoresViewModel()
        XCTAssertNil(vm.errorMessage)
        XCTAssertTrue(vm.stocks.isEmpty)
    }
    
    // MARK: - TradeViewModel Error State Tests
    
    @MainActor
    func testTradeViewModelOrdersErrorInitiallyNil() {
        let vm = TradeViewModel()
        XCTAssertNil(vm.ordersError)
        XCTAssertTrue(vm.todaysOrders.isEmpty)
    }
    
    // MARK: - PortfolioViewModel Error State Tests
    
    @MainActor
    func testPortfolioViewModelErrorInitiallyNil() {
        let vm = PortfolioViewModel()
        XCTAssertNil(vm.error)
        XCTAssertTrue(vm.holdings.isEmpty)
    }
}
