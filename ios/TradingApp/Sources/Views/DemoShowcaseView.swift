import SwiftUI

// TEMPORARY: Demo view to showcase new IB Gateway features
// Delete after demo recording

struct DemoShowcaseView: View {
    @State private var selectedDemo = 0
    @State private var isAutoPlaying = false
    
    let demos = [
        "1. Chart View",
        "2. Bracket Order", 
        "3. Market Scanner",
        "4. Margin Preview",
        "5. Trade History",
        "6. Loss Limit",
        "7. Volume Alerts"
    ]
    
    // Auto-advance timer
    let timer = Timer.publish(every: 3, on: .main, in: .common).autoconnect()
    
    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                // Demo selector
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        ForEach(0..<demos.count, id: \.self) { index in
                            Button {
                                withAnimation { selectedDemo = index }
                            } label: {
                                Text(demos[index])
                                    .font(.caption.bold())
                                    .foregroundColor(selectedDemo == index ? .black : .Brand.primary)
                                    .padding(.horizontal, 12)
                                    .padding(.vertical, 8)
                                    .background(selectedDemo == index ? Color.Brand.primary : Color.Background.secondary)
                                    .cornerRadius(20)
                            }
                        }
                    }
                    .padding(.horizontal)
                }
                .padding(.vertical, 12)
                .background(Color.Background.primary)
                
                // Demo content
                TabView(selection: $selectedDemo) {
                    // 1. Chart View
                    IBKRChartView(ticker: "AAPL")
                        .tag(0)
                    
                    // 2. Bracket Order
                    BracketOrderForm(
                        ticker: "NVDA",
                        currentPrice: 142.50,
                        side: "BUY",
                        isPresented: .constant(true)
                    )
                    .tag(1)
                    
                    // 3. Market Scanner
                    MarketScannerView()
                        .tag(2)
                    
                    // 4. Margin Preview
                    MarginPreviewSheet(
                        ticker: "TSLA",
                        side: "BUY",
                        quantity: 50,
                        orderType: "LMT",
                        limitPrice: 248.00,
                        onConfirm: {}
                    )
                    .tag(3)
                    
                    // 5. Trade History
                    TradeHistoryView()
                        .tag(4)
                    
                    // 6. Daily Loss Limit
                    List {
                        DailyLossLimitSettingsSection()
                    }
                    .listStyle(.insetGrouped)
                    .scrollContentBackground(.hidden)
                    .background(Color.Background.primary)
                    .tag(5)
                    
                    // 7. Volume Alerts
                    ScrollView {
                        VStack(spacing: 16) {
                            VolumeAnalysisCard(ticker: "AAPL")
                            VolumeAnalysisCard(ticker: "NVDA")
                            VolumeAnalysisCard(ticker: "TSLA")
                        }
                        .padding()
                    }
                    .background(Color.Background.primary)
                    .tag(6)
                }
                .tabViewStyle(.page(indexDisplayMode: .never))
            }
            .background(Color.Background.primary)
            .navigationTitle("🔥 New IB Features")
            .navigationBarTitleDisplayMode(.inline)
            .toolbarBackground(Color.Background.primary, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        isAutoPlaying.toggle()
                    } label: {
                        Image(systemName: isAutoPlaying ? "pause.fill" : "play.fill")
                            .foregroundColor(.Brand.primary)
                    }
                }
            }
            .onReceive(timer) { _ in
                if isAutoPlaying {
                    withAnimation(.easeInOut(duration: 0.5)) {
                        selectedDemo = (selectedDemo + 1) % demos.count
                    }
                }
            }
            .onAppear {
                // Auto-start demo playback
                DispatchQueue.main.asyncAfter(deadline: .now() + 1) {
                    isAutoPlaying = true
                }
            }
        }
    }
}

#Preview {
    DemoShowcaseView()
}
