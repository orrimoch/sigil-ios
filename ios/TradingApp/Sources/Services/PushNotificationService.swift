import Foundation
import UIKit
import UserNotifications

/// Manages push notification registration and device token handling.
/// Sends device token to backend for remote push delivery.
///
/// This service handles REMOTE push notifications (APNs).
/// For LOCAL notifications (trade confirmations, score alerts), see NotificationService.
final class PushNotificationService {
    static let shared = PushNotificationService()

    private(set) var deviceToken: String?
    private let baseURL = "http://127.0.0.1:8000/api/v1"

    private init() {}

    // MARK: - Registration

    /// Request push notification permission and register for remote notifications.
    func requestPushAuthorization() async -> Bool {
        let center = UNUserNotificationCenter.current()
        do {
            let granted = try await center.requestAuthorization(options: [.alert, .badge, .sound])
            if granted {
                await MainActor.run {
                    UIApplication.shared.registerForRemoteNotifications()
                }
            }
            return granted
        } catch {
            #if DEBUG
            print("[Push] Authorization failed: \(error)")
            #endif
            return false
        }
    }

    /// Called when APNs returns a device token.
    func didRegisterForRemoteNotifications(deviceToken: Data) {
        let token = deviceToken.map { String(format: "%02.2hhx", $0) }.joined()
        self.deviceToken = token

        #if DEBUG
        print("[Push] Device token: \(token)")
        #endif

        // Send token to backend
        Task {
            await registerTokenWithBackend(token: token)
        }
    }

    /// Called when APNs registration fails.
    func didFailToRegisterForRemoteNotifications(error: Error) {
        #if DEBUG
        print("[Push] Registration failed: \(error.localizedDescription)")
        print("[Push] This is expected on Simulator — push notifications require a real device")
        #endif
    }

    // MARK: - Backend Registration

    private func registerTokenWithBackend(token: String) async {
        guard let url = URL(string: "\(baseURL)/notifications/register-token") else { return }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        // Add auth token if available
        if let authToken = KeychainHelper.shared.loadString(key: "auth_token") {
            request.setValue("Bearer \(authToken)", forHTTPHeaderField: "Authorization")
        }

        let body: [String: String] = [
            "device_token": token,
            "platform": "ios"
        ]

        request.httpBody = try? JSONSerialization.data(withJSONObject: body)

        do {
            let (_, response) = try await URLSession.shared.data(for: request)
            if let http = response as? HTTPURLResponse {
                #if DEBUG
                print("[Push] Token registered with backend: \(http.statusCode)")
                #endif
            }
        } catch {
            #if DEBUG
            print("[Push] Failed to register token: \(error)")
            #endif
        }
    }

    /// Unregister token (on logout)
    func unregisterToken() async {
        guard let token = deviceToken,
              let url = URL(string: "\(baseURL)/notifications/unregister-token?device_token=\(token)") else { return }

        var request = URLRequest(url: url)
        request.httpMethod = "DELETE"

        do {
            let _ = try await URLSession.shared.data(for: request)
            deviceToken = nil
        } catch {
            #if DEBUG
            print("[Push] Failed to unregister: \(error)")
            #endif
        }
    }
}
