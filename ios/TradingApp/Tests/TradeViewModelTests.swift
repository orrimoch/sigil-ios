import XCTest
@testable import Sigil

/// REC-177: Tests for sell quantity validation
final class TradeViewModelTests: XCTestCase {
    
    @MainActor
    func testSellValidationErrorWhenNoPosition() async {
        let viewModel = TradeViewModel()
        viewModel.orderSide = .sell
        viewModel.quantity = "10"
        // No position set
        
        XCTAssertNotNil(viewModel.sellValidationError)
        XCTAssertEqual(viewModel.sellValidationError, "You don't own this stock")
    }
    
    @MainActor
    func testSellValidationErrorWhenExceedingPosition() async {
        let viewModel = TradeViewModel()
        viewModel.orderSide = .sell
        viewModel.quantity = "100"
        
        // Mock a position with 50 shares
        let holding = Holding(
            ticker: "AAPL",
            shares: 50,
            avgCost: 150.0,
            currentPrice: 155.0,
            marketValue: 7750.0,
            costBasis: 7500.0,
            unrealizedPnl: 250.0,
            unrealizedPnlPercent: 3.33,
            openedAt: "2026-01-01"
        )
        viewModel.currentPosition = holding
        
        XCTAssertNotNil(viewModel.sellValidationError)
        XCTAssertTrue(viewModel.sellValidationError?.contains("Exceeds position") ?? false)
    }
    
    @MainActor
    func testNoValidationErrorForValidSell() async {
        let viewModel = TradeViewModel()
        viewModel.orderSide = .sell
        viewModel.quantity = "25"
        
        // Mock a position with 50 shares
        let holding = Holding(
            ticker: "AAPL",
            shares: 50,
            avgCost: 150.0,
            currentPrice: 155.0,
            marketValue: 7750.0,
            costBasis: 7500.0,
            unrealizedPnl: 250.0,
            unrealizedPnlPercent: 3.33,
            openedAt: "2026-01-01"
        )
        viewModel.currentPosition = holding
        
        XCTAssertNil(viewModel.sellValidationError)
    }
    
    @MainActor
    func testNoValidationErrorForBuyOrders() async {
        let viewModel = TradeViewModel()
        viewModel.orderSide = .buy
        viewModel.quantity = "1000"
        // No position needed for buy orders
        
        XCTAssertNil(viewModel.sellValidationError)
    }
    
    @MainActor
    func testPositionSizeComputed() async {
        let viewModel = TradeViewModel()
        
        XCTAssertEqual(viewModel.positionSize, 0)
        XCTAssertFalse(viewModel.hasPosition)
        
        // Set a position
        let holding = Holding(
            ticker: "AAPL",
            shares: 75,
            avgCost: 150.0,
            currentPrice: 155.0,
            marketValue: 11625.0,
            costBasis: 11250.0,
            unrealizedPnl: 375.0,
            unrealizedPnlPercent: 3.33,
            openedAt: "2026-01-01"
        )
        viewModel.currentPosition = holding
        
        XCTAssertEqual(viewModel.positionSize, 75)
        XCTAssertTrue(viewModel.hasPosition)
    }
    
    @MainActor
    func testSetQuantityToPosition() async {
        let viewModel = TradeViewModel()
        
        let holding = Holding(
            ticker: "AAPL",
            shares: 42,
            avgCost: 150.0,
            currentPrice: 155.0,
            marketValue: 6510.0,
            costBasis: 6300.0,
            unrealizedPnl: 210.0,
            unrealizedPnlPercent: 3.33,
            openedAt: "2026-01-01"
        )
        viewModel.currentPosition = holding
        
        viewModel.setQuantityToPosition()
        
        XCTAssertEqual(viewModel.quantity, "42")
    }
    
    @MainActor
    func testSetQuickQuantity() async {
        let viewModel = TradeViewModel()
        
        viewModel.setQuickQuantity(50)
        XCTAssertEqual(viewModel.quantity, "50")
        
        viewModel.setQuickQuantity(100)
        XCTAssertEqual(viewModel.quantity, "100")
    }
    
    @MainActor
    func testCanSubmitOrderBlockedForInvalidSell() async {
        let viewModel = TradeViewModel()
        viewModel.orderSide = .sell
        viewModel.quantity = "100"
        viewModel.currentPrice = 150.0
        viewModel.selectedStock = StockScore(
            ticker: "AAPL",
            companyName: "Apple Inc",
            sector: "Technology",
            totalScore: 75,
            signal: "BUY",
            rank: 1,
            percentile: 99,
            fundamentalScore: 80,
            sentimentScore: 70,
            technicalScore: 75,
            macroScore: 72
        )
        
        // Position only has 50 shares
        let holding = Holding(
            ticker: "AAPL",
            shares: 50,
            avgCost: 150.0,
            currentPrice: 155.0,
            marketValue: 7750.0,
            costBasis: 7500.0,
            unrealizedPnl: 250.0,
            unrealizedPnlPercent: 3.33,
            openedAt: "2026-01-01"
        )
        viewModel.currentPosition = holding
        
        // Should not be able to submit (quantity 100 > position 50)
        XCTAssertFalse(viewModel.canSubmitOrder)
    }
    
    @MainActor
    func testCanSubmitOrderAllowedForValidSell() async {
        let viewModel = TradeViewModel()
        viewModel.orderSide = .sell
        viewModel.quantity = "25"
        viewModel.currentPrice = 150.0
        viewModel.selectedStock = StockScore(
            ticker: "AAPL",
            companyName: "Apple Inc",
            sector: "Technology",
            totalScore: 75,
            signal: "BUY",
            rank: 1,
            percentile: 99,
            fundamentalScore: 80,
            sentimentScore: 70,
            technicalScore: 75,
            macroScore: 72
        )
        
        // Position has 50 shares
        let holding = Holding(
            ticker: "AAPL",
            shares: 50,
            avgCost: 150.0,
            currentPrice: 155.0,
            marketValue: 7750.0,
            costBasis: 7500.0,
            unrealizedPnl: 250.0,
            unrealizedPnlPercent: 3.33,
            openedAt: "2026-01-01"
        )
        viewModel.currentPosition = holding
        
        // Should be able to submit (quantity 25 <= position 50)
        XCTAssertTrue(viewModel.canSubmitOrder)
    }
}
