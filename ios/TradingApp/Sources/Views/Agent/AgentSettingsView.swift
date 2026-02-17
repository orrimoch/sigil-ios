import SwiftUI

struct AgentSettingsView: View {
    @StateObject private var viewModel = AgentSettingsViewModel()
    @Environment(\.dismiss) private var dismiss
    
    var body: some View {
        NavigationStack {
            Form {
                // Mode Section
                modeSection
                
                // Trading Parameters
                tradingParametersSection
                
                // Risk Management
                riskManagementSection
                
                // Automation
                automationSection
                
                // Danger Zone
                dangerZoneSection
            }
            .navigationTitle("Agent Settings")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Cancel") {
                        dismiss()
                    }
                }
                
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Save") {
                        Task {
                            await viewModel.save()
                            dismiss()
                        }
                    }
                    .fontWeight(.semibold)
                    .disabled(!viewModel.hasChanges)
                }
            }
            .task {
                await viewModel.loadSettings()
            }
        }
    }
    
    // MARK: - Mode Section
    
    private var modeSection: some View {
        Section {
            Picker("Execution Mode", selection: $viewModel.mode) {
                Text("Manual").tag("manual")
                Text("Supervised").tag("supervised")
                Text("Autonomous").tag("autonomous")
            }
            .pickerStyle(.segmented)
            
            // Mode description
            modeDescription
        } header: {
            Text("Execution Mode")
        } footer: {
            Text(viewModel.modeFooter)
        }
    }
    
    private var modeDescription: some View {
        HStack(spacing: 12) {
            Image(systemName: viewModel.modeIcon)
                .font(.title2)
                .foregroundColor(viewModel.modeColor)
                .frame(width: 40)
            
            VStack(alignment: .leading, spacing: 4) {
                Text(viewModel.modeTitle)
                    .font(.subheadline.weight(.medium))
                    .foregroundColor(.Text.primary)
                
                Text(viewModel.modeSubtitle)
                    .font(.caption)
                    .foregroundColor(.Text.secondary)
            }
        }
        .padding(.vertical, 4)
    }
    
    // MARK: - Trading Parameters
    
    private var tradingParametersSection: some View {
        Section {
            Stepper(
                "Max Trades/Week: \(viewModel.maxTradesPerWeek)",
                value: $viewModel.maxTradesPerWeek,
                in: 1...20
            )
            
            VStack(alignment: .leading, spacing: 8) {
                Text("Min Score to Buy: \(Int(viewModel.minScoreForBuy))")
                    .font(.subheadline)
                Slider(value: $viewModel.minScoreForBuy, in: 50...100, step: 5)
                    .tint(.green)
            }
            
            VStack(alignment: .leading, spacing: 8) {
                Text("Max Score to Sell: \(Int(viewModel.maxScoreForSell))")
                    .font(.subheadline)
                Slider(value: $viewModel.maxScoreForSell, in: 0...50, step: 5)
                    .tint(.red)
            }
        } header: {
            Text("Trading Parameters")
        }
    }
    
    // MARK: - Risk Management
    
    private var riskManagementSection: some View {
        Section {
            Picker("Risk Profile", selection: $viewModel.riskProfile) {
                Text("Conservative").tag("conservative")
                Text("Moderate").tag("moderate")
                Text("Aggressive").tag("aggressive")
            }
            
            Toggle("Enable Stop-Loss", isOn: $viewModel.stopLossEnabled)
            
            if viewModel.stopLossEnabled {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Stop-Loss: \(Int(viewModel.stopLossPercent))%")
                        .font(.subheadline)
                    Slider(value: $viewModel.stopLossPercent, in: 1...20, step: 1)
                        .tint(.orange)
                }
            }
        } header: {
            Text("Risk Management")
        } footer: {
            Text(riskFooter)
        }
    }
    
    private var riskFooter: String {
        switch viewModel.riskProfile {
        case "conservative":
            return "Lower position sizes, tighter stops, fewer trades."
        case "aggressive":
            return "Larger positions, wider stops, more frequent trading."
        default:
            return "Balanced approach between risk and reward."
        }
    }
    
    // MARK: - Automation
    
    private var automationSection: some View {
        Section {
            Toggle("Auto-Run Weekly", isOn: $viewModel.autoRunEnabled)
        } header: {
            Text("Automation")
        } footer: {
            Text("When enabled, agent runs automatically at market open on Mondays.")
        }
    }
    
    // MARK: - Danger Zone
    
    private var dangerZoneSection: some View {
        Section {
            Button(role: .destructive) {
                viewModel.resetToDefaults()
            } label: {
                Label("Reset to Defaults", systemImage: "arrow.counterclockwise")
            }
        } header: {
            Text("Danger Zone")
        }
    }
}

// MARK: - ViewModel

@MainActor
class AgentSettingsViewModel: ObservableObject {
    @Published var mode: String = "supervised"
    @Published var maxTradesPerWeek: Int = 5
    @Published var minScoreForBuy: Double = 70
    @Published var maxScoreForSell: Double = 40
    @Published var riskProfile: String = "moderate"
    @Published var stopLossEnabled: Bool = true
    @Published var stopLossPercent: Double = 8
    @Published var autoRunEnabled: Bool = false
    
    private var originalSettings: AgentSettings?
    
    var hasChanges: Bool {
        guard let original = originalSettings else { return false }
        return mode != original.mode ||
            maxTradesPerWeek != original.maxTradesPerWeek ||
            minScoreForBuy != original.minScoreForBuy ||
            maxScoreForSell != original.maxScoreForSell ||
            riskProfile != original.riskProfile ||
            stopLossEnabled != original.stopLossEnabled ||
            stopLossPercent != original.stopLossPercent ||
            autoRunEnabled != original.autoRunEnabled
    }
    
    var modeIcon: String {
        switch mode {
        case "manual": return "hand.raised"
        case "supervised": return "eye"
        case "autonomous": return "cpu"
        default: return "questionmark"
        }
    }
    
    var modeColor: Color {
        switch mode {
        case "manual": return .blue
        case "supervised": return .orange
        case "autonomous": return .green
        default: return .gray
        }
    }
    
    var modeTitle: String {
        switch mode {
        case "manual": return "Manual Mode"
        case "supervised": return "Supervised Mode"
        case "autonomous": return "Autonomous Mode"
        default: return "Unknown"
        }
    }
    
    var modeSubtitle: String {
        switch mode {
        case "manual": return "Agent suggests, you execute"
        case "supervised": return "Agent queues, you approve"
        case "autonomous": return "Agent executes automatically"
        default: return ""
        }
    }
    
    var modeFooter: String {
        switch mode {
        case "manual":
            return "Agent will analyze and provide recommendations. All trading actions must be performed manually."
        case "supervised":
            return "Agent will queue trades for your approval. You have 24 hours to approve or reject each trade."
        case "autonomous":
            return "⚠️ Agent will execute trades automatically without approval. Use with caution."
        default:
            return ""
        }
    }
    
    func loadSettings() async {
        do {
            let response = try await AgentService.shared.getStatus()
            
            // Parse settings from response
            if let modeValue = response.settings["mode"]?.value as? String {
                mode = modeValue
            }
            if let maxTrades = response.settings["max_trades_per_week"]?.value as? Int {
                maxTradesPerWeek = maxTrades
            }
            if let minScore = response.settings["min_score_for_buy"]?.value as? Double {
                minScoreForBuy = minScore
            }
            if let maxScore = response.settings["max_score_for_sell"]?.value as? Double {
                maxScoreForSell = maxScore
            }
            if let risk = response.settings["risk_profile"]?.value as? String {
                riskProfile = risk
            }
            if let stopEnabled = response.settings["stop_loss_enabled"]?.value as? Bool {
                stopLossEnabled = stopEnabled
            }
            if let stopPct = response.settings["stop_loss_percent"]?.value as? Double {
                stopLossPercent = stopPct
            }
            if let autoRun = response.settings["auto_run_enabled"]?.value as? Bool {
                autoRunEnabled = autoRun
            }
            
            // Store original for comparison
            originalSettings = AgentSettings(
                mode: mode,
                maxTradesPerWeek: maxTradesPerWeek,
                minScoreForBuy: minScoreForBuy,
                maxScoreForSell: maxScoreForSell,
                riskProfile: riskProfile,
                stopLossEnabled: stopLossEnabled,
                stopLossPercent: stopLossPercent,
                autoRunEnabled: autoRunEnabled
            )
        } catch {
            print("Failed to load settings: \(error)")
            // Use defaults
            originalSettings = AgentSettings.default
        }
    }
    
    func save() async {
        let settings = AgentSettings(
            mode: mode,
            maxTradesPerWeek: maxTradesPerWeek,
            minScoreForBuy: minScoreForBuy,
            maxScoreForSell: maxScoreForSell,
            riskProfile: riskProfile,
            stopLossEnabled: stopLossEnabled,
            stopLossPercent: stopLossPercent,
            autoRunEnabled: autoRunEnabled
        )
        
        do {
            _ = try await AgentService.shared.updateSettings(settings)
            originalSettings = settings
        } catch {
            print("Failed to save settings: \(error)")
        }
    }
    
    func resetToDefaults() {
        let defaults = AgentSettings.default
        mode = defaults.mode
        maxTradesPerWeek = defaults.maxTradesPerWeek
        minScoreForBuy = defaults.minScoreForBuy
        maxScoreForSell = defaults.maxScoreForSell
        riskProfile = defaults.riskProfile
        stopLossEnabled = defaults.stopLossEnabled
        stopLossPercent = defaults.stopLossPercent
        autoRunEnabled = defaults.autoRunEnabled
    }
}

#Preview {
    AgentSettingsView()
}
