import Foundation

// MARK: - Agent Status

enum AgentStatusType: String, Codable {
    case active = "active"
    case paused = "paused"
    case running = "running"
    case error = "error"
    
    var displayName: String {
        switch self {
        case .active: return "Active"
        case .paused: return "Paused"
        case .running: return "Running"
        case .error: return "Error"
        }
    }
    
    var color: String {
        switch self {
        case .active: return "green"
        case .paused: return "yellow"
        case .running: return "blue"
        case .error: return "red"
        }
    }
}

struct AgentStatus: Codable {
    let status: String
    let settings: AgentSettings
    let lastRun: AgentRunSummary?
    let totalRuns: Int
    let pendingApprovals: Int
    
    var statusType: AgentStatusType {
        AgentStatusType(rawValue: status) ?? .paused
    }
}

struct AgentSettings: Codable {
    var mode: String
    var maxTradesPerWeek: Int
    var minScoreForBuy: Double
    var maxScoreForSell: Double
    var riskProfile: String
    var stopLossEnabled: Bool
    var stopLossPercent: Double
    var autoRunEnabled: Bool
    
    enum CodingKeys: String, CodingKey {
        case mode
        case maxTradesPerWeek = "max_trades_per_week"
        case minScoreForBuy = "min_score_for_buy"
        case maxScoreForSell = "max_score_for_sell"
        case riskProfile = "risk_profile"
        case stopLossEnabled = "stop_loss_enabled"
        case stopLossPercent = "stop_loss_percent"
        case autoRunEnabled = "auto_run_enabled"
    }
    
    static var `default`: AgentSettings {
        AgentSettings(
            mode: "supervised",
            maxTradesPerWeek: 5,
            minScoreForBuy: 70,
            maxScoreForSell: 40,
            riskProfile: "moderate",
            stopLossEnabled: true,
            stopLossPercent: 8.0,
            autoRunEnabled: false
        )
    }
}

struct AgentRunSummary: Codable {
    let runId: String
    let startedAt: String
    let completedAt: String?
    let decisionsMade: Int
    let executionsSucceeded: Int
    let success: Bool
    
    enum CodingKeys: String, CodingKey {
        case runId = "run_id"
        case startedAt = "started_at"
        case completedAt = "completed_at"
        case decisionsMade = "decisions_made"
        case executionsSucceeded = "executions_succeeded"
        case success
    }
}

// MARK: - Pending Trade Approval

struct PendingTrade: Codable, Identifiable {
    let id: String
    let ticker: String
    let action: String
    let shares: Int
    let estimatedPrice: Double
    let estimatedValue: Double
    let rationale: String
    let createdAt: String
    let expiresAt: String
    let isExpired: Bool
    
    enum CodingKeys: String, CodingKey {
        case id
        case ticker
        case action
        case shares
        case estimatedPrice = "estimated_price"
        case estimatedValue = "estimated_value"
        case rationale
        case createdAt = "created_at"
        case expiresAt = "expires_at"
        case isExpired = "is_expired"
    }
    
    var isBuy: Bool { action.uppercased() == "BUY" }
    
    var actionColor: String {
        isBuy ? "green" : "red"
    }
    
    var formattedValue: String {
        "$\(Int(estimatedValue).formatted())"
    }
}

// MARK: - Agent Decision

struct AgentDecision: Codable, Identifiable {
    let id: String
    let ticker: String
    let action: String
    let rationale: String
    let confidence: Double
    let score: Double
    let timestamp: String
    let outcome: DecisionOutcome?
    
    struct DecisionOutcome: Codable {
        let outcomePct: Double
        let exitPrice: Double?
        let exitDate: String?
        
        enum CodingKeys: String, CodingKey {
            case outcomePct = "outcome_pct"
            case exitPrice = "exit_price"
            case exitDate = "exit_date"
        }
    }
    
    var formattedDate: String {
        // Parse ISO date and format nicely
        let formatter = ISO8601DateFormatter()
        if let date = formatter.date(from: timestamp) {
            let displayFormatter = DateFormatter()
            displayFormatter.dateStyle = .medium
            displayFormatter.timeStyle = .short
            return displayFormatter.string(from: date)
        }
        return timestamp
    }
}

// MARK: - Agent Execution

struct AgentExecution: Codable, Identifiable {
    var id: String { orderId ?? UUID().uuidString }
    let ticker: String
    let action: String
    let shares: Int
    let fillPrice: Double?
    let fillValue: Double?
    let orderId: String?
    let executedAt: String?
    let success: Bool
    let message: String
    
    enum CodingKeys: String, CodingKey {
        case ticker
        case action
        case shares
        case fillPrice = "fill_price"
        case fillValue = "fill_value"
        case orderId = "order_id"
        case executedAt = "executed_at"
        case success
        case message
    }
}

// MARK: - Agent Stats

struct AgentStats: Codable {
    let totalDecisions: Int
    let totalExecutions: Int
    let successRate: Double
    let avgOutcome: Double
    let weeklyTrades: Int
    let lessonsLearned: Int
    
    enum CodingKeys: String, CodingKey {
        case totalDecisions = "total_decisions"
        case totalExecutions = "total_executions"
        case successRate = "success_rate"
        case avgOutcome = "avg_outcome"
        case weeklyTrades = "weekly_trades"
        case lessonsLearned = "lessons_learned"
    }
}

// MARK: - API Responses

struct AgentStatusResponse: Codable {
    let status: String
    let settings: [String: AnyCodable]
    let lastRun: [String: AnyCodable]?
    let totalRuns: Int
    let pendingApprovals: Int
    
    enum CodingKeys: String, CodingKey {
        case status
        case settings
        case lastRun = "last_run"
        case totalRuns = "total_runs"
        case pendingApprovals = "pending_approvals"
    }
}

struct PendingTradesResponse: Codable {
    let pending: [PendingTrade]
    let count: Int
}

struct ApprovalResponse: Codable {
    let success: Bool
    let message: String
    let executionResult: [String: AnyCodable]?
    
    enum CodingKeys: String, CodingKey {
        case success
        case message
        case executionResult = "execution_result"
    }
}

struct DecisionsResponse: Codable {
    let decisions: [AgentDecision]
    let total: Int
}

struct ExecutionsResponse: Codable {
    let executions: [AgentExecution]
    let total: Int
}

// MARK: - AnyCodable Helper

struct AnyCodable: Codable {
    let value: Any
    
    init(_ value: Any) {
        self.value = value
    }
    
    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if let bool = try? container.decode(Bool.self) {
            value = bool
        } else if let int = try? container.decode(Int.self) {
            value = int
        } else if let double = try? container.decode(Double.self) {
            value = double
        } else if let string = try? container.decode(String.self) {
            value = string
        } else if let array = try? container.decode([AnyCodable].self) {
            value = array.map { $0.value }
        } else if let dict = try? container.decode([String: AnyCodable].self) {
            value = dict.mapValues { $0.value }
        } else {
            value = NSNull()
        }
    }
    
    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch value {
        case let bool as Bool: try container.encode(bool)
        case let int as Int: try container.encode(int)
        case let double as Double: try container.encode(double)
        case let string as String: try container.encode(string)
        default: try container.encodeNil()
        }
    }
}
