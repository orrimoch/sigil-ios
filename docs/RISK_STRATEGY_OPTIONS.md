<img src="sigil_logo.jpg" alt="Sigil" width="240" />

# Risk Strategy Options — Addressing Backtest Failures

**Date:** February 8, 2026  
**Author:** PM Subagent  
**Context:** 18-month backtest showed -14.38% alpha due to holding through Q4 2018 crash

---

## Executive Summary

The current scoring system (buy ≥70, sell ≤50) lacks:
1. **Regime awareness** — can't distinguish bull vs. bear markets
2. **Exit discipline** — no P&L-based stop-losses or profit-taking
3. **Position sizing** — equal weight regardless of conviction or risk

Below are 4 concrete options, ordered from simplest to most complex.

---

## Option 1: Rule-Based Exit Layer

### Description
Add a simple rules layer on top of scores: stop-loss, trailing stop, and profit targets. No ML required.

**Rules:**
- **Hard stop-loss:** Exit if position drops -15% from entry
- **Trailing stop:** After +10% gain, trail at -8% from peak
- **Profit target:** Trim 50% at +25% gain, remainder rides with trailing stop
- **Time decay:** Exit after 8 weeks if return is between -5% and +5% (dead money)

### Based On
- Practical trading wisdom (Ernest Chan's *Quantitative Trading*)
- Taleb's "Black Swan" — accept you can't predict crashes, just limit exposure

### Complexity: **Low**
- 1-2 days implementation
- No new models or data sources
- Just logic in the `PortfolioManager`

### Effectiveness: **Medium-High**
- Would have limited Q4 2018 drawdown to ~-15% instead of -21%
- Simple, battle-tested, no overfitting risk

### Pros
- ✅ Immediate implementation
- ✅ No additional data or model training
- ✅ Easy to backtest and validate
- ✅ Users understand "I got stopped out at -15%"

### Cons
- ❌ Fixed thresholds may whipsaw in volatile markets
- ❌ Doesn't adapt to regime (same rules in bull vs. crash)
- ❌ Could exit good positions too early

---

## Option 2: Adaptive Thresholds with Volatility Scaling

### Description
Make buy/sell thresholds and position sizes dynamic based on market volatility. When VIX is high or 20-day volatility spikes, become more defensive.

**Implementation:**
```
volatility_factor = current_volatility / avg_volatility_90d

If volatility_factor > 1.5:  # High volatility regime
  - Raise sell threshold from 50 → 60
  - Lower buy threshold from 70 → 75
  - Reduce max position size by 30%
  - Tighten stop-loss from -15% → -10%
```

### Based On
- Nystrup et al. (2015): "Regime-based versus static asset allocation" — showed adaptive allocation beats static
- Kelly Criterion (1956): Reduce bet size when uncertainty is high

### Complexity: **Low-Medium**
- 2-3 days implementation
- Need to add VIX or realized volatility tracking
- Threshold lookup table in config

### Effectiveness: **Medium-High**
- October 2018: VIX spiked from 12 → 25, would have triggered defensive mode
- Reduces exposure before crash deepens, auto-recovers after

### Pros
- ✅ Self-adjusting to market conditions
- ✅ No black-box ML — logic is explainable
- ✅ Prevents overconfidence in calm markets
- ✅ Combines well with Option 1

### Cons
- ❌ VIX lags — by the time it spikes, damage may be done
- ❌ Risk of missing recovery (too defensive for too long)
- ❌ Needs parameter tuning (what's "high" volatility?)

---

## Option 3: HMM Regime Detection Module

### Description
Train a Hidden Markov Model to classify market regimes (Bull / Sideways / Bear) using SPY returns, VIX, and credit spreads. Override trading signals based on detected regime.

**Regime Actions:**
| Regime | Detection Signal | Action |
|--------|------------------|--------|
| Bull | HMM state 0, P(bull) > 0.7 | Normal trading, full position sizes |
| Sideways | HMM state 1, no clear direction | Reduce new positions by 50%, tighter stops |
| Bear | HMM state 2, P(bear) > 0.6 | No new buys, sell threshold → 55, aggressive stops |

### Based On
- Hamilton (1989): Foundational regime-switching model
- Guidolin & Timmermann (2007): Multi-asset regime detection
- Nystrup et al. (2015): HMM outperforms static allocation by 2-4% annually

### Complexity: **Medium**
- 1-2 weeks for research + implementation
- Libraries: `hmmlearn` (Python), lightweight
- Train on 10+ years of SPY data
- Need to handle regime persistence vs. false signals

### Effectiveness: **High**
- Q4 2018: HMM would likely detect Bear regime by late October
- 2015-2016 chop: Would reduce false buys in sideways market
- Historically adds 2-4% annual alpha in academic studies

### Pros
- ✅ Proactive — detects regime early, not reactive to losses
- ✅ Well-researched, proven in academic literature
- ✅ Single model covers market-wide risk
- ✅ Can display regime to users ("Market Caution Mode")

### Cons
- ❌ Requires training and validation pipeline
- ❌ Regime transitions are noisy — false positives possible
- ❌ Overfitting risk if tuned on same period as backtest
- ❌ Still need per-position exit rules (combine with Option 1)

---

## Option 4: RL-Based Position Sizing (Advanced)

### Description
Train a reinforcement learning agent to decide position sizes and hold/exit decisions based on state (score, P&L, volatility, regime). The agent learns optimal policy from historical data.

**State Space:**
- Current composite score
- Unrealized P&L %
- Days held
- Market regime (from Option 3)
- Sector volatility

**Action Space:**
- Hold, Add, Trim 25%, Trim 50%, Exit

**Reward:**
- Risk-adjusted return (Sharpe-weighted)
- Penalty for large drawdowns

### Based On
- FinRL (2020): Liu et al. — open-source DRL framework for trading
- Deng et al. (2017): Deep RL for financial signal representation

### Complexity: **High**
- 3-4 weeks minimum for proper implementation
- Requires significant training data and compute
- Prone to overfitting — needs robust cross-validation
- FinRL provides starter code but needs customization

### Effectiveness: **Potentially High, but Risky**
- Academic papers show strong results, but often in idealized conditions
- Real-world deployment is tricky — may overfit, may not generalize

### Pros
- ✅ Learns nuanced exit strategies human rules miss
- ✅ Can discover non-obvious patterns
- ✅ Framework (FinRL) exists, not building from scratch
- ✅ Maximizes specific objective (Sharpe, return, etc.)

### Cons
- ❌ Black box — hard to explain to users
- ❌ Overfitting is a serious risk
- ❌ Requires ongoing monitoring and retraining
- ❌ Overkill for a small team
- ❌ Could make weird decisions in novel market conditions

---

## Recommendation

**For immediate impact (Week 1):**
> Implement **Option 1 (Rule-Based Exits)** + **Option 2 (Volatility Scaling)**

This combination:
- Caps downside with stop-losses
- Adapts to market stress automatically
- Zero ML complexity
- Can be backtested in 1 day

**For next quarter (Strategic):**
> Add **Option 3 (HMM Regime Detection)** as a market-level overlay

This gives:
- Proactive risk management
- User-visible "market caution" indicator
- Proven academic backing

**Skip Option 4** unless the team grows. RL is powerful but fragile — the complexity-to-benefit ratio is poor for a small team.

---

## Implementation Priority

| Phase | Option | Effort | Impact | Timeline |
|-------|--------|--------|--------|----------|
| 1 | Rule-Based Exits | 2 days | High | Week 1 |
| 1 | Volatility Scaling | 2 days | Medium-High | Week 1 |
| 2 | HMM Regime Module | 2 weeks | High | Q1 2026 |
| 3 | RL Position Sizing | 4+ weeks | Uncertain | Defer |

---

## Re-Backtest Requirement

After implementing Options 1 + 2:
- Re-run the 18-month backtest (Jun 2018 - Nov 2019)
- Target: Reduce drawdown from -21% to ≤-12%
- Target: Improve Sharpe from 0.40 to ≥1.5
- Target: Positive alpha (currently -14.38%)

If targets not hit, adjust stop-loss thresholds or add Option 3.

---

*Document compiled from REFERENCES.md Sections 4, 5, 6*
