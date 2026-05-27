#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import asdict
from decimal import Decimal, ROUND_DOWN
from pathlib import Path

from ibkr_microexec.setups import TradeSetup, load_trade_setups


def require_pandas():
    try:
        import pandas as pd  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise SystemExit("Install research deps with: pip install -e .[research]") from exc
    return pd


def parse_window_minutes(window: str) -> tuple[int, int] | None:
    text = str(window).strip().upper()
    if text in {"", "NONE"}:
        return None
    start, end = text.split("-")
    sh, sm = [int(x) for x in start.split(":")]
    eh, em = [int(x) for x in end.split(":")]
    return sh * 60 + sm, eh * 60 + em


def in_window(series, window: str):
    bounds = parse_window_minutes(window)
    if bounds is None:
        return series == -1
    start, end = bounds
    return (series >= start) & (series <= end)


def safe_float(value, default: float = 0.0) -> float:
    try:
        if value != value:  # NaN check
            return default
        return float(value)
    except Exception:
        return default


def score_row(row, setup: TradeSetup) -> float:
    rel_volume = safe_float(row.get("rel_volume_20"), 0.0)
    ret_3 = safe_float(row.get("ret_3"), 0.0)
    ret_12 = safe_float(row.get("ret_12"), 0.0)
    range_bps = safe_float(row.get("range_bps"), 0.0)
    ma_bps = safe_float(row.get("close_vs_sma20_bps"), 0.0)

    if setup.family == "open_reclaim_long":
        return 0.45 * min(rel_volume / 3.0, 1.5) + 0.35 * max(ma_bps, 0) / 250 + 0.20 * max(ret_3, 0) * 100
    if setup.family == "momentum_continuation_long":
        return 0.45 * min(rel_volume / 3.0, 1.5) + 0.35 * max(ret_12, 0) * 100 + 0.20 * max(ma_bps, 0) / 250
    if setup.family == "flush_reclaim_long":
        return 0.40 * min(rel_volume / 3.0, 1.5) + 0.35 * max(ret_3, 0) * 100 + 0.25 * max(-ret_12, 0) * 100
    if setup.family == "gap_fade_research":
        return 0.40 * min(rel_volume / 3.0, 1.5) + 0.30 * max(ret_12, 0) * 100 + 0.30 * max(range_bps, 0) / 500
    if setup.family == "liquidity_rejector":
        return 0.5 * min(rel_volume / 3.0, 1.5) + 0.5 * max(range_bps, 0) / 500
    return 0.0


def setup_mask(df, setup: TradeSetup):
    rel_volume = df["rel_volume_20"].astype(float)
    ret_3 = df["ret_3"].astype(float)
    ret_12 = df["ret_12"].astype(float)
    close_vs_ma = df["close_vs_sma20_bps"].astype(float)
    minute = df["minute_of_day_et"].astype(int)

    base = (df["symbol"].astype(str).str.upper() == setup.symbol) & in_window(minute, setup.entry_window_et)
    base = base & (rel_volume >= float(setup.min_rel_volume))

    if setup.family == "open_reclaim_long":
        return base & (ret_12 < 0.01) & (ret_3 > 0.0015) & (close_vs_ma > 0)
    if setup.family == "momentum_continuation_long":
        return base & (ret_12 > 0.006) & (ret_3 > 0.001) & (close_vs_ma > 25)
    if setup.family == "flush_reclaim_long":
        return base & (ret_12 < -0.006) & (ret_3 > 0.001) & (close_vs_ma > -150)
    if setup.family == "gap_fade_research":
        return base & (ret_12 > 0.012) & (ret_3 < 0.003)
    if setup.family == "liquidity_rejector":
        return base
    return base & False


def infer_quantity(price: float, max_notional: Decimal) -> int:
    if price <= 0 or max_notional <= 0:
        return 0
    return int((max_notional / Decimal(str(price))).to_integral_value(rounding=ROUND_DOWN))


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply named final-project trade setups to feature data.")
    parser.add_argument("--features", default="data/features/features.csv")
    parser.add_argument("--setups", default="data/final_project_trade_setups.csv")
    parser.add_argument("--out", default="data/reports/setup_occurrences.csv")
    parser.add_argument("--top-per-setup", type=int, default=5)
    args = parser.parse_args()

    pd = require_pandas()
    features = pd.read_csv(args.features)
    features["datetime"] = pd.to_datetime(features["datetime"], utc=True, errors="coerce")
    setups = load_trade_setups(args.setups)

    records: list[dict] = []
    for setup in setups:
        subset = features.loc[setup_mask(features, setup)].copy()
        if subset.empty:
            continue
        subset["setup_score"] = subset.apply(lambda row: score_row(row, setup), axis=1)
        subset = subset.sort_values("setup_score", ascending=False).head(args.top_per_setup)
        for _, row in subset.iterrows():
            last_price = safe_float(row.get("last_price", row.get("close")), 0.0)
            record = {
                "setup_id": setup.setup_id,
                "symbol": setup.symbol,
                "family": setup.family,
                "setup_name": setup.setup_name,
                "research_side": setup.research_side,
                "live_side_allowed": setup.live_side_allowed,
                "datetime": row["datetime"],
                "entry_window_et": setup.entry_window_et,
                "exit_window_et": setup.exit_window_et,
                "last_price": round(last_price, 4),
                "setup_score": round(float(row["setup_score"]), 6),
                "quantity_paper": infer_quantity(last_price, setup.max_notional_paper),
                "quantity_live_cap": infer_quantity(last_price, setup.max_notional_live),
                "thesis": setup.thesis,
                "entry_rule_plain": setup.entry_rule_plain,
                "exit_rule_plain": setup.exit_rule_plain,
                "ml_question": setup.ml_question,
            }
            for col in [
                "ret_1",
                "ret_3",
                "ret_12",
                "range_bps",
                "rel_volume_20",
                "realized_vol_20",
                "close_vs_sma20_bps",
                "forward_return",
                "label_forward_up",
            ]:
                if col in row:
                    record[col] = row[col]
            records.append(record)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out = pd.DataFrame(records)
    if out.empty:
        out = pd.DataFrame(columns=["setup_id", "symbol", "datetime", "setup_score"])
    else:
        out = out.sort_values(["datetime", "setup_score"], ascending=[False, False])
    out.to_csv(out_path, index=False)
    print(f"wrote {out_path} rows={len(out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
