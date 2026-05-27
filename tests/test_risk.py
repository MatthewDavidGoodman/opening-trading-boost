from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from ibkr_microexec.config import load_plan
from ibkr_microexec.models import Position, Quote, TradeIntent
from ibkr_microexec.risk import evaluate_intent

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "trading_plan.example.toml"


def _plan():
    return load_plan(CONFIG)


def _when_window_open() -> datetime:
    # Monday, May 18 2026, 13:50 UTC = 09:50 America/New_York.
    return datetime(2026, 5, 18, 13, 50, tzinfo=timezone.utc)


def _quote(symbol: str = "EXAMPLE") -> Quote:
    return Quote(
        symbol=symbol,
        bid=Decimal("10.00"),
        ask=Decimal("10.02"),
        bid_size=100,
        ask_size=100,
    )


def _intent(**kwargs) -> TradeIntent:
    data = {
        "symbol": "EXAMPLE",
        "side": "BUY",
        "quantity": 1,
        "limit_price": Decimal("10.01"),
        "window": "morning_confirmed",
        "active": True,
        "client_tag": "unit_test",
        "notes": "",
    }
    data.update(kwargs)
    return TradeIntent(**data)


def test_approves_small_active_allowlisted_limit_order_inside_window():
    decision = evaluate_intent(_plan(), _intent(), _quote(), when_utc=_when_window_open())
    assert decision.approved
    assert decision.order is not None


def test_rejects_inactive_intent():
    decision = evaluate_intent(
        _plan(), _intent(active=False), _quote(), when_utc=_when_window_open()
    )
    assert not decision.approved
    assert "intent_inactive" in decision.reasons


def test_rejects_unknown_symbol():
    decision = evaluate_intent(_plan(), _intent(symbol="NOPE"), None, when_utc=_when_window_open())
    assert not decision.approved
    assert "symbol_not_allowlisted" in decision.reasons


def test_rejects_outside_window():
    saturday = datetime(2026, 5, 23, 13, 50, tzinfo=timezone.utc)
    decision = evaluate_intent(_plan(), _intent(), _quote(), when_utc=saturday)
    assert not decision.approved
    assert "outside_allowed_time_window" in decision.reasons


def test_rejects_wide_spread():
    quote = Quote(
        symbol="EXAMPLE",
        bid=Decimal("10.00"),
        ask=Decimal("10.50"),
        bid_size=100,
        ask_size=100,
    )
    decision = evaluate_intent(_plan(), _intent(), quote, when_utc=_when_window_open())
    assert not decision.approved
    assert "spread_too_wide" in decision.reasons


def test_rejects_too_large_order_notional():
    decision = evaluate_intent(
        _plan(),
        _intent(quantity=10, limit_price=Decimal("10.00")),
        _quote(),
        when_utc=_when_window_open(),
    )
    assert not decision.approved
    assert "exceeds_symbol_max_order_shares" in decision.reasons
    assert "exceeds_symbol_max_order_notional" in decision.reasons


def test_rejects_short_sell_when_not_held():
    decision = evaluate_intent(
        _plan(), _intent(side="SELL"), _quote(), positions={}, when_utc=_when_window_open()
    )
    assert not decision.approved
    assert "short_position_not_allowed" in decision.reasons


def test_allows_sell_when_position_exists():
    decision = evaluate_intent(
        _plan(),
        _intent(side="SELL"),
        _quote(),
        positions={"EXAMPLE": Position("EXAMPLE", quantity=2, avg_price=Decimal("10"))},
        when_utc=_when_window_open(),
    )
    assert decision.approved
