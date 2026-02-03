import Foundation
import LocalAuthentication

/// Manages app lock state — biometric (Face ID/Touch ID) primary, PIN fallback
@MainActor
class AppLockManager: ObservableObject {
    static let shared = AppLockManager()
    
    // MARK: - Published State
    @Published var isLocked: Bool = true
    @Published var isSetUp: Bool = false
    @Published var biometricType: BiometricType = .none
    
    enum BiometricType {
        case none, touchID, faceID
        
        var label: String {
            switch self {
            case .none: return "Biometric"
            case .touchID: return "Touch ID"
            case .faceID: return "Face ID"
            }
        }
        
        var icon: String {
            switch self {
            case .none: return "lock.fill"
            case .touchID: return "touchid"
            case .faceID: return "faceid"
            }
        }
    }
    
    // MARK: - Keys
    private let pinKey = "sigil_pin_code"
    private let setupKey = "sigil_lock_setup"
    
    // MARK: - Init
    init() {
        self.isSetUp = UserDefaults.standard.bool(forKey: setupKey)
        self.isLocked = isSetUp // Lock on launch if set up
        self.biometricType = detectBiometricType()
    }
    
    // MARK: - Biometric Detection
    
    func detectBiometricType() -> BiometricType {
        let context = LAContext()
        var error: NSError?
        
        guard context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &error) else {
            return .none
        }
        
        switch context.biometryType {
        case .faceID: return .faceID
        case .touchID: return .touchID
        default: return .none
        }
    }
    
    // MARK: - PIN Management
    
    func setPin(_ pin: String) {
        let _ = KeychainHelper.shared.save(key: pinKey, string: pin)
        UserDefaults.standard.set(true, forKey: setupKey)
        isSetUp = true
        isLocked = false
    }
    
    func verifyPin(_ pin: String) -> Bool {
        guard let storedPin = KeychainHelper.shared.loadString(key: pinKey) else { return false }
        return pin == storedPin
    }
    
    func resetLock() {
        KeychainHelper.shared.delete(key: pinKey)
        UserDefaults.standard.set(false, forKey: setupKey)
        isSetUp = false
        isLocked = false
    }
    
    // MARK: - Biometric Auth
    
    func authenticateWithBiometric() async -> Bool {
        let context = LAContext()
        context.localizedCancelTitle = "Use PIN"
        
        var error: NSError?
        guard context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &error) else {
            return false
        }
        
        do {
            let success = try await context.evaluatePolicy(
                .deviceOwnerAuthenticationWithBiometrics,
                localizedReason: "Unlock Sigil"
            )
            if success {
                isLocked = false
            }
            return success
        } catch {
            return false
        }
    }
    
    // MARK: - Unlock
    
    func unlock(withPin pin: String) -> Bool {
        if verifyPin(pin) {
            isLocked = false
            return true
        }
        return false
    }
    
    func lock() {
        if isSetUp {
            isLocked = true
        }
    }
}
