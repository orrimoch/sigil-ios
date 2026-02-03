import Foundation

/// API Service for communicating with Sigil backend
/// Includes disk caching for persistence across app launches
class APIService: ObservableObject {
    static let shared = APIService()
    
    // Backend URL - localhost works in iOS Simulator (shared network stack)
    private let baseURL = "http://127.0.0.1:8000/api/v1"
    
    private let decoder: JSONDecoder = {
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        return decoder
    }()
    
    // MARK: - Disk Cache
    
    private let cacheDir: URL = {
        let dir = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("SigilAPICache")
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir
    }()
    
    /// Default cache TTL: 30 minutes
    private let defaultTTL: TimeInterval = 30 * 60
    
    private func cacheKey(for url: URL) -> String {
        url.absoluteString
            .replacingOccurrences(of: baseURL, with: "")
            .replacingOccurrences(of: "/", with: "_")
            .replacingOccurrences(of: "?", with: "_")
            .replacingOccurrences(of: "&", with: "_")
            .replacingOccurrences(of: "=", with: "_")
    }
    
    private func loadFromCache<T: Decodable>(_ url: URL, maxAge: TimeInterval? = nil) -> T? {
        let key = cacheKey(for: url)
        let file = cacheDir.appendingPathComponent("\(key).json")
        
        guard FileManager.default.fileExists(atPath: file.path) else { return nil }
        
        // Check age if maxAge specified
        if let maxAge = maxAge,
           let attrs = try? FileManager.default.attributesOfItem(atPath: file.path),
           let modified = attrs[.modificationDate] as? Date,
           Date().timeIntervalSince(modified) > maxAge {
            return nil // Cache expired
        }
        
        guard let data = try? Data(contentsOf: file) else { return nil }
        return try? decoder.decode(T.self, from: data)
    }
    
    private func saveToCache(_ data: Data, for url: URL) {
        let key = cacheKey(for: url)
        let file = cacheDir.appendingPathComponent("\(key).json")
        try? data.write(to: file)
    }
    
    // MARK: - Stocks
    
    func getStocks(sector: String? = nil, limit: Int = 100) async throws -> StocksResponse {
        var components = URLComponents(string: "\(baseURL)/stocks")!
        var queryItems: [URLQueryItem] = [URLQueryItem(name: "limit", value: String(limit))]
        if let sector = sector {
            queryItems.append(URLQueryItem(name: "sector", value: sector))
        }
        components.queryItems = queryItems
        
        return try await fetch(components.url!)
    }
    
    func getStock(ticker: String) async throws -> StockResponse {
        let url = URL(string: "\(baseURL)/stocks/\(ticker)")!
        return try await fetch(url)
    }
    
    // MARK: - Scores
    
    func getScores(signal: String? = nil, limit: Int = 50) async throws -> ScoresResponse {
        var components = URLComponents(string: "\(baseURL)/scores")!
        var queryItems: [URLQueryItem] = [URLQueryItem(name: "limit", value: String(limit))]
        if let signal = signal {
            queryItems.append(URLQueryItem(name: "signal", value: signal))
        }
        components.queryItems = queryItems
        
        return try await fetch(components.url!)
    }
    
    func getScore(ticker: String) async throws -> ScoreDetailResponse {
        let url = URL(string: "\(baseURL)/scores/\(ticker)")!
        return try await fetch(url)
    }
    
    func getTopScores(n: Int, signal: String = "BUY") async throws -> TopScoresResponse {
        let url = URL(string: "\(baseURL)/scores/top/\(n)?signal=\(signal)")!
        return try await fetch(url)
    }
    
    // MARK: - Score Summary (F9.1)
    
    func getScoreSummary() async throws -> ScoreSummaryResponse {
        let url = URL(string: "\(baseURL)/scores/summary")!
        return try await fetch(url)
    }
    
    // MARK: - Score History
    
    func getScoreHistory(symbol: String, days: Int = 30) async throws -> ScoreHistoryResponse {
        let url = URL(string: "\(baseURL)/scores/\(symbol)/history?days=\(days)")!
        return try await fetch(url)
    }
    
    // MARK: - Market Indices
    
    func getMarketIndices() async throws -> MarketIndicesResponse {
        let url = URL(string: "\(baseURL)/market/indices")!
        return try await fetch(url)
    }
    
    // MARK: - Prices
    
    func getPrice(ticker: String) async throws -> PriceResponse {
        let url = URL(string: "\(baseURL)/prices/\(ticker)")!
        return try await fetch(url)
    }
    
    // MARK: - Price History
    
    func getPriceHistory(symbol: String, period: String = "3m") async throws -> PriceHistoryResponse {
        let url = URL(string: "\(baseURL)/data/price-history/\(symbol)?period=\(period)")!
        return try await fetch(url)
    }
    
    // MARK: - News
    
    func getNews(ticker: String) async throws -> NewsResponse {
        let url = URL(string: "\(baseURL)/news/\(ticker)")!
        return try await fetch(url)
    }
    
    // MARK: - Macro
    
    func getMacro() async throws -> MacroResponse {
        let url = URL(string: "\(baseURL)/macro")!
        return try await fetch(url)
    }
    
    // MARK: - Portfolio
    
    func getPortfolio() async throws -> PortfolioResponse {
        let url = URL(string: "\(baseURL)/portfolio")!
        return try await fetch(url)
    }
    
    func resetPortfolio(startingCash: Double = 100000) async throws -> [String: Any] {
        let url = URL(string: "\(baseURL)/portfolio/reset?starting_cash=\(startingCash)")!
        return try await post(url, body: nil)
    }
    
    func getPortfolioHistory(days: Int = 30) async throws -> PortfolioHistoryResponse {
        let url = URL(string: "\(baseURL)/portfolio/history?days=\(days)")!
        return try await fetch(url)
    }
    
    func getPortfolioPerformance(days: Int = 30) async throws -> PortfolioPerformanceResponse {
        let url = URL(string: "\(baseURL)/portfolio/performance?days=\(days)")!
        return try await fetch(url)
    }
    
    func getSectorAllocation() async throws -> SectorAllocationResponse {
        let url = URL(string: "\(baseURL)/portfolio/sectors")!
        return try await fetch(url)
    }
    
    func recordPortfolioSnapshot() async throws -> [String: Any] {
        let url = URL(string: "\(baseURL)/portfolio/snapshot")!
        return try await post(url, body: nil)
    }
    
    // MARK: - Alerts
    
    func getAlerts(limit: Int = 20) async throws -> AlertsResponse {
        let url = URL(string: "\(baseURL)/alerts?limit=\(limit)")!
        return try await fetch(url)
    }
    
    func getRecentAlerts(hours: Int = 24) async throws -> AlertsResponse {
        let url = URL(string: "\(baseURL)/alerts/recent?hours=\(hours)")!
        return try await fetch(url)
    }
    
    // MARK: - Orders
    
    func getOrders(status: String? = nil, limit: Int = 50) async throws -> OrdersResponse {
        var components = URLComponents(string: "\(baseURL)/orders")!
        var queryItems: [URLQueryItem] = [URLQueryItem(name: "limit", value: String(limit))]
        if let status = status {
            queryItems.append(URLQueryItem(name: "status", value: status))
        }
        components.queryItems = queryItems
        return try await fetch(components.url!)
    }
    
    func getTodaysOrders() async throws -> OrdersResponse {
        let url = URL(string: "\(baseURL)/orders/today")!
        return try await fetch(url)
    }
    
    func createOrder(ticker: String, side: String, quantity: Double, orderType: String = "MARKET", limitPrice: Double? = nil) async throws -> OrderResponse {
        let url = URL(string: "\(baseURL)/orders")!
        var body: [String: Any] = [
            "ticker": ticker,
            "side": side,
            "quantity": quantity,
            "order_type": orderType
        ]
        if let limitPrice = limitPrice {
            body["limit_price"] = limitPrice
        }
        
        var request = authorizedRequest(url: url, method: "POST")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        
        let (data, response) = try await dataWithAutoRefresh(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse, 200...299 ~= httpResponse.statusCode else {
            if let httpResponse = response as? HTTPURLResponse {
                throw APIError.httpError(statusCode: httpResponse.statusCode)
            }
            throw APIError.invalidResponse
        }
        
        return try decoder.decode(OrderResponse.self, from: data)
    }
    
    func cancelOrder(orderId: String) async throws -> OrderResponse {
        let url = URL(string: "\(baseURL)/orders/\(orderId)")!
        
        var request = authorizedRequest(url: url, method: "DELETE")
        
        let (data, response) = try await dataWithAutoRefresh(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse, 200...299 ~= httpResponse.statusCode else {
            if let httpResponse = response as? HTTPURLResponse {
                throw APIError.httpError(statusCode: httpResponse.statusCode)
            }
            throw APIError.invalidResponse
        }
        
        return try decoder.decode(OrderResponse.self, from: data)
    }
    
    // MARK: - Auth header injection

    /// Build a URLRequest with the current Bearer token attached (if available).
    private func authorizedRequest(url: URL, method: String = "GET") -> URLRequest {
        var request = URLRequest(url: url)
        request.httpMethod = method
        if let token = AuthService.shared.accessToken {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        return request
    }

    /// Perform a data task, and if we get a 401 try refreshing the token once.
    private func dataWithAutoRefresh(for request: URLRequest) async throws -> (Data, URLResponse) {
        let (data, response) = try await URLSession.shared.data(for: request)

        guard let http = response as? HTTPURLResponse else {
            return (data, response)
        }

        if http.statusCode == 401 {
            // Try token refresh
            do {
                let newToken = try await AuthService.shared.refreshToken()
                var retry = request
                retry.setValue("Bearer \(newToken)", forHTTPHeaderField: "Authorization")
                return try await URLSession.shared.data(for: retry)
            } catch {
                // Refresh failed — force logout
                await MainActor.run { AuthService.shared.logout() }
                throw APIError.httpError(statusCode: 401)
            }
        }

        return (data, response)
    }

    // MARK: - Private Helpers (POST)
    
    private func post(_ url: URL, body: Data?) async throws -> [String: Any] {
        var request = authorizedRequest(url: url, method: "POST")
        if let body = body {
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.httpBody = body
        }
        
        let (data, response) = try await dataWithAutoRefresh(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse, 200...299 ~= httpResponse.statusCode else {
            if let httpResponse = response as? HTTPURLResponse {
                throw APIError.httpError(statusCode: httpResponse.statusCode)
            }
            throw APIError.invalidResponse
        }
        
        return try JSONSerialization.jsonObject(with: data) as? [String: Any] ?? [:]
    }
    
    // MARK: - Private Helpers
    
    private func fetch<T: Decodable>(_ url: URL) async throws -> T {
        do {
            let request = authorizedRequest(url: url)
            let (data, response) = try await dataWithAutoRefresh(for: request)
            
            guard let httpResponse = response as? HTTPURLResponse else {
                throw APIError.invalidResponse
            }
            
            guard 200...299 ~= httpResponse.statusCode else {
                throw APIError.httpError(statusCode: httpResponse.statusCode)
            }
            
            // Cache the raw response data on success
            saveToCache(data, for: url)
            
            return try decoder.decode(T.self, from: data)
        } catch {
            // Network failed — try to serve from disk cache (any age)
            if let cached: T = loadFromCache(url, maxAge: nil) {
                return cached
            }
            throw error
        }
    }
    
    /// Fetch with cache-first strategy: returns cached data immediately if available,
    /// then refreshes in background. Use for data that doesn't change often.
    func fetchCached<T: Decodable>(_ url: URL, maxAge: TimeInterval? = nil) async throws -> T {
        // Try cache first
        if let cached: T = loadFromCache(url, maxAge: maxAge ?? defaultTTL) {
            return cached
        }
        // Cache miss or expired — fetch from network
        return try await fetch(url)
    }
}

// MARK: - API Errors

enum APIError: Error, LocalizedError {
    case invalidResponse
    case httpError(statusCode: Int)
    case decodingError(Error)
    
    var errorDescription: String? {
        switch self {
        case .invalidResponse:
            return "Invalid response from server"
        case .httpError(let statusCode):
            return "HTTP error: \(statusCode)"
        case .decodingError(let error):
            return "Decoding error: \(error.localizedDescription)"
        }
    }
}

// MARK: - Response Models

struct StocksResponse: Codable {
    let success: Bool
    let count: Int
    let stocks: [Stock]
}

struct StockResponse: Codable {
    let ticker: String
    let name: String
    let sector: String
    let industry: String
    let marketCap: Int
}

struct Stock: Codable, Identifiable {
    var id: String { ticker }
    let ticker: String
    let name: String
    let sector: String
    let industry: String
    let marketCap: Int
}

struct ScoresResponse: Codable {
    let success: Bool
    let count: Int
    let scores: [StockScore]
}

struct TopScoresResponse: Codable {
    let success: Bool
    let count: Int
    let scores: [StockScore]
}

struct ScoreDetailResponse: Codable {
    let success: Bool
    let data: StockScoreDetail
}

struct StockScore: Codable, Identifiable {
    var id: String { ticker }
    let ticker: String
    let companyName: String?
    let sector: String
    let totalScore: Double
    let signal: String
    let rank: Int
    let percentile: Double
    let fundamentalScore: Double
    let sentimentScore: Double
    let technicalScore: Double
    let macroScore: Double
    // Price data included in scores response (Bug 2 fix)
    var price: Double?
    var priceChange: Double?
    var priceChangePercent: Double?
}

struct StockScoreDetail: Codable {
    let ticker: String
    let sector: String
    let totalScore: Double
    let signal: String
    let rank: Int
    let percentile: Double
    let fundamentalScore: Double
    let sentimentScore: Double
    let technicalScore: Double
    let macroScore: Double
    let explanation: String?
}

struct PriceResponse: Codable {
    let ticker: String
    let price: Double?
    let open: Double?
    let high: Double?
    let low: Double?
    let volume: Int?
    let previousClose: Double?
    let change: Double?
    let changePercent: Double?
}

struct NewsResponse: Codable {
    let success: Bool
    let data: NewsData
}

struct NewsData: Codable {
    let ticker: String
    let articleCount: Int
    let sentiment: NewsSentiment
    let articles: [NewsArticle]
}

struct NewsSentiment: Codable {
    let score: Double
    let label: String
    let positiveCount: Int
    let negativeCount: Int
    let neutralCount: Int
}

struct NewsArticle: Codable, Identifiable {
    var id: String { link }
    let source: String
    let title: String
    let link: String
    let published: String?
}

struct MacroResponse: Codable {
    let success: Bool
    let data: MacroData
}

struct MacroData: Codable {
    let indicators: [String: MacroIndicator]
    let score: MacroScore
}

struct MacroIndicator: Codable {
    let value: Double
    let date: String
    let change: Double?
    let changePercent: Double?
}

struct MacroScore: Codable {
    let score: Double
    let regime: String
}

// MARK: - Portfolio Response Models

struct PortfolioResponse: Codable {
    let success: Bool
    let data: PortfolioData
}

struct PortfolioData: Codable {
    let summary: PortfolioSummary
    let holdings: [Holding]
    let isPaper: Bool
    let realizedPnl: Double
}

struct PortfolioSummary: Codable {
    let totalValue: Double
    let cash: Double
    let positionsValue: Double
    let totalPnl: Double
    let totalPnlPercent: Double
    let dailyPnl: Double
    let dailyPnlPercent: Double
    let positionsCount: Int
}

struct Holding: Codable, Identifiable {
    var id: String { ticker }
    let ticker: String
    let shares: Double
    let avgCost: Double
    let currentPrice: Double
    let marketValue: Double
    let costBasis: Double
    let unrealizedPnl: Double
    let unrealizedPnlPercent: Double
    let openedAt: String
}

// MARK: - F7.2 Portfolio History

struct PortfolioHistoryResponse: Codable {
    let success: Bool
    let count: Int
    let days: Int
    let data: [PortfolioSnapshot]
}

struct PortfolioSnapshot: Codable, Identifiable {
    var id: String { timestamp }
    let timestamp: String
    let totalValue: Double
    let cash: Double
    let positionsValue: Double
    let totalPnl: Double
    let totalPnlPercent: Double
}

struct PortfolioPerformanceResponse: Codable {
    let success: Bool
    let data: PortfolioPerformance
}

struct PortfolioPerformance: Codable {
    let periodDays: Int
    let startValue: Double?
    let endValue: Double?
    let change: Double?
    let changePercent: Double?
    let dataPoints: Int?
}

// MARK: - F7.3 Sector Allocation

struct SectorAllocationResponse: Codable {
    let success: Bool
    let count: Int
    let data: [SectorAllocation]
}

struct SectorAllocation: Codable, Identifiable {
    var id: String { sector }
    let sector: String
    let value: Double
    let percentage: Double
}

// MARK: - F4.4 Alerts

struct AlertsResponse: Codable {
    let success: Bool
    let count: Int
    let data: [AlertData]
}

struct AlertData: Codable, Identifiable {
    var id: String
    let type: String
    let ticker: String
    let title: String
    let subtitle: String
    let timestamp: String
    let read: Bool
}

// MARK: - Order Response Models

struct OrdersResponse: Codable {
    let success: Bool
    let count: Int
    let data: [OrderData]
}

struct OrderResponse: Codable {
    let success: Bool
    let data: OrderData
}

struct OrderData: Codable, Identifiable {
    var id: String { orderId }
    let orderId: String
    let ticker: String
    let side: String
    let orderType: String
    let quantity: Double
    let limitPrice: Double?
    let status: String
    let filledQuantity: Double
    let filledPrice: Double?
    let createdAt: String
    let updatedAt: String
    let filledAt: String?
    let rejectReason: String?
    let isPaper: Bool
}

// MARK: - Score Summary Response (F9.1)

struct ScoreSummaryResponse: Codable {
    let success: Bool
    let data: ScoreSummaryData?
}

struct ScoreSummaryData: Codable {
    let buyCount: Int
    let holdCount: Int
    let sellCount: Int
    let totalScored: Int
    let signalChanges: Int
    let topMovers: [ScoreMover]
    let newBuySignals: [NewBuySignal]
    let updatedAt: String?
}

struct ScoreMover: Codable {
    let ticker: String
    let score: Double
    let signal: String
    let scoreChange: Double
    let signalChange: String?
}

struct NewBuySignal: Codable {
    let ticker: String
    let score: Double
    let previousSignal: String?
}

// MARK: - Score History Response Models

struct ScoreHistoryResponse: Codable {
    let success: Bool
    let data: [ScoreHistoryData]
}

struct ScoreHistoryData: Codable {
    let date: String
    let score: Double
}

// MARK: - Price History Response Models

struct PriceHistoryResponse: Codable {
    let success: Bool
    let data: PriceHistoryData
}

struct PriceHistoryData: Codable {
    let symbol: String
    let period: String
    let prices: [PricePoint]
}

struct PricePoint: Codable {
    let date: String
    let open: Double
    let high: Double
    let low: Double
    let close: Double
    let volume: Int
}

// MARK: - Market Indices Response

struct MarketIndicesResponse: Codable {
    let success: Bool
    let count: Int
    let indices: [MarketIndexData]
}

struct MarketIndexData: Codable {
    let symbol: String
    let name: String
    let value: Double
    let change: Double
    let changePercent: Double
}
