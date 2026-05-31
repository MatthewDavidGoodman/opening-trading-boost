from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class L2SetupConfig:
    max_spread_bps: float = 100.0
    min_depth_10: float = 100.0
    min_imbalance_10: float = 0.10


def liquidity_rejection_reason(row: Any, config: L2SetupConfig) -> str:
    reasons = []
    if float(row["spread_bps"]) > config.max_spread_bps:
        reasons.append("spread_too_wide")
    if float(row["bid_depth_10"]) < config.min_depth_10:
        reasons.append("bid_depth_too_thin")
    if float(row["ask_depth_10"]) < config.min_depth_10:
        reasons.append("ask_depth_too_thin")
    return ";".join(reasons)


def detect_l2_setups(features, config: L2SetupConfig | None = None):
    pd = __import__("pandas")
    config = config or L2SetupConfig()
    records: list[dict[str, Any]] = []
    work = features.copy()
    work["datetime"] = pd.to_datetime(work["datetime"], utc=True, errors="coerce")
    work = work.sort_values(["symbol", "datetime"])
    work["prior_mid_return_1m"] = work.groupby("symbol")["mid_return_1m"].shift(1)

    for _, row in work.iterrows():
        base = row.to_dict()
        rejection_reason = liquidity_rejection_reason(row, config)
        if rejection_reason:
            records.append(
                {
                    **base,
                    "setup_id": "L2_LIQUIDITY_REJECT",
                    "setup_name": "L2 liquidity rejection",
                    "decision": "REJECT",
                    "rejection_reason": rejection_reason,
                }
            )
            continue

        long_confirmation = (
            float(row["imbalance_10"]) > config.min_imbalance_10
            and float(row["mid_return_5m"]) > 0
            and float(row["microprice"]) > float(row["midprice"])
        )
        if not long_confirmation:
            continue

        if float(row["mid_return_1m"]) > 0:
            records.append(
                {
                    **base,
                    "setup_id": "L2_MOMENTUM_CONFIRMATION",
                    "setup_name": "L2 momentum confirmation",
                    "decision": "PAPER_LONG",
                    "rejection_reason": "",
                }
            )
        prior_return = row["prior_mid_return_1m"]
        if pd.notna(prior_return) and float(prior_return) <= 0 < float(row["mid_return_1m"]):
            records.append(
                {
                    **base,
                    "setup_id": "L2_RECLAIM_LONG",
                    "setup_name": "L2 reclaim long",
                    "decision": "PAPER_LONG",
                    "rejection_reason": "",
                }
            )
    return pd.DataFrame(
        records,
        columns=[
            *work.columns,
            "setup_id",
            "setup_name",
            "decision",
            "rejection_reason",
        ],
    )
