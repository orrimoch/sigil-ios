import Foundation
import Combine

/// REC-128: Tracks when scores were last viewed to show NEW badge
@MainActor
class ScoresBadgeService: ObservableObject {
    static let shared = ScoresBadgeService()
    
    @Published var hasNewScores: Bool = false
    
    private let lastViewedKey = "scores_last_viewed_timestamp"
    private var cancellables = Set<AnyCancellable>()
    
    private init() {
        // Check on init
        Task {
            await checkForNewScores()
        }
    }
    
    /// Mark scores as viewed (called when user opens Scores tab)
    func markAsViewed() {
        let now = Date().timeIntervalSince1970
        UserDefaults.standard.set(now, forKey: lastViewedKey)
        hasNewScores = false
    }
    
    /// Check if there are new scores since last view
    func checkForNewScores() async {
        let lastViewed = UserDefaults.standard.double(forKey: lastViewedKey)
        
        // If never viewed, don't show badge (first launch)
        guard lastViewed > 0 else {
            hasNewScores = false
            return
        }
        
        do {
            // Get latest pipeline run timestamp from backend
            let latestRun = try await fetchLatestPipelineRun()
            
            if let runTimestamp = latestRun {
                // Show badge if pipeline ran after last view
                hasNewScores = runTimestamp > lastViewed
            } else {
                hasNewScores = false
            }
        } catch {
            print("ScoresBadgeService: Failed to check for new scores: \(error)")
            hasNewScores = false
        }
    }
    
    /// Fetch latest pipeline run timestamp from backend
    private func fetchLatestPipelineRun() async throws -> TimeInterval? {
        let url = URL(string: "http://127.0.0.1:8000/api/v1/pipeline/latest")!
        let (data, response) = try await URLSession.shared.data(from: url)
        
        guard let http = response as? HTTPURLResponse, http.statusCode == 200 else {
            return nil
        }
        
        let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]
        guard let dataDict = json?["data"] as? [String: Any],
              let completedAt = dataDict["completed_at"] as? String else {
            return nil
        }
        
        // Parse ISO8601 timestamp
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        
        if let date = formatter.date(from: completedAt) {
            return date.timeIntervalSince1970
        }
        
        // Try without fractional seconds
        formatter.formatOptions = [.withInternetDateTime]
        if let date = formatter.date(from: completedAt) {
            return date.timeIntervalSince1970
        }
        
        return nil
    }
}
