import XCTest
@testable import Sigil

/// Unit tests for F11.2 Biometric Authentication
/// Tests biometric type detection, preference storage, fallback to PIN
@MainActor
final class BiometricAuthTests: XCTestCase {
    
    var lockManager: AppLockManager!
    
    override func setUp() async throws {
        lockManager = AppLockManager.shared
        // Reset state
        UserDefaults.standard.set(false, forKey: "sigil_lock_setup")
        UserDefaults.standard.set(false, forKey: "sigil_biometric_enabled")
        KeychainHelper.shared.delete(key: "sigil_pin_code")
    }
    
    override func tearDown() async throws {
        UserDefaults.standard.removeObject(forKey: "sigil_lock_setup")
        UserDefaults.standard.removeObject(forKey: "sigil_biometric_enabled")
        KeychainHelper.shared.delete(key: "sigil_pin_code")
    }
    
    // MARK: - Singleton Tests
    
    func testSharedInstanceExists() {
        XCTAssertNotNil(AppLockManager.shared)
    }
    
    func testSharedInstanceIsSingleton() {
        let a = AppLockManager.shared
        let b = AppLockManager.shared
        XCTAssertTrue(a === b)
    }
    
    // MARK: - Biometric Type Detection
    
    func testDetectBiometricTypeReturnsValidType() {
        let type = lockManager.detectBiometricType()
        // In simulator, may return .none — that's fine
        XCTAssertTrue(
            [AppLockManager.BiometricType.none, .faceID, .touchID].contains(type),
            "Should return a valid biometric type"
        )
    }
    
    func testBiometricTypeLabel() {
        XCTAssertEqual(AppLockManager.BiometricType.faceID.label, "Face ID")
        XCTAssertEqual(AppLockManager.BiometricType.touchID.label, "Touch ID")
        XCTAssertEqual(AppLockManager.BiometricType.none.label, "Biometric")
    }
    
    func testBiometricTypeIcon() {
        XCTAssertEqual(AppLockManager.BiometricType.faceID.icon, "faceid")
        XCTAssertEqual(AppLockManager.BiometricType.touchID.icon, "touchid")
        XCTAssertEqual(AppLockManager.BiometricType.none.icon, "lock.fill")
    }
    
    // MARK: - Biometric Preference Storage
    
    func testBiometricEnabledDefaultsFalse() {
        UserDefaults.standard.removeObject(forKey: "sigil_biometric_enabled")
        let enabled = UserDefaults.standard.bool(forKey: "sigil_biometric_enabled")
        XCTAssertFalse(enabled, "Biometric should be disabled by default")
    }
    
    func testSetBiometricEnabled() {
        lockManager.setBiometricEnabled(true)
        
        let stored = UserDefaults.standard.bool(forKey: "sigil_biometric_enabled")
        XCTAssertTrue(stored, "Should persist biometric preference to UserDefaults")
        XCTAssertTrue(lockManager.biometricEnabled)
    }
    
    func testSetBiometricDisabled() {
        lockManager.setBiometricEnabled(true)
        lockManager.setBiometricEnabled(false)
        
        let stored = UserDefaults.standard.bool(forKey: "sigil_biometric_enabled")
        XCTAssertFalse(stored)
        XCTAssertFalse(lockManager.biometricEnabled)
    }
    
    // MARK: - Auto-trigger Logic
    
    func testShouldAutoTriggerBiometricWhenNotSetUp() {
        lockManager.setBiometricEnabled(true)
        // Not set up yet — should not auto-trigger
        XCTAssertFalse(lockManager.shouldAutoTriggerBiometric,
                        "Should not auto-trigger when lock not set up")
    }
    
    func testShouldAutoTriggerBiometricWhenDisabled() {
        lockManager.setPin("123456")
        lockManager.setBiometricEnabled(false)
        
        XCTAssertFalse(lockManager.shouldAutoTriggerBiometric,
                        "Should not auto-trigger when biometric disabled")
    }
    
    // MARK: - PIN Fallback
    
    func testPinStillWorksWhenBiometricEnabled() {
        lockManager.setPin("654321")
        lockManager.setBiometricEnabled(true)
        
        // PIN should still verify
        XCTAssertTrue(lockManager.verifyPin("654321"))
        XCTAssertFalse(lockManager.verifyPin("000000"))
    }
    
    func testUnlockWithPinWhenBiometricEnabled() {
        lockManager.setPin("111111")
        lockManager.setBiometricEnabled(true)
        lockManager.lock()
        
        XCTAssertTrue(lockManager.isLocked)
        
        let result = lockManager.unlock(withPin: "111111")
        XCTAssertTrue(result)
        XCTAssertFalse(lockManager.isLocked)
    }
    
    // MARK: - Reset Clears Biometric
    
    func testResetLockClearsBiometric() {
        lockManager.setPin("123456")
        lockManager.setBiometricEnabled(true)
        
        lockManager.resetLock()
        
        XCTAssertFalse(lockManager.biometricEnabled, "Reset should disable biometric")
        XCTAssertFalse(lockManager.isSetUp)
        XCTAssertFalse(lockManager.isLocked)
    }
    
    // MARK: - PIN Setup Basics
    
    func testSetPin() {
        lockManager.setPin("123456")
        
        XCTAssertTrue(lockManager.isSetUp)
        XCTAssertFalse(lockManager.isLocked) // setPin unlocks
        XCTAssertTrue(lockManager.verifyPin("123456"))
    }
    
    func testVerifyWrongPin() {
        lockManager.setPin("123456")
        
        XCTAssertFalse(lockManager.verifyPin("000000"))
        XCTAssertFalse(lockManager.verifyPin(""))
        XCTAssertFalse(lockManager.verifyPin("12345")) // too short
    }
    
    func testLockAndUnlock() {
        lockManager.setPin("999999")
        lockManager.lock()
        
        XCTAssertTrue(lockManager.isLocked)
        
        _ = lockManager.unlock(withPin: "999999")
        XCTAssertFalse(lockManager.isLocked)
    }
}
