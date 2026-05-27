#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


def read_symbols(args: argparse.Namespace) -> list[str]:
    if args.symbols:
        return [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    if args.universe:
        import pandas as pd

        df = pd.read_csv(args.universe)
        return [str(s).upper() for s in df["symbol"].dropna().unique()]
    raise SystemExit("Pass --symbols GME,AMC or --universe data/final_project_universe.csv")


def main() -> int:
    parser = argparse.ArgumentParser(description="Download OHLCV bars for the research layer.")
    parser.add_argument("--symbols", default="", help="Comma-separated tickers, e.g. GME,AMC,SOUN")
    parser.add_argument("--universe", default="data/final_project_universe.csv")
    parser.add_argument("--out-dir", default="data/raw/prices")
    parser.add_argument("--period", default="60d", help="yfinance period, e.g. 30d, 60d, 1y")
    parser.add_argument("--interval", default="5m", help="yfinance interval, e.g. 1m, 5m, 15m, 1d")
    args = parser.parse_args()

    try:
        import yfinance as yf
    except ImportError as exc:  # pragma: no cover
        raise SystemExit("Install research deps with: pip install -e .[research]") from exc

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    symbols = read_symbols(args)

    for symbol in symbols:
        print(f"downloading {symbol} {args.period} {args.interval}")
        df = yf.download(
            symbol,
            period=args.period,
            interval=args.interval,
            auto_adjust=False,
            progress=False,
            prepost=False,
            threads=False,
        )
        if df.empty:
            print(f"  no rows for {symbol}")
            continue
        if isinstance(df.columns, type(df.index)):
            pass
        if hasattr(df.columns, "levels") and len(getattr(df.columns, "levels", [])) > 1:
            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
        df = df.rename_axis("datetime").reset_index()
        df.columns = [str(c).lower().replace(" ", "_") for c in df.columns]
        keep = [c for c in ["datetime", "open", "high", "low", "close", "adj_close", "volume"] if c in df.columns]
        df[keep].to_csv(out_dir / f"{symbol}_{args.interval}.csv", index=False)
        print(f"  wrote {out_dir / f'{symbol}_{args.interval}.csv'} rows={len(df)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
