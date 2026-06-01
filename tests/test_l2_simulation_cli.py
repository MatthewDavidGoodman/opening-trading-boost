from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from research import simulate_l2_trades


def test_l2_simulator_stays_offline_and_writes_warmup_and_versioned_outputs(
    tmp_path, monkeypatch
):
    features = tmp_path / "features.csv"
    setups = tmp_path / "setups.csv"
    pd.DataFrame(
        [
            {
                "symbol": "SOUN",
                "datetime": f"2026-05-28T13:{minute:02d}:00Z",
                "best_bid": 10.00 + minute / 100,
                "best_ask": 10.02 + minute / 100,
                "spread_bps": 20.0,
                "imbalance_10": 0.4,
                "imbalance_1": 0.5,
                "microprice": 10.015 + minute / 100,
                "midprice": 10.01 + minute / 100,
                "bid_depth_10": 500,
                "ask_depth_10": 300,
                "trade_count": 10,
                "trade_volume": 1000,
                "mid_return_1m": 0.01,
                "mid_return_5m": 0.02,
            }
            for minute in range(35, 41)
        ]
    ).to_csv(features, index=False)
    pd.DataFrame(
        [
            {
                "symbol": "SOUN",
                "datetime": "2026-05-28T13:35:00Z",
                "setup_id": "L2_MOMENTUM_CONFIRMATION",
                "decision": "PAPER_LONG",
                "spread_bps": 20.0,
                "imbalance_10": 0.4,
                "microprice": 10.365,
                "midprice": 10.36,
                "bid_depth_10": 500,
                "ask_depth_10": 300,
            }
        ]
    ).to_csv(setups, index=False)

    paths = {
        "blotter": tmp_path / "all_day.csv",
        "summary": tmp_path / "all_day_summary.csv",
        "warmup": tmp_path / "warmup.csv",
        "warmup_summary": tmp_path / "warmup_summary.csv",
        "diagnostics": tmp_path / "diagnostics.csv",
        "comparison": tmp_path / "comparison.csv",
        "ladder": tmp_path / "ladder.csv",
        "ladder_summary": tmp_path / "ladder_summary.csv",
        "strategy_comparison": tmp_path / "strategy_comparison.csv",
        "ladder_family_summary": tmp_path / "ladder_family_summary.csv",
        "ladder_symbol_assessment": tmp_path / "ladder_symbol_assessment.csv",
        "primary_comparison": tmp_path / "primary_comparison.csv",
        "extended_benchmark_comparison": tmp_path / "extended_benchmark_comparison.csv",
        "pair_trade_experiment": tmp_path / "pair_trade_experiment.csv",
    }
    config = tmp_path / "databento.toml"
    config.write_text(
        f"""
[simulation]
session_focus = "opening_ladder"
warmup_start_et = "09:35"
warmup_end_et = "10:00"
extended_opening_benchmark_start_et = "09:30"
extended_opening_benchmark_end_et = "10:30"
max_warmup_trades_per_symbol = 1
max_warmup_notional = 300
max_ladder_probes_per_symbol = 2
ladder_probe_notional = 50
max_ladder_single_probe_notional = 150
max_ladder_total_notional_per_symbol = 300
allow_one_share_high_price_probe = true
ladder_cooldown_minutes = 7
max_active_symbols_per_open = 2
minimum_opening_score = 0.0
use_ranked_symbol_selection = true
holding_period_bars = 5
estimated_cost_bps = 5.0
blotter_path = "{paths["blotter"]}"
summary_path = "{paths["summary"]}"
opening_warmup_blotter_path = "{paths["warmup"]}"
opening_warmup_summary_path = "{paths["warmup_summary"]}"
opening_diagnostics_path = "{paths["diagnostics"]}"
opening_vs_allday_comparison_path = "{paths["comparison"]}"
opening_ladder_blotter_path = "{paths["ladder"]}"
opening_ladder_summary_path = "{paths["ladder_summary"]}"
opening_strategy_comparison_path = "{paths["strategy_comparison"]}"
opening_ladder_family_summary_path = "{paths["ladder_family_summary"]}"
opening_ladder_symbol_assessment_path = "{paths["ladder_symbol_assessment"]}"
opening_primary_comparison_path = "{paths["primary_comparison"]}"
opening_extended_benchmark_comparison_path = "{paths["extended_benchmark_comparison"]}"
opening_pair_trade_experiment_path = "{paths["pair_trade_experiment"]}"
""".strip(),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "simulate_l2_trades.py",
            "--config",
            str(config),
            "--features",
            str(features),
            "--setups",
            str(setups),
            "--report-version",
            "legacy_high_pnl",
            "--report-versions-dir",
            str(tmp_path / "versions"),
        ],
    )

    assert simulate_l2_trades.main() == 0
    warmup = pd.read_csv(paths["warmup"])
    assert len(warmup) == 1
    assert "active" not in warmup.columns
    assert "live" not in warmup.columns
    assert paths["comparison"].exists()
    comparison = pd.read_csv(paths["comparison"])
    assert comparison["mode"].tolist() == ["opening_warmup_only", "all_day_repeated_entries"]
    assert paths["ladder"].exists()
    ladder = pd.read_csv(paths["ladder"])
    assert "sizing_mode" in ladder.columns
    assert paths["ladder_summary"].exists()
    assert paths["ladder_family_summary"].exists()
    assert paths["ladder_symbol_assessment"].exists()
    assert paths["primary_comparison"].exists()
    assert paths["extended_benchmark_comparison"].exists()
    assert paths["pair_trade_experiment"].exists()
    primary = pd.read_csv(paths["primary_comparison"])
    assert primary["mode"].tolist() == ["single_opening_teaser", "ranked_opening_ladder"]
    strategy_comparison = pd.read_csv(paths["strategy_comparison"])
    assert strategy_comparison["mode"].tolist() == [
        "single_opening_teaser",
        "opening_ladder",
        "all_day_repeated_entries",
    ]
    assert (tmp_path / "versions" / "legacy_high_pnl_ladder_summary.csv").exists()
    assert (tmp_path / "versions" / "legacy_high_pnl_strategy_comparison.csv").exists()
    assert (tmp_path / "versions" / "legacy_high_pnl_family_summary.csv").exists()
