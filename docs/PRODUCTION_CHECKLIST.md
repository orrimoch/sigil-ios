<img src="sigil_logo.jpg" alt="Sigil" width="240" />

# Production Launch Checklist

**Ticket:** REC-276  
**Status:** In Progress  
**Last Updated:** 2026-02-17

---

## 🔴 Blockers (Need Or's Action)

### 1. Domain Registration

- [ ] Register `sigil.app` or `sigil.io` or alternative

- **Options:** Namecheap, Cloudflare, Google Domains
- **Cost:** ~$15-40/year
- **Action:** Or to decide domain and register

### 2. Backend Hosting

- [ ] Choose hosting provider

- **Options:**
  - Railway (~$5-20/month) - Easy deploy
  - Render (~$7/month) - Good free tier
  - Fly.io (~$5-15/month) - Edge deployment
  - DigitalOcean ($6/month) - VPS with more control
- **Requirements:** Python 3.9+, SQLite/PostgreSQL, 512MB+ RAM
- **Action:** Or to choose provider and create account

### 3. APNs Push Certificate

- [ ] Generate APNs .p8 key from Apple Developer Portal

- **Location:** Certificates, Identifiers & Profiles → Keys → Create Key
- **Required for:** Push notifications (trade alerts, score updates)
- **Action:** Or to generate from Apple Developer account

### 4. Email Service (Optional for MVP)

- [ ] SendGrid or SMTP for password reset emails

- **Options:**
  - SendGrid (100 emails/day free)
  - Mailgun (5,000 emails/month free)
  - AWS SES (~$0.10/1000 emails)
- **Action:** Or to create account if needed

---

## 🟡 Blaze Can Prepare (In Progress)

### 5. Version Tagging

- [ ] Create git tag `v1.0.0`
- [ ] Set up GitHub Releases
- [ ] Sync iOS app version (Info.plist)
- [ ] Document version scheme

### 6. CI/CD Pipeline

- [ ] GitHub Actions workflow for:
  - [ ] Backend tests on PR
  - [ ] iOS build verification
  - [ ] Auto-tag on merge to main
- [ ] Deploy script for hosting provider

### 7. Environment Configuration

- [ ] Create `.env.production` template
- [ ] Document all required env vars
- [ ] Secrets management guide

### 8. Database Migration

- [ ] PostgreSQL migration scripts (from SQLite)
- [ ] Data backup/restore procedures
- [ ] Production seed data

### 9. Security Hardening

- [ ] Enable AUTH_REQUIRED=true
- [ ] HTTPS enforcement
- [ ] Rate limiting configuration
- [ ] API key rotation procedure

### 10. Monitoring & Logging

- [ ] Error tracking (Sentry recommended)
- [ ] Uptime monitoring
- [ ] Log aggregation

---

## 🟢 Ready / Done

### App Store Assets

- [x] App icon (all sizes)
- [x] Screenshots (prepared in Simulator)
- [x] App description draft
- [x] Privacy policy URL needed

### Code Quality

- [x] 562+ tests passing
- [x] Zero build warnings
- [x] Error handling complete
- [x] Offline mode tested

### TestFlight

- [ ] Ready to upload once hosting is up
- [ ] Internal testing group configured
- [ ] Beta app description

---

## Post-MVP Features (Backlog)

- Walk-Forward Backtesting
- Strategy Optimizer
- iOS Home Screen Widget
- Apple Watch companion
- Multi-portfolio support

---

## Timeline Estimate

| Phase                  | Duration     | Blocker        |
| ---------------------- | ------------ | -------------- |
| Domain + Hosting Setup | 1-2 hours    | Or's accounts  |
| Backend Deployment     | 2-4 hours    | Hosting choice |
| APNs Configuration     | 30 min       | .p8 key        |
| TestFlight Upload      | 1-2 hours    | None           |
| **Total**              | **1-2 days** |                |

---

## Next Steps

1. **Or:** Choose domain + hosting provider
2. **Blaze:** Prepare deployment configs
3. **Or:** Generate APNs .p8 key
4. **Blaze:** Deploy backend, configure push
5. **Together:** TestFlight upload + testing
