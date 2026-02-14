import SwiftUI

// MARK: - REC-168: Daily Loss Limit Settings and Indicators

/// Daily PnL indicator for HomeView
struct DailyPnLIndicator: View {
    @State private var dailyPnL: IBKRDailyPnL?
    @State private var isLoading = false
    @State private var showHaltedAlert = false
    
    var body: some View {
        Group {
            if let pnl = dailyPnL {
                HStack(spacing: 12) {
                    // PnL Amount
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Today's P&L")
                            .font(.caption)
                            .foregroundColor(.Text.tertiary)
                        
                        HStack(spacing: 4) {
                            Text(pnl.dailyPnl >= 0 ? "+$\(pnl.dailyPnl, specifier: "%.2f")" : "-$\(abs(pnl.dailyPnl), specifier: "%.2f")")
                                .font(.headline.bold())
                                .foregroundColor(pnl.dailyPnl >= 0 ? .Signal.buy : .Signal.sell)
                            
                            Text("(\(pnl.dailyPnlPercent, specifier: "%.1f")%)")
                                .font(.caption)
                                .foregroundColor(pnl.dailyPnl >= 0 ? .Signal.buy : .Signal.sell)
                        }
                    }
                    
                    Spacer()
                    
                    // Trading Status
                    if pnl.tradingHalted {
                        Button {
                            showHaltedAlert = true
                        } label: {
                            HStack(spacing: 4) {
                                Image(systemName: "exclamationmark.octagon.fill")
                                Text("HALTED")
                                    .font(.caption.bold())
                            }
                            .foregroundColor(.white)
                            .padding(.horizontal, 10)
                            .padding(.vertical, 6)
                            .background(Color.Signal.sell)
                            .cornerRadius(8)
                        }
                    } else {
                        HStack(spacing: 4) {
                            Circle()
                                .fill(Color.Signal.buy)
                                .frame(width: 8, height: 8)
                            Text("ACTIVE")
                                .font(.caption.bold())
                                .foregroundColor(.Signal.buy)
                        }
                    }
                }
                .padding()
                .background(Color.Background.secondary)
                .cornerRadius(12)
            } else if isLoading {
                HStack {
                    ProgressView()
                        .tint(.Brand.primary)
                    Text("Loading P&L...")
                        .font(.caption)
                        .foregroundColor(.Text.tertiary)
                }
                .frame(maxWidth: .infinity)
                .padding()
                .background(Color.Background.secondary)
                .cornerRadius(12)
            }
        }
        .task {
            await loadDailyPnL()
        }
        .alert("Trading Halted", isPresented: $showHaltedAlert) {
            Button("OK", role: .cancel) {}
        } message: {
            Text("Daily loss limit exceeded. Trading is halted for today to protect your account.")
        }
    }
    
    private func loadDailyPnL() async {
        guard IBKRService.shared.isConnected else { return }
        isLoading = true
        defer { isLoading = false }
        
        do {
            dailyPnL = try await IBKRService.shared.getDailyPnL()
        } catch {
            #if DEBUG
            debugError(error, context: "Failed to load daily PnL")
            #endif
        }
    }
}

/// Settings row for configuring daily loss limit
struct DailyLossLimitSettingsSection: View {
    @State private var isEnabled = true
    @State private var lossLimitPercent: Double = 5.0
    @State private var isSaving = false
    @State private var showSavedToast = false
    @State private var isLoading = true
    @State private var saveError: String?
    @State private var loadError: String?
    @State private var hasLoadedFromBackend = false
    
    var body: some View {
        Section {
            if isLoading {
                // Loading skeleton
                HStack {
                    Image(systemName: "shield.fill")
                        .foregroundColor(.Brand.primary)
                    Text("Daily Loss Limit")
                        .foregroundColor(.Text.primary)
                    Spacer()
                    ProgressView()
                        .tint(.Brand.primary)
                }
            } else if let error = loadError {
                // Error state
                HStack {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .foregroundColor(.Signal.hold)
                    Text("Failed to load settings")
                        .foregroundColor(.Text.secondary)
                    Spacer()
                    Button("Retry") {
                        Task { await loadCurrentLimit() }
                    }
                    .font(.caption.bold())
                    .foregroundColor(.Brand.primary)
                }
            } else {
                // Enable/Disable Toggle
                Toggle(isOn: $isEnabled) {
                    HStack {
                        Image(systemName: "shield.fill")
                            .foregroundColor(.Brand.primary)
                        Text("Daily Loss Limit")
                            .foregroundColor(.Text.primary)
                    }
                }
                .tint(.Brand.primary)
                
                // Loss Limit Slider (only show when enabled)
                if isEnabled {
                    VStack(alignment: .leading, spacing: 12) {
                        HStack {
                            Text("Limit")
                                .foregroundColor(.Text.secondary)
                            Spacer()
                            Text("\(lossLimitPercent, specifier: "%.1f")%")
                                .font(.headline.bold())
                                .foregroundColor(.Brand.primary)
                        }
                        
                        Slider(value: $lossLimitPercent, in: 1...20, step: 0.5)
                            .tint(.Brand.primary)
                        
                        Text("Trading halts when daily loss exceeds \(lossLimitPercent, specifier: "%.1f")% of account value")
                            .font(.caption)
                            .foregroundColor(.Text.tertiary)
                    }
                    .padding(.vertical, 4)
                    
                    // Save Button
                    Button {
                        Task { await saveLossLimit() }
                    } label: {
                        HStack {
                            if isSaving {
                                ProgressView()
                                    .tint(.white)
                            } else {
                                Image(systemName: "checkmark.circle.fill")
                                Text("Save Limit")
                            }
                        }
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 12)
                        .background(Color.Brand.primary)
                        .foregroundColor(.Background.primary)
                        .cornerRadius(12)
                    }
                    .disabled(isSaving)
                }
            }
        } header: {
            Text("Risk Management")
                .accessibilityAddTraits(.isHeader)
        } footer: {
            if isEnabled && !isLoading && loadError == nil {
                Text("⚠️ When triggered, all new orders are blocked until the next trading day.")
                    .foregroundColor(.Signal.hold)
            }
        }
        .listRowBackground(Color.Background.secondary)
        .task {
            await loadCurrentLimit()
        }
        .alert("Save Failed", isPresented: .constant(saveError != nil)) {
            Button("OK") { saveError = nil }
        } message: {
            Text(saveError ?? "Unknown error")
        }
    }
    
    private func loadCurrentLimit() async {
        isLoading = true
        loadError = nil
        
        guard IBKRService.shared.isConnected else {
            // Not connected - use defaults but mark as loaded
            isLoading = false
            hasLoadedFromBackend = false
            return
        }
        
        do {
            let pnl = try await IBKRService.shared.getDailyPnL()
            lossLimitPercent = pnl.lossLimitPercent
            hasLoadedFromBackend = true
            isLoading = false
        } catch {
            loadError = error.localizedDescription
            isLoading = false
        }
    }
    
    private func saveLossLimit() async {
        guard IBKRService.shared.isConnected else {
            saveError = "Not connected to IB Gateway"
            return
        }
        isSaving = true
        defer { isSaving = false }
        
        do {
            try await IBKRService.shared.setDailyLossLimit(percent: lossLimitPercent)
            // Show haptic feedback
            UINotificationFeedbackGenerator().notificationOccurred(.success)
        } catch {
            saveError = error.localizedDescription
        }
    }
}

/// Modal shown when trading is halted
struct TradingHaltedSheet: View {
    @Environment(\.dismiss) private var dismiss
    let dailyPnL: IBKRDailyPnL
    
    var body: some View {
        VStack(spacing: 24) {
            // Warning Icon
            Image(systemName: "exclamationmark.octagon.fill")
                .font(.iconSize(60)).limitedScaling()
                .foregroundColor(.Signal.sell)
            
            Text("Trading Halted")
                .font(.title.bold())
                .foregroundColor(.Text.primary)
            
            Text("Your daily loss limit has been reached. Trading is suspended to protect your account.")
                .font(.body)
                .foregroundColor(.Text.secondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal)
            
            // Stats
            VStack(spacing: 12) {
                HStack {
                    Text("Today's Loss")
                    Spacer()
                    Text("-$\(abs(dailyPnL.dailyPnl), specifier: "%.2f")")
                        .foregroundColor(.Signal.sell)
                        .bold()
                }
                
                HStack {
                    Text("Loss Limit")
                    Spacer()
                    Text("\(dailyPnL.lossLimitPercent, specifier: "%.1f")%")
                        .foregroundColor(.Text.secondary)
                }
                
                HStack {
                    Text("Resumes")
                    Spacer()
                    Text("Tomorrow 9:30 AM ET")
                        .foregroundColor(.Text.secondary)
                }
            }
            .padding()
            .background(Color.Background.secondary)
            .cornerRadius(12)
            .padding(.horizontal)
            
            Spacer()
            
            Button {
                dismiss()
            } label: {
                Text("I Understand")
                    .font(.headline)
                    .frame(maxWidth: .infinity)
                    .padding()
                    .background(Color.Brand.primary)
                    .foregroundColor(.Background.primary)
                    .cornerRadius(12)
            }
            .padding(.horizontal)
            .padding(.bottom)
        }
        .padding(.top, 40)
        .background(Color.Background.primary)
    }
}

#Preview {
    VStack(spacing: 20) {
        DailyPnLIndicator()
        
        List {
            DailyLossLimitSettingsSection()
        }
        .listStyle(.insetGrouped)
    }
    .background(Color.Background.primary)
}
