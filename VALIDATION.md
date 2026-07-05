# VALIDATION.md — staged rollout and acceptance criteria

The rollout below operationalizes the strategy file's systematization plan
(Part II: Appendix B backtesting methodology, Appendix C forward-testing
protocol, Appendix E acceptance criteria, Appendix G kill-switches). **No
phase may be skipped, and each phase's gate must be met before advancing.**

## Phase 0 — Specification & unit correctness (done in this repo)

- All Appendix A definitions implemented as pure functions of closed bars;
  ambiguities resolved conservatively and logged in `DECISIONS.md`.
- Anti-lookahead test suite green: swings emit only at `i+R`; HTF bars
  invisible until closed; future-data mutation tests; determinism test.
- Cost model tests green (spread, stop slippage, worst-case sequencing, gaps).

**Gate:** `pytest` fully green. ✔

## Phase 1 — Full-cost historical backtest (Appendix B)

- Run `gold-qm backtest` on ≥ 3 years of the broker's own entry-TF data with
  the full cost model (never mid-price/zero-cost).
- Inspect the journal: do entries/exits land where a human reading the chart
  would place them? Spot-check ≥ 20 trades manually.

**Gate:** the system trades as specified (qualitative), and there are enough
trades to analyze (≥ 100 preferred over the full history).

## Phase 2 — Robustness (Appendix B.6–B.9)

- `gold-qm walkforward --windows 6 --oos 0.25` — **report OOS results only.**
- `gold-qm sensitivity --perturb 0.2` — no COLLAPSED flags on core parameters.
- `gold-qm ablation` — each retained layer must add expectancy or reduce risk,
  not merely shrink the sample (Appendix I.2).
- Review per-regime/per-session breakdowns: an edge that exists only in one
  regime needs an explicit regime filter, not a blended average.

**Gate (Appendix E, tune to taste):**
| criterion | minimum |
|---|---|
| OOS profit factor | ≥ 1.3 |
| OOS expectancy after full costs | > 0 R |
| OOS trade count | ≥ 30 |
| Max drawdown | within personal tolerance (≤ config `max_total_dd`) |
| Sensitivity | no collapse at ±20% |

## Phase 3 — Forward test / paper (Appendix C)

- `gold-qm forwardtest` against a real-time demo feed, **exact same code path**.
- Duration: ≥ 60 trading days **or** ≥ 30 qualifying trades, whichever is later.
- Compare forward expectancy, win rate and realized fill divergence vs the
  backtest's modeled slippage (`fill_divergence.csv`).

**Gate:** forward-test results not materially worse than backtest; realized
slippage within the modeled envelope. A significant gap means the execution
assumptions are wrong — fix the cost model and return to Phase 1.

## Phase 4 — Micro-live

- Implement + test a real `BrokerAdapter` and `BarFeed`; start with the
  **minimum viable size** (`sizing.risk_pct` at 0.25–0.5%).
- All kill-switches armed (they are not optional): daily −2R / −3%,
  4-consecutive-loss pause (manual review to resume), spread/vol breaker,
  −15% equity-floor hard stop.
- Run ≥ 1 month; reconcile every fill against the journal daily.

**Gate:** live fills match paper within tolerance; no kill-switch design
surprises; discipline holds (every trade traceable to the rules).

## Phase 5 — Scale-up

- Increase `risk_pct` stepwise (0.5% → 0.75% → 1.0% maximum per Part I §7.5),
  only after each step shows a stable month.
- Re-run Phase 2 quarterly on rolling data; if OOS acceptance fails on fresh
  data, de-risk back to Phase 3.
- Never exceed the portfolio risk cap (12.5%) or loosen a stop. Ever.

---

**Standing rule:** any code change to signal, risk or execution logic resets
validation to Phase 1. The one shared code path makes this cheap; use it.
