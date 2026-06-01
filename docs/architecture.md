# Opening Trading Boost Architecture

Opening Trading Boost is an offline Databento L2 opening warmup layer that can improve broader
trading research strategies by deciding which symbols are worth activating near the open.

```text
existing historical L2 inputs
        |
        v
feature construction
        |
        v
opening setup detection
        |
        v
offline warmup and ladder simulation
        |
        v
CSV reports, memo, notebook, and plots
```

The research path has no broker adapter and no live-order path. Simulation rows are paper-only
diagnostics. The ordinary workflow reads existing local inputs and does not call Databento.
