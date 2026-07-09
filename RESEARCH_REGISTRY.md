# Research Hypothesis Registry (G7 multiple-comparisons hygiene)

The 21.6-year gold set and the ~4–8y basket have already absorbed many QM
iterations; their p-values are **not innocent**. Every configuration run against
the data — including abandoned ones — is logged so results can be read with a
multiplicity-aware discount. Machine log: `research/registry.jsonl` (append-only,
via `gold_qm_system.research_gate.log_run`).

## Holdout freeze (write-once)
- **Cutoff: 2024-01-09 UTC.** Data on/after this instant is the **sealed holdout**
  (most-recent ~2.5y across all symbols). Off-limits to ALL experiments until a
  candidate has passed walk-forward on the development remainder. Evaluated
  **once, last, pass/fail, per strategy class.** Enforced by `research_gate.split_bars`.
- Development remainder by market: gold M15 ~2004→2024-01 (~19.6y); basket H1
  ~2018→2024-01 (~6y); basket M15 ~2022→2024-01 (**~1.5y — too thin; prefer H1**).

## Candidates
| id | class | status | kill criterion (pre-registered) |
|----|-------|--------|----------------------------------|
| C1 | London/NY opening-range breakout **and** fade (one family) | **pre-registered 2026-07-09** (frozen grid + symbols + kill line below); not yet run | dev expR ≤ 0 after costs on XAUUSD primary, **zero added filters** → stop |
| C2 | Overnight / session-holding premium | **KILLED 2026-07-09** (gold H1 dev, all 5 windows expR<0) | net expectancy ≤ 0 after costs over full dev history → stop (no regime-gate rescue unless pre-registered) |
| C3 | Post-news drift/fade (FOMC/NFP/CPI) | registered — **blocked on calendar data** | edge exists only inside the spread-blowout window → stop |
| C4 | ATR-pctile-gated channel breakout | registered — **benchmark** | none (benchmark); deploy only if it wins outright |

## Verdicts
- **C2 — KILLED 2026-07-09 (development, gold H1 2004→2024-01, long-only).** 5
  pre-registered session-hold windows, all net-negative after costs:
  overnight(21→7) −0.217R/PF0.33, asian(0→7) −0.056R/PF0.84, london(7→16)
  −0.141R/PF0.81, ny(13→21) −0.103R/PF0.82, day(7→21) −0.154R/PF0.82; n≈4.3–5.0k
  each (~220–255/yr — G1 crushed). Even the least-bad window is decisively <0
  (t≈−3.3). The gap-risk-premium lost the spread-vs-drift race exactly as the
  brief predicted C2 might. No rescue attempted (do-NOT list). Shakedown success:
  the rails run non-QM logic correctly (verified after fixing a metrics gap where
  the new `time_exit` reason was dropped from `_FULL_EXITS`). Holdout untouched.
  - **Closed in BOTH directions — no sign-flip shorts.** Gross (zero-cost)
    decomposition on the same dev set: gross expR = +0.062/+0.052/−0.003/+0.063/
    +0.034 (overnight/asian/london/ny/day) vs cost drag 0.11–0.28R. The edge is
    **cost-dominated**: gross drift is near-zero and slightly *positive* for long,
    so a sign-flipped short is gross-*negative* AND pays the identical round-trip
    cost → strictly worse, not a rescue. No directional session premium to harvest
    either way; C2 is fully closed.

## C1 — pre-registration (frozen BEFORE first backtest, 2026-07-09)
**Family:** London/NY session-open behavior — **breakout AND fade as ONE hypothesis
family, two branches** (a convergent trade in both branches is one hypothesis, not two).
**Mechanism (G2):** session opens concentrate flow; Asian-range stop clusters sit
just outside the range; fixing/hedging execute at fixed times. Breakout branch =
genuine flow initiation beyond the range; fade branch = stop-run exhaustion on the
first failed break. The data decides which (if either) survives costs.
**Signal:** Asian range = [0,7) UTC (fixed session convention). At London open
(07:00 UTC): breakout = enter in break direction beyond range±`buffer_k`×ATR; fade
= enter against the first bar that pokes beyond range±`buffer_k`×ATR then closes
back inside. Exit per `exit_mode`. NY open (13:00) included as the same rule.
**Frozen grid (G3 — 2 free params + the branch split; ATR period, session bounds
are fixed conventions, never tuned):**
- `branch` ∈ {breakout, fade}
- `buffer_k` ∈ {0.0, 0.25, 0.5} (ATR)
- `exit_mode` ∈ {session_end, fixed_2R}
→ 12 configs/symbol. No parameter outside this grid; no added filters.
**Symbol set (pre-registered, no per-symbol tuning):** primary **XAUUSD** (gold M15,
21.6y); secondary **USDJPY, US30, USOIL** (the G4 cost-viable set). Gold M15 is the
primary because non-gold M15 dev depth is thin until the Max-bars backfill lands.
**Kill line (numeric, pre-registered):** development (in-sample) expR ≤ 0 after full
costs on the **primary (XAUUSD)** with **zero added filters** → that branch is
killed. No filter-stacking to rescue (do-NOT list).
**Mandatory reporting when C1 runs:** raw N **and** effective-N (adjust for
cross-symbol correlation: N_eff ≈ N / [1 + (m−1)·ρ̄], ρ̄ = mean pairwise daily-PnL
correlation across the symbol set); the **cross-symbol daily-PnL correlation
matrix**; per-session/per-window breakdown; development sample only; holdout sealed.
**Status: registered, NOT yet run.**

## Rules (carried from the QM post-mortem)
- No rescue filters on a failing in-sample result.
- One config basket-wide (or pre-registered groups metals vs majors); no per-symbol tuning.
- Walk-forward OOS judged per-window (≥30 OOS/window), never stitched-total vs the bar.
- Never touch the holdout early — not even "just to check."
- Label every in-sample number as in-sample.
- Convergent discoveries (e.g. C1-fade ≡ C3-fade on the same trades) are ONE registry hypothesis.
