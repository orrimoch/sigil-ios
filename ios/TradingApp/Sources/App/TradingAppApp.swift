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
    
    private let notificationDelegate = NotificationDelegate()
    
    init() {
        notificationDelegate.appState = AppState.shared
        // Defer delegate setup until notification authorization is granted
        // to prevent iOS from showing the permission dialog at launch.
        // The delegate will be set when the user enables notifications in Settings.
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
                        .onAppear { checkAuthState() }
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
                            // Prompt PIN setup if not set up yet (after first use)
                            if !lockManager.isSetUp && !UserDefaults.standard.bool(forKey: "pinSetupDismissed") {
                                DispatchQueue.main.asyncAfter(deadline: .now() + 2.0) {
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
                // Lock when app goes to background
                lockManager.lock()
            }
        }
    }
    
    /// Check auth state on launch.
    /// If no server-side auth required (dev mode), auto-login with graceful fallback.
    private func checkAuthState() {
        // If already has a stored session, we're good
        if AuthService.shared.isLoggedIn {
            authCheckDone = true
            return
        }
        
        // Graceful fallback: try to validate with backend.
        // If backend has AUTH_REQUIRED = False, we allow skip.
        Task {
            do {
                // Quick health check — if server is reachable, check if auth is required
                let url = URL(string: "http://127.0.0.1:8000/api/v1/health")!
                let (_, response) = try await URLSession.shared.data(from: url)
                
                if let http = response as? HTTPURLResponse, http.statusCode == 200 {
                    // Server reachable — check if auth is actually required
                    // Try accessing a protected endpoint without token
                    let scoresURL = URL(string: "http://127.0.0.1:8000/api/v1/scores?limit=1")!
                    let (_, scoresResponse) = try await URLSession.shared.data(from: scoresURL)
                    
                    if let scoresHttp = scoresResponse as? HTTPURLResponse, scoresHttp.statusCode == 200 {
                        // Auth not required (dev mode) — auto-grant access
                        await MainActor.run {
                            authVM.isLoggedIn = true
                            authCheckDone = true
                        }
                        return
                    }
                }
            } catch {
                // Server not reachable — allow offline access (graceful fallback)
                await MainActor.run {
                    authVM.isLoggedIn = true
                    authCheckDone = true
                }
                return
            }
            
            // Server requires auth and user isn't logged in — show login
            await MainActor.run {
                authCheckDone = true
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
    
    @Published var portfolioSize: PortfolioSize = .medium
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
    }
    
    func completeOnboarding() {
        hasCompletedOnboarding = true
    }
    
    func resetOnboarding() {
        hasCompletedOnboarding = false
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
        case .home: return "house.fill"
        case .scores: return "chart.bar.fill"
        case .trade: return "arrow.left.arrow.right"
        case .portfolio: return "briefcase.fill"
        case .settings: return "gearshape.fill"
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
