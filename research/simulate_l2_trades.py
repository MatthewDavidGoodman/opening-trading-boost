#!/usr/bin/env python3
from __future__ import annotations

import argparse
import tomllib
from pathlib import Path

import pandas as pd

from opening_trading_boost.l2_simulation import (
    OpeningLadderConfig,
    build_opening_extended_benchmark_comparison,
    build_opening_ladder_symbol_assessment,
    build_opening_pair_trade_experiment,
    build_opening_primary_comparison,
    build_opening_strategy_comparison,
    build_opening_vs_allday_comparison,
    build_opening_diagnostics,
    filter_opening_warmup_trades,
    simulate_l2_trades,
    simulate_opening_ladder,
    simulate_extended_opening_benchmark,
    summarize_l2_trades,
    summarize_opening_ladder,
    summarize_opening_ladder_families,
    summarize_opening_warmup,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Simulate conservative paper-only L2 fills.")
    parser.add_argument("--config", default="config/databento_l2.example.toml")
    parser.add_argument("--features", default="data/features/l2_features.csv")
    parser.add_argument("--setups", default="data/reports/l2_setup_occurrences.csv")
    parser.add_argument("--blotter-out")
    parser.add_argument("--summary-out")
    parser.add_argument("--report-version")
    parser.add_argument("--report-versions-dir", default="data/reports/versions")
    args = parser.parse_args()

    raw_config = tomllib.loads(Path(args.config).read_text(encoding="utf-8"))
    config = raw_config["simulation"]
    setup_config = raw_config.get("l2_setups", {})
    if config.get("session_focus", "opening_ladder") not in {"opening_warmup", "opening_ladder"}:
        raise ValueError("simulation.session_focus must be 'opening_ladder' or 'opening_warmup'")
    occurrences = pd.read_csv(args.setups)
    features = pd.read_csv(args.features)
    blotter = simulate_l2_trades(
        features=features,
        occurrences=occurrences,
        holding_period_bars=int(config["holding_period_bars"]),
        estimated_cost_bps=float(config["estimated_cost_bps"]),
    )
    summary = summarize_l2_trades(blotter)
    diagnostics = build_opening_diagnostics(
        occurrences,
        warmup_start_et=str(config["warmup_start_et"]),
        warmup_end_et=str(config["warmup_end_et"]),
        max_spread_bps=float(setup_config.get("max_spread_bps", 100.0)),
        min_depth_10=float(setup_config.get("min_depth_10", 100.0)),
        min_imbalance_10=float(setup_config.get("min_imbalance_10", 0.10)),
    )
    warmup_blotter = filter_opening_warmup_trades(
        blotter,
        warmup_start_et=str(config["warmup_start_et"]),
        warmup_end_et=str(config["warmup_end_et"]),
        max_warmup_trades_per_symbol=int(config.get("max_warmup_trades_per_symbol", 1)),
        max_warmup_notional=float(config.get("max_warmup_notional", 300)),
        max_spread_bps=float(setup_config.get("max_spread_bps", 100.0)),
        min_depth_10=float(setup_config.get("min_depth_10", 100.0)),
        min_imbalance_10=float(setup_config.get("min_imbalance_10", 0.10)),
    )
    warmup_summary = summarize_opening_warmup(warmup_blotter, diagnostics)
    comparison = build_opening_vs_allday_comparison(warmup_blotter, blotter)
    ladder_config = OpeningLadderConfig(
            warmup_start_et=str(config["warmup_start_et"]),
            warmup_end_et=str(config["warmup_end_et"]),
            extended_opening_benchmark_start_et=str(
                config.get("extended_opening_benchmark_start_et", "09:30")
            ),
            extended_opening_benchmark_end_et=str(
                config.get("extended_opening_benchmark_end_et", "10:30")
            ),
            max_ladder_probes_per_symbol=int(config.get("max_ladder_probes_per_symbol", 2)),
            ladder_probe_notional=float(config.get("ladder_probe_notional", 50)),
            max_ladder_single_probe_notional=float(
                config.get("max_ladder_single_probe_notional", 150)
            ),
            max_ladder_total_notional_per_symbol=float(
                config.get("max_ladder_total_notional_per_symbol", 300)
            ),
            allow_one_share_high_price_probe=bool(
                config.get("allow_one_share_high_price_probe", True)
            ),
            ladder_cooldown_minutes=float(config.get("ladder_cooldown_minutes", 7)),
            max_active_symbols_per_open=int(config.get("max_active_symbols_per_open", 2)),
            minimum_opening_score=float(config.get("minimum_opening_score", 0.0)),
            use_ranked_symbol_selection=bool(config.get("use_ranked_symbol_selection", True)),
            holding_period_bars=int(config["holding_period_bars"]),
            estimated_cost_bps=float(config["estimated_cost_bps"]),
            max_spread_bps=float(setup_config.get("max_spread_bps", 100.0)),
            min_depth_10=float(setup_config.get("min_depth_10", 100.0)),
            min_imbalance_10=float(setup_config.get("min_imbalance_10", 0.10)),
            min_total_depth_10=float(setup_config.get("min_total_depth_10", 500)),
            min_trade_count=int(setup_config.get("min_trade_count", 10)),
            min_trade_volume=float(setup_config.get("min_trade_volume", 1000)),
            microprice_tolerance_bps=float(
                setup_config.get("microprice_tolerance_bps", 2.0)
            ),
            spread_compression_lookback=int(
                setup_config.get("spread_compression_lookback", 5)
            ),
            allow_spread_compression_setup=bool(
                setup_config.get("allow_spread_compression_setup", True)
            ),
            allow_pullback_reclaim_setup=bool(
                setup_config.get("allow_pullback_reclaim_setup", True)
            ),
            allow_imbalance_setup=bool(setup_config.get("allow_imbalance_setup", True)),
        )
    ladder_blotter = simulate_opening_ladder(features, ladder_config)
    extended_ladder_blotter = simulate_extended_opening_benchmark(features, ladder_config)
    ladder_summary = summarize_opening_ladder(ladder_blotter)
    ladder_family_summary = summarize_opening_ladder_families(ladder_blotter)
    ladder_symbol_assessment = build_opening_ladder_symbol_assessment(features, ladder_blotter)
    primary_comparison = build_opening_primary_comparison(warmup_blotter, ladder_blotter)
    extended_benchmark_comparison = build_opening_extended_benchmark_comparison(
        extended_ladder_blotter, blotter
    )
    pair_trade_experiment = build_opening_pair_trade_experiment(features, ladder_config)
    strategy_comparison = build_opening_strategy_comparison(
        warmup_blotter, ladder_blotter, blotter
    )
    blotter_path = Path(
        args.blotter_out or config.get("blotter_path", "data/reports/l2_trade_blotter.csv")
    )
    summary_path = Path(
        args.summary_out or config.get("summary_path", "data/reports/l2_performance_summary.csv")
    )
    warmup_blotter_path = Path(
        config.get("opening_warmup_blotter_path", "data/reports/l2_opening_warmup_blotter.csv")
    )
    warmup_summary_path = Path(
        config.get("opening_warmup_summary_path", "data/reports/l2_opening_warmup_summary.csv")
    )
    diagnostics_path = Path(
        config.get("opening_diagnostics_path", "data/reports/l2_opening_diagnostics.csv")
    )
    comparison_path = Path(
        config.get(
            "opening_vs_allday_comparison_path",
            "data/reports/l2_opening_vs_allday_comparison.csv",
        )
    )
    ladder_blotter_path = Path(
        config.get("opening_ladder_blotter_path", "data/reports/l2_opening_ladder_blotter.csv")
    )
    ladder_summary_path = Path(
        config.get("opening_ladder_summary_path", "data/reports/l2_opening_ladder_summary.csv")
    )
    strategy_comparison_path = Path(
        config.get(
            "opening_strategy_comparison_path",
            "data/reports/l2_opening_strategy_comparison.csv",
        )
    )
    ladder_family_summary_path = Path(
        config.get(
            "opening_ladder_family_summary_path",
            "data/reports/l2_opening_ladder_family_summary.csv",
        )
    )
    ladder_symbol_assessment_path = Path(
        config.get(
            "opening_ladder_symbol_assessment_path",
            "data/reports/l2_opening_ladder_symbol_assessment.csv",
        )
    )
    primary_comparison_path = Path(
        config.get(
            "opening_primary_comparison_path",
            "data/reports/l2_opening_primary_comparison.csv",
        )
    )
    extended_benchmark_comparison_path = Path(
        config.get(
            "opening_extended_benchmark_comparison_path",
            "data/reports/l2_opening_extended_benchmark_comparison.csv",
        )
    )
    pair_trade_experiment_path = Path(
        config.get(
            "opening_pair_trade_experiment_path",
            "data/reports/l2_opening_pair_trade_experiment.csv",
        )
    )
    for path in (
        blotter_path,
        summary_path,
        warmup_blotter_path,
        warmup_summary_path,
        diagnostics_path,
        comparison_path,
        ladder_blotter_path,
        ladder_summary_path,
        strategy_comparison_path,
        ladder_family_summary_path,
        ladder_symbol_assessment_path,
        primary_comparison_path,
        extended_benchmark_comparison_path,
        pair_trade_experiment_path,
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
    blotter.to_csv(blotter_path, index=False)
    summary.to_csv(summary_path, index=False)
    warmup_blotter.to_csv(warmup_blotter_path, index=False)
    warmup_summary.to_csv(warmup_summary_path, index=False)
    diagnostics.to_csv(diagnostics_path, index=False)
    comparison.to_csv(comparison_path, index=False)
    ladder_blotter.to_csv(ladder_blotter_path, index=False)
    ladder_summary.to_csv(ladder_summary_path, index=False)
    strategy_comparison.to_csv(strategy_comparison_path, index=False)
    ladder_family_summary.to_csv(ladder_family_summary_path, index=False)
    ladder_symbol_assessment.to_csv(ladder_symbol_assessment_path, index=False)
    primary_comparison.to_csv(primary_comparison_path, index=False)
    extended_benchmark_comparison.to_csv(extended_benchmark_comparison_path, index=False)
    pair_trade_experiment.to_csv(pair_trade_experiment_path, index=False)
    if args.report_version:
        version_dir = Path(args.report_versions_dir)
        version_dir.mkdir(parents=True, exist_ok=True)
        version_outputs = {
            f"{args.report_version}_ladder_summary.csv": ladder_summary,
            f"{args.report_version}_strategy_comparison.csv": strategy_comparison,
            f"{args.report_version}_family_summary.csv": ladder_family_summary,
        }
        for filename, report in version_outputs.items():
            version_path = version_dir / filename
            report.to_csv(version_path, index=False)
            print(f"wrote {version_path} rows={len(report)}")
    print(f"wrote {blotter_path} rows={len(blotter)}")
    print(f"wrote {summary_path} rows={len(summary)}")
    print(f"wrote {warmup_blotter_path} rows={len(warmup_blotter)}")
    print(f"wrote {warmup_summary_path} rows={len(warmup_summary)}")
    print(f"wrote {diagnostics_path} rows={len(diagnostics)}")
    print(f"wrote {comparison_path} rows={len(comparison)}")
    print(f"wrote {ladder_blotter_path} rows={len(ladder_blotter)}")
    print(f"wrote {ladder_summary_path} rows={len(ladder_summary)}")
    print(f"wrote {strategy_comparison_path} rows={len(strategy_comparison)}")
    print(f"wrote {ladder_family_summary_path} rows={len(ladder_family_summary)}")
    print(f"wrote {ladder_symbol_assessment_path} rows={len(ladder_symbol_assessment)}")
    print(f"wrote {primary_comparison_path} rows={len(primary_comparison)}")
    print(f"wrote {extended_benchmark_comparison_path} rows={len(extended_benchmark_comparison)}")
    print(f"wrote {pair_trade_experiment_path} rows={len(pair_trade_experiment)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
