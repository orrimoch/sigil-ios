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
        limitPrice: Double? = nil,
        trailingPercent: Double? = nil,
        trailingAmount: Double? = nil,
        outsideRth: Bool = false,
        tif: String = "DAY",
        goodTillDate: String? = nil,
        autoStopLossPercent: Double? = nil
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
            "outside_rth": outsideRth,
            "tif": tif,
        ]
        if let limitPrice = limitPrice {
            body["limit_price"] = limitPrice
        }
        if let trailingPercent = trailingPercent {
            body["trailing_percent"] = trailingPercent
        }
        if let trailingAmount = trailingAmount {
            body["trailing_amount"] = trailingAmount
        }
        if let goodTillDate = goodTillDate {
            body["good_till_date"] = goodTillDate
        }
        if let autoStopLossPercent = autoStopLossPercent {
            body["auto_stop_loss_percent"] = autoStopLossPercent
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
    
    /// Cancel an open order via IBKR
    func cancelOrder(orderId: String) async throws {
        let url = URL(string: "\(baseURL)/orders/\(orderId)")!
        var request = URLRequest(url: url)
        request.httpMethod = "DELETE"
        
        if let token = AuthService.shared.accessToken {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        
        let (data, response) = try await URLSession.shared.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse,
              200...299 ~= httpResponse.statusCode else {
            let statusCode = (response as? HTTPURLResponse)?.statusCode ?? 0
            if let errorData = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let detail = errorData["detail"] as? String {
                throw IBKRError.cancelFailed(detail)
            }
            throw IBKRError.cancelFailed("HTTP \(statusCode)")
        }
    }
    
    /// Get open (pending) orders from IBKR
    func getOpenOrders() async throws -> [IBKROrderResult] {
        let url = URL(string: "\(baseURL)/orders/open")!
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        
        if let token = AuthService.shared.accessToken {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        
        let (data, response) = try await URLSession.shared.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse,
              200...299 ~= httpResponse.statusCode else {
            throw IBKRError.fetchFailed
        }
        
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        let result = try decoder.decode(IBKROpenOrdersResponse.self, from: data)
        return result.data
    }
    
    /// Get real-time quote from IB Gateway (REC-140)
    /// Returns bid, ask, last, volume directly from IB — faster than Yahoo Finance
    func getQuote(ticker: String) async throws -> IBKRQuote {
        let url = URL(string: "\(baseURL)/quote/\(ticker.uppercased())")!
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        
        if let token = AuthService.shared.accessToken {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        
        let (data, response) = try await URLSession.shared.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse,
              200...299 ~= httpResponse.statusCode else {
            throw IBKRError.quoteFailed
        }
        
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        let result = try decoder.decode(IBKRQuoteResponse.self, from: data)
        return result.data
    }
    
    // MARK: - Historical Bars (REC-160)
    
    /// Get historical OHLCV bars from IB Gateway
    /// Better data quality than Yahoo Finance with real-time updates
    func getHistoricalBars(
        ticker: String,
        duration: String = "1 D",
        barSize: String = "5 mins",
        whatToShow: String = "TRADES",
        useRth: Bool = true
    ) async throws -> [IBKRBar] {
        var components = URLComponents(string: "\(baseURL)/bars/\(ticker.uppercased())")!
        components.queryItems = [
            URLQueryItem(name: "duration", value: duration),
            URLQueryItem(name: "bar_size", value: barSize),
            URLQueryItem(name: "what_to_show", value: whatToShow),
            URLQueryItem(name: "use_rth", value: useRth ? "true" : "false"),
        ]
        
        var request = URLRequest(url: components.url!)
        request.httpMethod = "GET"
        
        if let token = AuthService.shared.accessToken {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        
        let (data, response) = try await URLSession.shared.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse,
              200...299 ~= httpResponse.statusCode else {
            throw IBKRError.fetchFailed
        }
        
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        let result = try decoder.decode(IBKRBarsResponse.self, from: data)
        return result.data
    }
    
    // MARK: - Bracket Orders (REC-161)
    
    /// Submit a bracket order (entry + take-profit + stop-loss)
    /// All three orders are linked — professional risk management in one call
    func submitBracketOrder(
        ticker: String,
        side: String,
        quantity: Double,
        entryPrice: Double,
        takeProfitPrice: Double,
        stopLossPrice: Double,
        outsideRth: Bool = false
    ) async throws -> IBKRBracketResult {
        let url = URL(string: "\(baseURL)/bracket")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        if let token = AuthService.shared.accessToken {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        
        let body: [String: Any] = [
            "ticker": ticker,
            "side": side,
            "quantity": quantity,
            "entry_price": entryPrice,
            "take_profit_price": takeProfitPrice,
            "stop_loss_price": stopLossPrice,
            "outside_rth": outsideRth,
        ]
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        
        let (data, response) = try await URLSession.shared.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse,
              200...299 ~= httpResponse.statusCode else {
            let statusCode = (response as? HTTPURLResponse)?.statusCode ?? 0
            throw IBKRError.orderFailed("Bracket order failed: HTTP \(statusCode)")
        }
        
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        let result = try decoder.decode(IBKRBracketResponse.self, from: data)
        return result.data
    }
    
    // MARK: - Market Scanner (REC-157)
    
    /// Get market scanner results from IB Gateway
    /// Discover top gainers, losers, most active stocks in real-time
    func getScannerResults(
        scanCode: String = "TOP_PERC_GAIN",
        instrument: String = "STK",
        location: String = "STK.US.MAJOR",
        numRows: Int = 20,
        abovePrice: Double = 5.0,
        belowPrice: Double = 10000.0,
        aboveVolume: Int = 100000,
        marketCapAbove: Double = 1_000_000_000
    ) async throws -> [IBKRScannerResult] {
        var components = URLComponents(string: "\(baseURL)/scanner")!
        components.queryItems = [
            URLQueryItem(name: "scan_code", value: scanCode),
            URLQueryItem(name: "instrument", value: instrument),
            URLQueryItem(name: "location", value: location),
            URLQueryItem(name: "num_rows", value: String(numRows)),
            URLQueryItem(name: "above_price", value: String(abovePrice)),
            URLQueryItem(name: "below_price", value: String(belowPrice)),
            URLQueryItem(name: "above_volume", value: String(aboveVolume)),
            URLQueryItem(name: "market_cap_above", value: String(marketCapAbove)),
        ]
        
        var request = URLRequest(url: components.url!)
        request.httpMethod = "GET"
        
        if let token = AuthService.shared.accessToken {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        
        let (data, response) = try await URLSession.shared.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse,
              200...299 ~= httpResponse.statusCode else {
            throw IBKRError.fetchFailed
        }
        
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        let result = try decoder.decode(IBKRScannerResponse.self, from: data)
        return result.data
    }
    
    // MARK: - What-If Order Simulation (REC-162)
    
    /// Simulate an order to preview margin impact without placing it
    /// Shows initial/maintenance margin change and commission estimate
    func whatIfOrder(
        ticker: String,
        side: String,
        quantity: Double,
        orderType: String = "MARKET",
        limitPrice: Double? = nil
    ) async throws -> IBKRWhatIfResult {
        let url = URL(string: "\(baseURL)/whatif")!
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
            throw IBKRError.fetchFailed
        }
        
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        let result = try decoder.decode(IBKRWhatIfResponse.self, from: data)
        return result.data
    }
    
    // MARK: - Margin Monitor (REC-153)
    
    /// Get margin status and alerts
    func getMarginStatus() async throws -> IBKRMarginStatus {
        let url = URL(string: "\(baseURL)/margin")!
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        
        if let token = AuthService.shared.accessToken {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        
        let (data, response) = try await URLSession.shared.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse,
              200...299 ~= httpResponse.statusCode else {
            throw IBKRError.fetchFailed
        }
        
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        let result = try decoder.decode(IBKRMarginResponse.self, from: data)
        return result.data
    }
}

// MARK: - Errors

enum IBKRError: Error, LocalizedError {
    case connectionFailed(String)
    case disconnectFailed
    case orderFailed(String)
    case cancelFailed(String)
    case fetchFailed
    case quoteFailed
    case notConnected
    
    var errorDescription: String? {
        switch self {
        case .connectionFailed(let msg): return "IBKR connection failed: \(msg)"
        case .disconnectFailed: return "Failed to disconnect from IBKR"
        case .orderFailed(let msg): return "IBKR order failed: \(msg)"
        case .cancelFailed(let msg): return "Order cancellation failed: \(msg)"
        case .fetchFailed: return "Failed to fetch IBKR data"
        case .quoteFailed: return "Failed to fetch quote from IBKR"
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

struct IBKROpenOrdersResponse: Codable {
    let success: Bool
    let count: Int
    let data: [IBKROrderResult]
}

struct IBKRQuoteResponse: Codable {
    let success: Bool
    let data: IBKRQuote
}

struct IBKRQuote: Codable {
    let ticker: String
    let bid: Double?
    let ask: Double?
    let last: Double?
    let close: Double?
    let high: Double?
    let low: Double?
    let volume: Int?
    let price: Double?
    let mid: Double?
    let timestamp: String
}

// MARK: - Historical Bars (REC-160)

struct IBKRBarsResponse: Codable {
    let success: Bool
    let ticker: String
    let duration: String
    let barSize: String
    let count: Int
    let data: [IBKRBar]
}

struct IBKRBar: Codable, Identifiable {
    let date: String
    let open: Double
    let high: Double
    let low: Double
    let close: Double
    let volume: Int
    
    var id: String { date }
}

// MARK: - Bracket Orders (REC-161)

struct IBKRBracketResponse: Codable {
    let success: Bool
    let message: String
    let data: IBKRBracketResult
}

struct IBKRBracketResult: Codable {
    let ticker: String
    let side: String
    let quantity: Double
    let entry: IBKRBracketLeg
    let takeProfit: IBKRBracketLeg
    let stopLoss: IBKRBracketLeg
    let isPaper: Bool
}

struct IBKRBracketLeg: Codable {
    let orderId: String
    let orderType: String
    let status: String
    let limitPrice: Double?
    let stopPrice: Double?
}

// MARK: - Market Scanner (REC-157)

struct IBKRScannerResponse: Codable {
    let success: Bool
    let scanCode: String
    let count: Int
    let data: [IBKRScannerResult]
}

struct IBKRScannerResult: Codable, Identifiable {
    let rank: Int
    let ticker: String
    let exchange: String
    let contractId: Int?
    let distance: String?
    let benchmark: String?
    let projection: String?
    let legsStr: String?
    
    var id: Int { rank }
}

// MARK: - What-If Order (REC-162)

struct IBKRWhatIfResponse: Codable {
    let success: Bool
    let data: IBKRWhatIfResult
}

struct IBKRWhatIfResult: Codable {
    let ticker: String
    let side: String
    let quantity: Double
    let orderType: String
    let limitPrice: Double?
    
    // Margin info
    let initMarginBefore: Double
    let initMarginAfter: Double
    let initMarginChange: Double
    let maintMarginBefore: Double
    let maintMarginAfter: Double
    let maintMarginChange: Double
    let equityWithLoanBefore: Double
    let equityWithLoanAfter: Double
    let equityWithLoanChange: Double
    
    // Commission
    let commission: Double
    let minCommission: Double
    let maxCommission: Double
    let commissionCurrency: String
    
    // Warning
    let warningText: String?
}

// MARK: - Margin Monitor (REC-153)

struct IBKRMarginResponse: Codable {
    let success: Bool
    let data: IBKRMarginStatus
}

struct IBKRMarginStatus: Codable {
    let netLiquidation: Double
    let buyingPower: Double
    let grossPositionValue: Double
    let marginUsedPercent: Double
    let marginAvailablePercent: Double
    let alertLevel: String?
    let isPaper: Bool
}
