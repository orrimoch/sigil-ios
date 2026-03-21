"""
Portfolio Snapshot Backfill Script

Reconstructs accurate daily portfolio history using REAL historical prices.
Uses yfinance batch download for efficiency.

Usage:
    cd backend && python3 -m src.db.snapshot_backfill
    cd backend && python3 -m src.db.snapshot_backfill --force  # re-backfill all
"""

import sqlite3
import json
import sys
import yfinance as yf
from datetime import datetime, timedelta, date
from collections import defaultdict


DB_PATH = "data/sigil.db"


def get_portfolios_with_positions(db):
    """Get all portfolios that have positions."""
    portfolios = db.execute("SELECT * FROM portfolios").fetchall()
    result = []
    for port in portfolios:
        port = dict(port)
        positions = db.execute(
            "SELECT * FROM positions WHERE portfolio_id=?", (port["id"],)
        ).fetchall()
        if positions:
            port["positions"] = [dict(p) for p in positions]
            result.append(port)
    return result


def get_filled_orders(db, user_id):
    """Get all filled orders for a user, sorted by date."""
    orders = db.execute(
        "SELECT * FROM user_orders WHERE user_id=? AND status='FILLED' ORDER BY filled_at ASC",
        (user_id,),
    ).fetchall()
    return [dict(o) for o in orders]


def fetch_historical_prices_batch(tickers, start_date, end_date):
    """Fetch historical prices for ALL tickers in one batch call."""
    if not tickers:
        return {}

    print(f"  Fetching historical prices for {len(tickers)} tickers...")
    print(f"  Period: {start_date} to {end_date}")

    # yfinance batch download — much faster than one-by-one
    ticker_str = " ".join(tickers)
    data = yf.download(
        ticker_str,
        start=(start_date - timedelta(days=5)).isoformat(),
        end=(end_date + timedelta(days=1)).isoformat(),
        progress=False,
        auto_adjust=True,
        group_by="ticker",
    )

    prices = {}
    for ticker in tickers:
        prices[ticker] = {}
        try:
            if len(tickers) == 1:
                # Single ticker — different DataFrame structure
                ticker_data = data
            else:
                ticker_data = data[ticker]

            if ticker_data is not None and not ticker_data.empty:
                for idx, row in ticker_data.iterrows():
                    d = idx.date() if hasattr(idx, "date") else idx
                    close = row.get("Close")
                    if close is not None:
                        # Handle both scalar and Series
                        if hasattr(close, "iloc"):
                            close = close.iloc[0]
                        if close > 0:
                            prices[ticker][d] = float(close)
        except Exception as e:
            print(f"  Warning: Could not get prices for {ticker}: {e}")

    for ticker in tickers:
        print(f"    {ticker}: {len(prices.get(ticker, {}))} price points")

    return prices


def get_nearest_price(prices, target_date, max_lookback=7):
    """Get nearest available price (for weekends/holidays)."""
    for i in range(max_lookback):
        check = target_date - timedelta(days=i)
        if check in prices:
            return prices[check]
    # Forward look
    for i in range(1, max_lookback):
        check = target_date + timedelta(days=i)
        if check in prices:
            return prices[check]
    return None


def reconstruct_portfolio_history(db, portfolio, orders, historical_prices):
    """
    Reconstruct day-by-day portfolio value from orders + historical prices.
    
    This is the accurate method — it replays all trades and values positions
    at each day's actual closing price.
    """
    starting_cash = portfolio["starting_cash"]
    portfolio_id = portfolio["id"]

    # Determine date range
    if orders:
        first_order_date = datetime.fromisoformat(orders[0]["filled_at"]).date()
    else:
        # No orders — use position opened_at dates
        dates = []
        for pos in portfolio.get("positions", []):
            try:
                dates.append(datetime.fromisoformat(pos["opened_at"]).date())
            except:
                pass
        first_order_date = min(dates) if dates else date.today()

    start_date = first_order_date
    end_date = date.today()

    # Replay trades day by day
    positions = {}  # ticker -> shares
    cash = starting_cash
    order_idx = 0
    snapshots = []

    current_date = start_date
    while current_date <= end_date:
        # Apply orders that happened on or before this date
        while order_idx < len(orders):
            order = orders[order_idx]
            order_date = datetime.fromisoformat(order["filled_at"]).date()

            if order_date <= current_date:
                filled_price = order.get("filled_price", 0) or 0
                filled_qty = order.get("filled_quantity", 0) or 0
                trade_value = filled_qty * filled_price

                if order["side"] == "BUY":
                    cash -= trade_value
                    positions[order["ticker"]] = positions.get(order["ticker"], 0) + filled_qty
                else:  # SELL
                    cash += trade_value
                    positions[order["ticker"]] = positions.get(order["ticker"], 0) - filled_qty
                    if positions.get(order["ticker"], 0) <= 0:
                        positions.pop(order["ticker"], None)

                order_idx += 1
            else:
                break

        # Value positions at this day's closing price
        positions_value = 0.0
        for ticker, shares in positions.items():
            ticker_prices = historical_prices.get(ticker, {})
            price = get_nearest_price(ticker_prices, current_date)
            if price:
                positions_value += shares * price
            # If no price found, position value = 0 (shouldn't happen with good data)

        total_value = cash + positions_value
        pnl = total_value - starting_cash
        pnl_percent = (pnl / starting_cash * 100) if starting_cash > 0 else 0

        snapshots.append({
            "user_id": portfolio["user_id"],
            "portfolio_id": portfolio_id,
            "date": current_date.isoformat(),
            "total_value": round(total_value, 2),
            "cash": round(cash, 2),
            "positions_value": round(positions_value, 2),
            "total_pnl": round(pnl, 2),
            "total_pnl_percent": round(pnl_percent, 2),
            "created_at": datetime.now().isoformat(),
        })

        current_date += timedelta(days=1)

    return snapshots


def save_snapshots(db, snapshots, force=False):
    """Save snapshots to database."""
    if force:
        # Delete existing snapshots for this portfolio
        portfolio_id = snapshots[0]["portfolio_id"] if snapshots else None
        if portfolio_id:
            db.execute(
                "DELETE FROM portfolio_snapshots WHERE portfolio_id=?",
                (portfolio_id,),
            )

    for snap in snapshots:
        db.execute(
            """INSERT OR REPLACE INTO portfolio_snapshots 
               (user_id, portfolio_id, date, total_value, cash, positions_value, 
                total_pnl, total_pnl_percent, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                snap["user_id"],
                snap["portfolio_id"],
                snap["date"],
                snap["total_value"],
                snap["cash"],
                snap["positions_value"],
                snap["total_pnl"],
                snap["total_pnl_percent"],
                snap["created_at"],
            ),
        )

    db.commit()


def main():
    force = "--force" in sys.argv

    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row

    # Ensure table exists
    db.execute("""
        CREATE TABLE IF NOT EXISTS portfolio_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            portfolio_id TEXT NOT NULL,
            date TEXT NOT NULL,
            total_value REAL NOT NULL,
            cash REAL NOT NULL,
            positions_value REAL NOT NULL,
            total_pnl REAL NOT NULL,
            total_pnl_percent REAL NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(portfolio_id, date)
        )
    """)

    portfolios = get_portfolios_with_positions(db)
    print(f"Found {len(portfolios)} portfolios with positions\n")

    for port in portfolios:
        pid = port["id"]
        uid = port["user_id"]
        num_positions = len(port["positions"])
        print(f"Portfolio {pid[:8]}... (user: {uid[:12]}..., {num_positions} positions)")

        # Get all tickers from positions
        tickers = list(set(p["ticker"] for p in port["positions"]))
        print(f"  Tickers: {', '.join(tickers)}")

        # Get filled orders
        orders = get_filled_orders(db, uid)
        print(f"  Orders: {len(orders)} filled")

        # Determine date range
        if orders:
            start = datetime.fromisoformat(orders[0]["filled_at"]).date()
        else:
            dates = []
            for pos in port["positions"]:
                try:
                    dates.append(datetime.fromisoformat(pos["opened_at"]).date())
                except:
                    pass
            start = min(dates) if dates else date.today()

        end = date.today()

        # Fetch historical prices (batch)
        historical_prices = fetch_historical_prices_batch(tickers, start, end)

        # Reconstruct history
        snapshots = reconstruct_portfolio_history(db, port, orders, historical_prices)
        print(f"  Generated {len(snapshots)} daily snapshots")

        if snapshots:
            print(f"  First: {snapshots[0]['date']} = ${snapshots[0]['total_value']:,.2f} ({snapshots[0]['total_pnl_percent']:+.2f}%)")
            print(f"  Last:  {snapshots[-1]['date']} = ${snapshots[-1]['total_value']:,.2f} ({snapshots[-1]['total_pnl_percent']:+.2f}%)")

        # Save
        save_snapshots(db, snapshots, force=force)
        print(f"  Saved to database {'(force replaced)' if force else ''}\n")

    db.close()
    print("Done!")


if __name__ == "__main__":
    main()
