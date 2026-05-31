# IBKR MicroExec Starter

A guarded Python starter repo for **low-cost, low-volume Interactive Brokers execution**.

This is not a prediction engine and it does not recommend stocks. It is an execution harness:

- You define an allowlist of tickers.
- You define permitted trading windows.
- You submit explicit trade intents.
- The risk gate rejects anything outside the plan.
- Paper / dry-run is the default.
- Live trading requires multiple explicit switches.

Built for a small account workflow, e.g. testing with roughly **$3,000 max gross notional**, tiny orders, specific tickers, and specific times of day.

## Why this shape

For a small account, the dangerous failure modes are not fancy math failures. They are:

1. Accidentally sending live orders.
2. Trading outside the intended window.
3. Market orders in thin names.
4. Spreading a small account across too many positions.
5. Getting chopped up by bid/ask spreads and commissions.
6. Letting a script trade symbols you did not explicitly approve.

So this repo is intentionally boring: limit orders only, allowlist only, explicit time windows only, audit logs always.

## Architecture

```text
trade_intents.csv
       |
       v
config/trading_plan.toml ----> risk gate ----> broker adapter ----> audit log
                                  |                 |
                                  |                 +-- dry-run broker, default
                                  |                 +-- ib_async broker, optional
                                  |
                                  +-- rejects outside ticker/time/budget/spread rules
```

## Quick start

```bash
git clone <your-repo-url> ibkr-microexec-starter
cd ibkr-microexec-starter
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e .[dev]
cp config/trading_plan.example.toml config/trading_plan.toml
cp data/intents.example.csv data/intents.csv
python -m ibkr_microexec.cli validate-config --config config/trading_plan.toml
python -m ibkr_microexec.cli review-intents --config config/trading_plan.toml --intents data/intents.csv
```

For IBKR connectivity:

```bash
pip install -e .[ibkr]
```

Then run TWS or IB Gateway locally, enable API access, log into the **paper** account, and run:

```bash
python -m ibkr_microexec.cli run-once \
  --config config/trading_plan.toml \
  --intents data/intents.csv \
  --broker ibkr \
  --audit logs/audit.jsonl
```

This still does not send orders unless you add `--send`.

## Live trading gate

Live trading requires all of these:

1. `environment = "live"` in config.
2. `live_enabled = true` in config.
3. `IBKR_MICROEXEC_LIVE_CONFIRM=YES_I_UNDERSTAND` in your environment.
4. `--send` on the CLI.
5. No kill-switch file present.

Example:

```bash
export IBKR_MICROEXEC_LIVE_CONFIRM=YES_I_UNDERSTAND
python -m ibkr_microexec.cli run-once --config config/trading_plan.toml --intents data/intents.csv --broker ibkr --send
```

## Workflow

1. Edit `config/trading_plan.toml`.
2. Add only tickers you are willing to trade.
3. Add windows like `09:45-10:15 America/New_York` or `15:30-15:55 America/New_York`.
4. Put explicit orders in `data/intents.csv`.
5. Run `review-intents`.
6. Run in dry-run.
7. Run against paper IBKR.
8. Only then consider live.

## Trade intent CSV

Columns:

```csv
symbol,side,quantity,limit_price,window,active,client_tag,notes
```

Example:

```csv
EXAMPLE,BUY,1,10.01,midday,false,test_001,replace with a real approved ticker
```

`active=false` rows are ignored.

## Guardrails included

- Allowlist required.
- Limit orders only.
- Quantity must be a positive integer.
- Symbol-level max order shares.
- Symbol-level max position shares.
- Symbol-level price band.
- Symbol-level max spread in basis points.
- Minimum bid/ask displayed size check.
- Account-level max gross notional.
- Account-level single-order cap.
- Daily trade count cap.
- Time-window gate.
- Weekday gate.
- Kill-switch file.
- Live-trading environment confirmation.
- JSONL audit log.

## What this repo deliberately does not do

- No stock selection.
- No short selling by default.
- No market orders.
- No options.
- No crypto.
- No leverage.
- No margin logic.
- No PnL promises.
- No unattended always-on daemon.

## IBKR setup note

Interactive Brokers' TWS API connects to Trader Workstation or IB Gateway over a local TCP socket. IBKR recommends testing in paper before live trading. See `docs/ibkr_setup.md`.

## Codex usage

See `docs/codex_prompt.md` and `.codex/instructions.md`. The prompt is written to stop Codex from turning this into an overbuilt autonomous trading system.

## Run tests

```bash
pytest -q
```

## Disclaimer

This is educational software. It is not financial advice, an investment recommendation, or a promise of execution quality. You are responsible for broker permissions, taxes, trading rules, market data subscriptions, order routing, and live-trading consequences.

## Trading final project layer: setup-first retail-hype basket

This repo includes a final-project research layer for a setup-first trading study. Databento historical `mbp-10` L2 order book data is the primary final-project source. IBKR is not required for this research pipeline.

Project title:

**Retail-Hype Intraday Execution Under Capital and Liquidity Constraints**

Key files:

```text
data/final_project_universe.csv
data/final_project_trade_setups.csv
config/final_project_playbook.example.toml
config/meme_stock_trading_plan.example.toml
config/databento_l2.example.toml
research/download_databento_l2.py
research/build_l2_features.py
research/apply_l2_setups.py
research/simulate_l2_trades.py
research/download_prices.py
research/build_features.py
research/apply_trade_setups.py
research/export_trade_intents_from_setups.py
research/train_setup_gate.py
research/stream_ibkr_quotes.py
docs/trading_final_project.md
docs/codex_trading_final_project_prompt.md
notebooks/trading_final_project_retail_hype.ipynb
```

Install research dependencies:

```bash
pip install -e .[research]
pip install databento
```

Review the Databento request without credentials or network access:

```bash
python research/download_databento_l2.py --config config/databento_l2.example.toml --dry-run
```

Run the Databento L2 research path after filling in the config placeholders and setting `DATABENTO_API_KEY`:

```bash
python research/download_databento_l2.py --config config/databento_l2.example.toml
python research/build_l2_features.py --config config/databento_l2.example.toml
python research/apply_l2_setups.py --config config/databento_l2.example.toml
python research/simulate_l2_trades.py --config config/databento_l2.example.toml
.venv/bin/python -m pytest -q
```

The existing `yfinance` OHLCV scripts remain available as a legacy/fallback prototype path. The L2 simulator never connects to IBKR or sends broker orders. Any separately exported execution intent rows still default to `active=false`.
