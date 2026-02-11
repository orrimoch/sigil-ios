import Foundation
import Combine

/// REC-215: Risk Settings Service
/// Manages user risk preferences and syncs with backend API.
class RiskSettingsService: ObservableObject {
    static let shared = RiskSettingsService()
    
    // MARK: - Published Properties
    
    @Published private(set) var settings: RiskSettings = .defaults
    @Published private(set) var isLoading = false
    @Published private(set) var lastError: String?
    @Published private(set) var isSyncing = false
    
    // MARK: - Private Properties
    
    private var cancellables = Set<AnyCancellable>()
    private let apiService = APIService.shared
    
    // MARK: - Initialization
    
    private init() {
        // Load cached settings on init
        loadCachedSettings()
    }
    
    // MARK: - Public Methods
    
    /// Fetch settings from backend
    func fetchSettings() async {
        await MainActor.run { isLoading = true; lastError = nil }
        
        do {
            let response = try await apiService.getRiskSettings()
            print("🔍 RiskSettings fetch - success: \(response.success), hasData: \(response.data != nil)")
            
            if response.success, let data = response.data {
                let newSettings = RiskSettings.from(data)
                print("🔍 RiskSettings loaded - hardStop.enabled: \(newSettings.hardStop.enabled)")
                await MainActor.run {
                    self.settings = newSettings
                    self.cacheSettings(newSettings)
                    self.isLoading = false
                }
            } else {
                // Use cached settings if not logged in
                let errorMessage = response.error ?? "Please log in to sync settings"
                print("⚠️ RiskSettings fetch failed: \(errorMessage)")
                await MainActor.run {
                    self.lastError = errorMessage
                    self.isLoading = false
                }
            }
        } catch {
            print("❌ RiskSettings fetch error: \(error)")
            await MainActor.run {
                self.lastError = error.localizedDescription
                self.isLoading = false
            }
        }
    }
    
    /// Update settings on backend
    func updateSettings(_ newSettings: RiskSettings) async throws {
        await MainActor.run { isSyncing = true; lastError = nil }
        
        do {
            let payload = newSettings.toUpdatePayload()
            let response = try await apiService.updateRiskSettings(payload)
            
            if response.success, let data = response.data {
                let updated = RiskSettings.from(data)
                await MainActor.run {
                    self.settings = updated
                    self.cacheSettings(updated)
                    self.isSyncing = false
                }
            } else {
                // Show specific error message from backend
                let errorMessage = response.error ?? "Failed to save settings"
                throw NSError(domain: "RiskSettings", code: 0, userInfo: [NSLocalizedDescriptionKey: errorMessage])
            }
        } catch {
            await MainActor.run {
                self.lastError = error.localizedDescription
                self.isSyncing = false
            }
            throw error
        }
    }
    
    /// Reset settings to defaults
    func resetToDefaults() async throws {
        await MainActor.run { isSyncing = true }
        
        do {
            let response = try await apiService.resetRiskSettings()
            
            if response.success, let data = response.data {
                let updated = RiskSettings.from(data)
                await MainActor.run {
                    self.settings = updated
                    self.cacheSettings(updated)
                    self.isSyncing = false
                }
            } else {
                throw APIError.invalidResponse
            }
        } catch {
            await MainActor.run {
                self.lastError = error.localizedDescription
                self.isSyncing = false
            }
            throw error
        }
    }
    
    // MARK: - Private Methods
    
    private func loadCachedSettings() {
        // Try to load cached settings, clear if corrupt/outdated
        if let data = UserDefaults.standard.data(forKey: "cached_risk_settings") {
            do {
                let cached = try JSONDecoder().decode(RiskSettings.self, from: data)
                settings = cached
            } catch {
                // Cache is corrupt or outdated - clear it
                UserDefaults.standard.removeObject(forKey: "cached_risk_settings")
                print("Cleared corrupt risk settings cache: \(error)")
            }
        }
    }
    
    private func cacheSettings(_ settings: RiskSettings) {
        if let data = try? JSONEncoder().encode(settings) {
            UserDefaults.standard.set(data, forKey: "cached_risk_settings")
        }
    }
}

// MARK: - Risk Settings Model

struct RiskSettings: Codable, Equatable {
    var userId: String?
    var hardStop: StopConfig
    var trailingStop: TrailingStopConfig
    var vixAdjustment: VixAdjustmentConfig
    var positionLimit: PositionLimitConfig
    
    /// Default settings (all OFF)
    static let defaults = RiskSettings(
        userId: nil,
        hardStop: StopConfig.defaults,
        trailingStop: TrailingStopConfig.defaults,
        vixAdjustment: VixAdjustmentConfig.defaults,
        positionLimit: PositionLimitConfig.defaults
    )
    
    /// Create from API response data
    static func from(_ data: RiskSettingsData) -> RiskSettings {
        RiskSettings(
            userId: data.userId,
            hardStop: StopConfig(enabled: data.hardStop.enabled, thresholdPct: data.hardStop.thresholdPct),
            trailingStop: TrailingStopConfig(enabled: data.trailingStop.enabled, distancePct: data.trailingStop.distancePct),
            vixAdjustment: VixAdjustmentConfig(enabled: data.vixAdjustment.enabled),
            positionLimit: PositionLimitConfig(enabled: data.positionLimit.enabled, maxPct: data.positionLimit.maxPct)
        )
    }
    
    /// Convert to API update payload
    func toUpdatePayload() -> RiskSettingsUpdatePayload {
        RiskSettingsUpdatePayload(
            hardStop: RiskStopData(enabled: hardStop.enabled, thresholdPct: hardStop.thresholdPct),
            trailingStop: RiskTrailingStopData(enabled: trailingStop.enabled, distancePct: trailingStop.distancePct),
            vixAdjustment: RiskVixData(enabled: vixAdjustment.enabled),
            positionLimit: RiskPositionLimitData(enabled: positionLimit.enabled, maxPct: positionLimit.maxPct)
        )
    }
}

struct StopConfig: Codable, Equatable {
    var enabled: Bool
    var thresholdPct: Double  // e.g., -0.08 for -8%
    
    static let defaults = StopConfig(enabled: false, thresholdPct: -0.08)
    
    /// Percentage as display string (e.g., "-8%")
    var displayPercentage: String {
        String(format: "%.0f%%", thresholdPct * 100)
    }
}

struct TrailingStopConfig: Codable, Equatable {
    var enabled: Bool
    var distancePct: Double  // e.g., -0.10 for -10%
    
    static let defaults = TrailingStopConfig(enabled: false, distancePct: -0.10)
    
    /// Percentage as display string (e.g., "-10%")
    var displayPercentage: String {
        String(format: "%.0f%%", distancePct * 100)
    }
}

struct VixAdjustmentConfig: Codable, Equatable {
    var enabled: Bool
    
    static let defaults = VixAdjustmentConfig(enabled: false)
}

struct PositionLimitConfig: Codable, Equatable {
    var enabled: Bool
    var maxPct: Double  // e.g., 0.15 for 15%
    
    static let defaults = PositionLimitConfig(enabled: false, maxPct: 0.15)
    
    /// Percentage as display string (e.g., "15%")
    var displayPercentage: String {
        String(format: "%.0f%%", maxPct * 100)
    }
}
