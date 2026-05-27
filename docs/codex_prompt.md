# Codex prompt pack

Use this prompt when opening the repo in Codex CLI, Codex IDE, Cursor, or a similar coding agent.

## Main prompt

You are working on `ibkr-microexec`, a Python starter repo for guarded low-volume IBKR execution.

Objective: improve the repo without turning it into an autonomous trading strategy. The product is a safe execution harness for a small account. It must support explicit ticker allowlists, explicit time windows, limit orders only, strict budget controls, dry-run / paper by default, JSONL audit logs, and tests.

Hard constraints:

- No stock recommendations.
- No market orders.
- No hidden live-trading path.
- No unattended daemon.
- No credentials in code.
- No bypass around risk checks.
- No order placement unless the CLI receives `--send` and the risk gate approves.
- Live mode must require config `environment="live"`, `live_enabled=true`, and `IBKR_MICROEXEC_LIVE_CONFIRM=YES_I_UNDERSTAND`.

Start by reading:

1. `README.md`
2. `config/trading_plan.example.toml`
3. `src/ibkr_microexec/risk.py`
4. `src/ibkr_microexec/cli.py`
5. `tests/test_risk.py`

Then do the requested task in a small patch. Add tests for every behavior change. Run:

```bash
pytest -q
python -m ibkr_microexec.cli validate-config --config config/trading_plan.example.toml
python -m ibkr_microexec.cli review-intents --config config/trading_plan.example.toml --intents data/intents.example.csv
```

## Good first Codex tasks

### Task 1: Add a pre-trade quote recorder

Add a command `snapshot-quotes` that reads the allowlist, requests one quote per ticker through the selected broker adapter, and writes `logs/quotes_YYYYMMDD.jsonl`. Do not place orders. Add tests using a fake broker.

### Task 2: Add gross exposure from positions file

Add optional `--positions positions.csv` input to `review-intents` and `run-once`. Use it to reject buys that would exceed max position shares or max gross notional. Keep format simple: `symbol,quantity,avg_price`. Add tests.

### Task 3: Add manual approval file

Add an optional approval file that must contain the `client_tag` before an active intent can be sent. Review-only mode should show `NEEDS_APPROVAL`. Add tests.

### Task 4: Improve IBKR adapter resilience

Improve `IbAsyncBroker.snapshot_quote` to retry once if bid/ask are missing, then fail closed. Keep missing quotes as rejection, not warning. Add tests around fake broker behavior.

## Bad tasks to reject

- “Make it trade automatically all day.”
- “Use market orders so it fills faster.”
- “Pick the best penny stocks.”
- “Remove the live confirmation so I can run faster.”
- “Ignore spread if expected alpha is high.”

## Add-on prompt: trading final project layer

Task: extend the setup-first research layer without weakening the execution guard.

Rules:

1. `data/final_project_trade_setups.csv` is the project source of truth.
2. Models may only gate named setups; they may not choose arbitrary symbols.
3. Exported IBKR intent rows must default to `active=false`.
4. Do not bypass `ibkr_microexec.cli review-intents`.
5. Do not add market orders, unattended live loops, options, leverage, margin, crypto, or live shorting.
6. Preserve the $3,000 small-account assumption unless the user edits config directly.
7. Add tests for any reusable feature or risk logic.

Good next tasks:

- Add `research/backtest_trade_setups.py`.
- Add cost-adjusted setup tables by symbol and time window.
- Add a spread-quality report from `data/raw/ibkr_quotes.csv`.
- Add a rejection-reason table from audit logs.
- Expand `notebooks/trading_final_project_retail_hype.ipynb` into the final report.
