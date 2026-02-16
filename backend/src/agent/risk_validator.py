"""
Risk Validator Module (REC-286)

Validates trades against risk constraints:
1. Position limit: max 10% per position
2. Sector limit: max 30% per sector
3. Portfolio VaR: max 2% daily
4. Correlation: reduce if >80% correlated
5. Daily loss: 3% halts all trading

Can REDUCE position size or BLOCK trade entirely.
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
from datetime import datetime
from pathlib import Path
from loguru import logger

# Add src to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.position_sizing import SizedPosition


@dataclass
class RiskValidation:
    """Result of risk validation for a trade."""
    passed: bool
    original_shares: int
    adjusted_shares: int
    original_dollars: float
    adjusted_dollars: float
    violations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    @property
    def was_reduced(self) -> bool:
        return self.adjusted_shares < self.original_shares
    
    @property
    def was_blocked(self) -> bool:
        return self.adjusted_shares == 0


@dataclass
class PortfolioRiskState:
    """Current portfolio risk state."""
    daily_pnl_pct: float = 0.0
    portfolio_var: float = 0.0
    sector_exposure: Dict[str, float] = field(default_factory=dict)
    position_weights: Dict[str, float] = field(default_factory=dict)
    correlations: Dict[str, Dict[str, float]] = field(default_factory=dict)


class RiskValidator:
    """
    Validates trades against risk constraints.
    
    Can reduce or block trades that violate limits.
    
    Usage:
        validator = RiskValidator()
        result = await validator.validate(trade, context)
        if not result.passed:
            print(f"Violations: {result.violations}")
    """
    
    # Risk Limits (configurable)
    MAX_POSITION_PCT = 0.10      # 10% max per position
    MAX_SECTOR_PCT = 0.30        # 30% max per sector
    MAX_PORTFOLIO_VAR = 0.02     # 2% daily VaR limit
    MAX_CORRELATION = 0.80       # Reduce if correlated with existing
    DAILY_LOSS_LIMIT = -0.03    # 3% loss halts trading
    
    def __init__(
        self,
        max_position_pct: float = None,
        max_sector_pct: float = None,
        max_var: float = None,
        max_correlation: float = None,
        daily_loss_limit: float = None
    ):
        self.max_position_pct = max_position_pct or self.MAX_POSITION_PCT
        self.max_sector_pct = max_sector_pct or self.MAX_SECTOR_PCT
        self.max_var = max_var or self.MAX_PORTFOLIO_VAR
        self.max_correlation = max_correlation or self.MAX_CORRELATION
        self.daily_loss_limit = daily_loss_limit or self.DAILY_LOSS_LIMIT
    
    async def validate(
        self,
        trade: SizedPosition,
        context: 'TradingContext'
    ) -> RiskValidation:
        """
        Validate a single trade against all risk limits.
        
        Returns RiskValidation with adjusted shares if needed.
        """
        violations = []
        warnings = []
        adjusted_shares = trade.shares
        
        # Skip validation for SELL (exits)
        if trade.action == "SELL":
            return RiskValidation(
                passed=True,
                original_shares=trade.shares,
                adjusted_shares=trade.shares,
                original_dollars=trade.dollars,
                adjusted_dollars=trade.dollars,
            )
        
        # Check 1: Daily loss limit (blocks all trading)
        daily_pnl_pct = self._get_daily_pnl_pct(context)
        if daily_pnl_pct < self.daily_loss_limit:
            violations.append(
                f"Daily loss limit exceeded ({daily_pnl_pct:.1%} < {self.daily_loss_limit:.1%}) - trading halted"
            )
            return RiskValidation(
                passed=False,
                original_shares=trade.shares,
                adjusted_shares=0,
                original_dollars=trade.dollars,
                adjusted_dollars=0,
                violations=violations,
            )
        
        # Check 2: Position limit
        position_check = self._check_position_limit(trade, context)
        if not position_check[0]:
            violations.append(position_check[1])
            adjusted_shares = min(adjusted_shares, position_check[2])
        
        # Check 3: Sector limit
        sector_check = await self._check_sector_limit(trade, context)
        if not sector_check[0]:
            violations.append(sector_check[1])
            adjusted_shares = min(adjusted_shares, sector_check[2])
        
        # Check 4: Portfolio VaR (warning only for now)
        var_check = await self._check_portfolio_var(trade, context)
        if not var_check[0]:
            warnings.append(var_check[1])
            # Don't reduce for VaR, just warn
        
        # Check 5: Correlation with existing
        corr_check = await self._check_correlation(trade, context)
        if not corr_check[0]:
            warnings.append(corr_check[1])
            adjusted_shares = min(adjusted_shares, corr_check[2])
        
        # Calculate adjusted dollars
        price = trade.price if trade.price > 0 else (trade.dollars / trade.shares if trade.shares > 0 else 0)
        adjusted_dollars = adjusted_shares * price
        
        return RiskValidation(
            passed=len(violations) == 0 and adjusted_shares > 0,
            original_shares=trade.shares,
            adjusted_shares=adjusted_shares,
            original_dollars=trade.dollars,
            adjusted_dollars=adjusted_dollars,
            violations=violations,
            warnings=warnings,
        )
    
    async def validate_batch(
        self,
        trades: List[SizedPosition],
        context: 'TradingContext'
    ) -> List[Tuple[SizedPosition, RiskValidation]]:
        """
        Validate multiple trades.
        
        Returns list of (trade, validation) tuples.
        """
        results = []
        for trade in trades:
            validation = await self.validate(trade, context)
            results.append((trade, validation))
        return results
    
    def _get_daily_pnl_pct(self, context: 'TradingContext') -> float:
        """Get today's P&L as percentage of portfolio."""
        if context.portfolio.total_value <= 0:
            return 0
        
        # realized_pnl_today might be 0 if not tracked
        daily_pnl = context.portfolio.realized_pnl_today
        return daily_pnl / context.portfolio.total_value
    
    def _check_position_limit(
        self,
        trade: SizedPosition,
        context: 'TradingContext'
    ) -> Tuple[bool, str, int]:
        """Ensure position doesn't exceed max_position_pct of portfolio."""
        portfolio_value = context.portfolio.total_value
        if portfolio_value <= 0:
            return (False, "Invalid portfolio value", 0)
        
        max_dollars = portfolio_value * self.max_position_pct
        price = trade.price if trade.price > 0 else (trade.dollars / trade.shares if trade.shares > 0 else 1)
        max_shares = int(max_dollars / price) if price > 0 else 0
        
        if trade.dollars > max_dollars:
            return (
                False,
                f"Position exceeds {self.max_position_pct:.0%} limit "
                f"(${trade.dollars:,.0f} > ${max_dollars:,.0f})",
                max_shares
            )
        
        return (True, "", trade.shares)
    
    async def _check_sector_limit(
        self,
        trade: SizedPosition,
        context: 'TradingContext'
    ) -> Tuple[bool, str, int]:
        """Ensure sector doesn't exceed max_sector_pct of portfolio."""
        # Get stock sector
        try:
            sector = await self._get_sector(trade.ticker)
        except Exception as e:
            logger.warning(f"Sector lookup failed for {trade.ticker}: {e}")
            sector = "Unknown"
        
        # Current sector exposure
        current_exposure = context.portfolio.sector_exposure.get(sector, 0)
        
        # New exposure if trade executes
        portfolio_value = context.portfolio.total_value
        if portfolio_value <= 0:
            return (False, "Invalid portfolio value", 0)
        
        new_weight = trade.dollars / portfolio_value
        new_exposure = current_exposure + new_weight
        
        if new_exposure > self.max_sector_pct:
            # Calculate max allowed weight
            allowed_weight = max(0, self.max_sector_pct - current_exposure)
            allowed_dollars = allowed_weight * portfolio_value
            price = trade.price if trade.price > 0 else (trade.dollars / trade.shares if trade.shares > 0 else 1)
            allowed_shares = int(allowed_dollars / price) if price > 0 else 0
            
            return (
                False,
                f"Sector {sector} would exceed {self.max_sector_pct:.0%} limit "
                f"({new_exposure:.1%} after trade)",
                allowed_shares
            )
        
        return (True, "", trade.shares)
    
    async def _check_portfolio_var(
        self,
        trade: SizedPosition,
        context: 'TradingContext'
    ) -> Tuple[bool, str, int]:
        """Check if trade would push portfolio VaR over limit."""
        try:
            # Try to use existing VaR calculator
            from risk.portfolio_var import calculate_portfolio_var
            
            # This is a simplified check - full implementation would
            # calculate new VaR with the proposed trade
            current_var = await calculate_portfolio_var(context.portfolio)
            
            if current_var > self.max_var:
                return (
                    False,
                    f"Portfolio VaR ({current_var:.2%}) exceeds {self.max_var:.1%} limit",
                    trade.shares  # Don't reduce, just warn
                )
        except Exception as e:
            logger.debug(f"VaR check skipped: {e}")
        
        return (True, "", trade.shares)
    
    async def _check_correlation(
        self,
        trade: SizedPosition,
        context: 'TradingContext'
    ) -> Tuple[bool, str, int]:
        """Check correlation with existing holdings."""
        if not context.portfolio.positions:
            return (True, "", trade.shares)
        
        try:
            # Get correlations with existing positions
            max_corr = 0.0
            correlated_with = ""
            
            for position in context.portfolio.positions:
                corr = await self._get_correlation(trade.ticker, position.ticker)
                if corr > max_corr:
                    max_corr = corr
                    correlated_with = position.ticker
            
            if max_corr > self.max_correlation:
                # Reduce position by correlation factor
                reduction = 1 - (max_corr - self.max_correlation)
                adjusted_shares = int(trade.shares * reduction)
                
                return (
                    False,
                    f"High correlation ({max_corr:.0%}) with {correlated_with}",
                    adjusted_shares
                )
        except Exception as e:
            logger.debug(f"Correlation check skipped: {e}")
        
        return (True, "", trade.shares)
    
    async def _get_sector(self, ticker: str) -> str:
        """Get sector for a ticker."""
        try:
            import yfinance as yf
            stock = yf.Ticker(ticker)
            info = stock.info
            return info.get("sector", "Unknown")
        except:
            return "Unknown"
    
    async def _get_correlation(self, ticker1: str, ticker2: str) -> float:
        """Get correlation between two tickers."""
        try:
            import yfinance as yf
            
            data = yf.download(
                [ticker1, ticker2],
                period="60d",
                progress=False,
                auto_adjust=True
            )
            
            if data.empty or len(data) < 20:
                return 0.0
            
            returns = data['Close'].pct_change().dropna()
            
            if len(returns.columns) < 2:
                return 0.0
            
            corr = returns.corr().iloc[0, 1]
            return float(corr) if not np.isnan(corr) else 0.0
            
        except Exception as e:
            logger.debug(f"Correlation fetch failed: {e}")
            return 0.0


# Convenience function
async def validate_trades(
    trades: List[SizedPosition],
    context: 'TradingContext',
    **kwargs
) -> List[Tuple[SizedPosition, RiskValidation]]:
    """Convenience function to validate multiple trades."""
    validator = RiskValidator(**kwargs)
    return await validator.validate_batch(trades, context)


# CLI
if __name__ == "__main__":
    import asyncio
    import argparse
    
    parser = argparse.ArgumentParser(description="Risk Validator CLI")
    parser.add_argument("--ticker", "-t", required=True, help="Ticker to validate")
    parser.add_argument("--shares", "-s", type=int, default=100, help="Number of shares")
    parser.add_argument("--price", "-p", type=float, default=100.0, help="Price per share")
    
    args = parser.parse_args()
    
    async def main():
        from agent.context import aggregate_context
        
        # Get context
        print("Getting portfolio context...")
        context = await aggregate_context()
        
        # Create mock trade
        trade = SizedPosition(
            ticker=args.ticker,
            action="BUY",
            shares=args.shares,
            dollars=args.shares * args.price,
            weight=0.05,
            price=args.price,
            rationale="Test trade",
        )
        
        # Validate
        print(f"\nValidating: BUY {args.shares} {args.ticker} @ ${args.price}")
        print(f"Total: ${trade.dollars:,.2f}")
        print(f"Portfolio: ${context.portfolio.total_value:,.0f}")
        print("-" * 40)
        
        validator = RiskValidator()
        result = await validator.validate(trade, context)
        
        if result.passed:
            print("✅ PASSED")
        else:
            print("❌ BLOCKED/REDUCED")
        
        if result.violations:
            print("\nViolations:")
            for v in result.violations:
                print(f"  ⛔ {v}")
        
        if result.warnings:
            print("\nWarnings:")
            for w in result.warnings:
                print(f"  ⚠️ {w}")
        
        if result.was_reduced:
            print(f"\nAdjusted: {result.original_shares} → {result.adjusted_shares} shares")
            print(f"Amount: ${result.original_dollars:,.0f} → ${result.adjusted_dollars:,.0f}")
    
    asyncio.run(main())
