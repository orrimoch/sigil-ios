import SwiftUI

/// Splash screen showing the Sigil logo with a fade-in animation
struct LaunchView: View {
    @State private var opacity: Double = 0
    @State private var scale: CGFloat = 0.85
    @Binding var showLaunch: Bool
    
    var body: some View {
        ZStack {
            Color(red: 13/255, green: 13/255, blue: 15/255)
                .ignoresSafeArea()
            
            VStack(spacing: 0) {
                Image("SigilLogo")
                    .resizable()
                    .scaledToFit()
                    .frame(maxWidth: 280)
            }
            .opacity(opacity)
            .scaleEffect(scale)
        }
        .onAppear {
            withAnimation(.easeOut(duration: 0.8)) {
                opacity = 1.0
                scale = 1.0
            }
            
            DispatchQueue.main.asyncAfter(deadline: .now() + 2.0) {
                withAnimation(.easeIn(duration: 0.3)) {
                    opacity = 0
                }
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.35) {
                    showLaunch = false
                }
            }
        }
    }
}

#Preview {
    LaunchView(showLaunch: .constant(true))
}
