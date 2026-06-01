from __future__ import annotations

from pathlib import Path
from typing import Any

LEVELS = range(10)


def _require_pandas():
    try:
        import pandas as pd  # type: ignore
    except ImportError as exc:  # pragma: no cover - depends on optional install
        raise RuntimeError("Install research deps with: pip install -e .[research]") from exc
    return pd


def calculate_imbalance(bid_size: Any, ask_size: Any):
    bid_size = bid_size.astype("float64") if hasattr(bid_size, "astype") else float(bid_size)
    ask_size = ask_size.astype("float64") if hasattr(ask_size, "astype") else float(ask_size)
    total = bid_size + ask_size
    if hasattr(total, "where"):
        return ((bid_size - ask_size) / total.where(total != 0)).fillna(0.0)
    return 0.0 if total == 0 else (bid_size - ask_size) / total


def calculate_microprice(best_bid: Any, best_ask: Any, bid_size: Any, ask_size: Any):
    bid_size = bid_size.astype("float64") if hasattr(bid_size, "astype") else float(bid_size)
    ask_size = ask_size.astype("float64") if hasattr(ask_size, "astype") else float(ask_size)
    total = bid_size + ask_size
    midprice = (best_bid + best_ask) / 2.0
    if hasattr(total, "where"):
        microprice = (best_bid * ask_size + best_ask * bid_size) / total.where(total != 0)
        return microprice.where(total != 0, midprice)
    return midprice if total == 0 else (best_bid * ask_size + best_ask * bid_size) / total


def _book_columns() -> list[str]:
    columns: list[str] = []
    for level in LEVELS:
        columns.extend(
            [
                f"bid_px_{level:02d}",
                f"ask_px_{level:02d}",
                f"bid_sz_{level:02d}",
                f"ask_sz_{level:02d}",
            ]
        )
    return columns


def build_l2_features_for_frame(df, symbol: str, interval: str = "1min"):
    pd = _require_pandas()
    work = df.copy()
    if "datetime" not in work.columns:
        for candidate in ("ts_recv", "ts_event"):
            if candidate in work.columns:
                work["datetime"] = work[candidate]
                break
    if "datetime" not in work.columns:
        if work.index.name in {"ts_recv", "ts_event", "datetime"}:
            work = work.reset_index().rename(columns={work.index.name or "index": "datetime"})
        else:
            raise ValueError("MBP-10 data requires datetime, ts_recv, or ts_event")

    needed = set(_book_columns()) | {"action", "size"}
    missing = needed - set(work.columns)
    if missing:
        raise ValueError(f"Missing MBP-10 columns: {sorted(missing)}")

    work["datetime"] = pd.to_datetime(work["datetime"], utc=True, errors="coerce")
    work = work.dropna(subset=["datetime"]).sort_values("datetime").set_index("datetime")
    book_columns = _book_columns()
    for column in book_columns + ["size"]:
        work[column] = pd.to_numeric(work[column], errors="coerce")

    book = work[book_columns].resample(interval).last().dropna(subset=["bid_px_00", "ask_px_00"])
    trade_mask = work["action"].astype(str).str.upper() == "T"
    trades = work.loc[trade_mask, "size"].resample(interval).agg(["count", "sum"])
    trades = trades.reindex(book.index, fill_value=0)

    out = pd.DataFrame(index=book.index)
    out["symbol"] = symbol.upper()
    out["best_bid"] = book["bid_px_00"]
    out["best_ask"] = book["ask_px_00"]
    out["midprice"] = (out["best_bid"] + out["best_ask"]) / 2.0
    out["spread_bps"] = (out["best_ask"] - out["best_bid"]) / out["midprice"] * 10000.0
    out["bid_size_1"] = book["bid_sz_00"]
    out["ask_size_1"] = book["ask_sz_00"]
    out["bid_depth_10"] = book[[f"bid_sz_{level:02d}" for level in LEVELS]].sum(axis=1)
    out["ask_depth_10"] = book[[f"ask_sz_{level:02d}" for level in LEVELS]].sum(axis=1)
    out["imbalance_1"] = calculate_imbalance(out["bid_size_1"], out["ask_size_1"])
    out["imbalance_10"] = calculate_imbalance(out["bid_depth_10"], out["ask_depth_10"])
    out["microprice"] = calculate_microprice(
        out["best_bid"], out["best_ask"], out["bid_size_1"], out["ask_size_1"]
    )
    out["mid_return_1m"] = out["midprice"].pct_change()
    out["mid_return_5m"] = out["midprice"].pct_change(5)
    out["realized_vol_5m"] = out["mid_return_1m"].rolling(5, min_periods=2).std()
    out["trade_count"] = trades["count"].astype(int)
    out["trade_volume"] = trades["sum"].fillna(0)
    return out.reset_index()


def read_mbp10(path: str | Path):
    pd = _require_pandas()
    path = Path(path)
    if path.suffix == ".csv":
        return pd.read_csv(path)
    try:
        import databento as db  # type: ignore
    except ImportError as exc:  # pragma: no cover - depends on optional install
        raise RuntimeError("Install the Databento client with: pip install databento") from exc
    return db.read_dbn(path).to_df(price_type="float", pretty_ts=True, map_symbols=True)


def build_l2_feature_panel(
    raw_dir: str | Path,
    processed_dir: str | Path,
    out_path: str | Path,
    interval: str = "1min",
):
    pd = _require_pandas()
    raw_dir = Path(raw_dir)
    paths = sorted(
        list(raw_dir.glob("*.dbn"))
        + list(raw_dir.glob("*.dbn.zst"))
        + list(raw_dir.glob("*.csv"))
    )
    if not paths:
        raise FileNotFoundError(f"No MBP-10 files found in {raw_dir}")

    processed_dir = Path(processed_dir)
    processed_dir.mkdir(parents=True, exist_ok=True)
    frames = []
    for path in paths:
        symbol = path.name.split("_")[0].upper()
        frame = build_l2_features_for_frame(read_mbp10(path), symbol=symbol, interval=interval)
        frame.to_csv(processed_dir / f"{symbol}_l2_features.csv", index=False)
        frames.append(frame)

    panel = pd.concat(frames, ignore_index=True).sort_values(["datetime", "symbol"])
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    panel.to_csv(out_path, index=False)
    return panel
