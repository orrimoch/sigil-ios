"""
Risk Parity Position Sizing (REC-283)

Determines exact share counts using Risk Parity optimization:
1. Calculate equal-risk weights via covariance matrix
2. Apply conviction multiplier (higher score = bigger position)
3. Apply regime multiplier (crisis = smaller positions)
4. Convert weights to share counts

Each position contributes equal RISK, not equal DOLLARS.
"""

import numpy as np
from scipy.optimize import minimize
from dataclasses import dataclass
from typing import List, Dict, Optional
from datetime import datetime
from pathlib import Path
from loguru import logger
import yfinance as yf

# Add src to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))


@dataclass
class SizedPosition:
    """A sized trading position ready for execution."""
    ticker: str
    action: str  # "BUY" or "SELL"
    shares: int
    dollars: float
    weight: float  # Portfolio weight (0-1)
    price: float
    rationale: str  # Sizing breakdown
    
    def to_dict(self) -> Dict:
        return {
            "ticker": self.ticker,
            "action": self.action,
            "shares": self.shares,
            "dollars": self.dollars,
            "weight": self.weight,
            "price": self.price,
            "rationale": self.rationale,
        }


@dataclass 
class TradeDecision:
    """Input to position sizer from decision engine."""
    ticker: str
    action: str  # "BUY" or "SELL"
    score: float
    confidence: float
    sector: str
    rationale: str


class PositionSizer:
    """
    Position sizing using Risk Parity + conviction + regime adjustments.
    
    Pipeline:
    1. Risk Parity: Equal risk contribution (covariance-based)
    2. Conviction: Score ≥85 → larger position
    3. Regime: Crisis → smaller positions
    4. Limits: Cap at 10% per position
    
    Usage:
        sizer = PositionSizer()
        positions = await sizer.size_positions(decisions, context)
    """
    
    # Configuration
    LOOKBACK_DAYS = 60        # Days of history for covariance
    TARGET_ALLOCATION = 0.40  # Target total allocation for new trades
    MIN_WEIGHT = 0.02         # Minimum 2% per position
    MAX_WEIGHT = 0.10         # Maximum 10% per position
    MIN_SHARES = 1            # Minimum shares to trade
    
    def __init__(self, lookback_days: int = None):
        self.lookback_days = lookback_days or self.LOOKBACK_DAYS
        self._price_cache: Dict[str, float] = {}
        self._cov_cache: Optional[Dict] = None
    
    async def size_positions(
        self,
        decisions: List[TradeDecision],
        context: 'TradingContext'
    ) -> List[SizedPosition]:
        """
        Size all positions using Risk Parity optimization.
        
        Args:
            decisions: List of BUY/SELL decisions from decision engine
            context: Current trading context (portfolio, market state)
            
        Returns:
            List of SizedPosition ready for execution
        """
        if not decisions:
            return []
        
        results = []
        buy_decisions = [d for d in decisions if d.action == "BUY"]
        sell_decisions = [d for d in decisions if d.action == "SELL"]
        
        # Handle BUY decisions
        if buy_decisions:
            buy_positions = await self._size_buys(buy_decisions, context)
            results.extend(buy_positions)
        
        # Handle SELL decisions (full exit)
        for decision in sell_decisions:
            sell_position = await self._size_sell(decision, context)
            if sell_position:
                results.append(sell_position)
        
        return results
    
    async def _size_buys(
        self, 
        decisions: List[TradeDecision],
        context: 'TradingContext'
    ) -> List[SizedPosition]:
        """Size BUY positions using Risk Parity."""
        tickers = [d.ticker for d in decisions]
        
        # Step 1: Get Risk Parity weights
        rp_weights = await self._risk_parity_weights(tickers)
        
        # Step 2: Apply conviction and regime adjustments
        final_weights = {}
        for decision in decisions:
            base = rp_weights.get(decision.ticker, 0.05)
            conviction = self._conviction_multiplier(decision.score)
            regime = self._regime_multiplier(context.market.regime)
            
            adjusted = base * conviction * regime
            final_weights[decision.ticker] = min(adjusted, self.MAX_WEIGHT)
        
        # Normalize if total exceeds TARGET_ALLOCATION
        total = sum(final_weights.values())
        if total > self.TARGET_ALLOCATION:
            scale = self.TARGET_ALLOCATION / total
            final_weights = {k: v * scale for k, v in final_weights.items()}
        
        # Step 3: Convert weights to shares
        results = []
        portfolio_value = context.portfolio.total_value
        
        for decision in decisions:
            weight = final_weights[decision.ticker]
            
            if weight < self.MIN_WEIGHT:
                logger.debug(f"Skipping {decision.ticker}: weight {weight:.2%} below minimum")
                continue
            
            price = await self._get_price(decision.ticker)
            if price <= 0:
                logger.warning(f"Invalid price for {decision.ticker}, skipping")
                continue
            
            dollars = portfolio_value * weight
            shares = int(dollars / price)
            
            if shares < self.MIN_SHARES:
                logger.debug(f"Skipping {decision.ticker}: {shares} shares below minimum")
                continue
            
            # Build rationale
            base_weight = rp_weights.get(decision.ticker, 0.05)
            conviction = self._conviction_multiplier(decision.score)
            regime = self._regime_multiplier(context.market.regime)
            
            rationale = (
                f"Risk Parity {base_weight:.1%} × "
                f"conviction {conviction:.2f} × "
                f"regime {regime:.2f} = {weight:.1%}"
            )
            
            results.append(SizedPosition(
                ticker=decision.ticker,
                action="BUY",
                shares=shares,
                dollars=shares * price,
                weight=weight,
                price=price,
                rationale=rationale,
            ))
        
        return results
    
    async def _size_sell(
        self, 
        decision: TradeDecision, 
        context: 'TradingContext'
    ) -> Optional[SizedPosition]:
        """Size a SELL (full exit)."""
        # Find position in portfolio
        position = None
        for p in context.portfolio.positions:
            if p.ticker == decision.ticker:
                position = p
                break
        
        if not position:
            logger.warning(f"No position found for {decision.ticker}")
            return None
        
        return SizedPosition(
            ticker=decision.ticker,
            action="SELL",
            shares=position.shares,
            dollars=position.shares * position.current_price,
            weight=0,  # Exiting
            price=position.current_price,
            rationale="Full exit - SELL signal",
        )
    
    async def _risk_parity_weights(self, tickers: List[str]) -> Dict[str, float]:
        """
        Calculate Risk Parity weights.
        
        Each position contributes equal risk to the portfolio.
        Uses covariance matrix to measure risk contribution.
        """
        n = len(tickers)
        
        if n == 0:
            return {}
        
        if n == 1:
            return {tickers[0]: 0.05}  # Default 5%
        
        # Fetch returns and calculate covariance
        cov_matrix = await self._get_covariance_matrix(tickers)
        
        if cov_matrix is None:
            # Fallback to equal weights
            logger.warning("Could not calculate covariance, using equal weights")
            return {ticker: self.TARGET_ALLOCATION / n for ticker in tickers}
        
        # Optimize for equal risk contribution
        target_risk = np.ones(n) / n
        
        def objective(weights):
            """Minimize difference from equal risk contribution."""
            portfolio_vol = np.sqrt(weights @ cov_matrix @ weights)
            if portfolio_vol < 1e-8:
                return 0
            
            marginal_contrib = cov_matrix @ weights
            risk_contrib = weights * marginal_contrib / portfolio_vol
            
            # Squared difference from target
            return np.sum((risk_contrib - target_risk * portfolio_vol) ** 2)
        
        # Constraints: weights sum to TARGET_ALLOCATION
        constraints = [
            {'type': 'eq', 'fun': lambda w: np.sum(w) - self.TARGET_ALLOCATION}
        ]
        
        # Bounds: MIN_WEIGHT to MAX_WEIGHT per position
        bounds = [(self.MIN_WEIGHT, self.MAX_WEIGHT) for _ in range(n)]
        
        # Initial guess: equal weights
        x0 = np.ones(n) * self.TARGET_ALLOCATION / n
        
        try:
            result = minimize(
                objective, 
                x0, 
                method='SLSQP',
                bounds=bounds, 
                constraints=constraints,
                options={'ftol': 1e-8}
            )
            
            if result.success:
                return {ticker: weight for ticker, weight in zip(tickers, result.x)}
            else:
                logger.warning(f"Optimization failed: {result.message}")
        except Exception as e:
            logger.warning(f"Optimization error: {e}")
        
        # Fallback to equal weights
        return {ticker: self.TARGET_ALLOCATION / n for ticker in tickers}
    
    def _conviction_multiplier(self, score: float) -> float:
        """
        Higher score = larger position.
        
        Score 70 → 0.85 (below avg)
        Score 85 → 1.0 (baseline)
        Score 100 → 1.15 (above avg)
        """
        return 0.85 + (score - 70) / 100
    
    def _regime_multiplier(self, regime: str) -> float:
        """
        Crisis = smaller positions.
        
        Maps market regime to position scaling factor.
        """
        return {
            "low_vol": 1.1,     # Low volatility → slightly larger
            "normal": 1.0,      # Normal → no adjustment
            "high_vol": 0.7,    # High volatility → reduce 30%
            "crisis": 0.5,      # Crisis → reduce 50%
        }.get(regime, 1.0)
    
    async def _get_covariance_matrix(self, tickers: List[str]) -> Optional[np.ndarray]:
        """
        Fetch price history and compute covariance matrix.
        
        Uses daily returns over lookback period.
        Returns annualized covariance matrix.
        """
        try:
            # Download historical data
            data = yf.download(
                tickers, 
                period=f"{self.lookback_days}d", 
                progress=False,
                auto_adjust=True
            )
            
            if data.empty:
                return None
            
            # Handle single ticker case
            if len(tickers) == 1:
                if 'Close' in data.columns:
                    returns = data['Close'].pct_change().dropna()
                else:
                    returns = data.pct_change().dropna()
                variance = returns.var() * 252
                return np.array([[variance]])
            
            # Multi-ticker case
            prices = data['Close'] if 'Close' in data.columns else data
            returns = prices.pct_change().dropna()
            
            # Annualized covariance matrix
            cov_matrix = returns.cov().values * 252
            
            return cov_matrix
            
        except Exception as e:
            logger.error(f"Error calculating covariance: {e}")
            return None
    
    async def _get_price(self, ticker: str) -> float:
        """Get current price for a ticker."""
        if ticker in self._price_cache:
            return self._price_cache[ticker]
        
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="1d")
            
            if not hist.empty:
                price = float(hist['Close'].iloc[-1])
                self._price_cache[ticker] = price
                return price
                
        except Exception as e:
            logger.error(f"Error fetching price for {ticker}: {e}")
        
        return 0.0
    
    def clear_cache(self):
        """Clear price and covariance caches."""
        self._price_cache.clear()
        self._cov_cache = None


# Convenience function
async def size_positions(
    decisions: List[TradeDecision], 
    context: 'TradingContext'
) -> List[SizedPosition]:
    """Convenience function to size positions."""
    sizer = PositionSizer()
    return await sizer.size_positions(decisions, context)


# CLI
if __name__ == "__main__":
    import asyncio
    import argparse
    
    parser = argparse.ArgumentParser(description="Position Sizing Calculator")
    parser.add_argument("--tickers", "-t", nargs="+", required=True, help="Tickers to size")
    parser.add_argument("--portfolio", "-p", type=float, default=100000, help="Portfolio value")
    parser.add_argument("--regime", "-r", default="normal", help="Market regime")
    
    args = parser.parse_args()
    
    async def main():
        # Create mock decisions
        decisions = [
            TradeDecision(
                ticker=t,
                action="BUY",
                score=85,  # Default score
                confidence=0.8,
                sector="Unknown",
                rationale="Test"
            )
            for t in args.tickers
        ]
        
        # Create mock context
        from context import PortfolioState, MarketState, TradingContext
        
        context = TradingContext(
            timestamp=datetime.now(),
            portfolio=PortfolioState(
                cash=args.portfolio,
                total_value=args.portfolio,
                positions=[],
                sector_exposure={},
                unrealized_pnl=0,
            ),
            market=MarketState(
                regime=args.regime,
                regime_confidence=0.8,
                vix=20.0,
            ),
            buy_candidates=[],
            sell_candidates=[],
            hold_review=[],
            data_freshness=None,
        )
        
        # Size positions
        sizer = PositionSizer()
        positions = await sizer.size_positions(decisions, context)
        
        print(f"\n=== Position Sizing (${args.portfolio:,.0f} portfolio, {args.regime} regime) ===\n")
        
        total = 0
        for p in positions:
            print(f"{p.ticker}:")
            print(f"  Shares: {p.shares}")
            print(f"  Dollars: ${p.dollars:,.2f} ({p.weight:.1%})")
            print(f"  Price: ${p.price:.2f}")
            print(f"  {p.rationale}")
            print()
            total += p.dollars
        
        print(f"Total allocation: ${total:,.2f} ({total/args.portfolio:.1%})")
    
    asyncio.run(main())
