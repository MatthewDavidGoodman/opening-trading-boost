from __future__ import annotations

import os
from datetime import datetime
from decimal import Decimal

from .config import TradingPlan
from .models import OrderRequest, Position, Quote, RiskDecision, TradeIntent
from .timegate import is_window_open

LIVE_CONFIRM_ENV = "IBKR_MICROEXEC_LIVE_CONFIRM"
LIVE_CONFIRM_VALUE = "YES_I_UNDERSTAND"


def _gross_notional(positions: dict[str, Position]) -> Decimal:
    return sum((p.gross_notional for p in positions.values()), Decimal("0"))


def evaluate_intent(
    plan: TradingPlan,
    intent: TradeIntent,
    quote: Quote | None,
    positions: dict[str, Position] | None = None,
    daily_trade_count: int = 0,
    when_utc: datetime | None = None,
    require_live_confirm: bool = True,
) -> RiskDecision:
    positions = positions or {}
    reasons: list[str] = []

    if not intent.active:
        reasons.append("intent_inactive")

    if plan.runtime.kill_switch_file.exists():
        reasons.append("kill_switch_present")

    if plan.runtime.environment == "live":
        if not plan.runtime.live_enabled:
            reasons.append("live_environment_but_live_enabled_false")
        if require_live_confirm and os.getenv(LIVE_CONFIRM_ENV) != LIVE_CONFIRM_VALUE:
            reasons.append("missing_live_environment_confirmation")

    if plan.orders.order_type != "LMT":
        reasons.append("only_limit_orders_supported")

    if intent.symbol not in plan.tickers:
        reasons.append("symbol_not_allowlisted")
        return RiskDecision.reject(reasons)

    rule = plan.tickers[intent.symbol]

    if intent.window not in plan.windows:
        reasons.append("unknown_time_window")
    else:
        window = plan.windows[intent.window]
        if not is_window_open(window, when_utc):
            reasons.append("outside_allowed_time_window")

    if intent.quantity <= 0:
        reasons.append("quantity_must_be_positive")
    if intent.quantity > rule.max_order_shares:
        reasons.append("exceeds_symbol_max_order_shares")

    if intent.limit_price <= 0:
        reasons.append("limit_price_must_be_positive")
    if intent.limit_price < rule.min_price or intent.limit_price > rule.max_price:
        reasons.append("limit_price_outside_symbol_price_band")

    if intent.notional > rule.max_order_notional:
        reasons.append("exceeds_symbol_max_order_notional")
    if intent.notional > plan.budget.max_single_order_notional:
        reasons.append("exceeds_account_max_single_order_notional")

    if daily_trade_count >= plan.budget.max_daily_trades:
        reasons.append("daily_trade_limit_reached")

    current_position = positions.get(intent.symbol, Position(symbol=intent.symbol, quantity=0))
    new_qty = current_position.quantity + (intent.quantity if intent.side == "BUY" else -intent.quantity)
    if not plan.budget.allow_short and new_qty < 0:
        reasons.append("short_position_not_allowed")
    if abs(new_qty) > rule.max_position_shares:
        reasons.append("exceeds_symbol_max_position_shares")

    projected_gross = _gross_notional(positions) + intent.notional
    if projected_gross > plan.budget.max_gross_notional:
        reasons.append("exceeds_account_max_gross_notional")

    if plan.orders.require_quote:
        if quote is None:
            reasons.append("missing_quote")
        elif not quote.has_two_sided_quote:
            reasons.append("missing_two_sided_quote")
        else:
            spread_bps = quote.spread_bps
            if spread_bps is None:
                reasons.append("cannot_compute_spread")
            elif spread_bps > rule.max_spread_bps:
                reasons.append("spread_too_wide")
            if quote.bid_size is not None and quote.bid_size < rule.min_bid_size:
                reasons.append("bid_size_too_small")
            if quote.ask_size is not None and quote.ask_size < rule.min_ask_size:
                reasons.append("ask_size_too_small")

    if reasons:
        return RiskDecision.reject(reasons)

    return RiskDecision.approve(
        OrderRequest(
            symbol=intent.symbol,
            side=intent.side,
            quantity=intent.quantity,
            limit_price=intent.limit_price,
            client_tag=intent.client_tag,
            time_in_force=plan.orders.time_in_force,
            outside_regular_trading_hours=plan.orders.outside_regular_trading_hours,
        )
    )
