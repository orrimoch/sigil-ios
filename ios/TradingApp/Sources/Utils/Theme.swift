import SwiftUI

// MARK: - Institutional Dark Color Palette
// Bloomberg/IBKR inspired, NOT neon fintech

extension Color {
    
    // MARK: - Brand Colors
    
    struct Brand {
        /// Primary brand color - gold
        static let primary = Color(hex: "FFB800")
        
        /// Secondary brand color - muted teal
        static let secondary = Color(hex: "2D8B8B")
        
        /// Accent color for highlights
        static let accent = Color(hex: "FFB800")
    }
    
    // MARK: - Background Colors
    
    struct Background {
        /// Primary background - true carbon black
        static let primary = Color(hex: "0D0D0F")
        
        /// Secondary background - slightly lighter
        static let secondary = Color(hex: "1A1D23")
        
        /// Tertiary background - for cards/elevated surfaces
        static let tertiary = Color(hex: "252A33")
        
        /// Surface color for interactive elements
        static let surface = Color(hex: "2F3640")
        
        /// Card background
        static let card = Color(hex: "1E2229")
    }
    
    // MARK: - Text Colors
    
    struct Text {
        /// Primary text - high contrast
        static let primary = Color(hex: "F5F5F7")
        
        /// Secondary text - medium contrast
        static let secondary = Color(hex: "8E8E93")
        
        /// Tertiary text - meets WCAG 4.5:1
        static let tertiary = Color(hex: "7C7C82")
        
        /// Inverse text - for light backgrounds
        static let inverse = Color(hex: "121418")
    }
    
    // MARK: - Signal Colors
    
    struct Signal {
        /// Buy signal - green
        static let buy = Color(hex: "00C853")
        
        /// Sell signal - red
        static let sell = Color(hex: "FF5252")
        
        /// Hold signal - amber
        static let hold = Color(hex: "FFB300")
        
        /// Warning signal - orange (between hold and sell)
        static let warning = Color(hex: "FF9800")
        
        /// Positive change
        static let positive = Color(hex: "00C853")
        
        /// Negative change
        static let negative = Color(hex: "FF5252")
        
        /// Neutral/unchanged
        static let neutral = Color(hex: "8E8E93")
    }
    
    // MARK: - Chart Colors
    
    struct Chart {
        /// Primary line color
        static let line = Color(hex: "0066CC")
        
        /// Volume bars
        static let volume = Color(hex: "3D4654")
        
        /// Grid lines
        static let grid = Color(hex: "2F3640")
        
        /// Crosshair
        static let crosshair = Color(hex: "8E8E93")
    }
    
    // MARK: - Accent Colors
    
    struct Accent {
        /// Gold accent
        static let gold = Color(hex: "FFB800")
    }
    
    // MARK: - Border Colors
    
    struct Border {
        /// Primary border
        static let primary = Color(hex: "3D4654")
    }
    
    // MARK: - Utility
    
    struct Utility {
        /// Divider/separator
        static let divider = Color(hex: "2F3640")
        
        /// Border color
        static let border = Color(hex: "3D4654")
        
        /// Disabled state
        static let disabled = Color(hex: "5E5E63")
        
        /// Error state
        static let error = Color(hex: "FF5252")
        
        /// Warning state
        static let warning = Color(hex: "FFB300")
        
        /// Success state
        static let success = Color(hex: "00C853")
    }
}

// MARK: - Hex Color Extension

extension Color {
    init(hex: String) {
        let hex = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        var int: UInt64 = 0
        Scanner(string: hex).scanHexInt64(&int)
        let a, r, g, b: UInt64
        switch hex.count {
        case 3: // RGB (12-bit)
            (a, r, g, b) = (255, (int >> 8) * 17, (int >> 4 & 0xF) * 17, (int & 0xF) * 17)
        case 6: // RGB (24-bit)
            (a, r, g, b) = (255, int >> 16, int >> 8 & 0xFF, int & 0xFF)
        case 8: // ARGB (32-bit)
            (a, r, g, b) = (int >> 24, int >> 16 & 0xFF, int >> 8 & 0xFF, int & 0xFF)
        default:
            (a, r, g, b) = (255, 0, 0, 0)
        }
        self.init(
            .sRGB,
            red: Double(r) / 255,
            green: Double(g) / 255,
            blue: Double(b) / 255,
            opacity: Double(a) / 255
        )
    }
}

// MARK: - Button Styles

struct PrimaryButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.headline)
            .foregroundColor(Color.Background.primary)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 16)
            .background(Color.Brand.primary)
            .cornerRadius(12)
            .opacity(configuration.isPressed ? 0.85 : 1.0)
            .scaleEffect(configuration.isPressed ? 0.98 : 1.0)
            .animation(.easeInOut(duration: 0.15), value: configuration.isPressed)
    }
}

struct SecondaryButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.headline)
            .foregroundColor(.Brand.primary)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 16)
            .background(Color.Background.secondary)
            .cornerRadius(12)
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(Color.Brand.primary, lineWidth: 1)
            )
            .opacity(configuration.isPressed ? 0.85 : 1.0)
            .scaleEffect(configuration.isPressed ? 0.98 : 1.0)
            .animation(.easeInOut(duration: 0.15), value: configuration.isPressed)
    }
}

// MARK: - Additional Button Styles

struct DestructiveButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.headline)
            .foregroundColor(.white)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 16)
            .background(Color.Signal.sell)
            .cornerRadius(12)
            .opacity(configuration.isPressed ? 0.85 : 1.0)
            .scaleEffect(configuration.isPressed ? 0.98 : 1.0)
            .animation(.easeInOut(duration: 0.15), value: configuration.isPressed)
    }
}

struct BuyButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.headline)
            .foregroundColor(.white)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 16)
            .background(Color.Signal.buy)
            .cornerRadius(12)
            .opacity(configuration.isPressed ? 0.85 : 1.0)
            .scaleEffect(configuration.isPressed ? 0.98 : 1.0)
            .animation(.easeInOut(duration: 0.15), value: configuration.isPressed)
    }
}

struct SellButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.headline)
            .foregroundColor(.Signal.sell)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 16)
            .background(Color.clear)
            .cornerRadius(12)
            .overlay(RoundedRectangle(cornerRadius: 12).stroke(Color.Signal.sell, lineWidth: 2))
            .opacity(configuration.isPressed ? 0.85 : 1.0)
            .scaleEffect(configuration.isPressed ? 0.98 : 1.0)
            .animation(.easeInOut(duration: 0.15), value: configuration.isPressed)
    }
}

// MARK: - Card Style

struct CardStyle: ViewModifier {
    var padding: CGFloat = 16
    var cornerRadius: CGFloat = 12
    func body(content: Content) -> some View {
        content
            .padding(padding)
            .background(Color.Background.secondary)
            .cornerRadius(cornerRadius)
    }
}

extension View {
    func card(padding: CGFloat = 16, radius: CGFloat = 12) -> some View {
        modifier(CardStyle(padding: padding, cornerRadius: radius))
    }
}

// MARK: - Typography

extension Font {
    /// Large title for main headings
    static let displayLarge = Font.system(size: 32, weight: .bold, design: .default)
    
    /// Medium title
    static let displayMedium = Font.system(size: 24, weight: .semibold, design: .default)
    
    /// Monospace for numbers/prices
    static let mono = Font.system(size: 16, weight: .medium, design: .monospaced)
    
    /// Large monospace for portfolio value
    static let monoLarge = Font.system(size: 32, weight: .bold, design: .monospaced)
    
    /// Price display
    static let price = Font.system(size: 28, weight: .bold, design: .monospaced)
    
    /// Table header
    static let tableHeader = Font.system(size: 12, weight: .semibold, design: .default)
    
    /// Table data
    static let tableData = Font.system(size: 14, weight: .regular, design: .default)
}

// MARK: - Currency Formatting

extension Double {
    /// Format as currency with commas: $100,000.00
    var asCurrency: String {
        let formatter = NumberFormatter()
        formatter.numberStyle = .currency
        formatter.currencyCode = "USD"
        formatter.maximumFractionDigits = 2
        formatter.minimumFractionDigits = 2
        return formatter.string(from: NSNumber(value: self)) ?? "$\(String(format: "%.2f", self))"
    }
    
    /// Format as signed currency: +$1,234.56 or -$567.89
    var asSignedCurrency: String {
        let formatted = abs(self).asCurrency
        return self >= 0 ? "+\(formatted)" : "-\(formatted)"
    }
}

// MARK: - Shimmer Animation

struct ShimmerEffect: ViewModifier {
    @State private var phase: CGFloat = 0
    
    func body(content: Content) -> some View {
        content
            .overlay(
                GeometryReader { geo in
                    LinearGradient(
                        colors: [
                            Color.clear,
                            Color.white.opacity(0.12),
                            Color.clear
                        ],
                        startPoint: .leading,
                        endPoint: .trailing
                    )
                    .frame(width: geo.size.width * 2)
                    .offset(x: -geo.size.width + phase * geo.size.width * 3)
                }
                .clipped()
            )
            .onAppear {
                withAnimation(.linear(duration: 1.5).repeatForever(autoreverses: false)) {
                    phase = 1
                }
            }
    }
}

extension View {
    func shimmer() -> some View {
        modifier(ShimmerEffect())
    }
}
