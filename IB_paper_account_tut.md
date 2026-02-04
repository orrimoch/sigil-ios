<img src="docs/sigil_logo.jpg" alt="Sigil" width="240" />

# How to Create an IBKR Paper Trading Account

**Prerequisite:** You already have a funded, active Interactive Brokers (IBKR Pro) account.

---

## What Is a Paper Trading Account?

A paper trading account is a **simulated trading environment** linked to your live IBKR account. It lets you:

- Test strategies with **virtual money** (no risk)
- Access **real-time market data** (10-15 min delayed unless you have subscriptions)
- Place simulated orders that execute against **live market conditions**
- Use the same platforms: TWS, IBKR Desktop, IBKR Mobile, Client Portal, and **Web API**

Your paper account gets its own unique **username** (e.g., `your_username_paper` → typically your live username with a suffix) and **account ID** (format: `DU1234567` — the "D" prefix indicates demo/paper).

---

## Step 1: Log In to Client Portal

1. Go to [**https://www.interactivebrokers.com/en/home.php**](https://www.interactivebrokers.com/en/home.php)
2. Click **Log In** (top right)
3. Sign in with your **live account** credentials (username + password)
4. Complete Two-Factor Authentication (2FA) if prompted

---

## Step 2: Navigate to Paper Trading Settings

1. Click the **person/avatar icon** (head and shoulders) in the **top-right corner** of Client Portal
2. Click **Settings**
3. In the Settings page, look for **"Paper Trading Account"** in the left sidebar or in the account section
4. Click on it

> **Alternative path:** Settings → Account Settings → Paper Trading Account

---

## Step 3: Create the Paper Trading Account

1. If you don't have a paper account yet, you'll see an option to **create one**
2. Click **"Create"** or **"Open Paper Trading Account"**
3. IBKR will automatically generate:
   - A **paper trading username** (displayed on the page)
   - A **paper account ID** (starts with `DU` for individual accounts)
   - A **starting cash balance** (typically $1,000,000 USD)
4. **Note your paper trading username** — you'll need it to log in

> ⚠️ The paper account shares the same password as your live account. Only the **username** is different.

---

## Step 4: Note Your Paper Account Credentials

After creation, you'll see:

| Field | Example | Notes |
|-------|---------|-------|
| **Paper Username** | `jsmith_paper` or `jsmithPAPER` | Used to log in to paper trading |
| **Paper Account ID** | `DU1234567` | The account identifier for API calls |
| **Password** | *(same as live)* | Shared with your live account |

**Save these — you'll need the Account ID for Sigil's IBKR integration.**

---

## Step 5: Log In to Paper Trading

You can log in to paper trading from any IBKR platform:

### Option A: Client Portal (Web)

1. Go to [https://www.interactivebrokers.com/en/home.php](https://www.interactivebrokers.com/en/home.php)
2. Log in with your **paper trading username** (not your live username)
3. Enter your password (same as live)
4. Complete 2FA

### Option B: Trader Workstation (TWS)

1. Launch TWS
2. In the login screen, enter your **paper trading username**
3. Select **"Paper Trading"** if there's a toggle
4. Enter your password

### Option C: IBKR Mobile App

1. Open IBKR Mobile
2. Log in with your **paper trading username**
3. You'll see "PAPER" indicated in the app

---

## Step 6: Configure Paper Account (Optional)

### Reset Paper Account Balance

If you want to reset your paper balance back to the starting amount:

1. Log in to Client Portal with your **live account**
2. Go to Settings → Paper Trading Account
3. Click **"Reset"** to restore the default cash balance

### Market Data

- Paper accounts receive **delayed market data** by default (10-15 min delay)
- If your live account has **market data subscriptions**, the paper account shares them
- To get real-time data in paper trading, your live account must have active subscriptions

---

## Step 7: Get the Account ID for Sigil

For Sigil's IBKR integration, you need the **Paper Account ID**:

1. Log in to Client Portal with your **paper username**
2. The Account ID is displayed in the top-right corner or under **Account → Account Information**
3. It will look like: `DU1234567`

**In Sigil:**
1. Go to **Settings → Interactive Brokers → Connect IBKR**
2. Enter your paper account ID when prompted
3. Sigil will use this to route orders through the IBKR API

---

## Using Paper Account with IBKR Web API

The paper account works with IBKR's Client Portal Web API, which Sigil uses:

### Client Portal Gateway (for local development)

```bash
# 1. Download the Client Portal Gateway from IBKR
# 2. Unzip and navigate to the directory
cd ~/clientportal.gw

# 3. Start the gateway (macOS/Linux)
bin/run.sh root/conf.yaml

# 4. Open browser and navigate to:
# https://localhost:5000

# 5. Log in with your PAPER TRADING username
# 6. Complete 2FA
# 7. You'll see "Client login succeeds"
```

### Important Notes for API Usage

- **Port:** Gateway listens on port `5000` by default (change in `root/conf.yaml` → `listenPort`)
- **macOS conflict:** Port 5000 may be used by AirPlay Receiver — change to `5001` if needed
- **SSL warning:** Expected — the gateway uses a self-signed cert (connection to IBKR servers is still encrypted)
- **Re-auth:** You must re-authenticate at least **once per day** (after midnight)
- **Single session:** Only one brokerage session per username at a time — logging in via API will disconnect TWS/Mobile and vice versa
- **Java required:** Gateway needs JRE 8 update 192 or later (`java -version` to check)

### Key API Endpoints (Paper Account)

```
# Check authentication status
GET https://localhost:5000/v1/api/iserver/auth/status

# Get accounts
GET https://localhost:5000/v1/api/portfolio/accounts

# Get positions
GET https://localhost:5000/v1/api/portfolio/{accountId}/positions/0

# Place an order
POST https://localhost:5000/v1/api/iserver/account/{accountId}/orders
Body: {
  "orders": [{
    "conid": 265598,        // AAPL contract ID
    "orderType": "MKT",
    "side": "BUY",
    "quantity": 10,
    "tif": "DAY"
  }]
}

# Get order status
GET https://localhost:5000/v1/api/iserver/account/orders
```

---

## Troubleshooting

### "Paper Trading Account" option not visible
- Make sure you're logged in with your **live account** (not paper)
- Check under Settings → Account Settings
- Some account types may require contacting IBKR support to enable paper trading

### Can't log in to paper account
- Verify you're using the **paper username** (not your live username)
- Password is the same as your live account
- 2FA is required for paper accounts too

### "Server listen failed Address already in use" (macOS)
- Port 5000 conflict with AirPlay Receiver
- Fix: System Settings → General → AirDrop & Handoff → disable "AirPlay Receiver"
- Or change gateway port to 5001 in `root/conf.yaml`

### Delayed market data
- Normal for paper accounts without subscriptions
- Subscribe to market data on your live account — paper will share it

### Paper account balance seems wrong
- Paper P&L is calculated using market prices
- Reset via Client Portal if needed (Settings → Paper Trading Account → Reset)

---

## Quick Reference

| Item | Value |
|------|-------|
| **Client Portal** | https://www.interactivebrokers.com/en/home.php |
| **Paper username format** | `{live_username}_paper` or similar |
| **Paper account ID format** | `DU1234567` |
| **Password** | Same as live account |
| **Default paper balance** | $1,000,000 USD |
| **Gateway default port** | 5000 (recommend 5001 on macOS) |
| **Gateway download** | IBKR Campus → API → Web API → Client Portal Gateway |
| **API Docs** | https://www.interactivebrokers.com/campus/ibkr-api-page/cpapi-v1/ |
| **Java requirement** | JRE 8u192+ |
| **Re-auth frequency** | Once per day (after midnight) |

---

*Last updated: February 4, 2026*
