import Foundation
import Combine

/// F6.3: IBKR Live Trading Connection Service
/// Manages IBKR connection state, stores account ID in Keychain
@MainActor
final class IBKRService: ObservableObject {
    static let shared = IBKRService()
    
    // MARK: - Published State
    
    @Published var isConnected: Bool = false
    @Published var accountId: String?
    @Published var isPaperAccount: Bool = false
    @Published var isConnecting: Bool = false
    @Published var connectionError: String?
    
    // MARK: - Keys
    
    private let accountIdKey = "sigil_ibkr_account_id"
    private let connectedKey = "sigil_ibkr_connected"
    
    private let baseURL = "http://127.0.0.1:8000/api/v1/ibkr"
    
    // MARK: - Init
    
    private init() {
        // Restore connection state from Keychain/UserDefaults
        self.isConnected = UserDefaults.standard.bool(forKey: connectedKey)
        self.accountId = KeychainHelper.shared.loadString(key: accountIdKey)
        if let id = accountId {
            self.isPaperAccount = id.hasPrefix("DU")
        }
    }
    
    // MARK: - Connection Management
    
    /// Mock OAuth connection to IBKR
    func connect(accountId: String? = nil) async throws {
        isConnecting = true
        connectionError = nil
        defer { isConnecting = false }
        
        let url = URL(string: "\(baseURL)/connect")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        if let token = AuthService.shared.accessToken {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        
        var body: [String: Any] = [:]
        if let accountId = accountId {
            body["account_id"] = accountId
        }
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        
        let (data, response) = try await URLSession.shared.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse,
              200...299 ~= httpResponse.statusCode else {
            let statusCode = (response as? HTTPURLResponse)?.statusCode ?? 0
            throw IBKRError.connectionFailed("HTTP \(statusCode)")
        }
        
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        let result = try decoder.decode(IBKRConnectResponse.self, from: data)
        
        // Store connection state
        self.isConnected = true
        self.accountId = result.data.accountId
        self.isPaperAccount = result.data.isPaper
        
        // Persist
        UserDefaults.standard.set(true, forKey: connectedKey)
        if let id = result.data.accountId {
            KeychainHelper.shared.save(key: accountIdKey, string: id)
        }
    }
    
    /// Disconnect from IBKR
    func disconnect() async throws {
        let url = URL(string: "\(baseURL)/disconnect")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        
        if let token = AuthService.shared.accessToken {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        
        let (_, response) = try await URLSession.shared.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse,
              200...299 ~= httpResponse.statusCode else {
            throw IBKRError.disconnectFailed
        }
        
        // Clear state
        self.isConnected = false
        self.accountId = nil
        self.isPaperAccount = false
        
        // Clear persistence
        UserDefaults.standard.set(false, forKey: connectedKey)
        KeychainHelper.shared.delete(key: accountIdKey)
    }
    
    /// Check IBKR connection status from backend
    func refreshStatus() async {
        guard let url = URL(string: "\(baseURL)/status") else { return }
        
        do {
            var request = URLRequest(url: url)
            if let token = AuthService.shared.accessToken {
                request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
            }
            
            let (data, response) = try await URLSession.shared.data(for: request)
            
            guard let httpResponse = response as? HTTPURLResponse,
                  httpResponse.statusCode == 200 else { return }
            
            let decoder = JSONDecoder()
            decoder.keyDecodingStrategy = .convertFromSnakeCase
            let result = try decoder.decode(IBKRStatusResponse.self, from: data)
            
            self.isConnected = result.data.state == "connected"
            self.accountId = result.data.accountId
            self.isPaperAccount = result.data.isPaper
        } catch {
            // Silently fail — keep local state
        }
    }
    
    /// Submit an order via IBKR
    func submitOrder(
        ticker: String,
        side: String,
        quantity: Double,
        orderType: String = "MARKET",
        limitPrice: Double? = nil
    ) async throws -> IBKROrderResult {
        let url = URL(string: "\(baseURL)/orders")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        if let token = AuthService.shared.accessToken {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        
        var body: [String: Any] = [
            "ticker": ticker,
            "side": side,
            "quantity": quantity,
            "order_type": orderType,
        ]
        if let limitPrice = limitPrice {
            body["limit_price"] = limitPrice
        }
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        
        let (data, response) = try await URLSession.shared.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse,
              200...299 ~= httpResponse.statusCode else {
            let statusCode = (response as? HTTPURLResponse)?.statusCode ?? 0
            throw IBKRError.orderFailed("HTTP \(statusCode)")
        }
        
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        let result = try decoder.decode(IBKROrderResponse.self, from: data)
        return result.data
    }
}

// MARK: - Errors

enum IBKRError: Error, LocalizedError {
    case connectionFailed(String)
    case disconnectFailed
    case orderFailed(String)
    case notConnected
    
    var errorDescription: String? {
        switch self {
        case .connectionFailed(let msg): return "IBKR connection failed: \(msg)"
        case .disconnectFailed: return "Failed to disconnect from IBKR"
        case .orderFailed(let msg): return "IBKR order failed: \(msg)"
        case .notConnected: return "Not connected to IBKR"
        }
    }
}

// MARK: - Response Models

struct IBKRConnectResponse: Codable {
    let success: Bool
    let message: String
    let data: IBKRConnectionData
}

struct IBKRStatusResponse: Codable {
    let success: Bool
    let data: IBKRConnectionData
}

struct IBKRConnectionData: Codable {
    let userId: String
    let accountId: String?
    let state: String
    let isPaper: Bool
    let connectedAt: String?
    let errorMessage: String?
}

struct IBKROrderResponse: Codable {
    let success: Bool
    let data: IBKROrderResult
}

struct IBKROrderResult: Codable {
    let orderId: String
    let ticker: String
    let side: String
    let quantity: Double
    let orderType: String
    let status: String
    let filledPrice: Double?
    let filledAt: String?
    let isPaper: Bool
}
