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
            let response = try await api.getPortfolioHistory(days: selectedPeriod.days)
            history = response.data
            
            let perfResponse = try await api.getPortfolioPerformance(days: selectedPeriod.days)
            performance = perfResponse.data
        } catch {
            print("History error: \(error)")
        }
        
        // If history is empty, generate synthetic data based on actual portfolio state
        // TODO: Replace with a real portfolio performance API endpoint when available
        if history.isEmpty {
            history = generateSyntheticHistory()
        }
        
        isLoadingHistory = false
    }
    
    /// Generate synthetic history based on actual portfolio state.
    /// Shows flat line at current portfolio value (no historical data available yet).
    /// TODO: Replace with real API endpoint for portfolio performance history.
    private func generateSyntheticHistory() -> [PortfolioSnapshot] {
        let currentValue = totalValue
        let currentCash = cash
        let currentPositions = positionsValue
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        
        let days = selectedPeriod.days
        let dataPoints = min(days, 30)  // Cap at 30 data points
        
        var snapshots: [PortfolioSnapshot] = []
        for i in (0..<dataPoints).reversed() {
            let date = Calendar.current.date(byAdding: .day, value: -i, to: Date())!
            let timestamp = formatter.string(from: date)
            snapshots.append(PortfolioSnapshot(
                timestamp: timestamp,
                totalValue: currentValue,
                cash: currentCash,
                positionsValue: currentPositions,
                totalPnl: (summary?.totalPnl ?? 0),
                totalPnlPercent: (summary?.totalPnlPercent ?? 0)
            ))
        }
        
        return snapshots
    }
    
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
