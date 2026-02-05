import Foundation
import SwiftUI

/// ViewModel for Stock Detail View (F5.3, F5.4, F5.5)
@MainActor
class StockDetailViewModel: ObservableObject {
    // MARK: - Published State
    
    @Published var ticker: String
    @Published var name: String = ""
    @Published var sector: String = ""
    
    // Price data
    @Published var price: Double = 0
    @Published var change: Double = 0
    @Published var changePercent: Double = 0
    @Published var open: Double = 0
    @Published var high: Double = 0
    @Published var low: Double = 0
    @Published var volume: Int = 0
    @Published var previousClose: Double = 0
    
    // Score data
    @Published var score: Int = 0
    @Published var signal: String = "HOLD"
    @Published var rank: Int = 0
    @Published var percentile: Double = 0
    @Published var explanation: String = ""
    
    // Component scores
    @Published var fundamentalScore: Double = 50
    @Published var sentimentScore: Double = 50
    @Published var technicalScore: Double = 50
    @Published var macroScore: Double = 50
    
    // Score history (F5.5)
    @Published var scoreHistory: [ScoreHistoryPoint] = []
    
    // Price history
    @Published var priceHistory: [PriceHistoryItem] = []
    @Published var priceHistoryUnavailable = false
    
    // Key metrics
    @Published var metrics: [KeyMetric] = []
    
    // News
    @Published var newsSentiment: String = "neutral"
    @Published var newsCount: Int = 0
    
    // State
    @Published var isLoading = false
    @Published var errorMessage: String?
    @Published var selectedChartPeriod: ChartPeriod = .oneMonth
    
    // MARK: - Chart Periods
    
    enum ChartPeriod: String, CaseIterable {
        case oneDay = "1D"
        case oneWeek = "1W"
        case oneMonth = "1M"
        case threeMonths = "3M"
        case oneYear = "1Y"
        case all = "ALL"
        
        var apiPeriod: String {
            switch self {
            case .oneDay: return "1d"
            case .oneWeek: return "5d"
            case .oneMonth: return "1mo"
            case .threeMonths: return "3mo"
            case .oneYear: return "1y"
            case .all: return "max"
            }
        }
    }
    
    // MARK: - Initialization
    
    init(ticker: String) {
        self.ticker = ticker
    }
    
    // MARK: - Data Loading
    
    func loadData() async {
        isLoading = true
        errorMessage = nil
        
        // Load in parallel
        async let priceTask: () = loadPrice()
        async let scoreTask: () = loadScore()
        async let stockTask: () = loadStockInfo()
        async let newsTask: () = loadNews()
        async let historyTask: () = loadScoreHistory()
        async let priceHistoryTask: () = loadPriceHistory()
        
        let _ = await (priceTask, scoreTask, stockTask, newsTask, historyTask, priceHistoryTask)
        
        isLoading = false
    }
    
    private func loadPrice() async {
        do {
            let response = try await APIService.shared.getPrice(ticker: ticker)
            price = response.price ?? 0
            change = response.change ?? 0
            changePercent = response.changePercent ?? 0
            open = response.open ?? 0
            high = response.high ?? 0
            low = response.low ?? 0
            volume = response.volume ?? 0
            previousClose = response.previousClose ?? 0
        } catch {
            // Use sample data
            price = 185.92
            change = 2.02
            changePercent = 1.1
        }
    }
    
    private func loadScore() async {
        do {
            let response = try await APIService.shared.getScore(ticker: ticker)
            let data = response.data
            
            score = Int(data.totalScore)
            signal = data.signal
            rank = data.rank
            percentile = data.percentile
            explanation = data.explanation ?? ""
            
            fundamentalScore = data.fundamentalScore
            sentimentScore = data.sentimentScore
            technicalScore = data.technicalScore
            macroScore = data.macroScore
            sector = data.sector
            
        } catch {
            // Use sample data
            score = 78
            signal = "BUY"
            rank = 5
            percentile = 98.0
            fundamentalScore = 80
            sentimentScore = 75
            technicalScore = 78
            macroScore = 76
            explanation = "Strong fundamentals with positive momentum."
        }
    }
    
    private func loadStockInfo() async {
        do {
            let response = try await APIService.shared.getStock(ticker: ticker)
            name = response.name
            sector = response.sector
            
            // Build metrics
            metrics = [
                KeyMetric(label: "Market Cap", value: formatMarketCap(response.marketCap)),
                KeyMetric(label: "Sector", value: response.sector),
                KeyMetric(label: "Industry", value: response.industry),
            ]
        } catch {
            name = ticker
        }
    }
    
    private func loadNews() async {
        do {
            let response = try await APIService.shared.getNews(ticker: ticker)
            newsSentiment = response.data.sentiment.label
            newsCount = response.data.articleCount
        } catch {
            newsSentiment = "neutral"
            newsCount = 0
        }
    }
    
    private func loadScoreHistory() async {
        do {
            let response = try await APIService.shared.getScoreHistory(symbol: ticker, days: 90)
            
            let isoFormatter = ISO8601DateFormatter()
            isoFormatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
            
            let history: [ScoreHistoryPoint] = response.data.history.compactMap { item in
                // Try ISO8601 first, then fallback to simple date
                var date: Date?
                date = isoFormatter.date(from: item.date)
                if date == nil {
                    let dateFormatter = DateFormatter()
                    dateFormatter.dateFormat = "yyyy-MM-dd"
                    date = dateFormatter.date(from: String(item.date.prefix(10)))
                }
                guard let validDate = date else { return nil }
                return ScoreHistoryPoint(date: validDate, score: item.score, signal: item.signal)
            }
            
            if !history.isEmpty {
                scoreHistory = history
            } else {
                // API returned empty — show current score as single data point
                fallbackToCurrentScore()
            }
        } catch {
            // API unavailable — fall back to showing just the current score
            print("Score history API error: \(error)")
            fallbackToCurrentScore()
        }
    }
    
    func loadPriceHistory() async {
        do {
            let response = try await APIService.shared.getPriceHistory(symbol: ticker, period: selectedChartPeriod.apiPeriod)
            
            let dateFormatter = DateFormatter()
            dateFormatter.dateFormat = "yyyy-MM-dd"
            
            let items: [PriceHistoryItem] = response.data.prices.compactMap { point in
                guard let date = dateFormatter.date(from: point.date) else { return nil }
                return PriceHistoryItem(date: date, close: point.close, volume: point.volume)
            }
            
            if !items.isEmpty {
                priceHistory = items
                priceHistoryUnavailable = false
            } else {
                priceHistoryUnavailable = true
            }
        } catch {
            print("Price history API error: \(error)")
            priceHistoryUnavailable = true
        }
    }
    
    private func fallbackToCurrentScore() {
        let currentScore = Double(score)
        let sig: String
        if currentScore >= 70 { sig = "BUY" }
        else if currentScore >= 40 { sig = "HOLD" }
        else { sig = "SELL" }
        scoreHistory = [ScoreHistoryPoint(date: Date(), score: currentScore, signal: sig)]
    }
    
    // MARK: - Helpers
    
    private func formatMarketCap(_ value: Int) -> String {
        let trillion = 1_000_000_000_000
        let billion = 1_000_000_000
        let million = 1_000_000
        
        if value >= trillion {
            return "$\(String(format: "%.2f", Double(value) / Double(trillion)))T"
        } else if value >= billion {
            return "$\(String(format: "%.1f", Double(value) / Double(billion)))B"
        } else if value >= million {
            return "$\(String(format: "%.0f", Double(value) / Double(million)))M"
        }
        return "$\(value)"
    }
    
    var signalColor: Color {
        switch signal {
        case "BUY": return .Signal.buy
        case "SELL": return .Signal.sell
        default: return .Signal.hold
        }
    }
    
    var isPositive: Bool { changePercent >= 0 }
}

// MARK: - Data Models

struct ScoreHistoryPoint: Identifiable {
    var id: Date { date }
    let date: Date
    let score: Double
    let signal: String
    
    var signalChanged: Bool {
        // Would compare with previous point
        false
    }
}

struct KeyMetric: Identifiable {
    var id: String { label }
    let label: String
    let value: String
}

struct PriceHistoryItem: Identifiable {
    var id: Date { date }
    let date: Date
    let close: Double
    let volume: Int
}
