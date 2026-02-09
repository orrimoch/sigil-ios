<img src="sigil_logo.jpg" alt="Sigil" width="240" />

# Agentic Risk Management: Research Analysis

**Based on: [Open-Finance-Lab/AgenticTrading](https://github.com/Open-Finance-Lab/AgenticTrading)**  
**Author:** Jifeng Li @ SecureFinAI Lab  
**License:** OpenMDW-1.0  
**Report Date:** 2026-02-08

---

## Executive Summary

This document analyzes the **AgenticTrading** framework from Open-Finance-Lab as a potential reference architecture for implementing risk management features in Sigil. The framework provides a comprehensive multi-agent system for algorithmic trading with specialized pools for risk analysis, backtesting, and performance attribution.

**Key Findings:**
- ✅ Mature risk agent architecture with VaR, stress testing, and position limits
- ✅ LLM-powered natural language to structured task conversion
- ✅ Memory system for pattern discovery and regime tracking
- ⚠️ Requires Neo4j + OpenAI (adds infrastructure complexity)
- ⚠️ Different paradigm (stock-first vs. our universe-first scoring)
- 📊 **80,627 lines of Python** across agent pools

---

## 1. Architecture Overview

### 1.1 Framework Philosophy

AgenticTrading reframes algorithmic trading as a **multi-agent ecosystem**. Each stage of the trading pipeline is embodied by autonomous agents with reasoning, tool access, and memory.

| Traditional AT | Agentic Trading |
|----------------|-----------------|
| Linear rule-based modules | Multi-agent graph with contextual interactions |
| Static strategies | Agents learn and adapt via memory |
| Model-centric optimization | System-centric holistic feedback |
| Manual data flows | DAG-based orchestration |
| Post-hoc backtest only | Continuous auditing by Audit Agents |

### 1.2 Agent Pool Structure

```
FinAgents/
├── orchestrator/          # DAG Controller, Protocols
├── agent_pools/
│   ├── alpha_agent_pool/       # Signal generation (2,561 lines)
│   ├── risk_agent_pool/        # Risk management (core.py: 31KB)
│   ├── backtest_agent/         # Performance evaluation (2,608 lines)
│   ├── portfolio_construction_agent_pool/
│   ├── transaction_cost_agent_pool/
│   └── data_agent_pool/        # Market data acquisition
└── memory/                 # Neo4j + vector embeddings (56KB)
```

---

## 2. Risk Agent Pool (Most Relevant to Sigil)

### 2.1 Available Risk Agents

| Agent | File | Lines | Purpose |
|-------|------|-------|---------|
| **MarketRiskAgent** | `market_risk.py` | ~200 | Volatility, VaR, beta analysis |
| **VaRAgent** | `var_calculator.py` | ~300 | Parametric, Historical, Monte Carlo VaR |
| **VolatilityAgent** | `volatility.py` | ~250 | GARCH, implied vol, clustering |
| **CreditRiskAgent** | `credit_risk.py` | 987 | PD, LGD, credit VaR |
| **LiquidityRiskAgent** | `liquidity_risk.py` | 1,276 | Bid-ask, market impact, funding |
| **OperationalRiskAgent** | `operational_risk.py` | ~400 | Fraud detection, KRI monitoring |
| **StressTestingAgent** | `stress_testing.py` | ~500 | Scenario analysis, Monte Carlo |
| **ModelRiskAgent** | `model_risk.py` | ~350 | Model validation, governance |
| **CorrelationAgent** | `registry.py` | ~150 | Tail dependencies, copulas |

### 2.2 Key Risk Metrics Implemented

```python
# VaR Calculations (from var_calculator.py)
- Parametric VaR (95%, 99%, 99.9% confidence)
- Historical VaR
- Monte Carlo VaR
- Expected Shortfall (CVaR)

# Volatility Analysis (from volatility.py)
- Historical volatility (30/60/252-day)
- Implied volatility with skew
- GARCH(1,1) forecasting
- Volatility regime detection (high/medium/low)

# Market Impact (from liquidity_risk.py)
- Temporary impact modeling
- Permanent impact estimation
- Square-root impact model
- Liquidity scoring (0-10)
```

### 2.3 Risk Agent Interface

All risk agents implement a common `BaseRiskAgent` interface:

```python
class BaseRiskAgent(ABC):
    async def analyze(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Perform risk analysis based on request."""
        pass
    
    async def cleanup(self):
        """Clean up resources when shut down."""
        pass
```

**Example Usage:**
```python
market_risk_agent = MarketRiskAgent()
result = await market_risk_agent.analyze({
    "portfolio_data": portfolio,
    "risk_measures": ["var", "volatility", "beta"],
    "time_horizon": "daily"
})
```

---

## 3. Memory & Pattern System

### 3.1 Architecture

The memory system uses **Neo4j graph database** with **vector embeddings** for semantic search:

```
FinAgents/memory/
├── memory_server.py              # Main server (56KB)
├── intelligent_memory_indexer.py # Vector embeddings (18KB)
├── database.py                   # Neo4j schema (17KB)
├── database_initializer.py       # DB setup (18KB)
├── mcp_server.py                 # MCP protocol interface
└── llm_research_service.py       # LLM integration
```

### 3.2 Memory Features

| Feature | Implementation |
|---------|----------------|
| **Pattern Storage** | Store market patterns with success rates, frequency, statistical significance |
| **Regime Detection** | Track volatility_regime, trend_direction, market_stress levels |
| **Semantic Search** | TF-IDF or SentenceTransformers (`all-MiniLM-L6-v2`) embeddings |
| **Performance Tracking** | Store Sharpe, returns, win rates per strategy |
| **Event Logging** | Structured logging of all agent actions |

### 3.3 Pattern Record Structure

```python
@dataclass
class MemoryPatternRecord:
    pattern_id: str
    pattern_type: str  # e.g., "momentum_reversal", "mean_reversion_gap"
    pattern_features: Dict[str, Any]  # RSI, MACD, volume_ratio
    associated_outcomes: List[Dict]   # Historical signal results
    success_rate: float
    pattern_frequency: int
    market_conditions: Dict[str, Any]  # regime, trend, stress
    statistical_significance: float
    agent_source: str
```

---

## 4. Backtest Agent (Performance Attribution)

### 4.1 Capabilities

The `backtest_agent.py` (2,608 lines) provides:

| Feature | Description |
|---------|-------------|
| **Qlib Integration** | Full integration with Microsoft's Qlib framework |
| **Risk-Adjusted Metrics** | Sharpe, Sortino, Calmar ratios |
| **Walk-Forward Analysis** | Rolling window validation |
| **Factor Attribution** | IC analysis, factor contribution |
| **Transaction Costs** | Realistic slippage and commission modeling |
| **Visualization** | Equity curves, drawdown charts (via `backtest_visualizer.py`) |

### 4.2 Paper Interface Design

The backtest follows an academic "paper interface" with three components:

```python
# 1. Alpha Model → Signal generation
alpha_model = {
    "factors": [...],
    "weights": [...],
    "expected_return": 0.015
}

# 2. Risk Model → Position constraints
risk_model = {
    "var_limit": 0.05,
    "max_position_size": 0.15,
    "sector_limits": {...}
}

# 3. Transaction Cost Model → Execution
cost_model = {
    "commission_rate": 0.001,
    "slippage_rate": 0.0005,
    "market_impact": "square_root"
}
```

---

## 5. Technologies & Dependencies

### 5.1 Core Stack

| Technology | Purpose | Required? |
|------------|---------|-----------|
| **Python 3.8+** | Runtime | ✅ Yes |
| **FastAPI** | MCP server | ✅ Yes |
| **OpenAI API** | Context decomposition, NL→structured | ✅ Yes |
| **Neo4j** | Pattern memory, graph queries | ⚠️ For full memory |
| **NumPy/Pandas** | Data processing | ✅ Yes |
| **MCP (Model Context Protocol)** | Agent communication | ✅ Yes |
| **Qlib** | Backtesting framework | ⚠️ Optional |
| **SentenceTransformers** | Semantic embeddings | ⚠️ Optional |

### 5.2 Key Dependencies (requirements.txt)

```
mcp==1.13.1
openai==1.101.0
pandas==2.3.2
numpy==2.3.2
pydantic==2.11.7
fastapi
uvicorn
aiohttp
networkx
scikit-learn
```

### 5.3 Cost Estimates

| Service | Usage | Est. Monthly Cost |
|---------|-------|-------------------|
| **OpenAI API** | Context parsing (gpt-4o-mini) | $5-20 |
| **Neo4j Aura** | Cloud database | $0 (free tier) - $65 |
| **Self-hosted Neo4j** | Local database | $0 |
| **SentenceTransformers** | Local embeddings | $0 |

**Total:** $5-85/month depending on configuration

---

## 6. Training Requirements

### 6.1 ML Models in the Framework

| Model | Training Required? | Data Needed |
|-------|-------------------|-------------|
| **LLM (OpenAI)** | ❌ No (API) | N/A |
| **GARCH Volatility** | ✅ Per-stock | 252+ days returns |
| **HMM Regime** | ✅ Initial fit | 5+ years market data |
| **VaR Models** | ⚠️ Calibration | 1+ year returns |
| **SentenceTransformers** | ❌ Pre-trained | N/A |
| **Qlib ML Models** | ✅ Full training | Years of OHLCV |

### 6.2 Training Approach

The framework uses **no-training or minimal calibration** for most risk calculations:

```python
# Volatility: Historical calculation (no training)
volatility = returns.std() * np.sqrt(252)

# VaR: Parametric (no training, uses z-score)
var_95 = portfolio_value * volatility * 1.645

# Regime Detection: HMM (requires initial fit)
from hmmlearn import GaussianHMM
model = GaussianHMM(n_components=3)
model.fit(returns_data)  # One-time training
```

---

## 7. High-Level Implementation for Sigil

### 7.1 Recommended Components to Adopt

| Component | Priority | Effort | Impact |
|-----------|----------|--------|--------|
| **VaR Calculator** | 🔴 High | 2 days | Stop-loss automation |
| **Dynamic Thresholds** | 🔴 High | 1 day | VIX-adjusted SELL signals |
| **Position Limits** | 🔴 High | 1 day | Max 15% per stock |
| **Trailing Stop-Loss** | 🔴 High | 1 day | Protect gains |
| **Volatility Regime** | 🟡 Medium | 3 days | Adaptive trading |
| **Pattern Memory** | 🟡 Medium | 1 week | Market regime tracking |
| **Performance Attribution** | 🟢 Low | 1 week | Advanced analytics |

### 7.2 Proposed Sigil Integration

```
backend/src/
├── risk/                         # NEW: Risk management module
│   ├── __init__.py
│   ├── var_calculator.py         # VaR (parametric, historical)
│   ├── position_limits.py        # Max position size, sector limits
│   ├── stop_loss.py              # Hard stop, trailing stop
│   ├── dynamic_thresholds.py     # VIX-adjusted SELL thresholds
│   └── regime_detector.py        # HMM-based market regime
├── scoring/
│   └── pipeline.py               # Integrate risk signals
└── backtest/
    └── engine.py                 # Add risk rules to backtester
```

### 7.3 Quick Win: Minimum Viable Risk System

From the AI Engineer's analysis, these 3 rules would prevent the -21% drawdown:

```python
def should_sell(position):
    # Rule 1: Hard stop
    if position.unrealized_pnl_pct <= -0.08:
        return True, "Hard stop hit (-8%)"
    
    # Rule 2: Trailing stop
    if position.drawdown_from_peak <= -0.10:
        return True, "Trailing stop hit (-10% from peak)"
    
    # Rule 3: VIX-adjusted threshold
    vix = get_current_vix()
    adjusted_threshold = 50 + max(0, (vix - 15) * 0.5)
    if position.score < adjusted_threshold:
        return True, f"Score {position.score} below threshold {adjusted_threshold}"
    
    return False, None
```

---

## 8. Comparison: AgenticTrading vs. Sigil

| Aspect | AgenticTrading | Sigil |
|--------|----------------|-------|
| **Paradigm** | Stock-first (analyze what you ask) | Universe-first (score all 677 stocks) |
| **Scoring** | Per-strategy signals (0.0-1.0 confidence) | Composite 0-100 score (Fund+Sent+Tech+Macro) |
| **Signal Logic** | Strategy-specific rules | Static thresholds (BUY≥70, SELL<50) |
| **Risk Management** | Comprehensive (VaR, limits, stress) | Basic (backtest only) |
| **Memory** | Neo4j + vector embeddings | SQLite weekly scores |
| **LLM Usage** | Context parsing, NL→structured | Sentiment scoring |
| **Infrastructure** | Neo4j + OpenAI required | SQLite + Claude |
| **Codebase** | 80,627 lines | ~15,000 lines |

---

## 9. Recommendations

### 9.1 Immediate Actions (Week 1)

1. **Extract VaR patterns** from `risk_agent_pool/agents/var_calculator.py`
2. **Implement hard stop + trailing stop** rules in `backtest/engine.py`
3. **Add dynamic SELL thresholds** based on VIX (from `risk_agent_pool/registry.py`)

### 9.2 Short-Term (Weeks 2-3)

1. **Build `backend/src/risk/` module** with extracted patterns
2. **Integrate with live trading** via IBKR service
3. **Add position size limits** (Kelly criterion or fixed %)

### 9.3 Medium-Term (Month 2)

1. **Implement HMM regime detection** for market awareness
2. **Add pattern memory** (SQLite-based, no Neo4j needed)
3. **Enhance backtest reports** with attribution metrics

### 9.4 Skip for Now

- Full multi-agent orchestration (overkill)
- Neo4j memory system (SQLite sufficient)
- Qlib integration (our backtest is adequate)
- MCP protocol (not needed for Sigil's architecture)

---

## 10. Credits & References

### Original Work

**Repository:** [Open-Finance-Lab/AgenticTrading](https://github.com/Open-Finance-Lab/AgenticTrading)  
**Author:** Jifeng Li @ SecureFinAI Lab  
**License:** OpenMDW-1.0

### Academic References

- Hamilton (1989) — Regime-switching models for business cycles
- Jorion (1996) — Value at Risk methodology
- Kelly (1956) — Optimal bet sizing
- Nystrup et al. (2015) — HMM-based asset allocation

### Documentation

- [FinAgent Orchestration ReadTheDocs](https://finagent-orchestration.readthedocs.io)
- Microsoft Qlib: [https://github.com/microsoft/qlib](https://github.com/microsoft/qlib)

---

## Appendix A: File Reference

### Most Relevant Files for Sigil

| File | Path | Size | Priority |
|------|------|------|----------|
| VaR Calculator | `risk_agent_pool/agents/var_calculator.py` | ~300 lines | 🔴 High |
| Market Risk | `risk_agent_pool/agents/market_risk.py` | ~200 lines | 🔴 High |
| Stress Testing | `risk_agent_pool/agents/stress_testing.py` | ~500 lines | 🟡 Medium |
| Registry (all agents) | `risk_agent_pool/registry.py` | 711 lines | 🔴 High |
| Memory Bridge | `risk_agent_pool/memory_bridge.py` | 499 lines | 🟡 Medium |
| Core Orchestrator | `risk_agent_pool/core.py` | 777 lines | 🟢 Low |
| Backtest Agent | `backtest_agent/backtest_agent.py` | 2,608 lines | 🟡 Medium |
| Memory Indexer | `memory/intelligent_memory_indexer.py` | 508 lines | 🟢 Low |

---

*Report prepared by Blaze Neon for Sigil AI Stock Recommendation App*  
*Reviewed by PM Agent and AI Engineer Agent*

---

## Technical Review Notes

**Reviewed by:** AI Engineer Agent  
**Date:** 2026-02-08  
**Verdict:** ✅ APPROVED with minor clarifications

### Technical Accuracy Assessment

| Section | Accuracy | Notes |
|---------|----------|-------|
| VaR Calculations | ✅ Correct | Parametric VaR formula `portfolio_value * σ * 1.645` is accurate for 95% confidence |
| Volatility Annualization | ✅ Correct | `std() * √252` is the standard approach for daily→annual |
| GARCH Requirements | ✅ Reasonable | 252+ days is appropriate for stable parameter estimation |
| HMM Data Requirements | ✅ Conservative | 5+ years recommended; could work with 2+ years if regime changes are frequent |
| Implementation Estimates | ⚠️ Optimistic | See notes below |

### Clarifications

**1. Parametric VaR Assumptions (Section 6.2)**

The formula shown assumes:
- Normal distribution of returns (fat tails underestimated)
- Constant volatility (not true in stressed markets)
- No autocorrelation in returns

For production, consider adding a note that **Historical VaR** or **Monte Carlo VaR** are more robust for non-normal distributions.

**2. Portfolio VaR (Section 2.2)**

The simple formula `portfolio_value * volatility * z` works for single-position portfolios. For multi-stock portfolios, the correct formula incorporates the **covariance matrix**:

```python
# Single-stock VaR (as shown - correct)
var_single = portfolio_value * stock_volatility * 1.645

# Portfolio VaR (needed for Sigil's multi-stock portfolios)
# portfolio_var = sqrt(w' * Σ * w) * portfolio_value * z
weights = np.array([...])  # Portfolio weights
cov_matrix = returns.cov() * 252  # Annualized covariance
portfolio_vol = np.sqrt(weights @ cov_matrix @ weights)
portfolio_var = portfolio_value * portfolio_vol * 1.645
```

**3. GARCH Implementation Note (Section 6.2)**

For Python implementation, use the `arch` package:

```python
from arch import arch_model
model = arch_model(returns, vol='GARCH', p=1, q=1)
result = model.fit(disp='off')
forecast = result.forecast(horizon=1)
```

**4. Trailing Stop Logic (Section 7.3)**

The code is correct but needs a high-water-mark tracker in production:

```python
class Position:
    def __init__(self):
        self.entry_price = 0
        self.high_water_mark = 0  # Track peak value
    
    def update_price(self, current_price):
        self.high_water_mark = max(self.high_water_mark, current_price)
        self.drawdown_from_peak = (current_price - self.high_water_mark) / self.high_water_mark
```

### Missing Technical Considerations

1. **VaR Backtesting**: Consider implementing Kupiec or Christoffersen tests to validate VaR accuracy over time
2. **Liquidity-Adjusted Position Sizing**: The 15% limit should also consider average daily volume (ADV); illiquid stocks may need lower limits
3. **Corporate Actions**: Price history needs adjustment for splits/dividends before volatility calculation
4. **Look-Ahead Bias**: Ensure VIX threshold adjustments use prior-day VIX, not same-day

### Implementation Estimate Review

| Component | Documented | Revised Estimate | Notes |
|-----------|------------|------------------|-------|
| VaR Calculator | 2 days | 2-3 days | Add portfolio covariance support |
| Dynamic Thresholds | 1 day | 1 day | ✅ Realistic |
| Position Limits | 1 day | 1-2 days | Add liquidity checks |
| Trailing Stop-Loss | 1 day | 1 day | ✅ Realistic |
| Volatility Regime | 3 days | 4-5 days | HMM tuning can be tricky |
| Pattern Memory | 1 week | 1 week | ✅ Realistic for SQLite |

**Total Adjustment:** +2-4 days buffer recommended for production-quality implementation.

### Recommended Python Dependencies

For the risk module implementation:

```python
# requirements.txt additions
arch>=6.0.0           # GARCH modeling
hmmlearn>=0.3.0       # Regime detection (HMM)
scipy>=1.11.0         # Statistical functions
statsmodels>=0.14.0   # Time series analysis (already likely present)
```

### Conclusion

The document is **technically accurate** and provides a solid foundation for implementing risk management in Sigil. The code examples are correct for educational purposes; production implementation should incorporate the portfolio-level adjustments and additional safeguards noted above.

**Approved for use as implementation reference.**

---

## PM Review Notes

**Reviewer:** PM Agent  
**Date:** 2026-02-08  
**Verdict:** ✅ APPROVED with recommendations below

### Overall Assessment

This is an **excellent technical research document**—well-structured, properly prioritized, and includes concrete implementation guidance. The Section 7.3 "Quick Win" code example is exactly what engineering needs.

### Strengths
- Clear executive summary with key findings
- Effort estimates in days/weeks (enables sprint planning)
- Cost analysis for infrastructure decisions
- Explicit "Skip for Now" section prevents scope creep
- Code examples make recommendations tangible

### Recommended Additions for Stakeholder Clarity

#### 1. Business Problem Statement (Missing)
Add context at the top explaining *why* this matters:
> **Problem:** Our Feb 2025 backtest showed a -21% max drawdown during the Feb-Mar volatility spike. The current system has no automated risk controls—SELL signals only trigger when scores drop below 50, which can be too late in fast-moving markets.

#### 2. Success Metrics (Missing)
Define how we measure if this worked:
| Metric | Current | Target |
|--------|---------|--------|
| Max Drawdown | -21% | < -12% |
| False SELL Rate | N/A | < 15% |
| Avg Loss per Bad Trade | TBD | Reduce by 30% |

#### 3. User Experience Impact (Missing)
Clarify how this affects the app:
- **No UI changes for MVP** — risk rules run in backend/backtest
- **Future:** Could surface "Risk Alert" badges on portfolio positions
- **Transparency:** Consider showing users *why* a SELL was triggered

#### 4. Trade-off Acknowledgment (Missing)
Be explicit about costs:
- Dynamic thresholds may trigger earlier SELLs → fewer home runs, but smaller losses
- Hard stops lock in losses → prevents recovery, but caps downside
- **Recommendation:** Paper-trade rules for 2-4 weeks before live deployment

#### 5. Roadmap Integration (Missing)
Where does this fit in current priorities?
- **Suggest:** After REC-24 (Portfolio Overview) completes
- **Dependency:** Requires VIX data source (add to data pipeline)
- **Sprint fit:** Week 1 items (3 days) could fit in current sprint as stretch

#### 6. VIX Data Source (Unspecified)
The dynamic threshold depends on VIX. Clarify:
- **Source:** Yahoo Finance (free), CBOE (paid), or derive from SPY options?
- **Latency:** Real-time vs. delayed?
- **Fallback:** What if VIX feed fails?

#### 7. Validation Plan (Recommended)
Before going live:
1. Re-run 2024-2025 backtest WITH new risk rules
2. Compare P&L, drawdown, Sharpe vs. current system
3. Document expected hit to gross returns (acceptable trade-off?)

### Decision Matrix for Leadership

| Option | Effort | Risk Reduction | Trade-off |
|--------|--------|----------------|-----------|
| **A: Do Nothing** | 0 | 0% | Accept -21% drawdowns |
| **B: MVP Rules Only** (7.3) | 3 days | ~50% | Simple, fast |
| **C: Full Risk Module** (7.2) | 2 weeks | ~70% | Comprehensive, more testing |
| **D: Full + Memory System** | 6 weeks | ~80% | Adaptive, complex |

**PM Recommendation:** Start with **Option B**, validate in backtest, then graduate to **Option C** based on results.

### Action Items

- [ ] Add VIX to data pipeline (blocks implementation)
- [ ] Create Linear tickets for Week 1 items (REC-XX series)
- [ ] Schedule backtest validation after MVP implementation
- [ ] Define "acceptable false SELL rate" with stakeholders

---

*PM Review Complete*
