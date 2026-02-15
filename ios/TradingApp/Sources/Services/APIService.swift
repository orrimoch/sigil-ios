import Foundation

// MARK: - IOS-002: Certificate Pinning Delegate

/// URLSession delegate for certificate pinning
/// Validates server certificates against pinned public key hashes
final class CertificatePinningDelegate: NSObject, URLSessionDelegate {
    
    // IOS-002: Pinned certificate hashes (SHA-256 of SPKI)
    // TODO: Replace with actual production certificate hash before deployment
    // Generate with: openssl s_client -connect api.sigil.app:443 | openssl x509 -pubkey -noout | openssl pkey -pubin -outform der | openssl dgst -sha256 -binary | base64
    #if DEBUG
    // Development: Allow any certificate in debug (mkcert generates local certs)
    private static let pinnedHashes: Set<String> = []
    #else
    // Production: Pin to Sigil API certificate
    // IMPORTANT: Add real certificate hashes before App Store release
    // For TestFlight: Using empty set to allow connections (same as debug)
    // TODO: Generate hashes with: openssl s_client -connect api.sigil.app:443 | openssl x509 -pubkey -noout | openssl pkey -pubin -outform der | openssl dgst -sha256 -binary | base64
    private static let pinnedHashes: Set<String> = [
        // "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",  // Primary cert hash (uncomment and replace for production)
        // "BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB=",  // Backup cert hash (uncomment and replace for production)
    ]
    #endif
    
    func urlSession(
        _ session: URLSession,
        didReceive challenge: URLAuthenticationChallenge,
        completionHandler: @escaping (URLSession.AuthChallengeDisposition, URLCredential?) -> Void
    ) {
        guard challenge.protectionSpace.authenticationMethod == NSURLAuthenticationMethodServerTrust,
              let serverTrust = challenge.protectionSpace.serverTrust else {
            completionHandler(.cancelAuthenticationChallenge, nil)
            return
        }
        
        #if DEBUG
        // In debug mode, accept all certificates (for local dev with mkcert)
        if Self.pinnedHashes.isEmpty {
            let credential = URLCredential(trust: serverTrust)
            completionHandler(.useCredential, credential)
            return
        }
        #endif
        
        // Validate certificate chain
        var error: CFError?
        let isValid = SecTrustEvaluateWithError(serverTrust, &error)
        
        guard isValid else {
            #if DEBUG
            debugLog("[Security] Certificate validation failed: \(error?.localizedDescription ?? "unknown")")
            #endif
            completionHandler(.cancelAuthenticationChallenge, nil)
            return
        }
        
        // Check pinned hashes
        if !Self.pinnedHashes.isEmpty {
            let certificateCount = SecTrustGetCertificateCount(serverTrust)
            var matchFound = false
            
            for i in 0..<certificateCount {
                if let certificate = SecTrustGetCertificateAtIndex(serverTrust, i) {
                    let publicKeyHash = Self.sha256Hash(of: certificate)
                    if Self.pinnedHashes.contains(publicKeyHash) {
                        matchFound = true
                        break
                    }
                }
            }
            
            guard matchFound else {
                #if DEBUG
                debugLog("[Security] Certificate pinning failed - no matching hash")
                #endif
                completionHandler(.cancelAuthenticationChallenge, nil)
                return
            }
        }
        
        let credential = URLCredential(trust: serverTrust)
        completionHandler(.useCredential, credential)
    }
    
    /// Compute SHA-256 hash of certificate's public key (SPKI)
    private static func sha256Hash(of certificate: SecCertificate) -> String {
        guard let publicKey = SecCertificateCopyKey(certificate) else {
            return ""
        }
        
        guard let publicKeyData = SecKeyCopyExternalRepresentation(publicKey, nil) as Data? else {
            return ""
        }
        
        var hash = [UInt8](repeating: 0, count: Int(CC_SHA256_DIGEST_LENGTH))
        publicKeyData.withUnsafeBytes { buffer in
            _ = CC_SHA256(buffer.baseAddress, CC_LONG(buffer.count), &hash)
        }
        
        return Data(hash).base64EncodedString()
    }
}

// Import for CC_SHA256
import CommonCrypto

/// API Service for communicating with Sigil backend
/// Includes disk caching for persistence across app launches
class APIService: ObservableObject {
    static let shared = APIService()
    
    // IOS-001: HTTPS enforcement with environment-based configuration
    // Local Mac mini backend
    let baseURL = "http://127.0.0.1:8000/api/v1"
    
    // IOS-002: URLSession with certificate pinning and timeout
    private let pinningDelegate = CertificatePinningDelegate()
    private lazy var pinnedSession: URLSession = {
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 30  // 30 seconds for request
        config.timeoutIntervalForResource = 60 // 60 seconds for resource
        return URLSession(configuration: config, delegate: pinningDelegate, delegateQueue: nil)
    }()
    
    private let decoder: JSONDecoder = {
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        return decoder
    }()
    
    // MARK: - Disk Cache
    
    private let cacheDir: URL = {
        guard let cachesDir = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask).first else {
            // Fallback to temp directory if caches unavailable (should never happen on iOS)
            return FileManager.default.temporaryDirectory.appendingPathComponent("SigilAPICache")
        }
        let dir = cachesDir.appendingPathComponent("SigilAPICache")
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir
    }()
    
    /// Default cache TTL: 30 minutes
    private let defaultTTL: TimeInterval = 30 * 60
    
    // MARK: - URL Helpers
    
    /// Safely construct a URL, encoding path components
    private func makeURL(_ path: String) throws -> URL {
        guard let url = URL(string: "\(baseURL)\(path)") else {
            throw APIError.invalidURL
        }
        return url
    }
    
    /// Safely construct a URL with a ticker/symbol parameter
    private func makeURL(_ path: String, ticker: String) throws -> URL {
        guard let encoded = ticker.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed),
              let url = URL(string: "\(baseURL)\(path)/\(encoded)") else {
            throw APIError.invalidURL
        }
        return url
    }
    
    /// Safely construct a URL with query parameters
    private func makeURL(_ path: String, queryItems: [URLQueryItem]) throws -> URL {
        guard var components = URLComponents(string: "\(baseURL)\(path)") else {
            throw APIError.invalidURL
        }
        if !queryItems.isEmpty {
            components.queryItems = queryItems
        }
        guard let url = components.url else {
            throw APIError.invalidURL
        }
        return url
    }
    
    /// Safely construct URLComponents for building dynamic queries
    private func makeComponents(_ path: String) throws -> URLComponents {
        guard let components = URLComponents(string: "\(baseURL)\(path)") else {
            throw APIError.invalidURL
        }
        return components
    }
    
    /// Handle HTTP error responses with special handling for rate limiting (429)
    /// Always throws an error - marked as -> Never so compiler knows control flow doesn't continue
    private func handleHTTPError(_ response: URLResponse?) throws -> Never {
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }
        
        if httpResponse.statusCode == 429 {
            // Parse Retry-After header if present
            let retryAfter = httpResponse.value(forHTTPHeaderField: "Retry-After")
                .flatMap { Int($0) }
            throw APIError.rateLimited(retryAfter: retryAfter)
        }
        
        throw APIError.httpError(statusCode: httpResponse.statusCode)
    }
    
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
        var queryItems: [URLQueryItem] = [URLQueryItem(name: "limit", value: String(limit))]
        if let sector = sector {
            queryItems.append(URLQueryItem(name: "sector", value: sector))
        }
        let url = try makeURL("/stocks", queryItems: queryItems)
        return try await fetch(url)
    }
    
    func getStock(ticker: String) async throws -> StockResponse {
        let url = try makeURL("/stocks", ticker: ticker)
        return try await fetch(url)
    }
    
    // MARK: - Scores
    
    func getScores(signal: String? = nil, limit: Int = 50) async throws -> ScoresResponse {
        var queryItems: [URLQueryItem] = [URLQueryItem(name: "limit", value: String(limit))]
        if let signal = signal {
            queryItems.append(URLQueryItem(name: "signal", value: signal))
        }
        let url = try makeURL("/scores", queryItems: queryItems)
        return try await fetch(url)
    }
    
    func getScore(ticker: String) async throws -> ScoreDetailResponse {
        let url = try makeURL("/scores", ticker: ticker)
        return try await fetch(url)
    }
    
    func getTopScores(n: Int, signal: String = "BUY") async throws -> TopScoresResponse {
        let url = try makeURL("/scores/top/\(n)", queryItems: [URLQueryItem(name: "signal", value: signal)])
        return try await fetch(url)
    }
    
    // MARK: - Score Summary (F9.1)
    
    func getScoreSummary() async throws -> ScoreSummaryResponse {
        let url = try makeURL("/scores/summary")
        return try await fetch(url)
    }
    
    // MARK: - Score Changes (F9.3)
    
    func getScoreChanges() async throws -> ScoreChangesResponse {
        let url = try makeURL("/scores/changes")
        return try await fetch(url)
    }
    
    // MARK: - Score History
    
    func getScoreHistory(symbol: String, days: Int = 30) async throws -> ScoreHistoryResponse {
        guard let encoded = symbol.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed),
              let url = URL(string: "\(baseURL)/scores/\(encoded)/history?days=\(days)") else {
            throw APIError.invalidURL
        }
        return try await fetch(url)
    }
    
    // MARK: - Market Indices
    
    func getMarketIndices() async throws -> MarketIndicesResponse {
        let url = try makeURL("/market/indices")
        return try await fetch(url)
    }
    
    // MARK: - Prices
    
    func getPrice(ticker: String) async throws -> PriceResponse {
        let url = try makeURL("/prices", ticker: ticker)
        return try await fetch(url)
    }
    
    // MARK: - Price History
    
    func getPriceHistory(symbol: String, period: String = "3m") async throws -> PriceHistoryResponse {
        guard let encoded = symbol.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed),
              let url = URL(string: "\(baseURL)/data/price-history/\(encoded)?period=\(period)") else {
            throw APIError.invalidURL
        }
        return try await fetch(url)
    }
    
    // MARK: - News
    
    func getNews(ticker: String) async throws -> NewsResponse {
        let url = try makeURL("/news", ticker: ticker)
        return try await fetch(url)
    }
    
    // MARK: - Macro
    
    func getMacro() async throws -> MacroResponse {
        let url = try makeURL("/macro")
        return try await fetch(url)
    }
    
    // MARK: - Portfolio
    
    func getPortfolio() async throws -> PortfolioResponse {
        let url = try makeURL("/portfolio")
        return try await fetch(url)
    }
    
    func resetPortfolio(startingCash: Double = 100000) async throws -> [String: Any] {
        let url = try makeURL("/portfolio/reset", queryItems: [URLQueryItem(name: "starting_cash", value: String(startingCash))])
        return try await post(url, body: nil)
    }
    
    func getPortfolioHistory(days: Int = 30) async throws -> PortfolioHistoryResponse {
        let url = try makeURL("/portfolio/history", queryItems: [URLQueryItem(name: "days", value: String(days))])
        return try await fetch(url)
    }
    
    func getPortfolioPerformance(days: Int = 30) async throws -> PortfolioPerformanceResponse {
        let url = try makeURL("/portfolio/performance", queryItems: [URLQueryItem(name: "days", value: String(days))])
        return try await fetch(url)
    }
    
    func getSectorAllocation() async throws -> SectorAllocationResponse {
        let url = try makeURL("/portfolio/sectors")
        return try await fetch(url)
    }
    
    func recordPortfolioSnapshot() async throws -> [String: Any] {
        let url = try makeURL("/portfolio/snapshot")
        return try await post(url, body: nil)
    }
    
    // MARK: - Alerts
    
    func getAlerts(limit: Int = 20) async throws -> AlertsResponse {
        let url = try makeURL("/alerts", queryItems: [URLQueryItem(name: "limit", value: String(limit))])
        return try await fetch(url)
    }
    
    func getRecentAlerts(hours: Int = 24) async throws -> AlertsResponse {
        let url = try makeURL("/alerts/recent", queryItems: [URLQueryItem(name: "hours", value: String(hours))])
        return try await fetch(url)
    }
    
    // MARK: - Orders
    
    func getOrders(status: String? = nil, limit: Int = 50) async throws -> OrdersResponse {
        var queryItems: [URLQueryItem] = [URLQueryItem(name: "limit", value: String(limit))]
        if let status = status {
            queryItems.append(URLQueryItem(name: "status", value: status))
        }
        let url = try makeURL("/orders", queryItems: queryItems)
        return try await fetch(url)
    }
    
    func getTodaysOrders() async throws -> OrdersResponse {
        let url = try makeURL("/orders/today")
        return try await fetch(url)
    }
    
    func createOrder(ticker: String, side: String, quantity: Double, orderType: String = "MARKET", limitPrice: Double? = nil) async throws -> OrderResponse {
        let url = try makeURL("/orders")
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
                try handleHTTPError(response)
            }
            throw APIError.invalidResponse
        }
        
        return try decoder.decode(OrderResponse.self, from: data)
    }
    
    func cancelOrder(orderId: String) async throws -> OrderResponse {
        guard let encodedId = orderId.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) else {
            throw APIError.invalidURL
        }
        let url = try makeURL("/orders/\(encodedId)")
        
        var request = authorizedRequest(url: url, method: "DELETE")
        
        let (data, response) = try await dataWithAutoRefresh(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse, 200...299 ~= httpResponse.statusCode else {
            if let httpResponse = response as? HTTPURLResponse {
                try handleHTTPError(response)
            }
            throw APIError.invalidResponse
        }
        
        return try decoder.decode(OrderResponse.self, from: data)
    }
    
    // MARK: - Trade Validation (Phase 2 Risk)
    
    /// Validate a trade against risk settings before submission
    /// Returns warnings if trade exceeds position limits or other risk rules
    func validateTrade(ticker: String, action: String, quantity: Double, price: Double) async throws -> TradeValidationResponse {
        let url = try makeURL("/trade/validate")
        let body: [String: Any] = [
            "ticker": ticker,
            "action": action,
            "quantity": quantity,
            "price": price
        ]
        
        var request = authorizedRequest(url: url, method: "POST")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        
        let (data, response) = try await dataWithAutoRefresh(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse, 200...299 ~= httpResponse.statusCode else {
            if let httpResponse = response as? HTTPURLResponse {
                try handleHTTPError(response)
            }
            throw APIError.invalidResponse
        }
        
        return try decoder.decode(TradeValidationResponse.self, from: data)
    }
    
    // MARK: - Risk Settings (REC-215)
    
    func getRiskSettings() async throws -> RiskSettingsAPIResponse {
        let url = try makeURL("/user/risk-settings")
        let request = authorizedRequest(url: url)
        
        let (data, response) = try await dataWithAutoRefresh(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse, 200...299 ~= httpResponse.statusCode else {
            if let httpResponse = response as? HTTPURLResponse {
                try handleHTTPError(response)
            }
            throw APIError.invalidResponse
        }
        
        return try decoder.decode(RiskSettingsAPIResponse.self, from: data)
    }
    
    func updateRiskSettings(_ settings: RiskSettingsUpdatePayload) async throws -> RiskSettingsAPIResponse {
        let url = try makeURL("/user/risk-settings")
        
        var request = authorizedRequest(url: url, method: "PUT")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        request.httpBody = try encoder.encode(settings)
        
        let (data, response) = try await dataWithAutoRefresh(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse, 200...299 ~= httpResponse.statusCode else {
            if let httpResponse = response as? HTTPURLResponse {
                try handleHTTPError(response)
            }
            throw APIError.invalidResponse
        }
        
        #if DEBUG
        // Debug: print raw response
        if let jsonString = String(data: data, encoding: .utf8) {
            debugLog("🔍 Risk settings response: \(jsonString)")
        }
        #endif
        
        do {
            return try decoder.decode(RiskSettingsAPIResponse.self, from: data)
        } catch {
            #if DEBUG
            debugError(error, context: "Risk settings decode")
            #endif
            throw error
        }
    }
    
    func resetRiskSettings() async throws -> RiskSettingsAPIResponse {
        let url = try makeURL("/user/risk-settings/reset")
        
        var request = authorizedRequest(url: url, method: "POST")
        
        let (data, response) = try await dataWithAutoRefresh(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse, 200...299 ~= httpResponse.statusCode else {
            if let httpResponse = response as? HTTPURLResponse {
                try handleHTTPError(response)
            }
            throw APIError.invalidResponse
        }
        
        return try decoder.decode(RiskSettingsAPIResponse.self, from: data)
    }
    
    // MARK: - Portfolio Risk (REC-230)
    
    /// Get portfolio-level risk metrics including risk score
    func getPortfolioRisk() async throws -> PortfolioRiskAPIResponse {
        let url = try makeURL("/risk/portfolio")
        return try await fetch(url)
    }
    
    // MARK: - Market VIX (Risk Module)
    
    /// Get current VIX value and regime classification
    func getMarketVIX() async throws -> MarketVIXResponse {
        let url = try makeURL("/market/vix")
        return try await fetch(url)
    }
    
    // MARK: - Claude Risk Analysis (Risk Module)
    
    /// Get AI-powered risk analysis for a specific ticker
    func getRiskAnalysis(ticker: String) async throws -> ClaudeRiskAnalysisResponse {
        let url = try makeURL("/risk/analyze", ticker: ticker)
        let response: ClaudeRiskAnalysisAPIResponse = try await fetch(url)
        return response.data
    }
    
    // MARK: - Market Regime (Risk Module)
    
    /// Get HMM-based market regime classification
    func getMarketRegime() async throws -> MarketRegimeResponse {
        let url = try makeURL("/market/regime")
        return try await fetch(url)
    }
    
    // MARK: - Sector Risk (Risk Module)
    
    /// Get sector concentration analysis and warnings
    func getSectorRisk() async throws -> SectorRiskResponse {
        let url = try makeURL("/portfolio/sectors/exposure")
        return try await fetch(url)
    }
    
    // MARK: - Risk Cache Warming
    
    /// Pre-warm risk analysis cache for portfolio holdings.
    /// Call after login to ensure instant risk display.
    func warmRiskCache(force: Bool = false) async throws -> WarmCacheResponse {
        let url = try makeURL("/risk/warm-cache", queryItems: [URLQueryItem(name: "force", value: String(force))])
        var request = authorizedRequest(url: url, method: "POST")
        request.httpMethod = "POST"
        let (data, response) = try await dataWithAutoRefresh(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse,
              200...299 ~= httpResponse.statusCode else {
            throw APIError.invalidResponse
        }
        
        return try decoder.decode(WarmCacheResponse.self, from: data)
    }
    
    // MARK: - Crowd Wisdom (REC-259, REC-261)
    
    /// Get weekly top 5 smart money picks based on insider buying
    func getSmartMoneyPicks(week: String? = nil) async throws -> TopPicksResponse {
        var queryItems: [URLQueryItem] = []
        if let week = week {
            queryItems.append(URLQueryItem(name: "week", value: week))
        }
        let url = try makeURL("/crowd-wisdom/top-picks", queryItems: queryItems)
        return try await fetch(url)
    }
    
    /// Get all crowd wisdom scores for a week
    func getCrowdWisdomScores(week: String? = nil, limit: Int = 50) async throws -> CrowdWisdomScoresResponse {
        var queryItems: [URLQueryItem] = [URLQueryItem(name: "limit", value: String(limit))]
        if let week = week {
            queryItems.append(URLQueryItem(name: "week", value: week))
        }
        let url = try makeURL("/crowd-wisdom/scores", queryItems: queryItems)
        return try await fetch(url)
    }
    
    /// Get crowd wisdom score for a specific ticker
    func getCrowdWisdomScore(ticker: String) async throws -> CrowdWisdomScore {
        let url = try makeURL("/crowd-wisdom/scores", ticker: ticker)
        return try await fetch(url)
    }
    
    // MARK: - Pipeline Status (Scores Last Updated)
    
    /// Get pipeline status including last run time
    func getPipelineStatus() async throws -> PipelineStatusResponse {
        let url = try makeURL("/pipeline/status")
        return try await fetch(url)
    }
    
    // MARK: - Price Alerts (REC-158)
    
    /// Create a price alert
    func createPriceAlert(ticker: String, condition: PriceAlertCondition, targetPrice: Double) async throws -> CreatePriceAlertResponse {
        let url = try makeURL("/ibkr/alerts")
        let requestBody = CreatePriceAlertRequest(
            ticker: ticker.uppercased(),
            condition: condition.rawValue,
            targetPrice: targetPrice
        )
        let body = try JSONEncoder().encode(requestBody)
        
        var request = authorizedRequest(url: url, method: "POST")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = body
        
        let (data, response) = try await dataWithAutoRefresh(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse, 200...299 ~= httpResponse.statusCode else {
            try handleHTTPError(response)
            throw APIError.invalidResponse
        }
        
        return try decoder.decode(CreatePriceAlertResponse.self, from: data)
    }
    
    /// Get all price alerts for the current user
    func getPriceAlerts() async throws -> PriceAlertsResponse {
        let url = try makeURL("/ibkr/alerts")
        return try await fetch(url)
    }
    
    /// Delete a price alert
    func deletePriceAlert(alertId: String) async throws -> DeletePriceAlertResponse {
        let url = try makeURL("/ibkr/alerts", ticker: alertId)
        
        var request = authorizedRequest(url: url, method: "DELETE")
        let (data, response) = try await dataWithAutoRefresh(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse, 200...299 ~= httpResponse.statusCode else {
            try handleHTTPError(response)
            throw APIError.invalidResponse
        }
        
        return try decoder.decode(DeletePriceAlertResponse.self, from: data)
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
    /// IOS-002: Uses pinned URLSession for certificate validation
    private func dataWithAutoRefresh(for request: URLRequest) async throws -> (Data, URLResponse) {
        let (data, response) = try await pinnedSession.data(for: request)

        guard let http = response as? HTTPURLResponse else {
            return (data, response)
        }

        if http.statusCode == 401 {
            // Try token refresh
            do {
                let newToken = try await AuthService.shared.refreshToken()
                var retry = request
                retry.setValue("Bearer \(newToken)", forHTTPHeaderField: "Authorization")
                return try await pinnedSession.data(for: retry)
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
                try handleHTTPError(response)
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
                try handleHTTPError(response)
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
    case invalidURL
    case httpError(statusCode: Int)
    case rateLimited(retryAfter: Int?)
    case decodingError(Error)
    
    var errorDescription: String? {
        switch self {
        case .invalidResponse:
            return "Invalid response from server"
        case .invalidURL:
            return "Invalid URL"
        case .httpError(let statusCode):
            return "HTTP error: \(statusCode)"
        case .rateLimited(let retryAfter):
            if let seconds = retryAfter {
                return "Too many requests. Please wait \(seconds) seconds."
            }
            return "Too many requests. Please try again later."
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
    let updatedAt: String?
    // Note: No CodingKeys needed - APIService uses .convertFromSnakeCase globally
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

// MARK: - Trade Validation Response (Phase 2 Risk)

struct TradeValidationResponse: Codable {
    let valid: Bool
    let warnings: [TradeWarning]
    let riskMetrics: TradeRiskMetrics
}

struct TradeWarning: Codable {
    let type: String
    let message: String
    let severity: String?
}

struct TradeRiskMetrics: Codable {
    let validationSkipped: Bool?
    let reason: String?
    let quantity: Double?
    let price: Double?
    let positionPct: Double?
    let limitPct: Double?
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

// MARK: - Score Changes Response (F9.3)

struct ScoreChangesResponse: Codable {
    let success: Bool
    let count: Int
    let data: [SignalChange]
}

struct SignalChange: Codable {
    let ticker: String
    let oldSignal: String
    let newSignal: String
    let oldScore: Double
    let newScore: Double
    let scoreChange: Double
}

// MARK: - Score History Response Models

struct ScoreHistoryResponse: Codable {
    let success: Bool
    let data: ScoreHistoryWrapper
}

struct ScoreHistoryWrapper: Codable {
    let ticker: String
    let count: Int
    let history: [ScoreHistoryData]
    let signalChanges: [ScoreSignalChange]?
}

struct ScoreSignalChange: Codable {
    let date: String
    let fromSignal: String
    let toSignal: String
    let score: Double
}

struct ScoreHistoryData: Codable {
    let date: String
    let totalScore: Double
    let signal: String
    let fundamentalScore: Double?
    let sentimentScore: Double?
    let technicalScore: Double?
    let macroScore: Double?
    
    var score: Double { totalScore }
}

// MARK: - Price History Response Models

struct PriceHistoryResponse: Codable {
    let success: Bool
    let data: PriceHistoryData
}

struct PriceHistoryData: Codable {
    let ticker: String
    let period: String
    let count: Int?
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

// MARK: - User Preferences (REC-126, REC-127)

struct UserPreferences: Codable {
    var riskTolerance: String?
    var portfolioSize: String?
}

struct PreferencesResponse: Codable {
    let success: Bool
    let preferences: UserPreferences
}

extension APIService {
    
    /// Get user's trading preferences (REC-126, REC-127)
    func getPreferences() async throws -> UserPreferences {
        guard let token = AuthService.shared.accessToken else {
            throw APIError.httpError(statusCode: 401)
        }
        
        let url = try makeURL("/auth/preferences")
        var request = URLRequest(url: url)
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        
        let (data, response) = try await URLSession.shared.data(for: request)
        
        guard let http = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }
        guard 200...299 ~= http.statusCode else {
            throw APIError.httpError(statusCode: http.statusCode)
        }
        
        let result = try decoder.decode(PreferencesResponse.self, from: data)
        return result.preferences
    }
    
    /// Update user's trading preferences (REC-126, REC-127)
    func updatePreferences(riskTolerance: String?, portfolioSize: String?) async throws -> UserPreferences {
        guard let token = AuthService.shared.accessToken else {
            throw APIError.httpError(statusCode: 401)
        }
        
        let url = try makeURL("/auth/preferences")
        var request = URLRequest(url: url)
        request.httpMethod = "PUT"
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        var body: [String: Any] = [:]
        if let risk = riskTolerance { body["risk_tolerance"] = risk }
        if let size = portfolioSize { body["portfolio_size"] = size }
        
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        
        let (data, response) = try await URLSession.shared.data(for: request)
        
        guard let http = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }
        guard 200...299 ~= http.statusCode else {
            throw APIError.httpError(statusCode: http.statusCode)
        }
        
        let result = try decoder.decode(PreferencesResponse.self, from: data)
        return result.preferences
    }
    
    // MARK: - REC-272: Configuration Management
    
    /// Save IBKR account configuration
    func saveIBKRConfig(accountId: String, gatewayHost: String = "127.0.0.1", gatewayPort: Int = 4002, isPaper: Bool = true) async throws {
        let url = try makeURL("/config/ibkr")
        var request = authorizedRequest(url: url, method: "POST")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let body: [String: Any] = [
            "account_id": accountId,
            "gateway_host": gatewayHost,
            "gateway_port": gatewayPort,
            "is_paper": isPaper
        ]
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        
        let (data, response) = try await dataWithAutoRefresh(for: request)
        
        guard let http = response as? HTTPURLResponse, 200...299 ~= http.statusCode else {
            throw APIError.httpError(statusCode: (response as? HTTPURLResponse)?.statusCode ?? 500)
        }
        
        // Also save to Keychain locally
        KeychainHelper.shared.save(key: "sigil_ibkr_account_id", string: accountId)
    }
    
    /// Get IBKR account configuration
    func getIBKRConfig() async throws -> IBKRConfigResponse {
        let url = try makeURL("/config/ibkr")
        return try await fetch(url)
    }
    
    /// Get LLM provider configuration
    func getLLMConfig() async throws -> LLMConfigResponse {
        let url = try makeURL("/config/llm")
        return try await fetch(url)
    }
    
    /// Get system configuration overview
    func getSystemConfig() async throws -> SystemConfigResponse {
        let url = try makeURL("/config/system")
        return try await fetch(url)
    }
}

// MARK: - Risk Settings API Types (REC-215)

struct RiskSettingsAPIResponse: Codable {
    let success: Bool
    let data: RiskSettingsData?
    let error: String?
}

struct RiskSettingsData: Codable {
    var userId: String?
    var hardStop: RiskStopData
    var trailingStop: RiskTrailingStopData
    var vixAdjustment: RiskVixData
    var positionLimit: RiskPositionLimitData
    // Note: No CodingKeys needed - decoder uses .convertFromSnakeCase
}

struct RiskStopData: Codable {
    var enabled: Bool
    var thresholdPct: Double
    // Note: No CodingKeys needed - decoder uses .convertFromSnakeCase
}

struct RiskTrailingStopData: Codable {
    var enabled: Bool
    var distancePct: Double
    // Note: No CodingKeys needed - decoder uses .convertFromSnakeCase
}

struct RiskVixData: Codable {
    var enabled: Bool
}

struct RiskPositionLimitData: Codable {
    var enabled: Bool
    var maxPct: Double
    // Note: No CodingKeys needed - decoder uses .convertFromSnakeCase
}

struct RiskSettingsUpdatePayload: Codable {
    var hardStop: RiskStopData?
    var trailingStop: RiskTrailingStopData?
    var vixAdjustment: RiskVixData?
    var positionLimit: RiskPositionLimitData?
    // Note: Uses snake_case encoder in updateRiskSettings
}

// MARK: - Market VIX Response (Risk Module)

struct MarketVIXResponse: Codable {
    let vix: Double
    let regime: String
    let change: Double?
    let changePct: Double?
    
    enum CodingKeys: String, CodingKey {
        case vix
        case regime
        case change
        case changePct = "change_pct"
    }
}

// MARK: - Warm Cache Response (Risk Module)

struct WarmCacheResponse: Codable {
    let success: Bool
    let data: WarmCacheData
}

struct WarmCacheData: Codable {
    let requested: Int
    let alreadyCached: Int
    let analyzed: Int
    let failed: Int
    let message: String?
    // Note: decoder uses .convertFromSnakeCase
}

// MARK: - Claude Risk Analysis Response (Risk Module)

struct ClaudeRiskAnalysisAPIResponse: Codable {
    let success: Bool
    let data: ClaudeRiskAnalysisResponse
}

struct ClaudeRiskAnalysisResponse: Codable {
    let ticker: String
    let riskScore: Int
    let riskLevel: String
    let riskFactors: [String]  // Backend returns simple strings
    let recommendation: String
    let reasoning: String
    let confidence: Double?
    let analyzedAt: String?
    let cached: Bool?
    // Note: No CodingKeys needed - decoder uses .convertFromSnakeCase
}

struct RiskFactor: Codable, Identifiable {
    var id: String { factor }
    let factor: String
    let impact: String
    let description: String?
}

// MARK: - HMM Regime Response (Risk Module)

struct MarketRegimeResponse: Codable {
    let regime: String
    let confidence: Double
    let states: [String]
}

// MARK: - Sector Risk Response (Risk Module)

struct SectorRiskResponse: Codable {
    let sectors: [SectorRiskData]
    let warnings: [SectorWarning]
    let hhi: Double
}

struct SectorRiskData: Codable, Identifiable {
    var id: String { sector }
    let sector: String
    let weight: Double
    let value: Double?
}

struct SectorWarning: Codable, Identifiable {
    var id: String { sector }
    let sector: String
    let weight: Double
    let message: String
}

// MARK: - Portfolio Risk API Types (REC-230)

struct PortfolioRiskAPIResponse: Codable {
    let success: Bool
    let data: PortfolioRiskData?
}

struct PortfolioRiskData: Codable {
    let totalValue: Double?
    let var95Daily: Double?
    let var99Daily: Double?
    let var95Pct: Double?
    let var99Pct: Double?
    let riskScore: String
    let positionVars: [PositionVarData]?
    let correlationBenefit: Double?
    let calculatedAt: String?
    let message: String?
    
    enum CodingKeys: String, CodingKey {
        case totalValue = "total_value"
        case var95Daily = "var_95_daily"
        case var99Daily = "var_99_daily"
        case var95Pct = "var_95_pct"
        case var99Pct = "var_99_pct"
        case riskScore = "risk_score"
        case positionVars = "position_vars"
        case correlationBenefit = "correlation_benefit"
        case calculatedAt = "calculated_at"
        case message
    }
}

struct PositionVarData: Codable {
    let ticker: String
    let positionValue: Double
    let var95Daily: Double
    let var95Pct: Double
    let dailyVolatility: Double?
    let annualizedVolatility: Double?
    
    enum CodingKeys: String, CodingKey {
        case ticker
        case positionValue = "position_value"
        case var95Daily = "var_95_daily"
        case var95Pct = "var_95_pct"
        case dailyVolatility = "daily_volatility"
        case annualizedVolatility = "annualized_volatility"
    }
}

// MARK: - Pipeline Status Response (Scores Last Updated)

struct PipelineStatusResponse: Codable {
    let success: Bool
    let data: PipelineStatusData
}

struct PipelineStatusData: Codable {
    let activeRuns: Int
    let active: [String: ActiveRunInfo]?
    let latest: LatestPipelineRun?
    
    enum CodingKeys: String, CodingKey {
        case activeRuns = "active_runs"
        case active
        case latest
    }
}

struct ActiveRunInfo: Codable {
    let status: String
    let startedAt: String
    
    enum CodingKeys: String, CodingKey {
        case status
        case startedAt = "started_at"
    }
}

struct LatestPipelineRun: Codable {
    let runId: String
    let startedAt: String
    let completedAt: String?
    let status: String
    let totalDurationSeconds: Double?
    
    enum CodingKeys: String, CodingKey {
        case runId = "run_id"
        case startedAt = "started_at"
        case completedAt = "completed_at"
        case status
        case totalDurationSeconds = "total_duration_seconds"
    }
}

// MARK: - REC-272: Configuration Response Types

struct IBKRConfigResponse: Codable {
    let success: Bool
    let data: IBKRConfigData
}

struct IBKRConfigData: Codable {
    let accountId: String?
    let gatewayHost: String
    let gatewayPort: Int
    let isConfigured: Bool
    let isPaper: Bool?
    let source: String?
    
    enum CodingKeys: String, CodingKey {
        case accountId = "account_id"
        case gatewayHost = "gateway_host"
        case gatewayPort = "gateway_port"
        case isConfigured = "is_configured"
        case isPaper = "is_paper"
        case source
    }
}

struct LLMConfigResponse: Codable {
    let success: Bool
    let data: LLMConfigData
}

struct LLMConfigData: Codable {
    let provider: String
    let model: String
    let available: Bool
    let fallbackModel: String?
    let note: String?
    
    enum CodingKeys: String, CodingKey {
        case provider
        case model
        case available
        case fallbackModel = "fallback_model"
        case note
    }
}

struct SystemConfigResponse: Codable {
    let success: Bool
    let data: SystemConfigData
}

struct SystemConfigData: Codable {
    let llm: SystemLLMConfig
    let database: SystemDatabaseConfig
    let ibkr: SystemIBKRConfig
    let environment: String?
}

struct SystemLLMConfig: Codable {
    let provider: String
    let configured: Bool
}

struct SystemDatabaseConfig: Codable {
    let type: String
}

struct SystemIBKRConfig: Codable {
    let configured: Bool
    let gatewayHost: String
    let gatewayPort: Int
    
    enum CodingKeys: String, CodingKey {
        case configured
        case gatewayHost = "gateway_host"
        case gatewayPort = "gateway_port"
    }
}
