# Ranked Opening Ladder Results Memo

## 1. Executive result

This final project is an offline L2 research workflow built from Databento MBP-10 features. It does
not claim production alpha and does not place orders. On this sample, short and selective
opening-ladder variants performed better than longer-window or all-day reuse variants.

The best raw result is the named `legacy_high_pnl_ladder`: five trades, `+160.89` total net bps,
`+32.18` average net bps, and an `80%` win rate. The cleaner controlled result is
`ranked_opening_ladder`: four trades, `+61.28` total net bps, `+15.32` average net bps, and a `75%`
win rate.

## 2. Strategy versions compared

| Version | Trades | Average net bps | Total net bps | Win rate | Role |
|---|---:|---:|---:|---:|---|
| `legacy_high_pnl_ladder` | 5 | +32.18 | +160.89 | 80% | Best raw PnL |
| `ranked_opening_ladder` | 4 | +15.32 | +61.28 | 75% | Cleaner controlled version |
| `extended_opening_benchmark` | 6 | -17.42 | -104.53 | 50% | Longer-window benchmark |
| `bad_benchmark_all_day_reuse` | 24 | -16.46 | -395.12 | 37.5% | Negative control |
| `pair_trade_appendix` | 13 | -84.57 | -1099.46 | 15.4% | Research-only appendix |

## 3. Best raw PnL configuration

`legacy_high_pnl_ladder` preserves the reproduced high-PnL run as an explicit configuration rather
than an accidental fallback. It uses the `09:30-10:30 ET` window, imbalance-only setups, unranked
eligible symbols, and sizing rules that skip high-price one-share probes.

By symbol, RIVN contributed `+99.81` bps from two probes and SOUN contributed `+61.08` bps from
three probes. RKLB had zero probes because its price did not pass the legacy sizing rule.

## 4. Controlled ranked configuration

`ranked_opening_ladder` is the cleaner controlled presentation. It narrows the active window to
`09:35-10:00 ET`, selects the top two symbols by opening score, and permits the configured setup
families. Its four trades returned `+61.28` total net bps with a `75%` win rate.

The lower PnL does not contradict the legacy result. The legacy configuration answers which
reproduced variant had the best raw PnL. The ranked configuration asks what remains after tighter
selection and controls.

## 5. Bad benchmarks

The extended opening benchmark returned `-104.53` total net bps across six trades. The all-day reuse
benchmark returned `-395.12` total net bps across 24 trades. These results support the narrow
opening focus and argue against repeated setup reuse throughout the day.

## 6. Symbol-level interpretation

The legacy run concentrated its positive contribution in RIVN and SOUN. In the controlled ranking
workflow, RKLB technically qualified but ranked below the active symbol cutoff. That distinction is
useful: a qualifying diagnostic is not automatically an instruction to allocate a probe.

## 7. Setup-family interpretation

The legacy high-PnL configuration intentionally permits the imbalance family only. The controlled
ranked version evaluates imbalance, spread-compression, and pullback-reclaim families under a
tighter selection rule. Family-level results should be treated as descriptive for this sample, not
as evidence of a stable production edge.

## 8. Pair-trade appendix

The strategy comparison preserves the research-only pair appendix summary: 13 rows, `-1099.46`
total bps, `-84.57` average bps, and a `15.4%` win rate. The row-level pair CSV is empty after the
current legacy rerun, so the plot displays this preserved summary rather than a histogram. The
appendix result is not proposed as a primary strategy.

## 9. Limitations

This is a small, offline historical sample. It does not establish out-of-sample persistence,
production fill quality, capacity, or live execution behavior. The simulated paper probes use
configured costs and historical MBP-10 features. Results may change across sessions, symbols,
market regimes, and cost assumptions.

## 10. Next work

The next research step is date-based out-of-sample evaluation across additional sessions while
keeping the named configurations fixed. The report should track stability by date, symbol, setup
family, spread regime, and cost assumption before any broader conclusion is made.
