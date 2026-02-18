"""
Decision Engine with Claude (REC-285)

Uses Claude to synthesize context + memory into trading decisions.
Extended thinking enabled for deep analysis.
"""

import json
import os
from dataclasses import dataclass
from typing import List, Dict, Optional, Any
from datetime import datetime
from pathlib import Path
from loguru import logger

# REC-312: Retry logic for API resilience
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

# Add src to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from .position_sizing import TradeDecision
from .memory import Memory


# Default model (Haiku for cost efficiency)
DEFAULT_MODEL = "claude-3-haiku-20240307"  # REC-304: updated from deprecated 20241022

SYSTEM_PROMPT = """You are an expert portfolio manager for Sigil, an AI-powered trading system.

Your job is to review the current market context, portfolio state, constraints, and historical similar situations, then decide which trades to make this week.

## TRADING PHILOSOPHY
- Capture weekly trends, not intraday moves
- Maximum 3-5 trades per week (quality over quantity)
- Hold positions for 5-30 days
- Risk-aware: respect ALL constraints provided
- When in doubt, don't trade (preserve capital)

## STRATEGIC BIAS (OWNER PREFERENCE)
AI and data infrastructure will dominate for the next decade. Apply these biases:

**STRONGLY FAVOR (boost confidence +15%):**
- Nano photonics / silicon photonics (LITE, COHR, II-VI, POET, Cisco optics)
- Data center infrastructure (NVDA, AMD, AVGO, MRVL, ANET, VRT, EQIX)
- AI semiconductors & accelerators (NVDA, AMD, INTC, QCOM, ARM, MCHP)
- AI cloud & compute (GOOGL, MSFT, AMZN, META, ORCL)
- AI networking (ANET, CSCO, JNPR)

**MODERATELY FAVOR (boost confidence +10%):**
- Semiconductor equipment (ASML, LRCX, AMAT, KLAC)
- Memory for AI workloads (MU, WDC, STX)
- Edge AI / robotics (ISRG, IONQ, quantum computing)

**When choosing between similar-scored candidates, prefer the AI/data center play.**
**A score of 72 in AI infrastructure > score of 78 in traditional sectors.**

## DECISION RULES
- BUY when: score ≥75, regime is calm/normal, sector not overweight, within cash budget
- HOLD when: score ≥60, position healthy
- SELL when: score <60, OR stop-loss triggered, OR regime is crisis + position losing

## SELL TIERS (automatic sizing by system)
When you recommend SELL, the system will size it based on score:
- Score < 40: Full exit (100% of position)
- Score 40-50: Trim 50% of position
- Score 50-60: Trim 25% of position
- Stop-loss hit (down >8%): Full exit regardless of score
- Severe loss (down >15%): Full exit regardless of score

**You just recommend SELL - the system handles partial vs full exit.**

## CONSTRAINT RULES (MUST FOLLOW)
1. NEVER recommend total BUY value exceeding available cash
2. NEVER recommend a single position exceeding max position size
3. AVOID adding to sectors marked as OVERWEIGHT (>25% exposure)
4. PREFER sectors marked as UNDERWEIGHT for diversification
5. In CRISIS regime: only SELL or small defensive BUYs
6. In ELEVATED VIX (>25): reduce position sizes mentally by 20%

## OUTPUT FORMAT
For each decision, provide:
- action: "BUY" or "SELL"
- ticker: Stock symbol
- rationale: 2-3 sentences explaining WHY (reference score, regime, diversification, constraints)
- confidence: 0.0-1.0

IMPORTANT: Output ONLY a valid JSON array. No markdown, no explanation outside the JSON.

Example:
[
  {"action": "BUY", "ticker": "CMI", "rationale": "Score 89.8 exceptional. Industrials underweight at 8%, adds diversification. Within $15K position limit.", "confidence": 0.85},
  {"action": "SELL", "ticker": "XYZ", "rationale": "Score dropped to 35. Position -12% underwater. Cut losses per risk rules.", "confidence": 0.90}
]

If no trades fit constraints, return empty array: []
"""


@dataclass
class DecisionResult:
    """Result from decision engine."""
    decisions: List[TradeDecision]
    thinking: Optional[str] = None  # Claude's thinking process
    raw_response: Optional[str] = None
    model: str = DEFAULT_MODEL
    tokens_used: int = 0


class DecisionEngine:
    """
    Uses Claude to make trading decisions based on context and memory.
    
    Usage:
        engine = DecisionEngine()
        result = await engine.decide(context, memories)
        for decision in result.decisions:
            print(f"{decision.action} {decision.ticker}: {decision.rationale}")
    """
    
    def __init__(
        self,
        api_key: str = None,
        model: str = DEFAULT_MODEL,
        thinking_budget: int = 2000  # Haiku limit is 4096 total
    ):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.model = model
        self.thinking_budget = thinking_budget
        self._client = None
    
    async def decide(
        self,
        context: 'TradingContext',
        memories: List[Memory],
        max_decisions: int = 5
    ) -> DecisionResult:
        """
        Make trading decisions based on context and similar past situations.
        
        Args:
            context: Current trading context (portfolio, market, candidates)
            memories: Similar past situations with outcomes
            max_decisions: Maximum number of decisions to return
            
        Returns:
            DecisionResult with list of TradeDecision
        """
        # Build prompt
        prompt = self._build_prompt(context, memories)
        
        try:
            # Call Claude
            response = await self._call_claude(prompt)
            
            # Parse decisions
            decisions = self._parse_response(response, context, max_decisions)
            
            return DecisionResult(
                decisions=decisions,
                thinking=response.get("thinking"),
                raw_response=response.get("content"),
                model=self.model,
                tokens_used=response.get("tokens", 0),
            )
            
        except Exception as e:
            logger.error(f"Decision engine error: {e}")
            return DecisionResult(
                decisions=[],
                raw_response=str(e),
                model=self.model,
            )
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((Exception,)),  # Retry on any exception
        before_sleep=before_sleep_log(logger, "WARNING"),
        reraise=True,
    )
    async def _call_claude(self, prompt: str) -> Dict[str, Any]:
        """Call Claude API with extended thinking and retry logic (REC-312)."""
        try:
            import anthropic
            
            if self._client is None:
                self._client = anthropic.AsyncAnthropic(api_key=self.api_key)
            
            # Check if model supports extended thinking (only Sonnet, not Haiku)
            use_thinking = ("sonnet" in self.model.lower()) and ("haiku" not in self.model.lower())
            
            kwargs = {
                "model": self.model,
                "max_tokens": 4096,  # Haiku limit
                "system": SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": prompt}],
            }
            
            # Add thinking for supported models
            if use_thinking:
                kwargs["thinking"] = {
                    "type": "enabled",
                    "budget_tokens": self.thinking_budget  # Default 5000
                }
                kwargs["max_tokens"] = max(kwargs["max_tokens"], self.thinking_budget + 3000)
            
            response = await self._client.messages.create(**kwargs)
            
            # Extract content and thinking
            content = ""
            thinking = ""
            
            for block in response.content:
                if hasattr(block, 'text'):
                    content = block.text
                elif hasattr(block, 'thinking'):
                    thinking = block.thinking
            
            return {
                "content": content,
                "thinking": thinking if thinking else None,
                "tokens": response.usage.input_tokens + response.usage.output_tokens,
            }
            
        except ImportError:
            logger.warning("anthropic package not installed, using mock response")
            return self._mock_response(prompt)
        except Exception as e:
            logger.error(f"Claude API error: {e}")
            raise
    
    def _mock_response(self, prompt: str) -> Dict[str, Any]:
        """Mock response for testing without API key."""
        # Extract top candidate from prompt if possible
        if "BUY Candidates" in prompt:
            lines = prompt.split("\n")
            for line in lines:
                if line.strip().startswith("- ") and "Score" in line:
                    # Parse "- CMI: Score 89.8 ..."
                    parts = line.strip("- ").split(":")
                    if parts:
                        ticker = parts[0].strip()
                        return {
                            "content": json.dumps([{
                                "action": "BUY",
                                "ticker": ticker,
                                "rationale": "Top scoring candidate with strong fundamentals.",
                                "confidence": 0.75
                            }]),
                            "thinking": "Mock response - selected top candidate",
                            "tokens": 100,
                        }
        
        return {
            "content": "[]",
            "thinking": "Mock response - no clear candidates",
            "tokens": 50,
        }
    
    def _build_prompt(
        self,
        context: 'TradingContext',
        memories: List[Memory]
    ) -> str:
        """Build the prompt with all context and memories."""
        sections = []
        
        # Portfolio section
        portfolio = context.portfolio
        
        # Calculate constraints
        max_position_pct = 0.10  # 10% max per position
        max_position_dollars = portfolio.total_value * max_position_pct
        max_sector_pct = 0.30  # 30% max per sector
        
        # Identify overweight/underweight sectors
        overweight_sectors = []
        underweight_sectors = []
        for sector, weight in portfolio.sector_exposure.items():
            if sector == "Cash":
                continue
            if weight > 0.25:
                overweight_sectors.append(f"{sector} ({weight:.0%})")
            elif weight < 0.10:
                underweight_sectors.append(f"{sector} ({weight:.0%})")
        
        # Get current holdings list
        current_holdings = []
        if hasattr(portfolio, 'positions') and portfolio.positions:
            current_holdings = [p.ticker for p in portfolio.positions]
        
        sections.append(f"""## Current Portfolio
- Available Cash: ${portfolio.cash:,.0f}
- Total Portfolio Value: ${portfolio.total_value:,.0f}
- Number of Positions: {portfolio.position_count}
- Unrealized P&L: ${portfolio.unrealized_pnl:+,.0f}

### Current Holdings
{', '.join(current_holdings) if current_holdings else 'None'}

### Sector Exposure
{self._format_sectors(portfolio.sector_exposure)}

## CONSTRAINTS (MUST FOLLOW)
- Max BUY budget: ${portfolio.cash:,.0f} (your available cash)
- Max position size: ${max_position_dollars:,.0f} ({max_position_pct:.0%} of portfolio)
- Max sector exposure: {max_sector_pct:.0%}
- Overweight sectors (AVOID adding): {', '.join(overweight_sectors) if overweight_sectors else 'None'}
- Underweight sectors (PREFER): {', '.join(underweight_sectors) if underweight_sectors else 'None'}
""")
        
        # Market section with risk warnings
        market = context.market
        
        # Generate risk warnings based on conditions
        risk_warnings = []
        if market.regime == "crisis":
            risk_warnings.append("⚠️ CRISIS REGIME: Only defensive actions recommended")
        elif market.regime == "high_volatility":
            risk_warnings.append("⚠️ HIGH VOLATILITY: Consider smaller position sizes")
        
        vix = market.vix or 0
        if vix > 30:
            risk_warnings.append(f"⚠️ VIX ELEVATED ({vix:.0f}): Reduce position sizes by 30%")
        elif vix > 25:
            risk_warnings.append(f"⚠️ VIX ELEVATED ({vix:.0f}): Reduce position sizes by 20%")
        elif vix > 20:
            risk_warnings.append(f"⚠️ VIX ABOVE NORMAL ({vix:.0f}): Be cautious")
        
        risk_section = "\n".join(risk_warnings) if risk_warnings else "✅ No elevated risk warnings"
        
        sections.append(f"""## Market State
- Regime: {market.regime} (confidence: {(market.regime_confidence or 0):.0%})
- VIX: {(market.vix or 0):.1f} ({market.vix_regime or 'unknown'})
- Trend: {market.trend}

### Risk Warnings
{risk_section}
""")
        
        # Candidates section
        sections.append(f"""## BUY Candidates (Top 10)
{self._format_candidates(context.buy_candidates[:10])}

## SELL Candidates (Current Holdings)
{self._format_candidates(context.sell_candidates)}
""")
        
        # Memory section
        if memories:
            sections.append(f"""## Similar Past Situations
{self._format_memories(memories)}
""")
        else:
            sections.append("## Similar Past Situations\nNo similar situations found in memory.\n")
        
        # Question with constraint reminder
        sections.append(f"""## Decision Required
Based on all the above, what trades should I make this week?

REMEMBER:
1. Total BUY value must NOT exceed ${portfolio.cash:,.0f}
2. Each position must NOT exceed ${max_position_dollars:,.0f}
3. Respect sector limits — avoid overweight sectors
4. Factor in market regime and VIX warnings
5. Quality over quantity — 0-3 high-conviction trades is better than 5 mediocre ones

Output your decisions as a JSON array. If no good trades, return [].""")
        
        return "\n".join(sections)
    
    def _format_sectors(self, sectors: Dict[str, float]) -> str:
        """Format sector exposure."""
        if not sectors:
            return "  No positions"
        
        lines = []
        for sector, weight in sorted(sectors.items(), key=lambda x: -x[1]):
            lines.append(f"  {sector}: {weight:.1%}")
        return "\n".join(lines)
    
    def _format_candidates(self, candidates: List) -> str:
        """Format stock candidates."""
        if not candidates:
            return "  None"
        
        lines = []
        for c in candidates:
            lines.append(
                f"- {c.ticker}: Score {c.score:.0f} ({c.signal}) | "
                f"Sector: {c.sector}"
            )
        return "\n".join(lines)
    
    def _format_memories(self, memories: List[Memory]) -> str:
        """Format past similar situations."""
        lines = []
        for m in memories:
            outcome = f"+{m.outcome_pct:.1f}%" if m.outcome_pct > 0 else f"{m.outcome_pct:.1f}%"
            lines.append(
                f"- {m.ticker} ({m.action}): Score {m.score:.0f}, "
                f"Regime {m.regime} → {outcome} (similarity: {m.similarity:.0%})"
            )
            if m.lesson_learned:
                lines.append(f"  Lesson: {m.lesson_learned}")
        return "\n".join(lines) if lines else "No similar situations found."
    
    def _parse_response(
        self,
        response: Dict[str, Any],
        context: 'TradingContext',
        max_decisions: int
    ) -> List[TradeDecision]:
        """Parse Claude's response into TradeDecision objects."""
        content = response.get("content", "[]")
        
        try:
            # Clean up response (remove markdown if present)
            content = content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            content = content.strip()
            
            decisions_data = json.loads(content)
            
            if not isinstance(decisions_data, list):
                logger.warning(f"Expected list, got {type(decisions_data)}")
                return []
            
            decisions = []
            for d in decisions_data[:max_decisions]:
                # Get candidate info
                ticker = d.get("ticker", "").upper()
                action = d.get("action", "").upper()
                
                if not ticker or action not in ("BUY", "SELL"):
                    continue
                
                # Find candidate to get score and sector
                candidate = None
                all_candidates = context.buy_candidates + context.sell_candidates
                for c in all_candidates:
                    if c.ticker == ticker:
                        candidate = c
                        break
                
                decisions.append(TradeDecision(
                    ticker=ticker,
                    action=action,
                    score=candidate.score if candidate else 0,
                    confidence=float(d.get("confidence", 0.5)),
                    sector=candidate.sector if candidate else "Unknown",
                    rationale=d.get("rationale", ""),
                ))
            
            return decisions
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse response as JSON: {e}")
            logger.debug(f"Raw content: {content}")
            return []


# Convenience function
async def make_decisions(
    context: 'TradingContext',
    memories: List[Memory],
    **kwargs
) -> DecisionResult:
    """Convenience function to make trading decisions."""
    engine = DecisionEngine(**kwargs)
    return await engine.decide(context, memories)


# CLI
if __name__ == "__main__":
    import asyncio
    import argparse
    
    parser = argparse.ArgumentParser(description="Decision Engine CLI")
    parser.add_argument("--mock", action="store_true", help="Use mock response (no API)")
    parser.add_argument("--ticker", "-t", help="Focus on specific ticker")
    
    args = parser.parse_args()
    
    async def main():
        from agent.context import aggregate_context
        from agent.memory import get_agent_memory
        
        # Get context
        print("Aggregating context...")
        context = await aggregate_context(top_n_candidates=10)
        
        # Get memories
        print("Retrieving similar situations...")
        memory = await get_agent_memory()
        memories = await memory.retrieve_similar(context, k=5)
        await memory.close()
        
        # Make decisions
        print("Consulting Claude...")
        engine = DecisionEngine()
        
        if args.mock:
            # Force mock response
            result = DecisionResult(
                decisions=[],
                thinking="Mock mode",
            )
        else:
            result = await engine.decide(context, memories)
        
        # Print results
        print(f"\n{'='*60}")
        print("TRADING DECISIONS")
        print(f"{'='*60}")
        
        if result.thinking:
            print(f"\n💭 Thinking:\n{result.thinking[:500]}...")
        
        if result.decisions:
            print(f"\n📊 Decisions ({len(result.decisions)}):\n")
            for d in result.decisions:
                emoji = "🟢" if d.action == "BUY" else "🔴"
                print(f"{emoji} {d.action} {d.ticker}")
                print(f"   Score: {d.score:.0f} | Confidence: {d.confidence:.0%}")
                print(f"   {d.rationale}")
                print()
        else:
            print("\n✋ No trades recommended this week.")
        
        print(f"\nTokens used: {result.tokens_used}")
    
    asyncio.run(main())
