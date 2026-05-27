#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import csv
import tomllib
from datetime import datetime, timezone
from pathlib import Path


def read_symbols(path: str | Path) -> list[str]:
    import pandas as pd

    df = pd.read_csv(path)
    return [str(s).upper() for s in df["symbol"].dropna().unique()]


async def stream(args: argparse.Namespace) -> int:
    try:
        from ib_async import IB, Stock
    except ImportError as exc:  # pragma: no cover
        raise SystemExit("Install IBKR deps with: pip install -e .[ibkr]") from exc

    config = tomllib.loads(Path(args.config).read_text(encoding="utf-8"))
    symbols = read_symbols(args.universe)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    ib_cfg = config["ibkr"]
    runtime = config["runtime"]
    env = runtime.get("environment", "paper")
    port = int(ib_cfg["paper_port"] if env == "paper" else ib_cfg["live_port"])

    ib = IB()
    await ib.connectAsync(str(ib_cfg.get("host", "127.0.0.1")), port, clientId=int(ib_cfg.get("client_id", 2198)))
    contracts = [Stock(symbol, "SMART", "USD") for symbol in symbols]
    tickers = [ib.reqMktData(contract, "", False, False) for contract in contracts]

    fieldnames = ["timestamp_utc", "symbol", "bid", "ask", "bid_size", "ask_size", "last", "last_size"]
    with out_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if f.tell() == 0:
            writer.writeheader()
        stop_at = asyncio.get_running_loop().time() + float(args.seconds)
        while asyncio.get_running_loop().time() < stop_at:
            await asyncio.sleep(float(args.interval_seconds))
            now = datetime.now(timezone.utc).isoformat()
            for ticker in tickers:
                contract = ticker.contract
                writer.writerow(
                    {
                        "timestamp_utc": now,
                        "symbol": contract.symbol,
                        "bid": ticker.bid,
                        "ask": ticker.ask,
                        "bid_size": ticker.bidSize,
                        "ask_size": ticker.askSize,
                        "last": ticker.last,
                        "last_size": ticker.lastSize,
                    }
                )
            f.flush()
    ib.disconnect()
    print(f"wrote {out_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Stream IBKR paper quotes to CSV for research review.")
    parser.add_argument("--config", default="config/meme_stock_trading_plan.example.toml")
    parser.add_argument("--universe", default="data/final_project_universe.csv")
    parser.add_argument("--out", default="data/raw/ibkr_quotes.csv")
    parser.add_argument("--seconds", type=int, default=300)
    parser.add_argument("--interval-seconds", type=float, default=5.0)
    args = parser.parse_args()
    return asyncio.run(stream(args))


if __name__ == "__main__":
    raise SystemExit(main())
