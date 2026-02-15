import SwiftUI

/// List of user's price alerts (REC-158)
struct MyAlertsView: View {
    @StateObject private var viewModel = MyAlertsViewModel()
    @State private var alertToDelete: PriceAlert?
    @State private var showDeleteConfirmation = false
    
    var body: some View {
        List {
            if viewModel.isLoading && viewModel.alerts.isEmpty {
                // Loading skeleton
                ForEach(0..<3, id: \.self) { _ in
                    HStack {
                        VStack(alignment: .leading, spacing: 4) {
                            RoundedRectangle(cornerRadius: 4)
                                .fill(Color.Background.tertiary)
                                .frame(width: 60, height: 16)
                            RoundedRectangle(cornerRadius: 4)
                                .fill(Color.Background.tertiary)
                                .frame(width: 120, height: 12)
                        }
                        Spacer()
                        RoundedRectangle(cornerRadius: 4)
                            .fill(Color.Background.tertiary)
                            .frame(width: 80, height: 16)
                    }
                    .padding(.vertical, 4)
                }
                .shimmer()
                .listRowBackground(Color.Background.secondary)
            } else if viewModel.alerts.isEmpty {
                // Empty state
                VStack(spacing: 16) {
                    Image(systemName: "bell.slash")
                        .font(.largeTitle)
                        .foregroundColor(.Text.tertiary)
                    
                    Text("No Price Alerts")
                        .font(.headline)
                        .foregroundColor(.Text.primary)
                    
                    Text("Set alerts from any stock detail page to get notified when prices hit your targets.")
                        .font(.caption)
                        .foregroundColor(.Text.secondary)
                        .multilineTextAlignment(.center)
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 40)
                .listRowBackground(Color.Background.primary)
            } else {
                // Active alerts section
                let activeAlerts = viewModel.alerts.filter { $0.isActive }
                if !activeAlerts.isEmpty {
                    Section {
                        ForEach(activeAlerts) { alert in
                            PriceAlertRow(alert: alert)
                                .swipeActions(edge: .trailing, allowsFullSwipe: true) {
                                    Button(role: .destructive) {
                                        alertToDelete = alert
                                        showDeleteConfirmation = true
                                    } label: {
                                        Label("Delete", systemImage: "trash")
                                    }
                                }
                        }
                    } header: {
                        Text("Active Alerts")
                    }
                    .listRowBackground(Color.Background.secondary)
                }
                
                // Triggered alerts section
                let triggeredAlerts = viewModel.alerts.filter { !$0.isActive }
                if !triggeredAlerts.isEmpty {
                    Section {
                        ForEach(triggeredAlerts) { alert in
                            PriceAlertRow(alert: alert, isTriggered: true)
                                .swipeActions(edge: .trailing, allowsFullSwipe: true) {
                                    Button(role: .destructive) {
                                        alertToDelete = alert
                                        showDeleteConfirmation = true
                                    } label: {
                                        Label("Delete", systemImage: "trash")
                                    }
                                }
                        }
                    } header: {
                        Text("Triggered")
                    } footer: {
                        Text("Triggered alerts are automatically deactivated.")
                    }
                    .listRowBackground(Color.Background.secondary)
                }
            }
        }
        .listStyle(.insetGrouped)
        .scrollContentBackground(.hidden)
        .background(Color.Background.primary)
        .navigationTitle("My Alerts")
        .navigationBarTitleDisplayMode(.large)
        .toolbarBackground(Color.Background.primary, for: .navigationBar)
        .toolbarColorScheme(.dark, for: .navigationBar)
        .refreshable {
            await viewModel.loadAlerts()
        }
        .task {
            await viewModel.loadAlerts()
        }
        .alert("Delete Alert?", isPresented: $showDeleteConfirmation) {
            Button("Cancel", role: .cancel) {
                alertToDelete = nil
            }
            Button("Delete", role: .destructive) {
                if let alert = alertToDelete {
                    Task {
                        await viewModel.deleteAlert(alert)
                    }
                }
                alertToDelete = nil
            }
        } message: {
            if let alert = alertToDelete {
                Text("Delete alert for \(alert.ticker) \(alert.condition.lowercased()) $\(String(format: "%.2f", alert.targetPrice))?")
            }
        }
        .overlay {
            if let error = viewModel.errorMessage {
                VStack {
                    Spacer()
                    Text(error)
                        .font(.caption)
                        .foregroundColor(.white)
                        .padding()
                        .background(Color.Signal.sell)
                        .cornerRadius(8)
                        .padding()
                }
            }
        }
    }
}

// MARK: - Price Alert Row

struct PriceAlertRow: View {
    let alert: PriceAlert
    var isTriggered: Bool = false
    
    var body: some View {
        HStack(spacing: 12) {
            // Condition icon
            Image(systemName: alert.conditionType.icon)
                .font(.title2)
                .foregroundColor(isTriggered ? .Signal.neutral : (alert.conditionType == .above ? .Signal.buy : .Signal.sell))
            
            // Alert info
            VStack(alignment: .leading, spacing: 2) {
                HStack {
                    Text(alert.ticker)
                        .font(.headline)
                        .foregroundColor(isTriggered ? .Text.secondary : .Text.primary)
                    
                    if isTriggered {
                        Text("TRIGGERED")
                            .font(.caption2.bold())
                            .foregroundColor(.white)
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(Color.Signal.neutral)
                            .cornerRadius(4)
                    }
                }
                
                Text("\(alert.condition.capitalized) \(alert.targetPrice.asCurrency)")
                    .font(.subheadline)
                    .foregroundColor(.Text.secondary)
                
                if let createdDate = alert.createdDate {
                    Text("Created \(createdDate.formatted(.relative(presentation: .named)))")
                        .font(.caption)
                        .foregroundColor(.Text.tertiary)
                }
            }
            
            Spacer()
            
            // Status indicator
            if !isTriggered {
                Circle()
                    .fill(Color.Signal.buy)
                    .frame(width: 8, height: 8)
            }
        }
        .padding(.vertical, 4)
        .opacity(isTriggered ? 0.6 : 1.0)
    }
}

// MARK: - ViewModel

@MainActor
class MyAlertsViewModel: ObservableObject {
    @Published var alerts: [PriceAlert] = []
    @Published var isLoading = false
    @Published var errorMessage: String?
    
    func loadAlerts() async {
        isLoading = true
        errorMessage = nil
        
        do {
            let response = try await APIService.shared.getPriceAlerts()
            alerts = response.data.sorted { a, b in
                // Active alerts first, then by created date
                if a.isActive != b.isActive {
                    return a.isActive
                }
                return (a.createdDate ?? Date()) > (b.createdDate ?? Date())
            }
        } catch {
            errorMessage = error.localizedDescription
        }
        
        isLoading = false
    }
    
    func deleteAlert(_ alert: PriceAlert) async {
        do {
            _ = try await APIService.shared.deletePriceAlert(alertId: alert.id)
            alerts.removeAll { $0.id == alert.id }
        } catch {
            errorMessage = "Failed to delete alert: \(error.localizedDescription)"
            // Clear error after a delay
            DispatchQueue.main.asyncAfter(deadline: .now() + 3) {
                self.errorMessage = nil
            }
        }
    }
}

// MARK: - Preview

#Preview {
    NavigationStack {
        MyAlertsView()
    }
}
