#!/usr/bin/env python3
from __future__ import annotations

import argparse
import tomllib
from pathlib import Path

from opening_trading_boost.features import FeatureConfig, build_feature_panel


def main() -> int:
    parser = argparse.ArgumentParser(description="Build research features from downloaded OHLCV files.")
    parser.add_argument("--policy", default="config/model_policy.example.toml")
    parser.add_argument("--price-dir", default=None)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    policy = tomllib.loads(Path(args.policy).read_text(encoding="utf-8"))
    price_dir = args.price_dir or policy["features"]["price_dir"]
    out_path = Path(args.out or policy["features"]["feature_path"])
    label_cfg = policy.get("labels", {})
    cfg = FeatureConfig(
        forward_bars=int(label_cfg.get("forward_bars", 3)),
        min_forward_return_bps=float(label_cfg.get("min_forward_return_bps", 25.0)),
        cost_buffer_bps=float(label_cfg.get("cost_buffer_bps", 20.0)),
    )

    panel = build_feature_panel(price_dir, cfg=cfg)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    panel.to_csv(out_path, index=False)
    print(f"wrote {out_path} rows={len(panel)} symbols={panel['symbol'].nunique()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
