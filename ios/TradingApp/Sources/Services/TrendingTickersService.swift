import Foundation

// MARK: - REC-259: Trending Tickers Cache Service
// Caches Reddit trending tickers for badge display across the app

@MainActor
class TrendingTickersService: ObservableObject {
    static let shared = TrendingTickersService()
    
    @Published private(set) var trendingTickers: Set<String> = []
    @Published private(set) var tickerData: [String: SmartMoneyPick] = [:]
    @Published private(set) var lastUpdated: Date?
    @Published private(set) var isLoading = false
    
    private let cacheKey = "trendingTickersCache"
    private let cacheExpiryMinutes: Double = 15
    
    private init() {
        loadFromCache()
    }
    
    // MARK: - Public API
    
    /// Check if a ticker is currently trending on Reddit
    func isTrending(_ ticker: String) -> Bool {
        trendingTickers.contains(ticker.uppercased())
    }
    
    /// Get trending data for a specific ticker (if available)
    func getTrendingData(_ ticker: String) -> SmartMoneyPick? {
        tickerData[ticker.uppercased()]
    }
    
    /// Refresh trending data from API
    func refresh() async {
        guard !isLoading else { return }
        
        isLoading = true
        defer { isLoading = false }
        
        do {
            let response = try await APIService.shared.getSmartMoneyPicks()
            
            // Update cache
            var newTickerSet: Set<String> = []
            var newTickerData: [String: SmartMoneyPick] = [:]
            
            for pick in response.picks {
                let ticker = pick.ticker.uppercased()
                newTickerSet.insert(ticker)
                newTickerData[ticker] = pick
            }
            
            trendingTickers = newTickerSet
            tickerData = newTickerData
            lastUpdated = Date()
            
            saveToCache()
            
            #if DEBUG
            debugLog("[TrendingTickers] Refreshed: \(trendingTickers.count) trending tickers")
            #endif
        } catch {
            #if DEBUG
            debugError(error, context: "[TrendingTickers] Refresh failed")
            #endif
        }
    }
    
    // MARK: - Cache Management
    
    private func loadFromCache() {
        guard let data = UserDefaults.standard.data(forKey: cacheKey),
              let cache = try? JSONDecoder().decode(TrendingCache.self, from: data),
              let lastUpdate = cache.lastUpdated,
              Date().timeIntervalSince(lastUpdate) < cacheExpiryMinutes * 60 else {
            // Cache expired or missing, load fresh
            Task { await refresh() }
            return
        }
        
        trendingTickers = Set(cache.tickers)
        tickerData = cache.tickerData
        lastUpdated = lastUpdate
        
        #if DEBUG
        debugLog("[TrendingTickers] Loaded from cache: \(trendingTickers.count) tickers")
        #endif
    }
    
    private func saveToCache() {
        let cache = TrendingCache(
            tickers: Array(trendingTickers),
            tickerData: tickerData,
            lastUpdated: lastUpdated
        )
        
        if let data = try? JSONEncoder().encode(cache) {
            UserDefaults.standard.set(data, forKey: cacheKey)
        }
    }
}

// MARK: - Cache Model

private struct TrendingCache: Codable {
    let tickers: [String]
    let tickerData: [String: SmartMoneyPick]
    let lastUpdated: Date?
}
