# Build Prompt — Gold (XAUUSD) QM Trading System
### For: Claude Code CLI running the Fable 5 model
### How to use: place `Gold_Trading_Strategy.md` in the project root, then paste everything below (from "PROMPT START") into Claude Code.

---

## PROMPT START

You are building a production-grade, **rule-based XAUUSD (gold) trading system** in Python. The authoritative specification is the file **`Gold_Trading_Strategy.md`** in this repository — read it in full before writing any code. **Part II (Appendices A–I) is the unambiguous engineering spec and overrides Part I wherever they conflict for automation purposes.** Do not invent trading logic that isn't traceable to that file.

### Prime directive (read twice)
This is a discretionary "smart-money"/Quasimodo strategy whose concepts (swings, fresh QML, Over/Under, compression) are naturally defined *in hindsight*. **The #1 failure mode is lookahead / repainting bias.** Your entire architecture must guarantee that every decision at bar `t` uses information available **only through the close of bar `t`**. If you are ever unsure whether something leaks future data, stop and add a test. A system that looks profitable in backtest because it peeked is worse than useless.

### Tech stack
- Python 3.11+, `pandas`, `numpy`, `pydantic` (config), `pyyaml`, `pytest`, `matplotlib` (reports), `rich` or `click`/`typer` (CLI). Avoid heavyweight vectorized backtest libs that hide fill logic — build an explicit **event-driven** engine so fills and lookahead are fully controlled. You may use `backtesting.py` ONLY if you can prove no-lookahead; otherwise roll your own event loop.
- Keep the **backtest and the live/paper runner sharing the same signal-generation code path** — this is non-negotiable (see Appendix C/H).

### Architecture
Follow the layout in **Appendix H** of the spec (`config/ data/ indicators/ structure/ patterns/ risk/ engine/ execution/ calendar/ metrics/ journal/ reports/ tests/ cli.py`). Every threshold from Appendix A–G must live in a YAML config, not be hard-coded.

### Implement, in this order (commit after each, with its tests passing):

1. **Data layer** (`data/`): load OHLCV CSV/Parquet for multiple timeframes (M1/M5/M15/H1/H4/D1), normalize to UTC, and provide a **no-lookahead multi-timeframe aligner**: at a lower-TF timestamp, a higher-TF bar's values are visible only if that HTF bar has already closed (Appendix B.3). Support a session-dependent spread table (Appendix D).

2. **Indicators** (`indicators/`): ATR (EMA form per Part I §7.2), RSI, and a **repaint-safe fractal swing detector** — a swing at bar `i` is emitted only at bar `i+R` (Appendix A.1). Expose `swing_strength`.

3. **Structure state machine** (`structure/`): HH/HL/LH/LL, `bias` state (Bullish/Bearish/Ranging), and BOS/CHoCH/MSS transitions per Appendix A.2. Pure function of closed bars.

4. **Patterns** (`patterns/`): QM detector (points 2→3→4→5, QML, Over/Under, freshness, tolerances — Appendix A.3), Fib entry-zone confluence (A.4), price-action triggers (pin/engulfing/inside-bar — A.5), SFP booster (A.6), and compression/CPLQ detection.

5. **Risk module** (`risk/`): the three sizing methods (risk %, volatility %, margin %) and **`final_size = MIN` of the three** (Part I §7.2). Implement ongoing/in-trade risk ceiling and volatility ceiling (§7.3), and the total-portfolio-risk cap (§7.4). Stops/targets per Appendix A.7.

6. **Execution sim** (`execution/`): realistic fills — spread, base + news + stop-fill slippage, commission, swap, worst-case intrabar sequencing for wick trades (Appendix D, B.5). Define a `BrokerAdapter` interface so a real broker can be plugged in later without touching signal code.

7. **News/calendar filter** (`calendar/`): pluggable economic-calendar source; enforce the `news_blackout` window (Appendix D). Ship with a CSV-backed stub the user can populate.

8. **Engine** (`engine/`): one event-driven core with two runners — `backtest` (historical) and `paper/live` (streams bars in real time from a feed). Same signal path.

9. **Metrics & reports** (`metrics/`, `reports/`): expectancy (R), profit factor, max DD + duration, Sharpe, Sortino, Calmar/MAR, R-multiple distribution, trade count/month, modeled-vs-realized slippage, and **per-regime + per-session breakdowns** (Appendix E, F). Output an equity-curve PNG and an HTML/Markdown report.

10. **Journal** (`journal/`): auto-log every trade with the fields in Part I §9 plus which sizing method was binding.

### CLI (`cli.py`) — required subcommands
- `backtest --config <yaml> --data <dir> --from <date> --to <date>` → full stats + report.
- `walkforward --config <yaml> --windows <n> --oos <fraction>` → rolling in-sample optimize / out-of-sample validate; **report OOS only** (Appendix B.6).
- `sensitivity --config <yaml> --perturb 0.2` → ±20% parameter sweep, flags overfitting (B.7).
- `ablation --config <yaml>` → marginal contribution of each layer: structure-only → +QM → +Fib → +price-action → +SFP (B.8). This is important: the layered filter stack risks tiny samples.
- `forwardtest --config <yaml> --feed <source>` → real-time paper trading against a demo feed; logs intended vs actual fills and slippage divergence (Appendix C).
- `live --config <yaml> --broker <adapter>` → same path as forwardtest but real orders; must respect all kill-switches (Appendix G). Default this OFF / require an explicit `--i-understand-the-risk` flag.

### Kill-switches (Appendix G) — wire into engine, not optional
Daily loss limit, consecutive-loss pause, spread/vol circuit breaker, equity-floor hard stop. Live and paper runners must honor them.

### Tests (`tests/`) — write these FIRST where possible (TDD for the risky parts)
- **Anti-lookahead tests:** feed a series where a future spike would change a past decision; assert the decision is unchanged. Assert swings never emit before `i+R`. Assert HTF values are never visible before HTF bar close.
- **Sizing test:** assert `final_size == min(risk, vol, margin)` across cases; assert portfolio cap trims correctly.
- **Pattern tests:** hand-crafted QM sell/buy fixtures (valid, invalid-order, stale-QML) → correct labels.
- **Cost test:** assert costs reduce PnL and stop-fill slippage applies on stop exits.
- **Determinism test:** same data + config ⇒ identical results.

### Deliverables
1. Working package with all subcommands and passing `pytest`.
2. A `README.md`: install, how to supply data, how to run each subcommand, and a clear **"Backtest ≠ live" disclaimer**.
3. A `sample_config.yaml` populated with the Appendix defaults.
4. A short `VALIDATION.md` documenting the intended Phase 0→5 rollout (from the strategy file's transition plan) and the acceptance criteria in Appendix E.

### Working style
- Read `Gold_Trading_Strategy.md` fully first; restate your build plan and the parameter list you extracted before coding.
- Small, tested commits. If a spec item is ambiguous, choose the **most conservative, no-lookahead** interpretation and note the assumption in a `DECISIONS.md`.
- Never fabricate performance numbers. If asked to "show results," run the engine on whatever data is present or clearly state that data is required.
- Add the disclaimer that this is software for research/testing, not financial advice, and that a positive backtest does not imply live profitability.

## PROMPT END
