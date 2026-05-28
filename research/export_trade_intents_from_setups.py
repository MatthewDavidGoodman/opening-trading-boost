#!/usr/bin/env python3
from __future__ import annotations

import argparse
from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP
from pathlib import Path

from ibkr_microexec.config import TradingPlan, load_plan


def require_pandas():
    try:
        import pandas as pd  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise SystemExit("Install research deps with: pip install -e .[research]") from exc
    return pd


def round_price(value: float) -> str:
    return str(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _floor_shares_for_notional(notional: Decimal, price: Decimal) -> int:
    if notional <= 0 or price <= 0:
        return 0
    return int((notional / price).to_integral_value(rounding=ROUND_FLOOR))


def _capped_quantity(
    requested_quantity: int,
    price: Decimal,
    symbol: str,
    plan: TradingPlan,
    remaining_gross_notional: Decimal,
) -> tuple[int, list[str]]:
    reasons: list[str] = []
    rule = plan.tickers.get(symbol)
    if rule is None:
        return 0, ["symbol_not_allowlisted"]

    if price < rule.min_price or price > rule.max_price:
        return 0, ["limit_price_outside_symbol_price_band"]

    caps = [
        requested_quantity,
        rule.max_order_shares,
        rule.max_position_shares,
        _floor_shares_for_notional(rule.max_order_notional, price),
        _floor_shares_for_notional(plan.budget.max_single_order_notional, price),
        _floor_shares_for_notional(remaining_gross_notional, price),
    ]
    quantity = max(0, min(caps))

    if quantity < requested_quantity:
        if requested_quantity > rule.max_order_shares:
            reasons.append("capped_symbol_max_order_shares")
        if requested_quantity > rule.max_position_shares:
            reasons.append("capped_symbol_max_position_shares")
        if Decimal(requested_quantity) * price > rule.max_order_notional:
            reasons.append("capped_symbol_max_order_notional")
        if Decimal(requested_quantity) * price > plan.budget.max_single_order_notional:
            reasons.append("capped_account_max_single_order_notional")
        if Decimal(requested_quantity) * price > remaining_gross_notional:
            reasons.append("capped_account_max_gross_notional")

    if quantity == 0 and not reasons:
        reasons.append("capped_quantity_zero")

    return quantity, reasons


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Turn setup occurrences into inactive IBKR intent rows for manual review."
    )
    parser.add_argument("--setup-occurrences", default="data/reports/setup_occurrences.csv")
    parser.add_argument("--out", default="data/intents.generated.csv")
    parser.add_argument("--config", default="config/meme_stock_trading_plan.example.toml")
    parser.add_argument("--rejections-out", default="data/reports/export_rejections.csv")
    parser.add_argument("--mode", choices=["paper", "live"], default="paper")
    parser.add_argument("--max-rows", type=int, default=6)
    args = parser.parse_args()

    pd = require_pandas()
    plan = load_plan(args.config)
    df = pd.read_csv(args.setup_occurrences)
    if df.empty:
        raise SystemExit("No setup rows found. Run research/apply_trade_setups.py first.")

    if args.mode == "live":
        df = df[
            (df["live_side_allowed"] == "BUY")
            & (df["research_side"] != "NONE")
            & (df["quantity_live_cap"].astype(int) > 0)
        ]
        quantity_col = "quantity_live_cap"
    else:
        df = df[
            (df["live_side_allowed"] == "BUY")
            & (df["research_side"] != "NONE")
            & (df["quantity_paper"].astype(int) > 0)
        ]
        quantity_col = "quantity_paper"

    df = df.sort_values("setup_score", ascending=False).drop_duplicates("symbol").head(args.max_rows)
    rows = []
    rejections = []
    remaining_gross_notional = plan.budget.max_gross_notional
    for _, row in df.iterrows():
        symbol = str(row["symbol"]).upper()
        limit_price = Decimal(round_price(float(row["last_price"])))
        requested_quantity = int(row[quantity_col])
        quantity, cap_reasons = _capped_quantity(
            requested_quantity=requested_quantity,
            price=limit_price,
            symbol=symbol,
            plan=plan,
            remaining_gross_notional=remaining_gross_notional,
        )
        if quantity <= 0:
            rejections.append(
                {
                    "symbol": symbol,
                    "setup_id": str(row["setup_id"]),
                    "requested_quantity": requested_quantity,
                    "limit_price": str(limit_price),
                    "reason": ";".join(cap_reasons),
                }
            )
            continue

        remaining_gross_notional -= limit_price * Decimal(quantity)
        rows.append(
            {
                "symbol": symbol,
                "side": "BUY",
                "quantity": quantity,
                "limit_price": str(limit_price),
                "window": str(row["entry_window_et"]),
                "active": "false",
                "client_tag": str(row["setup_id"]),
                "notes": f"final_project_setup={row['setup_name']}; score={row['setup_score']}",
            }
        )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        rows,
        columns=[
            "symbol",
            "side",
            "quantity",
            "limit_price",
            "window",
            "active",
            "client_tag",
            "notes",
        ],
    ).to_csv(out_path, index=False)
    rejections_path = Path(args.rejections_out)
    rejections_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        rejections,
        columns=["symbol", "setup_id", "requested_quantity", "limit_price", "reason"],
    ).to_csv(rejections_path, index=False)
    print(f"wrote {out_path} rows={len(rows)} active=false; review before enabling")
    print(f"wrote {rejections_path} rows={len(rejections)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
