from __future__ import annotations

from typing import Any


def simulate_long_fill(
    entry_ask: float, exit_bid: float, estimated_cost_bps: float
) -> dict[str, float]:
    if entry_ask <= 0 or exit_bid <= 0:
        raise ValueError("Simulated prices must be positive")
    gross_return_bps = (exit_bid / entry_ask - 1.0) * 10000.0
    return {
        "entry_price": entry_ask,
        "exit_price": exit_bid,
        "gross_return_bps": gross_return_bps,
        "estimated_cost_bps": estimated_cost_bps,
        "net_return_bps": gross_return_bps - estimated_cost_bps,
    }


def simulate_l2_trades(features, occurrences, holding_period_bars: int, estimated_cost_bps: float):
    pd = __import__("pandas")
    feature_frame = features.copy()
    feature_frame["datetime"] = pd.to_datetime(feature_frame["datetime"], utc=True, errors="coerce")
    feature_frame = feature_frame.sort_values(["symbol", "datetime"])
    by_symbol = {
        symbol: frame.reset_index(drop=True)
        for symbol, frame in feature_frame.groupby(feature_frame["symbol"].astype(str))
    }

    records: list[dict[str, Any]] = []
    paper_longs = occurrences.loc[occurrences["decision"] == "PAPER_LONG"].copy()
    paper_longs["datetime"] = pd.to_datetime(paper_longs["datetime"], utc=True, errors="coerce")
    for _, setup in paper_longs.iterrows():
        symbol = str(setup["symbol"])
        symbol_features = by_symbol.get(symbol)
        if symbol_features is None:
            continue
        matches = symbol_features.index[symbol_features["datetime"] == setup["datetime"]].tolist()
        if not matches:
            continue
        entry_index = matches[0]
        exit_index = entry_index + holding_period_bars
        if exit_index >= len(symbol_features):
            continue
        entry = symbol_features.iloc[entry_index]
        exit_row = symbol_features.iloc[exit_index]
        fill = simulate_long_fill(
            entry_ask=float(entry["best_ask"]),
            exit_bid=float(exit_row["best_bid"]),
            estimated_cost_bps=estimated_cost_bps,
        )
        records.append(
            {
                "symbol": symbol,
                "setup_id": setup["setup_id"],
                "entry_datetime": entry["datetime"],
                "exit_datetime": exit_row["datetime"],
                **fill,
            }
        )
    return pd.DataFrame(
        records,
        columns=[
            "symbol",
            "setup_id",
            "entry_datetime",
            "exit_datetime",
            "entry_price",
            "exit_price",
            "gross_return_bps",
            "estimated_cost_bps",
            "net_return_bps",
        ],
    )


def summarize_l2_trades(blotter):
    pd = __import__("pandas")
    columns = [
        "setup_id",
        "trade_count",
        "average_gross_return_bps",
        "average_net_return_bps",
        "total_net_return_bps",
        "win_rate",
    ]
    if blotter.empty:
        return pd.DataFrame(columns=columns)
    summary = (
        blotter.groupby("setup_id")
        .agg(
            trade_count=("net_return_bps", "size"),
            average_gross_return_bps=("gross_return_bps", "mean"),
            average_net_return_bps=("net_return_bps", "mean"),
            total_net_return_bps=("net_return_bps", "sum"),
            win_rate=("net_return_bps", lambda values: (values > 0).mean()),
        )
        .reset_index()
    )
    return summary[columns]
