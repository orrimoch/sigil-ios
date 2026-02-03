#!/usr/bin/env python3
"""
Script to build/refresh the stock universe.

Run: python scripts/build_universe.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from data.stock_universe import build_universe, save_universe, get_sectors
from loguru import logger


def main():
    logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} | {level} | {message}")
    
    print("\n" + "=" * 60)
    print("  TradingApp - Building Stock Universe")
    print("=" * 60 + "\n")
    
    # Build universe
    universe = build_universe()
    
    # Save to cache
    save_universe(universe)
    
    # Print summary
    print("\n" + "-" * 60)
    print(f"✅ Universe built: {len(universe)} stocks")
    print("-" * 60)
    
    print("\n📊 Top 10 by Market Cap:\n")
    print(f"  {'Ticker':<8} {'Name':<35} {'Market Cap':>12} {'Sector':<20}")
    print(f"  {'-'*8} {'-'*35} {'-'*12} {'-'*20}")
    
    for stock in universe[:10]:
        mcap = f"${stock['market_cap']/1e9:.1f}B"
        print(f"  {stock['ticker']:<8} {stock['name'][:35]:<35} {mcap:>12} {stock['sector'][:20]:<20}")
    
    print("\n📈 Sector Breakdown:\n")
    sectors = get_sectors()
    for sector, count in sectors.items():
        bar = "█" * (count // 5)
        print(f"  {sector:<30} {count:>3} {bar}")
    
    print("\n" + "=" * 60)
    print("  Done! Universe saved to data/stock_universe.json")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
