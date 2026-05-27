# Codex Prompt: Trading Final Project Build-Out

You are working inside this repo for Matthew Goodman's trading final project.

Goal: convert the setup-first retail-hype intraday project into a reproducible research repo with a paper-trading execution path.

Hard rules:

- Do not turn this into an autonomous live trading bot.
- Do not add market orders.
- Do not add options, crypto, margin, or short-live execution.
- Keep live mode off by default.
- Treat `data/final_project_trade_setups.csv` as the source of truth for the project.
- The model may only gate named setups. It may not choose arbitrary tickers.
- Generated IBKR intents must default to `active=false`.
- Any live-enabled intent must pass ticker allowlist, time-window, notional, spread, quote-size, and kill-switch checks.

Next coding tasks:

1. Improve `research/apply_trade_setups.py` so each setup family has transparent rule diagnostics.
2. Add `research/backtest_trade_setups.py` to compare setup-only vs. ML-gated results.
3. Add cost model output: commission, spread, slippage buffer, net forward return.
4. Add train/test split by date, never random row split.
5. Add a report generator that writes tables into `data/reports/`.
6. Expand the notebook into a final-project report.
7. Add tests for setup parsing, window parsing, and no-live-short behavior.
