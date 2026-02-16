import Foundation

// MARK: - AI Config Response (REC-272)

/// API wrapper for AI config
struct AIConfigAPIResponse: Codable {
    let success: Bool
    let data: AIConfigResponse
}

/// AI configuration details
struct AIConfigResponse: Codable {
    let provider: String
    let model: String
    let available: Bool
    let fallbackModel: String?
    let note: String?
    
    /// Display name for UI
    var providerDisplayName: String {
        switch provider.lowercased() {
        case "anthropic":
            return "Claude (\(modelShortName))"
        case "openai":
            return "GPT (\(modelShortName))"
        case "google":
            return "Gemini (\(modelShortName))"
        default:
            return provider.capitalized
        }
    }
    
    private var modelShortName: String {
        // Extract short name from model ID
        if model.contains("haiku") { return "Haiku" }
        if model.contains("sonnet") { return "Sonnet" }
        if model.contains("opus") { return "Opus" }
        if model.contains("4o-mini") { return "4o mini" }
        if model.contains("4o") { return "4o" }
        if model.contains("o1-mini") { return "o1 mini" }
        if model.contains("o1") { return "o1" }
        if model.contains("flash") { return "Flash" }
        if model.contains("pro") { return "Pro" }
        return model
    }
}

// MARK: - AI Providers List

/// API wrapper for providers list
struct AIProvidersAPIResponse: Codable {
    let success: Bool
    let data: AIProvidersResponse
}

/// Available AI providers
struct AIProvidersResponse: Codable {
    let currentProvider: String
    let providers: [AIProviderInfo]
}

/// Individual provider info
struct AIProviderInfo: Codable, Identifiable {
    let provider: String
    let name: String
    let models: [String]
    let defaultModel: String
    let configured: Bool
    let envVar: String
    
    var id: String { provider }
    
    /// Icon for this provider
    var icon: String {
        switch provider.lowercased() {
        case "anthropic": return "brain.head.profile"
        case "openai": return "sparkle"
        case "google": return "globe"
        default: return "cpu"
        }
    }
    
    /// Color for this provider
    var color: String {
        switch provider.lowercased() {
        case "anthropic": return "orange"
        case "openai": return "green"
        case "google": return "blue"
        default: return "gray"
        }
    }
}
