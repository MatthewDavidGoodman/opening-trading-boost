from datetime import datetime, timezone
from pathlib import Path

from ibkr_microexec.config import load_plan
from ibkr_microexec.timegate import is_window_open

ROOT = Path(__file__).resolve().parents[1]


def test_time_window_open_on_monday_morning():
    plan = load_plan(ROOT / "config" / "trading_plan.example.toml")
    when = datetime(2026, 5, 18, 13, 50, tzinfo=timezone.utc)
    assert is_window_open(plan.windows["morning_confirmed"], when)


def test_time_window_closed_on_saturday():
    plan = load_plan(ROOT / "config" / "trading_plan.example.toml")
    when = datetime(2026, 5, 23, 13, 50, tzinfo=timezone.utc)
    assert not is_window_open(plan.windows["morning_confirmed"], when)
