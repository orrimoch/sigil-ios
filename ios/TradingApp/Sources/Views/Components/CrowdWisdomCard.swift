import SwiftUI

// MARK: - REC-260: Crowd Wisdom Card for Stock Detail
// Shows Reddit viral data for a specific ticker

struct CrowdWisdomCard: View {
    let ticker: String
    @StateObject private var viewModel: CrowdWisdomCardViewModel
    
    init(ticker: String) {
        self.ticker = ticker
        self._viewModel = StateObject(wrappedValue: CrowdWisdomCardViewModel(ticker: ticker))
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Header
            HStack {
                Image(systemName: "flame.fill")
                    .foregroundColor(.orange)
                Text("Reddit Activity")
                    .font(.headline)
                    .foregroundColor(.Text.primary)
                
                Spacer()
                
                if viewModel.isLoading {
                    ProgressView()
                        .scaleEffect(0.8)
                }
            }
            
            if let data = viewModel.trendingData {
                // Trending data available
                VStack(spacing: 12) {
                    // Signal badge
                    HStack {
                        RedditSignalBadge(signal: data.signal)
                        Spacer()
                        Text("Viral Score: \(String(format: "%.1f", data.viralScore))")
                            .font(.subheadline.bold())
                            .foregroundColor(.Brand.primary)
                    }
                    
                    Divider()
                        .background(Color.Utility.divider)
                    
                    // Metrics grid
                    HStack(spacing: 20) {
                        MetricItem(
                            icon: "bubble.left.fill",
                            value: data.formattedMentions,
                            label: "Mentions"
                        )
                        
                        MetricItem(
                            icon: "arrow.up.circle.fill",
                            value: data.formattedUpvotes,
                            label: "Upvotes"
                        )
                        
                        MetricItem(
                            icon: "chart.line.uptrend.xyaxis",
                            value: String(format: "%.1fx", data.trendingVelocity),
                            label: "Velocity"
                        )
                    }
                    
                    // Sentiment indicator
                    HStack {
                        Text("Sentiment:")
                            .font(.caption)
                            .foregroundColor(.Text.secondary)
                        
                        Text(data.sentimentEmoji)
                        
                        Text(data.sentimentLabel.replacingOccurrences(of: "_", with: " "))
                            .font(.caption.bold())
                            .foregroundColor(sentimentColor(data.sentimentLabel))
                        
                        Spacer()
                    }
                }
            } else if viewModel.notTrending {
                // Not currently trending
                VStack(spacing: 8) {
                    Image(systemName: "chart.bar.xaxis")
                        .font(.title2)
                        .foregroundColor(.Text.tertiary)
                    Text("Not currently trending on Reddit")
                        .font(.caption)
                        .foregroundColor(.Text.secondary)
                    Text("Stock isn't in the top Reddit mentions this week")
                        .font(.caption2)
                        .foregroundColor(.Text.tertiary)
                        .multilineTextAlignment(.center)
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 8)
            } else if let error = viewModel.error {
                // Error state
                VStack(spacing: 8) {
                    Image(systemName: "exclamationmark.triangle")
                        .foregroundColor(.orange)
                    Text(error)
                        .font(.caption)
                        .foregroundColor(.Text.secondary)
                    Button("Retry") {
                        Task { await viewModel.load() }
                    }
                    .font(.caption)
                    .foregroundColor(.Brand.primary)
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 8)
            }
        }
        .padding()
        .background(Color.Background.secondary)
        .cornerRadius(12)
        .task {
            await viewModel.load()
        }
    }
    
    private func sentimentColor(_ sentiment: String) -> Color {
        switch sentiment {
        case "VERY_BULLISH": return .green
        case "BULLISH": return .green.opacity(0.8)
        case "NEUTRAL": return .Text.secondary
        case "BEARISH": return .red.opacity(0.8)
        case "VERY_BEARISH": return .red
        default: return .Text.secondary
        }
    }
}

// MARK: - Reddit Signal Badge

private struct RedditSignalBadge: View {
    let signal: String
    
    var body: some View {
        HStack(spacing: 4) {
            Image(systemName: iconName)
                .font(.caption)
            Text(signal)
                .font(.caption.bold())
        }
        .foregroundColor(.white)
        .padding(.horizontal, 10)
        .padding(.vertical, 4)
        .background(backgroundColor)
        .cornerRadius(6)
    }
    
    private var iconName: String {
        switch signal {
        case "VERY_HOT": return "flame.fill"
        case "HOT": return "flame"
        case "TRENDING": return "arrow.up.right"
        default: return "minus"
        }
    }
    
    private var backgroundColor: Color {
        switch signal {
        case "VERY_HOT": return .red
        case "HOT": return .orange
        case "TRENDING": return .yellow.opacity(0.9)
        default: return .Text.secondary
        }
    }
}

// MARK: - Metric Item

private struct MetricItem: View {
    let icon: String
    let value: String
    let label: String
    
    var body: some View {
        VStack(spacing: 4) {
            HStack(spacing: 4) {
                Image(systemName: icon)
                    .font(.caption)
                    .foregroundColor(.Text.tertiary)
                Text(value)
                    .font(.subheadline.bold())
                    .foregroundColor(.Text.primary)
            }
            Text(label)
                .font(.caption2)
                .foregroundColor(.Text.tertiary)
        }
    }
}

// MARK: - ViewModel

@MainActor
class CrowdWisdomCardViewModel: ObservableObject {
    let ticker: String
    
    @Published var trendingData: SmartMoneyPick?
    @Published var notTrending = false
    @Published var isLoading = false
    @Published var error: String?
    
    init(ticker: String) {
        self.ticker = ticker
    }
    
    func load() async {
        isLoading = true
        error = nil
        notTrending = false
        
        // First check the cached trending data
        if let cached = TrendingTickersService.shared.getTrendingData(ticker) {
            trendingData = cached
            isLoading = false
            return
        }
        
        // If not in cache, try to fetch from API
        do {
            let response = try await APIService.shared.getCrowdWisdomScore(ticker: ticker)
            
            if response.viralScore > 0 {
                // Convert TrendingTicker to SmartMoneyPick for consistency
                trendingData = SmartMoneyPick(
                    rank: 0, // Not ranked
                    ticker: response.ticker,
                    companyName: response.companyName,
                    viralScore: response.viralScore,
                    mentionCount: response.mentionCount,
                    totalUpvotes: response.totalUpvotes,
                    sentimentLabel: response.sentimentLabel,
                    trendingVelocity: response.trendingVelocity,
                    currentPrice: response.currentPrice,
                    signal: response.signal
                )
            } else {
                notTrending = true
            }
        } catch {
            // Not an error - just means the ticker isn't trending
            notTrending = true
            #if DEBUG
            debugLog("[CrowdWisdomCard] \(ticker) not trending: \(error.localizedDescription)")
            #endif
        }
        
        isLoading = false
    }
}

// MARK: - Preview

#if DEBUG
struct CrowdWisdomCard_Previews: PreviewProvider {
    static var previews: some View {
        VStack(spacing: 16) {
            CrowdWisdomCard(ticker: "PLTR")
            CrowdWisdomCard(ticker: "AAPL")
        }
        .padding()
        .background(Color.black)
        .previewLayout(.sizeThatFits)
    }
}
#endif
