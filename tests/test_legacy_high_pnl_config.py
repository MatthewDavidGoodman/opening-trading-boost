from __future__ import annotations

import tomllib
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "databento_l2.legacy_high_pnl.example.toml"
COMPARISON = ROOT / "data" / "reports" / "l2_strategy_version_comparison.csv"


def _config() -> dict:
    return tomllib.loads(CONFIG.read_text(encoding="utf-8"))


def test_legacy_config_disables_ranked_selection():
    assert _config()["simulation"]["use_ranked_symbol_selection"] is False


def test_legacy_config_disables_one_share_high_price_probes():
    assert _config()["simulation"]["allow_one_share_high_price_probe"] is False


def test_legacy_config_uses_0930_to_1030_window():
    simulation = _config()["simulation"]

    assert simulation["warmup_start_et"] == "09:30"
    assert simulation["warmup_end_et"] == "10:30"


def test_legacy_config_permits_imbalance_setup_only():
    setups = _config()["l2_setups"]

    assert setups["allow_imbalance_setup"] is True
    assert setups["allow_spread_compression_setup"] is False
    assert setups["allow_pullback_reclaim_setup"] is False


def test_strategy_version_comparison_includes_legacy_high_pnl_ladder():
    comparison = pd.read_csv(COMPARISON)

    assert "legacy_high_pnl_ladder" in set(comparison["version"])
