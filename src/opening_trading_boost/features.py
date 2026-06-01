from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FeatureConfig:
    forward_bars: int = 3
    min_forward_return_bps: float = 25.0
    cost_buffer_bps: float = 20.0


def _require_pandas():
    try:
        import pandas as pd  # type: ignore
    except ImportError as exc:  # pragma: no cover - depends on optional install
        raise RuntimeError("Install research deps with: pip install -e .[research]") from exc
    return pd


def read_price_csv(path: str | Path):
    """Read a per-symbol OHLCV CSV written by research/download_prices.py."""
    pd = _require_pandas()
    df = pd.read_csv(path)
    possible_time_cols = ["datetime", "Datetime", "date", "Date", "timestamp"]
    time_col = next((col for col in possible_time_cols if col in df.columns), None)
    if time_col:
        df["datetime"] = pd.to_datetime(df[time_col], utc=True, errors="coerce")
    elif "datetime" not in df.columns:
        raise ValueError(f"No datetime column found in {path}")

    rename = {col: col.lower().replace(" ", "_") for col in df.columns}
    df = df.rename(columns=rename)
    needed = {"open", "high", "low", "close", "volume", "datetime"}
    missing = needed - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns in {path}: {sorted(missing)}")
    return df.sort_values("datetime").reset_index(drop=True)


def build_features_for_frame(df, symbol: str, cfg: FeatureConfig | None = None):
    """Build compact intraday/daily features for one symbol."""
    pd = _require_pandas()
    cfg = cfg or FeatureConfig()
    out = df.copy()
    out["symbol"] = symbol.upper()
    out["datetime"] = pd.to_datetime(out["datetime"], utc=True, errors="coerce")
    out = out.dropna(subset=["datetime", "close"]).sort_values("datetime")

    close = out["close"].astype(float)
    high = out["high"].astype(float)
    low = out["low"].astype(float)
    volume = out["volume"].astype(float)

    out["ret_1"] = close.pct_change()
    out["ret_3"] = close.pct_change(3)
    out["ret_12"] = close.pct_change(12)
    out["range_bps"] = ((high - low) / close).replace([float("inf"), float("-inf")], None) * 10000
    out["dollar_volume"] = close * volume
    out["rel_volume_20"] = volume / volume.rolling(20, min_periods=5).mean()
    out["realized_vol_20"] = out["ret_1"].rolling(20, min_periods=10).std()
    out["close_vs_sma20_bps"] = (close / close.rolling(20, min_periods=10).mean() - 1.0) * 10000

    dt = out["datetime"].dt.tz_convert("America/New_York")
    out["hour_et"] = dt.dt.hour
    out["minute_et"] = dt.dt.minute
    out["minute_of_day_et"] = out["hour_et"] * 60 + out["minute_et"]
    out["weekday"] = dt.dt.weekday

    fwd = close.shift(-cfg.forward_bars) / close - 1.0
    out["forward_return"] = fwd
    threshold = (cfg.min_forward_return_bps + cfg.cost_buffer_bps) / 10000.0
    out["label_forward_up"] = (fwd > threshold).astype(int)
    out["last_price"] = close

    feature_cols = [
        "symbol",
        "datetime",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "last_price",
        "ret_1",
        "ret_3",
        "ret_12",
        "range_bps",
        "dollar_volume",
        "rel_volume_20",
        "realized_vol_20",
        "close_vs_sma20_bps",
        "hour_et",
        "minute_et",
        "minute_of_day_et",
        "weekday",
        "forward_return",
        "label_forward_up",
    ]
    return out[feature_cols].dropna().reset_index(drop=True)


def build_feature_panel(price_dir: str | Path, cfg: FeatureConfig | None = None):
    """Build a panel from one CSV per symbol inside price_dir."""
    pd = _require_pandas()
    paths = sorted(Path(price_dir).glob("*.csv"))
    if not paths:
        raise FileNotFoundError(f"No CSV files found in {price_dir}")
    frames = []
    for path in paths:
        symbol = path.stem.split("_")[0].upper()
        frames.append(build_features_for_frame(read_price_csv(path), symbol=symbol, cfg=cfg))
    return pd.concat(frames, ignore_index=True).sort_values(["datetime", "symbol"])
