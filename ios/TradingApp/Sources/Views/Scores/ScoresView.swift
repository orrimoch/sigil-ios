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
                if viewModel.isLoading && viewModel.filteredStocks.isEmpty {
                    Spacer()
                    ProgressView()
                        .tint(.Brand.primary)
                    Text("Loading scores...")
                        .font(.caption)
                        .foregroundColor(.Text.tertiary)
                        .padding(.top, 8)
                    Spacer()
                } else if viewModel.filteredStocks.isEmpty {
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
                placement: .navigationBarDrawer(displayMode: .always),
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
                    .foregroundColor(.Text.tertiary)
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
    var color: Color = .Brand.primary
    let action: () -> Void
    
    var body: some View {
        Button(action: action) {
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
            .frame(width: 100, alignment: .leading)
            
            Spacer()
            
            // Score badge
            Text("\(stock.score)")
                .font(.headline.monospacedDigit())
                .foregroundColor(.white)
                .frame(width: 44)
                .padding(.vertical, 6)
                .background(stock.signalColor)
                .cornerRadius(6)
            
            // Rank
            Text("#\(stock.rank)")
                .font(.caption)
                .foregroundColor(.Text.tertiary)
                .frame(width: 40)
            
            Spacer()
            
            // Price and change
            VStack(alignment: .trailing, spacing: 2) {
                Text(stock.formattedPrice)
                    .font(.subheadline.monospacedDigit())
                    .foregroundColor(.Text.primary)
                
                Text(stock.formattedChange)
                    .font(.caption.monospacedDigit())
                    .foregroundColor(stock.isPositive ? .Signal.positive : .Signal.negative)
            }
            .frame(width: 80, alignment: .trailing)
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
