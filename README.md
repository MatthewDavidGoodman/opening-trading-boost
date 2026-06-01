# Opening Trading Boost

Opening Trading Boost is an offline Databento L2 opening warmup layer that can improve broader
trading research strategies by deciding which symbols are worth activating near the open.

This is an offline trading final project. It reads existing historical research inputs, derives L2
features, evaluates opening-window setups, simulates conservative paper probes, and creates report
CSVs and plots. It does not connect to a broker, place live orders, or expose API keys.

## Research Flow

```text
historical Databento mbp-10 inputs
        |
        v
L2 feature panel -> opening setup detection -> offline simulation -> reports and plots
```

The opening warmup layer uses spread, depth, imbalance, microprice, and tape activity to classify
symbols as `tradable_today`, `watch_only`, or `pass_today`. The classifications are research
signals for broader strategy activation, not live-order instructions.

## Key Files

```text
config/databento_l2.example.toml
research/download_databento_l2.py
research/build_l2_features.py
research/apply_l2_setups.py
research/simulate_l2_trades.py
research/make_l2_output_plots.py
docs/trading_final_project.md
docs/l2_results_memo.md
notebooks/l2_final_project_outputs.ipynb
```

## Install

```bash
git clone <your-repo-url> opening-trading-boost
cd opening-trading-boost
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e .[dev,research]
```

## Offline Workflow

Review the configured Databento request without credentials or network access:

```bash
.venv/bin/python research/download_databento_l2.py \
  --config config/databento_l2.example.toml \
  --dry-run
```

Build reports from existing local inputs:

```bash
.venv/bin/python research/build_l2_features.py --config config/databento_l2.example.toml
.venv/bin/python research/apply_l2_setups.py --config config/databento_l2.example.toml
.venv/bin/python research/simulate_l2_trades.py --config config/databento_l2.example.toml
.venv/bin/python research/make_l2_output_plots.py
```

The download script exists for an explicitly initiated historical-data workflow. Do not run it as
part of ordinary offline analysis. Raw DBN files remain outside the tracked research artifacts.

## Outputs

The primary outputs are written under `data/reports/` and `data/plots/`. The final memo explains the
ranked opening ladder, the reproduced high-PnL comparison, and the longer-window benchmarks.

## Tests

```bash
.venv/bin/python -m pytest -q
```

## Scope

- Offline-only execution.
- No broker connection.
- No live orders.
- No API keys in logs, reports, or configuration examples.
- No financial advice or production trading claims.
