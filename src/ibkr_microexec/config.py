from __future__ import annotations

import tomllib
from dataclasses import dataclass
from datetime import time
from decimal import Decimal
from pathlib import Path
from typing import Any

from .models import Environment

_DAY_ALIASES = {"Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"}


@dataclass(frozen=True)
class IBKRConfig:
    host: str
    paper_port: int
    live_port: int
    client_id: int
    account: str
    readonly_market_data: bool

    def port_for(self, environment: Environment) -> int:
        return self.live_port if environment == "live" else self.paper_port


@dataclass(frozen=True)
class RuntimeConfig:
    environment: Environment
    live_enabled: bool
    kill_switch_file: Path
    log_dir: Path


@dataclass(frozen=True)
class BudgetConfig:
    max_gross_notional: Decimal
    max_single_order_notional: Decimal
    max_daily_trades: int
    min_cash_reserve: Decimal
    allow_short: bool


@dataclass(frozen=True)
class OrderConfig:
    order_type: str
    time_in_force: str
    outside_regular_trading_hours: bool
    require_quote: bool
    send_by_default: bool


@dataclass(frozen=True)
class TimeWindow:
    name: str
    timezone: str
    start: time
    end: time
    days: tuple[str, ...]


@dataclass(frozen=True)
class TickerRule:
    symbol: str
    exchange: str
    currency: str
    max_position_shares: int
    max_order_shares: int
    max_order_notional: Decimal
    min_price: Decimal
    max_price: Decimal
    max_spread_bps: Decimal
    min_bid_size: int
    min_ask_size: int


@dataclass(frozen=True)
class TradingPlan:
    name: str
    timezone: str
    ibkr: IBKRConfig
    runtime: RuntimeConfig
    budget: BudgetConfig
    orders: OrderConfig
    windows: dict[str, TimeWindow]
    tickers: dict[str, TickerRule]


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value))


def _parse_time(value: str) -> time:
    parts = value.split(":")
    if len(parts) != 2:
        raise ValueError(f"Invalid HH:MM time: {value}")
    hour, minute = int(parts[0]), int(parts[1])
    return time(hour=hour, minute=minute)


def _require_table(raw: dict[str, Any], key: str) -> dict[str, Any]:
    value = raw.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"Missing [{key}] table in config")
    return value


def _parse_windows(raw_windows: list[dict[str, Any]]) -> dict[str, TimeWindow]:
    windows: dict[str, TimeWindow] = {}
    for item in raw_windows:
        days = tuple(item.get("days", []))
        unknown_days = set(days) - _DAY_ALIASES
        if unknown_days:
            raise ValueError(f"Unknown day names in window {item.get('name')}: {sorted(unknown_days)}")
        window = TimeWindow(
            name=str(item["name"]),
            timezone=str(item["timezone"]),
            start=_parse_time(str(item["start"])),
            end=_parse_time(str(item["end"])),
            days=days,
        )
        if window.name in windows:
            raise ValueError(f"Duplicate window name: {window.name}")
        if window.start >= window.end:
            raise ValueError(f"Window start must be before end for {window.name}")
        windows[window.name] = window
    if not windows:
        raise ValueError("At least one [[windows]] entry is required")
    return windows


def _parse_tickers(raw_tickers: list[dict[str, Any]]) -> dict[str, TickerRule]:
    tickers: dict[str, TickerRule] = {}
    for item in raw_tickers:
        symbol = str(item["symbol"]).upper().strip()
        if not symbol:
            raise ValueError("Ticker symbol cannot be blank")
        rule = TickerRule(
            symbol=symbol,
            exchange=str(item.get("exchange", "SMART")),
            currency=str(item.get("currency", "USD")),
            max_position_shares=int(item["max_position_shares"]),
            max_order_shares=int(item["max_order_shares"]),
            max_order_notional=_decimal(item["max_order_notional"]),
            min_price=_decimal(item["min_price"]),
            max_price=_decimal(item["max_price"]),
            max_spread_bps=_decimal(item["max_spread_bps"]),
            min_bid_size=int(item.get("min_bid_size", 1)),
            min_ask_size=int(item.get("min_ask_size", 1)),
        )
        if rule.symbol in tickers:
            raise ValueError(f"Duplicate ticker rule: {rule.symbol}")
        if rule.min_price <= 0 or rule.max_price <= rule.min_price:
            raise ValueError(f"Bad price band for {rule.symbol}")
        if rule.max_order_shares <= 0 or rule.max_position_shares <= 0:
            raise ValueError(f"Share caps must be positive for {rule.symbol}")
        tickers[rule.symbol] = rule
    if not tickers:
        raise ValueError("At least one [[tickers]] entry is required")
    return tickers


def load_plan(path: str | Path) -> TradingPlan:
    config_path = Path(path)
    raw = tomllib.loads(config_path.read_text(encoding="utf-8"))

    meta = _require_table(raw, "meta")
    ibkr = _require_table(raw, "ibkr")
    runtime = _require_table(raw, "runtime")
    budget = _require_table(raw, "budget")
    orders = _require_table(raw, "orders")

    environment = str(runtime.get("environment", "paper"))
    if environment not in {"paper", "live"}:
        raise ValueError("runtime.environment must be 'paper' or 'live'")

    order_type = str(orders.get("order_type", "LMT")).upper()
    if order_type != "LMT":
        raise ValueError("Only LMT order_type is supported")

    return TradingPlan(
        name=str(meta.get("name", "microexec")),
        timezone=str(meta.get("timezone", "America/New_York")),
        ibkr=IBKRConfig(
            host=str(ibkr.get("host", "127.0.0.1")),
            paper_port=int(ibkr.get("paper_port", 7497)),
            live_port=int(ibkr.get("live_port", 7496)),
            client_id=int(ibkr.get("client_id", 1)),
            account=str(ibkr.get("account", "")),
            readonly_market_data=bool(ibkr.get("readonly_market_data", False)),
        ),
        runtime=RuntimeConfig(
            environment=environment,  # type: ignore[arg-type]
            live_enabled=bool(runtime.get("live_enabled", False)),
            kill_switch_file=Path(str(runtime.get("kill_switch_file", ".kill_switch"))),
            log_dir=Path(str(runtime.get("log_dir", "logs"))),
        ),
        budget=BudgetConfig(
            max_gross_notional=_decimal(budget["max_gross_notional"]),
            max_single_order_notional=_decimal(budget["max_single_order_notional"]),
            max_daily_trades=int(budget["max_daily_trades"]),
            min_cash_reserve=_decimal(budget.get("min_cash_reserve", 0)),
            allow_short=bool(budget.get("allow_short", False)),
        ),
        orders=OrderConfig(
            order_type=order_type,
            time_in_force=str(orders.get("time_in_force", "DAY")).upper(),
            outside_regular_trading_hours=bool(orders.get("outside_regular_trading_hours", False)),
            require_quote=bool(orders.get("require_quote", True)),
            send_by_default=bool(orders.get("send_by_default", False)),
        ),
        windows=_parse_windows(raw.get("windows", [])),
        tickers=_parse_tickers(raw.get("tickers", [])),
    )
