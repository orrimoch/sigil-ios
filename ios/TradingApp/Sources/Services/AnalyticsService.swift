import Foundation

/// Analytics abstraction layer.
/// Currently logs to console. Swap implementation for PostHog/Mixpanel/Firebase later.
/// Usage: Analytics.shared.track(.appLaunched)
final class Analytics {
    static let shared = Analytics()
    
    private var userId: String?
    private var sessionStart = Date()
    private var eventCount = 0
    
    private init() {}
    
    // MARK: - Configuration
    
    func configure(userId: String? = nil) {
        self.userId = userId
        self.sessionStart = Date()
        self.eventCount = 0
        log("Analytics configured", properties: ["userId": userId ?? "anonymous"])
    }
    
    func setUserId(_ id: String) {
        self.userId = id
    }
    
    // MARK: - Event Tracking
    
    func track(_ event: AnalyticsEvent, properties: [String: Any]? = nil) {
        eventCount += 1
        var merged = properties ?? [:]
        merged["event_number"] = eventCount
        merged["session_duration_s"] = Int(Date().timeIntervalSince(sessionStart))
        if let userId { merged["user_id"] = userId }
        log(event.rawValue, properties: merged)
        
        // Persist event count for session summary
        UserDefaults.standard.set(eventCount, forKey: "analytics_event_count")
    }
    
    func trackScreen(_ screen: String) {
        track(.screenView, properties: ["screen": screen])
    }
    
    func trackError(_ error: String, context: String? = nil) {
        track(.error, properties: ["error": error, "context": context ?? "unknown"])
    }
    
    // MARK: - Logging (replace with SDK calls later)
    
    private func log(_ event: String, properties: [String: Any]) {
        #if DEBUG
        let propsString = properties.map { "\($0.key)=\($0.value)" }.joined(separator: ", ")
        debugLog("[Analytics] \(event) | \(propsString)")
        #endif
    }
}

// MARK: - Event Definitions

enum AnalyticsEvent: String {
    // App Lifecycle
    case appLaunched = "app_launched"
    case appBackgrounded = "app_backgrounded"
    case appForegrounded = "app_foregrounded"
    case sessionStarted = "session_started"
    
    // Auth
    case loginSuccess = "login_success"
    case loginFailed = "login_failed"
    case registerSuccess = "register_success"
    case loggedOut = "logged_out"
    
    // Onboarding
    case onboardingStarted = "onboarding_started"
    case onboardingCompleted = "onboarding_completed"
    case onboardingSkipped = "onboarding_skipped"
    
    // Navigation
    case screenView = "screen_view"
    case tabSwitched = "tab_switched"
    
    // Scores
    case scoreViewed = "score_viewed"
    case stockDetailViewed = "stock_detail_viewed"
    case scoreFiltered = "score_filtered"
    case scoreSearched = "score_searched"
    
    // Trading
    case orderPreview = "order_preview"
    case orderSubmitted = "order_submitted"
    case orderCancelled = "order_cancelled"
    case ibkrConnected = "ibkr_connected"
    case ibkrDisconnected = "ibkr_disconnected"
    
    // Portfolio
    case portfolioViewed = "portfolio_viewed"
    case portfolioReset = "portfolio_reset"
    case holdingTapped = "holding_tapped"
    
    // Watchlist
    case watchlistAdded = "watchlist_added"
    case watchlistRemoved = "watchlist_removed"
    
    // Settings
    case settingsChanged = "settings_changed"
    case riskToleranceChanged = "risk_tolerance_changed"
    case portfolioSizeChanged = "portfolio_size_changed"
    case notificationToggled = "notification_toggled"
    
    // Notifications
    case notificationReceived = "notification_received"
    case notificationTapped = "notification_tapped"
    
    // Errors
    case error = "error"
    case apiError = "api_error"
    
    // Features
    case chartInspected = "chart_inspected"
    case pullToRefresh = "pull_to_refresh"
    case swipeAction = "swipe_action"
}
