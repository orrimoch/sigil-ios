import Foundation
import Combine

/// F9.3: Watchlist Service — manages user's watched stocks
/// Stores watched tickers in UserDefaults for persistence
@MainActor
final class WatchlistService: ObservableObject {
    static let shared = WatchlistService()
    
    @Published var watchedTickers: Set<String> = []
    
    private let storageKey = "sigil_watchlist"
    
    private init() {
        loadWatchlist()
    }
    
    // MARK: - Watchlist Management
    
    /// Add a ticker to the watchlist
    func addToWatchlist(_ ticker: String) {
        watchedTickers.insert(ticker.uppercased())
        saveWatchlist()
    }
    
    /// Remove a ticker from the watchlist
    func removeFromWatchlist(_ ticker: String) {
        watchedTickers.remove(ticker.uppercased())
        saveWatchlist()
    }
    
    /// Toggle a ticker in the watchlist
    func toggleWatchlist(_ ticker: String) {
        let uppercased = ticker.uppercased()
        if watchedTickers.contains(uppercased) {
            removeFromWatchlist(uppercased)
        } else {
            addToWatchlist(uppercased)
        }
    }
    
    /// Check if a ticker is watched
    func isWatched(_ ticker: String) -> Bool {
        watchedTickers.contains(ticker.uppercased())
    }
    
    // MARK: - Score Change Detection
    
    /// Check for signal changes on watched stocks and send notifications
    func checkForSignalChanges() async {
        guard UserDefaults.standard.bool(forKey: "scoreAlerts") else { return }
        guard !watchedTickers.isEmpty else { return }
        
        do {
            let response = try await APIService.shared.getScoreChanges()
            
            for change in response.data {
                // Only notify for watched stocks
                guard isWatched(change.ticker) else { continue }
                
                NotificationService.shared.sendScoreAlert(
                    ticker: change.ticker,
                    oldSignal: change.oldSignal,
                    newSignal: change.newSignal,
                    score: change.newScore
                )
            }
        } catch {
            print("[WatchlistService] Failed to check signal changes: \(error)")
        }
    }
    
    // MARK: - Persistence
    
    private func loadWatchlist() {
        let stored = UserDefaults.standard.stringArray(forKey: storageKey) ?? []
        watchedTickers = Set(stored)
    }
    
    private func saveWatchlist() {
        UserDefaults.standard.set(Array(watchedTickers), forKey: storageKey)
    }
}
