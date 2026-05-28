from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from research import export_trade_intents_from_setups

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "meme_stock_trading_plan.example.toml"


def _write_setups(path: Path, rows: list[dict[str, object]]) -> None:
    pd.DataFrame(rows).to_csv(path, index=False)


def _setup_row(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "setup_id": "BBAI_AI_DEFENSE_MOMENTUM",
        "symbol": "BBAI",
        "family": "momentum_continuation_long",
        "setup_name": "AI-defense momentum continuation",
        "research_side": "BUY",
        "live_side_allowed": "BUY",
        "datetime": "2026-04-17 14:35:00+00:00",
        "entry_window_et": "10:00-11:30",
        "exit_window_et": "15:30-15:55",
        "last_price": 4.385,
        "setup_score": 4.2,
        "quantity_paper": 91,
        "quantity_live_cap": 45,
        "thesis": "",
        "entry_rule_plain": "",
        "exit_rule_plain": "",
        "ml_question": "",
        "ret_1": 0,
        "ret_3": 0,
        "ret_12": 0,
        "range_bps": 0,
        "rel_volume_20": 1,
        "realized_vol_20": 0,
        "close_vs_sma20_bps": 0,
        "forward_return": 0,
        "label_forward_up": 0,
    }
    data.update(overrides)
    return data


def _run_export(
    monkeypatch,
    setup_csv: Path,
    out_csv: Path,
    rejections_csv: Path,
    config: Path = CONFIG,
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "export_trade_intents_from_setups.py",
            "--setup-occurrences",
            str(setup_csv),
            "--out",
            str(out_csv),
            "--rejections-out",
            str(rejections_csv),
            "--config",
            str(config),
            "--max-rows",
            "10",
        ],
    )
    assert export_trade_intents_from_setups.main() == 0


def test_export_caps_quantity_to_symbol_and_notional_limits(tmp_path, monkeypatch):
    setup_csv = tmp_path / "setups.csv"
    out_csv = tmp_path / "intents.csv"
    rejections_csv = tmp_path / "rejections.csv"
    _write_setups(setup_csv, [_setup_row()])

    _run_export(monkeypatch, setup_csv, out_csv, rejections_csv)

    intents = pd.read_csv(out_csv)
    assert intents.loc[0, "symbol"] == "BBAI"
    assert intents.loc[0, "quantity"] == 6
    assert float(intents.loc[0, "quantity"]) * float(intents.loc[0, "limit_price"]) <= 60


def test_export_skips_zero_quantity_and_writes_rejection(tmp_path, monkeypatch):
    setup_csv = tmp_path / "setups.csv"
    out_csv = tmp_path / "intents.csv"
    rejections_csv = tmp_path / "rejections.csv"
    config = tmp_path / "tiny_gross.toml"
    config.write_text(
        CONFIG.read_text(encoding="utf-8").replace(
            "max_gross_notional = 3000.00", "max_gross_notional = 5.00"
        ),
        encoding="utf-8",
    )
    _write_setups(
        setup_csv,
        [_setup_row(symbol="SOUN", setup_id="SOUN_OPEN_RECLAIM", last_price=8.325)],
    )

    _run_export(monkeypatch, setup_csv, out_csv, rejections_csv, config=config)

    assert pd.read_csv(out_csv).empty
    rejections = pd.read_csv(rejections_csv)
    assert rejections.loc[0, "symbol"] == "SOUN"
    assert "capped_account_max_gross_notional" in rejections.loc[0, "reason"]


def test_export_always_writes_inactive_intents(tmp_path, monkeypatch):
    setup_csv = tmp_path / "setups.csv"
    out_csv = tmp_path / "intents.csv"
    rejections_csv = tmp_path / "rejections.csv"
    _write_setups(setup_csv, [_setup_row()])

    _run_export(monkeypatch, setup_csv, out_csv, rejections_csv)

    intents = pd.read_csv(out_csv)
    assert intents["active"].astype(str).str.lower().tolist() == ["false"]


def test_export_excludes_none_side_rows(tmp_path, monkeypatch):
    setup_csv = tmp_path / "setups.csv"
    out_csv = tmp_path / "intents.csv"
    rejections_csv = tmp_path / "rejections.csv"
    _write_setups(
        setup_csv,
        [
            _setup_row(),
            _setup_row(
                setup_id="KOSS_LIQUIDITY_REJECT",
                symbol="KOSS",
                research_side="NONE",
                live_side_allowed="BUY",
                setup_score=99,
                quantity_paper=10,
                last_price=4.25,
            ),
        ],
    )

    _run_export(monkeypatch, setup_csv, out_csv, rejections_csv)

    intents = pd.read_csv(out_csv)
    assert intents["symbol"].tolist() == ["BBAI"]
