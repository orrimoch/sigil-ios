"""
Context Augmenter — Formats Retrieved Episodes for the Decision Engine

This component bridges EMATA retrieval with Sigil's DecisionEngine.

Current Sigil (decision_engine.py):
    _format_memories(memories) → simple text list:
    "- AAPL (BUY): Score 75, Regime normal → +5.2% (similarity: 85%)"

EMATA augmenter:
    augment(retrieved_episodes) → structured prompt sections with:
    1. Episode narratives with full context
    2. Outcome-grouped summaries (what worked, what didn't)
    3. Regime-specific guidance distilled from episodes
    4. Pattern detection across retrieved episodes
    5. Confidence calibration (how reliable are these memories?)

Integration point: Replaces DecisionEngine._format_memories() in the
prompt construction. The augmented text goes into the same position
in the prompt but provides much richer decision support.
"""

from typing import List, Dict, Optional, Any, Tuple
from collections import defaultdict
import numpy as np

from .episode import RetrievedEpisode, Episode, ContextSnapshot


class ContextAugmenter:
    """
    Formats retrieved episodes into decision-support text for Claude.
    
    The augmenter analyzes patterns across retrieved episodes and
    creates structured guidance that's more useful than a flat list
    of past decisions.
    
    Usage:
        augmenter = ContextAugmenter()
        
        # In DecisionEngine._build_prompt():
        memory_section = augmenter.augment(retrieved_episodes, current_context)
        # Insert into prompt where _format_memories() currently goes
    """
    
    def __init__(
        self,
        max_detailed_episodes: int = 5,
        max_summary_episodes: int = 10,
        include_pattern_analysis: bool = True,
        include_regime_guidance: bool = True,
        include_confidence_calibration: bool = True,
    ):
        self.max_detailed = max_detailed_episodes
        self.max_summary = max_summary_episodes
        self.include_patterns = include_pattern_analysis
        self.include_regime = include_regime_guidance
        self.include_calibration = include_confidence_calibration
    
    def augment(
        self,
        episodes: List[RetrievedEpisode],
        current_context: Optional[ContextSnapshot] = None,
    ) -> str:
        """
        Generate augmented memory context for the decision engine prompt.
        
        Returns a formatted string that replaces the simple memory list
        in DecisionEngine._build_prompt().
        """
        if not episodes:
            return "## Episodic Memory\nNo similar past situations found in memory.\n"
        
        sections = ["## Episodic Memory"]
        sections.append(f"*{len(episodes)} relevant past experiences retrieved*\n")
        
        # Section 1: Detailed episode narratives (top k)
        sections.append(self._format_detailed_episodes(episodes[:self.max_detailed]))
        
        # Section 2: Outcome-grouped summary
        sections.append(self._format_outcome_summary(episodes[:self.max_summary]))
        
        # Section 3: Pattern analysis
        if self.include_patterns and len(episodes) >= 3:
            patterns = self._analyze_patterns(episodes)
            if patterns:
                sections.append(patterns)
        
        # Section 4: Regime-specific guidance
        if self.include_regime and current_context:
            regime_guidance = self._format_regime_guidance(episodes, current_context)
            if regime_guidance:
                sections.append(regime_guidance)
        
        # Section 5: Confidence calibration
        if self.include_calibration:
            calibration = self._format_confidence_calibration(episodes)
            if calibration:
                sections.append(calibration)
        
        return "\n".join(sections)
    
    def augment_minimal(self, episodes: List[RetrievedEpisode]) -> str:
        """
        Minimal augmentation — for comparison with baseline.
        Matches current Sigil format from DecisionEngine._format_memories().
        """
        if not episodes:
            return "No similar situations found in memory."
        
        lines = []
        for re in episodes:
            ep = re.episode
            outcome = (
                f"+{ep.outcome.pct_return:.1f}%"
                if ep.outcome and ep.outcome.pct_return > 0
                else f"{ep.outcome.pct_return:.1f}%" if ep.outcome else "pending"
            )
            lines.append(
                f"- {ep.decision.ticker} ({ep.decision.action}): "
                f"Score {ep.decision.score:.0f}, Regime {ep.context.regime} → "
                f"{outcome} (similarity: {re.embedding_similarity:.0%})"
            )
            if ep.lesson:
                lines.append(f"  Lesson: {ep.lesson}")
        
        return "\n".join(lines)
    
    def _format_detailed_episodes(self, episodes: List[RetrievedEpisode]) -> str:
        """Format top episodes with full context narratives."""
        lines = ["### Most Relevant Past Decisions\n"]
        
        for i, re in enumerate(episodes, 1):
            ep = re.episode
            outcome_emoji = self._outcome_emoji(ep)
            
            lines.append(f"**{i}. {ep.decision.action} {ep.decision.ticker}** "
                         f"({ep.context.regime} regime, {ep.context.sector}) "
                         f"— Relevance: {re.final_score:.0%}")
            
            lines.append(f"   Score: {ep.decision.score:.0f} | "
                         f"VIX: {ep.context.vix:.1f} | "
                         f"Cash: {ep.context.cash_pct:.0%} | "
                         f"Positions: {ep.context.position_count}")
            
            lines.append(f"   Components: F={ep.context.fundamental_score:.0f} "
                         f"S={ep.context.sentiment_score:.0f} "
                         f"T={ep.context.technical_score:.0f} "
                         f"M={ep.context.macro_score:.0f}")
            
            if ep.outcome:
                lines.append(f"   {outcome_emoji} Outcome: {ep.outcome.pct_return:+.1f}% "
                             f"over {ep.outcome.holding_days}d ({ep.outcome.tag})")
            
            if ep.lesson:
                lines.append(f"   💡 Lesson: {ep.lesson}")
            
            # Show retrieval dimensions
            match_flags = []
            if re.regime_match:
                match_flags.append("regime✓")
            if re.sector_match:
                match_flags.append("sector✓")
            lines.append(f"   [emb={re.embedding_similarity:.2f} "
                         f"ctx={re.context_similarity:.2f} "
                         f"{' '.join(match_flags)}]")
            lines.append("")
        
        return "\n".join(lines)
    
    def _format_outcome_summary(self, episodes: List[RetrievedEpisode]) -> str:
        """Group episodes by outcome quality."""
        wins = []
        losses = []
        neutral = []
        
        for re in episodes:
            ep = re.episode
            if not ep.outcome:
                continue
            
            entry = (ep.decision.ticker, ep.decision.action, 
                     ep.decision.score, ep.outcome.pct_return, ep.lesson)
            
            if ep.outcome.pct_return > 1.0:
                wins.append(entry)
            elif ep.outcome.pct_return < -1.0:
                losses.append(entry)
            else:
                neutral.append(entry)
        
        lines = ["### Outcome Summary\n"]
        
        if wins:
            lines.append(f"**✅ Successful ({len(wins)}):**")
            for ticker, action, score, ret, lesson in wins:
                lines.append(f"  - {action} {ticker} (score {score:.0f}) → {ret:+.1f}%")
            avg_win = np.mean([w[3] for w in wins])
            lines.append(f"  Average win: {avg_win:+.1f}%\n")
        
        if losses:
            lines.append(f"**❌ Unsuccessful ({len(losses)}):**")
            for ticker, action, score, ret, lesson in losses:
                lines.append(f"  - {action} {ticker} (score {score:.0f}) → {ret:+.1f}%")
            avg_loss = np.mean([l[3] for l in losses])
            lines.append(f"  Average loss: {avg_loss:+.1f}%\n")
        
        if neutral:
            lines.append(f"**➖ Neutral ({len(neutral)}): ** "
                         f"{', '.join(n[0] for n in neutral)}\n")
        
        # Win rate from similar situations
        total = len(wins) + len(losses) + len(neutral)
        if total > 0:
            wr = len(wins) / total * 100
            lines.append(f"**Historical win rate in similar situations: {wr:.0f}%**\n")
        
        return "\n".join(lines)
    
    def _analyze_patterns(self, episodes: List[RetrievedEpisode]) -> str:
        """Detect patterns across retrieved episodes."""
        complete = [re for re in episodes if re.episode.is_complete]
        if len(complete) < 3:
            return ""
        
        lines = ["### Patterns Detected\n"]
        patterns_found = False
        
        # Pattern 1: Score threshold patterns
        high_score = [re for re in complete if re.episode.decision.score >= 75]
        low_score = [re for re in complete if re.episode.decision.score < 60]
        
        if high_score and len(high_score) >= 2:
            avg_ret = np.mean([re.episode.outcome.pct_return for re in high_score])
            wr = sum(1 for re in high_score if re.episode.outcome.is_positive) / len(high_score)
            lines.append(f"- **High-score trades (≥75):** {len(high_score)} instances, "
                         f"avg return {avg_ret:+.1f}%, win rate {wr:.0%}")
            patterns_found = True
        
        if low_score and len(low_score) >= 2:
            avg_ret = np.mean([re.episode.outcome.pct_return for re in low_score])
            wr = sum(1 for re in low_score if re.episode.outcome.is_positive) / len(low_score)
            lines.append(f"- **Low-score trades (<60):** {len(low_score)} instances, "
                         f"avg return {avg_ret:+.1f}%, win rate {wr:.0%}")
            patterns_found = True
        
        # Pattern 2: Regime-outcome correlation
        regime_outcomes = defaultdict(list)
        for re in complete:
            regime_outcomes[re.episode.context.regime].append(
                re.episode.outcome.pct_return
            )
        
        for regime, returns in regime_outcomes.items():
            if len(returns) >= 2:
                avg = np.mean(returns)
                lines.append(f"- **{regime} regime:** {len(returns)} trades, "
                             f"avg return {avg:+.1f}%")
                patterns_found = True
        
        # Pattern 3: Sector concentration
        sector_counts = defaultdict(int)
        for re in complete:
            sector_counts[re.episode.context.sector] += 1
        
        dominant = max(sector_counts.items(), key=lambda x: x[1]) if sector_counts else None
        if dominant and dominant[1] >= 3:
            sector_eps = [re for re in complete 
                         if re.episode.context.sector == dominant[0]]
            avg_ret = np.mean([re.episode.outcome.pct_return for re in sector_eps])
            lines.append(f"- **{dominant[0]} dominates** similar situations "
                         f"({dominant[1]} of {len(complete)}), avg {avg_ret:+.1f}%")
            patterns_found = True
        
        # Pattern 4: Common lessons
        lessons = [re.episode.lesson for re in complete if re.episode.lesson]
        if lessons and len(lessons) >= 2:
            lines.append(f"\n**Key lessons from similar situations:**")
            for lesson in lessons[:3]:
                lines.append(f"  - {lesson}")
            patterns_found = True
        
        if not patterns_found:
            return ""
        
        lines.append("")
        return "\n".join(lines)
    
    def _format_regime_guidance(
        self,
        episodes: List[RetrievedEpisode],
        current_context: ContextSnapshot,
    ) -> str:
        """Generate regime-specific guidance from past episodes."""
        # Find episodes from the same regime
        same_regime = [
            re for re in episodes
            if re.episode.context.regime == current_context.regime
            and re.episode.is_complete
        ]
        
        if len(same_regime) < 2:
            return ""
        
        returns = [re.episode.outcome.pct_return for re in same_regime]
        avg_ret = np.mean(returns)
        win_rate = sum(1 for r in returns if r > 0) / len(returns)
        
        lines = [f"### Regime Guidance ({current_context.regime})\n"]
        lines.append(f"Based on {len(same_regime)} past decisions in "
                     f"**{current_context.regime}** regime:")
        lines.append(f"- Average return: {avg_ret:+.1f}%")
        lines.append(f"- Win rate: {win_rate:.0%}")
        
        # Best and worst in this regime
        best = max(same_regime, key=lambda re: re.episode.outcome.pct_return)
        worst = min(same_regime, key=lambda re: re.episode.outcome.pct_return)
        
        lines.append(f"- Best: {best.episode.decision.action} "
                     f"{best.episode.decision.ticker} → "
                     f"{best.episode.outcome.pct_return:+.1f}%")
        lines.append(f"- Worst: {worst.episode.decision.action} "
                     f"{worst.episode.decision.ticker} → "
                     f"{worst.episode.outcome.pct_return:+.1f}%")
        
        # VIX correlation
        if current_context.vix > 25:
            high_vix_eps = [re for re in same_regime if re.episode.context.vix > 25]
            if high_vix_eps:
                hvix_avg = np.mean([re.episode.outcome.pct_return for re in high_vix_eps])
                lines.append(f"- ⚠️ In elevated VIX (>25): avg return {hvix_avg:+.1f}%")
        
        lines.append("")
        return "\n".join(lines)
    
    def _format_confidence_calibration(
        self, episodes: List[RetrievedEpisode]
    ) -> str:
        """
        Assess how much to trust these memories.
        
        Key insight: If retrieved memories have low similarity scores
        or few episodes match, the agent should weight them less.
        """
        if not episodes:
            return ""
        
        avg_similarity = np.mean([re.embedding_similarity for re in episodes])
        avg_final = np.mean([re.final_score for re in episodes])
        regime_matches = sum(1 for re in episodes if re.regime_match)
        complete = sum(1 for re in episodes if re.episode.is_complete)
        
        # Confidence level
        if avg_final > 0.7 and complete >= 5:
            confidence = "HIGH"
            emoji = "🟢"
            advice = "These memories are highly relevant. Weight them strongly."
        elif avg_final > 0.4 and complete >= 3:
            confidence = "MEDIUM"
            emoji = "🟡"
            advice = "Moderately relevant memories. Consider but don't over-rely."
        else:
            confidence = "LOW"
            emoji = "🔴"
            advice = "Few relevant memories found. Rely more on current data."
        
        lines = [f"### Memory Confidence: {emoji} {confidence}\n"]
        lines.append(f"- Avg relevance: {avg_final:.0%}")
        lines.append(f"- Regime matches: {regime_matches}/{len(episodes)}")
        lines.append(f"- Complete episodes: {complete}/{len(episodes)}")
        lines.append(f"- {advice}\n")
        
        return "\n".join(lines)
    
    def _outcome_emoji(self, episode: Episode) -> str:
        """Get emoji for outcome."""
        if not episode.outcome:
            return "⏳"
        tag = episode.outcome.tag
        return {
            "strong_win": "🏆",
            "win": "✅",
            "small_win": "✅",
            "neutral": "➖",
            "loss": "❌",
            "strong_loss": "💀",
        }.get(tag, "❓")
