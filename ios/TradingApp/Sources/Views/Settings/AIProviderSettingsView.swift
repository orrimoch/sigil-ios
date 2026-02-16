import SwiftUI

/// REC-272: AI Provider Settings View
/// Allows users to see which AI providers are configured and active.
struct AIProviderSettingsView: View {
    @StateObject private var viewModel = AIProviderSettingsViewModel()
    
    var body: some View {
        List {
            // Current Provider Section
            Section {
                if viewModel.isLoading {
                    HStack {
                        ProgressView()
                            .tint(.Accent.gold)
                        Text("Loading...")
                            .foregroundColor(.Text.secondary)
                    }
                } else if let config = viewModel.currentConfig {
                    HStack {
                        Image(systemName: "checkmark.circle.fill")
                            .foregroundColor(.Signal.buy)
                        
                        VStack(alignment: .leading) {
                            Text("Active Provider")
                                .font(.caption)
                                .foregroundColor(.Text.tertiary)
                            Text(config.providerDisplayName)
                                .foregroundColor(.Text.primary)
                        }
                        
                        Spacer()
                        
                        if config.available {
                            Text("Online")
                                .font(.caption)
                                .foregroundColor(.Signal.buy)
                        } else {
                            Text("Offline")
                                .font(.caption)
                                .foregroundColor(.Signal.sell)
                        }
                    }
                } else if let error = viewModel.error {
                    HStack {
                        Image(systemName: "exclamationmark.triangle.fill")
                            .foregroundColor(.Signal.hold)
                        Text(error)
                            .font(.caption)
                            .foregroundColor(.Signal.sell)
                    }
                }
            } header: {
                Text("Current Configuration")
            }
            .listRowBackground(Color.Background.secondary)
            
            // Available Providers Section
            Section {
                ForEach(viewModel.providers) { provider in
                    HStack {
                        Image(systemName: provider.icon)
                            .foregroundColor(provider.configured ? .Accent.gold : .Text.tertiary)
                            .frame(width: 24)
                        
                        VStack(alignment: .leading) {
                            Text(provider.name)
                                .foregroundColor(.Text.primary)
                            
                            Text(provider.configured ? "Configured" : "Not configured")
                                .font(.caption)
                                .foregroundColor(provider.configured ? .Signal.buy : .Text.tertiary)
                        }
                        
                        Spacer()
                        
                        if provider.provider == viewModel.currentConfig?.provider {
                            Image(systemName: "checkmark")
                                .foregroundColor(.Accent.gold)
                        }
                    }
                }
            } header: {
                Text("Available Providers")
            } footer: {
                Text("AI providers are configured via environment variables on the backend server. Contact your administrator to change providers.")
            }
            .listRowBackground(Color.Background.secondary)
            
            // Info Section
            Section {
                VStack(alignment: .leading, spacing: 12) {
                    InfoRow(
                        icon: "bolt.fill",
                        title: "Scoring",
                        description: "AI analyzes fundamentals, news, and market data to generate stock scores."
                    )
                    
                    InfoRow(
                        icon: "shield.fill",
                        title: "Risk Analysis",
                        description: "AI evaluates portfolio risk and provides recommendations."
                    )
                    
                    InfoRow(
                        icon: "chart.line.uptrend.xyaxis",
                        title: "Sentiment",
                        description: "AI reads financial news to gauge market sentiment."
                    )
                }
                .padding(.vertical, 8)
            } header: {
                Text("What AI Powers")
            }
            .listRowBackground(Color.Background.secondary)
        }
        .listStyle(.insetGrouped)
        .scrollContentBackground(.hidden)
        .background(Color.Background.primary)
        .navigationTitle("AI Provider")
        .navigationBarTitleDisplayMode(.inline)
        .refreshable {
            await viewModel.refresh()
        }
        .task {
            await viewModel.load()
        }
    }
}

// MARK: - Info Row

private struct InfoRow: View {
    let icon: String
    let title: String
    let description: String
    
    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: icon)
                .foregroundColor(.Accent.gold)
                .frame(width: 20)
            
            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(.subheadline.bold())
                    .foregroundColor(.Text.primary)
                
                Text(description)
                    .font(.caption)
                    .foregroundColor(.Text.secondary)
            }
        }
    }
}

// MARK: - ViewModel

@MainActor
class AIProviderSettingsViewModel: ObservableObject {
    @Published var currentConfig: AIConfigResponse?
    @Published var providers: [AIProviderInfo] = []
    @Published var isLoading = false
    @Published var error: String?
    
    func load() async {
        isLoading = true
        error = nil
        
        do {
            async let configTask = APIService.shared.getAIConfig()
            async let providersTask = APIService.shared.getAIProviders()
            
            let (config, providersResponse) = try await (configTask, providersTask)
            
            currentConfig = config
            providers = providersResponse.providers
        } catch {
            self.error = error.localizedDescription
        }
        
        isLoading = false
    }
    
    func refresh() async {
        await load()
    }
}

// MARK: - Preview

#Preview {
    NavigationStack {
        AIProviderSettingsView()
    }
}
