#!/usr/bin/env python3
from __future__ import annotations

import argparse
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path


def require_pandas():
    try:
        import pandas as pd  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise SystemExit("Install research deps with: pip install -e .[research]") from exc
    return pd


def round_price(value: float) -> str:
    return str(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Turn setup occurrences into inactive IBKR intent rows for manual review."
    )
    parser.add_argument("--setup-occurrences", default="data/reports/setup_occurrences.csv")
    parser.add_argument("--out", default="data/intents.generated.csv")
    parser.add_argument("--mode", choices=["paper", "live"], default="paper")
    parser.add_argument("--max-rows", type=int, default=6)
    args = parser.parse_args()

    pd = require_pandas()
    df = pd.read_csv(args.setup_occurrences)
    if df.empty:
        raise SystemExit("No setup rows found. Run research/apply_trade_setups.py first.")

    if args.mode == "live":
        df = df[(df["live_side_allowed"] == "BUY") & (df["quantity_live_cap"].astype(int) > 0)]
        quantity_col = "quantity_live_cap"
    else:
        df = df[(df["research_side"].isin(["BUY"])) & (df["quantity_paper"].astype(int) > 0)]
        quantity_col = "quantity_paper"

    df = df.sort_values("setup_score", ascending=False).drop_duplicates("symbol").head(args.max_rows)
    rows = []
    for _, row in df.iterrows():
        rows.append(
            {
                "symbol": str(row["symbol"]).upper(),
                "side": "BUY",
                "quantity": int(row[quantity_col]),
                "limit_price": round_price(float(row["last_price"])),
                "window": str(row["entry_window_et"]),
                "active": "false",
                "client_tag": str(row["setup_id"]),
                "notes": f"final_project_setup={row['setup_name']}; score={row['setup_score']}",
            }
        )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(out_path, index=False)
    print(f"wrote {out_path} rows={len(rows)} active=false; review before enabling")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
