from __future__ import annotations

import csv
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Literal

ResearchSide = Literal["BUY", "PAPER_SHORT", "NONE"]
LiveSide = Literal["BUY", "NONE"]


@dataclass(frozen=True)
class TradeSetup:
    setup_id: str
    symbol: str
    family: str
    setup_name: str
    research_side: ResearchSide
    live_side_allowed: LiveSide
    entry_window_et: str
    exit_window_et: str
    min_rel_volume: Decimal
    max_spread_bps: Decimal
    max_notional_paper: Decimal
    max_notional_live: Decimal
    thesis: str
    why_this_name: str
    entry_rule_plain: str
    exit_rule_plain: str
    ml_question: str

    @property
    def live_enabled(self) -> bool:
        return self.live_side_allowed != "NONE" and self.max_notional_live > 0


def _decimal(value: str, default: str = "0") -> Decimal:
    text = str(value).strip()
    if not text:
        text = default
    return Decimal(text)


def _parse_research_side(value: str) -> ResearchSide:
    side = str(value).strip().upper()
    if side not in {"BUY", "PAPER_SHORT", "NONE"}:
        raise ValueError(f"research_side must be BUY, PAPER_SHORT, or NONE, got {value!r}")
    return side  # type: ignore[return-value]


def _parse_live_side(value: str) -> LiveSide:
    side = str(value).strip().upper()
    if side not in {"BUY", "NONE"}:
        raise ValueError(f"live_side_allowed must be BUY or NONE, got {value!r}")
    return side  # type: ignore[return-value]


def load_trade_setups(path: str | Path) -> list[TradeSetup]:
    rows: list[TradeSetup] = []
    with Path(path).open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required = {
            "setup_id",
            "symbol",
            "family",
            "setup_name",
            "research_side",
            "live_side_allowed",
            "entry_window_et",
            "exit_window_et",
            "min_rel_volume",
            "max_spread_bps",
            "max_notional_paper",
            "max_notional_live",
            "thesis",
            "why_this_name",
            "entry_rule_plain",
            "exit_rule_plain",
            "ml_question",
        }
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Missing required setup columns: {sorted(missing)}")
        for idx, row in enumerate(reader, start=2):
            try:
                setup = TradeSetup(
                    setup_id=str(row["setup_id"]).strip().upper(),
                    symbol=str(row["symbol"]).strip().upper(),
                    family=str(row["family"]).strip(),
                    setup_name=str(row["setup_name"]).strip(),
                    research_side=_parse_research_side(str(row["research_side"])),
                    live_side_allowed=_parse_live_side(str(row["live_side_allowed"])),
                    entry_window_et=str(row["entry_window_et"]).strip(),
                    exit_window_et=str(row["exit_window_et"]).strip(),
                    min_rel_volume=_decimal(str(row["min_rel_volume"]), "1"),
                    max_spread_bps=_decimal(str(row["max_spread_bps"]), "100"),
                    max_notional_paper=_decimal(str(row["max_notional_paper"]), "0"),
                    max_notional_live=_decimal(str(row["max_notional_live"]), "0"),
                    thesis=str(row["thesis"]).strip(),
                    why_this_name=str(row["why_this_name"]).strip(),
                    entry_rule_plain=str(row["entry_rule_plain"]).strip(),
                    exit_rule_plain=str(row["exit_rule_plain"]).strip(),
                    ml_question=str(row["ml_question"]).strip(),
                )
            except Exception as exc:  # noqa: BLE001 - add row context
                raise ValueError(f"Bad setup row {idx}: {exc}") from exc
            rows.append(setup)
    return rows
