# EMATA → Sigil Integration Plan

## Priority: P1 (High Value, Moderate Effort)

---

## Phase 1: Database Schema (1-2 hours)

### Changes to `agent_decisions` table
```sql
ALTER TABLE agent_decisions ADD COLUMN context_features float4[];
ALTER TABLE agent_decisions ADD COLUMN times_retrieved int DEFAULT 0;
ALTER TABLE agent_decisions ADD COLUMN times_helpful int DEFAULT 0;
ALTER TABLE agent_decisions ADD COLUMN utility_score float DEFAULT 0.5;

CREATE INDEX idx_decisions_regime ON agent_decisions(regime) WHERE outcome_pct IS NOT NULL;
CREATE INDEX idx_decisions_sector ON agent_decisions(sector) WHERE outcome_pct IS NOT NULL;
```

### Store context features on insert
In `AgentMemory.store_decision()`, compute and store `ContextSnapshot.to_feature_vector()` alongside the embedding.

---

## Phase 2: Retriever Integration (3-4 hours)

### Add to `memory.py`
1. Add `retrieve_episodic()` method to `AgentMemory` that uses the multi-dimensional scoring from `EpisodicRetriever`
2. Keep `retrieve_similar()` as fallback (backward compatible)
3. The SQL query becomes:
```sql
SELECT *, 1 - (embedding <=> $1) as emb_similarity
FROM agent_decisions
WHERE embedding IS NOT NULL
  AND outcome_pct IS NOT NULL
  AND ($2::text IS NULL OR regime = $2)
ORDER BY embedding <=> $1
LIMIT $3
```
4. Post-fetch Python re-ranking with context features, regime/sector bonuses, utility scores

### Update `trading_loop.py`
In `TradingLoop._retrieve_memories()`:
```python
# Before:
memories = await self.memory.retrieve_similar(context, k=10)

# After:
episodes = await self.memory.retrieve_episodic(context, k=10)
memories = episodes  # Same interface, richer data
```

---

## Phase 3: Augmented Prompts (2-3 hours)

### Update `decision_engine.py`
Replace `_format_memories()` with `ContextAugmenter.augment()`. The augmented text goes into the same section of the prompt but provides:
- Outcome-grouped summaries (what worked, what didn't)
- Pattern detection across episodes
- Regime-specific guidance
- Memory confidence calibration

This is the highest-impact change — it directly improves what Claude sees.

---

## Phase 4: Meta-Learning (2-3 hours)

### Update `learning.py`
After `LearningLoop._store_outcome_and_lesson()`:
1. Look up which episodes were retrieved for this decision (from retrieval log)
2. Update utility scores: positive outcomes credit memories, negative outcomes penalize
3. Apply periodic decay to unused episodes

### Add retrieval logging
In `trading_loop.py` Step 2, after retrieval:
```python
self._last_retrieval = {episode.id: score for episode, score in retrieved}
```

In Step 8 (learning), after outcome:
```python
await self._update_memory_utility(decision_id, outcome_pct)
```

---

## Phase 5: Evaluation & Tuning (4-6 hours)

### A/B testing framework
1. Run parallel retrievals: `retrieve_similar()` (current) vs `retrieve_episodic()` (EMATA)
2. Log both sets of retrieved memories
3. Compare decision quality over 4-8 weeks

### Hyperparameter tuning
Key parameters to tune:
- `w_embedding` vs `w_context` vs `w_regime_bonus` vs `w_sector_bonus` vs `w_utility`
- `outcome_informativeness_weight`
- `max_same_ticker` diversity cap
- `utility_learning_rate` for meta-learning

### Cold start
Import existing `agent_decisions` as episodes. The current data already has embeddings and outcomes — just needs context features computed retroactively.

---

## Estimated Total: 12-18 hours

### Risk Assessment
- **Low risk:** Schema changes, augmented prompts, retrieval logging
- **Medium risk:** Multi-dimensional retrieval (new scoring logic)
- **Low risk:** Meta-learning (additive, doesn't change existing behavior)

### Rollback Plan
Feature-flagged behind `EMATA_ENABLED` env var. If disabled, falls back to current `retrieve_similar()` and `_format_memories()`.

---

## Success Metrics (Production)

| Metric | Current (Naive) | Target (EMATA) |
|--------|----------------|----------------|
| Retrieval precision | ~25% | >35% |
| Win rate | Baseline | +3-5% |
| Avg return per trade | Baseline | +1-2% |
| Max drawdown | Baseline | 20-30% better |
| Decision confidence | Baseline | More calibrated |
