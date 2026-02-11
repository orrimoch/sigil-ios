import SwiftUI

// MARK: - REC-259: Smart Money Picks Section

/// Displays weekly top 5 stocks with strongest insider buying signals
struct SmartMoneyPicksSection: View {
    @StateObject private var viewModel = SmartMoneyPicksViewModel()
    @State private var isExpanded = true
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Header
            Button(action: { withAnimation { isExpanded.toggle() }}) {
                HStack {
                    Label("Smart Money Picks", systemImage: "chart.line.uptrend.xyaxis")
                        .font(.headline)
                        .foregroundColor(.Text.primary)
                    
                    Spacer()
                    
                    if viewModel.isLoading {
                        ProgressView()
                            .scaleEffect(0.8)
                    }
                    
                    Image(systemName: isExpanded ? "chevron.up" : "chevron.down")
                        .foregroundColor(.Text.secondary)
                        .font(.caption)
                }
            }
            .accessibilityLabel("Smart Money Picks")
            .accessibilityHint(isExpanded ? "Tap to collapse" : "Tap to expand")
            
            if isExpanded {
                if let error = viewModel.error {
                    // Error state
                    VStack(spacing: 8) {
                        Image(systemName: "exclamationmark.triangle")
                            .foregroundColor(.orange)
                        Text(error)
                            .font(.caption)
                            .foregroundColor(.Text.secondary)
                            .multilineTextAlignment(.center)
                        Button("Retry") {
                            Task { await viewModel.loadPicks() }
                        }
                        .font(.caption)
                        .foregroundColor(.Brand.primary)
                    }
                    .frame(maxWidth: .infinity)
                    .padding()
                } else if viewModel.picks.isEmpty && !viewModel.isLoading {
                    // Empty state
                    VStack(spacing: 8) {
                        Image(systemName: "sparkles")
                            .font(.title2)
                            .foregroundColor(.Text.secondary)
                        Text("No smart money picks this week")
                            .font(.caption)
                            .foregroundColor(.Text.secondary)
                    }
                    .frame(maxWidth: .infinity)
                    .padding()
                } else {
                    // Picks list
                    VStack(spacing: 8) {
                        ForEach(viewModel.picks) { pick in
                            SmartMoneyPickRow(pick: pick)
                        }
                    }
                    
                    // Week indicator
                    if let weekStart = viewModel.weekStart {
                        HStack {
                            Image(systemName: "calendar")
                                .font(.caption2)
                            Text("Week of \(formattedWeekStart(weekStart))")
                                .font(.caption2)
                        }
                        .foregroundColor(.Text.tertiary)
                        .frame(maxWidth: .infinity, alignment: .trailing)
                    }
                }
            }
        }
        .padding()
        .background(Color.Background.secondary)
        .cornerRadius(12)
        .task {
            await viewModel.loadPicks()
        }
    }
    
    private func formattedWeekStart(_ weekStart: String) -> String {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        guard let date = formatter.date(from: weekStart) else { return weekStart }
        formatter.dateFormat = "MMM d"
        return formatter.string(from: date)
    }
}

// MARK: - Smart Money Pick Row

struct SmartMoneyPickRow: View {
    let pick: SmartMoneyPick
    
    var body: some View {
        NavigationLink {
            StockDetailView(ticker: pick.ticker)
        } label: {
            HStack(spacing: 12) {
                // Rank badge
                ZStack {
                    Circle()
                        .fill(rankColor)
                        .frame(width: 28, height: 28)
                    Text("\(pick.rank)")
                        .font(.caption.bold())
                        .foregroundColor(.white)
                }
                
                // Stock info
                VStack(alignment: .leading, spacing: 2) {
                    HStack(spacing: 4) {
                        Text(pick.ticker)
                            .font(.subheadline.bold())
                            .foregroundColor(.Text.primary)
                        
                        Text(pick.signalEmoji)
                            .font(.caption)
                    }
                    
                    Text(pick.companyName)
                        .font(.caption)
                        .foregroundColor(.Text.secondary)
                        .lineLimit(1)
                }
                
                Spacer()
                
                // Insider buying info
                VStack(alignment: .trailing, spacing: 2) {
                    Text(pick.formattedBuyValue)
                        .font(.subheadline.bold())
                        .foregroundColor(.Signal.buy)
                    
                    Text("\(pick.insiderBuyCount) insiders")
                        .font(.caption)
                        .foregroundColor(.Text.secondary)
                }
                
                Image(systemName: "chevron.right")
                    .font(.caption)
                    .foregroundColor(.Text.tertiary)
            }
            .padding(.vertical, 8)
            .padding(.horizontal, 4)
            .accessibilityElement(children: .combine)
            .accessibilityLabel("\(pick.ticker), rank \(pick.rank), \(pick.insiderBuyCount) insider buys totaling \(pick.formattedBuyValue)")
        }
        .buttonStyle(PlainButtonStyle())
    }
    
    private var rankColor: Color {
        switch pick.rank {
        case 1: return .Brand.primary
        case 2: return .orange
        case 3: return .yellow.opacity(0.8)
        default: return .Text.secondary
        }
    }
}

// MARK: - ViewModel

@MainActor
class SmartMoneyPicksViewModel: ObservableObject {
    @Published var picks: [SmartMoneyPick] = []
    @Published var weekStart: String?
    @Published var isLoading = false
    @Published var error: String?
    
    private let api = APIService.shared
    
    func loadPicks() async {
        isLoading = true
        error = nil
        
        do {
            let response = try await api.getSmartMoneyPicks()
            picks = response.picks
            weekStart = response.weekStart
        } catch {
            self.error = "Unable to load picks"
            print("[SmartMoneyPicks] Error: \(error)")
        }
        
        isLoading = false
    }
}

// MARK: - Preview

#if DEBUG
struct SmartMoneyPicksSection_Previews: PreviewProvider {
    static var previews: some View {
        SmartMoneyPicksSection()
            .padding()
            .background(Color.black)
            .previewLayout(.sizeThatFits)
    }
}
#endif
