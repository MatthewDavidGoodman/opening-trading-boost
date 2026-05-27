# Trading Final Project: Retail-Hype Intraday Execution

## Title

**Retail-Hype Intraday Execution Under Capital and Liquidity Constraints**

This is a setup-first trading project. The model does not start by searching the whole market. It starts with a small hand-picked universe, named trade setups, and explicit trading hypotheses.

## Core question

Can a small-capital trader improve intraday paper-trading results in retail-hype names by combining:

1. a fixed meme/retail-hype universe,
2. setup-specific time windows,
3. liquidity and spread gates,
4. simple ML gates over named setups,
5. limit-order-only execution through IBKR paper trading?

## Starting universe

| Symbol | Role |
|---|---|
| SOUN | AI meme / retail-hype primary name |
| GME | classic meme reflexivity test; research only by default |
| AMC | classic meme liquidity/reversal test; research only by default |
| RKLB | space/defense retail theme with better liquidity |
| LUNR | headline-sensitive space event name |
| ACHR | eVTOL / aerospace mobility retail-beta name |
| BBAI | AI-defense hype name |
| KOSS | thin legacy meme; liquidity rejection test |
| RIVN | larger EV retail-beta liquidity control |

These are not recommendations. They are research instruments for testing microstructure and execution behavior.

## Named setups

### 1. SOUN_OPEN_RECLAIM — AI hype open reclaim

**Hypothesis:** AI meme names may continue after a weak open only when volume validates the reclaim.

**Rule:** 10:00–11:15 ET, price turns positive over the recent bars, price is above short moving-average proxy, and relative volume is above threshold.

**Model question:** Does ML improve setup selection after accounting for costs?

### 2. GME_OPEN_EXHAUSTION — classic meme opening exhaustion

**Hypothesis:** Classic meme openings often overextend before mean-reverting.

**Rule:** 09:45–10:30 ET, early momentum is extended but recent bars weaken.

**Execution status:** research/paper-short only; not live-enabled.

**Model question:** Can the model separate continuation squeezes from fake breakouts?

### 3. AMC_FLUSH_RECLAIM — classic meme flush reclaim

**Hypothesis:** Long-only reclaims after panic flushes may be cleaner than chasing opening strength.

**Rule:** 10:15–11:30 ET, early selloff followed by positive 3-bar turn and relative-volume confirmation.

**Execution status:** research only by default.

### 4. RKLB_SPACE_CONTINUATION — space theme volume continuation

**Hypothesis:** More liquid space retail names may trend intraday when price and volume confirm the same theme.

**Rule:** 10:00–11:30 ET, positive 12-bar return, positive 3-bar return, above-normal volume, price above short moving average.

### 5. LUNR_EVENT_REVERSAL — space event gap reversal

**Hypothesis:** Headline-sensitive space names can overreact early, then become long-only reversal tests.

**Rule:** 10:15–11:30 ET, negative early move followed by reclaim and volume confirmation.

### 6. ACHR_EVTOL_RECLAIM — eVTOL open reclaim

**Hypothesis:** Aerospace mobility story stocks may behave like AI hype names when retail attention is active.

**Rule:** same family as SOUN open reclaim, but tested as cross-theme transfer.

### 7. BBAI_AI_DEFENSE_MOMENTUM — AI-defense momentum continuation

**Hypothesis:** AI-defense hype trends only when price and relative volume agree.

**Rule:** momentum continuation with stricter relative-volume threshold.

### 8. KOSS_LIQUIDITY_REJECT — thin meme liquidity rejection

**Hypothesis:** Some names are interesting for research but should be rejected by execution-quality rules.

**Rule:** log the setup, but do not send orders. This proves why spread, quote depth, and dollar volume matter.

### 9. RIVN_RETAIL_BETA_CONTINUATION — liquid retail-beta control

**Hypothesis:** A larger, more liquid retail-hype name should show whether the strategy works only in chaotic thin names or also in better execution conditions.

## Data plan

Use two data paths:

1. **Downloaded bars** for research/backtest via `yfinance`.
2. **IBKR paper quote stream** for live paper-session quote/fill study.

Suggested research bar interval:

```bash
python research/download_prices.py \
  --universe data/final_project_universe.csv \
  --period 60d \
  --interval 5m
```

Feature build:

```bash
python research/build_features.py \
  --policy config/model_policy.example.toml
```

Apply named setups:

```bash
python research/apply_trade_setups.py \
  --features data/features/features.csv \
  --setups data/final_project_trade_setups.csv \
  --out data/reports/setup_occurrences.csv
```

Export inactive intent rows for review:

```bash
python research/export_trade_intents_from_setups.py \
  --setup-occurrences data/reports/setup_occurrences.csv \
  --out data/intents.generated.csv \
  --mode paper
```

Review through the execution cage:

```bash
python -m ibkr_microexec.cli review-intents \
  --config config/meme_stock_trading_plan.example.toml \
  --intents data/intents.generated.csv
```

## ML role

ML is not the stock picker.

The setup is chosen first. ML answers:

> Given that this named setup appeared, should the trade be taken or skipped?

Good first models:

- logistic regression,
- random forest,
- gradient boosting if installed,
- conformal-style confidence gate or simple probability threshold.

Target variable:

```text
future return over next 3 bars > spread + commission + slippage buffer
```

This fits a trading final project because it separates:

- hypothesis design,
- data engineering,
- microstructure-aware costs,
- ML gate,
- IBKR paper execution,
- post-trade evaluation.

## Metrics

Report the following:

- gross return,
- net return after estimated costs,
- hit rate,
- average trade return,
- Sharpe or t-stat by setup family,
- max drawdown,
- turnover,
- no-trade rate,
- setup rejection reasons,
- spread paid,
- fill quality against mid/limit,
- time-window performance.

## Final write-up structure

1. Introduction: retail hype is not only an alpha problem; it is an execution problem.
2. Universe and setup design.
3. Data and feature construction.
4. Setup-only baseline.
5. ML-gated setup model.
6. Cost and liquidity filter.
7. IBKR paper execution layer.
8. Results by setup family and time of day.
9. Failure cases.
10. Conclusion: when the model should trade, pass, or reject the name entirely.
