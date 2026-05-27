from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path

from .models import Position


def load_positions(path: str | Path | None) -> dict[str, Position]:
    if path is None:
        return {}
    positions_path = Path(path)
    if not positions_path.exists():
        raise FileNotFoundError(f"Positions file not found: {positions_path}")
    out: dict[str, Position] = {}
    with positions_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required = {"symbol", "quantity", "avg_price"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Missing positions columns: {sorted(missing)}")
        for idx, row in enumerate(reader, start=2):
            try:
                symbol = str(row["symbol"]).strip().upper()
                out[symbol] = Position(
                    symbol=symbol,
                    quantity=int(str(row["quantity"]).strip()),
                    avg_price=Decimal(str(row["avg_price"]).strip()),
                )
            except Exception as exc:  # noqa: BLE001 - give row context
                raise ValueError(f"Bad positions row {idx}: {exc}") from exc
    return out
