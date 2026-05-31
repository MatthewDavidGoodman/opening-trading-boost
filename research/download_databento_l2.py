#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import tomllib
from pathlib import Path
from typing import Any, Callable


def load_config(path: str | Path) -> dict[str, Any]:
    raw = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    config = raw.get("databento")
    if not isinstance(config, dict):
        raise SystemExit("Missing [databento] table in config")
    if config.get("schema") != "mbp-10":
        raise SystemExit("Databento L2 pipeline requires schema = \"mbp-10\"")
    return config


def build_requests(config: dict[str, Any]) -> list[dict[str, Any]]:
    symbols = [str(symbol).upper() for symbol in config.get("symbols", [])]
    if not symbols:
        raise SystemExit("Configure at least one Databento symbol")
    return [
        {
            "dataset": str(config["dataset"]),
            "schema": "mbp-10",
            "symbols": [symbol],
            "start": str(config["start"]),
            "end": str(config["end"]),
            "stype_in": str(config["stype_in"]),
            "limit": int(config["max_rows"]),
        }
        for symbol in symbols
    ]


def _historical_factory(api_key: str):
    try:
        import databento as db  # type: ignore
    except ImportError as exc:  # pragma: no cover - depends on optional install
        raise SystemExit("Install the Databento client with: pip install databento") from exc
    return db.Historical(api_key)


def download(
    config_path: str | Path,
    *,
    dry_run: bool = False,
    client_factory: Callable[[str], Any] | None = None,
) -> list[Path]:
    config = load_config(config_path)
    requests = build_requests(config)
    raw_dir = Path(str(config["raw_dir"]))

    for request in requests:
        print(f"Databento request: {request}")
    if dry_run:
        print("dry-run: no Databento API call made")
        return []

    api_key = os.getenv("DATABENTO_API_KEY")
    if not api_key:
        raise SystemExit("DATABENTO_API_KEY must be set for Databento downloads")

    client = (client_factory or _historical_factory)(api_key)
    raw_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for request in requests:
        symbol = request["symbols"][0]
        path = raw_dir / f"{symbol}_mbp-10.dbn.zst"
        data = client.timeseries.get_range(**request)
        data.to_file(path)
        paths.append(path)
        print(f"wrote {path}")
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description="Download Databento historical MBP-10 L2 data.")
    parser.add_argument("--config", default="config/databento_l2.example.toml")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    download(args.config, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
