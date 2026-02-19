import Foundation

/// F4.3: Market Hours Service
/// Determines NYSE/NASDAQ market status based on current time
/// Regular hours: 9:30 AM - 4:00 PM ET
/// Pre-market: 4:00 AM - 9:30 AM ET
/// After-hours: 4:00 PM - 8:00 PM ET
@MainActor
final class MarketHoursService: ObservableObject {
    static let shared = MarketHoursService()
    
    // MARK: - Published State
    
    @Published var status: MarketStatus = .closed
    @Published var statusText: String = "Market Closed"
    @Published var nextEventText: String = ""
    
    // MARK: - Market Status Enum
    
    enum MarketStatus: String {
        case preMarket = "pre_market"
        case open = "open"
        case afterHours = "after_hours"
        case closed = "closed"
        
        var displayName: String {
            switch self {
            case .preMarket: return "Pre-Market"
            case .open: return "Market Open"
            case .afterHours: return "After-Hours"
            case .closed: return "Market Closed"
            }
        }
        
        var color: String {
            switch self {
            case .preMarket: return "Signal.hold"
            case .open: return "Signal.buy"
            case .afterHours: return "Signal.hold"
            case .closed: return "Text.tertiary"
            }
        }
        
        var icon: String {
            switch self {
            case .preMarket: return "sunrise.fill"
            case .open: return "chart.line.uptrend.xyaxis"
            case .afterHours: return "moon.fill"
            case .closed: return "moon.zzz.fill"
            }
        }
    }
    
    // MARK: - Time Zone
    
    private let easternTimeZone: TimeZone
    private var updateTimer: Timer?
    
    // MARK: - Init
    
    private init() {
        // US Eastern Time (handles DST automatically)
        self.easternTimeZone = TimeZone(identifier: "America/New_York") ?? TimeZone.current
        updateStatus()
        startTimer()
    }
    
    deinit {
        updateTimer?.invalidate()
    }
    
    // MARK: - Timer
    
    private func startTimer() {
        // Update every minute
        updateTimer = Timer.scheduledTimer(withTimeInterval: 60, repeats: true) { [weak self] timer in
            guard let self = self else {
                timer.invalidate()
                return
            }
            Task { @MainActor [weak self] in
                self?.updateStatus()
            }
        }
    }
    
    // MARK: - Status Calculation
    
    func updateStatus() {
        let now = Date()
        let calendar = Calendar.current
        
        // Get current time in Eastern
        var easternCalendar = calendar
        easternCalendar.timeZone = easternTimeZone
        
        let components = easternCalendar.dateComponents([.hour, .minute, .weekday], from: now)
        guard let hour = components.hour,
              let minute = components.minute,
              let weekday = components.weekday else {
            status = .closed
            statusText = "Market Closed"
            nextEventText = ""
            return
        }
        
        // Weekend check (1 = Sunday, 7 = Saturday)
        let isWeekend = weekday == 1 || weekday == 7
        
        // Convert to minutes since midnight for easier comparison
        let currentMinutes = hour * 60 + minute
        
        // Market hours in minutes since midnight ET
        let preMarketOpen = 4 * 60      // 4:00 AM
        let regularOpen = 9 * 60 + 30   // 9:30 AM
        let regularClose = 16 * 60      // 4:00 PM
        let afterHoursClose = 20 * 60   // 8:00 PM
        
        // Check for US market holidays (simplified - major holidays only)
        if isUSMarketHoliday(date: now) || isWeekend {
            status = .closed
            statusText = isWeekend ? "Weekend" : "Holiday"
            nextEventText = formatNextOpen(from: now, calendar: easternCalendar)
            return
        }
        
        // Determine status based on time
        if currentMinutes < preMarketOpen {
            // Before 4:00 AM - closed
            status = .closed
            statusText = "Market Closed"
            nextEventText = "Pre-market opens at 4:00 AM ET"
        } else if currentMinutes < regularOpen {
            // 4:00 AM - 9:30 AM - pre-market
            status = .preMarket
            statusText = "Pre-Market"
            let minutesUntilOpen = regularOpen - currentMinutes
            nextEventText = "Opens in \(formatMinutes(minutesUntilOpen))"
        } else if currentMinutes < regularClose {
            // 9:30 AM - 4:00 PM - regular hours
            status = .open
            statusText = "Market Open"
            let minutesUntilClose = regularClose - currentMinutes
            nextEventText = "Closes in \(formatMinutes(minutesUntilClose))"
        } else if currentMinutes < afterHoursClose {
            // 4:00 PM - 8:00 PM - after-hours
            status = .afterHours
            statusText = "After-Hours"
            let minutesUntilClose = afterHoursClose - currentMinutes
            nextEventText = "Closes in \(formatMinutes(minutesUntilClose))"
        } else {
            // After 8:00 PM - closed
            status = .closed
            statusText = "Market Closed"
            nextEventText = "Opens tomorrow at 9:30 AM ET"
        }
    }
    
    // MARK: - Helpers
    
    private func formatMinutes(_ minutes: Int) -> String {
        if minutes < 60 {
            return "\(minutes)m"
        } else {
            let hours = minutes / 60
            let mins = minutes % 60
            if mins == 0 {
                return "\(hours)h"
            }
            return "\(hours)h \(mins)m"
        }
    }
    
    private func formatNextOpen(from date: Date, calendar: Calendar) -> String {
        // Find next weekday
        var nextDate = calendar.date(byAdding: .day, value: 1, to: date) ?? date
        var weekday = calendar.component(.weekday, from: nextDate)
        
        // Skip to Monday if needed
        while weekday == 1 || weekday == 7 {
            nextDate = calendar.date(byAdding: .day, value: 1, to: nextDate) ?? nextDate
            weekday = calendar.component(.weekday, from: nextDate)
        }
        
        let formatter = DateFormatter()
        formatter.timeZone = easternTimeZone
        formatter.dateFormat = "EEEE"
        let dayName = formatter.string(from: nextDate)
        
        return "Opens \(dayName) 9:30 AM ET"
    }
    
    private func isUSMarketHoliday(date: Date) -> Bool {
        // Simplified holiday check - major US market holidays
        // Full implementation would use a holiday calendar API
        let calendar = Calendar.current
        var easternCalendar = calendar
        easternCalendar.timeZone = easternTimeZone
        
        let components = easternCalendar.dateComponents([.month, .day], from: date)
        guard let month = components.month, let day = components.day else { return false }
        
        // Fixed-date holidays (simplified)
        let fixedHolidays: [(month: Int, day: Int)] = [
            (1, 1),   // New Year's Day
            (7, 4),   // Independence Day
            (12, 25), // Christmas
        ]
        
        for holiday in fixedHolidays {
            if month == holiday.month && day == holiday.day {
                return true
            }
        }
        
        return false
    }
    
    // MARK: - Public API
    
    /// Check if regular trading hours are active
    var isRegularHours: Bool {
        status == .open
    }
    
    /// Check if any trading is possible (pre-market, regular, or after-hours)
    var isTradingPossible: Bool {
        status == .preMarket || status == .open || status == .afterHours
    }
}
