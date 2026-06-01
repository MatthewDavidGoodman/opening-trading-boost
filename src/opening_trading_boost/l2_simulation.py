from __future__ import annotations

from dataclasses import dataclass, replace
from math import floor
from typing import Any

SETUP_PRIORITY = (
    "L2_RECLAIM_LONG",
    "L2_MOMENTUM_CONFIRMATION",
    "L2_LIQUIDITY_REJECT",
)
OPENING_LADDER_FAMILY_PRIORITY = (
    "OPENING_LADDER_PULLBACK_RECLAIM_LONG",
    "OPENING_LADDER_IMBALANCE_LONG",
    "OPENING_LADDER_SPREAD_COMPRESSION_LONG",
)
PRETRADE_FEATURES = (
    "spread_bps",
    "imbalance_10",
    "imbalance_1",
    "microprice",
    "midprice",
    "bid_depth_10",
    "ask_depth_10",
    "trade_count",
    "trade_volume",
    "mid_return_1m",
    "mid_return_5m",
)


@dataclass(frozen=True)
class OpeningLadderConfig:
    warmup_start_et: str = "09:35"
    warmup_end_et: str = "10:00"
    extended_opening_benchmark_start_et: str = "09:30"
    extended_opening_benchmark_end_et: str = "10:30"
    max_ladder_probes_per_symbol: int = 2
    ladder_probe_notional: float = 50.0
    max_ladder_single_probe_notional: float = 150.0
    max_ladder_total_notional_per_symbol: float = 300.0
    allow_one_share_high_price_probe: bool = True
    ladder_cooldown_minutes: float = 7.0
    max_active_symbols_per_open: int = 2
    minimum_opening_score: float = 0.0
    use_ranked_symbol_selection: bool = True
    holding_period_bars: int = 5
    estimated_cost_bps: float = 5.0
    max_spread_bps: float = 100.0
    min_depth_10: float = 100.0
    min_imbalance_10: float = 0.10
    min_total_depth_10: float = 500.0
    min_trade_count: int = 10
    min_trade_volume: float = 1000.0
    microprice_tolerance_bps: float = 2.0
    spread_compression_lookback: int = 5
    allow_spread_compression_setup: bool = True
    allow_pullback_reclaim_setup: bool = True
    allow_imbalance_setup: bool = True


def _is_inside_opening_window(entry_datetime, start_et: str, end_et: str) -> bool:
    pd = __import__("pandas")
    local_time = pd.to_datetime(entry_datetime, utc=True).tz_convert("America/New_York").time()
    return pd.to_datetime(start_et).time() <= local_time < pd.to_datetime(end_et).time()


def classify_opening_phase(entry_datetime) -> str:
    pd = __import__("pandas")
    local_time = pd.to_datetime(entry_datetime, utc=True).tz_convert("America/New_York").time()
    boundaries = (
        ("09:30", "09:35", "observe_open"),
        ("09:35", "09:50", "first_teaser_window"),
        ("09:50", "10:15", "confirmation_window"),
        ("10:15", "10:30", "final_warmup_window"),
    )
    for start, end, phase in boundaries:
        if pd.to_datetime(start).time() <= local_time < pd.to_datetime(end).time():
            return phase
    return "outside_opening_warmup"


def pretrade_assessment(
    row: Any,
    max_spread_bps: float = 100.0,
    min_depth_10: float = 100.0,
    min_imbalance_10: float = 0.10,
) -> str:
    """Classify tradability using entry-time book and tape fields only."""
    if (
        float(row["spread_bps"]) > max_spread_bps
        or float(row["bid_depth_10"]) < min_depth_10
        or float(row["ask_depth_10"]) < min_depth_10
    ):
        return "pass_today"
    if (
        float(row["imbalance_10"]) >= min_imbalance_10
        and float(row["imbalance_1"]) > 0
        and float(row["microprice"]) > float(row["midprice"])
        and float(row["trade_count"]) > 0
        and float(row["trade_volume"]) > 0
        and float(row["mid_return_1m"]) > 0
        and float(row["mid_return_5m"]) > 0
    ):
        return "tradable_today"
    return "watch_only"


def realized_outcome(net_return_bps: float) -> str:
    if net_return_bps > 0:
        return "win"
    if net_return_bps < 0:
        return "loss"
    return "flat"


def calculate_opening_score(row: Any, setup_family: str, config: OpeningLadderConfig) -> float:
    spread_quality = max(0.0, 1.0 - float(row["spread_bps"]) / config.max_spread_bps) * 2.0
    total_depth = float(row["bid_depth_10"]) + float(row["ask_depth_10"])
    depth_quality = min(total_depth / config.min_total_depth_10, 3.0)
    microprice_support = 1.0 if float(row["microprice"]) > float(row["midprice"]) else 0.0
    recent_return_quality = float(float(row["mid_return_1m"]) >= 0) + float(
        float(row["mid_return_5m"]) >= 0
    )
    family_quality = {
        "OPENING_LADDER_SPREAD_COMPRESSION_LONG": 3.0,
        "OPENING_LADDER_PULLBACK_RECLAIM_LONG": 2.0,
        "OPENING_LADDER_IMBALANCE_LONG": 1.0 + recent_return_quality,
    }[setup_family]
    return spread_quality + depth_quality + microprice_support + recent_return_quality + family_quality


def evaluate_opening_ladder_probe(
    row: Any,
    config: OpeningLadderConfig,
    prior_probe_count: int = 0,
    prior_total_notional: float = 0.0,
    next_probe_allowed_at=None,
    prior_row: Any | None = None,
    rolling_median_spread_bps: float | None = None,
) -> dict[str, Any]:
    pd = __import__("pandas")
    entry_datetime = pd.to_datetime(row["datetime"], utc=True)
    entry_price = float(row["best_ask"])
    if entry_price <= config.ladder_probe_notional:
        quantity = floor(config.ladder_probe_notional / entry_price)
        sizing_mode = "target_notional_floor"
    elif (
        config.allow_one_share_high_price_probe
        and entry_price <= config.max_ladder_single_probe_notional
    ):
        quantity = 1
        sizing_mode = "one_share_high_price_probe"
    else:
        quantity = 0
        sizing_mode = "rejected_price_above_cap"
    simulated_notional = quantity * entry_price
    gate_failures = []
    if not _is_inside_opening_window(
        entry_datetime, config.warmup_start_et, config.warmup_end_et
    ):
        gate_failures.append("outside_opening_warmup")
    if next_probe_allowed_at is not None and entry_datetime < pd.to_datetime(
        next_probe_allowed_at, utc=True
    ):
        gate_failures.append("cooldown_active")
    if prior_probe_count >= config.max_ladder_probes_per_symbol:
        gate_failures.append("max_ladder_probes_reached")
    if quantity == 0:
        gate_failures.append("price_above_max_single_probe_notional")
    if (
        quantity > 0
        and prior_total_notional + simulated_notional
        > config.max_ladder_total_notional_per_symbol
    ):
        gate_failures.append("total_ladder_notional_cap_reached")

    spread_ok = float(row["spread_bps"]) <= config.max_spread_bps
    bid_depth_ok = float(row["bid_depth_10"]) >= config.min_depth_10
    microprice_above_mid = float(row["microprice"]) > float(row["midprice"])
    trade_count_positive = float(row["trade_count"]) > 0
    recent_return_non_negative = float(row["mid_return_1m"]) >= 0 or float(
        row["mid_return_5m"]
    ) >= 0
    prior_return_negative = prior_row is not None and (
        float(prior_row["mid_return_1m"]) < 0 or float(prior_row["mid_return_5m"]) < 0
    )
    imbalance_improving = prior_row is not None and float(row["imbalance_10"]) > float(
        prior_row["imbalance_10"]
    )
    family_results = {
        "OPENING_LADDER_PULLBACK_RECLAIM_LONG": {
            "enabled": config.allow_pullback_reclaim_setup,
            "conditions": {
                "spread_within_limit": spread_ok,
                "bid_depth_sufficient": bid_depth_ok,
                "prior_pullback_present": prior_return_negative,
                "current_return_reclaimed": float(row["mid_return_1m"]) >= 0,
                "microprice_confirming": float(row["microprice"]) >= float(row["midprice"]),
                "trade_count_positive": trade_count_positive,
                "imbalance_confirming": imbalance_improving or float(row["imbalance_10"]) >= 0,
            },
        },
        "OPENING_LADDER_IMBALANCE_LONG": {
            "enabled": config.allow_imbalance_setup,
            "conditions": {
                "spread_within_limit": spread_ok,
                "bid_depth_sufficient": bid_depth_ok,
                "imbalance_confirming": float(row["imbalance_10"]) >= config.min_imbalance_10,
                "microprice_confirming": microprice_above_mid,
                "trade_count_positive": trade_count_positive,
                "recent_return_non_negative": recent_return_non_negative,
            },
        },
        "OPENING_LADDER_SPREAD_COMPRESSION_LONG": {
            "enabled": config.allow_spread_compression_setup,
            "conditions": {
                "spread_within_limit": spread_ok,
                "spread_compressed": rolling_median_spread_bps is None
                or float(row["spread_bps"]) <= rolling_median_spread_bps,
                "total_depth_sufficient": float(row["bid_depth_10"])
                + float(row["ask_depth_10"])
                >= config.min_total_depth_10,
                "trade_count_sufficient": float(row["trade_count"]) >= config.min_trade_count,
                "trade_volume_sufficient": float(row["trade_volume"]) >= config.min_trade_volume,
                "current_return_non_negative": float(row["mid_return_1m"]) >= 0,
                "microprice_within_tolerance": float(row["microprice"])
                >= float(row["midprice"]) * (1 - config.microprice_tolerance_bps / 10000),
            },
        },
    }
    selected_family = ""
    selected_conditions: list[str] = []
    for family in OPENING_LADDER_FAMILY_PRIORITY:
        result = family_results[family]
        if result["enabled"] and all(result["conditions"].values()):
            selected_family = family
            selected_conditions = list(result["conditions"])
            break

    family_failure_map = {
        "spread_within_limit": "spread_too_wide",
        "bid_depth_sufficient": "depth_too_thin",
        "imbalance_confirming": "imbalance_not_confirming",
        "microprice_confirming": "microprice_not_confirming",
        "trade_count_positive": "insufficient_trade_count",
        "recent_return_non_negative": "recent_mid_returns_negative",
        "prior_pullback_present": "no_reclaim_structure",
        "current_return_reclaimed": "no_reclaim_structure",
        "spread_compressed": "spread_not_compressed",
        "total_depth_sufficient": "total_depth_too_thin",
        "trade_count_sufficient": "insufficient_trade_count",
        "trade_volume_sufficient": "insufficient_trade_volume",
        "current_return_non_negative": "no_reclaim_structure",
        "microprice_within_tolerance": "microprice_not_confirming",
    }
    family_failures = []
    if not selected_family:
        for result in family_results.values():
            if not result["enabled"]:
                continue
            for condition, passed in result["conditions"].items():
                if not passed:
                    family_failures.append(family_failure_map[condition])
    failed_conditions = list(dict.fromkeys([*gate_failures, *family_failures]))
    reasons = list(failed_conditions)
    legacy_aliases = {
        "cooldown_active": "ladder_cooldown_not_passed",
        "total_ladder_notional_cap_reached": "max_ladder_total_notional_reached",
        "imbalance_not_confirming": "book_pressure_against_trade",
    }
    reasons.extend(legacy_aliases[reason] for reason in failed_conditions if reason in legacy_aliases)
    probe_allowed = bool(selected_family) and not gate_failures
    qualifying_families = [
        family
        for family, result in family_results.items()
        if result["enabled"] and all(result["conditions"].values())
    ]
    opening_score_family = (
        max(qualifying_families, key=lambda family: calculate_opening_score(row, family, config))
        if qualifying_families
        else ""
    )
    opening_score = (
        calculate_opening_score(row, opening_score_family, config)
        if opening_score_family
        else float("nan")
    )
    return {
        "probe_allowed": probe_allowed,
        "probe_rejection_reason": ";".join(dict.fromkeys(reasons)),
        "ladder_setup_family": selected_family,
        "setup_family_reason": (
            f"qualified:{selected_family}" if selected_family else "no_setup_family_qualified"
        ),
        "qualifying_conditions": ";".join(selected_conditions),
        "failed_conditions": ";".join(failed_conditions),
        "sizing_mode": sizing_mode,
        "opening_score": opening_score,
        "opening_score_family": opening_score_family,
        "paper_quantity": quantity if probe_allowed else 0,
        "simulated_notional": simulated_notional if probe_allowed else 0.0,
    }


def simulate_long_fill(
    entry_ask: float, exit_bid: float, estimated_cost_bps: float
) -> dict[str, float]:
    if entry_ask <= 0 or exit_bid <= 0:
        raise ValueError("Simulated prices must be positive")
    gross_return_bps = (exit_bid / entry_ask - 1.0) * 10000.0
    return {
        "entry_price": entry_ask,
        "exit_price": exit_bid,
        "gross_return_bps": gross_return_bps,
        "estimated_cost_bps": estimated_cost_bps,
        "net_return_bps": gross_return_bps - estimated_cost_bps,
    }


def deduplicate_l2_occurrences(occurrences):
    pd = __import__("pandas")
    paper_longs = occurrences.loc[occurrences["decision"] == "PAPER_LONG"].copy()
    paper_longs["datetime"] = pd.to_datetime(paper_longs["datetime"], utc=True, errors="coerce")
    priority = {setup_id: index for index, setup_id in enumerate(SETUP_PRIORITY)}
    paper_longs["_priority"] = paper_longs["setup_id"].map(priority).fillna(len(priority))
    paper_longs = paper_longs.sort_values(["symbol", "datetime", "_priority", "setup_id"])

    records: list[dict[str, Any]] = []
    for (_, _), group in paper_longs.groupby(["symbol", "datetime"], sort=False):
        primary = group.iloc[0].drop(labels="_priority").to_dict()
        primary["overlapping_setup_count"] = len(group)
        primary["overlapping_setup_ids"] = ";".join(dict.fromkeys(group["setup_id"].astype(str)))
        records.append(primary)
    return pd.DataFrame(
        records,
        columns=[
            *[column for column in paper_longs.columns if column != "_priority"],
            "overlapping_setup_count",
            "overlapping_setup_ids",
        ],
    )


def simulate_l2_trades(features, occurrences, holding_period_bars: int, estimated_cost_bps: float):
    pd = __import__("pandas")
    feature_frame = features.copy()
    feature_frame["datetime"] = pd.to_datetime(feature_frame["datetime"], utc=True, errors="coerce")
    feature_frame = feature_frame.sort_values(["symbol", "datetime"])
    by_symbol = {
        symbol: frame.reset_index(drop=True)
        for symbol, frame in feature_frame.groupby(feature_frame["symbol"].astype(str))
    }

    records: list[dict[str, Any]] = []
    paper_longs = deduplicate_l2_occurrences(occurrences)
    for _, setup in paper_longs.iterrows():
        symbol = str(setup["symbol"])
        symbol_features = by_symbol.get(symbol)
        if symbol_features is None:
            continue
        matches = symbol_features.index[symbol_features["datetime"] == setup["datetime"]].tolist()
        if not matches:
            continue
        entry_index = matches[0]
        exit_index = entry_index + holding_period_bars
        if exit_index >= len(symbol_features):
            continue
        entry = symbol_features.iloc[entry_index]
        exit_row = symbol_features.iloc[exit_index]
        fill = simulate_long_fill(
            entry_ask=float(entry["best_ask"]),
            exit_bid=float(exit_row["best_bid"]),
            estimated_cost_bps=estimated_cost_bps,
        )
        records.append(
            {
                "symbol": symbol,
                "setup_id": setup["setup_id"],
                "overlapping_setup_count": setup["overlapping_setup_count"],
                "overlapping_setup_ids": setup["overlapping_setup_ids"],
                "entry_datetime": entry["datetime"],
                "exit_datetime": exit_row["datetime"],
                "paper_quantity": 1,
                "simulated_notional": float(entry["best_ask"]),
                **{feature: entry.get(feature, float("nan")) for feature in PRETRADE_FEATURES},
                **fill,
            }
        )
    return pd.DataFrame(
        records,
        columns=[
            "symbol",
            "setup_id",
            "overlapping_setup_count",
            "overlapping_setup_ids",
            "entry_datetime",
            "exit_datetime",
            "paper_quantity",
            "simulated_notional",
            *PRETRADE_FEATURES,
            "entry_price",
            "exit_price",
            "gross_return_bps",
            "estimated_cost_bps",
            "net_return_bps",
        ],
    )


def _rank_opening_symbols(feature_frame, config: OpeningLadderConfig):
    pd = __import__("pandas")
    records = []
    for symbol, symbol_features in feature_frame.groupby(feature_frame["symbol"].astype(str)):
        symbol_features = symbol_features.reset_index(drop=True)
        best_score = float("nan")
        qualified = False
        for entry_index, entry in symbol_features.iterrows():
            if not _is_inside_opening_window(
                entry["datetime"], config.warmup_start_et, config.warmup_end_et
            ):
                continue
            spread_start = max(0, entry_index - config.spread_compression_lookback)
            prior_spreads = symbol_features.iloc[spread_start:entry_index]["spread_bps"]
            decision = evaluate_opening_ladder_probe(
                entry,
                config,
                prior_row=symbol_features.iloc[entry_index - 1] if entry_index else None,
                rolling_median_spread_bps=(
                    float(prior_spreads.median()) if not prior_spreads.empty else None
                ),
            )
            if decision["probe_allowed"]:
                qualified = True
                best_score = max(best_score, decision["opening_score"]) if pd.notna(best_score) else decision[
                    "opening_score"
                ]
        records.append({"symbol": symbol, "opening_score": best_score, "setup_family_qualified": qualified})
    ranking = pd.DataFrame(records)
    ranking["_sort_score"] = ranking["opening_score"].fillna(float("-inf"))
    ranking = ranking.sort_values(["_sort_score", "symbol"], ascending=[False, True]).reset_index(drop=True)
    ranking["opening_rank"] = range(1, len(ranking) + 1)
    ranking["selected_for_ladder"] = (
        ranking["setup_family_qualified"]
        & (ranking["opening_score"] >= config.minimum_opening_score)
        & (ranking["opening_rank"] <= config.max_active_symbols_per_open)
    )
    if not config.use_ranked_symbol_selection:
        ranking["selected_for_ladder"] = ranking["setup_family_qualified"] & (
            ranking["opening_score"] >= config.minimum_opening_score
        )
    return ranking.drop(columns="_sort_score")


def simulate_opening_ladder(features, config: OpeningLadderConfig):
    pd = __import__("pandas")
    feature_frame = features.copy()
    feature_frame["datetime"] = pd.to_datetime(feature_frame["datetime"], utc=True, errors="coerce")
    feature_frame = feature_frame.sort_values(["symbol", "datetime"])
    ranking = _rank_opening_symbols(feature_frame, config)
    rank_by_symbol = ranking.set_index("symbol").to_dict("index")
    records: list[dict[str, Any]] = []
    for symbol, symbol_features in feature_frame.groupby(feature_frame["symbol"].astype(str)):
        symbol_features = symbol_features.reset_index(drop=True)
        probe_count = 0
        total_notional = 0.0
        next_probe_allowed_at = None
        symbol_rank = rank_by_symbol[symbol]
        for entry_index, entry in symbol_features.iterrows():
            if not _is_inside_opening_window(
                entry["datetime"], config.warmup_start_et, config.warmup_end_et
            ):
                continue
            exit_index = entry_index + config.holding_period_bars
            prior_row = symbol_features.iloc[entry_index - 1] if entry_index else None
            spread_start = max(0, entry_index - config.spread_compression_lookback)
            prior_spreads = symbol_features.iloc[spread_start:entry_index]["spread_bps"]
            decision = evaluate_opening_ladder_probe(
                entry,
                config,
                prior_probe_count=probe_count,
                prior_total_notional=total_notional,
                next_probe_allowed_at=next_probe_allowed_at,
                prior_row=prior_row,
                rolling_median_spread_bps=(
                    float(prior_spreads.median()) if not prior_spreads.empty else None
                ),
            )
            if decision["ladder_setup_family"] and not symbol_rank["selected_for_ladder"]:
                failures = [
                    *filter(None, decision["failed_conditions"].split(";")),
                    "ranked_below_active_symbol_cutoff",
                ]
                decision["probe_allowed"] = False
                decision["probe_rejection_reason"] = ";".join(dict.fromkeys(failures))
                decision["failed_conditions"] = ";".join(dict.fromkeys(failures))
                decision["paper_quantity"] = 0
                decision["simulated_notional"] = 0.0
            record = {
                "symbol": symbol,
                "ladder_probe_number": probe_count + 1,
                "entry_datetime": entry["datetime"],
                **{feature: entry.get(feature, float("nan")) for feature in PRETRADE_FEATURES},
                **decision,
                "symbol_opening_score": symbol_rank["opening_score"],
                "opening_rank": symbol_rank["opening_rank"],
                "selected_for_ladder": symbol_rank["selected_for_ladder"],
                "entry_price": float(entry["best_ask"]),
                "estimated_cost_bps": config.estimated_cost_bps,
                "opening_phase": classify_opening_phase(entry["datetime"]),
                "pretrade_assessment": pretrade_assessment(
                    entry,
                    max_spread_bps=config.max_spread_bps,
                    min_depth_10=config.min_depth_10,
                    min_imbalance_10=config.min_imbalance_10,
                ),
            }
            if decision["probe_allowed"] and exit_index >= len(symbol_features):
                decision["probe_allowed"] = False
                decision["probe_rejection_reason"] = "missing_exit_data"
                decision["failed_conditions"] = "missing_exit_data"
                decision["paper_quantity"] = 0
                decision["simulated_notional"] = 0.0
                record.update(decision)
            if decision["probe_allowed"]:
                exit_row = symbol_features.iloc[exit_index]
                fill = simulate_long_fill(
                    entry_ask=float(entry["best_ask"]),
                    exit_bid=float(exit_row["best_bid"]),
                    estimated_cost_bps=config.estimated_cost_bps,
                )
                holding_minutes = (
                    exit_row["datetime"] - entry["datetime"]
                ).total_seconds() / 60.0
                record.update(
                    {
                        "exit_datetime": exit_row["datetime"],
                        **fill,
                        "holding_minutes": holding_minutes,
                        "capital_released_at": exit_row["datetime"],
                        "notional_minutes": decision["simulated_notional"] * holding_minutes,
                        "net_bps_per_capital_minute": fill["net_return_bps"] / holding_minutes,
                        "realized_outcome": realized_outcome(fill["net_return_bps"]),
                    }
                )
                probe_count += 1
                total_notional += decision["simulated_notional"]
                cooldown_release = entry["datetime"] + pd.Timedelta(
                    minutes=config.ladder_cooldown_minutes
                )
                next_probe_allowed_at = max(cooldown_release, exit_row["datetime"])
            records.append(record)
    columns = [
        "symbol",
        "ladder_probe_number",
        "probe_allowed",
        "probe_rejection_reason",
        "ladder_setup_family",
        "setup_family_reason",
        "qualifying_conditions",
        "failed_conditions",
        "sizing_mode",
        "opening_score",
        "opening_score_family",
        "symbol_opening_score",
        "opening_rank",
        "selected_for_ladder",
        "entry_datetime",
        "exit_datetime",
        "paper_quantity",
        "simulated_notional",
        *PRETRADE_FEATURES,
        "entry_price",
        "exit_price",
        "gross_return_bps",
        "estimated_cost_bps",
        "net_return_bps",
        "holding_minutes",
        "capital_released_at",
        "notional_minutes",
        "net_bps_per_capital_minute",
        "opening_phase",
        "pretrade_assessment",
        "realized_outcome",
    ]
    return pd.DataFrame(records, columns=columns)


def enrich_trade_metrics(
    blotter,
    max_spread_bps: float = 100.0,
    min_depth_10: float = 100.0,
    min_imbalance_10: float = 0.10,
):
    pd = __import__("pandas")
    work = blotter.copy()
    extra_columns = [
        "holding_minutes",
        "capital_released_at",
        "notional_minutes",
        "net_bps_per_capital_minute",
        "opening_phase",
        "pretrade_assessment",
        "realized_outcome",
        "realized_net_return_bps",
    ]
    if work.empty:
        for column in extra_columns:
            work[column] = pd.Series(dtype="object")
        return work
    work["entry_datetime"] = pd.to_datetime(work["entry_datetime"], utc=True, errors="coerce")
    work["exit_datetime"] = pd.to_datetime(work["exit_datetime"], utc=True, errors="coerce")
    work["holding_minutes"] = (
        (work["exit_datetime"] - work["entry_datetime"]).dt.total_seconds() / 60.0
    )
    work["capital_released_at"] = work["entry_datetime"] + pd.to_timedelta(
        work["holding_minutes"], unit="m"
    )
    work["notional_minutes"] = work["simulated_notional"] * work["holding_minutes"]
    work["net_bps_per_capital_minute"] = work["net_return_bps"] / work["holding_minutes"]
    work["opening_phase"] = work["entry_datetime"].map(classify_opening_phase)
    work["pretrade_assessment"] = work.apply(
        lambda row: pretrade_assessment(
            row,
            max_spread_bps=max_spread_bps,
            min_depth_10=min_depth_10,
            min_imbalance_10=min_imbalance_10,
        ),
        axis=1,
    )
    work["realized_outcome"] = work["net_return_bps"].map(realized_outcome)
    work["realized_net_return_bps"] = work["net_return_bps"]
    return work


def filter_opening_warmup_trades(
    blotter,
    warmup_start_et: str,
    warmup_end_et: str,
    max_warmup_trades_per_symbol: int,
    max_warmup_notional: float,
    max_spread_bps: float = 100.0,
    min_depth_10: float = 100.0,
    min_imbalance_10: float = 0.10,
):
    pd = __import__("pandas")
    work = enrich_trade_metrics(
        blotter,
        max_spread_bps=max_spread_bps,
        min_depth_10=min_depth_10,
        min_imbalance_10=min_imbalance_10,
    )
    if work.empty:
        return work
    work["entry_datetime"] = pd.to_datetime(work["entry_datetime"], utc=True, errors="coerce")
    local_entries = work["entry_datetime"].dt.tz_convert("America/New_York")
    start = pd.to_datetime(warmup_start_et).time()
    end = pd.to_datetime(warmup_end_et).time()
    in_window = (local_entries.dt.time >= start) & (local_entries.dt.time <= end)
    within_notional = work["simulated_notional"] <= max_warmup_notional
    work = work.loc[in_window & within_notional].sort_values(["symbol", "entry_datetime"])
    return work.groupby("symbol", sort=False).head(max_warmup_trades_per_symbol).reset_index(drop=True)


def build_opening_diagnostics(
    occurrences,
    warmup_start_et: str,
    warmup_end_et: str,
    max_spread_bps: float = 100.0,
    min_depth_10: float = 100.0,
    min_imbalance_10: float = 0.10,
):
    pd = __import__("pandas")
    diagnostics = occurrences.copy()
    diagnostics["datetime"] = pd.to_datetime(diagnostics["datetime"], utc=True, errors="coerce")
    local_entries = diagnostics["datetime"].dt.tz_convert("America/New_York")
    start = pd.to_datetime(warmup_start_et).time()
    end = pd.to_datetime(warmup_end_et).time()
    diagnostics["is_opening_warmup_window"] = (
        (local_entries.dt.time >= start) & (local_entries.dt.time <= end)
    )
    used_symbols: set[str] = set()
    diagnostic_reasons = []
    for _, row in diagnostics.sort_values(["symbol", "datetime"]).iterrows():
        reasons = []
        if not row["is_opening_warmup_window"]:
            reasons.append("outside_opening_warmup")
        if float(row["spread_bps"]) > max_spread_bps:
            reasons.append("spread_too_wide")
        if (
            float(row["bid_depth_10"]) < min_depth_10
            or float(row["ask_depth_10"]) < min_depth_10
        ):
            reasons.append("depth_too_thin")
        if float(row["imbalance_10"]) < min_imbalance_10:
            reasons.append("book_pressure_against_trade")
        if float(row["microprice"]) <= float(row["midprice"]):
            reasons.append("microprice_not_confirming")
        symbol = str(row["symbol"])
        if (
            row["is_opening_warmup_window"]
            and row["decision"] == "PAPER_LONG"
            and symbol in used_symbols
        ):
            reasons.append("already_used_warmup_trade")
        elif row["is_opening_warmup_window"] and row["decision"] == "PAPER_LONG":
            used_symbols.add(symbol)
        diagnostic_reasons.append(";".join(reasons))
    diagnostics = diagnostics.sort_values(["symbol", "datetime"])
    diagnostics["diagnostic_reasons"] = diagnostic_reasons
    return diagnostics


def summarize_l2_trades(blotter):
    pd = __import__("pandas")
    columns = [
        "setup_id",
        "trade_count",
        "average_gross_return_bps",
        "average_net_return_bps",
        "total_net_return_bps",
        "win_rate",
    ]
    if blotter.empty:
        return pd.DataFrame(columns=columns)
    summary = (
        blotter.groupby("setup_id")
        .agg(
            trade_count=("net_return_bps", "size"),
            average_gross_return_bps=("gross_return_bps", "mean"),
            average_net_return_bps=("net_return_bps", "mean"),
            total_net_return_bps=("net_return_bps", "sum"),
            win_rate=("net_return_bps", lambda values: (values > 0).mean()),
        )
        .reset_index()
    )
    return summary[columns]


def summarize_opening_warmup(blotter, diagnostics):
    pd = __import__("pandas")
    columns = [
        "symbol",
        "opening_setup_occurrence_count",
        "opening_diagnostic_reject_count",
        "warmup_trade_count",
        "average_net_return_bps",
        "total_net_return_bps",
        "win_rate",
        "pretrade_assessment",
        "realized_outcome",
        "realized_net_return_bps",
        "total_notional_minutes",
        "average_holding_minutes",
        "average_net_bps_per_capital_minute",
    ]
    opening = diagnostics.loc[diagnostics["is_opening_warmup_window"]].copy()
    symbols = sorted(opening["symbol"].astype(str).unique())
    records = []
    for symbol in symbols:
        symbol_diagnostics = opening.loc[opening["symbol"].astype(str) == symbol]
        symbol_trades = blotter.loc[blotter["symbol"].astype(str) == symbol]
        trade_count = len(symbol_trades)
        reject_count = int((symbol_diagnostics["decision"] == "REJECT").sum())
        if trade_count:
            trade = symbol_trades.iloc[0]
            assessment = trade["pretrade_assessment"]
            outcome = trade["realized_outcome"]
            realized_net = trade["realized_net_return_bps"]
        else:
            assessment = "pass_today" if reject_count else "watch_only"
            outcome = "flat"
            realized_net = float("nan")
        records.append(
            {
                "symbol": symbol,
                "opening_setup_occurrence_count": len(symbol_diagnostics),
                "opening_diagnostic_reject_count": reject_count,
                "warmup_trade_count": trade_count,
                "average_net_return_bps": symbol_trades["net_return_bps"].mean(),
                "total_net_return_bps": symbol_trades["net_return_bps"].sum(),
                "win_rate": (symbol_trades["net_return_bps"] > 0).mean(),
                "pretrade_assessment": assessment,
                "realized_outcome": outcome,
                "realized_net_return_bps": realized_net,
                "total_notional_minutes": symbol_trades["notional_minutes"].sum(),
                "average_holding_minutes": symbol_trades["holding_minutes"].mean(),
                "average_net_bps_per_capital_minute": symbol_trades[
                    "net_bps_per_capital_minute"
                ].mean(),
            }
        )
    return pd.DataFrame(records, columns=columns)


def build_opening_vs_allday_comparison(warmup_blotter, all_day_blotter):
    pd = __import__("pandas")
    columns = [
        "mode",
        "trade_count",
        "avg_net_return_bps",
        "total_net_return_bps",
        "win_rate",
        "total_notional_minutes",
        "avg_net_bps_per_capital_minute",
    ]
    records = []
    for mode, blotter in (
        ("opening_warmup_only", enrich_trade_metrics(warmup_blotter)),
        ("all_day_repeated_entries", enrich_trade_metrics(all_day_blotter)),
    ):
        records.append(
            {
                "mode": mode,
                "trade_count": len(blotter),
                "avg_net_return_bps": blotter["net_return_bps"].mean(),
                "total_net_return_bps": blotter["net_return_bps"].sum(),
                "win_rate": (blotter["net_return_bps"] > 0).mean(),
                "total_notional_minutes": blotter["notional_minutes"].sum(),
                "avg_net_bps_per_capital_minute": blotter[
                    "net_bps_per_capital_minute"
                ].mean(),
            }
        )
    return pd.DataFrame(records, columns=columns)


def summarize_opening_ladder(ladder_blotter):
    pd = __import__("pandas")
    columns = [
        "symbol",
        "ladder_candidate_count",
        "ladder_probe_count",
        "rejected_probe_count",
        "average_net_return_bps",
        "total_net_return_bps",
        "win_rate",
        "total_simulated_notional",
        "total_notional_minutes",
        "average_holding_minutes",
        "average_net_bps_per_capital_minute",
        "probes_by_setup_family",
        "avg_net_bps_by_setup_family",
        "win_rate_by_setup_family",
    ]
    if ladder_blotter.empty:
        return pd.DataFrame(columns=columns)
    records = []
    for symbol, candidates in ladder_blotter.groupby("symbol"):
        probes = candidates.loc[candidates["probe_allowed"]].copy()
        records.append(
            {
                "symbol": symbol,
                "ladder_candidate_count": len(candidates),
                "ladder_probe_count": len(probes),
                "rejected_probe_count": int((~candidates["probe_allowed"]).sum()),
                "average_net_return_bps": probes["net_return_bps"].mean(),
                "total_net_return_bps": probes["net_return_bps"].sum(),
                "win_rate": (probes["net_return_bps"] > 0).mean(),
                "total_simulated_notional": probes["simulated_notional"].sum(),
                "total_notional_minutes": probes["notional_minutes"].sum(),
                "average_holding_minutes": probes["holding_minutes"].mean(),
                "average_net_bps_per_capital_minute": probes[
                    "net_bps_per_capital_minute"
                ].mean(),
                **_family_breakdown_fields(probes),
            }
        )
    return pd.DataFrame(records, columns=columns)


def _serialize_family_metric(probes, metric) -> str:
    if probes.empty:
        return ""
    values = []
    for family, family_probes in probes.groupby("ladder_setup_family", sort=True):
        values.append(f"{family}={metric(family_probes)}")
    return ";".join(values)


def _family_breakdown_fields(probes) -> dict[str, str]:
    return {
        "probes_by_setup_family": _serialize_family_metric(probes, lambda rows: len(rows)),
        "avg_net_bps_by_setup_family": _serialize_family_metric(
            probes, lambda rows: rows["net_return_bps"].mean()
        ),
        "win_rate_by_setup_family": _serialize_family_metric(
            probes, lambda rows: (rows["net_return_bps"] > 0).mean()
        ),
    }


def summarize_opening_ladder_families(ladder_blotter):
    pd = __import__("pandas")
    columns = [
        "ladder_setup_family",
        "trade_count",
        "avg_net_return_bps",
        "total_net_return_bps",
        "win_rate",
        "total_simulated_notional",
        "total_notional_minutes",
        "avg_net_bps_per_capital_minute",
    ]
    probes = ladder_blotter.loc[ladder_blotter["probe_allowed"]].copy()
    if probes.empty:
        return pd.DataFrame(columns=columns)
    summary = (
        probes.groupby("ladder_setup_family")
        .agg(
            trade_count=("net_return_bps", "size"),
            avg_net_return_bps=("net_return_bps", "mean"),
            total_net_return_bps=("net_return_bps", "sum"),
            win_rate=("net_return_bps", lambda values: (values > 0).mean()),
            total_simulated_notional=("simulated_notional", "sum"),
            total_notional_minutes=("notional_minutes", "sum"),
            avg_net_bps_per_capital_minute=("net_bps_per_capital_minute", "mean"),
        )
        .reset_index()
    )
    return summary[columns]


def build_opening_strategy_comparison(warmup_blotter, ladder_blotter, all_day_blotter):
    pd = __import__("pandas")
    columns = [
        "mode",
        "trade_count",
        "avg_net_return_bps",
        "total_net_return_bps",
        "win_rate",
        "total_simulated_notional",
        "total_notional_minutes",
        "avg_holding_minutes",
        "avg_net_bps_per_capital_minute",
        "probes_by_setup_family",
        "avg_net_bps_by_setup_family",
        "win_rate_by_setup_family",
    ]
    ladder_probes = ladder_blotter.loc[ladder_blotter["probe_allowed"]].copy()
    records = []
    for mode, blotter in (
        ("single_opening_teaser", enrich_trade_metrics(warmup_blotter)),
        ("opening_ladder", ladder_probes),
        ("all_day_repeated_entries", enrich_trade_metrics(all_day_blotter)),
    ):
        family_breakdown = (
            _family_breakdown_fields(blotter)
            if "ladder_setup_family" in blotter.columns
            else _family_breakdown_fields(pd.DataFrame())
        )
        records.append(
            {
                "mode": mode,
                "trade_count": len(blotter),
                "avg_net_return_bps": blotter["net_return_bps"].mean(),
                "total_net_return_bps": blotter["net_return_bps"].sum(),
                "win_rate": (blotter["net_return_bps"] > 0).mean(),
                "total_simulated_notional": blotter["simulated_notional"].sum(),
                "total_notional_minutes": blotter["notional_minutes"].sum(),
                "avg_holding_minutes": blotter["holding_minutes"].mean(),
                "avg_net_bps_per_capital_minute": blotter[
                    "net_bps_per_capital_minute"
                ].mean(),
                **family_breakdown,
            }
        )
    return pd.DataFrame(records, columns=columns)


def summarize_ladder_mode(mode: str, blotter):
    pd = __import__("pandas")
    probes = blotter.loc[blotter["probe_allowed"]].copy() if "probe_allowed" in blotter else blotter
    return {
        "mode": mode,
        "trade_count": len(probes),
        "avg_net_return_bps": probes["net_return_bps"].mean(),
        "total_net_return_bps": probes["net_return_bps"].sum(),
        "win_rate": (probes["net_return_bps"] > 0).mean(),
        "total_simulated_notional": probes["simulated_notional"].sum(),
        "total_notional_minutes": probes["notional_minutes"].sum(),
        "avg_holding_minutes": probes["holding_minutes"].mean(),
        "avg_net_bps_per_capital_minute": probes["net_bps_per_capital_minute"].mean(),
    }


def build_opening_primary_comparison(warmup_blotter, ranked_ladder_blotter):
    pd = __import__("pandas")
    return pd.DataFrame(
        [
            summarize_ladder_mode("single_opening_teaser", enrich_trade_metrics(warmup_blotter)),
            summarize_ladder_mode("ranked_opening_ladder", ranked_ladder_blotter),
        ]
    )


def build_opening_extended_benchmark_comparison(extended_ladder_blotter, all_day_blotter):
    pd = __import__("pandas")
    return pd.DataFrame(
        [
            summarize_ladder_mode("extended_opening_benchmark", extended_ladder_blotter),
            summarize_ladder_mode("bad_benchmark_all_day_reuse", enrich_trade_metrics(all_day_blotter)),
        ]
    )


def build_opening_ladder_symbol_assessment(features, ladder_blotter):
    pd = __import__("pandas")
    columns = [
        "symbol",
        "opening_score",
        "opening_rank",
        "selected_for_ladder",
        "assessment",
        "ladder_candidate_count",
        "qualified_candidate_count",
        "ladder_probe_count",
        "total_net_return_bps",
    ]
    records = []
    symbols = sorted(features["symbol"].astype(str).unique())
    for symbol in symbols:
        candidates = ladder_blotter.loc[ladder_blotter["symbol"].astype(str) == symbol]
        if candidates.empty:
            records.append({"symbol": symbol, "assessment": "no_data"})
            continue
        qualified = candidates.loc[candidates["ladder_setup_family"].fillna("") != ""]
        probes = candidates.loc[candidates["probe_allowed"]]
        selected = bool(candidates["selected_for_ladder"].iloc[0])
        total_net_return_bps = probes["net_return_bps"].sum()
        if selected:
            assessment = "tradable_today" if total_net_return_bps > 0 else "tradable_but_negative"
        elif not qualified.empty:
            assessment = "qualified_but_not_selected"
        else:
            assessment = "watch_only"
        records.append(
            {
                "symbol": symbol,
                "opening_score": candidates["symbol_opening_score"].iloc[0],
                "opening_rank": candidates["opening_rank"].iloc[0],
                "selected_for_ladder": selected,
                "assessment": assessment,
                "ladder_candidate_count": len(candidates),
                "qualified_candidate_count": len(qualified),
                "ladder_probe_count": len(probes),
                "total_net_return_bps": total_net_return_bps,
            }
        )
    return pd.DataFrame(records, columns=columns)


def build_opening_pair_trade_experiment(features, config: OpeningLadderConfig):
    pd = __import__("pandas")
    columns = [
        "timestamp",
        "long_symbol",
        "short_symbol",
        "setup_family_long",
        "setup_family_short",
        "long_return_bps",
        "short_return_bps",
        "pair_return_bps",
        "equal_dollar_notional",
    ]
    feature_frame = features.copy()
    feature_frame["datetime"] = pd.to_datetime(feature_frame["datetime"], utc=True, errors="coerce")
    feature_frame = feature_frame.sort_values(["symbol", "datetime"])
    candidates = []
    for symbol, symbol_features in feature_frame.groupby(feature_frame["symbol"].astype(str)):
        symbol_features = symbol_features.reset_index(drop=True)
        for entry_index, entry in symbol_features.iterrows():
            if not _is_inside_opening_window(
                entry["datetime"], config.warmup_start_et, config.warmup_end_et
            ):
                continue
            exit_index = entry_index + config.holding_period_bars
            if exit_index >= len(symbol_features):
                continue
            spread_start = max(0, entry_index - config.spread_compression_lookback)
            prior_spreads = symbol_features.iloc[spread_start:entry_index]["spread_bps"]
            decision = evaluate_opening_ladder_probe(
                entry,
                config,
                prior_row=symbol_features.iloc[entry_index - 1] if entry_index else None,
                rolling_median_spread_bps=(
                    float(prior_spreads.median()) if not prior_spreads.empty else None
                ),
            )
            if decision["probe_allowed"]:
                candidates.append(
                    {
                        "timestamp": entry["datetime"],
                        "symbol": symbol,
                        "opening_score": decision["opening_score"],
                        "ladder_setup_family": decision["ladder_setup_family"],
                        "entry": entry,
                        "exit": symbol_features.iloc[exit_index],
                    }
                )
    records = []
    for timestamp, group in pd.DataFrame(candidates).groupby("timestamp") if candidates else []:
        if len(group) < 2:
            continue
        ranked = group.sort_values(["opening_score", "symbol"], ascending=[False, True])
        long_leg = ranked.iloc[0]
        short_leg = ranked.iloc[-1]
        long_fill = simulate_long_fill(
            float(long_leg["entry"]["best_ask"]),
            float(long_leg["exit"]["best_bid"]),
            config.estimated_cost_bps,
        )
        short_return_bps = (
            float(short_leg["exit"]["best_ask"]) / float(short_leg["entry"]["best_bid"]) - 1.0
        ) * 10000.0 + config.estimated_cost_bps
        records.append(
            {
                "timestamp": timestamp,
                "long_symbol": long_leg["symbol"],
                "short_symbol": short_leg["symbol"],
                "setup_family_long": long_leg["ladder_setup_family"],
                "setup_family_short": short_leg["ladder_setup_family"],
                "long_return_bps": long_fill["net_return_bps"],
                "short_return_bps": short_return_bps,
                "pair_return_bps": long_fill["net_return_bps"] - short_return_bps,
                "equal_dollar_notional": config.ladder_probe_notional,
            }
        )
    return pd.DataFrame(records, columns=columns)


def simulate_extended_opening_benchmark(features, config: OpeningLadderConfig):
    return simulate_opening_ladder(
        features,
        replace(
            config,
            warmup_start_et=config.extended_opening_benchmark_start_et,
            warmup_end_et=config.extended_opening_benchmark_end_et,
            use_ranked_symbol_selection=False,
        ),
    )
