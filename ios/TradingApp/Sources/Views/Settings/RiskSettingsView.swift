import SwiftUI

/// REC-215: Risk Settings Screen
/// User configures risk management parameters (all defaults OFF)
/// - Hard Stop-Loss
/// - Trailing Stop-Loss  
/// - VIX Adjustment
/// - Position Limits
struct RiskSettingsView: View {
    @StateObject private var service = RiskSettingsService.shared
    
    // Local editing state
    @State private var localSettings: RiskSettings = .defaults
    @State private var hasChanges = false
    @State private var showResetAlert = false
    @State private var showSaveError = false
    @State private var saveErrorMessage = ""
    
    var body: some View {
        List {
            // MARK: - Hard Stop-Loss Section
            Section {
                Toggle(isOn: $localSettings.hardStop.enabled) {
                    HStack {
                        Image(systemName: "hand.raised.fill")
                            .foregroundColor(localSettings.hardStop.enabled ? .Signal.sell : .Text.tertiary)
                        VStack(alignment: .leading) {
                            Text("Hard Stop-Loss")
                                .foregroundColor(.Text.primary)
                            Text("Auto-sell when loss exceeds threshold")
                                .font(.caption)
                                .foregroundColor(.Text.tertiary)
                        }
                    }
                }
                .tint(.Accent.gold)
                .onChange(of: localSettings.hardStop.enabled) { _ in hasChanges = true }
                
                if localSettings.hardStop.enabled {
                    VStack(alignment: .leading, spacing: 8) {
                        HStack {
                            Text("Threshold")
                                .foregroundColor(.Text.secondary)
                            Spacer()
                            // UX-005: Use absolute value for consistent sign convention
                            Text(String(format: "%.0f%%", abs(localSettings.hardStop.thresholdPct * 100)))
                                .foregroundColor(.Signal.sell)
                                .fontWeight(.semibold)
                        }
                        
                        Slider(
                            value: Binding(
                                get: { localSettings.hardStop.thresholdPct * -100 },
                                set: { localSettings.hardStop.thresholdPct = -$0 / 100 }
                            ),
                            in: 5...20,
                            step: 1
                        ) {
                            Text("Stop %")
                        } minimumValueLabel: {
                            Text("-5%")
                                .font(.caption2)
                                .foregroundColor(.Text.tertiary)
                        } maximumValueLabel: {
                            Text("-20%")
                                .font(.caption2)
                                .foregroundColor(.Text.tertiary)
                        }
                        .tint(.Signal.sell)
                        .onChange(of: localSettings.hardStop.thresholdPct) { _ in hasChanges = true }
                    }
                    .padding(.vertical, 4)
                }
            } header: {
                Text("Stop-Loss Protection")
                    .accessibilityAddTraits(.isHeader)
            } footer: {
                Text("Places IBKR stop order when enabled. Executes automatically even if app is closed.")
            }
            .listRowBackground(Color.Background.secondary)
            
            // MARK: - Trailing Stop-Loss Section
            Section {
                Toggle(isOn: $localSettings.trailingStop.enabled) {
                    HStack {
                        Image(systemName: "arrow.down.right.circle.fill")
                            .foregroundColor(localSettings.trailingStop.enabled ? .Accent.gold : .Text.tertiary)
                        VStack(alignment: .leading) {
                            Text("Trailing Stop")
                                .foregroundColor(.Text.primary)
                            Text("Lock in gains by selling if price drops from peak")
                                .font(.caption)
                                .foregroundColor(.Text.tertiary)
                        }
                    }
                }
                .tint(.Accent.gold)
                .onChange(of: localSettings.trailingStop.enabled) { _ in hasChanges = true }
                
                if localSettings.trailingStop.enabled {
                    VStack(alignment: .leading, spacing: 8) {
                        HStack {
                            Text("Distance from Peak")
                                .foregroundColor(.Text.secondary)
                            Spacer()
                            // UX-005: Use absolute value for consistent sign convention
                            Text(String(format: "%.0f%%", abs(localSettings.trailingStop.distancePct * 100)))
                                .foregroundColor(.Accent.gold)
                                .fontWeight(.semibold)
                        }
                        
                        Slider(
                            value: Binding(
                                get: { localSettings.trailingStop.distancePct * -100 },
                                set: { localSettings.trailingStop.distancePct = -$0 / 100 }
                            ),
                            in: 5...25,
                            step: 1
                        ) {
                            Text("Trail %")
                        } minimumValueLabel: {
                            Text("-5%")
                                .font(.caption2)
                                .foregroundColor(.Text.tertiary)
                        } maximumValueLabel: {
                            Text("-25%")
                                .font(.caption2)
                                .foregroundColor(.Text.tertiary)
                        }
                        .tint(.Accent.gold)
                        .onChange(of: localSettings.trailingStop.distancePct) { _ in hasChanges = true }
                    }
                    .padding(.vertical, 4)
                }
            } header: {
                Text("Profit Protection")
                    .accessibilityAddTraits(.isHeader)
            } footer: {
                Text("Trailing stop follows price up but never moves down. IBKR tracks the peak server-side.")
            }
            .listRowBackground(Color.Background.secondary)
            
            // MARK: - VIX Adjustment Section
            Section {
                Toggle(isOn: $localSettings.vixAdjustment.enabled) {
                    HStack {
                        Image(systemName: "waveform.path.ecg")
                            .foregroundColor(localSettings.vixAdjustment.enabled ? .Brand.primary : .Text.tertiary)
                        VStack(alignment: .leading) {
                            Text("VIX-Adjusted Signals")
                                .foregroundColor(.Text.primary)
                            Text("More conservative during high volatility")
                                .font(.caption)
                                .foregroundColor(.Text.tertiary)
                        }
                    }
                }
                .tint(.Accent.gold)
                .onChange(of: localSettings.vixAdjustment.enabled) { _ in hasChanges = true }
            } header: {
                Text("Market Conditions")
                    .accessibilityAddTraits(.isHeader)
            } footer: {
                Text("When VIX > 15, raises the bar for BUY signals and lowers it for SELL signals to protect you during turbulent markets.")
            }
            .listRowBackground(Color.Background.secondary)
            
            // MARK: - Position Limits Section
            Section {
                Toggle(isOn: $localSettings.positionLimit.enabled) {
                    HStack {
                        Image(systemName: "chart.pie.fill")
                            .foregroundColor(localSettings.positionLimit.enabled ? .Signal.buy : .Text.tertiary)
                        VStack(alignment: .leading) {
                            Text("Position Size Limit")
                                .foregroundColor(.Text.primary)
                            Text("Warn if trade exceeds portfolio percentage")
                                .font(.caption)
                                .foregroundColor(.Text.tertiary)
                        }
                    }
                }
                .tint(.Accent.gold)
                .onChange(of: localSettings.positionLimit.enabled) { _ in hasChanges = true }
                
                if localSettings.positionLimit.enabled {
                    VStack(alignment: .leading, spacing: 8) {
                        HStack {
                            Text("Max Position Size")
                                .foregroundColor(.Text.secondary)
                            Spacer()
                            Text(String(format: "%.0f%%", localSettings.positionLimit.maxPct * 100))
                                .foregroundColor(.Signal.buy)
                                .fontWeight(.semibold)
                        }
                        
                        Slider(
                            value: Binding(
                                get: { localSettings.positionLimit.maxPct * 100 },
                                set: { localSettings.positionLimit.maxPct = $0 / 100 }
                            ),
                            in: 5...30,
                            step: 1
                        ) {
                            Text("Max %")
                        } minimumValueLabel: {
                            Text("5%")
                                .font(.caption2)
                                .foregroundColor(.Text.tertiary)
                        } maximumValueLabel: {
                            Text("30%")
                                .font(.caption2)
                                .foregroundColor(.Text.tertiary)
                        }
                        .tint(.Signal.buy)
                        .onChange(of: localSettings.positionLimit.maxPct) { _ in hasChanges = true }
                    }
                    .padding(.vertical, 4)
                }
            } header: {
                Text("Position Sizing")
                    .accessibilityAddTraits(.isHeader)
            } footer: {
                Text("Shows a warning when a trade would make a single stock too large a portion of your portfolio.")
            }
            .listRowBackground(Color.Background.secondary)
            
            // MARK: - Actions Section
            Section {
                Button {
                    showResetAlert = true
                } label: {
                    HStack {
                        Image(systemName: "arrow.counterclockwise")
                            .foregroundColor(.Signal.sell)
                        Text("Reset to Defaults")
                            .foregroundColor(.Signal.sell)
                    }
                }
            }
            .listRowBackground(Color.Background.secondary)
        }
        .listStyle(.insetGrouped)
        .scrollContentBackground(.hidden)
        .background(Color.Background.primary)
        .navigationTitle("Risk Management")
        .navigationBarTitleDisplayMode(.large)
        .toolbarBackground(Color.Background.primary, for: .navigationBar)
        .toolbarColorScheme(.dark, for: .navigationBar)
        .toolbar {
            ToolbarItem(placement: .confirmationAction) {
                if hasChanges {
                    Button("Save") {
                        saveSettings()
                    }
                    .fontWeight(.semibold)
                    .foregroundColor(.Accent.gold)
                    .disabled(service.isSyncing)
                }
            }
        }
        .overlay {
            if service.isLoading || service.isSyncing {
                ProgressView()
                    .scaleEffect(1.5)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .background(Color.black.opacity(0.3))
            }
        }
        .onAppear {
            loadSettings()
        }
        .onDisappear {
            // Auto-save when navigating away if there are unsaved changes
            if hasChanges {
                Task {
                    try? await service.updateSettings(localSettings)
                }
            }
        }
        .alert("Reset to Defaults?", isPresented: $showResetAlert) {
            Button("Cancel", role: .cancel) {}
            Button("Reset", role: .destructive) {
                resetSettings()
            }
        } message: {
            Text("This will disable all risk protections and reset thresholds to their default values.")
        }
        .alert("Failed to Save", isPresented: $showSaveError) {
            Button("OK", role: .cancel) {}
        } message: {
            Text(saveErrorMessage)
        }
    }
    
    // MARK: - Private Methods
    
    private func loadSettings() {
        Task {
            await service.fetchSettings()
            await MainActor.run {
                localSettings = service.settings
                hasChanges = false
            }
        }
    }
    
    private func saveSettings() {
        Task {
            do {
                try await service.updateSettings(localSettings)
                await MainActor.run {
                    hasChanges = false
                }
            } catch {
                await MainActor.run {
                    saveErrorMessage = error.localizedDescription
                    showSaveError = true
                }
            }
        }
    }
    
    private func resetSettings() {
        Task {
            do {
                try await service.resetToDefaults()
                await MainActor.run {
                    localSettings = service.settings
                    hasChanges = false
                }
            } catch {
                await MainActor.run {
                    saveErrorMessage = error.localizedDescription
                    showSaveError = true
                }
            }
        }
    }
}

// MARK: - Preview

#Preview {
    NavigationStack {
        RiskSettingsView()
    }
    .preferredColorScheme(.dark)
}
