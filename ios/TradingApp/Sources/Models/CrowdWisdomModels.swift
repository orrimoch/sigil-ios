import Foundation

// MARK: - REC-261: Crowd Wisdom iOS Models

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
    
    enum CodingKeys: String, CodingKey {
        case rank
        case ticker
        case companyName = "company_name"
        case insiderScore = "insider_score"
        case insiderBuyCount = "insider_buy_count"
        case insiderBuyValue = "insider_buy_value"
        case notableEvents = "notable_events"
        case currentPrice = "current_price"
        case signal
    }
    
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
    
    enum CodingKeys: String, CodingKey {
        case success
        case weekStart = "week_start"
        case picks
    }
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
    
    enum CodingKeys: String, CodingKey {
        case ticker
        case companyName = "company_name"
        case sector
        case currentPrice = "current_price"
        case insiderScore = "insider_score"
        case insiderBuyCount = "insider_buy_count"
        case insiderBuyValue = "insider_buy_value"
        case insiderCluster = "insider_cluster"
        case executiveBuys = "executive_buys"
        case notableEvents = "notable_events"
        case discoveryReason = "discovery_reason"
        case signal
    }
}

/// Response from /api/v1/crowd-wisdom/scores
struct CrowdWisdomScoresResponse: Codable {
    let success: Bool
    let count: Int
    let weekStart: String
    let scores: [CrowdWisdomScore]
    
    enum CodingKeys: String, CodingKey {
        case success
        case count
        case weekStart = "week_start"
        case scores
    }
}
