import SwiftUI

/// F3.3: Tab Navigation
/// Bottom tab bar with 5 tabs: Home, Scores, Trade, Portfolio, Settings
struct ContentView: View {
    @EnvironmentObject var appState: AppState
    @State private var scoresHasNewData = false
    
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
                // TODO: "NEW" badge not yet connected to backend signal data
                .badge(scoresHasNewData ? "NEW" : nil)
            
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
        .onChange(of: appState.selectedTab) { _, _ in
            UIImpactFeedbackGenerator(style: .light).impactOccurred()
        }
        .task {
            // F9.3: Check for signal changes on watched stocks
            await WatchlistService.shared.checkForSignalChanges()
        }
        .onAppear {
            // Configure tab bar appearance (Institutional Dark theme)
            let appearance = UITabBarAppearance()
            appearance.configureWithOpaqueBackground()
            appearance.backgroundColor = UIColor(Color.Background.primary)
            
            UITabBar.appearance().standardAppearance = appearance
            UITabBar.appearance().scrollEdgeAppearance = appearance
        }
    }
}

// MARK: - Preview

#Preview {
    ContentView()
        .environmentObject(AppState())
}
