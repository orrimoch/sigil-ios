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
    TARGET_ALLOCATION = 0.90  # Target % of AVAILABLE CASH to deploy (90% = keep 10% buffer)
    MIN_WEIGHT = 0.05         # Minimum 5% of cash per position
    MAX_WEIGHT = 0.40         # Maximum 40% of cash per position
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
        """Size BUY positions using Portfolio-Wide Risk Parity."""
        new_tickers = [d.ticker for d in decisions]
        
        # Get existing portfolio tickers
        existing_tickers = [p.ticker for p in context.portfolio.positions]
        existing_weights = {}
        for p in context.portfolio.positions:
            existing_weights[p.ticker] = p.market_value / context.portfolio.total_value
        
        # Step 1: Get Risk Parity weights considering FULL PORTFOLIO
        rp_weights = await self._portfolio_risk_parity_weights(
            new_tickers=new_tickers,
            existing_tickers=existing_tickers,
            existing_weights=existing_weights,
            context=context
        )
        
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
        
        # Step 3: Convert weights to shares (weights are % of available cash)
        results = []
        available_cash = context.portfolio.cash
        deployment_budget = available_cash * self.TARGET_ALLOCATION  # 90% of cash, keep 10% buffer
        remaining_cash = deployment_budget
        
        logger.info(f"Position sizing: ${available_cash:,.2f} cash, deploying ${deployment_budget:,.2f} ({self.TARGET_ALLOCATION:.0%})")
        
        for decision in decisions:
            weight = final_weights[decision.ticker]
            
            if weight < self.MIN_WEIGHT:
                logger.debug(f"Skipping {decision.ticker}: weight {weight:.2%} below minimum")
                continue
            
            price = await self._get_price(decision.ticker)
            if price <= 0:
                logger.warning(f"Invalid price for {decision.ticker}, skipping")
                continue
            
            # Weight is % of deployment budget (which is 90% of available cash)
            dollars = deployment_budget * weight
            shares = int(dollars / price)
            
            if shares < self.MIN_SHARES:
                logger.debug(f"Skipping {decision.ticker}: {shares} shares below minimum")
                continue
            
            # Check if we have enough cash for this trade
            trade_cost = shares * price
            if trade_cost > remaining_cash:
                # Try to reduce position to fit available cash
                affordable_shares = int(remaining_cash / price)
                if affordable_shares >= self.MIN_SHARES:
                    logger.info(f"Reducing {decision.ticker}: {shares} → {affordable_shares} shares (cash limited)")
                    shares = affordable_shares
                    trade_cost = shares * price
                else:
                    logger.warning(f"Skipping {decision.ticker}: ${trade_cost:,.2f} exceeds available cash ${remaining_cash:,.2f}")
                    continue
            
            # Deduct from remaining cash
            remaining_cash -= trade_cost
            
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
    
    async def _portfolio_risk_parity_weights(
        self,
        new_tickers: List[str],
        existing_tickers: List[str],
        existing_weights: Dict[str, float],
        context: 'TradingContext'
    ) -> Dict[str, float]:
        """
        Calculate Risk Parity weights considering the FULL PORTFOLIO.
        
        This includes:
        1. Existing holdings (fixed weights)
        2. New positions (optimized to balance total portfolio risk)
        3. Correlations BETWEEN existing and new positions
        
        Goal: New positions should balance risk contribution across entire portfolio.
        """
        # Combine all tickers
        all_tickers = list(set(existing_tickers + new_tickers))
        n_total = len(all_tickers)
        n_new = len(new_tickers)
        n_existing = len(existing_tickers)
        
        if n_new == 0:
            return {}
        
        logger.info(f"Portfolio Risk Parity: {n_existing} existing + {n_new} new positions")
        
        # Get full covariance matrix
        cov_matrix = await self._get_covariance_matrix(all_tickers)
        
        if cov_matrix is None:
            logger.warning("Could not calculate full covariance, falling back to simple weights")
            return {ticker: self.TARGET_ALLOCATION / n_new for ticker in new_tickers}
        
        # Build index mapping
        ticker_to_idx = {t: i for i, t in enumerate(all_tickers)}
        
        # Current portfolio weights (existing positions)
        current_weights = np.zeros(n_total)
        for ticker, weight in existing_weights.items():
            if ticker in ticker_to_idx:
                current_weights[ticker_to_idx[ticker]] = weight
        
        # Calculate current portfolio risk contribution
        existing_vol = np.sqrt(current_weights @ cov_matrix @ current_weights) if current_weights.sum() > 0 else 0
        logger.info(f"Existing portfolio volatility: {existing_vol:.1%}")
        
        # Calculate correlation of new stocks with existing portfolio
        new_correlations = {}
        for ticker in new_tickers:
            idx = ticker_to_idx[ticker]
            ticker_vol = np.sqrt(cov_matrix[idx, idx])
            
            if ticker_vol > 0 and existing_vol > 0:
                # Correlation with existing portfolio
                cov_with_portfolio = sum(
                    cov_matrix[idx, ticker_to_idx[ex_ticker]] * existing_weights.get(ex_ticker, 0)
                    for ex_ticker in existing_tickers if ex_ticker in ticker_to_idx
                )
                correlation = cov_with_portfolio / (ticker_vol * existing_vol) if existing_vol > 0 else 0
            else:
                correlation = 0
            
            new_correlations[ticker] = correlation
            logger.debug(f"{ticker}: vol={ticker_vol:.1%}, corr_with_portfolio={correlation:.2f}")
        
        # Optimize new position weights
        # Goal: Equal MARGINAL risk contribution from new positions
        new_indices = [ticker_to_idx[t] for t in new_tickers]
        
        def objective(new_weights_arr):
            """
            Minimize variance of risk contribution among new positions,
            while considering correlation with existing portfolio.
            """
            # Build full weight vector
            full_weights = current_weights.copy()
            for i, idx in enumerate(new_indices):
                full_weights[idx] = new_weights_arr[i]
            
            portfolio_vol = np.sqrt(full_weights @ cov_matrix @ full_weights)
            if portfolio_vol < 1e-8:
                return 0
            
            # Calculate risk contribution of each new position
            marginal_contrib = cov_matrix @ full_weights
            risk_contribs = []
            for i, idx in enumerate(new_indices):
                rc = full_weights[idx] * marginal_contrib[idx] / portfolio_vol
                risk_contribs.append(rc)
            
            risk_contribs = np.array(risk_contribs)
            
            # Minimize variance of risk contributions (equal risk)
            return np.var(risk_contribs)
        
        # Constraints
        constraints = [
            # New positions sum to TARGET_ALLOCATION
            {'type': 'eq', 'fun': lambda w: np.sum(w) - self.TARGET_ALLOCATION}
        ]
        
        # Bounds for new positions
        bounds = [(self.MIN_WEIGHT, self.MAX_WEIGHT) for _ in range(n_new)]
        
        # Initial guess: inverse volatility weighting (less volatile = higher weight)
        initial_weights = []
        for ticker in new_tickers:
            idx = ticker_to_idx[ticker]
            vol = np.sqrt(cov_matrix[idx, idx])
            # Penalize high correlation with existing portfolio (diversification bonus)
            corr_penalty = 1 - 0.3 * abs(new_correlations.get(ticker, 0))
            initial_weights.append((1 / vol if vol > 0 else 1) * corr_penalty)
        
        # Normalize to TARGET_ALLOCATION
        total_init = sum(initial_weights)
        x0 = np.array([w * self.TARGET_ALLOCATION / total_init for w in initial_weights])
        
        try:
            result = minimize(
                objective,
                x0,
                method='SLSQP',
                bounds=bounds,
                constraints=constraints,
                options={'ftol': 1e-8, 'maxiter': 200}
            )
            
            if result.success:
                optimal_weights = {
                    ticker: weight 
                    for ticker, weight in zip(new_tickers, result.x)
                }
                
                # Log the results
                for ticker, weight in optimal_weights.items():
                    corr = new_correlations.get(ticker, 0)
                    logger.info(f"  {ticker}: {weight:.1%} weight (corr={corr:.2f})")
                
                return optimal_weights
            else:
                logger.warning(f"Portfolio optimization failed: {result.message}")
        except Exception as e:
            logger.warning(f"Portfolio optimization error: {e}")
        
        # Fallback: inverse volatility with correlation penalty
        logger.info("Using inverse-volatility fallback with correlation adjustment")
        fallback = {}
        for ticker in new_tickers:
            idx = ticker_to_idx[ticker]
            vol = np.sqrt(cov_matrix[idx, idx])
            corr = new_correlations.get(ticker, 0)
            # Lower weight if highly correlated with existing portfolio
            weight = (1 / vol if vol > 0 else 1) * (1 - 0.3 * abs(corr))
            fallback[ticker] = weight
        
        # Normalize
        total = sum(fallback.values())
        return {k: v * self.TARGET_ALLOCATION / total for k, v in fallback.items()}
    
    async def _risk_parity_weights(self, tickers: List[str]) -> Dict[str, float]:
        """
        Calculate Risk Parity weights (standalone, without existing portfolio).
        
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
