import SwiftUI

// MARK: - REC-266: Reddit Trending Stocks Section

/// Displays weekly top 5 trending stocks based on Reddit viral activity
struct SmartMoneyPicksSection: View {
    @StateObject private var viewModel = SmartMoneyPicksViewModel()
    @State private var isExpanded = true
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Header
            Button(action: { withAnimation { isExpanded.toggle() }}) {
                HStack {
                    Label("🔥 Trending on Reddit", systemImage: "flame")
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
            .accessibilityLabel("Trending on Reddit")
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
                        Image(systemName: "flame.circle")
                            .font(.title2)
                            .foregroundColor(.Text.secondary)
                        Text("No trending stocks this week")
                            .font(.caption)
                            .foregroundColor(.Text.secondary)
                    }
                    .frame(maxWidth: .infinity)
                    .padding()
                } else {
                    // Picks list
                    VStack(spacing: 8) {
                        ForEach(viewModel.picks) { pick in
                            TrendingPickRow(pick: pick)
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

// MARK: - Trending Pick Row

struct TrendingPickRow: View {
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
                        
                        Text(pick.sentimentEmoji)
                            .font(.caption)
                    }
                    
                    Text(pick.companyName)
                        .font(.caption)
                        .foregroundColor(.Text.secondary)
                        .lineLimit(1)
                }
                
                Spacer()
                
                // Reddit metrics
                VStack(alignment: .trailing, spacing: 2) {
                    HStack(spacing: 4) {
                        Image(systemName: "bubble.left.fill")
                            .font(.system(size: 10))
                            .foregroundColor(.Text.tertiary)
                        Text(pick.formattedMentions)
                            .font(.subheadline.bold())
                            .foregroundColor(.Brand.primary)
                    }
                    
                    HStack(spacing: 4) {
                        Image(systemName: "arrow.up.circle.fill")
                            .font(.system(size: 10))
                            .foregroundColor(.Text.tertiary)
                        Text(pick.formattedUpvotes)
                            .font(.caption)
                            .foregroundColor(.Text.secondary)
                    }
                }
                
                Image(systemName: "chevron.right")
                    .font(.caption)
                    .foregroundColor(.Text.tertiary)
            }
            .padding(.vertical, 8)
            .padding(.horizontal, 4)
            .accessibilityElement(children: .combine)
            .accessibilityLabel("\(pick.ticker), rank \(pick.rank), \(pick.mentionCount) mentions, \(pick.totalUpvotes) upvotes")
        }
        .buttonStyle(PlainButtonStyle())
    }
    
    private var rankColor: Color {
        switch pick.rank {
        case 1: return .red
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
            self.error = "Unable to load trending stocks"
            print("[TrendingPicks] Error: \(error)")
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
