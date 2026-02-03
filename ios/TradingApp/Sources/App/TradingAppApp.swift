import SwiftUI
import UserNotifications

/// Main entry point for Sigil
@main
struct SigilApp: App {
    @StateObject private var appState = AppState()
    @StateObject private var lockManager = AppLockManager.shared
    @StateObject private var notificationService = NotificationService.shared
    @State private var showLaunch = true
    @State private var showPinSetup = false
    
    var body: some Scene {
        WindowGroup {
            ZStack {
                if showLaunch {
                    LaunchView(showLaunch: $showLaunch)
                        .transition(.opacity)
                } else if lockManager.isSetUp && lockManager.isLocked {
                    // App is locked → show lock screen
                    LockScreenView(lockManager: lockManager)
                        .transition(.opacity)
                } else if appState.hasCompletedOnboarding {
                    ContentView()
                        .environmentObject(appState)
                        .onOpenURL { url in
                            handleURL(url)
                        }
                        .onAppear {
                            startDemoIfNeeded()
                            // Request notification permission on first launch
                            Task {
                                let granted = await notificationService.requestAuthorization()
                                if granted {
                                    // Schedule recurring notifications based on user preferences
                                    notificationService.scheduleWeeklyScoreUpdate()
                                }
                            }
                            // Prompt PIN setup if not set up yet (after first use)
                            if !lockManager.isSetUp && !UserDefaults.standard.bool(forKey: "pinSetupDismissed") {
                                DispatchQueue.main.asyncAfter(deadline: .now() + 2.0) {
                                    showPinSetup = true
                                }
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
            .onReceive(NotificationCenter.default.publisher(for: UIApplication.willResignActiveNotification)) { _ in
                // Lock when app goes to background
                lockManager.lock()
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
    @Published var hasCompletedOnboarding: Bool {
        didSet {
            UserDefaults.standard.set(hasCompletedOnboarding, forKey: "hasCompletedOnboarding")
        }
    }
    
    @Published var portfolioSize: PortfolioSize = .medium
    @Published var isPaperTrading: Bool = true
    @Published var selectedTab: Tab = .home
    
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
