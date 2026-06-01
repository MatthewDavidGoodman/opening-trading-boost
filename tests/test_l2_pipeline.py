from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from opening_trading_boost.l2_features import (
    build_l2_features_for_frame,
    calculate_imbalance,
    calculate_microprice,
)
from opening_trading_boost.l2_setups import L2SetupConfig, detect_l2_setups
from opening_trading_boost.l2_simulation import (
    OpeningLadderConfig,
    build_opening_ladder_symbol_assessment,
    build_opening_pair_trade_experiment,
    build_opening_primary_comparison,
    build_opening_diagnostics,
    build_opening_strategy_comparison,
    classify_opening_phase,
    enrich_trade_metrics,
    evaluate_opening_ladder_probe,
    filter_opening_warmup_trades,
    pretrade_assessment,
    simulate_l2_trades,
    simulate_long_fill,
    simulate_opening_ladder,
    simulate_extended_opening_benchmark,
    summarize_l2_trades,
    summarize_opening_ladder_families,
)
from research.download_databento_l2 import download


def _mbp10_fixture() -> pd.DataFrame:
    rows = []
    for minute in range(7):
        row: dict[str, object] = {
            "ts_recv": f"2026-05-01T14:0{minute}:00Z",
            "action": "T" if minute in {1, 6} else "A",
            "size": 10 + minute,
        }
        for level in range(10):
            row[f"bid_px_{level:02d}"] = 10.00 + minute * 0.01 - level * 0.01
            row[f"ask_px_{level:02d}"] = 10.02 + minute * 0.01 + level * 0.01
            row[f"bid_sz_{level:02d}"] = 20 + level
            row[f"ask_sz_{level:02d}"] = 10 + level
        rows.append(row)
    return pd.DataFrame(rows)


def test_l2_feature_calculation():
    features = build_l2_features_for_frame(_mbp10_fixture(), symbol="SOUN")

    row = features.iloc[1]
    assert row["symbol"] == "SOUN"
    assert row["best_bid"] == pytest.approx(10.01)
    assert row["best_ask"] == pytest.approx(10.03)
    assert row["spread_bps"] == pytest.approx((0.02 / 10.02) * 10000)
    assert row["trade_count"] == 1
    assert row["trade_volume"] == 11
    assert features.iloc[6]["mid_return_5m"] > 0
    assert features["imbalance_1"].between(-1, 1).all()
    assert features["imbalance_10"].between(-1, 1).all()
    assert features["microprice"].between(features["best_bid"], features["best_ask"]).all()


def test_imbalance_calculation():
    imbalance = calculate_imbalance(pd.Series([30.0]), pd.Series([10.0]))
    assert imbalance.iloc[0] == pytest.approx(0.5)


def test_microprice_calculation():
    microprice = calculate_microprice(
        pd.Series([10.0]),
        pd.Series([10.2]),
        pd.Series([30.0]),
        pd.Series([10.0]),
    )
    assert microprice.iloc[0] == pytest.approx(10.15)


def test_unsigned_sizes_do_not_underflow():
    frame = _mbp10_fixture()
    for level in range(10):
        frame[f"ask_sz_{level:02d}"] = frame[f"bid_sz_{level:02d}"] + 10
    features = build_l2_features_for_frame(
        frame.astype(
            {f"{side}_sz_{level:02d}": "uint64" for side in ("bid", "ask") for level in range(10)}
        ),
        symbol="SOUN",
    )

    assert features["imbalance_1"].between(-1, 1).all()
    assert features["imbalance_10"].between(-1, 1).all()


def test_zero_size_denominator_falls_back_safely():
    imbalance = calculate_imbalance(pd.Series([0], dtype="uint64"), pd.Series([0], dtype="uint64"))
    microprice = calculate_microprice(
        pd.Series([10.0]),
        pd.Series([10.2]),
        pd.Series([0], dtype="uint64"),
        pd.Series([0], dtype="uint64"),
    )

    assert imbalance.iloc[0] == 0.0
    assert microprice.iloc[0] == pytest.approx(10.1)


def test_liquidity_rejection_rule():
    features = pd.DataFrame(
        [
            {
                "symbol": "SOUN",
                "datetime": "2026-05-01T14:00:00Z",
                "spread_bps": 150.0,
                "bid_depth_10": 50,
                "ask_depth_10": 75,
                "imbalance_10": 0.4,
                "mid_return_1m": 0.01,
                "mid_return_5m": 0.02,
                "microprice": 10.1,
                "midprice": 10.0,
            }
        ]
    )

    setups = detect_l2_setups(features, L2SetupConfig())

    assert setups.loc[0, "setup_id"] == "L2_LIQUIDITY_REJECT"
    assert setups.loc[0, "decision"] == "REJECT"
    assert "spread_too_wide" in setups.loc[0, "rejection_reason"]
    assert "bid_depth_too_thin" in setups.loc[0, "rejection_reason"]


def test_simulated_cost_subtraction():
    result = simulate_long_fill(entry_ask=10.0, exit_bid=10.1, estimated_cost_bps=5.0)
    assert result["gross_return_bps"] == pytest.approx(100.0)
    assert result["net_return_bps"] == pytest.approx(95.0)


def _simulation_features() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "symbol": "SOUN",
                "datetime": f"2026-05-28T{hour_minute}:00Z",
                "best_bid": bid,
                "best_ask": bid + 0.02,
                "spread_bps": 20.0,
                "imbalance_10": 0.4,
                "imbalance_1": 0.5,
                "microprice": bid + 0.015,
                "midprice": bid + 0.01,
                "bid_depth_10": 500,
                "ask_depth_10": 300,
                "trade_count": 10,
                "trade_volume": 1000,
                "mid_return_1m": 0.01,
                "mid_return_5m": 0.02,
            }
            for hour_minute, bid in [
                ("13:35", 10.00),
                ("13:36", 10.01),
                ("13:37", 10.02),
                ("13:38", 10.03),
                ("13:39", 10.04),
                ("13:40", 10.10),
                ("14:21", 10.20),
                ("14:22", 10.21),
                ("14:23", 10.22),
                ("14:24", 10.23),
                ("14:25", 10.24),
                ("14:26", 10.30),
                ("15:00", 10.40),
                ("15:01", 10.41),
                ("15:02", 10.42),
                ("15:03", 10.43),
                ("15:04", 10.44),
                ("15:05", 10.50),
            ]
        ]
    )


def _simulation_occurrences() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "symbol": "SOUN",
                "datetime": "2026-05-28T13:35:00Z",
                "setup_id": "L2_MOMENTUM_CONFIRMATION",
                "decision": "PAPER_LONG",
            },
            {
                "symbol": "SOUN",
                "datetime": "2026-05-28T13:35:00Z",
                "setup_id": "L2_RECLAIM_LONG",
                "decision": "PAPER_LONG",
            },
            {
                "symbol": "SOUN",
                "datetime": "2026-05-28T14:21:00Z",
                "setup_id": "L2_MOMENTUM_CONFIRMATION",
                "decision": "PAPER_LONG",
            },
            {
                "symbol": "SOUN",
                "datetime": "2026-05-28T15:00:00Z",
                "setup_id": "L2_MOMENTUM_CONFIRMATION",
                "decision": "PAPER_LONG",
            },
        ]
    )


def test_duplicate_setup_rows_produce_one_blotter_row_with_reclaim_priority():
    blotter = simulate_l2_trades(_simulation_features(), _simulation_occurrences(), 5, 5.0)

    assert len(blotter) == 3
    first = blotter.iloc[0]
    assert first["setup_id"] == "L2_RECLAIM_LONG"
    assert first["overlapping_setup_count"] == 2
    assert first["overlapping_setup_ids"] == "L2_RECLAIM_LONG;L2_MOMENTUM_CONFIRMATION"
    assert blotter["entry_datetime"].nunique() == 3


def test_performance_summary_uses_deduplicated_blotter():
    blotter = simulate_l2_trades(_simulation_features(), _simulation_occurrences(), 5, 5.0)
    summary = summarize_l2_trades(blotter)

    assert summary["trade_count"].sum() == 3
    assert summary.set_index("setup_id").loc["L2_RECLAIM_LONG", "trade_count"] == 1


def test_non_overlapping_setup_rows_remain_separate():
    occurrences = _simulation_occurrences().iloc[[0, 2, 3]]
    blotter = simulate_l2_trades(_simulation_features(), occurrences, 5, 5.0)

    assert len(blotter) == 3
    assert blotter["overlapping_setup_count"].tolist() == [1, 1, 1]


def test_opening_warmup_filter_and_max_one_trade_per_symbol():
    blotter = simulate_l2_trades(_simulation_features(), _simulation_occurrences(), 5, 5.0)
    warmup = filter_opening_warmup_trades(blotter, "09:30", "10:30", 1, 300)

    assert len(warmup) == 1
    assert warmup.loc[0, "entry_datetime"] == pd.Timestamp("2026-05-28T13:35:00Z")
    assert warmup.loc[0, "paper_quantity"] == 1
    assert warmup.loc[0, "simulated_notional"] <= 300
    assert "active" not in warmup.columns
    assert "live" not in warmup.columns


def test_pretrade_assessment_does_not_depend_on_realized_return():
    row = _simulation_features().iloc[0].to_dict()
    row["realized_net_return_bps"] = -999.0
    first = pretrade_assessment(row)
    row["realized_net_return_bps"] = 999.0

    assert first == "tradable_today"
    assert pretrade_assessment(row) == first


def test_capital_release_and_notional_minutes():
    blotter = simulate_l2_trades(_simulation_features(), _simulation_occurrences(), 5, 5.0)
    enriched = enrich_trade_metrics(blotter)
    first = enriched.iloc[0]

    assert first["holding_minutes"] == pytest.approx(5.0)
    assert first["capital_released_at"] == first["entry_datetime"] + pd.Timedelta(minutes=5)
    assert first["notional_minutes"] == pytest.approx(first["simulated_notional"] * 5)


@pytest.mark.parametrize(
    ("timestamp", "phase"),
    [
        ("2026-05-28T13:30:00Z", "observe_open"),
        ("2026-05-28T13:35:00Z", "first_teaser_window"),
        ("2026-05-28T13:50:00Z", "confirmation_window"),
        ("2026-05-28T14:15:00Z", "final_warmup_window"),
        ("2026-05-28T14:30:00Z", "outside_opening_warmup"),
    ],
)
def test_opening_phase_classification(timestamp, phase):
    assert classify_opening_phase(timestamp) == phase


def test_opening_diagnostics_explain_rejections_and_repeated_entries():
    occurrences = pd.DataFrame(
        [
            {
                "symbol": "SOUN",
                "datetime": "2026-05-28T13:35:00Z",
                "spread_bps": 20.0,
                "bid_depth_10": 500,
                "ask_depth_10": 300,
                "imbalance_10": 0.4,
                "microprice": 10.02,
                "midprice": 10.01,
                "decision": "PAPER_LONG",
            },
            {
                "symbol": "SOUN",
                "datetime": "2026-05-28T13:36:00Z",
                "spread_bps": 150.0,
                "bid_depth_10": 50,
                "ask_depth_10": 300,
                "imbalance_10": -0.1,
                "microprice": 10.00,
                "midprice": 10.01,
                "decision": "PAPER_LONG",
            },
            {
                "symbol": "SOUN",
                "datetime": "2026-05-28T18:00:00Z",
                "spread_bps": 20.0,
                "bid_depth_10": 500,
                "ask_depth_10": 300,
                "imbalance_10": 0.4,
                "microprice": 10.02,
                "midprice": 10.01,
                "decision": "PAPER_LONG",
            },
        ]
    )

    diagnostics = build_opening_diagnostics(occurrences, "09:30", "10:30")
    second_reasons = diagnostics.iloc[1]["diagnostic_reasons"]

    assert "spread_too_wide" in second_reasons
    assert "depth_too_thin" in second_reasons
    assert "book_pressure_against_trade" in second_reasons
    assert "microprice_not_confirming" in second_reasons
    assert "already_used_warmup_trade" in second_reasons
    assert diagnostics.iloc[2]["diagnostic_reasons"] == "outside_opening_warmup"


def _ladder_row(**overrides) -> dict[str, object]:
    row: dict[str, object] = {
        "symbol": "SOUN",
        "datetime": "2026-05-28T13:35:00Z",
        "best_bid": 10.00,
        "best_ask": 10.02,
        "spread_bps": 20.0,
        "imbalance_10": 0.4,
        "imbalance_1": 0.5,
        "microprice": 10.015,
        "midprice": 10.01,
        "bid_depth_10": 500,
        "ask_depth_10": 300,
        "trade_count": 10,
        "trade_volume": 1000,
        "mid_return_1m": 0.01,
        "mid_return_5m": 0.02,
    }
    row.update(overrides)
    return row


def _ladder_features() -> pd.DataFrame:
    return pd.DataFrame(
        [
            _ladder_row(
                datetime=f"2026-05-28T13:{minute:02d}:00Z",
                best_bid=10.00 + (minute - 35) / 100,
                best_ask=10.02 + (minute - 35) / 100,
                midprice=10.01 + (minute - 35) / 100,
                microprice=10.015 + (minute - 35) / 100,
            )
            for minute in range(35, 56)
        ]
    )


def test_ladder_sizing_floors_notional_into_share_quantity():
    decision = evaluate_opening_ladder_probe(_ladder_row(), OpeningLadderConfig())

    assert decision["probe_allowed"]
    assert decision["paper_quantity"] == 4
    assert decision["simulated_notional"] == pytest.approx(40.08)
    assert decision["sizing_mode"] == "target_notional_floor"


def test_ladder_allows_one_share_above_target_notional_below_single_probe_cap():
    decision = evaluate_opening_ladder_probe(
        _ladder_row(best_ask=75.01), OpeningLadderConfig()
    )

    assert decision["probe_allowed"]
    assert decision["paper_quantity"] == 1
    assert decision["simulated_notional"] == pytest.approx(75.01)
    assert decision["sizing_mode"] == "one_share_high_price_probe"


def test_ladder_rejects_price_above_max_single_probe_notional():
    decision = evaluate_opening_ladder_probe(
        _ladder_row(best_ask=150.01), OpeningLadderConfig()
    )

    assert not decision["probe_allowed"]
    assert "price_above_max_single_probe_notional" in decision["probe_rejection_reason"]
    assert decision["sizing_mode"] == "rejected_price_above_cap"


def test_ladder_cooldown_prevents_immediate_repeated_probe():
    decision = evaluate_opening_ladder_probe(
        _ladder_row(datetime="2026-05-28T13:36:00Z"),
        OpeningLadderConfig(),
        next_probe_allowed_at="2026-05-28T13:40:00Z",
    )

    assert not decision["probe_allowed"]
    assert "ladder_cooldown_not_passed" in decision["probe_rejection_reason"]


def test_ladder_rejects_probe_outside_opening_window():
    decision = evaluate_opening_ladder_probe(
        _ladder_row(datetime="2026-05-28T14:30:00Z"), OpeningLadderConfig()
    )

    assert not decision["probe_allowed"]
    assert "outside_opening_warmup" in decision["probe_rejection_reason"]


def test_ladder_max_probe_count_is_enforced():
    decision = evaluate_opening_ladder_probe(
        _ladder_row(), OpeningLadderConfig(), prior_probe_count=3
    )

    assert not decision["probe_allowed"]
    assert "max_ladder_probes_reached" in decision["probe_rejection_reason"]


def test_ladder_total_notional_cap_is_enforced():
    decision = evaluate_opening_ladder_probe(
        _ladder_row(),
        OpeningLadderConfig(max_ladder_total_notional_per_symbol=120),
        prior_total_notional=100,
    )

    assert not decision["probe_allowed"]
    assert "max_ladder_total_notional_reached" in decision["probe_rejection_reason"]


def test_ladder_high_price_probe_respects_total_notional_cap():
    decision = evaluate_opening_ladder_probe(
        _ladder_row(best_ask=75.01),
        OpeningLadderConfig(max_ladder_total_notional_per_symbol=150),
        prior_total_notional=100,
    )

    assert not decision["probe_allowed"]
    assert decision["sizing_mode"] == "one_share_high_price_probe"
    assert "total_ladder_notional_cap_reached" in decision["failed_conditions"]


def test_rklb_style_price_is_not_automatically_rejected_below_single_probe_cap():
    decision = evaluate_opening_ladder_probe(
        _ladder_row(best_ask=72.50),
        OpeningLadderConfig(),
    )

    assert decision["probe_allowed"]
    assert decision["paper_quantity"] == 1
    assert decision["sizing_mode"] == "one_share_high_price_probe"
    assert "price_above_max_single_probe_notional" not in decision["failed_conditions"]


def test_bad_l2_diagnostics_reject_ladder_probe():
    decision = evaluate_opening_ladder_probe(
        _ladder_row(spread_bps=150, bid_depth_10=50, imbalance_10=-0.1, microprice=10.0),
        OpeningLadderConfig(),
    )

    assert not decision["probe_allowed"]
    assert "spread_too_wide" in decision["probe_rejection_reason"]
    assert "depth_too_thin" in decision["probe_rejection_reason"]
    assert "book_pressure_against_trade" in decision["probe_rejection_reason"]
    assert "microprice_not_confirming" in decision["probe_rejection_reason"]


def test_ladder_requires_an_explicitly_non_negative_recent_return():
    decision = evaluate_opening_ladder_probe(
        _ladder_row(mid_return_1m=-0.01, mid_return_5m=float("nan")),
        OpeningLadderConfig(),
    )

    assert not decision["probe_allowed"]
    assert "recent_mid_returns_negative" in decision["probe_rejection_reason"]


def test_spread_compression_setup_qualifies_without_positive_imbalance():
    decision = evaluate_opening_ladder_probe(
        _ladder_row(imbalance_10=-0.2, microprice=10.009),
        OpeningLadderConfig(),
        rolling_median_spread_bps=25,
    )

    assert decision["probe_allowed"]
    assert decision["ladder_setup_family"] == "OPENING_LADDER_SPREAD_COMPRESSION_LONG"


def test_pullback_reclaim_setup_qualifies_after_prior_negative_return():
    decision = evaluate_opening_ladder_probe(
        _ladder_row(imbalance_10=0.05),
        OpeningLadderConfig(),
        prior_row=_ladder_row(mid_return_1m=-0.01, mid_return_5m=-0.02, imbalance_10=-0.1),
    )

    assert decision["probe_allowed"]
    assert decision["ladder_setup_family"] == "OPENING_LADDER_PULLBACK_RECLAIM_LONG"


def test_imbalance_setup_still_qualifies():
    decision = evaluate_opening_ladder_probe(_ladder_row(), OpeningLadderConfig())

    assert decision["ladder_setup_family"] == "OPENING_LADDER_IMBALANCE_LONG"


def test_ladder_family_priority_prefers_pullback_then_imbalance_then_compression():
    pullback = evaluate_opening_ladder_probe(
        _ladder_row(),
        OpeningLadderConfig(),
        prior_row=_ladder_row(mid_return_1m=-0.01),
        rolling_median_spread_bps=25,
    )
    imbalance = evaluate_opening_ladder_probe(
        _ladder_row(), OpeningLadderConfig(), rolling_median_spread_bps=25
    )
    compression = evaluate_opening_ladder_probe(
        _ladder_row(imbalance_10=-0.2, microprice=10.009),
        OpeningLadderConfig(),
        rolling_median_spread_bps=25,
    )

    assert pullback["ladder_setup_family"] == "OPENING_LADDER_PULLBACK_RECLAIM_LONG"
    assert imbalance["ladder_setup_family"] == "OPENING_LADDER_IMBALANCE_LONG"
    assert compression["ladder_setup_family"] == "OPENING_LADDER_SPREAD_COMPRESSION_LONG"


def test_ladder_failed_conditions_include_family_diagnostics():
    decision = evaluate_opening_ladder_probe(
        _ladder_row(
            imbalance_10=-0.2,
            microprice=9.99,
            bid_depth_10=100,
            ask_depth_10=100,
            trade_count=1,
            trade_volume=10,
        ),
        OpeningLadderConfig(),
        rolling_median_spread_bps=10,
    )

    assert not decision["probe_allowed"]
    assert "spread_not_compressed" in decision["failed_conditions"]
    assert "total_depth_too_thin" in decision["failed_conditions"]
    assert "insufficient_trade_count" in decision["failed_conditions"]
    assert "insufficient_trade_volume" in decision["failed_conditions"]
    assert "microprice_not_confirming" in decision["failed_conditions"]
    assert "imbalance_not_confirming" in decision["failed_conditions"]


def test_ladder_caps_apply_to_spread_compression_family():
    decision = evaluate_opening_ladder_probe(
        _ladder_row(imbalance_10=-0.2, microprice=10.009),
        OpeningLadderConfig(),
        prior_probe_count=3,
        rolling_median_spread_bps=25,
    )

    assert not decision["probe_allowed"]
    assert decision["ladder_setup_family"] == "OPENING_LADDER_SPREAD_COMPRESSION_LONG"
    assert "max_ladder_probes_reached" in decision["failed_conditions"]


def test_ladder_recycles_capital_and_calculates_notional_minutes():
    blotter = simulate_opening_ladder(_ladder_features(), OpeningLadderConfig())
    probes = blotter.loc[blotter["probe_allowed"]].reset_index(drop=True)

    assert len(probes) == 2
    assert probes.loc[0, "capital_released_at"] == probes.loc[0, "exit_datetime"]
    assert probes.loc[0, "holding_minutes"] == pytest.approx(5.0)
    assert probes.loc[0, "notional_minutes"] == pytest.approx(
        probes.loc[0, "simulated_notional"] * 5
    )


def test_strategy_comparison_includes_three_modes():
    all_day = simulate_l2_trades(_simulation_features(), _simulation_occurrences(), 5, 5.0)
    warmup = filter_opening_warmup_trades(all_day, "09:30", "10:30", 1, 300)
    ladder = simulate_opening_ladder(_ladder_features(), OpeningLadderConfig())

    comparison = build_opening_strategy_comparison(warmup, ladder, all_day)

    assert comparison["mode"].tolist() == [
        "single_opening_teaser",
        "opening_ladder",
        "all_day_repeated_entries",
    ]
    family_summary = summarize_opening_ladder_families(ladder)
    assert family_summary["ladder_setup_family"].tolist() == ["OPENING_LADDER_IMBALANCE_LONG"]


def test_primary_ladder_defaults_to_tight_opening_window_and_reduced_entries():
    config = OpeningLadderConfig()

    assert config.warmup_start_et == "09:35"
    assert config.warmup_end_et == "10:00"
    assert config.max_ladder_probes_per_symbol == 2
    assert config.ladder_cooldown_minutes == 7


def test_extended_opening_benchmark_retains_old_window_only_for_benchmark():
    features = pd.DataFrame(
        [
            _ladder_row(datetime=f"2026-05-28T13:{minute:02d}:00Z")
            for minute in range(30, 36)
        ]
    )

    primary = simulate_opening_ladder(features, OpeningLadderConfig())
    extended = simulate_extended_opening_benchmark(features, OpeningLadderConfig())

    assert primary["entry_datetime"].min() == pd.Timestamp("2026-05-28T13:35:00Z")
    assert extended["entry_datetime"].min() == pd.Timestamp("2026-05-28T13:30:00Z")


def _ranked_ladder_features() -> pd.DataFrame:
    rows = []
    for symbol, spread, depth in [("TOP", 10.0, 900), ("MID", 20.0, 700), ("LOW", 40.0, 500)]:
        for minute in range(35, 46):
            rows.append(
                _ladder_row(
                    symbol=symbol,
                    datetime=f"2026-05-28T13:{minute:02d}:00Z",
                    spread_bps=spread,
                    bid_depth_10=depth,
                    ask_depth_10=depth,
                )
            )
    return pd.DataFrame(rows)


def test_ranked_selection_keeps_only_top_two_symbols():
    blotter = simulate_opening_ladder(_ranked_ladder_features(), OpeningLadderConfig())
    selected = set(blotter.loc[blotter["selected_for_ladder"], "symbol"])
    low = blotter.loc[blotter["symbol"] == "LOW"]

    assert selected == {"TOP", "MID"}
    assert low["failed_conditions"].str.contains("ranked_below_active_symbol_cutoff").all()


def test_low_ranked_qualified_symbol_assessment_is_not_selected():
    features = _ranked_ladder_features()
    blotter = simulate_opening_ladder(features, OpeningLadderConfig())
    assessment = build_opening_ladder_symbol_assessment(features, blotter).set_index("symbol")

    assert assessment.loc["LOW", "assessment"] == "qualified_but_not_selected"
    assert not assessment.loc["LOW", "selected_for_ladder"]


def test_pair_trade_experiment_requires_two_symbols_at_same_timestamp():
    one_symbol = _ladder_features()
    two_symbols = pd.concat(
        [one_symbol, one_symbol.assign(symbol="RIVN", spread_bps=10.0)], ignore_index=True
    )

    assert build_opening_pair_trade_experiment(one_symbol, OpeningLadderConfig()).empty
    pair = build_opening_pair_trade_experiment(two_symbols, OpeningLadderConfig())
    assert not pair.empty
    assert set(pair.columns) == {
        "timestamp",
        "long_symbol",
        "short_symbol",
        "setup_family_long",
        "setup_family_short",
        "long_return_bps",
        "short_return_bps",
        "pair_return_bps",
        "equal_dollar_notional",
    }


def test_pair_trade_experiment_is_not_in_primary_comparison():
    all_day = simulate_l2_trades(_simulation_features(), _simulation_occurrences(), 5, 5.0)
    warmup = filter_opening_warmup_trades(all_day, "09:35", "10:00", 1, 300)
    ladder = simulate_opening_ladder(_ladder_features(), OpeningLadderConfig())

    comparison = build_opening_primary_comparison(warmup, ladder)

    assert comparison["mode"].tolist() == ["single_opening_teaser", "ranked_opening_ladder"]


def _write_databento_config(path: Path) -> None:
    path.write_text(
        """
[databento]
dataset = "TEST.DATASET"
schema = "mbp-10"
symbols = ["SOUN"]
start = "2026-05-01"
end = "2026-05-02"
stype_in = "raw_symbol"
raw_dir = "data/databento/raw"
processed_dir = "data/databento/processed"
feature_path = "data/features/l2_features.csv"
resample_interval = "1min"
max_rows = 100
""".strip(),
        encoding="utf-8",
    )


def test_missing_api_key_fails_cleanly(tmp_path, monkeypatch):
    config = tmp_path / "databento.toml"
    _write_databento_config(config)
    monkeypatch.delenv("DATABENTO_API_KEY", raising=False)

    with pytest.raises(SystemExit, match="DATABENTO_API_KEY must be set"):
        download(config)


def test_dry_run_does_not_call_network(tmp_path, monkeypatch, capsys):
    config = tmp_path / "databento.toml"
    _write_databento_config(config)
    monkeypatch.delenv("DATABENTO_API_KEY", raising=False)

    def fail_if_called(_api_key: str):
        raise AssertionError("dry-run constructed a network client")

    assert download(config, dry_run=True, client_factory=fail_if_called) == []
    assert "dry-run: no Databento API call made" in capsys.readouterr().out
