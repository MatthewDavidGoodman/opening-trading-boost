from __future__ import annotations

from pathlib import Path

import pandas as pd

from research import download_databento_l2, make_l2_output_plots


def _write_fixture_reports(reports: Path, empty_pair_appendix: bool = False) -> None:
    (reports / "versions").mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "version": "legacy_high_pnl_ladder",
                "trade_count": 5,
                "avg_net_return_bps": 32.18,
                "total_net_return_bps": 160.89,
                "win_rate": 0.8,
            },
            {
                "version": "ranked_opening_ladder",
                "trade_count": 4,
                "avg_net_return_bps": 15.32,
                "total_net_return_bps": 61.28,
                "win_rate": 0.75,
            },
            {
                "version": "pair_trade_appendix",
                "trade_count": 13,
                "avg_net_return_bps": -84.57,
                "total_net_return_bps": -1099.46,
                "win_rate": 0.154,
            },
        ]
    ).to_csv(reports / "l2_strategy_version_comparison.csv", index=False)
    pd.DataFrame(
        [
            {
                "symbol": "SOUN",
                "opening_score": 10.0,
                "assessment": "tradable_today",
                "total_net_return_bps": 61.08,
            },
            {
                "symbol": "RKLB",
                "opening_score": None,
                "assessment": "qualified_but_not_selected",
                "total_net_return_bps": 0.0,
            },
        ]
    ).to_csv(reports / "l2_opening_ladder_symbol_assessment.csv", index=False)
    pd.DataFrame(
        [
            {
                "ladder_setup_family": "OPENING_LADDER_IMBALANCE_LONG",
                "total_net_return_bps": 61.08,
            }
        ]
    ).to_csv(reports / "l2_opening_ladder_family_summary.csv", index=False)
    pd.DataFrame(
        [
            {"symbol": "RIVN", "total_net_return_bps": 99.81},
            {"symbol": "SOUN", "total_net_return_bps": 61.08},
            {"symbol": "RKLB", "total_net_return_bps": 0.0},
        ]
    ).to_csv(reports / "versions" / "legacy_high_pnl_ladder_summary.csv", index=False)
    pair_rows = [] if empty_pair_appendix else [{"pair_return_bps": -10.0}, {"pair_return_bps": 5.0}]
    pd.DataFrame(pair_rows, columns=["pair_return_bps"]).to_csv(
        reports / "l2_opening_pair_trade_experiment.csv", index=False
    )


def test_plotting_script_runs_with_minimal_fixture_csvs(tmp_path):
    reports = tmp_path / "reports"
    plots = tmp_path / "plots"
    _write_fixture_reports(reports)

    written = make_l2_output_plots.generate_plots(reports, plots)

    assert len(written) == 10
    assert all(path.exists() for path in written)


def test_plotting_script_handles_empty_pair_trade_csv(tmp_path):
    reports = tmp_path / "reports"
    plots = tmp_path / "plots"
    _write_fixture_reports(reports, empty_pair_appendix=True)

    written = make_l2_output_plots.generate_plots(reports, plots)

    assert plots / "08_pair_trade_appendix_distribution.png" in written


def test_empty_pair_plot_uses_preserved_strategy_comparison_summary():
    versions = pd.DataFrame(
        [
            {
                "version": "pair_trade_appendix",
                "trade_count": 13,
                "avg_net_return_bps": -84.57,
                "total_net_return_bps": -1099.46,
                "win_rate": 0.154,
            }
        ]
    )

    text = make_l2_output_plots._pair_appendix_summary_text(versions)

    assert "row-level pair file empty for current legacy rerun" in text
    assert "13 trades" in text
    assert "-1099.46 total bps" in text
    assert "-84.57 avg bps" in text
    assert "15.4% win rate" in text


def test_results_memo_is_generated():
    memo = Path(__file__).resolve().parents[1] / "docs" / "l2_results_memo.md"

    assert memo.exists()
    assert "# Ranked Opening Ladder Results Memo" in memo.read_text(encoding="utf-8")


def test_plotting_script_requires_no_databento_call(tmp_path, monkeypatch):
    reports = tmp_path / "reports"
    plots = tmp_path / "plots"
    _write_fixture_reports(reports, empty_pair_appendix=True)

    def reject_call(*_args, **_kwargs):
        raise AssertionError("offline plotting attempted a Databento call")

    monkeypatch.setattr(download_databento_l2, "download", reject_call)

    assert len(make_l2_output_plots.generate_plots(reports, plots)) == 10


def test_plotting_script_is_offline_only(tmp_path):
    reports = tmp_path / "reports"
    plots = tmp_path / "plots"
    _write_fixture_reports(reports, empty_pair_appendix=True)

    assert len(make_l2_output_plots.generate_plots(reports, plots)) == 10
