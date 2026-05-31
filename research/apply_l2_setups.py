#!/usr/bin/env python3
from __future__ import annotations

import argparse
import tomllib
from pathlib import Path

import pandas as pd

from ibkr_microexec.l2_setups import L2SetupConfig, detect_l2_setups


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Apply setup-first rules to Databento L2 features."
    )
    parser.add_argument("--config", default="config/databento_l2.example.toml")
    parser.add_argument("--features", default="data/features/l2_features.csv")
    parser.add_argument("--out", default="data/reports/l2_setup_occurrences.csv")
    args = parser.parse_args()

    raw = tomllib.loads(Path(args.config).read_text(encoding="utf-8"))
    setup = raw.get("l2_setups", {})
    config = L2SetupConfig(
        max_spread_bps=float(setup.get("max_spread_bps", 100.0)),
        min_depth_10=float(setup.get("min_depth_10", 100)),
        min_imbalance_10=float(setup.get("min_imbalance_10", 0.10)),
    )
    occurrences = detect_l2_setups(pd.read_csv(args.features), config)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    occurrences.to_csv(out_path, index=False)
    print(f"wrote {out_path} rows={len(occurrences)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
