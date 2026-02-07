<img src="../docs/sigil_logo.jpg" alt="Sigil" width="240" />

# iOS App Distribution Guide

**Last Updated:** February 7, 2026  
**Purpose:** Package Sigil for installation on real iPhones/iPads for testing

---

## Overview

There are 3 ways to install an iOS app on real devices:

| Method | Best For | Max Devices | Difficulty |
|--------|----------|-------------|------------|
| **Xcode Direct** | Single developer device | 1 | Easy |
| **TestFlight** | Beta testing team | 10,000 | Medium |
| **App Store** | Public release | Unlimited | Hard |

**Recommended: TestFlight** — Industry standard for beta testing. Easy to install, automatic updates, crash reports.

---

## Prerequisites

### 1. Apple Developer Account

You need a paid Apple Developer account ($99/year).

- Sign up: https://developer.apple.com/programs/
- Takes 24-48 hours for approval
- Provides access to App Store Connect and TestFlight

### 2. Xcode Setup

Ensure Xcode is configured with your Apple ID:

```
Xcode → Settings → Accounts → Add Apple ID
```

### 3. Bundle Identifier

Sigil uses: `com.sigil.ios`

This must be unique and registered in your Apple Developer account.

---

## Method 1: Xcode Direct Install (Fastest for Single Device)

Best for: Quick testing on your own device.

### Step 1: Connect Your Device

1. Connect iPhone/iPad via USB cable
2. Trust the computer on the device
3. In Xcode: Window → Devices and Simulators → Verify device appears

### Step 2: Select Your Device as Target

1. Open `TradingApp.xcodeproj`
2. In the scheme selector (top bar), choose your connected device instead of Simulator

### Step 3: Configure Signing

1. Select the project in Navigator
2. Go to **Signing & Capabilities** tab
3. Check **Automatically manage signing**
4. Select your Team (Apple Developer account)

### Step 4: Build and Run

```bash
# Or just press Cmd+R in Xcode
xcodebuild -project ios/TradingApp/TradingApp.xcodeproj \
  -scheme TradingApp \
  -destination 'id=<YOUR_DEVICE_UDID>' \
  build
```

The app will install and launch on your device.

**Limitation:** Only works while device is connected or for 7 days (free account) / indefinitely (paid account).

---

## Method 2: TestFlight Distribution (Recommended)

Best for: Team testing, beta users, real-world testing.

### Step 1: Create App in App Store Connect

1. Go to https://appstoreconnect.apple.com
2. Click **My Apps** → **+** → **New App**
3. Fill in:
   - Platform: iOS
   - Name: Sigil
   - Primary Language: English
   - Bundle ID: com.sigil.ios
   - SKU: sigil-ios-001 (any unique identifier)

### Step 2: Configure App Information

In App Store Connect, fill in required fields:
- Privacy Policy URL (required for financial apps)
- App Category: Finance
- Age Rating: 17+ (financial trading)

### Step 3: Archive the App in Xcode

1. Select **Any iOS Device (arm64)** as build target
2. Set version number:
   ```
   Project → General → Version: 1.0.0
   Project → General → Build: 1
   ```
3. Menu: **Product → Archive**
4. Wait for build to complete (~2-5 minutes)

### Step 4: Upload to App Store Connect

1. When archive completes, **Organizer** window opens
2. Select the archive → Click **Distribute App**
3. Choose: **App Store Connect** → **Upload**
4. Options:
   - ✅ Include bitcode (optional)
   - ✅ Upload symbols
   - ✅ Manage Version and Build Number
5. Click **Upload**
6. Wait for processing (~5-15 minutes)

### Step 5: Submit for TestFlight Review

1. Go to App Store Connect → Your App → TestFlight tab
2. Wait for build to appear (processing takes 5-30 minutes)
3. Click on the build
4. Fill in **Test Information**:
   - What to Test: "Core trading features, portfolio management, scoring"
   - Beta App Description: Brief description
   - Contact Email: Your email
5. Add **Export Compliance** info (usually "No" for encryption)
6. Click **Submit for Review**

First TestFlight review takes 24-48 hours. Subsequent builds are usually auto-approved.

### Step 6: Add Testers

**Internal Testers** (up to 100, instant access):
1. TestFlight → Internal Testing → Create Group
2. Add testers by Apple ID email
3. They get instant access (no review needed)

**External Testers** (up to 10,000, needs review):
1. TestFlight → External Testing → Create Group
2. Add testers by email
3. Builds require Apple review before distribution

### Step 7: Install on Device

Testers receive email with TestFlight invite:
1. Download TestFlight app from App Store
2. Open invite email → Click "View in TestFlight"
3. Install the app
4. App updates automatically when new builds are uploaded

---

## Versioning Strategy

### Semantic Versioning

```
MAJOR.MINOR.PATCH (Build)
  1   .  0  .  0   (1)
```

| Component | When to Increment |
|-----------|-------------------|
| MAJOR | Breaking changes, major redesign |
| MINOR | New features |
| PATCH | Bug fixes |
| Build | Every upload (auto-increment) |

### Update Version in Xcode

**GUI:**
1. Project Navigator → TradingApp
2. General tab → Identity section
3. Update Version and Build

**Script (recommended):**
```bash
# Increment build number
cd ios/TradingApp
agvtool next-version -all

# Set specific version
agvtool new-marketing-version 1.0.1
agvtool new-version -all 42
```

### Version in Code

```swift
// Access in Swift
let version = Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String
let build = Bundle.main.infoDictionary?["CFBundleVersion"] as? String
```

---

## Automated Build Script

Create `scripts/build_testflight.sh`:

```bash
#!/bin/bash
set -e

# Configuration
PROJECT_DIR="ios/TradingApp"
SCHEME="TradingApp"
ARCHIVE_PATH="build/Sigil.xcarchive"
EXPORT_PATH="build/Sigil.ipa"

echo "🔨 Building Sigil for TestFlight..."

# Clean previous builds
rm -rf build/

# Increment build number
cd $PROJECT_DIR
BUILD_NUM=$(agvtool what-version -terse)
NEW_BUILD=$((BUILD_NUM + 1))
agvtool new-version -all $NEW_BUILD
echo "📦 Build number: $NEW_BUILD"
cd ../..

# Archive
xcodebuild archive \
  -project $PROJECT_DIR/TradingApp.xcodeproj \
  -scheme $SCHEME \
  -destination 'generic/platform=iOS' \
  -archivePath $ARCHIVE_PATH \
  -allowProvisioningUpdates \
  CODE_SIGN_STYLE=Automatic

echo "✅ Archive created: $ARCHIVE_PATH"

# Export IPA
xcodebuild -exportArchive \
  -archivePath $ARCHIVE_PATH \
  -exportPath $EXPORT_PATH \
  -exportOptionsPlist $PROJECT_DIR/ExportOptions.plist \
  -allowProvisioningUpdates

echo "✅ IPA exported: $EXPORT_PATH"
echo ""
echo "📤 Upload to App Store Connect:"
echo "   xcrun altool --upload-app -f $EXPORT_PATH/*.ipa -t ios -u YOUR_APPLE_ID"
```

### ExportOptions.plist

Create `ios/TradingApp/ExportOptions.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>method</key>
    <string>app-store</string>
    <key>destination</key>
    <string>upload</string>
    <key>signingStyle</key>
    <string>automatic</string>
    <key>uploadSymbols</key>
    <true/>
</dict>
</plist>
```

---

## Upload via Command Line

After exporting IPA:

```bash
# Using altool (older method)
xcrun altool --upload-app \
  -f build/Sigil.ipa/*.ipa \
  -t ios \
  -u "your@apple.id" \
  -p "@keychain:AC_PASSWORD"

# Using notarytool (newer, faster)
xcrun notarytool submit build/Sigil.ipa/*.ipa \
  --apple-id "your@apple.id" \
  --team-id "YOUR_TEAM_ID" \
  --password "@keychain:AC_PASSWORD"
```

### Store Password in Keychain

```bash
xcrun altool --store-password-in-keychain-item "AC_PASSWORD" \
  -u "your@apple.id" \
  -p "app-specific-password"
```

Generate app-specific password at: https://appleid.apple.com/account/manage

---

## Troubleshooting

### "No signing certificate found"

1. Xcode → Settings → Accounts → Your Apple ID
2. Click "Manage Certificates"
3. Click "+" → "Apple Distribution"

### "Provisioning profile doesn't include device"

For Ad Hoc distribution only. Use TestFlight instead (no device registration needed).

### "App is not available" on TestFlight

1. Check if build finished processing (App Store Connect)
2. Check if tester accepted invite
3. Check if build passed review (external testers)

### Build fails with signing errors

```bash
# Reset signing
cd ios/TradingApp
xcodebuild -project TradingApp.xcodeproj -scheme TradingApp -showBuildSettings | grep DEVELOPMENT_TEAM
```

Ensure DEVELOPMENT_TEAM matches your Apple Developer Team ID.

---

## Checklist: First TestFlight Release

- [ ] Apple Developer account active ($99/year)
- [ ] App created in App Store Connect
- [ ] Bundle ID matches (`com.sigil.ios`)
- [ ] Version set (1.0.0)
- [ ] Privacy Policy URL added
- [ ] Archive created in Xcode
- [ ] Build uploaded to App Store Connect
- [ ] Test Information filled in
- [ ] Export Compliance answered
- [ ] Build submitted for review
- [ ] Testers added to TestFlight group
- [ ] Testers installed via TestFlight app

---

## Quick Reference

| Action | Command/Location |
|--------|------------------|
| Archive app | Product → Archive (Xcode) |
| View archives | Window → Organizer (Xcode) |
| Upload build | Organizer → Distribute App |
| Manage TestFlight | appstoreconnect.apple.com |
| Add testers | App Store Connect → TestFlight |
| Increment build | `agvtool next-version -all` |
| Set version | `agvtool new-marketing-version 1.0.1` |

---

## Related Resources

- [Apple Developer Documentation](https://developer.apple.com/documentation/xcode/distributing-your-app-for-beta-testing-and-releases)
- [TestFlight Guide](https://developer.apple.com/testflight/)
- [App Store Connect Help](https://help.apple.com/app-store-connect/)

---

*For questions, check Apple's documentation or ask the team.*
