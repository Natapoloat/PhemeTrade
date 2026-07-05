# gold-qm-system

A rule-based **XAUUSD (gold)** trading system implementing the Quasimodo /
smart-money strategy specified in [`Gold_Trading_Strategy.md`](Gold_Trading_Strategy.md)
(Part II, Appendices A–I, is the authoritative engineering spec). Built as an
explicit **event-driven** engine with anti-lookahead guarantees at every layer.

> ## ⚠️ Backtest ≠ live — read this first
> This is **research/testing software, not financial advice**. A positive
> backtest — even one that survives walk-forward, sensitivity and ablation
> testing — does **not** imply live profitability. Costs, slippage, broker
> behavior and regime change can erase any modeled edge. Trading gold CFDs/
> futures with leverage can lose more than your deposit. Follow the staged
> rollout in [`VALIDATION.md`](VALIDATION.md); never skip the forward test.

## What makes this implementation defensible

- **No lookahead, by construction.** Swings emit only at `i+R` (repaint-safe
  fractals); the strategy consumes *only* closed entry-TF bars and builds its
  own higher-TF bars incrementally, so an unclosed H1/H4 candle can never leak
  into a decision. Signals fire at bar close; fills happen at the *next* bar's
  open. Dedicated anti-lookahead tests mutate future data and assert past
  decisions are bit-identical.
- **One code path.** Backtest, paper (forward test) and live all run the same
  `QMStrategy` through the same `_run_core` event loop — only the bar source
  and the `BrokerAdapter` differ.
- **Realistic costs.** Session-dependent spread, base + stop-fill + news
  slippage, commission, swap (triple-swap day), worst-case intrabar
  sequencing (stop always fills before target inside one bar), gap fills at
  the worse open.
- **Risk before signals.** Three-method sizing (`final = MIN(risk, vol,
  margin)`), in-trade risk/volatility ceilings with exact trims, a portfolio
  risk cap, and four kill-switches wired into the engine.

## Install

```bash
# Python 3.11+ required
python -m pip install -e ".[dev]"
python -m pytest             # 108 tests should pass
```

## Supplying data

Put per-timeframe OHLCV files in a directory, named `<SYMBOL>_<TF>.csv` or
`.parquet`, e.g. `data/XAUUSD_M5.csv`. Only the **entry timeframe** (default
`M5`) is required — coarser TFs are built internally. CSV columns:

```
open_time (or timestamp/time/datetime), open, high, low, close[, volume]
```

Timestamps are the bar **open** time; naive timestamps are assumed UTC.
Prefer your own broker's historical feed (gold differs across venues,
Appendix D). Optionally supply an economic calendar CSV
(`timestamp_utc,impact,currency,title`, see `examples/economic_calendar_sample.csv`)
and point `news.calendar_csv` at it.

## Expect very few trades — by design

The full layer stack (HTF bias ∧ fresh QM ∧ Fib∩QML confluence ∧ price-action
trigger ∧ session ∧ news ∧ regime) is extremely selective; on structureless
synthetic data it can legitimately produce zero trades over months. Use
`gold-qm ablation` to see where candidates die in the funnel, and heed
Appendix I.2: a tiny sample proves nothing. Note one deliberate conservatism:
a QML whose first retest happens during a *disallowed session* is consumed
(stale) — the system never trades a second retest (Part I §4.2.5).

## Configuration

Every strategy threshold lives in YAML — see [`sample_config.yaml`](sample_config.yaml),
which carries the Appendix A–G defaults. **They are starting values to be
validated, not sacred numbers.** Interpretation choices for every ambiguous
spec point are logged in [`DECISIONS.md`](DECISIONS.md).

## CLI

```bash
# historical backtest with full costs -> report.md + equity PNG + journal.csv
gold-qm backtest --config sample_config.yaml --data ./data --from 2020-01-01 --to 2024-12-31

# rolling in-sample optimize / out-of-sample validate; ONLY OOS numbers are reportable
gold-qm walkforward --config sample_config.yaml --data ./data --windows 6 --oos 0.25

# ±20% parameter sweep; flags parameters whose removal collapses performance
gold-qm sensitivity --config sample_config.yaml --data ./data --perturb 0.2

# marginal contribution of each layer: structure-only -> +QM -> +Fib -> +PA -> SFP split
gold-qm ablation --config sample_config.yaml --data ./data

# paper trading on a streaming feed (CSV replay or your own BarFeed factory);
# logs intended-vs-actual fills and slippage divergence
gold-qm forwardtest --config sample_config.yaml --feed ./data/XAUUSD_M5.csv --speed 1

# LIVE - off by default; requires an explicit risk acknowledgment AND a broker
# adapter + real-time feed that YOU implement and test
gold-qm live --config sample_config.yaml \
    --broker my_broker_pkg.adapter:MyBroker --feed my_broker_pkg.feed:make_feed \
    --i-understand-the-risk
```

(Or `python -m gold_qm_system.cli ...` without installing the entry point.)

## Going live

No real broker adapter ships with this package — deliberately. To trade live:

1. Implement `gold_qm_system.execution.BrokerAdapter` for your venue
   (including the per-bar `process_bar` fill-sync method) and a `BarFeed`
   yielding **closed** entry-TF bars.
2. Complete the full rollout in [`VALIDATION.md`](VALIDATION.md) — including
   ≥ 60 trading days / ≥ 30 trades of forward testing whose fills do not
   diverge materially from the backtest's cost model.
3. All kill-switches (daily loss, consecutive-loss pause, spread/volatility
   breaker, equity floor) are enforced by the engine in every mode.

## Architecture

```
gold_qm_system/
  config/       pydantic schema — every Appendix A–G threshold, from YAML
  data/         loaders, UTC normalization, no-lookahead HTF aligner, spread table
  indicators/   ATR (EMA form), RSI, repaint-safe fractal swings (+ incremental forms)
  structure/    market-structure state machine (bias, BOS/CHoCH/MSS)
  patterns/     QM detector (freshness lifecycle), Fib zone, pin/engulf/inside-bar, SFP, CPLQ
  risk/         MIN-of-three sizing, stop/target builder, ongoing ceilings, portfolio cap
  engine/       incremental HTF aggregator, QMStrategy, shared backtest/feed runners
  execution/    SimBroker (costs/fills), BrokerAdapter interface, kill-switches
  calendar/     economic-calendar news blackout (CSV-backed)
  metrics/      Appendix E stats + per-session/per-regime breakdowns
  reports/      Markdown report + equity/R-distribution PNGs
  journal/      auto trade journal (Part I §9 fields incl. binding sizing method)
  tests/        108 tests: anti-lookahead, sizing, patterns, costs, determinism, CLI
  cli.py        backtest | walkforward | sensitivity | ablation | forwardtest | live
```
