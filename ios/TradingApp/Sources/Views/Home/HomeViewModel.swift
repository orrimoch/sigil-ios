import Foundation
import SwiftUI

/// ViewModel for Home Dashboard (F4.x)
/// Connects to real API endpoints for portfolio, market, picks, and alerts
@MainActor
class HomeViewModel: ObservableObject {
    // MARK: - Published State
    
    // F4.1: Portfolio Summary
    @Published var portfolioValue: Double? = nil
    @Published var dailyChange: Double = 0
    @Published var dailyChangePercent: Double = 0
    
    // F4.2: Market Overview
    @Published var marketIndices: [MarketIndex] = []
    
    // F4.3: Top AI Picks
    @Published var topPicks: [TopPick] = []
    
    // F4.4: Alerts Feed
    @Published var alerts: [AlertItem] = []
    
    // GAP-005: Actions This Week (recommended trades based on portfolio vs scores)
    @Published var weeklyActions: [WeeklyAction] = []
    
    // Risk Module: VIX Indicator
    @Published var vixValue: Double?
    @Published var vixChange: Double?
    @Published var vixChangePct: Double?
    @Published var vixRegime: String?
    
    // Risk Module: Market Regime
    @Published var marketRegime: String = "normal"
    @Published var regimeConfidence: Double?
    
    // Pipeline Status (Scores Last Updated)
    @Published var scoresLastUpdated: Date?
    @Published var isPipelineRunning: Bool = false
    
    // Loading states
    @Published var isLoading = false
    @Published var errorMessage: String?
    @Published var marketError: String?
    @Published var lastUpdated: Date?
    
    // MARK: - Private
    
    private let api = APIService.shared
    
    // MARK: - Data Loading
    
    func loadData() async {
        isLoading = true
        errorMessage = nil
        
        var loadErrors: [String] = []
        
        // Load in parallel
        await withTaskGroup(of: String?.self) { group in
            group.addTask {
                await self.loadPortfolio()
                return nil
            }
            group.addTask {
                await self.loadMarketIndices()
                return nil
            }
            group.addTask {
                do {
                    try await self.loadTopPicksThrowing()
                    return nil
                } catch {
                    return "Failed to load data: \(error.localizedDescription)"
                }
            }
            group.addTask {
                await self.loadAlerts()
                return nil
            }
            // Risk Module: Load VIX and regime
            group.addTask {
                await self.loadVIX()
                return nil
            }
            group.addTask {
                await self.loadMarketRegime()
                return nil
            }
            // Pipeline Status
            group.addTask {
                await self.loadPipelineStatus()
                return nil
            }
            // GAP-005: Weekly Actions
            group.addTask {
                await self.loadWeeklyActions()
                return nil
            }
            
            for await errorMsg in group {
                if let msg = errorMsg {
                    loadErrors.append(msg)
                }
            }
        }
        
        // Only show error if ALL critical data failed
        if topPicks.isEmpty && !loadErrors.isEmpty {
            errorMessage = loadErrors.first ?? "Unable to load data. Please try again."
        }
        
        lastUpdated = Date()
        isLoading = false
    }
    
    func refresh() async {
        await loadData()
    }
    
    // MARK: - F4.1: Portfolio Summary
    
    private func loadPortfolio() async {
        do {
            let response = try await api.getPortfolio()
            let summary = response.data.summary
            
            portfolioValue = summary.totalValue
            dailyChange = summary.dailyPnl
            dailyChangePercent = summary.dailyPnlPercent
        } catch {
            // Keep existing values on error
            #if DEBUG
            debugError(error, context: "Portfolio load")
            #endif
        }
    }
    
    // MARK: - F4.2: Market Overview
    
    private func loadMarketIndices() async {
        // Bug 3 fix: Use dedicated market indices endpoint for real index values
        // (not ETF proxies like QQQ/DIA which show ~$500 instead of ~23,500/~49,500)
        do {
            let response = try await withTimeout(seconds: 15) {
                try await self.api.getMarketIndices()
            }
            
            var indices: [MarketIndex] = []
            for idx in response.indices {
                indices.append(MarketIndex(
                    symbol: idx.symbol,
                    name: idx.name,
                    value: idx.value,
                    change: idx.change,
                    changePercent: idx.changePercent
                ))
            }
            
            if indices.isEmpty {
                marketError = "Market data unavailable"
            } else {
                marketError = nil
            }
            
            marketIndices = indices
        } catch {
            #if DEBUG
            debugError(error, context: "Market indices load")
            #endif
            
            // Fallback: try macro endpoint for whatever is available
            do {
                let macro = try await withTimeout(seconds: 10) {
                    try await self.api.getMacro()
                }
                
                var indices: [MarketIndex] = []
                if let sp500 = macro.data.indicators["sp500"] {
                    indices.append(MarketIndex(
                        symbol: "SPX",
                        name: "S&P 500",
                        value: sp500.value,
                        change: sp500.change ?? 0,
                        changePercent: sp500.changePercent ?? 0
                    ))
                }
                if let vix = macro.data.indicators["vix"] {
                    indices.append(MarketIndex(
                        symbol: "VIX",
                        name: "VIX",
                        value: vix.value,
                        change: vix.change ?? 0,
                        changePercent: vix.changePercent ?? 0
                    ))
                }
                
                marketIndices = indices
                marketError = indices.isEmpty ? "Market data unavailable" : nil
            } catch {
                marketError = "Market data unavailable"
            }
        }
    }
    
    // MARK: - F4.3: Top AI Picks
    
    private func loadTopPicksThrowing() async throws {
        try await loadTopPicksImpl(throwOnError: true)
    }
    
    private func loadTopPicks() async {
        try? await loadTopPicksImpl(throwOnError: false)
    }
    
    private func loadTopPicksImpl(throwOnError: Bool) async throws {
        // Try to fetch from API first
        var picks: [TopPick] = []
        
        do {
            let response = try await withTimeout(seconds: 10) {
                try await self.api.getScores(limit: 5)
            }
            
            if response.scores.isEmpty {
                throw APIError.httpError(statusCode: 404)
            }
            
            // Always set from scores API (pipeline status may not be reachable)
            if let updatedAt = response.updatedAt {
                scoresLastUpdated = parseDate(updatedAt)
            }
            
            picks = response.scores.map { score in
                TopPick(
                    ticker: score.ticker,
                    name: score.companyName ?? score.ticker,
                    score: Int(score.totalScore),
                    signal: score.signal,
                    price: 0,
                    change: 0,
                    changePercent: 0
                )
            }
        } catch {
            if throwOnError {
                throw error
            }
            #if DEBUG
            debugError(error, context: "Top picks API unavailable, using sample data")
            #endif
            // Fallback sample data (matches ScoresViewModel)
            picks = [
                TopPick(ticker: "NVDA", name: "NVIDIA Corporation", score: 85, signal: "BUY", price: 0, change: 0, changePercent: 0),
                TopPick(ticker: "AAPL", name: "Apple Inc.", score: 78, signal: "BUY", price: 0, change: 0, changePercent: 0),
                TopPick(ticker: "MSFT", name: "Microsoft Corporation", score: 76, signal: "BUY", price: 0, change: 0, changePercent: 0),
                TopPick(ticker: "GOOGL", name: "Alphabet Inc.", score: 74, signal: "BUY", price: 0, change: 0, changePercent: 0),
                TopPick(ticker: "AMZN", name: "Amazon.com Inc.", score: 72, signal: "BUY", price: 0, change: 0, changePercent: 0),
            ]
        }
        
        // Fetch live prices in parallel
        await withTaskGroup(of: (Int, PriceResponse?).self) { group in
            for (index, pick) in picks.enumerated() {
                group.addTask {
                    let price = try? await self.api.getPrice(ticker: pick.ticker)
                    return (index, price)
                }
            }
            
            for await (index, price) in group {
                if let price = price, index < picks.count {
                    picks[index].price = price.price ?? 0
                    picks[index].change = price.change ?? 0
                    picks[index].changePercent = price.changePercent ?? 0
                }
            }
        }
        
        topPicks = picks
    }
    
    // MARK: - F4.4: Alerts Feed
    
    private func loadAlerts() async {
        do {
            let response = try await api.getAlerts()
            alerts = response.data.map { alert in
                AlertItem(
                    id: alert.id,
                    type: AlertType(rawValue: alert.type) ?? .scoreChange,
                    ticker: alert.ticker,
                    title: alert.title,
                    subtitle: alert.subtitle,
                    timestamp: parseDate(alert.timestamp)
                )
            }
        } catch {
            // Show empty alerts on error (no sample data)
            alerts = []
        }
    }
    
    // MARK: - GAP-005: Actions This Week
    
    private func loadWeeklyActions() async {
        var actions: [WeeklyAction] = []
        
        do {
            // Get portfolio holdings
            let portfolio = try await api.getPortfolio()
            let holdingTickers = Set(portfolio.data.holdings.map { $0.ticker })
            
            // Get top scores (potential buys)
            let scores = try await api.getScores(limit: 20)
            
            // Find top BUY signals not in portfolio
            for score in scores.scores.prefix(3) {
                if score.signal == "BUY" && !holdingTickers.contains(score.ticker) {
                    actions.append(WeeklyAction(
                        type: .buy,
                        ticker: score.ticker,
                        companyName: score.companyName ?? score.ticker,
                        score: Int(score.totalScore),
                        reason: "Score \(Int(score.totalScore)) — Strong fundamentals"
                    ))
                }
            }
            
            // Check holdings for SELL signals
            for holding in portfolio.data.holdings {
                if let score = scores.scores.first(where: { $0.ticker == holding.ticker }),
                   score.signal == "SELL" {
                    actions.append(WeeklyAction(
                        type: .sell,
                        ticker: holding.ticker,
                        companyName: score.companyName ?? holding.ticker,
                        score: Int(score.totalScore),
                        reason: "Score \(Int(score.totalScore)) — Consider reducing"
                    ))
                }
            }
            
            weeklyActions = actions
        } catch {
            // Silent fail - actions are optional
            #if DEBUG
            debugError(error, context: "Weekly actions load")
            #endif
        }
    }
    
    // MARK: - Risk Module: VIX
    
    private func loadVIX() async {
        do {
            let response = try await api.getMarketVIX()
            vixValue = response.vix
            vixChange = response.change
            vixChangePct = response.changePct
            vixRegime = response.regime
        } catch {
            // VIX is optional - don't block UI
            #if DEBUG
            debugError(error, context: "VIX load")
            #endif
        }
    }
    
    // MARK: - Risk Module: Market Regime
    
    private func loadMarketRegime() async {
        do {
            let response = try await api.getMarketRegime()
            marketRegime = response.regime
            regimeConfidence = response.confidence
        } catch {
            // Regime is optional - default to normal
            #if DEBUG
            debugError(error, context: "Market regime load")
            #endif
            marketRegime = "normal"
        }
    }
    
    // MARK: - Pipeline Status (Scores Last Updated)
    
    private func loadPipelineStatus() async {
        do {
            let response = try await api.getPipelineStatus()
            isPipelineRunning = response.data.activeRuns > 0
            
            // Parse completed_at from latest run
            if let latest = response.data.latest,
               let completedAt = latest.completedAt {
                scoresLastUpdated = parseDate(completedAt)
            }
        } catch {
            #if DEBUG
            debugError(error, context: "Pipeline status load")
            #endif
        }
    }
    
    private func parseDate(_ isoString: String) -> Date {
        // BUG-027 fix: try with fractional seconds first, then without
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let date = formatter.date(from: isoString) {
            return date
        }
        formatter.formatOptions = [.withInternetDateTime]
        if let date = formatter.date(from: isoString) {
            return date
        }
        // Last resort: try basic date format
        let basic = DateFormatter()
        basic.dateFormat = "yyyy-MM-dd'T'HH:mm:ss"
        basic.timeZone = TimeZone(identifier: "UTC")
        return basic.date(from: isoString) ?? Date()
    }
}

// MARK: - Data Models

struct MarketIndex: Identifiable {
    var id: String { symbol }
    let symbol: String
    let name: String
    var value: Double
    var change: Double
    var changePercent: Double
    
    var isPositive: Bool { change >= 0 }
    
    var formattedValue: String {
        let formatter = NumberFormatter()
        formatter.numberStyle = .decimal
        formatter.groupingSeparator = ","
        formatter.maximumFractionDigits = 2
        formatter.minimumFractionDigits = 2
        return formatter.string(from: NSNumber(value: value)) ?? String(format: "%.2f", value)
    }
    
    var formattedChange: String {
        let prefix = change >= 0 ? "+" : ""
        return "\(prefix)\(String(format: "%.2f", changePercent))%"
    }
}

struct TopPick: Identifiable {
    var id: String { ticker }
    let ticker: String
    let name: String
    let score: Int
    let signal: String
    var price: Double
    var change: Double
    var changePercent: Double
    
    var formattedPrice: String {
        price == 0 ? "—" : price.asCurrency
    }
    
    var formattedChange: String {
        let prefix = changePercent >= 0 ? "+" : ""
        return "\(prefix)\(String(format: "%.1f", changePercent))%"
    }
    
    var isPositive: Bool { changePercent >= 0 }
}

struct AlertItem: Identifiable {
    let id: String
    let type: AlertType
    let ticker: String
    let title: String
    let subtitle: String
    let timestamp: Date
    
    var formattedTime: String {
        let formatter = RelativeDateTimeFormatter()
        formatter.unitsStyle = .abbreviated
        return formatter.localizedString(for: timestamp, relativeTo: Date())
    }
    
    var icon: String {
        switch type {
        case .scoreChange: return "chart.line.uptrend.xyaxis"
        case .signalChange: return "arrow.left.arrow.right"
        case .earnings: return "dollarsign.circle"
        case .news: return "newspaper"
        }
    }
    
    var iconColor: Color {
        switch type {
        case .scoreChange: return .Accent.gold
        case .signalChange: return .Signal.hold
        case .earnings: return .Signal.buy
        case .news: return .Text.secondary
        }
    }
}

enum AlertType: String {
    case scoreChange = "score_change"
    case signalChange = "signal_change"
    case earnings = "earnings"
    case news = "news"
}

// GAP-005: Weekly Action Model
struct WeeklyAction: Identifiable {
    let id = UUID()
    let type: WeeklyActionType
    let ticker: String
    let companyName: String
    let score: Int
    let reason: String
}

enum WeeklyActionType {
    case buy
    case sell
    
    var label: String {
        switch self {
        case .buy: return "BUY"
        case .sell: return "SELL"
        }
    }
    
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

// MARK: - Timeout Helper

struct TimeoutError: Error {}

func withTimeout<T>(seconds: TimeInterval, operation: @escaping () async throws -> T) async throws -> T {
    try await withThrowingTaskGroup(of: T.self) { group in
        group.addTask {
            try await operation()
        }
        group.addTask {
            try await Task.sleep(nanoseconds: UInt64(seconds * 1_000_000_000))
            throw TimeoutError()
        }
        
        guard let result = try await group.next() else {
            throw TimeoutError()
        }
        group.cancelAll()
        return result
    }
}
