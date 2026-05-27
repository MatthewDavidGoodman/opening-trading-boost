from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from .audit import append_audit
from .broker import make_broker
from .config import TradingPlan, load_plan
from .intents import load_trade_intents
from .positions import load_positions
from .risk import evaluate_intent


def _print_decision(symbol: str, tag: str, approved: bool, reasons: list[str]) -> None:
    status = "APPROVED" if approved else "REJECTED"
    print(f"{status:8} {symbol:10} {tag:20} {','.join(reasons)}")


def cmd_validate_config(args: argparse.Namespace) -> int:
    plan = load_plan(args.config)
    print(f"OK config={args.config} name={plan.name} env={plan.runtime.environment}")
    print(f"windows={len(plan.windows)} tickers={len(plan.tickers)}")
    return 0


def _dry_quote_for_review(plan: TradingPlan, symbol: str):
    # Review mode should exercise risk logic without requiring market data.
    from .models import Quote

    rule = plan.tickers.get(symbol)
    if rule is None:
        return None
    bid = max(rule.min_price, rule.min_price + (rule.max_price - rule.min_price) / 3)
    spread_bps = min(rule.max_spread_bps / Decimal("4"), Decimal("10"))
    ask = bid * (Decimal("1") + spread_bps / Decimal("10000"))
    return Quote(symbol=symbol, bid=bid, ask=ask, bid_size=100, ask_size=100)


def cmd_review_intents(args: argparse.Namespace) -> int:
    plan = load_plan(args.config)
    intents = load_trade_intents(args.intents, active_only=False)
    positions = load_positions(args.positions)
    when_utc = datetime.now(timezone.utc)
    print(f"Reviewing {len(intents)} intents at {when_utc.isoformat()} against env={plan.runtime.environment}")
    for intent in intents:
        quote = _dry_quote_for_review(plan, intent.symbol)
        decision = evaluate_intent(
            plan=plan,
            intent=intent,
            quote=quote,
            positions=positions,
            daily_trade_count=0,
            when_utc=when_utc,
            require_live_confirm=False,
        )
        _print_decision(intent.symbol, intent.client_tag, decision.approved, decision.reasons)
    return 0


def cmd_run_once(args: argparse.Namespace) -> int:
    plan = load_plan(args.config)
    intents = load_trade_intents(args.intents, active_only=True)
    positions = load_positions(args.positions)
    broker = make_broker(args.broker, plan)
    audit_path = args.audit or str(plan.runtime.log_dir / "audit.jsonl")

    send = bool(args.send)
    if plan.orders.send_by_default and not send:
        print("Config send_by_default=true, but CLI still requires --send. Refusing sends.")

    broker.connect()
    submitted = 0
    try:
        for intent in intents:
            quote = broker.snapshot_quote(intent.symbol) if plan.orders.require_quote else None
            decision = evaluate_intent(
                plan=plan,
                intent=intent,
                quote=quote,
                positions=positions,
                daily_trade_count=submitted,
                when_utc=datetime.now(timezone.utc),
            )
            _print_decision(intent.symbol, intent.client_tag, decision.approved, decision.reasons)
            append_audit(
                audit_path,
                {
                    "event_type": "risk_decision",
                    "intent": intent,
                    "quote": quote,
                    "decision": decision,
                    "send_requested": send,
                    "broker": args.broker,
                },
            )
            if not decision.approved or decision.order is None:
                continue
            if not send:
                append_audit(
                    audit_path,
                    {
                        "event_type": "not_sent_review_only",
                        "order": decision.order,
                        "message": "Use --send to submit after review.",
                    },
                )
                continue
            report = broker.place_limit_order(decision.order)
            submitted += 1
            append_audit(
                audit_path,
                {"event_type": "execution_report", "order": decision.order, "report": report},
            )
            print(f"SENT     {intent.symbol:10} {intent.client_tag:20} {report.message}")
    finally:
        broker.disconnect()
    return 0


def cmd_kill(args: argparse.Namespace) -> int:
    plan = load_plan(args.config)
    plan.runtime.kill_switch_file.write_text("kill switch active\n", encoding="utf-8")
    print(f"Kill switch active: {plan.runtime.kill_switch_file}")
    return 0


def cmd_unkill(args: argparse.Namespace) -> int:
    plan = load_plan(args.config)
    try:
        plan.runtime.kill_switch_file.unlink()
        print(f"Kill switch removed: {plan.runtime.kill_switch_file}")
    except FileNotFoundError:
        print(f"Kill switch was not present: {plan.runtime.kill_switch_file}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ibkr-microexec")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("validate-config", help="Validate TOML config")
    p.add_argument("--config", required=True)
    p.set_defaults(func=cmd_validate_config)

    p = sub.add_parser("review-intents", help="Review CSV intents without touching IBKR")
    p.add_argument("--config", required=True)
    p.add_argument("--intents", required=True)
    p.add_argument("--positions")
    p.set_defaults(func=cmd_review_intents)

    p = sub.add_parser("run-once", help="Run one guarded execution pass")
    p.add_argument("--config", required=True)
    p.add_argument("--intents", required=True)
    p.add_argument("--positions")
    p.add_argument("--broker", default="dry-run", choices=["dry-run", "ibkr"])
    p.add_argument("--audit")
    p.add_argument("--send", action="store_true", help="Actually send approved orders")
    p.set_defaults(func=cmd_run_once)

    p = sub.add_parser("kill", help="Create kill-switch file")
    p.add_argument("--config", required=True)
    p.set_defaults(func=cmd_kill)

    p = sub.add_parser("unkill", help="Remove kill-switch file")
    p.add_argument("--config", required=True)
    p.set_defaults(func=cmd_unkill)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except Exception as exc:  # noqa: BLE001 - CLI error path
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
