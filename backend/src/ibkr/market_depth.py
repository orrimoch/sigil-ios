"""
REC-150: Level 2 Market Depth

Fetch and display market depth (bid/ask ladder) from IB Gateway.
Shows order book with price levels and sizes.
"""

from dataclasses import dataclass
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class DepthLevel:
    """Single level in the order book."""
    price: float
    size: int
    num_orders: int = 1  # Number of orders at this level
    
    def to_dict(self) -> dict:
        return {
            "price": round(self.price, 2),
            "size": self.size,
            "num_orders": self.num_orders,
        }


@dataclass
class MarketDepth:
    """Full market depth with bid and ask sides."""
    ticker: str
    bids: List[DepthLevel]  # Sorted highest to lowest
    asks: List[DepthLevel]  # Sorted lowest to highest
    last_price: Optional[float] = None
    spread: Optional[float] = None
    spread_percent: Optional[float] = None
    timestamp: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "bids": [b.to_dict() for b in self.bids],
            "asks": [a.to_dict() for a in self.asks],
            "last_price": round(self.last_price, 2) if self.last_price else None,
            "spread": round(self.spread, 4) if self.spread else None,
            "spread_percent": round(self.spread_percent, 4) if self.spread_percent else None,
            "timestamp": self.timestamp,
            "bid_depth": sum(b.size for b in self.bids),
            "ask_depth": sum(a.size for a in self.asks),
            "levels": len(self.bids),
        }


def get_market_depth_mock(ticker: str, levels: int = 10) -> MarketDepth:
    """
    Generate mock market depth data for testing.
    
    In production, this would be replaced with IBKR reqMktDepth.
    """
    import random
    from datetime import datetime, timezone
    
    # Get a base price (in real impl, get from IBKR)
    base_price = {
        "AAPL": 185.50,
        "MSFT": 410.20,
        "GOOGL": 175.80,
        "AMZN": 178.50,
        "NVDA": 875.30,
        "META": 485.60,
        "TSLA": 185.40,
    }.get(ticker.upper(), 100.0)
    
    # Generate bid/ask levels
    bids = []
    asks = []
    
    spread = base_price * 0.0002  # 0.02% spread
    best_bid = base_price - spread / 2
    best_ask = base_price + spread / 2
    
    for i in range(levels):
        # Bids (descending)
        bid_price = best_bid - (i * 0.01)
        bid_size = random.randint(100, 5000) * 100
        bids.append(DepthLevel(price=bid_price, size=bid_size, num_orders=random.randint(1, 20)))
        
        # Asks (ascending)
        ask_price = best_ask + (i * 0.01)
        ask_size = random.randint(100, 5000) * 100
        asks.append(DepthLevel(price=ask_price, size=ask_size, num_orders=random.randint(1, 20)))
    
    return MarketDepth(
        ticker=ticker.upper(),
        bids=bids,
        asks=asks,
        last_price=base_price,
        spread=spread,
        spread_percent=(spread / base_price) * 100,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


async def get_market_depth_ibkr(ticker: str, levels: int = 10) -> Optional[MarketDepth]:
    """
    Get market depth from IB Gateway.
    
    Requires IBKR connection and market data subscription.
    """
    try:
        from ibkr.ibkr_service import IBKRService
        
        service = IBKRService()
        if not service.is_connected():
            logger.warning("IBKR not connected, using mock data")
            return get_market_depth_mock(ticker, levels)
        
        # TODO: Implement actual IBKR market depth request
        # This requires:
        # 1. reqMktDepth(reqId, contract, numRows, isSmartDepth, mktDepthOptions)
        # 2. Handling updateMktDepth callbacks
        # 3. Building the order book from updates
        
        # For now, return mock data
        return get_market_depth_mock(ticker, levels)
        
    except Exception as e:
        logger.error(f"Failed to get market depth: {e}")
        return get_market_depth_mock(ticker, levels)
