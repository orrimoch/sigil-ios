import SwiftUI
import Combine

/// F6.x Trade View Model
/// Handles order entry, stock search, and order history
@MainActor
class TradeViewModel: ObservableObject {
    // MARK: - Published Properties
    
    // Search
    @Published var searchText = ""
    @Published var searchResults: [StockScore] = []
    @Published var isSearching = false
    
    // Selected stock
    @Published var selectedStock: StockScore?
    @Published var currentPrice: Double?
    @Published var priceLoading = false
    
    // REC-178: Daily price change
    @Published var dailyChange: Double?
    @Published var dailyChangePercent: Double?
    
    // REC-177: Position tracking for sell validation
    @Published var currentPosition: Holding?
    @Published var allHoldings: [Holding] = []
    
    // Order entry
    @Published var orderSide: OrderSide = .buy
    @Published var orderType: OrderType = .market
    @Published var quantity: String = ""
    @Published var limitPrice: String = ""
    
    // Order flow
    @Published var showPreview = false
    @Published var showConfirmation = false
    @Published var showLiveTradeConfirmation = false
    @Published var isSubmitting = false
    @Published var lastOrder: OrderData?
    @Published var orderError: String?
    
    // Risk validation (Phase 2)
    @Published var riskWarnings: [String] = []
    @Published var showRiskWarning = false
    
    // Order history
    @Published var todaysOrders: [OrderData] = []
    @Published var ordersLoading = false
    @Published var ordersError: String?
    
    // MARK: - Computed Properties
    
    var quantityValue: Double {
        Double(quantity) ?? 0
    }
    
    var limitPriceValue: Double? {
        orderType == .limit ? Double(limitPrice) : nil
    }
    
    var executionPrice: Double {
        orderType == .limit ? (limitPriceValue ?? 0) : (currentPrice ?? 0)
    }
    
    var estimatedTotal: Double {
        quantityValue * executionPrice
    }
    
    var canSubmitOrder: Bool {
        guard let _ = selectedStock,
              quantityValue > 0,
              currentPrice != nil else { return false }
        
        // Limit and Stop orders require a price
        if orderType.needsPrice {
            guard let limitPrice = limitPriceValue, limitPrice > 0 else { return false }
        }
        
        // REC-177: Validate sell quantity against position size
        if orderSide == .sell {
            guard let position = currentPosition, quantityValue <= position.shares else {
                return false
            }
        }
        
        return true
    }
    
    // REC-177: Position size for current stock (0 if not held)
    var positionSize: Double {
        currentPosition?.shares ?? 0
    }
    
    // REC-177: Check if user has a position in selected stock
    var hasPosition: Bool {
        positionSize > 0
    }
    
    // REC-177: Validation error message for sell orders
    var sellValidationError: String? {
        guard orderSide == .sell else { return nil }
        
        if currentPosition == nil {
            return "You don't own this stock"
        }
        
        if quantityValue > positionSize {
            return "Exceeds position (\(Int(positionSize)) shares)"
        }
        
        return nil
    }
    
    // MARK: - Private
    
    private let api = APIService.shared
    private var searchTask: Task<Void, Never>?
    
    // MARK: - Search
    
    func search() {
        searchTask?.cancel()
        
        guard searchText.count >= 1 else {
            searchResults = []
            return
        }
        
        searchTask = Task {
            isSearching = true
            defer { isSearching = false }
            
            let query = searchText.uppercased()
            
            // Search stock universe first (always fast and reliable)
            do {
                let response = try await api.getStocks(limit: 500)
                let matched = response.stocks.filter { stock in
                    stock.ticker.uppercased().contains(query) ||
                    stock.name.uppercased().contains(query) ||
                    stock.sector.uppercased().contains(query)
                }.prefix(20)
                
                searchResults = matched.map { stock in
                    StockScore(
                        ticker: stock.ticker,
                        companyName: stock.name,
                        sector: stock.sector,
                        totalScore: 0,
                        signal: "—",
                        rank: 0,
                        percentile: 0,
                        fundamentalScore: 0,
                        sentimentScore: 0,
                        technicalScore: 0,
                        macroScore: 0
                    )
                }
            } catch {
                print("Stock search error: \(error)")
                searchResults = []
            }
        }
    }
    
    func selectStock(_ stock: StockScore) {
        selectedStock = stock
        searchText = stock.ticker
        searchResults = []
        
        // REC-178: Auto-select order side based on signal
        if stock.signal == "SELL" {
            orderSide = .sell
        } else if stock.signal == "BUY" {
            orderSide = .buy
        }
        // For HOLD, keep current selection (user decides)
        
        // Fetch current price, score, and position in parallel
        Task {
            await withTaskGroup(of: Void.self) { group in
                group.addTask { await self.fetchPrice(for: stock.ticker) }
                group.addTask { await self.fetchScore(for: stock.ticker) }
                group.addTask { await self.fetchPosition(for: stock.ticker) }
            }
        }
    }
    
    // REC-177: Fetch user's position in a stock
    private func fetchPosition(for ticker: String) async {
        do {
            let response = try await api.getPortfolio()
            await MainActor.run {
                self.allHoldings = response.data.holdings
                self.currentPosition = response.data.holdings.first { $0.ticker == ticker }
            }
        } catch {
            print("Position fetch error: \(error)")
            await MainActor.run {
                self.currentPosition = nil
            }
        }
    }
    
    // REC-177: Set quantity to position size (for "Sell All" single position)
    func setQuantityToPosition() {
        guard let position = currentPosition else { return }
        quantity = String(Int(position.shares))
    }
    
    // REC-177: Set quantity to quick amount
    func setQuickQuantity(_ amount: Int) {
        quantity = String(amount)
    }
    
    // REC-177: Sell all holdings (entire portfolio)
    func sellAllPortfolio() async {
        // Fetch latest holdings
        do {
            let response = try await api.getPortfolio()
            allHoldings = response.data.holdings
        } catch {
            print("Failed to fetch portfolio: \(error)")
            return
        }
        
        // Submit sell orders for each holding
        for holding in allHoldings where holding.shares > 0 {
            do {
                _ = try await api.createOrder(
                    ticker: holding.ticker,
                    side: "SELL",
                    quantity: holding.shares,
                    orderType: "MARKET",
                    limitPrice: nil
                )
                
                // Track analytics
                Analytics.shared.track(.orderSubmitted, properties: [
                    "ticker": holding.ticker,
                    "side": "SELL",
                    "quantity": holding.shares,
                    "type": "MARKET",
                    "context": "sell_all_portfolio"
                ])
            } catch {
                print("Failed to sell \(holding.ticker): \(error)")
            }
        }
        
        // Refresh orders
        await fetchTodaysOrders()
    }
    
    private func fetchScore(for ticker: String) async {
        do {
            let response = try await api.getScore(ticker: ticker)
            let detail = response.data
            await MainActor.run {
                self.selectedStock = StockScore(
                    ticker: detail.ticker,
                    companyName: self.selectedStock?.companyName,
                    sector: detail.sector,
                    totalScore: detail.totalScore,
                    signal: detail.signal,
                    rank: detail.rank,
                    percentile: detail.percentile,
                    fundamentalScore: detail.fundamentalScore,
                    sentimentScore: detail.sentimentScore,
                    technicalScore: detail.technicalScore,
                    macroScore: detail.macroScore
                )
            }
        } catch {
            print("Score fetch unavailable for \(ticker): \(error)")
            // Keep the stock selected without score — that's fine
        }
    }
    
    func clearSelection() {
        selectedStock = nil
        currentPrice = nil
        dailyChange = nil
        dailyChangePercent = nil
        currentPosition = nil
        searchText = ""
        quantity = ""
        limitPrice = ""
    }
    
    // MARK: - Price
    
    func fetchPrice(for ticker: String) async {
        priceLoading = true
        defer { priceLoading = false }
        
        do {
            let response = try await api.getPrice(ticker: ticker)
            currentPrice = response.price
            // REC-178: Daily change data
            dailyChange = response.change
            dailyChangePercent = response.changePercent
        } catch {
            print("Price error: \(error)")
            currentPrice = nil
            dailyChange = nil
            dailyChangePercent = nil
        }
    }
    
    // MARK: - Order Entry
    
    func previewOrder() {
        guard canSubmitOrder else { return }
        Analytics.shared.track(.orderPreview, properties: ["ticker": selectedStock?.ticker ?? "unknown"])
        showPreview = true
    }
    
    /// Whether to route orders through IBKR (live mode + connected)
    var shouldUseIBKR: Bool {
        return !AppState.shared.isPaperTrading && IBKRService.shared.isConnected
    }
    
    /// Confirm and execute a live IBKR trade after user acknowledged the warning
    func confirmLiveTrade() async {
        // showLiveTradeConfirmation is already true, so submitOrder will proceed
        await submitOrder()
    }
    
    func submitOrder() async {
        guard let stock = selectedStock, canSubmitOrder else { return }
        
        // F6.3: Extra confirmation for live IBKR trades
        if shouldUseIBKR && !showLiveTradeConfirmation {
            showLiveTradeConfirmation = true
            return
        }
        // Reset the confirmation flag after use
        showLiveTradeConfirmation = false
        
        isSubmitting = true
        orderError = nil
        riskWarnings = []
        
        // Phase 2: Validate trade against risk settings
        do {
            let validation = try await api.validateTrade(
                ticker: stock.ticker,
                action: orderSide.rawValue,
                quantity: quantityValue,
                price: executionPrice
            )
            
            // Collect warnings
            let warnings = validation.warnings.map { $0.message }
            if !warnings.isEmpty {
                riskWarnings = warnings
                // Show warning but don't block - user can still proceed
                print("[Trade] Risk warnings: \(warnings)")
            }
        } catch {
            // Validation failed - log but don't block trade
            // This could be auth issue or endpoint not available
            print("[Trade] Validation skipped: \(error.localizedDescription)")
        }
        
        do {
            if shouldUseIBKR {
                // F6.3: Route to IBKR for live trading
                let ibkrResult = try await IBKRService.shared.submitOrder(
                    ticker: stock.ticker,
                    side: orderSide.rawValue,
                    quantity: quantityValue,
                    orderType: orderType.rawValue,
                    limitPrice: limitPriceValue
                )
                
                // Convert IBKR result to OrderData for display
                lastOrder = OrderData(
                    orderId: ibkrResult.orderId,
                    ticker: ibkrResult.ticker,
                    side: ibkrResult.side,
                    orderType: ibkrResult.orderType,
                    quantity: ibkrResult.quantity,
                    limitPrice: nil,
                    status: ibkrResult.status,
                    filledQuantity: ibkrResult.quantity,
                    filledPrice: ibkrResult.filledPrice,
                    createdAt: ibkrResult.filledAt ?? "",
                    updatedAt: ibkrResult.filledAt ?? "",
                    filledAt: ibkrResult.filledAt,
                    rejectReason: nil,
                    isPaper: ibkrResult.isPaper
                )
            } else {
                // Paper trading: use existing endpoint
                let response = try await api.createOrder(
                    ticker: stock.ticker,
                    side: orderSide.rawValue,
                    quantity: quantityValue,
                    orderType: orderType.rawValue,
                    limitPrice: limitPriceValue
                )
                
                lastOrder = response.data
            }
            
            showPreview = false
            showConfirmation = true
            
            // Analytics: track successful order submission
            Analytics.shared.track(.orderSubmitted, properties: [
                "ticker": stock.ticker,
                "side": orderSide.rawValue,
                "quantity": quantityValue,
                "type": orderType.rawValue
            ])
            
            // F9.2: Send trade confirmation notification
            NotificationService.shared.sendTradeConfirmation(
                ticker: stock.ticker,
                side: orderSide.rawValue,
                quantity: quantityValue,
                price: executionPrice,
                total: estimatedTotal
            )
            
            // Refresh orders
            await fetchTodaysOrders()
            
            // Clear form
            clearSelection()
            
        } catch let error as APIError {
            orderError = error.errorDescription
        } catch {
            orderError = error.localizedDescription
        }
        
        isSubmitting = false
    }
    
    // MARK: - Order History
    
    func fetchTodaysOrders() async {
        ordersLoading = true
        ordersError = nil
        defer { ordersLoading = false }
        
        do {
            let response = try await api.getTodaysOrders()
            todaysOrders = response.data
        } catch {
            ordersError = error.localizedDescription
            print("Orders error: \(error)")
        }
    }
    
    func cancelOrder(_ order: OrderData) async {
        do {
            if shouldUseIBKR {
                // F6.6: Route cancellation through IBKR for live trading
                try await IBKRService.shared.cancelOrder(orderId: order.orderId)
            } else {
                // Paper trading: use existing endpoint
                _ = try await api.cancelOrder(orderId: order.orderId)
            }
            await fetchTodaysOrders()
        } catch {
            print("Cancel error: \(error)")
        }
    }
}

// MARK: - Order Types

enum OrderSide: String, CaseIterable {
    case buy = "BUY"
    case sell = "SELL"
    
    var color: Color {
        switch self {
        case .buy: return .Signal.buy
        case .sell: return .Signal.sell
        }
    }
    
    var icon: String {
        switch self {
        case .buy: return "arrow.up.circle.fill"
        case .sell: return "arrow.down.circle.fill"
        }
    }
}

enum OrderType: String, CaseIterable {
    case market = "MARKET"
    case limit = "LIMIT"
    case stop = "STP"
    case trailingStop = "TRAIL"
    
    var description: String {
        switch self {
        case .market: return "Executes immediately at current price"
        case .limit: return "Executes when price reaches your limit"
        case .stop: return "Triggers when price falls to your stop price"
        case .trailingStop: return "Stop that follows price up, locking in gains"
        }
    }
    
    var priceLabel: String {
        switch self {
        case .market: return ""
        case .limit: return "Limit Price"
        case .stop: return "Stop Price"
        case .trailingStop: return "Trail Amount ($)"
        }
    }
    
    var needsPrice: Bool {
        self != .market
    }
}

enum TimeInForce: String, CaseIterable {
    case day = "DAY"
    case gtc = "GTC"
    case gtd = "GTD"
    
    var description: String {
        switch self {
        case .day: return "Day only"
        case .gtc: return "Good till canceled"
        case .gtd: return "Good till date"
        }
    }
}

// MARK: - Order Status Extensions

extension OrderData {
    var statusColor: Color {
        switch status {
        case "FILLED": return .Signal.buy
        case "PENDING": return .Signal.hold
        case "CANCELLED": return .Signal.hold
        case "REJECTED": return .Signal.sell
        default: return .Text.secondary
        }
    }
    
    var sideColor: Color {
        side == "BUY" ? .Signal.buy : .Signal.sell
    }
    
    var formattedTime: String {
        // Parse ISO date string (handles both with and without fractional seconds)
        let trimmed = createdAt.trimmingCharacters(in: .whitespaces)
        
        // Try ISO8601DateFormatter with fractional seconds first
        let isoFormatter = ISO8601DateFormatter()
        isoFormatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        
        if let date = isoFormatter.date(from: trimmed) {
            return Self.displayFormatter.string(from: date)
        }
        
        // Fallback: parse manually for timestamps like "2026-02-03T15:20:06.241415"
        let df = DateFormatter()
        df.dateFormat = "yyyy-MM-dd'T'HH:mm:ss.SSSSSS"
        df.locale = Locale(identifier: "en_US_POSIX")
        
        if let date = df.date(from: trimmed) {
            return Self.displayFormatter.string(from: date)
        }
        
        // Try without fractional seconds
        df.dateFormat = "yyyy-MM-dd'T'HH:mm:ss"
        if let date = df.date(from: trimmed) {
            return Self.displayFormatter.string(from: date)
        }
        
        return trimmed
    }
    
    private static let displayFormatter: DateFormatter = {
        let f = DateFormatter()
        f.dateFormat = "MMM d, h:mm a"
        return f
    }()
}
