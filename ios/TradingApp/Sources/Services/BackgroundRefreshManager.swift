import Foundation
import BackgroundTasks
import UIKit

/// Manages background app refresh for periodic score data updates.
/// Registers BGAppRefreshTask to check for new scores and signal changes.
///
/// Wire into app: call `BackgroundRefreshManager.shared.registerTasks()` in App.init()
/// and `BackgroundRefreshManager.shared.scheduleAppRefresh()` when app backgrounds.
final class BackgroundRefreshManager {
    static let shared = BackgroundRefreshManager()
    
    /// Task identifier — must match Info.plist BGTaskSchedulerPermittedIdentifiers
    static let refreshTaskId = "com.sigil.ios.scoreRefresh"
    static let processingTaskId = "com.sigil.ios.dataProcessing"
    
    private init() {}
    
    // MARK: - Registration (call from App.init)
    
    func registerTasks() {
        BGTaskScheduler.shared.register(
            forTaskWithIdentifier: Self.refreshTaskId,
            using: nil
        ) { task in
            self.handleAppRefresh(task: task as! BGAppRefreshTask)
        }
        
        BGTaskScheduler.shared.register(
            forTaskWithIdentifier: Self.processingTaskId,
            using: nil
        ) { task in
            self.handleProcessingTask(task: task as! BGProcessingTask)
        }
        
        #if DEBUG
        print("[BackgroundRefresh] Tasks registered")
        #endif
    }
    
    // MARK: - Scheduling (call when app backgrounds)
    
    func scheduleAppRefresh() {
        let request = BGAppRefreshTaskRequest(identifier: Self.refreshTaskId)
        request.earliestBeginDate = Date(timeIntervalSinceNow: 30 * 60) // 30 min minimum
        
        do {
            try BGTaskScheduler.shared.submit(request)
            #if DEBUG
            print("[BackgroundRefresh] App refresh scheduled for ~30 min")
            #endif
        } catch {
            #if DEBUG
            print("[BackgroundRefresh] Failed to schedule: \(error)")
            #endif
        }
    }
    
    func scheduleProcessingTask() {
        let request = BGProcessingTaskRequest(identifier: Self.processingTaskId)
        request.earliestBeginDate = Date(timeIntervalSinceNow: 60 * 60) // 1 hour
        request.requiresNetworkConnectivity = true
        request.requiresExternalPower = false
        
        do {
            try BGTaskScheduler.shared.submit(request)
            #if DEBUG
            print("[BackgroundRefresh] Processing task scheduled for ~1 hour")
            #endif
        } catch {
            #if DEBUG
            print("[BackgroundRefresh] Failed to schedule processing: \(error)")
            #endif
        }
    }
    
    // MARK: - Task Handlers
    
    private func handleAppRefresh(task: BGAppRefreshTask) {
        // Schedule next refresh
        scheduleAppRefresh()
        
        let refreshTask = Task {
            do {
                // 1. Check for score summary updates
                let scoreSummary = try await fetchScoreSummary()
                
                // 2. Check watchlist signal changes
                await WatchlistService.shared.checkForSignalChanges()
                
                // 3. Update notification content with fresh data
                await NotificationService.shared.updateWeeklyContentFromAPI()
                
                // 4. Update app badge with alert count
                let alertCount = scoreSummary.signalChanges
                await MainActor.run {
                    UNUserNotificationCenter.current().setBadgeCount(alertCount)
                }
                
                task.setTaskCompleted(success: true)
                
                #if DEBUG
                print("[BackgroundRefresh] Refresh completed: \(scoreSummary.signalChanges) signal changes")
                #endif
            } catch {
                task.setTaskCompleted(success: false)
                #if DEBUG
                print("[BackgroundRefresh] Refresh failed: \(error)")
                #endif
            }
        }
        
        task.expirationHandler = {
            refreshTask.cancel()
        }
    }
    
    private func handleProcessingTask(task: BGProcessingTask) {
        scheduleProcessingTask()
        
        let processingTask = Task {
            do {
                // Heavier work: full score data sync
                await WatchlistService.shared.checkForSignalChanges()
                await NotificationService.shared.updateWeeklyContentFromAPI()
                task.setTaskCompleted(success: true)
            } catch {
                task.setTaskCompleted(success: false)
            }
        }
        
        task.expirationHandler = {
            processingTask.cancel()
        }
    }
    
    // MARK: - API
    
    private struct ScoreSummaryResponse: Codable {
        let success: Bool
        let data: ScoreSummaryData
    }
    
    private struct ScoreSummaryData: Codable {
        let buyCount: Int
        let holdCount: Int
        let sellCount: Int
        let signalChanges: Int
        
        enum CodingKeys: String, CodingKey {
            case buyCount = "buy_count"
            case holdCount = "hold_count"
            case sellCount = "sell_count"
            case signalChanges = "signal_changes"
        }
    }
    
    private func fetchScoreSummary() async throws -> ScoreSummaryData {
        let url = URL(string: "http://127.0.0.1:8000/api/v1/scores/summary")!
        let (data, _) = try await URLSession.shared.data(from: url)
        let decoder = JSONDecoder()
        let response = try decoder.decode(ScoreSummaryResponse.self, from: data)
        return response.data
    }
}

// MARK: - Integration Notes
//
// To wire into the app, add to TradingAppApp.swift:
//
// 1. In init():
//    BackgroundRefreshManager.shared.registerTasks()
//
// 2. In willResignActiveNotification handler:
//    BackgroundRefreshManager.shared.scheduleAppRefresh()
//
// 3. Add to Info.plist BGTaskSchedulerPermittedIdentifiers:
//    - com.sigil.ios.scoreRefresh
//    - com.sigil.ios.dataProcessing
//
// 4. Add UIBackgroundModes: fetch, processing
