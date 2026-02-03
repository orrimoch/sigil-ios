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
    
    // Order entry
    @Published var orderSide: OrderSide = .buy
    @Published var orderType: OrderType = .market
    @Published var quantity: String = ""
    @Published var limitPrice: String = ""
    
    // Order flow
    @Published var showPreview = false
    @Published var showConfirmation = false
    @Published var isSubmitting = false
    @Published var lastOrder: OrderData?
    @Published var orderError: String?
    
    // Order history
    @Published var todaysOrders: [OrderData] = []
    @Published var ordersLoading = false
    
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
        
        if orderType == .limit {
            guard let limitPrice = limitPriceValue, limitPrice > 0 else { return false }
        }
        
        return true
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
        
        // Fetch current price and score in parallel
        Task {
            await withTaskGroup(of: Void.self) { group in
                group.addTask { await self.fetchPrice(for: stock.ticker) }
                group.addTask { await self.fetchScore(for: stock.ticker) }
            }
        }
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
        } catch {
            print("Price error: \(error)")
            currentPrice = nil
        }
    }
    
    // MARK: - Order Entry
    
    func previewOrder() {
        guard canSubmitOrder else { return }
        showPreview = true
    }
    
    func submitOrder() async {
        guard let stock = selectedStock, canSubmitOrder else { return }
        
        isSubmitting = true
        orderError = nil
        
        do {
            let response = try await api.createOrder(
                ticker: stock.ticker,
                side: orderSide.rawValue,
                quantity: quantityValue,
                orderType: orderType.rawValue,
                limitPrice: limitPriceValue
            )
            
            lastOrder = response.data
            showPreview = false
            showConfirmation = true
            
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
        defer { ordersLoading = false }
        
        do {
            let response = try await api.getTodaysOrders()
            todaysOrders = response.data
        } catch {
            print("Orders error: \(error)")
        }
    }
    
    func cancelOrder(_ order: OrderData) async {
        do {
            _ = try await api.cancelOrder(orderId: order.orderId)
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
    
    var description: String {
        switch self {
        case .market: return "Executes immediately at current price"
        case .limit: return "Executes when price reaches your limit"
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
