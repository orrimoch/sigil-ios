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

# Add src to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from .position_sizing import TradeDecision
from .memory import Memory


# Default model (Haiku for cost efficiency)
DEFAULT_MODEL = "claude-3-5-haiku-20241022"

SYSTEM_PROMPT = """You are an expert portfolio manager for Sigil, an AI-powered trading system.

Your job is to review the current market context, portfolio state, and historical similar situations, then decide which trades to make this week.

TRADING PHILOSOPHY:
- You capture weekly trends, not intraday moves
- Maximum 3-5 trades per week (quality over quantity)
- Position trades held for 5-30 days
- You are risk-aware: never exceed position/sector limits
- When in doubt, don't trade (preserve capital)

DECISION RULES:
- BUY when: score ≥75, regime is calm/normal, sector not overweight
- SELL when: score <40, OR stop-loss triggered, OR regime is crisis + losing
- HOLD when: 40 ≤ score < 75, wait for stronger signal

For each decision, provide:
1. action: "BUY" or "SELL"
2. ticker: Stock symbol
3. rationale: Clear explanation (2-3 sentences)
4. confidence: 0.0-1.0

IMPORTANT: Output ONLY a valid JSON array. No markdown, no explanation outside the JSON.

Example output:
[
  {"action": "BUY", "ticker": "CMI", "rationale": "Score 89.8 exceptional. Industrials adds diversification. Similar CAT trade returned +12%.", "confidence": 0.85},
  {"action": "SELL", "ticker": "XYZ", "rationale": "Score dropped to 35. Stop-loss triggered. Cut losses early.", "confidence": 0.90}
]

If no trades recommended, return empty array: []
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
        thinking_budget: int = 5000
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
    
    async def _call_claude(self, prompt: str) -> Dict[str, Any]:
        """Call Claude API with extended thinking."""
        try:
            import anthropic
            
            if self._client is None:
                self._client = anthropic.AsyncAnthropic(api_key=self.api_key)
            
            # Check if model supports extended thinking
            use_thinking = "claude-3-5" in self.model or "claude-sonnet" in self.model
            
            kwargs = {
                "model": self.model,
                "max_tokens": 4000,
                "system": SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": prompt}],
            }
            
            # Add thinking for supported models
            if use_thinking:
                kwargs["thinking"] = {
                    "type": "enabled",
                    "budget_tokens": self.thinking_budget
                }
            
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
        sections.append(f"""## Current Portfolio
- Cash: ${portfolio.cash:,.0f}
- Total Value: ${portfolio.total_value:,.0f}
- Positions: {portfolio.position_count}
- Unrealized P&L: ${portfolio.unrealized_pnl:+,.0f}

Sector Exposure:
{self._format_sectors(portfolio.sector_exposure)}
""")
        
        # Market section
        market = context.market
        sections.append(f"""## Market State
- Regime: {market.regime} (confidence: {market.regime_confidence:.0%})
- VIX: {market.vix:.1f} ({market.vix_regime})
- Trend: {market.trend}
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
        
        # Question
        sections.append("""## Decision Required
Based on all the above, what trades should I make this week?
Consider risk limits, diversification, and market regime.
Output your decisions as a JSON array.""")
        
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
