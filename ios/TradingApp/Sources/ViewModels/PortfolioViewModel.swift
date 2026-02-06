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
    @Published var selectedPeriod: PerformancePeriod = .oneMonth
    
    // F7.3: Sector Allocation
    @Published var sectorAllocation: [SectorAllocation] = []
    
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
            print("Portfolio error: \(error)")
        }
        
        isLoading = false
    }
    
    func fetchHistory() async {
        isLoadingHistory = true
        
        do {
            // Fetch real history computed from trade records
            let response = try await api.getPortfolioHistory(days: selectedPeriod.days)
            history = response.data
            
            let perfResponse = try await api.getPortfolioPerformance(days: selectedPeriod.days)
            performance = perfResponse.data
        } catch {
            print("History error: \(error)")
            // No fallback — show empty state if API fails
            history = []
        }
        
        isLoadingHistory = false
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
            print("Sectors error: \(error)")
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
    
    func fetchAll() async {
        await fetchPortfolio()
        await fetchHistory()
        await fetchSectorAllocation()
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
