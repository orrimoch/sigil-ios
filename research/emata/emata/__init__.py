"""
EMATA — Episodic Memory-Augmented Trading Agents

Research implementation for Sigil's agent memory system.
Extends the existing three-tier memory (working/short-term/long-term)
with structured episodic retrieval, outcome-weighted ranking, and
meta-learning on memory utility.

Architecture mapping to Sigil:
  - Episode ↔ Decision (memory.py) + TradingContext (context.py) + TradeOutcome (learning.py)
  - EpisodeStore ↔ AgentMemory (extends retrieve_similar with multi-dim scoring)
  - EpisodicRetriever ↔ New component between memory and decision_engine
  - ContextAugmenter ↔ New component that formats retrieved episodes for DecisionEngine
  - MetaLearner ↔ Extension of LearningLoop to track which memories helped
"""

__version__ = "0.1.0"
