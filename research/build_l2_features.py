#!/usr/bin/env python3
from __future__ import annotations

import argparse
import tomllib
from pathlib import Path

from ibkr_microexec.l2_features import build_l2_feature_panel


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build 1-minute L2 features from Databento MBP-10."
    )
    parser.add_argument("--config", default="config/databento_l2.example.toml")
    parser.add_argument("--raw-dir")
    parser.add_argument("--processed-dir")
    parser.add_argument("--out")
    args = parser.parse_args()

    config = tomllib.loads(Path(args.config).read_text(encoding="utf-8"))["databento"]
    panel = build_l2_feature_panel(
        raw_dir=args.raw_dir or config["raw_dir"],
        processed_dir=args.processed_dir or config["processed_dir"],
        out_path=args.out or config["feature_path"],
        interval=config["resample_interval"],
    )
    print(
        f"wrote {args.out or config['feature_path']} "
        f"rows={len(panel)} symbols={panel['symbol'].nunique()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
