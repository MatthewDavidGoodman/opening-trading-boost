from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path

from .models import Side, TradeIntent

_TRUE_VALUES = {"1", "true", "yes", "y", "active"}
_FALSE_VALUES = {"0", "false", "no", "n", "inactive", ""}


def parse_bool(value: str) -> bool:
    normalized = str(value).strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    raise ValueError(f"Cannot parse boolean value: {value!r}")


def parse_side(value: str) -> Side:
    side = str(value).strip().upper()
    if side not in {"BUY", "SELL"}:
        raise ValueError(f"side must be BUY or SELL, got {value!r}")
    return side  # type: ignore[return-value]


def load_trade_intents(path: str | Path, active_only: bool = False) -> list[TradeIntent]:
    rows: list[TradeIntent] = []
    with Path(path).open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required = {"symbol", "side", "quantity", "limit_price", "window", "active", "client_tag"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Missing required intent columns: {sorted(missing)}")
        for idx, row in enumerate(reader, start=2):
            try:
                intent = TradeIntent(
                    symbol=str(row["symbol"]).strip().upper(),
                    side=parse_side(str(row["side"])),
                    quantity=int(str(row["quantity"]).strip()),
                    limit_price=Decimal(str(row["limit_price"]).strip()),
                    window=str(row["window"]).strip(),
                    active=parse_bool(str(row["active"])),
                    client_tag=str(row["client_tag"]).strip(),
                    notes=str(row.get("notes", "")).strip(),
                )
            except Exception as exc:  # noqa: BLE001 - give row context
                raise ValueError(f"Bad intent row {idx}: {exc}") from exc
            if active_only and not intent.active:
                continue
            rows.append(intent)
    return rows
