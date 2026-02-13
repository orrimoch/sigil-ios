import Foundation

// MARK: - REC-261: Crowd Wisdom iOS Models
// Note: No CodingKeys needed - decoder uses .convertFromSnakeCase

/// Weekly top pick stock with insider buying signals
struct SmartMoneyPick: Codable, Identifiable {
    let rank: Int
    let ticker: String
    let companyName: String
    let insiderScore: Double
    let insiderBuyCount: Int
    let insiderBuyValue: Double
    let notableEvents: [String]
    let currentPrice: Double?
    let signal: String
    
    var id: String { ticker }
    
    /// Formatted buy value (e.g., "$1.2M")
    var formattedBuyValue: String {
        if insiderBuyValue >= 1_000_000 {
            return String(format: "$%.1fM", insiderBuyValue / 1_000_000)
        } else if insiderBuyValue >= 1_000 {
            return String(format: "$%.0fK", insiderBuyValue / 1_000)
        } else {
            return String(format: "$%.0f", insiderBuyValue)
        }
    }
    
    /// Signal color
    var signalColor: String {
        switch signal {
        case "STRONG_BUY": return "green"
        case "BUY": return "blue"
        default: return "gray"
        }
    }
    
    /// Signal emoji
    var signalEmoji: String {
        switch signal {
        case "STRONG_BUY": return "🔥"
        case "BUY": return "📈"
        default: return "➖"
        }
    }
}

/// Response from /api/v1/crowd-wisdom/top-picks
struct TopPicksResponse: Codable {
    let success: Bool
    let weekStart: String
    let picks: [SmartMoneyPick]
}

/// Detailed crowd wisdom score for a stock
struct CrowdWisdomScore: Codable, Identifiable {
    let ticker: String
    let companyName: String
    let sector: String
    let currentPrice: Double?
    let insiderScore: Double
    let insiderBuyCount: Int
    let insiderBuyValue: Double
    let insiderCluster: Bool
    let executiveBuys: Int
    let notableEvents: [String]
    let discoveryReason: String
    let signal: String
    
    var id: String { ticker }
}

/// Response from /api/v1/crowd-wisdom/scores
struct CrowdWisdomScoresResponse: Codable {
    let success: Bool
    let count: Int
    let weekStart: String
    let scores: [CrowdWisdomScore]
}
