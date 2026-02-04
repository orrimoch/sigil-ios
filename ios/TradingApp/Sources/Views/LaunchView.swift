import SwiftUI

/// Splash screen showing the Sigil logo with a fade-in animation
struct LaunchView: View {
    @State private var opacity: Double = 0
    @State private var scale: CGFloat = 0.85
    @Binding var showLaunch: Bool
    
    var body: some View {
        ZStack {
            Color.Background.primary
                .ignoresSafeArea()
            
            VStack(spacing: 0) {
                Image("SigilLogo")
                    .resizable()
                    .scaledToFit()
                    .frame(maxWidth: 280)
                    .accessibilityLabel("Sigil - AI Market Intelligence")
            }
            .opacity(opacity)
            .scaleEffect(scale)
        }
        .onAppear {
            withAnimation(.easeOut(duration: 0.6)) {
                opacity = 1.0
                scale = 1.0
            }
            
            DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) {
                withAnimation(.easeInOut(duration: 0.5)) {
                    opacity = 0
                    scale = 1.02
                }
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.55) {
                    showLaunch = false
                }
            }
        }
    }
}

#Preview {
    LaunchView(showLaunch: .constant(true))
}
