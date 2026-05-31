from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from ibkr_microexec.l2_features import (
    build_l2_features_for_frame,
    calculate_imbalance,
    calculate_microprice,
)
from ibkr_microexec.l2_setups import L2SetupConfig, detect_l2_setups
from ibkr_microexec.l2_simulation import simulate_long_fill
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
