# IBKR setup notes

This repo uses the Trader Workstation / IB Gateway path rather than Client Portal Web API.

## Recommended path

1. Install Trader Workstation or IB Gateway.
2. Log into the paper account first.
3. Enable socket API access in settings.
4. Confirm the API port in TWS / Gateway.
5. Keep `environment = "paper"` in `config/trading_plan.toml`.
6. Run `review-intents` before `run-once`.
7. Run `run-once` without `--send` first.
8. Only use `--send` against paper after the review output looks right.

## Common local ports

Common defaults are often:

- Paper TWS: `7497`
- Live TWS: `7496`

Confirm these in your own TWS / Gateway configuration rather than assuming.

## API settings checklist

In TWS / Gateway, check:

- Socket clients enabled.
- Trusted IPs include `127.0.0.1` if required.
- Read-only API is disabled only when you intend to place paper orders.
- Paper account is selected.
- Market data permissions are adequate for the symbols you are quoting.

## Paper first

This repo is built so paper trading is the natural first path. Do not move to live until you have:

- Verified contract qualification.
- Verified quotes.
- Verified limit price behavior.
- Verified rejected orders stay rejected.
- Verified order status callbacks in TWS / Gateway.
- Verified audit log entries.
- Verified cancel behavior manually inside TWS.

## Thin-stock warning

Small / thin stocks can have wide spreads, stale quotes, gaps, halts, and poor displayed depth. That is why this repo uses limit orders only and rejects orders when spread or quote-size rules fail.
