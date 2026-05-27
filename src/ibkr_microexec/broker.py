from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Protocol

from .config import TradingPlan
from .models import ExecutionReport, OrderRequest, Quote


class Broker(Protocol):
    def connect(self) -> None: ...

    def disconnect(self) -> None: ...

    def snapshot_quote(self, symbol: str) -> Quote: ...

    def place_limit_order(self, order: OrderRequest) -> ExecutionReport: ...


@dataclass
class DryRunBroker:
    """Broker adapter that never touches a real broker."""

    default_bid: Decimal = Decimal("10.00")
    default_ask: Decimal = Decimal("10.02")

    def connect(self) -> None:
        return None

    def disconnect(self) -> None:
        return None

    def snapshot_quote(self, symbol: str) -> Quote:
        return Quote(
            symbol=symbol,
            bid=self.default_bid,
            ask=self.default_ask,
            bid_size=100,
            ask_size=100,
            timestamp_utc=datetime.now(timezone.utc),
        )

    def place_limit_order(self, order: OrderRequest) -> ExecutionReport:
        return ExecutionReport(
            accepted_by_adapter=True,
            broker_order_id=f"DRYRUN-{order.client_tag}",
            message="dry_run_no_order_sent",
        )


class IbAsyncBroker:
    """Thin adapter around ib_async.

    Install with: pip install -e .[ibkr]
    """

    def __init__(self, plan: TradingPlan) -> None:
        self.plan = plan
        self.ib = None

    def connect(self) -> None:
        try:
            from ib_async import IB  # type: ignore
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise RuntimeError("Install IBKR dependencies with: pip install -e .[ibkr]") from exc

        self.ib = IB()
        port = self.plan.ibkr.port_for(self.plan.runtime.environment)
        self.ib.connect(self.plan.ibkr.host, port, clientId=self.plan.ibkr.client_id)

    def disconnect(self) -> None:
        if self.ib is not None:
            self.ib.disconnect()

    def _contract(self, symbol: str):
        if self.ib is None:
            raise RuntimeError("Broker is not connected")
        from ib_async import Stock  # type: ignore

        rule = self.plan.tickers[symbol]
        contract = Stock(symbol, rule.exchange, rule.currency)
        qualified = self.ib.qualifyContracts(contract)
        if not qualified:
            raise RuntimeError(f"Could not qualify contract for {symbol}")
        return qualified[0]

    def snapshot_quote(self, symbol: str) -> Quote:
        if self.ib is None:
            raise RuntimeError("Broker is not connected")
        contract = self._contract(symbol)
        ticker = self.ib.reqMktData(contract, "", True, False)
        self.ib.sleep(2)

        def dec(value) -> Decimal | None:
            try:
                if value is None or value != value or value <= 0:  # NaN-safe
                    return None
                return Decimal(str(value))
            except Exception:
                return None

        bid = dec(getattr(ticker, "bid", None))
        ask = dec(getattr(ticker, "ask", None))
        bid_size_raw = getattr(ticker, "bidSize", None)
        ask_size_raw = getattr(ticker, "askSize", None)
        return Quote(
            symbol=symbol,
            bid=bid,
            ask=ask,
            bid_size=int(bid_size_raw) if bid_size_raw is not None else None,
            ask_size=int(ask_size_raw) if ask_size_raw is not None else None,
            timestamp_utc=datetime.now(timezone.utc),
        )

    def place_limit_order(self, order: OrderRequest) -> ExecutionReport:
        if self.ib is None:
            raise RuntimeError("Broker is not connected")
        from ib_async import LimitOrder  # type: ignore

        contract = self._contract(order.symbol)
        ib_order = LimitOrder(
            order.side,
            order.quantity,
            float(order.limit_price),
            tif=order.time_in_force,
            outsideRth=order.outside_regular_trading_hours,
        )
        if self.plan.ibkr.account:
            ib_order.account = self.plan.ibkr.account
        trade = self.ib.placeOrder(contract, ib_order)
        broker_order_id = str(getattr(trade.order, "orderId", "")) if getattr(trade, "order", None) else None
        return ExecutionReport(
            accepted_by_adapter=True,
            broker_order_id=broker_order_id,
            message="order_submitted_to_ibkr",
        )


def make_broker(kind: str, plan: TradingPlan) -> Broker:
    normalized = kind.strip().lower()
    if normalized in {"dry", "dry-run", "dryrun"}:
        return DryRunBroker()
    if normalized in {"ibkr", "ib_async", "ibasync"}:
        return IbAsyncBroker(plan)
    raise ValueError(f"Unknown broker kind: {kind}")
