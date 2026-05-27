# Codex instructions for this repo

You are working on a guarded IBKR execution starter for a small account. Treat safety and fail-closed behavior as product requirements.

Hard rules:

1. Do not add market orders.
2. Do not add options, crypto, margin, or short-selling unless explicitly requested and tests are added.
3. Do not recommend tickers or strategies.
4. Do not hard-code credentials, account numbers, or API keys.
5. Default to dry-run / paper.
6. Live trading must require explicit config, explicit environment variable, and explicit CLI flag.
7. Keep all order decisions auditable in JSONL.
8. Any new execution path needs a unit test for rejection cases.
9. Do not bypass the allowlist, time-window gate, spread gate, or notional limits.
10. Prefer small, reviewable commits.

Before editing, inspect:

- README.md
- config/trading_plan.example.toml
- src/ibkr_microexec/risk.py
- tests/test_risk.py

Definition of done:

- `pytest -q` passes.
- `python -m ibkr_microexec.cli validate-config --config config/trading_plan.example.toml` passes.
- `python -m ibkr_microexec.cli review-intents --config config/trading_plan.example.toml --intents data/intents.example.csv` runs without placing orders.

## Trading final project rules

- Treat `data/final_project_trade_setups.csv` as the source of truth for the research design.
- Keep ML upstream from execution. Models may gate named setups, not invent arbitrary tickers.
- Any exported IBKR intent rows must default to `active=false`.
- Do not add unattended live trading loops.
- Do not add market orders, options, margin, crypto, live shorting, or leverage.
- Treat meme / retail-hype symbols as paper-first research instruments unless the user explicitly edits config and passes the existing live gates.
- Any new model must include a date-based train/test evaluation and a plain-language limitation note.
