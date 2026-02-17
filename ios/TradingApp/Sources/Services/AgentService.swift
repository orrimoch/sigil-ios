import Foundation

/// Service for agent-related API calls
class AgentService {
    static let shared = AgentService()
    private let baseURL = APIService.shared.baseURL
    
    private init() {}
    
    // MARK: - Status & Control
    
    /// Get current agent status
    func getStatus() async throws -> AgentStatusResponse {
        let url = URL(string: "\(baseURL)/api/v1/agent/status")!
        let (data, _) = try await URLSession.shared.data(from: url)
        return try JSONDecoder().decode(AgentStatusResponse.self, from: data)
    }
    
    /// Pause the agent
    func pause() async throws -> Bool {
        let url = URL(string: "\(baseURL)/api/v1/agent/pause")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        let (data, _) = try await URLSession.shared.data(for: request)
        let response = try JSONDecoder().decode([String: Bool].self, from: data)
        return response["success"] ?? false
    }
    
    /// Resume the agent
    func resume() async throws -> Bool {
        let url = URL(string: "\(baseURL)/api/v1/agent/resume")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        let (data, _) = try await URLSession.shared.data(for: request)
        let response = try JSONDecoder().decode([String: Bool].self, from: data)
        return response["success"] ?? false
    }
    
    /// Trigger a trading loop run
    func runTradingLoop(dryRun: Bool = false) async throws -> [String: Any] {
        let url = URL(string: "\(baseURL)/api/v1/agent/run")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(["dry_run": dryRun])
        
        let (data, _) = try await URLSession.shared.data(for: request)
        return try JSONSerialization.jsonObject(with: data) as? [String: Any] ?? [:]
    }
    
    // MARK: - Pending Approvals
    
    /// Get pending trades awaiting approval
    func getPendingTrades() async throws -> [PendingTrade] {
        let url = URL(string: "\(baseURL)/api/v1/agent/pending")!
        let (data, _) = try await URLSession.shared.data(from: url)
        let response = try JSONDecoder().decode(PendingTradesResponse.self, from: data)
        return response.pending
    }
    
    /// Approve a pending trade
    func approveTrade(pendingId: String) async throws -> ApprovalResponse {
        let url = URL(string: "\(baseURL)/api/v1/agent/pending/\(pendingId)/approve")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        
        let (data, _) = try await URLSession.shared.data(for: request)
        return try JSONDecoder().decode(ApprovalResponse.self, from: data)
    }
    
    /// Reject a pending trade
    func rejectTrade(pendingId: String, reason: String? = nil) async throws -> ApprovalResponse {
        let url = URL(string: "\(baseURL)/api/v1/agent/pending/\(pendingId)/reject")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        if let reason = reason {
            request.httpBody = try JSONEncoder().encode(["reason": reason])
        }
        
        let (data, _) = try await URLSession.shared.data(for: request)
        return try JSONDecoder().decode(ApprovalResponse.self, from: data)
    }
    
    // MARK: - History
    
    /// Get decision history
    func getDecisions(limit: Int = 50, action: String? = nil) async throws -> [AgentDecision] {
        var urlComponents = URLComponents(string: "\(baseURL)/api/v1/agent/decisions")!
        var queryItems = [URLQueryItem(name: "limit", value: "\(limit)")]
        if let action = action {
            queryItems.append(URLQueryItem(name: "action", value: action))
        }
        urlComponents.queryItems = queryItems
        
        let (data, _) = try await URLSession.shared.data(from: urlComponents.url!)
        let response = try JSONDecoder().decode(DecisionsResponse.self, from: data)
        return response.decisions
    }
    
    /// Get execution history
    func getExecutions(limit: Int = 50) async throws -> [AgentExecution] {
        let url = URL(string: "\(baseURL)/api/v1/agent/executions?limit=\(limit)")!
        let (data, _) = try await URLSession.shared.data(from: url)
        let response = try JSONDecoder().decode(ExecutionsResponse.self, from: data)
        return response.executions
    }
    
    /// Get agent stats
    func getStats() async throws -> AgentStats {
        let url = URL(string: "\(baseURL)/api/v1/agent/stats")!
        let (data, _) = try await URLSession.shared.data(from: url)
        return try JSONDecoder().decode(AgentStats.self, from: data)
    }
    
    // MARK: - Settings
    
    /// Update agent settings
    func updateSettings(_ settings: AgentSettings) async throws -> Bool {
        let url = URL(string: "\(baseURL)/api/v1/agent/settings")!
        var request = URLRequest(url: url)
        request.httpMethod = "PUT"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(settings)
        
        let (data, _) = try await URLSession.shared.data(for: request)
        let response = try JSONDecoder().decode([String: Bool].self, from: data)
        return response["success"] ?? false
    }
}
