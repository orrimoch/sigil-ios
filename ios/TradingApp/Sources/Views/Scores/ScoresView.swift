import SwiftUI

/// F5.x: Scores Tab
/// Sortable list of all stocks with scores and signals
struct ScoresView: View {
    @StateObject private var viewModel = ScoresViewModel()
    @State private var showSectorPicker = false
    
    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                // Filter bar
                FilterBar(viewModel: viewModel, showSectorPicker: $showSectorPicker)
                
                // Stock list
                if viewModel.isLoading && viewModel.filteredStocks.isEmpty && viewModel.errorMessage == nil {
                    // Skeleton loading state
                    VStack(spacing: 0) {
                        ForEach(0..<8, id: \.self) { _ in
                            HStack {
                                VStack(alignment: .leading, spacing: 4) {
                                    RoundedRectangle(cornerRadius: 4)
                                        .fill(Color.Background.tertiary)
                                        .frame(width: 60, height: 16)
                                    RoundedRectangle(cornerRadius: 4)
                                        .fill(Color.Background.tertiary)
                                        .frame(width: 100, height: 12)
                                }
                                Spacer()
                                RoundedRectangle(cornerRadius: 4)
                                    .fill(Color.Background.tertiary)
                                    .frame(width: 44, height: 28)
                                    .cornerRadius(6)
                                VStack(alignment: .trailing, spacing: 4) {
                                    RoundedRectangle(cornerRadius: 4)
                                        .fill(Color.Background.tertiary)
                                        .frame(width: 70, height: 16)
                                    RoundedRectangle(cornerRadius: 4)
                                        .fill(Color.Background.tertiary)
                                        .frame(width: 50, height: 12)
                                }
                            }
                            .padding(.horizontal)
                            .padding(.vertical, 12)
                            Divider().background(Color.Utility.divider)
                        }
                    }
                    .shimmer()
                } else if let error = viewModel.errorMessage, viewModel.stocks.isEmpty {
                    ErrorStateView(
                        title: "Something went wrong",
                        message: error,
                        retryAction: {
                            Task { await viewModel.loadData() }
                        }
                    )
                } else if viewModel.filteredStocks.isEmpty {
                    // Show recent searches if search is active and text is empty
                    if viewModel.searchText.isEmpty && !viewModel.recentSearches.isEmpty {
                        RecentSearchesView(viewModel: viewModel)
                    }
                    Spacer()
                    VStack(spacing: 12) {
                        Image(systemName: "magnifyingglass")
                            .font(.largeTitle)
                            .foregroundColor(.Text.tertiary)
                        Text("No stocks found")
                            .font(.headline)
                            .foregroundColor(.Text.secondary)
                        Text("Try adjusting your filters")
                            .font(.caption)
                            .foregroundColor(.Text.tertiary)
                        
                        // Clear Filters button
                        if viewModel.selectedSignal != nil || viewModel.selectedSector != nil || !viewModel.searchText.isEmpty {
                            Button {
                                viewModel.setSignalFilter(nil)
                                viewModel.setSectorFilter(nil)
                                viewModel.searchText = ""
                                viewModel.applyFilters()
                            } label: {
                                Text("Clear Filters")
                                    .font(.subheadline.bold())
                                    .foregroundColor(.Accent.gold)
                                    .padding(.horizontal, 16)
                                    .padding(.vertical, 8)
                                    .background(Color.Accent.gold.opacity(0.15))
                                    .cornerRadius(8)
                            }
                            .padding(.top, 4)
                        }
                    }
                    Spacer()
                } else {
                    List {
                        ForEach(viewModel.filteredStocks) { stock in
                            NavigationLink {
                                StockDetailView(ticker: stock.ticker)
                            } label: {
                                StockScoreRow(stock: stock)
                            }
                            .swipeActions(edge: .trailing) {
                                NavigationLink {
                                    StockDetailView(ticker: stock.ticker)
                                } label: {
                                    Label("Trade", systemImage: "arrow.left.arrow.right")
                                }
                                .tint(.Signal.buy)
                            }
                            .swipeActions(edge: .leading) {
                                Button {
                                    WatchlistService.shared.toggleWatchlist(stock.ticker)
                                } label: {
                                    Label("Watch", systemImage: "bell")
                                }
                                .tint(.Accent.gold)
                            }
                            .listRowBackground(Color.Background.primary)
                            .listRowSeparatorTint(Color.Utility.divider)
                        }
                    }
                    .listStyle(.plain)
                    .scrollContentBackground(.hidden)
                }
            }
            .background(Color.Background.primary)
            .navigationTitle("Scores")
            .navigationBarTitleDisplayMode(.large)
            .toolbarBackground(Color.Background.primary, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .searchable(
                text: $viewModel.searchText,
                placement: .navigationBarDrawer(displayMode: .automatic),
                prompt: "Search ticker or company"
            )
            .onSubmit(of: .search) {
                viewModel.addToRecentSearches(viewModel.searchText)
            }
            .onChange(of: viewModel.searchText) { _, newValue in
                viewModel.applyFilters()
            }
            .refreshable {
                await viewModel.loadData()
            }
            .task {
                await viewModel.loadData()
            }
            .sheet(isPresented: $showSectorPicker) {
                SectorPickerSheet(
                    sectors: viewModel.availableSectors,
                    selected: viewModel.selectedSector,
                    onSelect: { sector in
                        viewModel.setSectorFilter(sector)
                        showSectorPicker = false
                    }
                )
                .presentationDetents([.medium])
            }
        }
    }
}

// MARK: - Filter Bar

struct FilterBar: View {
    @ObservedObject var viewModel: ScoresViewModel
    @Binding var showSectorPicker: Bool
    
    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                // Signal filters
                FilterChip(title: "All", isSelected: viewModel.selectedSignal == nil) {
                    viewModel.setSignalFilter(nil)
                }
                FilterChip(title: "BUY", isSelected: viewModel.selectedSignal == "BUY", color: .Signal.buy) {
                    viewModel.setSignalFilter("BUY")
                }
                FilterChip(title: "HOLD", isSelected: viewModel.selectedSignal == "HOLD", color: .Signal.hold) {
                    viewModel.setSignalFilter("HOLD")
                }
                FilterChip(title: "SELL", isSelected: viewModel.selectedSignal == "SELL", color: .Signal.sell) {
                    viewModel.setSignalFilter("SELL")
                }
                
                Divider()
                    .frame(height: 20)
                
                // Sector filter
                Button {
                    showSectorPicker = true
                } label: {
                    HStack(spacing: 4) {
                        Text(viewModel.selectedSector ?? "Sector")
                        Image(systemName: "chevron.down")
                    }
                    .font(.caption)
                    .foregroundColor(viewModel.selectedSector != nil ? .white : .Text.secondary)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 6)
                    .background(viewModel.selectedSector != nil ? Color.Brand.primary : Color.Background.tertiary)
                    .cornerRadius(8)
                }
                
                Divider()
                    .frame(height: 20)
                
                // Sort menu
                Menu {
                    ForEach(ScoresViewModel.SortOrder.allCases, id: \.self) { order in
                        Button {
                            viewModel.setSortOrder(order)
                        } label: {
                            HStack {
                                Text(order.rawValue)
                                if viewModel.sortOrder == order {
                                    Image(systemName: "checkmark")
                                }
                            }
                        }
                    }
                } label: {
                    HStack(spacing: 4) {
                        Image(systemName: "arrow.up.arrow.down")
                        Text(viewModel.sortOrder.rawValue)
                    }
                    .font(.caption)
                    .foregroundColor(.Text.secondary)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 6)
                    .background(Color.Background.tertiary)
                    .cornerRadius(8)
                }
                
                // Results count
                Text("\(viewModel.filteredStocks.count) stocks")
                    .font(.caption)
                    .foregroundColor(.Text.secondary)
                    .padding(.leading, 8)
            }
            .padding(.horizontal)
            .padding(.vertical, 8)
        }
        .background(Color.Background.secondary)
    }
}

// MARK: - Filter Chip

struct FilterChip: View {
    let title: String
    let isSelected: Bool
    var color: Color = .Accent.gold
    let action: () -> Void
    
    var body: some View {
        Button {
            UIImpactFeedbackGenerator(style: .light).impactOccurred()
            action()
        } label: {
            Text(title)
                .font(.caption.bold())
                .foregroundColor(isSelected ? .white : .Text.secondary)
                .padding(.horizontal, 12)
                .padding(.vertical, 6)
                .background(isSelected ? color : Color.Background.tertiary)
                .cornerRadius(8)
        }
    }
}

// MARK: - Stock Score Row

struct StockScoreRow: View {
    let stock: StockScoreItem
    
    var body: some View {
        HStack(spacing: 12) {
            // Ticker and name
            VStack(alignment: .leading, spacing: 2) {
                Text(stock.ticker)
                    .font(.headline)
                    .foregroundColor(.Text.primary)
                
                Text(stock.name.isEmpty ? stock.sector : stock.name)
                    .font(.caption)
                    .foregroundColor(.Text.secondary)
                    .lineLimit(1)
            }
            
            Spacer()
            
            // Score badge
            Text("\(stock.score)")
                .font(.headline.monospacedDigit())
                .foregroundColor(.white)
                .frame(width: 44)
                .padding(.vertical, 6)
                .background(stock.signalColor)
                .cornerRadius(6)
            
            // Price and change
            VStack(alignment: .trailing, spacing: 2) {
                Text(stock.formattedPrice)
                    .font(.subheadline.monospacedDigit())
                    .foregroundColor(.Text.primary)
                
                Text(stock.formattedChange)
                    .font(.caption.monospacedDigit())
                    .foregroundColor(stock.isPositive ? .Signal.positive : .Signal.negative)
            }
        }
        .padding(.vertical, 4)
    }
}

// MARK: - Sector Picker Sheet

struct SectorPickerSheet: View {
    let sectors: [String]
    let selected: String?
    let onSelect: (String?) -> Void
    
    var body: some View {
        NavigationStack {
            List {
                Button {
                    onSelect(nil)
                } label: {
                    HStack {
                        Text("All Sectors")
                            .foregroundColor(.Text.primary)
                        Spacer()
                        if selected == nil {
                            Image(systemName: "checkmark")
                                .foregroundColor(.Brand.primary)
                        }
                    }
                }
                .listRowBackground(Color.Background.secondary)
                
                ForEach(sectors, id: \.self) { sector in
                    Button {
                        onSelect(sector)
                    } label: {
                        HStack {
                            Text(sector)
                                .foregroundColor(.Text.primary)
                            Spacer()
                            if selected == sector {
                                Image(systemName: "checkmark")
                                    .foregroundColor(.Brand.primary)
                            }
                        }
                    }
                    .listRowBackground(Color.Background.secondary)
                }
            }
            .listStyle(.insetGrouped)
            .scrollContentBackground(.hidden)
            .background(Color.Background.primary)
            .navigationTitle("Select Sector")
            .navigationBarTitleDisplayMode(.inline)
        }
    }
}

// MARK: - Recent Searches (F5.2)

struct RecentSearchesView: View {
    @ObservedObject var viewModel: ScoresViewModel
    
    var body: some View {
        if !viewModel.recentSearches.isEmpty {
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Text("Recent Searches")
                        .font(.caption)
                        .foregroundColor(.Text.secondary)
                    
                    Spacer()
                    
                    Button("Clear") {
                        viewModel.clearRecentSearches()
                    }
                    .font(.caption)
                    .foregroundColor(.Brand.primary)
                }
                
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        ForEach(viewModel.recentSearches, id: \.self) { search in
                            Button {
                                viewModel.search(search)
                            } label: {
                                Text(search)
                                    .font(.caption)
                                    .foregroundColor(.Text.primary)
                                    .padding(.horizontal, 12)
                                    .padding(.vertical, 6)
                                    .background(Color.Background.tertiary)
                                    .cornerRadius(8)
                            }
                        }
                    }
                }
            }
            .padding()
            .background(Color.Background.secondary)
        }
    }
}

// MARK: - Preview

#Preview {
    ScoresView()
        .environmentObject(AppState())
}
