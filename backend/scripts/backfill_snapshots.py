#!/usr/bin/env python3
"""
Backfill portfolio_snapshots table from actual positions + historical prices.

Uses positions table + current cash as source of truth.
Reconstructs cash timeline by working backwards from current DB cash.
Uses yf.download() with all tickers in ONE call for speed.
"""

import sqlite3
import sys
from datetime import datetime, timedelta, date, timezone
from pathlib import Path
from collections import defaultdict

import yfinance as yf
import pandas as pd

DB_PATH = Path(__file__).parent.parent / "data" / "sigil.db"


def get_positions_for_portfolio(conn, portfolio_id):
    """Get all positions for a portfolio, sorted by opened_at."""
    cursor = conn.execute(
        "SELECT ticker, quantity, avg_cost, opened_at "
        "FROM positions WHERE portfolio_id = ? ORDER BY opened_at",
        (portfolio_id,),
    )
    positions = []
    for row in cursor.fetchall():
        ticker, qty, avg_cost, opened_at_str = row
        for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                opened_at = datetime.strptime(opened_at_str, fmt)
                break
            except ValueError:
                continue
        else:
            opened_at = datetime.now()
        positions.append({
            "ticker": ticker,
            "quantity": qty,
            "avg_cost": avg_cost,
            "cost_basis": qty * avg_cost,
            "opened_at": opened_at,
            "date": opened_at.date(),
        })
    return positions


def get_portfolio_info(conn, user_id):
    """Get portfolio id, starting cash, and current cash balance."""
    cursor = conn.execute(
        "SELECT id, starting_cash, cash_balance FROM portfolios WHERE user_id = ?",
        (user_id,),
    )
    row = cursor.fetchone()
    if not row:
        return None, None, None
    return row[0], row[1], row[2]


def fetch_batch_prices(tickers, start_date, end_date):
    """Batch-download historical prices in ONE yfinance call."""
    if not tickers:
        return {}

    print(f"  Fetching prices for {len(tickers)} tickers: {', '.join(tickers)}")

    fetch_start = start_date - timedelta(days=7)
    fetch_end = end_date + timedelta(days=1)

    try:
        data = yf.download(
            tickers if len(tickers) > 1 else tickers[0],
            start=fetch_start.isoformat(),
            end=fetch_end.isoformat(),
            progress=False,
            auto_adjust=True,
            group_by="ticker" if len(tickers) > 1 else None,
        )
    except Exception as e:
        print(f"  ERROR downloading prices: {e}")
        return {}

    if data.empty:
        return {}

    result = {}
    if len(tickers) == 1:
        ticker = tickers[0]
        result[ticker] = {}
        for idx, row in data.iterrows():
            d = idx.date() if hasattr(idx, 'date') else idx
            close = row.get('Close', None)
            if close is not None:
                if hasattr(close, 'iloc'):
                    close = close.iloc[0]
                if pd.notna(close):
                    result[ticker][d] = float(close)
    else:
        for ticker in tickers:
            result[ticker] = {}
            try:
                if ticker in data.columns.get_level_values(0):
                    ticker_data = data[ticker]
                    for idx, row in ticker_data.iterrows():
                        d = idx.date() if hasattr(idx, 'date') else idx
                        close = row.get('Close', None)
                        if close is not None and pd.notna(close):
                            result[ticker][d] = float(close)
            except Exception as e:
                print(f"  WARNING: Error processing {ticker}: {e}")

    for t in tickers:
        print(f"    {t}: {len(result.get(t, {}))} price points")

    return result


def get_nearest_price(prices, target_date):
    """Find nearest available price (looking backwards for weekends/holidays)."""
    if not prices:
        return None
    for i in range(7):
        check = target_date - timedelta(days=i)
        if check in prices:
            return prices[check]
    sorted_dates = sorted(prices.keys())
    earlier = [d for d in sorted_dates if d <= target_date]
    if earlier:
        return prices[earlier[-1]]
    if sorted_dates:
        return prices[sorted_dates[0]]
    return None


def backfill_user(conn, user_id, label=""):
    """
    Backfill snapshots using positions + DB cash as source of truth.
    
    Strategy:
    - Current cash = DB cash_balance (truth)
    - Work backwards: before each position opened, cash was higher by that position's cost
    - Build a timeline of cash values and active positions
    - Value positions at market prices for each day
    """
    print(f"\n{'='*60}")
    print(f"Backfilling: {label} (user_id={user_id})")
    print(f"{'='*60}")

    portfolio_id, starting_cash, current_cash = get_portfolio_info(conn, user_id)
    if not portfolio_id:
        print(f"  No portfolio found, skipping")
        return 0

    print(f"  Portfolio: {portfolio_id}")
    print(f"  Starting cash: ${starting_cash:,.2f}")
    print(f"  Current cash:  ${current_cash:,.2f}")

    all_positions = get_positions_for_portfolio(conn, portfolio_id)
    if not all_positions:
        print(f"  No positions, skipping")
        return 0

    print(f"  Found {len(all_positions)} positions")

    # Sort positions by opened date (latest first for backward reconstruction)
    sorted_positions = sorted(all_positions, key=lambda p: p["opened_at"])

    first_date = sorted_positions[0]["date"]
    end_date = date.today()
    print(f"  Date range: {first_date} to {end_date}")

    # Build cash change events (sorted by date)
    # Each position opening reduced cash by its cost basis
    cash_events = []
    for pos in sorted_positions:
        cash_events.append({
            "date": pos["date"],
            "ticker": pos["ticker"],
            "quantity": pos["quantity"],
            "cost": pos["cost_basis"],
        })
    cash_events.sort(key=lambda e: e["date"])

    # Reconstruct cash at the START (before any position opened)
    total_cost_all = sum(p["cost_basis"] for p in all_positions)
    initial_cash = current_cash + total_cost_all
    print(f"  Reconstructed initial cash: ${initial_cash:,.2f}")
    print(f"  Total position cost basis:  ${total_cost_all:,.2f}")

    # Collect tickers and fetch prices
    tickers = list(set(p["ticker"] for p in all_positions))
    prices = fetch_batch_prices(tickers, first_date, end_date)

    # Build daily snapshots
    now_iso = datetime.now(timezone.utc).isoformat()
    snapshots = []
    cash = initial_cash
    active_positions = {}  # ticker -> quantity
    event_idx = 0

    current_date = first_date
    while current_date <= end_date:
        # Activate positions opened on or before this date
        while event_idx < len(cash_events):
            event = cash_events[event_idx]
            if event["date"] <= current_date:
                ticker = event["ticker"]
                cash -= event["cost"]
                active_positions[ticker] = active_positions.get(ticker, 0) + event["quantity"]
                event_idx += 1
            else:
                break

        # Calculate positions value at market price
        positions_value = 0.0
        for ticker, qty in active_positions.items():
            price = get_nearest_price(prices.get(ticker, {}), current_date)
            if price:
                positions_value += qty * price

        total_value = cash + positions_value
        pnl = total_value - starting_cash
        pnl_pct = (pnl / starting_cash * 100) if starting_cash > 0 else 0

        snapshots.append((
            user_id,
            portfolio_id,
            current_date.isoformat(),
            round(total_value, 2),
            round(cash, 2),
            round(positions_value, 2),
            round(pnl, 2),
            round(pnl_pct, 2),
            now_iso,
        ))

        current_date += timedelta(days=1)

    # Clear and insert
    print(f"  Inserting {len(snapshots)} snapshots...")
    conn.execute("DELETE FROM portfolio_snapshots WHERE user_id = ?", (user_id,))
    conn.executemany(
        "INSERT OR REPLACE INTO portfolio_snapshots "
        "(user_id, portfolio_id, date, total_value, cash, positions_value, "
        "total_pnl, total_pnl_percent, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        snapshots,
    )
    conn.commit()

    if snapshots:
        first = snapshots[0]
        last = snapshots[-1]
        print(f"  First snapshot: {first[2]} — ${first[3]:,.2f} (cash: ${first[4]:,.2f})")
        print(f"  Last snapshot:  {last[2]} — ${last[3]:,.2f} (cash: ${last[4]:,.2f})")
        print(f"  PnL: ${last[6]:,.2f} ({last[7]:+.2f}%)")

    print(f"  ✅ Done — {len(snapshots)} snapshots inserted")
    return len(snapshots)


def main():
    print("=" * 60)
    print("Portfolio Snapshot Backfill")
    print("=" * 60)

    conn = sqlite3.connect(str(DB_PATH))

    # Or (or@sigil.com) — main user
    n1 = backfill_user(
        conn,
        "8f9cbe7a-f6ae-43bd-a4b2-39ba7a1ecbd2",
        "Or (or@sigil.com)",
    )

    # Anonymous user
    n2 = backfill_user(conn, "anonymous", "Anonymous")

    # 67a047b2 anonymous
    n3 = backfill_user(
        conn,
        "67a047b2-aa12-4b34-8f19-dac5237a7af0",
        "67a047b2 Anonymous",
    )

    conn.close()

    total = n1 + n2 + n3
    print(f"\n{'='*60}")
    print(f"TOTAL: {total} snapshots backfilled")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
