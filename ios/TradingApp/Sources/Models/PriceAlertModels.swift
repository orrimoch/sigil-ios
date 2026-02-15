import Foundation

// MARK: - Price Alert Models (REC-158)

/// A price alert condition type
enum PriceAlertCondition: String, Codable, CaseIterable {
    case above = "ABOVE"
    case below = "BELOW"
    
    var displayName: String {
        switch self {
        case .above: return "Above"
        case .below: return "Below"
        }
    }
    
    var icon: String {
        switch self {
        case .above: return "arrow.up.circle.fill"
        case .below: return "arrow.down.circle.fill"
        }
    }
}

/// A user's price alert
struct PriceAlert: Codable, Identifiable {
    let id: String
    let userId: String
    let ticker: String
    let condition: String
    let targetPrice: Double
    let createdAt: String
    let triggeredAt: String?
    let isActive: Bool
    
    var conditionType: PriceAlertCondition {
        PriceAlertCondition(rawValue: condition) ?? .above
    }
    
    var createdDate: Date? {
        ISO8601DateFormatter().date(from: createdAt)
    }
    
    var triggeredDate: Date? {
        guard let triggeredAt else { return nil }
        return ISO8601DateFormatter().date(from: triggeredAt)
    }
}

/// Request to create a price alert
struct CreatePriceAlertRequest: Codable {
    let ticker: String
    let condition: String
    let targetPrice: Double
    
    enum CodingKeys: String, CodingKey {
        case ticker
        case condition
        case targetPrice = "target_price"
    }
}

/// Response from creating a price alert
struct CreatePriceAlertResponse: Codable {
    let success: Bool
    let message: String
    let data: PriceAlert
}

/// Response from listing price alerts
struct PriceAlertsResponse: Codable {
    let success: Bool
    let count: Int
    let data: [PriceAlert]
}

/// Response from deleting a price alert
struct DeletePriceAlertResponse: Codable {
    let success: Bool
    let message: String
}
