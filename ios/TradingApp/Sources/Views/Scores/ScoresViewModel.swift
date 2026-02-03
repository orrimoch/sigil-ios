import Foundation
import SwiftUI

/// ViewModel for Scores Tab (F5.x)
@MainActor
class ScoresViewModel: ObservableObject {
    // MARK: - Published State
    
    @Published var stocks: [StockScoreItem] = []
    @Published var filteredStocks: [StockScoreItem] = []
    
    @Published var searchText = ""
    @Published var selectedSignal: String? = nil
    @Published var selectedSector: String? = nil
    @Published var sortOrder: SortOrder = .scoreDesc
    
    @Published var recentSearches: [String] = []
    
    @Published var isLoading = false
    @Published var errorMessage: String?
    
    @Published var availableSectors: [String] = []
    
    // MARK: - Sort Options
    
    enum SortOrder: String, CaseIterable {
        case scoreDesc = "Score ↓"
        case scoreAsc = "Score ↑"
        case tickerAsc = "Ticker A-Z"
        case tickerDesc = "Ticker Z-A"
        case changeDesc = "Change ↓"
        case changeAsc = "Change ↑"
        
        var comparator: (StockScoreItem, StockScoreItem) -> Bool {
            switch self {
            case .scoreDesc: return { $0.score > $1.score }
            case .scoreAsc: return { $0.score < $1.score }
            case .tickerAsc: return { $0.ticker < $1.ticker }
            case .tickerDesc: return { $0.ticker > $1.ticker }
            case .changeDesc: return { $0.changePercent > $1.changePercent }
            case .changeAsc: return { $0.changePercent < $1.changePercent }
            }
        }
    }
    
    // MARK: - Initialization
    
    init() {
        loadRecentSearches()
    }
    
    // MARK: - Data Loading
    
    func loadData() async {
        isLoading = true
        errorMessage = nil
        
        do {
            let response = try await APIService.shared.getScores(limit: 1000)
            
            // Map to local model — prices are now included in scores response (Bug 2 fix)
            var items: [StockScoreItem] = []
            
            for score in response.scores {
                let item = StockScoreItem(
                    ticker: score.ticker,
                    name: "", // Will be filled from stock info
                    sector: score.sector,
                    score: Int(score.totalScore),
                    signal: score.signal,
                    rank: score.rank,
                    percentile: score.percentile,
                    price: score.price ?? 0,
                    change: score.priceChange ?? 0,
                    changePercent: score.priceChangePercent ?? 0,
                    fundamentalScore: score.fundamentalScore,
                    sentimentScore: score.sentimentScore,
                    technicalScore: score.technicalScore,
                    macroScore: score.macroScore
                )
                items.append(item)
            }
            
            stocks = items
            
            // Extract unique sectors
            availableSectors = Array(Set(stocks.map { $0.sector })).sorted()
            
            // Apply filters
            applyFilters()
            
        } catch {
            errorMessage = error.localizedDescription
            // Use sample data on error
            loadSampleData()
        }
        
        isLoading = false
    }
    
    private func loadSampleData() {
        stocks = [
            StockScoreItem(ticker: "NVDA", name: "NVIDIA Corporation", sector: "Technology", score: 85, signal: "BUY", rank: 1, percentile: 99.5, price: 721.33, change: 22.35, changePercent: 3.2, fundamentalScore: 82, sentimentScore: 88, technicalScore: 85, macroScore: 78),
            StockScoreItem(ticker: "AAPL", name: "Apple Inc.", sector: "Technology", score: 78, signal: "BUY", rank: 5, percentile: 98.0, price: 185.92, change: 2.02, changePercent: 1.1, fundamentalScore: 80, sentimentScore: 75, technicalScore: 78, macroScore: 76),
            StockScoreItem(ticker: "MSFT", name: "Microsoft Corporation", sector: "Technology", score: 76, signal: "BUY", rank: 8, percentile: 97.5, price: 404.72, change: 3.21, changePercent: 0.8, fundamentalScore: 78, sentimentScore: 72, technicalScore: 76, macroScore: 74),
            StockScoreItem(ticker: "GOOGL", name: "Alphabet Inc.", sector: "Technology", score: 74, signal: "BUY", rank: 12, percentile: 96.0, price: 141.80, change: 2.10, changePercent: 1.5, fundamentalScore: 75, sentimentScore: 70, technicalScore: 74, macroScore: 72),
            StockScoreItem(ticker: "AMZN", name: "Amazon.com Inc.", sector: "Consumer Discretionary", score: 72, signal: "BUY", rank: 15, percentile: 95.0, price: 178.25, change: 3.66, changePercent: 2.1, fundamentalScore: 70, sentimentScore: 74, technicalScore: 72, macroScore: 70),
            StockScoreItem(ticker: "META", name: "Meta Platforms Inc.", sector: "Technology", score: 71, signal: "BUY", rank: 18, percentile: 94.0, price: 474.99, change: 2.37, changePercent: 0.5, fundamentalScore: 68, sentimentScore: 75, technicalScore: 70, macroScore: 68),
            StockScoreItem(ticker: "JPM", name: "JPMorgan Chase & Co.", sector: "Financials", score: 65, signal: "HOLD", rank: 45, percentile: 88.0, price: 183.21, change: -0.55, changePercent: -0.3, fundamentalScore: 70, sentimentScore: 60, technicalScore: 62, macroScore: 68),
            StockScoreItem(ticker: "V", name: "Visa Inc.", sector: "Financials", score: 62, signal: "HOLD", rank: 60, percentile: 85.0, price: 275.50, change: 0.55, changePercent: 0.2, fundamentalScore: 65, sentimentScore: 58, technicalScore: 60, macroScore: 62),
            StockScoreItem(ticker: "JNJ", name: "Johnson & Johnson", sector: "Healthcare", score: 58, signal: "HOLD", rank: 80, percentile: 80.0, price: 156.78, change: -0.16, changePercent: -0.1, fundamentalScore: 62, sentimentScore: 52, technicalScore: 55, macroScore: 60),
            StockScoreItem(ticker: "XOM", name: "Exxon Mobil Corporation", sector: "Energy", score: 45, signal: "HOLD", rank: 150, percentile: 65.0, price: 103.45, change: -1.26, changePercent: -1.2, fundamentalScore: 48, sentimentScore: 40, technicalScore: 42, macroScore: 50),
            StockScoreItem(ticker: "T", name: "AT&T Inc.", sector: "Communication Services", score: 35, signal: "SELL", rank: 350, percentile: 25.0, price: 17.23, change: -0.37, changePercent: -2.1, fundamentalScore: 30, sentimentScore: 35, technicalScore: 38, macroScore: 40),
        ]
        availableSectors = Array(Set(stocks.map { $0.sector })).sorted()
        applyFilters()
    }
    
    // MARK: - Filtering & Sorting
    
    func applyFilters() {
        var result = stocks
        
        // Apply search
        if !searchText.isEmpty {
            result = result.filter {
                $0.ticker.localizedCaseInsensitiveContains(searchText) ||
                $0.name.localizedCaseInsensitiveContains(searchText)
            }
        }
        
        // Apply signal filter
        if let signal = selectedSignal {
            result = result.filter { $0.signal == signal }
        }
        
        // Apply sector filter
        if let sector = selectedSector {
            result = result.filter { $0.sector == sector }
        }
        
        // Apply sort
        result.sort(by: sortOrder.comparator)
        
        filteredStocks = result
    }
    
    // MARK: - Search
    
    func search(_ query: String) {
        searchText = query
        applyFilters()
    }
    
    func addToRecentSearches(_ query: String) {
        guard !query.isEmpty else { return }
        
        // Remove if exists, add to front
        recentSearches.removeAll { $0.lowercased() == query.lowercased() }
        recentSearches.insert(query.uppercased(), at: 0)
        
        // Keep only last 10
        if recentSearches.count > 10 {
            recentSearches = Array(recentSearches.prefix(10))
        }
        
        saveRecentSearches()
    }
    
    func clearRecentSearches() {
        recentSearches = []
        saveRecentSearches()
    }
    
    private func loadRecentSearches() {
        recentSearches = UserDefaults.standard.stringArray(forKey: "recentSearches") ?? []
    }
    
    private func saveRecentSearches() {
        UserDefaults.standard.set(recentSearches, forKey: "recentSearches")
    }
    
    // MARK: - Filter Setters
    
    func setSignalFilter(_ signal: String?) {
        selectedSignal = signal
        applyFilters()
    }
    
    func setSectorFilter(_ sector: String?) {
        selectedSector = sector
        applyFilters()
    }
    
    func setSortOrder(_ order: SortOrder) {
        sortOrder = order
        applyFilters()
    }
}

// MARK: - Data Models

struct StockScoreItem: Identifiable {
    var id: String { ticker }
    
    let ticker: String
    let name: String
    let sector: String
    let score: Int
    let signal: String
    let rank: Int
    let percentile: Double
    
    var price: Double
    var change: Double
    var changePercent: Double
    
    let fundamentalScore: Double
    let sentimentScore: Double
    let technicalScore: Double
    let macroScore: Double
    
    var formattedPrice: String {
        price.asCurrency
    }
    
    var formattedChange: String {
        let prefix = changePercent >= 0 ? "+" : ""
        return "\(prefix)\(String(format: "%.1f", changePercent))%"
    }
    
    var isPositive: Bool { changePercent >= 0 }
    
    var signalColor: Color {
        switch signal {
        case "BUY": return .Signal.buy
        case "SELL": return .Signal.sell
        default: return .Signal.hold
        }
    }
}
