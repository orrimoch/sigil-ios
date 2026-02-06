import SwiftUI

/// F3.3: Tab Navigation
/// Bottom tab bar with 5 tabs: Home, Scores, Trade, Portfolio, Settings
struct ContentView: View {
    @EnvironmentObject var appState: AppState
    @StateObject private var scoresBadge = ScoresBadgeService.shared
    
    var body: some View {
        TabView(selection: $appState.selectedTab) {
            // Home Tab
            HomeView()
                .tabItem {
                    Label(Tab.home.rawValue, systemImage: Tab.home.icon)
                }
                .tag(Tab.home)
            
            // Scores Tab
            ScoresView()
                .tabItem {
                    Label(Tab.scores.rawValue, systemImage: Tab.scores.icon)
                }
                .tag(Tab.scores)
                // REC-128: Show NEW badge when scores updated since last view
                .badge(scoresBadge.hasNewScores ? "NEW" : nil)
            
            // Trade Tab
            TradeView()
                .tabItem {
                    Label(Tab.trade.rawValue, systemImage: Tab.trade.icon)
                }
                .tag(Tab.trade)
            
            // Portfolio Tab
            PortfolioView()
                .tabItem {
                    Label(Tab.portfolio.rawValue, systemImage: Tab.portfolio.icon)
                }
                .tag(Tab.portfolio)
            
            // Settings Tab
            SettingsView()
                .tabItem {
                    Label(Tab.settings.rawValue, systemImage: Tab.settings.icon)
                }
                .tag(Tab.settings)
        }
        .tint(Color.Accent.gold)
        .animation(.spring(response: 0.3, dampingFraction: 0.8), value: appState.selectedTab)
        .onChange(of: appState.selectedTab) { _, newValue in
            UIImpactFeedbackGenerator(style: .light).impactOccurred()
            Analytics.shared.track(.tabSwitched, properties: ["tab": newValue.rawValue])
            
            // REC-128: Clear NEW badge when user opens Scores tab
            if newValue == .scores {
                scoresBadge.markAsViewed()
            }
        }
        .task {
            // F9.3: Check for signal changes on watched stocks
            await WatchlistService.shared.checkForSignalChanges()
        }
        .onAppear {
            // Configure tab bar appearance (Institutional Dark theme)
            // REC-178: Fix tab bar visual bug - ensure no green border/glow
            let appearance = UITabBarAppearance()
            appearance.configureWithOpaqueBackground()
            appearance.backgroundColor = UIColor(Color.Background.primary)
            
            // Unselected item colors - use tertiary text color
            let normalAttrs: [NSAttributedString.Key: Any] = [
                .foregroundColor: UIColor(Color.Text.tertiary)
            ]
            appearance.stackedLayoutAppearance.normal.iconColor = UIColor(Color.Text.tertiary)
            appearance.stackedLayoutAppearance.normal.titleTextAttributes = normalAttrs
            
            // Selected item colors - use gold accent
            let selectedAttrs: [NSAttributedString.Key: Any] = [
                .foregroundColor: UIColor(Color.Accent.gold)
            ]
            appearance.stackedLayoutAppearance.selected.iconColor = UIColor(Color.Accent.gold)
            appearance.stackedLayoutAppearance.selected.titleTextAttributes = selectedAttrs
            
            // Remove any border/shadow
            appearance.shadowColor = .clear
            appearance.shadowImage = UIImage()
            
            UITabBar.appearance().standardAppearance = appearance
            UITabBar.appearance().scrollEdgeAppearance = appearance
            UITabBar.appearance().unselectedItemTintColor = UIColor(Color.Text.tertiary)
        }
    }
}

// MARK: - Preview

#Preview {
    ContentView()
        .environmentObject(AppState())
}
