<img src="sigil_logo.jpg" alt="Sigil" width="240" />

# Academic References — TradingApp iOS

## 1. Multi-Factor Ranking Model

### Foundational Papers

**Fama-French Three-Factor Model (1993)**
- Fama, E. F., & French, K. R. (1993). *Common risk factors in the returns on stocks and bonds.* Journal of Financial Economics, 33(1), 3-56.
- URL: https://doi.org/10.1016/0304-405X(93)90023-5
- **Key insight:** Market, size (SMB), and value (HML) factors explain stock returns

**Carhart Four-Factor Model (1997)**
- Carhart, M. M. (1997). *On persistence in mutual fund performance.* Journal of Finance, 52(1), 57-82.
- URL: https://doi.org/10.1111/j.1540-6261.1997.tb03808.x
- **Key insight:** Added momentum factor to Fama-French

**Fama-French Five-Factor Model (2015)**
- Fama, E. F., & French, K. R. (2015). *A five-factor asset pricing model.* Journal of Financial Economics, 116(1), 1-22.
- URL: https://doi.org/10.1016/j.jfineco.2014.10.010
- **Key insight:** Added profitability (RMW) and investment (CMA) factors

### Factor Investing

**Quality Minus Junk (2019)**
- Asness, C. S., Frazzini, A., & Pedersen, L. H. (2019). *Quality minus junk.* Review of Accounting Studies, 24, 34-112.
- URL: https://doi.org/10.1007/s11142-018-9470-2
- **Key insight:** Quality factor definition and returns

**Momentum (1993)**
- Jegadeesh, N., & Titman, S. (1993). *Returns to buying winners and selling losers.* Journal of Finance, 48(1), 65-91.
- URL: https://doi.org/10.1111/j.1540-6261.1993.tb04702.x
- **Key insight:** 3-12 month momentum predicts returns

---

## 2. Sentiment Analysis Models

### FinBERT & Financial NLP

**FinBERT (2019)**
- Araci, D. (2019). *FinBERT: Financial Sentiment Analysis with Pre-trained Language Models.* arXiv preprint.
- URL: https://arxiv.org/abs/1908.10063
- **Key insight:** BERT fine-tuned on financial text outperforms general models

**FinBERT by ProsusAI (2020)**
- Huang, A. H., Wang, H., & Yang, Y. (2020). *FinBERT: A Pre-trained Financial Language Representation Model for Financial Text Mining.* IJCAI 2020.
- URL: https://www.ijcai.org/proceedings/2020/622
- **Key insight:** Pre-training on financial corpus improves performance

**BloombergGPT (2023)**
- Wu, S., et al. (2023). *BloombergGPT: A Large Language Model for Finance.* arXiv preprint.
- URL: https://arxiv.org/abs/2303.17564
- **Key insight:** 50B parameter model trained on 363B tokens of financial data

**FinGPT (2023)**
- Yang, H., et al. (2023). *FinGPT: Open-Source Financial Large Language Models.* arXiv preprint.
- URL: https://arxiv.org/abs/2306.06031
- **Key insight:** Open-source alternative using LoRA fine-tuning

### Sentiment & Stock Returns

**Textual Analysis in Finance (2016)**
- Loughran, T., & McDonald, B. (2016). *Textual Analysis in Accounting and Finance: A Survey.* Journal of Accounting Research, 54(4), 1187-1230.
- URL: https://doi.org/10.1111/1475-679X.12123
- **Key insight:** Survey of NLP methods in finance

**News Sentiment & Stock Returns (2007)**
- Tetlock, P. C. (2007). *Giving content to investor sentiment.* Journal of Finance, 62(3), 1139-1168.
- URL: https://doi.org/10.1111/j.1540-6261.2007.01232.x
- **Key insight:** Media pessimism predicts market downturns

---

## 3. Earnings Surprise Model

### Earnings Predictability

**Post-Earnings Announcement Drift (1968)**
- Ball, R., & Brown, P. (1968). *An empirical evaluation of accounting income numbers.* Journal of Accounting Research, 6(2), 159-178.
- URL: https://doi.org/10.2307/2490232
- **Key insight:** Stock prices don't immediately adjust to earnings news

**Earnings Momentum (1996)**
- Chan, L. K., Jegadeesh, N., & Lakonishok, J. (1996). *Momentum strategies.* Journal of Finance, 51(5), 1681-1713.
- URL: https://doi.org/10.1111/j.1540-6261.1996.tb05222.x
- **Key insight:** Earnings surprises predict future returns

**Analyst Forecasts (2001)**
- Bradshaw, M. T. (2001). *The use of target prices to justify sell-side analysts' stock recommendations.* Accounting Horizons, 16(1), 27-41.
- **Key insight:** Analyst estimate revisions signal information

---

## 4. Macro Regime Detection (HMM)

### Hidden Markov Models in Finance

**Regime Switching Models (1989)**
- Hamilton, J. D. (1989). *A new approach to the economic analysis of nonstationary time series and the business cycle.* Econometrica, 57(2), 357-384.
- URL: https://doi.org/10.2307/1912559
- **Key insight:** Foundational paper on regime-switching models

**HMM for Market Regimes (2012)**
- Nystrup, P., Hansen, B. W., Madsen, H., & Lindström, E. (2015). *Regime-based versus static asset allocation.* Journal of Portfolio Management, 42(1), 103-115.
- URL: https://doi.org/10.3905/jpm.2015.42.1.103
- **Key insight:** HMM-based allocation outperforms static

**Economic Regime Detection (2017)**
- Guidolin, M., & Timmermann, A. (2007). *Asset allocation under multivariate regime switching.* Journal of Economic Dynamics and Control, 31(11), 3503-3544.
- URL: https://doi.org/10.1016/j.jedc.2006.12.004
- **Key insight:** Multi-asset regime detection framework

---

## 5. Reinforcement Learning for Trading

### FinRL Framework

**FinRL (2020)**
- Liu, X. Y., Yang, H., Chen, Q., et al. (2020). *FinRL: A Deep Reinforcement Learning Library for Automated Stock Trading.* NeurIPS 2020 Workshop.
- URL: https://arxiv.org/abs/2011.09607
- GitHub: https://github.com/AI4Finance-Foundation/FinRL
- **Key insight:** Open-source DRL framework for trading

**Deep Reinforcement Learning for Trading (2017)**
- Deng, Y., Bao, F., Kong, Y., Ren, Z., & Dai, Q. (2017). *Deep direct reinforcement learning for financial signal representation and trading.* IEEE Transactions on Neural Networks and Learning Systems, 28(3), 653-664.
- URL: https://doi.org/10.1109/TNNLS.2016.2522401
- **Key insight:** DRL for intraday trading

---

## 6. Portfolio Optimization & Risk

### Modern Portfolio Theory

**Mean-Variance Optimization (1952)**
- Markowitz, H. (1952). *Portfolio selection.* Journal of Finance, 7(1), 77-91.
- URL: https://doi.org/10.1111/j.1540-6261.1952.tb01525.x
- **Key insight:** Foundational portfolio theory

**Kelly Criterion (1956)**
- Kelly, J. L. (1956). *A new interpretation of information rate.* Bell System Technical Journal, 35(4), 917-926.
- URL: https://doi.org/10.1002/j.1538-7305.1956.tb03809.x
- **Key insight:** Optimal bet sizing for long-term growth

### Risk Management

**Value at Risk (1996)**
- Jorion, P. (1996). *Value at Risk: The New Benchmark for Controlling Market Risk.* McGraw-Hill.
- **Key insight:** VaR methodology for risk measurement

**Black Swan Events (2007)**
- Taleb, N. N. (2007). *The Black Swan: The Impact of the Highly Improbable.* Random House.
- **Key insight:** Fat tails and model limitations

---

## 7. Market Microstructure

### Execution & Slippage

**Market Microstructure (2010)**
- Hasbrouck, J. (2010). *Empirical Market Microstructure.* Oxford University Press.
- **Key insight:** Comprehensive market microstructure text

**Optimal Execution (2001)**
- Almgren, R., & Chriss, N. (2001). *Optimal execution of portfolio transactions.* Journal of Risk, 3, 5-40.
- URL: https://doi.org/10.21314/JOR.2001.041
- **Key insight:** Minimizing market impact in large orders

---

## Books (Essential Reading)

1. **Advances in Financial Machine Learning** — Marcos López de Prado (2018)
   - Wiley. ISBN: 978-1119482086
   - Topics: Feature engineering, backtesting, ML for finance

2. **Machine Learning for Asset Managers** — Marcos López de Prado (2020)
   - Cambridge Elements. ISBN: 978-1108792899
   - Topics: Factor investing with ML

3. **Quantitative Trading** — Ernest P. Chan (2009)
   - Wiley. ISBN: 978-0470284889
   - Topics: Practical algorithmic trading

4. **Algorithmic Trading** — Ernest P. Chan (2013)
   - Wiley. ISBN: 978-1118460146
   - Topics: Mean reversion, momentum strategies

5. **Active Portfolio Management** — Grinold & Kahn (1999)
   - McGraw-Hill. ISBN: 978-0070248823
   - Topics: Information ratio, factor models

---

## Online Resources

- **SSRN Finance Papers:** https://papers.ssrn.com/sol3/JELJOUR_Results.cfm?form_name=journalbrowse&journal_id=898250
- **arXiv Quantitative Finance:** https://arxiv.org/list/q-fin/recent
- **Journal of Financial Economics:** https://www.sciencedirect.com/journal/journal-of-financial-economics
- **Review of Financial Studies:** https://academic.oup.com/rfs

---

*Compiled: February 2, 2026*
