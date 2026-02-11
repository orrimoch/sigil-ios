import Foundation
import SwiftUI

/// ViewModel for login / register UI.
@MainActor
final class AuthViewModel: ObservableObject {

    @Published var isLoggedIn: Bool = false
    @Published var isLoading: Bool = false
    @Published var errorMessage: String?

    private let authService = AuthService.shared

    init() {
        // Mirror the service's auth state
        isLoggedIn = authService.isLoggedIn

        // Keep in sync with AuthService (Combine pipeline)
        authService.$isLoggedIn
            .receive(on: RunLoop.main)
            .assign(to: &$isLoggedIn)
    }

    // MARK: - Actions

    func login(email: String, password: String) {
        guard !email.isEmpty, !password.isEmpty else {
            errorMessage = "Please enter your email and password."
            return
        }

        isLoading = true
        errorMessage = nil

        Task {
            do {
                try await authService.login(email: email, password: password)
                
                // Pre-warm risk cache once per day (first login of the day)
                warmRiskCacheIfNeeded()
            } catch {
                errorMessage = error.localizedDescription
            }
            isLoading = false
        }
    }
    
    // MARK: - Daily Risk Cache Warming
    
    private static let lastWarmDateKey = "riskCacheLastWarmDate"
    
    /// Warm risk cache once per day (first app open of the day)
    func warmRiskCacheIfNeeded() {
        let today = Calendar.current.startOfDay(for: Date())
        let lastWarm = UserDefaults.standard.object(forKey: Self.lastWarmDateKey) as? Date
        
        // Skip if already warmed today
        if let lastWarm = lastWarm, Calendar.current.isDate(lastWarm, inSameDayAs: today) {
            print("Risk cache already warmed today, skipping")
            return
        }
        
        // Warm cache in background
        Task.detached(priority: .background) {
            do {
                let result = try await APIService.shared.warmRiskCache()
                print("Risk cache warmed: \(result.data.analyzed) analyzed, \(result.data.alreadyCached) cached")
                
                // Mark today as warmed
                await MainActor.run {
                    UserDefaults.standard.set(Date(), forKey: Self.lastWarmDateKey)
                }
            } catch {
                print("Risk cache warming failed (non-critical): \(error)")
            }
        }
    }

    func register(email: String, password: String, fullName: String) {
        guard !email.isEmpty, !password.isEmpty, !fullName.isEmpty else {
            errorMessage = "Please fill in all fields."
            return
        }
        guard password.count >= 8 else {
            errorMessage = "Password must be at least 8 characters."
            return
        }

        isLoading = true
        errorMessage = nil

        Task {
            do {
                try await authService.register(email: email, password: password, fullName: fullName)
            } catch {
                errorMessage = error.localizedDescription
            }
            isLoading = false
        }
    }

    func logout() {
        authService.logout()
    }

    // MARK: - Password Reset

    @Published var resetCode: String?
    @Published var resetSuccess: Bool = false

    func requestPasswordReset(email: String) {
        guard !email.isEmpty else {
            errorMessage = "Please enter your email."
            return
        }

        isLoading = true
        errorMessage = nil

        Task {
            do {
                let code = try await authService.requestPasswordReset(email: email)
                resetCode = code  // DEV: shown in-app for testing
            } catch {
                errorMessage = error.localizedDescription
            }
            isLoading = false
        }
    }

    func confirmPasswordReset(email: String, code: String, newPassword: String) {
        guard !code.isEmpty, !newPassword.isEmpty else {
            errorMessage = "Please fill in all fields."
            return
        }
        guard newPassword.count >= 8 else {
            errorMessage = "Password must be at least 8 characters."
            return
        }

        isLoading = true
        errorMessage = nil

        Task {
            do {
                try await authService.confirmPasswordReset(email: email, code: code, newPassword: newPassword)
                resetSuccess = true
            } catch {
                errorMessage = error.localizedDescription
            }
            isLoading = false
        }
    }
}
