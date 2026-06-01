# Codex instructions for this repo

Opening Trading Boost is an offline Databento L2 opening warmup layer for trading research. It
decides which symbols are worth activating near the open for broader offline strategy analysis.

Hard rules:

1. Do not call Databento unless the user explicitly requests a download.
2. Do not connect to a broker.
3. Do not place live orders.
4. Do not print or store API keys.
5. Do not touch raw DBN files.
6. Keep simulation outputs clearly labeled as offline research.
7. Keep edits scoped and reviewable.

Before editing, inspect:

- `README.md`
- `config/databento_l2.example.toml`
- `src/opening_trading_boost/l2_simulation.py`
- `tests/test_l2_pipeline.py`

Definition of done:

- `.venv/bin/python -m pytest -q` passes.
- `.venv/bin/python research/make_l2_output_plots.py` completes.
- `git diff --check` passes.
- Legacy execution-starter branding is removed.
