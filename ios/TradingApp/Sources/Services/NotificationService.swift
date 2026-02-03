import Foundation
import UserNotifications

/// F9.2: Local Notification Service
/// Wraps UNUserNotificationCenter for trade confirmations and score alerts
@MainActor
final class NotificationService: ObservableObject {
    static let shared = NotificationService()
    
    @Published var isAuthorized = false
    @Published var authorizationStatus: UNAuthorizationStatus = .notDetermined
    
    private let center = UNUserNotificationCenter.current()
    
    private init() {
        Task { await refreshAuthorizationStatus() }
    }
    
    // MARK: - Authorization
    
    /// Request notification permission from the user
    func requestAuthorization() async -> Bool {
        do {
            let granted = try await center.requestAuthorization(options: [.alert, .badge, .sound])
            await refreshAuthorizationStatus()
            return granted
        } catch {
            print("[NotificationService] Authorization error: \(error)")
            return false
        }
    }
    
    /// Check current authorization status
    func refreshAuthorizationStatus() async {
        let settings = await center.notificationSettings()
        authorizationStatus = settings.authorizationStatus
        isAuthorized = settings.authorizationStatus == .authorized
    }
    
    // MARK: - Trade Confirmation (F9.2)
    
    /// Send a local notification confirming a trade was executed
    func sendTradeConfirmation(
        ticker: String,
        side: String,
        quantity: Double,
        price: Double,
        total: Double
    ) {
        // Respect user's trade confirmation preference
        guard UserDefaults.standard.bool(forKey: "tradeConfirmations") else { return }
        guard isAuthorized else { return }
        
        let content = UNMutableNotificationContent()
        let sideEmoji = side == "BUY" ? "🟢" : "🔴"
        let formattedPrice = String(format: "$%.2f", price)
        let formattedTotal = String(format: "$%.2f", total)
        let formattedQty = quantity.truncatingRemainder(dividingBy: 1) == 0
            ? String(format: "%.0f", quantity)
            : String(format: "%.2f", quantity)
        
        content.title = "\(sideEmoji) \(side) Order Filled"
        content.body = "\(formattedQty) shares of \(ticker) at \(formattedPrice)\nTotal: \(formattedTotal)"
        content.sound = .default
        content.categoryIdentifier = "TRADE_CONFIRMATION"
        content.userInfo = [
            "type": "trade_confirmation",
            "ticker": ticker,
            "side": side,
            "quantity": quantity,
            "price": price
        ]
        
        // Fire immediately (1 second delay for UX — feels like a real confirmation)
        let trigger = UNTimeIntervalNotificationTrigger(timeInterval: 1, repeats: false)
        let request = UNNotificationRequest(
            identifier: "trade-\(ticker)-\(Date().timeIntervalSince1970)",
            content: content,
            trigger: trigger
        )
        
        center.add(request) { error in
            if let error {
                print("[NotificationService] Failed to schedule trade notification: \(error)")
            }
        }
    }
    
    // MARK: - Score Alert (F9.1 placeholder)
    
    /// Send a notification when a watched stock changes signal
    func sendScoreAlert(ticker: String, oldSignal: String, newSignal: String, score: Double) {
        guard UserDefaults.standard.bool(forKey: "scoreAlerts") else { return }
        guard isAuthorized else { return }
        
        let content = UNMutableNotificationContent()
        let emoji: String
        switch newSignal.uppercased() {
        case "BUY": emoji = "🟢"
        case "SELL": emoji = "🔴"
        default: emoji = "🟡"
        }
        
        content.title = "\(emoji) \(ticker) Signal Changed"
        content.body = "\(oldSignal) → \(newSignal) (Score: \(String(format: "%.1f", score)))"
        content.sound = .default
        content.categoryIdentifier = "SCORE_ALERT"
        content.userInfo = [
            "type": "score_alert",
            "ticker": ticker,
            "signal": newSignal,
            "score": score
        ]
        
        let trigger = UNTimeIntervalNotificationTrigger(timeInterval: 1, repeats: false)
        let request = UNNotificationRequest(
            identifier: "score-\(ticker)-\(Date().timeIntervalSince1970)",
            content: content,
            trigger: trigger
        )
        
        center.add(request) { error in
            if let error {
                print("[NotificationService] Failed to schedule score notification: \(error)")
            }
        }
    }
    
    // MARK: - Weekly Score Update (F9.1 placeholder)
    
    /// Schedule a weekly notification for score updates (Sundays 7pm EST)
    func scheduleWeeklyScoreUpdate() {
        guard UserDefaults.standard.bool(forKey: "weeklyScoreAlerts") else {
            // Remove any existing weekly notification
            center.removePendingNotificationRequests(withIdentifiers: ["weekly-score-update"])
            return
        }
        guard isAuthorized else { return }
        
        // Remove old one first
        center.removePendingNotificationRequests(withIdentifiers: ["weekly-score-update"])
        
        let content = UNMutableNotificationContent()
        content.title = "📊 Weekly Score Update"
        content.body = "New AI scores are ready. Check your top picks!"
        content.sound = .default
        content.categoryIdentifier = "WEEKLY_UPDATE"
        
        // Sunday at 7pm EST (19:00 America/New_York)
        var dateComponents = DateComponents()
        dateComponents.weekday = 1 // Sunday
        dateComponents.hour = 19
        dateComponents.minute = 0
        dateComponents.timeZone = TimeZone(identifier: "America/New_York")
        
        let trigger = UNCalendarNotificationTrigger(dateMatching: dateComponents, repeats: true)
        let request = UNNotificationRequest(
            identifier: "weekly-score-update",
            content: content,
            trigger: trigger
        )
        
        center.add(request) { error in
            if let error {
                print("[NotificationService] Failed to schedule weekly notification: \(error)")
            }
        }
    }
    
    // MARK: - Cleanup
    
    /// Remove all pending notifications
    func removeAllPending() {
        center.removeAllPendingNotificationRequests()
    }
    
    /// Remove all delivered notifications
    func clearDelivered() {
        center.removeAllDeliveredNotifications()
    }
}
