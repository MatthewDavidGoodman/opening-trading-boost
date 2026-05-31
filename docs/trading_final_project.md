# Trading Final Project: Retail-Hype Intraday Execution

## Title

**Retail-Hype Intraday Execution Under Capital and Liquidity Constraints**

This is a setup-first trading project. The model does not start by searching the whole market. It starts with a small hand-picked universe, named trade setups, and explicit trading hypotheses.

## Core question

Can a small-capital trader improve intraday simulated results in retail-hype names by combining:

1. a fixed meme/retail-hype universe,
2. setup-specific time windows,
3. liquidity and spread gates,
4. simple ML gates over named setups,
5. conservative L2 fill assumptions using historical order book data?

## Starting universe

| Symbol | Role |
|---|---|
| SOUN | AI meme / retail-hype primary name |
| RKLB | space/defense retail theme with better liquidity |
| ACHR | eVTOL / aerospace mobility retail-beta name |
| RIVN | larger EV retail-beta liquidity control |
| BBAI | optional AI-defense hype name when added to config |

These are not recommendations. They are research instruments for testing microstructure and execution behavior.

## Legacy/fallback OHLCV named setups

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

## Primary data plan: Databento L2

The final project uses Databento historical market-by-price data as its primary source:

- schema: `mbp-10`
- top ten bid and ask levels
- one-minute feature resampling
- raw DBN files under `data/databento/raw/`
- processed per-symbol files under `data/databento/processed/`
- final panel at `data/features/l2_features.csv`

Set `DATABENTO_API_KEY` in the environment before making a real request. Update the dataset, date range, and `stype_in` placeholders in `config/databento_l2.example.toml` for the Databento dataset available to your account.

Preview the request without credentials or a network call:

```bash
python research/download_databento_l2.py \
  --config config/databento_l2.example.toml \
  --dry-run
```

After reviewing cost and dataset availability, download MBP-10:

```bash
export DATABENTO_API_KEY="..."
python research/download_databento_l2.py \
  --config config/databento_l2.example.toml
```

Build the L2 feature panel:

```bash
python research/build_l2_features.py \
  --config config/databento_l2.example.toml
```

Apply the setup-first L2 rules:

```bash
python research/apply_l2_setups.py \
  --config config/databento_l2.example.toml
```

Simulate conservative paper-only fills:

```bash
python research/simulate_l2_trades.py \
  --config config/databento_l2.example.toml
```

The simulation enters long setups at the ask, exits at the bid after the configured holding period, and subtracts estimated costs. It does not submit orders.

## L2 setups

- `L2_RECLAIM_LONG`: liquidity passes, five-minute midprice return is positive, ten-level imbalance favors bids, microprice is above midprice, and the latest one-minute return turns positive after a non-positive bar.
- `L2_MOMENTUM_CONFIRMATION`: liquidity passes with the same L2 long confirmation conditions and a positive one-minute midprice return.
- `L2_LIQUIDITY_REJECT`: spread or ten-level depth fails the configured standards.

## Legacy/fallback prototype data

The existing `yfinance` OHLCV pipeline remains available as a legacy/fallback prototype. It is not the primary final-project data source:

```bash
python research/download_prices.py --universe data/final_project_universe.csv --period 60d --interval 5m
python research/build_features.py --policy config/model_policy.example.toml
python research/apply_trade_setups.py --features data/features/features.csv --out data/reports/setup_occurrences.csv
```

IBKR is not required for the final project. The guarded execution starter and inactive intent exporter remain separate optional review tooling. No IBKR connection or order placement is part of the Databento L2 pipeline.

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
7. Conservative L2 fill simulation.
8. Results by setup family and time of day.
9. Failure cases.
10. Conclusion: when the model should trade, pass, or reject the name entirely.
