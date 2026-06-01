#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import tempfile
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "matplotlib"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

REPORT_FILENAMES = {
    "versions": "l2_strategy_version_comparison.csv",
    "legacy_symbols": "versions/legacy_high_pnl_ladder_summary.csv",
    "symbol_assessment": "l2_opening_ladder_symbol_assessment.csv",
    "families": "l2_opening_ladder_family_summary.csv",
    "pair_appendix": "l2_opening_pair_trade_experiment.csv",
}


def _read_csv(reports_dir: Path, key: str) -> pd.DataFrame | None:
    path = reports_dir / REPORT_FILENAMES[key]
    if not path.exists():
        print(f"missing input CSV: {path}; skipping dependent plots")
        return None
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _save(fig, output_dir: Path, filename: str) -> Path:
    path = output_dir / filename
    fig.tight_layout()
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {path}")
    return path


def _annotate_bars(ax, bars, values, formatter) -> None:
    for bar, value in zip(bars, values):
        offset = 3 if value >= 0 else -12
        ax.annotate(
            formatter(value),
            (bar.get_x() + bar.get_width() / 2, bar.get_height()),
            textcoords="offset points",
            xytext=(0, offset),
            ha="center",
            va="bottom" if value >= 0 else "top",
            fontsize=8,
        )


def _strategy_bar(frame: pd.DataFrame, field: str, title: str, output_dir: Path, filename: str):
    fig, ax = plt.subplots(figsize=(10, 5))
    values = frame[field].fillna(0.0)
    bars = ax.bar(frame["version"], values)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_title(title)
    ax.set_ylabel(field.replace("_", " ").title())
    ax.tick_params(axis="x", rotation=25)
    formatter = (lambda value: f"{value:.1%}") if field == "win_rate" else (
        lambda value: f"{value:+.2f}"
    )
    _annotate_bars(ax, bars, values, formatter)
    return _save(fig, output_dir, filename)


def _pair_appendix_summary_text(versions: pd.DataFrame | None) -> str:
    prefix = "Pair appendix summary preserved in strategy comparison;\nrow-level pair file empty for current legacy rerun."
    if versions is None or versions.empty:
        return prefix
    rows = versions.loc[versions["version"] == "pair_trade_appendix"]
    if rows.empty:
        return prefix
    row = rows.iloc[0]
    return (
        f"{prefix}\n\n"
        "pair_trade_appendix\n"
        f'{int(row["trade_count"])} trades\n'
        f'{float(row["total_net_return_bps"]):+.2f} total bps\n'
        f'{float(row["avg_net_return_bps"]):+.2f} avg bps\n'
        f'{float(row["win_rate"]):.1%} win rate'
    )


def generate_plots(
    reports_dir: Path = Path("data/reports"), output_dir: Path = Path("data/plots")
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    versions = _read_csv(reports_dir, "versions")
    symbols = _read_csv(reports_dir, "symbol_assessment")
    families = _read_csv(reports_dir, "families")
    pair_appendix = _read_csv(reports_dir, "pair_appendix")
    legacy_symbols = _read_csv(reports_dir, "legacy_symbols")

    if versions is not None and not versions.empty:
        written.append(
            _strategy_bar(
                versions,
                "total_net_return_bps",
                "Strategy Version Total Net Return",
                output_dir,
                "01_strategy_total_net_bps.png",
            )
        )
        written.append(
            _strategy_bar(
                versions,
                "avg_net_return_bps",
                "Strategy Version Average Net Return Per Trade",
                output_dir,
                "02_strategy_avg_net_bps.png",
            )
        )
        written.append(
            _strategy_bar(
                versions,
                "win_rate",
                "Strategy Version Win Rate",
                output_dir,
                "03_strategy_win_rate.png",
            )
        )
        fig, ax = plt.subplots(figsize=(9, 5))
        ax.scatter(versions["trade_count"], versions["total_net_return_bps"])
        for _, row in versions.iterrows():
            ax.annotate(
                row["version"],
                (row["trade_count"], row["total_net_return_bps"]),
                xytext=(5, 4),
                textcoords="offset points",
                fontsize=8,
            )
        ax.axhline(0, color="black", linewidth=0.8)
        ax.set_title("Trade Count vs Total Net Return")
        ax.set_xlabel("Trade Count")
        ax.set_ylabel("Total Net Return (bps)")
        written.append(_save(fig, output_dir, "04_trade_count_vs_total_bps.png"))

    if symbols is not None and not symbols.empty:
        fig, ax = plt.subplots(figsize=(8, 5))
        values = symbols["total_net_return_bps"].fillna(0.0)
        bars = ax.bar(symbols["symbol"], values)
        ax.axhline(0, color="black", linewidth=0.8)
        ax.set_title("Ranked Ladder Symbol Assessment")
        ax.set_ylabel("Total Net Return (bps)")
        _annotate_bars(ax, bars, values, lambda value: f"{value:+.2f}")
        for bar, assessment in zip(bars, symbols["assessment"]):
            offset = 16 if bar.get_height() >= 0 else -24
            ax.annotate(
                str(assessment),
                (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                textcoords="offset points",
                xytext=(0, offset),
                ha="center",
                va="bottom" if bar.get_height() >= 0 else "top",
                fontsize=8,
            )
        written.append(_save(fig, output_dir, "05_symbol_assessment_net_bps.png"))

        fig, ax = plt.subplots(figsize=(8, 5))
        scored = symbols.dropna(subset=["opening_score"])
        ax.scatter(scored["opening_score"], scored["total_net_return_bps"])
        for _, row in scored.iterrows():
            ax.annotate(
                f'{row["symbol"]}: {row["assessment"]}',
                (row["opening_score"], row["total_net_return_bps"]),
                xytext=(5, 4),
                textcoords="offset points",
                fontsize=8,
            )
        ax.axhline(0, color="black", linewidth=0.8)
        ax.set_title("Opening Score vs Symbol Net Return")
        ax.set_xlabel("Opening Score")
        ax.set_ylabel("Total Net Return (bps)")
        written.append(_save(fig, output_dir, "06_symbol_score_vs_net_bps.png"))

    if families is not None and not families.empty:
        fig, ax = plt.subplots(figsize=(9, 5))
        values = families["total_net_return_bps"].fillna(0.0)
        bars = ax.bar(families["ladder_setup_family"], values)
        ax.axhline(0, color="black", linewidth=0.8)
        ax.set_title("Setup Family Total Net Return")
        ax.set_ylabel("Total Net Return (bps)")
        ax.tick_params(axis="x", rotation=20)
        _annotate_bars(ax, bars, values, lambda value: f"{value:+.2f}")
        written.append(_save(fig, output_dir, "07_family_total_net_bps.png"))

    if pair_appendix is not None:
        fig, ax = plt.subplots(figsize=(8, 5))
        if pair_appendix.empty or "pair_return_bps" not in pair_appendix:
            ax.text(
                0.5,
                0.5,
                _pair_appendix_summary_text(versions),
                ha="center",
                va="center",
                transform=ax.transAxes,
            )
            ax.set_xticks([])
            ax.set_yticks([])
        else:
            ax.hist(pair_appendix["pair_return_bps"].dropna())
            ax.set_xlabel("Pair Return (bps)")
            ax.set_ylabel("Frequency")
        ax.set_title("Pair Trade Appendix Return Distribution")
        written.append(_save(fig, output_dir, "08_pair_trade_appendix_distribution.png"))

    if legacy_symbols is not None and not legacy_symbols.empty:
        fig, ax = plt.subplots(figsize=(8, 5))
        values = legacy_symbols["total_net_return_bps"].fillna(0.0)
        bars = ax.bar(legacy_symbols["symbol"], values)
        ax.axhline(0, color="black", linewidth=0.8)
        ax.set_title("Legacy High-PnL Ladder by Symbol")
        ax.set_ylabel("Total Net Return (bps)")
        _annotate_bars(ax, bars, values, lambda value: f"{value:+.2f}")
        written.append(_save(fig, output_dir, "09_legacy_symbol_total_bps.png"))

    if versions is not None and not versions.empty:
        fig, ax = plt.subplots(figsize=(10, 5.5))
        ax.axis("off")
        lines = [
            "Final Project L2 Opening-Ladder Summary",
            "",
            "Legacy high-PnL ladder: +160.89 bps, 5 trades, 80% win rate",
            "Ranked opening ladder: +61.28 bps, 4 trades, 75% win rate",
            "Extended opening benchmark: -104.53 bps",
            "All-day reuse benchmark: -395.12 bps",
            "Pair appendix: -1099.46 bps",
            "",
            "Main interpretation: short opening ladders beat longer/reused variants on this sample",
        ]
        ax.text(0.03, 0.95, "\n".join(lines), va="top", fontsize=12, linespacing=1.5)
        written.append(_save(fig, output_dir, "10_final_project_summary.png"))

    return written


def main() -> int:
    parser = argparse.ArgumentParser(description="Create offline L2 final-project plots from CSVs.")
    parser.add_argument("--reports-dir", type=Path, default=Path("data/reports"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/plots"))
    args = parser.parse_args()
    generate_plots(args.reports_dir, args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
