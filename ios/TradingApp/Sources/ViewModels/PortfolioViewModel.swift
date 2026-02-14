import SwiftUI
import Combine

/// F7.x Portfolio View Model
/// Manages portfolio data, holdings, performance, and sector allocation
@MainActor
class PortfolioViewModel: ObservableObject {
    // MARK: - Published Properties
    
    // Summary
    @Published var summary: PortfolioSummary?
    @Published var holdings: [Holding] = []
    @Published var isPaper: Bool = true
    @Published var realizedPnl: Double = 0
    
    // F7.2: History & Performance
    @Published var history: [PortfolioSnapshot] = []
    @Published var performance: PortfolioPerformance?
    @Published var selectedPeriod: PerformancePeriod = .oneWeek
    @Published var portfolioAgeDays: Int = 0  // Days since first trade/snapshot
    
    // F7.3: Sector Allocation
    @Published var sectorAllocation: [SectorAllocation] = []
    
    // REC-230: Portfolio Risk Score
    @Published var portfolioRiskScore: RiskScore = .low
    @Published var isLoadingRisk = false
    
    // Risk Module: Full VaR Display
    @Published var var95Daily: Double?
    @Published var var95Pct: Double?
    
    // Risk Module: Sector Concentration Warnings
    @Published var sectorWarnings: [SectorWarning] = []
    @Published var sectorHHI: Double?
    
    // REC-231: Risk Settings (for stop distance calculation)
    @Published var riskSettings: RiskSettingsData?
    
    // Loading states
    @Published var isLoading = false
    @Published var isLoadingHistory = false
    @Published var isLoadingSectors = false
    @Published var error: String?
    
    // MARK: - Private
    
    private let api = APIService.shared
    
    // MARK: - Computed Properties
    
    var totalValue: Double {
        summary?.totalValue ?? 100_000
    }
    
    var dailyPnl: Double {
        summary?.dailyPnl ?? 0
    }
    
    var dailyPnlPercent: Double {
        summary?.dailyPnlPercent ?? 0
    }
    
    var cash: Double {
        summary?.cash ?? 100_000
    }
    
    var positionsValue: Double {
        summary?.positionsValue ?? 0
    }
    
    // MARK: - Data Fetching
    
    func fetchPortfolio() async {
        isLoading = true
        error = nil
        
        do {
            let response = try await api.getPortfolio()
            summary = response.data.summary
            holdings = response.data.holdings
            isPaper = response.data.isPaper
            realizedPnl = response.data.realizedPnl
        } catch {
            self.error = error.localizedDescription
            debugError(error, context: "Portfolio")
        }
        
        isLoading = false
    }
    
    func fetchHistory() async {
        isLoadingHistory = true
        
        do {
            // Fetch real history computed from trade records
            let response = try await api.getPortfolioHistory(days: selectedPeriod.days)
            history = response.data
            
            // Calculate portfolio age from first snapshot
            if let firstSnapshot = response.data.first {
                let formatter = ISO8601DateFormatter()
                formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
                if let firstDate = formatter.date(from: firstSnapshot.timestamp) ?? {
                    formatter.formatOptions = [.withInternetDateTime]
                    return formatter.date(from: firstSnapshot.timestamp)
                }() {
                    portfolioAgeDays = max(1, Calendar.current.dateComponents([.day], from: firstDate, to: Date()).day ?? 1)
                    
                    // Auto-select appropriate period on first load
                    if selectedPeriod.days > portfolioAgeDays * 2 {
                        selectedPeriod = appropriatePeriod
                    }
                }
            }
            
            let perfResponse = try await api.getPortfolioPerformance(days: selectedPeriod.days)
            performance = perfResponse.data
        } catch {
            debugError(error, context: "History")
            // No fallback — show empty state if API fails
            history = []
        }
        
        isLoadingHistory = false
    }
    
    /// Returns periods that make sense for the portfolio's age
    var availablePeriods: [PerformancePeriod] {
        PerformancePeriod.allCases.filter { period in
            // Show period if portfolio is at least 50% of that period's duration
            // (e.g., show 1W if portfolio is at least 3-4 days old)
            period.days <= portfolioAgeDays * 2 || period == .all
        }
    }
    
    /// Best period to show based on portfolio age
    var appropriatePeriod: PerformancePeriod {
        if portfolioAgeDays <= 7 { return .oneWeek }
        if portfolioAgeDays <= 30 { return .oneMonth }
        if portfolioAgeDays <= 90 { return .threeMonths }
        return .oneYear
    }
    
    /// REMOVED: No more fake data generation
    /// History now comes from real trade records on the backend.
    
    // Keep for backward compat if referenced elsewhere
    @available(*, deprecated, message: "Use real history from API")
    private func generateLocalFallbackHistory() -> [PortfolioSnapshot] {
        return [] // No fake data
    }
    
    // MARK: - Sector Allocation
    
    func fetchSectorAllocation() async {
        isLoadingSectors = true
        
        do {
            let response = try await api.getSectorAllocation()
            sectorAllocation = response.data
        } catch {
            debugError(error, context: "Sectors")
        }
        
        isLoadingSectors = false
    }
    
    func resetPortfolio() async {
        isLoading = true
        
        do {
            _ = try await api.resetPortfolio()
            await fetchPortfolio()
            await fetchHistory()
            await fetchSectorAllocation()
        } catch {
            self.error = error.localizedDescription
        }
        
        isLoading = false
    }
    
    // MARK: - REC-230: Portfolio Risk Score
    
    func fetchPortfolioRisk() async {
        isLoadingRisk = true
        
        do {
            let response = try await api.getPortfolioRisk()
            if let data = response.data {
                // Convert string to RiskScore enum
                portfolioRiskScore = RiskScore(rawValue: data.riskScore) ?? .low
                
                // Risk Module: Extract VaR data for display
                var95Daily = data.var95Daily
                var95Pct = data.var95Pct
            }
        } catch {
            debugError(error, context: "Portfolio risk")
            // Default to low on error (don't block UI)
            portfolioRiskScore = .low
        }
        
        isLoadingRisk = false
    }
    
    // MARK: - Risk Module: Sector Concentration
    
    func fetchSectorRisk() async {
        do {
            let response = try await api.getSectorRisk()
            sectorWarnings = response.warnings
            sectorHHI = response.hhi
        } catch {
            debugError(error, context: "Sector risk")
            // Don't block UI on error
        }
    }
    
    // MARK: - REC-231: Risk Settings for Stop Distance
    
    func fetchRiskSettings() async {
        do {
            let response = try await api.getRiskSettings()
            riskSettings = response.data
        } catch {
            debugError(error, context: "Risk settings")
        }
    }
    
    /// Calculate stop distance for a holding based on risk settings
    func stopDistance(for holding: Holding) -> (stopPrice: Double, distancePct: Double, stopType: String)? {
        guard let settings = riskSettings else { return nil }
        
        // Check trailing stop first (it's more dynamic)
        if settings.trailingStop.enabled {
            // Use current price as high water mark approximation
            // In production, HWM would come from backend
            let highWaterMark = max(holding.currentPrice, holding.avgCost)
            let trailPct = settings.trailingStop.distancePct
            let stopPrice = highWaterMark * (1 + trailPct)
            let distancePct = (stopPrice - holding.currentPrice) / holding.currentPrice * 100
            return (stopPrice, distancePct, "trailing")
        }
        
        // Fall back to hard stop
        if settings.hardStop.enabled {
            let stopPrice = holding.avgCost * (1 + settings.hardStop.thresholdPct)
            let distancePct = (stopPrice - holding.currentPrice) / holding.currentPrice * 100
            return (stopPrice, distancePct, "hard")
        }
        
        return nil
    }
    
    func fetchAll() async {
        await fetchPortfolio()
        await fetchHistory()
        await fetchSectorAllocation()
        await fetchPortfolioRisk()
        await fetchRiskSettings()
        await fetchSectorRisk()  // Risk Module: Sector concentration warnings
    }
}

// MARK: - Performance Period

enum PerformancePeriod: String, CaseIterable {
    case oneWeek = "1W"
    case oneMonth = "1M"
    case threeMonths = "3M"
    case oneYear = "1Y"
    case all = "All"
    
    var days: Int {
        switch self {
        case .oneWeek: return 7
        case .oneMonth: return 30
        case .threeMonths: return 90
        case .oneYear: return 365
        case .all: return 365
        }
    }
}
