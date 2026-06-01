# Opening Trading Boost

Opening Trading Boost is an offline Databento L2 research project that tests a short opening-warmup trading layer for retail-hype names.

The idea is simple: before a broader intraday strategy starts trading, use early order book behavior to decide which symbols are worth activating, which should be watched, and which should be skipped.

The test basket uses three deliberately different hype/liquidity names:

- **SOUN** — lower-priced AI retail-hype name with active opening flow.
- **RIVN** — EV retail-beta name with heavier liquidity and different book behavior.
- **RKLB** — space/aerospace retail-hype name used as a higher-priced stress case for the ladder sizing and ranking logic.

This is not a live trading system. It does not connect to a broker or place orders. It is an offline trading final project built around Databento MBP-10 L2 order book data.

## Key Results

| Version | Trades | Total Net Bps | Avg Net Bps | Win Rate | Interpretation |
|---|---:|---:|---:|---:|---|
| `legacy_high_pnl_ladder` | 5 | +160.89 | +32.18 | 80.0% | Best raw opening-warmup result |
| `ranked_opening_ladder` | 4 | +61.28 | +15.32 | 75.0% | Cleaner ranked top-2 version |
| `extended_opening_benchmark` | 6 | -104.53 | -17.42 | 50.0% | Longer window performed worse |
| `bad_benchmark_all_day_reuse` | 24 | -395.12 | -16.46 | 37.5% | All-day reuse failed |
| `pair_trade_appendix` | 13 | -1099.46 | -84.57 | 15.4% | Research-only appendix, poor result |

## Final Project Outputs

- [Two-page project summary PDF](docs/opening_trading_boost_2pager.pdf)
- [Results memo](docs/l2_results_memo.md)
- [Final notebook](notebooks/l2_final_project_outputs.ipynb)
- [Strategy version comparison](data/reports/l2_strategy_version_comparison.csv)
- [Generated plots](data/plots/)

## Core Takeaway

A short, selective opening warmup layer performed better than longer-window, all-day reuse, and pair-trade variants on this sample.

The warmup layer is meant to be a flexible add-on for team trading research: rank hype names near the open, avoid weak opening conditions, and decide which symbols deserve strategy activation.
