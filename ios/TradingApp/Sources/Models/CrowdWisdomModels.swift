import Foundation

// MARK: - REC-266: Reddit-Based Crowd Wisdom Models
// Note: No CodingKeys needed - decoder uses .convertFromSnakeCase

/// Weekly trending stock pick based on Reddit viral activity
struct SmartMoneyPick: Codable, Identifiable {
    let rank: Int
    let ticker: String
    let companyName: String
    let viralScore: Double
    let mentionCount: Int
    let totalUpvotes: Int
    let sentimentLabel: String
    let trendingVelocity: Double
    let currentPrice: Double?
    let signal: String
    
    var id: String { ticker }
    
    /// Formatted upvote count (e.g., "1.5K")
    var formattedUpvotes: String {
        if totalUpvotes >= 1_000_000 {
            return String(format: "%.1fM", Double(totalUpvotes) / 1_000_000)
        } else if totalUpvotes >= 1_000 {
            return String(format: "%.1fK", Double(totalUpvotes) / 1_000)
        } else {
            return "\(totalUpvotes)"
        }
    }
    
    /// Formatted mention count
    var formattedMentions: String {
        if mentionCount >= 1_000 {
            return String(format: "%.1fK", Double(mentionCount) / 1_000)
        } else {
            return "\(mentionCount)"
        }
    }
    
    /// Signal color based on signal type
    var signalColor: String {
        switch signal {
        case "VERY_HOT": return "red"
        case "HOT": return "orange"
        case "TRENDING": return "yellow"
        default: return "gray"
        }
    }
    
    /// Signal emoji based on sentiment and signal
    var signalEmoji: String {
        switch signal {
        case "VERY_HOT": return "🔥"
        case "HOT": return "📈"
        case "TRENDING": return "✨"
        default: return "➖"
        }
    }
    
    /// Sentiment emoji
    var sentimentEmoji: String {
        switch sentimentLabel {
        case "VERY_BULLISH": return "🚀"
        case "BULLISH": return "📈"
        case "NEUTRAL": return "➖"
        case "BEARISH": return "📉"
        case "VERY_BEARISH": return "💀"
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

/// Detailed trending ticker with full viral score data
struct TrendingTicker: Codable, Identifiable {
    let ticker: String
    let companyName: String
    let viralScore: Double
    let mentionCount: Int
    let totalUpvotes: Int
    let totalComments: Int
    let uniquePosts: Int
    let subreddits: [String]
    let avgSentiment: Double?
    let sentimentLabel: String
    let trendingVelocity: Double
    let currentPrice: Double?
    let revenueTtm: Double?
    let epsLatest: Double?
    let passesFilters: Bool
    let filterReason: String?
    let signal: String
    
    var id: String { ticker }
    
    /// Formatted viral score
    var formattedViralScore: String {
        String(format: "%.1f", viralScore)
    }
    
    /// Formatted subreddits list
    var subredditList: String {
        subreddits.map { "r/\($0)" }.joined(separator: ", ")
    }
}

/// Response from /api/v1/crowd-wisdom/trending
struct TrendingListResponse: Codable {
    let success: Bool
    let count: Int
    let weekStart: String
    let tickers: [TrendingTicker]
}

/// Response from /api/v1/crowd-wisdom/scores/{ticker}
struct TickerScoreResponse: Codable {
    let success: Bool
    let ticker: String
    let companyName: String
    let viralScore: Double
    let mentionCount: Int
    let totalUpvotes: Int
    let totalComments: Int
    let subreddits: [String]
    let sentimentLabel: String
    let trendingVelocity: Double
    let passesFilters: Bool
    let filterReason: String?
    let signal: String
    let weekStart: String
}

// MARK: - Legacy Compatibility Aliases

/// Alias for backward compatibility with existing code
typealias CrowdWisdomScore = TrendingTicker

/// Alias for backward compatibility
typealias CrowdWisdomScoresResponse = TrendingListResponse
