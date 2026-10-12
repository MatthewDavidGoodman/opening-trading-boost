# Opening Trading Boost

An offline market-microstructure research project that uses **Databento MBP-10 level-2 order-book data** to decide which symbols merit activation during the opening session.

The research question is narrow: can early order-book behavior improve symbol selection and execution decisions before a broader intraday strategy begins trading?

The test basket intentionally spans different retail-sensitive/liquidity profiles:

- **SOUN** — lower-priced AI / retail-flow name;
- **RIVN** — higher-liquidity EV / retail-beta name;
- **RKLB** — aerospace / retail-flow name used as a higher-priced sizing and ranking stress case.

This is **not a live trading system**. It does not connect to a broker or place orders. The results come from a small offline research sample and should not be interpreted as evidence of production alpha.

## Research inputs

The project studies three opening-session setup families:

1. **Imbalance** — one-sided pressure in the opening book.
2. **Spread compression** — bid/ask tightening that may indicate improving liquidity.
3. **Pullback reclaim** — an early pullback followed by recovery during the opening window.

The ranked variant scores symbols from these opening features and activates only the strongest candidates instead of reusing every setup throughout the day.

## Execution model

The research engine can choose among:

- `REST` — passive limit order;
- `JOIN` — join the best bid or offer;
- `IMPROVE` — improve inside the spread by one tick;
- `CROSS` — marketable limit order;
- `CANCEL_REPLACE` — update a stale order;
- `REDUCE_ONLY` — trade only to reduce exposure;
- `STAND_DOWN` — skip poor conditions.

## Key sample results

| Version | Trades | Total Net Bps | Avg Net Bps | Win Rate | Interpretation |
|---|---:|---:|---:|---:|---|
| `legacy_high_pnl_ladder` | 5 | +160.89 | +32.18 | 80.0% | strongest raw opening-warmup result |
| `ranked_opening_ladder` | 4 | +61.28 | +15.32 | 75.0% | cleaner ranked top-2 variant |
| `extended_opening_benchmark` | 6 | -104.53 | -17.42 | 50.0% | longer opening window performed worse |
| `bad_benchmark_all_day_reuse` | 24 | -395.12 | -16.46 | 37.5% | indiscriminate all-day reuse failed |
| `pair_trade_appendix` | 13 | -1099.46 | -84.57 | 15.4% | research appendix; poor result |

The useful finding is not the headline PnL number. On this limited sample, **selective opening-session use behaved materially better than extending the same signals indiscriminately through the day**. That is a hypothesis for further validation, not a production conclusion.

## Project outputs

- [Two-page project summary PDF](docs/opening_trading_boost_2pager.pdf)
- [Results memo](docs/l2_results_memo.md)
- [Final notebook](notebooks/l2_final_project_outputs.ipynb)
- [Strategy-version comparison](data/reports/l2_strategy_version_comparison.csv)
- [Generated plots](data/plots/)

## Next validation work

A stronger research version would expand the symbol/date sample, use strict out-of-sample selection, stress transaction-cost and queue-position assumptions, and report confidence intervals rather than relying on a handful of realized trades.
