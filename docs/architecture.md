# Architecture

## Components

### Config loader

`config.py` loads TOML into typed dataclasses. It fails early if windows or tickers are malformed.

### Intent loader

`intents.py` loads CSV rows into `TradeIntent` objects. Only `active=true` rows are eligible.

### Risk gate

`risk.py` is the center of the repo. It returns a `RiskDecision`, not a boolean, so every rejection carries reasons.

### Broker adapter

`broker.py` defines a small interface:

- `connect()`
- `snapshot_quote(symbol)`
- `place_limit_order(order)`
- `disconnect()`

The default dry-run broker never touches IBKR.

### CLI

`cli.py` exposes:

- `validate-config`
- `review-intents`
- `run-once`
- `kill`
- `unkill`

## Fail-closed philosophy

If anything important is missing, reject:

- Missing quote.
- Missing bid/ask.
- Unknown ticker.
- Unknown time window.
- Missing live confirmation.
- Kill-switch file exists.
- Non-limit order.

## Suggested next modules

- `positions.py`: load broker positions or CSV positions.
- `quotes.py`: quote history recorder.
- `approvals.py`: manual approval file by `client_tag`.
- `commissions.py`: estimate fee drag for tiny orders.
- `calendar.py`: market holidays and half-days.
