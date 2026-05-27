from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Literal

Side = Literal["BUY", "SELL"]
Environment = Literal["paper", "live"]


@dataclass(frozen=True)
class Quote:
    symbol: str
    bid: Decimal | None
    ask: Decimal | None
    bid_size: int | None = None
    ask_size: int | None = None
    timestamp_utc: datetime | None = None

    @property
    def has_two_sided_quote(self) -> bool:
        return self.bid is not None and self.ask is not None and self.bid > 0 and self.ask > 0

    @property
    def mid(self) -> Decimal | None:
        if not self.has_two_sided_quote:
            return None
        assert self.bid is not None and self.ask is not None
        return (self.bid + self.ask) / Decimal("2")

    @property
    def spread_bps(self) -> Decimal | None:
        mid = self.mid
        if mid is None or mid <= 0:
            return None
        assert self.bid is not None and self.ask is not None
        return ((self.ask - self.bid) / mid) * Decimal("10000")


@dataclass(frozen=True)
class TradeIntent:
    symbol: str
    side: Side
    quantity: int
    limit_price: Decimal
    window: str
    active: bool
    client_tag: str
    notes: str = ""

    @property
    def notional(self) -> Decimal:
        return self.limit_price * Decimal(self.quantity)


@dataclass(frozen=True)
class Position:
    symbol: str
    quantity: int
    avg_price: Decimal = Decimal("0")

    @property
    def gross_notional(self) -> Decimal:
        return abs(Decimal(self.quantity) * self.avg_price)


@dataclass(frozen=True)
class OrderRequest:
    symbol: str
    side: Side
    quantity: int
    limit_price: Decimal
    client_tag: str
    time_in_force: str
    outside_regular_trading_hours: bool = False


@dataclass(frozen=True)
class RiskDecision:
    approved: bool
    reasons: list[str] = field(default_factory=list)
    order: OrderRequest | None = None

    @classmethod
    def approve(cls, order: OrderRequest) -> "RiskDecision":
        return cls(approved=True, reasons=["approved"], order=order)

    @classmethod
    def reject(cls, reasons: list[str]) -> "RiskDecision":
        return cls(approved=False, reasons=reasons, order=None)


@dataclass(frozen=True)
class ExecutionReport:
    accepted_by_adapter: bool
    broker_order_id: str | None
    message: str
