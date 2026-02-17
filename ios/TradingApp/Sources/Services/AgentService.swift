import Foundation

/// Service for agent-related API calls
/// Uses authenticated requests with automatic token refresh
class AgentService {
    static let shared = AgentService()
    private let baseURL: String
    
    // URLSession with standard timeout
    private lazy var session: URLSession = {
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 30
        config.timeoutIntervalForResource = 60
        return URLSession(configuration: config)
    }()
    
    private let decoder: JSONDecoder = {
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        return decoder
    }()
    
    private init() {
        #if DEBUG
        baseURL = "http://127.0.0.1:8000"
        #else
        baseURL = "https://api.sigil.app"
        #endif
    }
    
    // MARK: - Auth Header Injection
    
    /// Build a URLRequest with Bearer token attached (if available)
    private func authorizedRequest(url: URL, method: String = "GET") -> URLRequest {
        var request = URLRequest(url: url)
        request.httpMethod = method
        if let token = AuthService.shared.accessToken {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        return request
    }
    
    /// Perform request with automatic 401 retry after token refresh
    private func dataWithAutoRefresh(for request: URLRequest) async throws -> (Data, URLResponse) {
        let (data, response) = try await session.data(for: request)
        
        guard let http = response as? HTTPURLResponse else {
            return (data, response)
        }
        
        if http.statusCode == 401 {
            // Try token refresh
            do {
                let newToken = try await AuthService.shared.refreshToken()
                var retry = request
                retry.setValue("Bearer \(newToken)", forHTTPHeaderField: "Authorization")
                return try await session.data(for: retry)
            } catch {
                // Refresh failed — force logout
                await MainActor.run { AuthService.shared.logout() }
                throw AgentServiceError.unauthorized
            }
        }
        
        return (data, response)
    }
    
    /// Generic GET request with auth
    private func get<T: Decodable>(_ path: String, queryItems: [URLQueryItem]? = nil) async throws -> T {
        var components = URLComponents(string: "\(baseURL)\(path)")!
        components.queryItems = queryItems
        
        let request = authorizedRequest(url: components.url!)
        let (data, response) = try await dataWithAutoRefresh(for: request)
        
        guard let http = response as? HTTPURLResponse, 200...299 ~= http.statusCode else {
            if let http = response as? HTTPURLResponse {
                throw AgentServiceError.httpError(statusCode: http.statusCode)
            }
            throw AgentServiceError.invalidResponse
        }
        
        return try decoder.decode(T.self, from: data)
    }
    
    /// Generic POST request with auth
    private func post<T: Decodable>(_ path: String, body: Encodable? = nil) async throws -> T {
        let url = URL(string: "\(baseURL)\(path)")!
        var request = authorizedRequest(url: url, method: "POST")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        if let body = body {
            let encoder = JSONEncoder()
            encoder.keyEncodingStrategy = .convertToSnakeCase
            request.httpBody = try encoder.encode(body)
        }
        
        let (data, response) = try await dataWithAutoRefresh(for: request)
        
        guard let http = response as? HTTPURLResponse, 200...299 ~= http.statusCode else {
            if let http = response as? HTTPURLResponse {
                throw AgentServiceError.httpError(statusCode: http.statusCode)
            }
            throw AgentServiceError.invalidResponse
        }
        
        return try decoder.decode(T.self, from: data)
    }
    
    /// Generic PUT request with auth
    private func put<T: Decodable>(_ path: String, body: Encodable) async throws -> T {
        let url = URL(string: "\(baseURL)\(path)")!
        var request = authorizedRequest(url: url, method: "PUT")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        request.httpBody = try encoder.encode(body)
        
        let (data, response) = try await dataWithAutoRefresh(for: request)
        
        guard let http = response as? HTTPURLResponse, 200...299 ~= http.statusCode else {
            if let http = response as? HTTPURLResponse {
                throw AgentServiceError.httpError(statusCode: http.statusCode)
            }
            throw AgentServiceError.invalidResponse
        }
        
        return try decoder.decode(T.self, from: data)
    }
    
    // MARK: - Status & Control
    
    /// Get current agent status
    func getStatus() async throws -> AgentStatusResponse {
        try await get("/api/v1/agent/status")
    }
    
    /// Pause the agent
    func pause() async throws -> Bool {
        let response: [String: Bool] = try await post("/api/v1/agent/pause")
        return response["success"] ?? false
    }
    
    /// Resume the agent
    func resume() async throws -> Bool {
        let response: [String: Bool] = try await post("/api/v1/agent/resume")
        return response["success"] ?? false
    }
    
    /// Trigger a trading loop run
    func runTradingLoop(dryRun: Bool = false) async throws -> TradingLoopResponse {
        try await post("/api/v1/agent/run", body: ["dry_run": dryRun])
    }
    
    // MARK: - Pending Approvals
    
    /// Get pending trades awaiting approval
    func getPendingTrades() async throws -> [PendingTrade] {
        let response: PendingTradesResponse = try await get("/api/v1/agent/pending")
        return response.pending
    }
    
    /// Approve a pending trade
    func approveTrade(pendingId: String) async throws -> ApprovalResponse {
        try await post("/api/v1/agent/pending/\(pendingId)/approve")
    }
    
    /// Reject a pending trade
    func rejectTrade(pendingId: String, reason: String? = nil) async throws -> ApprovalResponse {
        if let reason = reason {
            return try await post("/api/v1/agent/pending/\(pendingId)/reject", body: ["reason": reason])
        }
        return try await post("/api/v1/agent/pending/\(pendingId)/reject")
    }
    
    // MARK: - History
    
    /// Get decision history
    func getDecisions(limit: Int = 50, action: String? = nil) async throws -> [AgentDecision] {
        var queryItems = [URLQueryItem(name: "limit", value: "\(limit)")]
        if let action = action {
            queryItems.append(URLQueryItem(name: "action", value: action))
        }
        let response: DecisionsResponse = try await get("/api/v1/agent/decisions", queryItems: queryItems)
        return response.decisions
    }
    
    /// Get execution history
    func getExecutions(limit: Int = 50) async throws -> [AgentExecution] {
        let response: ExecutionsResponse = try await get("/api/v1/agent/executions", queryItems: [
            URLQueryItem(name: "limit", value: "\(limit)")
        ])
        return response.executions
    }
    
    /// Get agent stats
    func getStats() async throws -> AgentStats {
        try await get("/api/v1/agent/stats")
    }
    
    // MARK: - Settings
    
    /// Update agent settings
    func updateSettings(_ settings: AgentSettings) async throws -> Bool {
        let response: [String: Bool] = try await put("/api/v1/agent/settings", body: settings)
        return response["success"] ?? false
    }
}

// MARK: - Error Types

enum AgentServiceError: Error, LocalizedError {
    case unauthorized
    case httpError(statusCode: Int)
    case invalidResponse
    case networkError(Error)
    
    var errorDescription: String? {
        switch self {
        case .unauthorized:
            return "Session expired. Please log in again."
        case .httpError(let code):
            return "Server error (HTTP \(code))"
        case .invalidResponse:
            return "Invalid response from server"
        case .networkError(let error):
            return "Network error: \(error.localizedDescription)"
        }
    }
}

// MARK: - Response Types

struct TradingLoopResponse: Codable {
    let success: Bool
    let dryRun: Bool
    let decisionsCount: Int
    let executionsCount: Int
    let errors: [String]?
    
    enum CodingKeys: String, CodingKey {
        case success
        case dryRun = "dry_run"
        case decisionsCount = "decisions_count"
        case executionsCount = "executions_count"
        case errors
    }
}
