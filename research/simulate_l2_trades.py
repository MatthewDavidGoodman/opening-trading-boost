#!/usr/bin/env python3
from __future__ import annotations

import argparse
import tomllib
from pathlib import Path

import pandas as pd

from ibkr_microexec.l2_simulation import simulate_l2_trades, summarize_l2_trades


def main() -> int:
    parser = argparse.ArgumentParser(description="Simulate conservative paper-only L2 fills.")
    parser.add_argument("--config", default="config/databento_l2.example.toml")
    parser.add_argument("--features", default="data/features/l2_features.csv")
    parser.add_argument("--setups", default="data/reports/l2_setup_occurrences.csv")
    parser.add_argument("--blotter-out")
    parser.add_argument("--summary-out")
    args = parser.parse_args()

    config = tomllib.loads(Path(args.config).read_text(encoding="utf-8"))["simulation"]
    blotter = simulate_l2_trades(
        features=pd.read_csv(args.features),
        occurrences=pd.read_csv(args.setups),
        holding_period_bars=int(config["holding_period_bars"]),
        estimated_cost_bps=float(config["estimated_cost_bps"]),
    )
    summary = summarize_l2_trades(blotter)
    blotter_path = Path(args.blotter_out or config["blotter_path"])
    summary_path = Path(args.summary_out or config["summary_path"])
    blotter_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    blotter.to_csv(blotter_path, index=False)
    summary.to_csv(summary_path, index=False)
    print(f"wrote {blotter_path} rows={len(blotter)}")
    print(f"wrote {summary_path} rows={len(summary)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
