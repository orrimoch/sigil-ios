import SwiftUI
import UserNotifications

/// Handles notification taps and routes to appropriate tab
class NotificationDelegate: NSObject, UNUserNotificationCenterDelegate {
    weak var appState: AppState?
    
    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        didReceive response: UNNotificationResponse,
        withCompletionHandler completionHandler: @escaping () -> Void
    ) {
        let userInfo = response.notification.request.content.userInfo
        
        // Handle deep link URL from notification
        if let urlString = userInfo["url"] as? String,
           let url = URL(string: urlString),
           let host = url.host {
            DispatchQueue.main.async { [weak self] in
                switch host {
                case "scores": self?.appState?.selectedTab = .scores
                case "trade": self?.appState?.selectedTab = .trade
                case "portfolio": self?.appState?.selectedTab = .portfolio
                case "settings": self?.appState?.selectedTab = .settings
                default: self?.appState?.selectedTab = .home
                }
            }
        }
        
        // Handle notification action buttons
        if response.actionIdentifier == "VIEW_SCORES" {
            DispatchQueue.main.async { [weak self] in
                self?.appState?.selectedTab = .scores
            }
        }
        
        // Handle score alert taps — go to scores
        if let type = userInfo["type"] as? String,
           (type == "score_alert" || type == "score_alert_batch") {
            DispatchQueue.main.async { [weak self] in
                self?.appState?.selectedTab = .scores
            }
        }
        
        // Handle trade confirmation taps — go to portfolio
        if let type = userInfo["type"] as? String, type == "trade_confirmation" {
            DispatchQueue.main.async { [weak self] in
                self?.appState?.selectedTab = .portfolio
            }
        }
        
        completionHandler()
    }
    
    /// Show notifications even when app is in foreground
    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        willPresent notification: UNNotification,
        withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void
    ) {
        completionHandler([.banner, .sound])
    }
}

/// Main entry point for Sigil
@main
struct SigilApp: App {
    @StateObject private var appState = AppState.shared
    @StateObject private var authVM = AuthViewModel()
    @StateObject private var lockManager = AppLockManager.shared
    @StateObject private var notificationService = NotificationService.shared
    @State private var showLaunch = true
    @State private var showPinSetup = false
    @State private var authCheckDone = false
    @State private var lastActiveTime = Date()
    
    private let notificationDelegate = NotificationDelegate()
    
    init() {
        notificationDelegate.appState = AppState.shared
        // Defer delegate setup until notification authorization is granted
        // to prevent iOS from showing the permission dialog at launch.
        // The delegate will be set when the user enables notifications in Settings.
        
        // REC-133: Register background refresh tasks
        BackgroundRefreshManager.shared.registerTasks()
        
        // MEDIUM FIX TRADE-001/SHEET-001: Style segmented controls to match Institutional Dark theme
        let segmentedAppearance = UISegmentedControl.appearance()
        segmentedAppearance.selectedSegmentTintColor = UIColor(Color.Accent.gold)
        segmentedAppearance.backgroundColor = UIColor(Color.Background.secondary)
        segmentedAppearance.setTitleTextAttributes([
            .foregroundColor: UIColor(Color.Text.primary)
        ], for: .normal)
        segmentedAppearance.setTitleTextAttributes([
            .foregroundColor: UIColor(Color.Background.primary)
        ], for: .selected)
    }
    
    var body: some Scene {
        WindowGroup {
            ZStack {
                if showLaunch {
                    LaunchView(showLaunch: $showLaunch)
                        .transition(.opacity)
                } else if !authCheckDone {
                    // Brief loading while checking auth state
                    ProgressView()
                        .tint(.Brand.primary)
                        .onAppear {
                            Analytics.shared.configure()
                            Analytics.shared.track(.appLaunched)
                            checkAuthState()
                        }
                } else if !authVM.isLoggedIn {
                    // Auth gate — show login if not authenticated
                    LoginView()
                        .environmentObject(authVM)
                        .transition(.opacity)
                } else if lockManager.isSetUp && lockManager.isLocked {
                    // App is locked → show lock screen
                    LockScreenView(lockManager: lockManager)
                        .transition(.opacity)
                } else if appState.hasCompletedOnboarding {
                    ContentView()
                        .environmentObject(appState)
                        .environmentObject(authVM)
                        .onOpenURL { url in
                            handleURL(url)
                        }
                        .onAppear {
                            startDemoIfNeeded()
                            // Set up notifications only if user previously granted permission
                            if UserDefaults.standard.bool(forKey: "notificationsEnabled") {
                                Task {
                                    await notificationService.refreshAuthorizationStatus()
                                    if notificationService.isAuthorized {
                                        UNUserNotificationCenter.current().delegate = notificationDelegate
                                        notificationService.scheduleWeeklyScoreUpdate()
                                        await notificationService.updateWeeklyContentFromAPI()
                                    }
                                }
                            }
                            // F9.3: Check for signal changes on app launch
                            Task {
                                await WatchlistService.shared.checkForSignalChanges()
                            }
                            // Daily risk cache warming (once per day)
                            authVM.warmRiskCacheIfNeeded()
                            // Prompt PIN setup if not set up yet (after first use)
                            if !lockManager.isSetUp && !UserDefaults.standard.bool(forKey: "pinSetupDismissed") {
                                DispatchQueue.main.asyncAfter(deadline: .now() + 5.0) {
                                    showPinSetup = true
                                }
                            }
                        }
                        .onReceive(NotificationCenter.default.publisher(for: UIApplication.willEnterForegroundNotification)) { _ in
                            // F9.3: Check for signal changes when app returns to foreground
                            Task {
                                await WatchlistService.shared.checkForSignalChanges()
                            }
                        }
                        .sheet(isPresented: $showPinSetup) {
                            PinSetupView(lockManager: lockManager)
                                .onDisappear {
                                    if !lockManager.isSetUp {
                                        // User skipped — don't nag again this session
                                        UserDefaults.standard.set(true, forKey: "pinSetupDismissed")
                                    }
                                }
                        }
                        .transition(.opacity)
                } else {
                    OnboardingView()
                        .environmentObject(appState)
                        .transition(.opacity)
                }
            }
            .animation(.easeInOut(duration: 0.3), value: showLaunch)
            .animation(.easeInOut(duration: 0.3), value: lockManager.isLocked)
            .animation(.easeInOut(duration: 0.3), value: authVM.isLoggedIn)
            .onReceive(NotificationCenter.default.publisher(for: UIApplication.willEnterForegroundNotification)) { _ in
                // Refresh biometric type in case user enrolled Face ID while away
                lockManager.refreshBiometricType()
            }
            .onReceive(NotificationCenter.default.publisher(for: UIApplication.willResignActiveNotification)) { _ in
                // Record time when app goes to background (30s grace period before locking)
                lastActiveTime = Date()
                Analytics.shared.track(.appBackgrounded)
                // REC-133: Schedule background refresh for score data
                BackgroundRefreshManager.shared.scheduleAppRefresh()
            }
            .onReceive(NotificationCenter.default.publisher(for: UIApplication.willEnterForegroundNotification)) { _ in
                // Lock only if backgrounded for more than 30 seconds
                if Date().timeIntervalSince(lastActiveTime) > 30 {
                    lockManager.lock()
                }
                Analytics.shared.track(.appForegrounded)
            }
        }
    }
    
    /// Check if app was launched in demo mode (via environment variable or launch argument).
    /// Usage: `xcrun simctl launch --console-pty booted com.sigil.ios DEMO_MODE=1`
    private var isDemoMode: Bool {
        // Check environment variable (most reliable with simctl)
        if ProcessInfo.processInfo.environment["DEMO_MODE"] == "1" {
            return true
        }
        // Check launch arguments (alternative)
        for (index, arg) in CommandLine.arguments.enumerated() {
            if arg == "-demo_mode" || arg == "DEMO_MODE=1" {
                return true
            }
            // Handle -demo_mode YES format
            if arg == "-demo_mode" && index + 1 < CommandLine.arguments.count {
                let value = CommandLine.arguments[index + 1].lowercased()
                if value == "yes" || value == "true" || value == "1" {
                    return true
                }
            }
        }
        // Check UserDefaults (set via `simctl spawn booted defaults write`)
        return UserDefaults.standard.bool(forKey: "demo_mode")
    }
    
    /// Check auth state on launch (REC-130).
    ///
    /// 1. Ask backend `/auth/status` whether auth is required.
    /// 2. If `auth_required == false` → auto-grant (dev mode).
    /// 3. If `auth_required == true` AND we have a stored session → validate it.
    /// 4. If server unreachable → grant if stored session exists, otherwise show login.
    private func checkAuthState() {
        // DEMO MODE: Bypass all auth checks
        if isDemoMode {
            #if DEBUG
            debugLog("🎬 Demo mode enabled — bypassing auth")
            #endif
            authVM.isLoggedIn = true
            appState.hasCompletedOnboarding = true
            authCheckDone = true
            return
        }
        
        // Fast path: stored session — try to use it
        let hasSession = AuthService.shared.isLoggedIn

        Task {
            do {
                let authRequired = try await AuthService.shared.checkServerAuthStatus()

                if !authRequired {
                    // Server says auth not required (dev mode) — auto-grant
                    await MainActor.run {
                        authVM.isLoggedIn = true
                        authCheckDone = true
                    }
                    return
                }

                // Auth IS required — need a valid session
                if hasSession {
                    // Validate stored token via /auth/me
                    do {
                        try await AuthService.shared.fetchProfile()
                        await MainActor.run { authCheckDone = true }
                    } catch {
                        // Token might be expired — try refresh
                        do {
                            try await AuthService.shared.refreshToken()
                            try await AuthService.shared.fetchProfile()
                            await MainActor.run { authCheckDone = true }
                        } catch {
                            // Refresh failed — force login
                            await MainActor.run {
                                AuthService.shared.logout()
                                authCheckDone = true
                            }
                        }
                    }
                } else {
                    // No session and auth required — show login
                    await MainActor.run { authCheckDone = true }
                }
            } catch {
                // Server unreachable — offline fallback
                await MainActor.run {
                    if hasSession {
                        // Trust the stored session offline
                        authCheckDone = true
                    } else {
                        // No session, no server — show login
                        authCheckDone = true
                    }
                }
            }
        }
    }
    
    private func handleURL(_ url: URL) {
        guard let host = url.host else { return }
        switch host {
        case "home": appState.selectedTab = .home
        case "scores": appState.selectedTab = .scores
        case "trade": appState.selectedTab = .trade
        case "portfolio": appState.selectedTab = .portfolio
        case "settings": appState.selectedTab = .settings
        default: break
        }
    }
    
    private func startDemoIfNeeded() {
        // Check for demo mode via UserDefaults (set via simctl)
        let demoTab = UserDefaults.standard.string(forKey: "demo_tab") ?? ""
        if !demoTab.isEmpty {
            switch demoTab {
            case "scores": appState.selectedTab = .scores
            case "trade": appState.selectedTab = .trade
            case "portfolio": appState.selectedTab = .portfolio
            case "settings": appState.selectedTab = .settings
            default: appState.selectedTab = .home
            }
            // Clear after use
            UserDefaults.standard.removeObject(forKey: "demo_tab")
        }
    }
}

/// Global app state
class AppState: ObservableObject {
    static let shared = AppState()
    
    @Published var hasCompletedOnboarding: Bool {
        didSet {
            UserDefaults.standard.set(hasCompletedOnboarding, forKey: "hasCompletedOnboarding")
        }
    }
    
    @Published var portfolioSize: PortfolioSize = .medium {
        didSet {
            UserDefaults.standard.set(portfolioSize.rawValue, forKey: "portfolioSize")
            // REC-127: Sync to backend
            syncPortfolioSizeToBackend()
        }
    }
    @Published var isPaperTrading: Bool = true
    @Published var selectedTab: Tab = {
        if let raw = UserDefaults.standard.string(forKey: "initialTab"),
           let tab = Tab(rawValue: raw) {
            UserDefaults.standard.removeObject(forKey: "initialTab")
            return tab
        }
        return .home
    }()
    
    init() {
        self.hasCompletedOnboarding = UserDefaults.standard.bool(forKey: "hasCompletedOnboarding")
        // Load saved portfolio size
        if let sizeRaw = UserDefaults.standard.string(forKey: "portfolioSize"),
           let size = PortfolioSize.allCases.first(where: { $0.rawValue == sizeRaw }) {
            self._portfolioSize = Published(initialValue: size)
        }
    }
    
    func completeOnboarding() {
        hasCompletedOnboarding = true
    }
    
    func resetOnboarding() {
        hasCompletedOnboarding = false
    }
    
    // MARK: - REC-127: Sync Portfolio Size to Backend
    
    private func syncPortfolioSizeToBackend() {
        // Only sync if authenticated
        guard AuthService.shared.isLoggedIn else { return }
        
        // Map enum to backend value (small/medium/large)
        let sizeValue: String
        switch portfolioSize {
        case .small: sizeValue = "small"
        case .medium: sizeValue = "medium"
        case .large: sizeValue = "large"
        }
        
        Task {
            do {
                _ = try await APIService.shared.updatePreferences(
                    riskTolerance: nil,
                    portfolioSize: sizeValue
                )
            } catch {
                #if DEBUG
                debugError(error, context: "Failed to sync portfolio size")
                #endif
            }
        }
    }
}

/// Available tabs in the main app
enum Tab: String, CaseIterable {
    case home = "Home"
    case scores = "Scores"
    case trade = "Trade"
    case portfolio = "Portfolio"
    case settings = "Settings"
    
    var icon: String {
        switch self {
        case .home: return "house"
        case .scores: return "chart.bar"
        case .trade: return "dollarsign.circle"
        case .portfolio: return "briefcase"
        case .settings: return "gearshape"
        }
    }
}

/// Portfolio size options
enum PortfolioSize: String, CaseIterable {
    case small = "Small ($1K-$10K)"
    case medium = "Medium ($10K-$100K)"
    case large = "Large ($100K+)"
    
    var description: String {
        switch self {
        case .small: return "Conservative, fewer positions"
        case .medium: return "Balanced, 5-10 positions"
        case .large: return "Diversified, up to 15 positions"
        }
    }
}
