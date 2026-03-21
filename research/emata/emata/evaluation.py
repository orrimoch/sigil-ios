"""
Evaluation Framework — Measuring EMATA's Impact

Compares EMATA retrieval against baselines:
1. No Memory: Decisions without any memory retrieval
2. Naive Similarity: Pure embedding cosine (current Sigil approach)
3. EMATA Full: Multi-dimensional retrieval + augmentation + meta-learning

Metrics:
- Retrieval Precision: How often do retrieved episodes have the same outcome direction?
- Decision Quality: Simulated portfolio returns using different memory strategies
- Retrieval Diversity: Regime/sector spread of retrieved episodes
- Learning Convergence: Does utility scoring improve retrieval over time?

Uses synthetic episodes generated from Sigil's actual composite score data
to create realistic evaluation scenarios.
"""

import json
import numpy as np
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

from .episode import (
    Episode, DecisionRecord, ContextSnapshot, 
    OutcomeRecord, RetrievedEpisode,
)
from .episode_store import EpisodeStore
from .retriever import EpisodicRetriever, RetrieverConfig
from .augmenter import ContextAugmenter
from .meta_learner import MetaLearner, MetaLearnerConfig


@dataclass
class EvalMetrics:
    """Evaluation metrics for a single retrieval strategy."""
    strategy_name: str
    
    # Retrieval quality
    retrieval_precision: float = 0.0   # % of retrieved eps with same outcome direction
    retrieval_recall: float = 0.0      # % of relevant eps that were retrieved
    avg_similarity: float = 0.0        # Average similarity score of retrieved eps
    
    # Diversity
    regime_diversity: float = 0.0      # Entropy of regime distribution
    sector_diversity: float = 0.0      # Entropy of sector distribution
    outcome_balance: float = 0.0       # Ratio of wins to losses in retrieved set
    
    # Decision quality (simulated)
    avg_return: float = 0.0
    win_rate: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    
    # Meta-learning
    utility_improvement: float = 0.0   # Change in retrieval quality over time
    convergence_epoch: int = 0         # When utility stabilized
    
    # Efficiency
    avg_retrieval_time_ms: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class EvalScenario:
    """A single evaluation scenario (query + expected good episodes)."""
    query_context: ContextSnapshot
    query_decision: DecisionRecord
    relevant_episode_ids: List[str]  # Episodes that SHOULD be retrieved
    actual_outcome: float  # What happened when this decision was made


class SyntheticDataGenerator:
    """
    Generate realistic episodes from Sigil's composite score data.
    
    Uses the actual score distributions, sector spread, and regime
    patterns from composite_scores.json to create test episodes.
    """
    
    # Market regimes and their characteristics
    REGIMES = {
        "low_vol": {"vix_range": (10, 15), "trend_probs": {"up": 0.6, "sideways": 0.3, "down": 0.1}},
        "normal": {"vix_range": (15, 22), "trend_probs": {"up": 0.35, "sideways": 0.4, "down": 0.25}},
        "high_vol": {"vix_range": (22, 35), "trend_probs": {"up": 0.2, "sideways": 0.3, "down": 0.5}},
        "crisis": {"vix_range": (35, 80), "trend_probs": {"up": 0.05, "sideways": 0.15, "down": 0.8}},
    }
    
    # Outcome distributions by regime (mean, std)
    OUTCOME_DIST = {
        "low_vol": {"BUY": (3.0, 5.0), "SELL": (-2.0, 4.0)},
        "normal": {"BUY": (1.5, 8.0), "SELL": (-1.0, 6.0)},
        "high_vol": {"BUY": (-1.0, 12.0), "SELL": (2.0, 10.0)},
        "crisis": {"BUY": (-5.0, 15.0), "SELL": (5.0, 12.0)},
    }
    
    def __init__(self, scores_path: Optional[str] = None, seed: int = 42):
        self.rng = np.random.RandomState(seed)
        self.scores_data = self._load_scores(scores_path) if scores_path else None
    
    def _load_scores(self, path: str) -> Dict:
        """Load Sigil composite scores for realistic data generation."""
        with open(path) as f:
            data = json.load(f)
        return data.get("scores", {})
    
    def generate_episodes(
        self,
        n: int = 200,
        regime_distribution: Optional[Dict[str, float]] = None,
    ) -> List[Episode]:
        """
        Generate n synthetic episodes with realistic distributions.
        
        If scores_data is loaded, uses actual ticker/sector/score distributions.
        Otherwise generates from statistical priors.
        """
        if regime_distribution is None:
            regime_distribution = {
                "low_vol": 0.25,
                "normal": 0.45,
                "high_vol": 0.20,
                "crisis": 0.10,
            }
        
        episodes = []
        sectors = [
            "Technology", "Healthcare", "Finance", "Energy",
            "Industrials", "Consumer", "Communications", "Utilities",
        ]
        
        # Get ticker/sector data from Sigil if available
        if self.scores_data:
            available_tickers = list(self.scores_data.keys())
            ticker_sectors = {
                t: d.get("sector", "Unknown") 
                for t, d in self.scores_data.items()
            }
            ticker_scores = {
                t: d.get("total_score", 50) 
                for t, d in self.scores_data.items()
            }
        else:
            available_tickers = [
                "AAPL", "NVDA", "MSFT", "GOOGL", "AMZN", "META", "TSLA",
                "AMD", "CRM", "AVGO", "ANET", "CMI", "UNH", "JPM", "V",
                "MA", "LLY", "JNJ", "PG", "XOM", "CVX", "NEE",
            ]
            ticker_sectors = {t: self.rng.choice(sectors) for t in available_tickers}
            ticker_scores = {t: self.rng.uniform(20, 95) for t in available_tickers}
        
        base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
        
        for i in range(n):
            # Pick regime
            regime = self.rng.choice(
                list(regime_distribution.keys()),
                p=list(regime_distribution.values()),
            )
            regime_info = self.REGIMES[regime]
            
            # Pick ticker
            ticker = self.rng.choice(available_tickers)
            sector = ticker_sectors.get(ticker, "Unknown")
            base_score = ticker_scores.get(ticker, 50)
            
            # Add noise to score
            score = np.clip(base_score + self.rng.normal(0, 10), 0, 100)
            
            # Determine action based on score
            action = "BUY" if score >= 65 else "SELL"
            
            # Generate context
            vix = self.rng.uniform(*regime_info["vix_range"])
            trend_choices = list(regime_info["trend_probs"].keys())
            trend_probs = list(regime_info["trend_probs"].values())
            trend = self.rng.choice(trend_choices, p=trend_probs)
            
            context = ContextSnapshot(
                regime=regime,
                regime_confidence=self.rng.uniform(0.5, 0.95),
                vix=vix,
                vix_regime="calm" if vix < 20 else "elevated" if vix < 30 else "fear",
                trend=trend,
                cash_pct=self.rng.uniform(0.1, 0.6),
                position_count=self.rng.randint(0, 15),
                sector_exposure={sector: self.rng.uniform(0.05, 0.3)},
                fundamental_score=np.clip(self.rng.normal(score, 15), 0, 100),
                sentiment_score=np.clip(self.rng.normal(score * 0.8, 20), 0, 100),
                technical_score=np.clip(self.rng.normal(score, 18), 0, 100),
                macro_score=np.clip(self.rng.normal(50, 15), 0, 100),
                sector=sector,
            )
            
            # Generate outcome
            outcome_mean, outcome_std = self.OUTCOME_DIST[regime][action]
            # Score influence: high scores → better BUY outcomes
            score_bonus = (score - 50) / 50 * 3  # ±3% based on score
            pct_return = self.rng.normal(outcome_mean + score_bonus, outcome_std)
            pct_return = np.clip(pct_return, -30, 50)
            
            # Outcome tag
            if pct_return > 10:
                tag = "strong_win"
            elif pct_return > 5:
                tag = "win"
            elif pct_return > 1:
                tag = "small_win"
            elif pct_return > -1:
                tag = "neutral"
            elif pct_return > -5:
                tag = "loss"
            else:
                tag = "strong_loss"
            
            holding_days = self.rng.randint(5, 30)
            
            # Generate lesson
            lesson = self._generate_lesson(ticker, action, regime, pct_return, score)
            
            # Confidence correlated with score
            confidence = np.clip(0.3 + score / 200 + self.rng.normal(0, 0.1), 0.1, 0.95)
            
            episode = Episode(
                timestamp=base_time + timedelta(days=i * 2 + self.rng.randint(0, 2)),
                decision=DecisionRecord(
                    ticker=ticker,
                    action=action,
                    shares=self.rng.randint(5, 50),
                    price=self.rng.uniform(20, 500),
                    score=score,
                    confidence=confidence,
                    rationale=f"{action} {ticker} with score {score:.0f} in {regime} regime",
                ),
                context=context,
                outcome=OutcomeRecord(
                    pct_return=pct_return,
                    holding_days=holding_days,
                    exit_price=0,  # Not critical for evaluation
                    tag=tag,
                    pnl_dollars=0,  # Not critical for evaluation
                    recorded_at=base_time + timedelta(days=i * 2 + holding_days),
                ),
                lesson=lesson,
            )
            
            episodes.append(episode)
        
        return episodes
    
    def _generate_lesson(
        self, ticker: str, action: str, regime: str, 
        pct_return: float, score: float,
    ) -> str:
        """Generate a realistic lesson string."""
        if pct_return > 5:
            templates = [
                f"Strong entry on {ticker}. Score {score:.0f} in {regime} regime was a reliable signal.",
                f"Holding through volatility paid off. High score confirmed the thesis.",
                f"Score-driven {action} on {ticker} in {regime} market delivered well.",
            ]
        elif pct_return > 0:
            templates = [
                f"Modest gain on {ticker}. Timing was acceptable for {regime} conditions.",
                f"Positive but small return. Consider tighter entry criteria in {regime}.",
            ]
        elif pct_return > -3:
            templates = [
                f"Near-breakeven on {ticker}. Score of {score:.0f} wasn't decisive enough.",
                f"Flat trade. {regime.replace('_', ' ').title()} regime neutralized the signal.",
            ]
        else:
            templates = [
                f"Loss on {ticker}. {action} at score {score:.0f} in {regime} was too aggressive.",
                f"Regime conditions ({regime}) overrode the score signal. Tighten risk.",
                f"Should have sized down in {regime}. Score {score:.0f} gave false confidence.",
            ]
        
        return self.rng.choice(templates)
    
    def generate_eval_scenarios(
        self,
        episodes: List[Episode],
        n_scenarios: int = 50,
    ) -> List[EvalScenario]:
        """
        Generate evaluation scenarios from existing episodes.
        
        For each scenario, identifies which episodes SHOULD be retrieved
        (same regime + sector + similar score) as ground truth.
        """
        scenarios = []
        
        for i in range(min(n_scenarios, len(episodes) - 10)):
            # Use a later episode as the query
            query_idx = len(episodes) - n_scenarios + i
            query_ep = episodes[query_idx]
            
            # Past episodes as the memory pool
            pool = episodes[:query_idx]
            
            # Determine relevant episodes (ground truth)
            relevant_ids = []
            for ep in pool:
                if not ep.is_complete:
                    continue
                # Relevant if: same regime OR same sector OR similar score (±15)
                regime_match = ep.context.regime == query_ep.context.regime
                sector_match = ep.context.sector == query_ep.context.sector
                score_close = abs(ep.decision.score - query_ep.decision.score) < 15
                
                if (regime_match and sector_match) or (regime_match and score_close):
                    relevant_ids.append(ep.id)
            
            scenarios.append(EvalScenario(
                query_context=query_ep.context,
                query_decision=query_ep.decision,
                relevant_episode_ids=relevant_ids,
                actual_outcome=query_ep.outcome.pct_return if query_ep.outcome else 0,
            ))
        
        return scenarios


class Evaluator:
    """
    Runs comparative evaluation of retrieval strategies.
    
    Compares:
    1. No Memory baseline
    2. Naive Similarity (current Sigil) baseline
    3. EMATA full retrieval
    4. EMATA + meta-learning (after convergence)
    """
    
    def __init__(
        self,
        episodes: List[Episode],
        scenarios: List[EvalScenario],
    ):
        self.episodes = episodes
        self.scenarios = scenarios
    
    def evaluate_all(self, k: int = 10) -> Dict[str, EvalMetrics]:
        """Run all evaluation strategies and return comparative metrics."""
        results = {}
        
        # Strategy 1: No Memory
        results["no_memory"] = self._eval_no_memory()
        
        # Strategy 2: Naive Similarity (current Sigil)
        results["naive_similarity"] = self._eval_naive_similarity(k)
        
        # Strategy 3: EMATA (multi-dimensional, no meta-learning)
        results["emata_base"] = self._eval_emata(k, with_meta_learning=False)
        
        # Strategy 4: EMATA + Meta-Learning
        results["emata_meta"] = self._eval_emata(k, with_meta_learning=True)
        
        return results
    
    def _eval_no_memory(self) -> EvalMetrics:
        """Evaluate decisions without memory (baseline)."""
        metrics = EvalMetrics(strategy_name="no_memory")
        
        # Without memory, decisions are based purely on current scores
        # Simulate: action = BUY if score >= 65 else pass
        returns = []
        for scenario in self.scenarios:
            score = scenario.query_decision.score
            if score >= 65:
                returns.append(scenario.actual_outcome)
            else:
                returns.append(0)  # No trade
        
        if returns:
            metrics.avg_return = float(np.mean(returns))
            metrics.win_rate = sum(1 for r in returns if r > 0) / max(len(returns), 1)
            if np.std(returns) > 0:
                metrics.sharpe_ratio = float(np.mean(returns) / np.std(returns) * np.sqrt(52))
            metrics.max_drawdown = float(self._compute_max_drawdown(returns))
        
        return metrics
    
    def _eval_naive_similarity(self, k: int) -> EvalMetrics:
        """Evaluate with pure embedding cosine similarity (current Sigil)."""
        metrics = EvalMetrics(strategy_name="naive_similarity")
        
        # Build store with all episodes
        store = EpisodeStore()
        store.store_batch(self.episodes)
        
        # Simple retriever config: 100% embedding weight
        config = RetrieverConfig(
            w_embedding=1.0,
            w_context=0.0,
            w_regime_bonus=0.0,
            w_sector_bonus=0.0,
            w_utility=0.0,
            outcome_informativeness_weight=0.0,
            prefer_diverse_outcomes=False,
            max_same_ticker=-1,
        )
        config.validate()
        retriever = EpisodicRetriever(store, config)
        
        precision_scores = []
        diversity_regimes = []
        diversity_sectors = []
        returns = []
        
        for scenario in self.scenarios:
            retrieved = retriever.retrieve(scenario.query_context, k=k)
            
            # Precision: fraction of retrieved that are in relevant set
            if retrieved and scenario.relevant_episode_ids:
                retrieved_ids = {re.episode.id for re in retrieved}
                relevant_ids = set(scenario.relevant_episode_ids)
                precision = len(retrieved_ids & relevant_ids) / len(retrieved_ids)
                precision_scores.append(precision)
            
            # Diversity
            if retrieved:
                regimes = [re.episode.context.regime for re in retrieved]
                sectors = [re.episode.context.sector for re in retrieved]
                diversity_regimes.append(self._entropy(regimes))
                diversity_sectors.append(self._entropy(sectors))
            
            # Simulated decision quality
            ret = self._simulate_decision(scenario, retrieved)
            returns.append(ret)
        
        metrics.retrieval_precision = float(np.mean(precision_scores)) if precision_scores else 0
        metrics.regime_diversity = float(np.mean(diversity_regimes)) if diversity_regimes else 0
        metrics.sector_diversity = float(np.mean(diversity_sectors)) if diversity_sectors else 0
        metrics.avg_return = float(np.mean(returns)) if returns else 0
        metrics.win_rate = sum(1 for r in returns if r > 0) / max(len(returns), 1)
        if returns and np.std(returns) > 0:
            metrics.sharpe_ratio = float(np.mean(returns) / np.std(returns) * np.sqrt(52))
        metrics.max_drawdown = float(self._compute_max_drawdown(returns))
        metrics.avg_similarity = float(
            np.mean([np.mean([re.embedding_similarity for re in ret]) 
                     for ret in [retriever.retrieve(s.query_context, k=k) for s in self.scenarios[:5]]
                     if ret])
        ) if self.scenarios else 0
        
        return metrics
    
    def _eval_emata(self, k: int, with_meta_learning: bool) -> EvalMetrics:
        """Evaluate EMATA retrieval."""
        strategy_name = "emata_meta" if with_meta_learning else "emata_base"
        metrics = EvalMetrics(strategy_name=strategy_name)
        
        # Build store
        store = EpisodeStore()
        store.store_batch(self.episodes)
        
        # EMATA config
        config = RetrieverConfig(
            w_embedding=0.40,
            w_context=0.25,
            w_regime_bonus=0.15,
            w_sector_bonus=0.10,
            w_utility=0.10,
            outcome_informativeness_weight=0.3,
            prefer_diverse_outcomes=True,
            max_same_ticker=2,
        )
        config.validate()
        retriever = EpisodicRetriever(store, config)
        
        meta_learner = None
        if with_meta_learning:
            meta_config = MetaLearnerConfig(
                utility_learning_rate=0.2,
                attribution_mode="proportional",
            )
            meta_learner = MetaLearner(store, meta_config)
        
        precision_scores = []
        diversity_regimes = []
        diversity_sectors = []
        returns = []
        
        for scenario in self.scenarios:
            retrieved = retriever.retrieve(scenario.query_context, k=k)
            
            # Precision
            if retrieved and scenario.relevant_episode_ids:
                retrieved_ids = {re.episode.id for re in retrieved}
                relevant_ids = set(scenario.relevant_episode_ids)
                precision = len(retrieved_ids & relevant_ids) / len(retrieved_ids)
                precision_scores.append(precision)
            
            # Diversity
            if retrieved:
                regimes = [re.episode.context.regime for re in retrieved]
                sectors = [re.episode.context.sector for re in retrieved]
                diversity_regimes.append(self._entropy(regimes))
                diversity_sectors.append(self._entropy(sectors))
            
            # Simulated decision
            ret = self._simulate_decision(scenario, retrieved)
            returns.append(ret)
            
            # Meta-learning update
            if meta_learner and retrieved:
                dummy_id = f"decision_{len(returns)}"
                meta_learner.log_retrieval(dummy_id, retrieved)
                meta_learner.update_from_outcome(dummy_id, scenario.actual_outcome)
        
        metrics.retrieval_precision = float(np.mean(precision_scores)) if precision_scores else 0
        metrics.regime_diversity = float(np.mean(diversity_regimes)) if diversity_regimes else 0
        metrics.sector_diversity = float(np.mean(diversity_sectors)) if diversity_sectors else 0
        metrics.avg_return = float(np.mean(returns)) if returns else 0
        metrics.win_rate = sum(1 for r in returns if r > 0) / max(len(returns), 1)
        if returns and np.std(returns) > 0:
            metrics.sharpe_ratio = float(np.mean(returns) / np.std(returns) * np.sqrt(52))
        metrics.max_drawdown = float(self._compute_max_drawdown(returns))
        
        # Outcome balance
        if retrieved:
            for scenario in self.scenarios[:5]:
                ret = retriever.retrieve(scenario.query_context, k=k)
                if ret:
                    wins = sum(1 for re in ret if re.episode.outcome and re.episode.outcome.is_positive)
                    losses = sum(1 for re in ret if re.episode.outcome and not re.episode.outcome.is_positive)
                    if wins + losses > 0:
                        metrics.outcome_balance = float(np.mean([
                            min(wins, losses) / max(wins, losses) if max(wins, losses) > 0 else 1.0
                        ]))
        
        # Meta-learning improvement
        if meta_learner:
            dist = meta_learner.get_utility_distribution()
            metrics.utility_improvement = dist.get("mean", 0.5) - 0.5
        
        return metrics
    
    def _simulate_decision(
        self,
        scenario: EvalScenario,
        retrieved: List[RetrievedEpisode],
    ) -> float:
        """
        Simulate a decision informed by retrieved episodes.
        
        Simple model: if retrieved episodes suggest caution (avg outcome < 0
        for similar situations), reduce exposure → take half the actual outcome.
        If retrieved episodes are positive, full exposure.
        """
        if not retrieved:
            # No memory: raw decision
            return scenario.actual_outcome
        
        # Analyze retrieved episodes
        outcomes = [
            re.episode.outcome.pct_return 
            for re in retrieved 
            if re.episode.outcome
        ]
        
        if not outcomes:
            return scenario.actual_outcome
        
        avg_retrieved_outcome = np.mean(outcomes)
        win_rate = sum(1 for o in outcomes if o > 0) / len(outcomes)
        
        # Decision modifier based on memory evidence
        if avg_retrieved_outcome > 2.0 and win_rate > 0.6:
            # Strong positive evidence: full position
            exposure = 1.0
        elif avg_retrieved_outcome < -2.0 or win_rate < 0.3:
            # Negative evidence: reduce or skip
            exposure = 0.25
        else:
            # Mixed evidence: moderate position
            exposure = 0.7
        
        return scenario.actual_outcome * exposure
    
    def _entropy(self, labels: List[str]) -> float:
        """Shannon entropy of a label distribution (higher = more diverse)."""
        if not labels:
            return 0.0
        counts = defaultdict(int)
        for l in labels:
            counts[l] += 1
        n = len(labels)
        probs = [c / n for c in counts.values()]
        return float(-sum(p * np.log2(p + 1e-10) for p in probs))
    
    def _compute_max_drawdown(self, returns: List[float]) -> float:
        """Compute maximum drawdown from a series of returns."""
        if not returns:
            return 0.0
        cumulative = np.cumsum(returns)
        running_max = np.maximum.accumulate(cumulative)
        drawdowns = cumulative - running_max
        return float(np.min(drawdowns)) if len(drawdowns) > 0 else 0.0
    
    def format_comparison(self, results: Dict[str, EvalMetrics]) -> str:
        """Format a human-readable comparison table."""
        lines = [
            "=" * 80,
            "EMATA EVALUATION RESULTS",
            "=" * 80,
            "",
            f"{'Metric':<30} {'No Memory':>12} {'Naive Sim':>12} {'EMATA':>12} {'EMATA+Meta':>12}",
            "-" * 80,
        ]
        
        strategies = ["no_memory", "naive_similarity", "emata_base", "emata_meta"]
        
        metrics_to_show = [
            ("Retrieval Precision", "retrieval_precision", ".1%"),
            ("Regime Diversity", "regime_diversity", ".2f"),
            ("Sector Diversity", "sector_diversity", ".2f"),
            ("Outcome Balance", "outcome_balance", ".2f"),
            ("Avg Return (%)", "avg_return", "+.2f"),
            ("Win Rate", "win_rate", ".1%"),
            ("Sharpe Ratio", "sharpe_ratio", ".2f"),
            ("Max Drawdown (%)", "max_drawdown", ".2f"),
            ("Utility Improvement", "utility_improvement", "+.3f"),
        ]
        
        for label, attr, fmt in metrics_to_show:
            values = []
            for s in strategies:
                m = results.get(s)
                if m:
                    val = getattr(m, attr, 0)
                    values.append(f"{val:{fmt}}")
                else:
                    values.append("N/A")
            
            line = f"{label:<30} " + " ".join(f"{v:>12}" for v in values)
            lines.append(line)
        
        lines.append("-" * 80)
        
        # Highlight winner
        best_strategy = max(
            results.items(), 
            key=lambda x: x[1].avg_return if x[1] else float('-inf')
        )
        lines.append(f"\n🏆 Best strategy by avg return: {best_strategy[0]}")
        
        best_precision = max(
            results.items(),
            key=lambda x: x[1].retrieval_precision if x[1] else 0
        )
        lines.append(f"🎯 Best retrieval precision: {best_precision[0]}")
        
        return "\n".join(lines)
