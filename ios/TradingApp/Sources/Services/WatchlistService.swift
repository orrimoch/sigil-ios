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
    
    /// Check for signal changes on watched stocks and send notifications.
    /// If more than 3 changes, sends a single summary notification instead of individual ones.
    func checkForSignalChanges() async {
        guard UserDefaults.standard.bool(forKey: "scoreAlerts") else { return }
        guard !watchedTickers.isEmpty else { return }
        
        do {
            let response = try await APIService.shared.getScoreChanges()
            
            // Filter to watched stocks only
            let watchedChanges = response.data.filter { isWatched($0.ticker) }
            guard !watchedChanges.isEmpty else { return }
            
            if watchedChanges.count > 3 {
                // Batch notification: summarize all changes
                let firstThree = watchedChanges.prefix(3).map { "\($0.ticker) → \($0.newSignal)" }
                let remaining = watchedChanges.count - 3
                let summary = firstThree.joined(separator: ", ") + ", and \(remaining) more."
                
                NotificationService.shared.sendBatchScoreAlert(
                    count: watchedChanges.count,
                    summary: summary
                )
            } else {
                // Individual notifications for 3 or fewer changes
                for change in watchedChanges {
                    NotificationService.shared.sendScoreAlert(
                        ticker: change.ticker,
                        oldSignal: change.oldSignal,
                        newSignal: change.newSignal,
                        score: change.newScore
                    )
                }
            }
        } catch {
            #if DEBUG
            debugError(error, context: "[WatchlistService] Failed to check signal changes")
            #endif
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
