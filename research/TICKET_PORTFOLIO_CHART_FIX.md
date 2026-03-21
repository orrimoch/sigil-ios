# REC-TBD: Fix Portfolio History Chart Shows Wrong Period Return

**Priority:** P1 (Critical)
**Status:** In Progress
**Created:** 2026-03-21
**Assigned:** Blaze Neon (sub-agent)
**Note:** Linear API limit — will create in Linear once resolved

## Description
Portfolio chart in iOS app shows +1.98% period return instead of the real +64% all-time return.

## Root Cause
1. **History endpoint times out** — fetches 9 tickers one-by-one from Yahoo Finance (synchronous)
2. **No cached history** — every chart load re-fetches everything from scratch
3. **Performance "All" period** — starts from first trade value, not from starting capital ($100K)

## Fix (In Progress)
1. ✅ Add `portfolio_snapshots` table to sigil.db
2. ✅ Backfill historical snapshots (Feb 5 → today) using batch Yahoo Finance
3. ✅ Update `PortfolioHistoryService` to read from snapshots (instant loads)
4. ✅ Fix batch price fetching (all tickers in one call)
5. ✅ Fix "All" period to use $100K starting capital as start_value
6. ✅ Add daily snapshot cron job (11 PM ISR)
7. ✅ Write unit tests for snapshot service
8. ✅ Run full test suite (unit + integration) — no regressions

## Files Modified
- `backend/src/db/portfolio_history_service.py` — main fix
- `backend/data/sigil.db` — new table
- `backend/tests/unit/test_portfolio_snapshots.py` — new tests

## Acceptance Criteria
- [ ] Chart shows +64% all-time return for Or's portfolio
- [ ] History endpoint responds in <1 second (reads from DB, not Yahoo)
- [ ] Daily snapshots recorded automatically
- [ ] All existing unit tests pass
- [ ] All existing integration tests pass
- [ ] New snapshot tests pass

## Work Log
*(Updated by sub-agent as work progresses)*
