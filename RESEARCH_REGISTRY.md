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
| C1 | London/NY opening-range breakout **and** fade (one family) | **KILLED 2026-07-09** (gold primary; breakout gross +0.028R but net −0.044R cost-dominated, fade no edge) | dev expR ≤ 0 after costs on XAUUSD primary, **zero added filters** → stop |
| C2 | Overnight / session-holding premium | **KILLED 2026-07-09** (gold H1 dev, all 5 windows expR<0) | net expectancy ≤ 0 after costs over full dev history → stop (no regime-gate rescue unless pre-registered) |
| C3 | Post-news drift/fade (FOMC/NFP/CPI) | **KILLED 2026-07-09** (gold M15; best fade/2h gross PF 1.15 but net −0.161R, worst cost drag 0.227R) | edge exists only inside the spread-blowout window → stop |
| C4 | ATR-pctile-gated channel breakout | **run + KILLED 2026-07-09** (gold H1 net −0.039R; frozen-param 15-symbol basket OOS N=5221 net −0.086R/PF0.78/t−6.69) | none (benchmark); deploy only if it wins outright |

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

- **C1 primary — KILLED 2026-07-09 (development, gold M15 2004→2024-01).**
  Pre-registered 12-config grid, both branches fail the kill line on the primary:
  - **breakout** best NET expR **−0.044R** (buf0.5, session_end, n=8087, win 42%,
    reliably <0 at t≈−4). Valid session-hold test (median hold 5.8h, 78% exit at
    session end). Gross/net decomposition: **GROSS +0.028R / PF 1.07** → cost drag
    0.072R → **NET −0.044R / PF 0.85**. i.e. a *small real edge that costs eat* —
    cost-dominated, same story as C2. Per the pre-registered line (expR ≤ 0 after
    costs) this is a KILL; no rescue (no cost-engineering tweak may be added to
    C1 — that would be a NEW hypothesis needing its own pre-registration).
  - **fade** best NET expR −0.238R, PF 0.40–0.58 — no edge. KILL.
  - **Stop-convention correction (audit trail):** the first grid run used a
    1×M15-ATR stop and was INVALID/degenerate — median hold 0.25–0.5h, ~80%
    noise-stopped in ~2 bars (a micro-scalp, not a session hold); those 12 entries
    were purged (a scale bug, not a hypothesis test). Stop corrected BEFORE any
    valid result to a **structural, session-scaled** stop (breakout: far side of
    the Asian range; fade: beyond the failed-break extreme). Holdout untouched.
  - Because the pre-registered PRIMARY (gold) fails, C1 is closed without needing
    the secondary-set backfill; the breakout's positive-gross/cost-negative result
    is logged as a pointer for any future *low-cost-execution* hypothesis (limit
    entry at the range) — which would be separately pre-registered, not a C1 rescue.

- **C4 benchmark — net-negative on gold H1 (development), best GROSS edge found.**
  Donchian break + ATR-pctile gate, chandelier trail, gold H1 dev 2004→2024-01.
  Best config L55/no-gate: NET **−0.039R / PF 0.885** (win 34%, n=2193); the vol
  gate made it worse (−0.072R). Gross/net: **GROSS +0.076R / PF 1.208** → drag
  0.115R → net −0.039R. This is the **largest gross edge in the whole project**
  (> C1 breakout 1.07, > C2 ~1.0, > QM) yet still (a) fails PF≥1.3 even frictionless
  and (b) is cost-dominated to net-negative. Benchmark did its job: the best trend
  signal on gold does not clear costs.

## Low-cost-execution thread — DEAD ON ARRIVAL (2026-07-09)
Prompted by C1 breakout's positive gross, asked: can limit/stop entry cut cost enough
to net-clear? **No — the gross (zero-cost) ceiling across all breakout configs is PF
≤ 1.074**, far below the 1.3 bar. Gross bounds net from above and in-sample bounds
OOS; a frictionless ceiling that fails cannot be rescued by execution. Closed without
building a limit-order simulator (saved a large wasted effort).

- **C4-basket — KILLED, powered (2026-07-09).** Frozen gold C4 params (L55, no gate)
  across 16 symbols H1 dev, 15 non-gold = OOS-by-symbol. **Pooled OOS N=5221, net expR
  −0.086R, PF 0.779, win 33%, t=−6.69** (effective-N ~2017 — NOT a power issue). Only
  USDJPY +0.005 / GBPJPY +0.05 net-positive (marginal); cheaper-cost symbols did NOT
  clear (BTC −0.008, US30 −0.077, USTEC −0.0 — lower cost → ~flat, not positive). Even
  gross PF mostly <1.2. Kill line HIT decisively. Breadth + lower cost cannot manufacture
  the edge; the trend-follow-on-this-universe line is closed with high confidence.

## SYNTHESIS (2026-07-09) — gold intraday appears efficient to these families
Four strategy families now tested on gold M15/H1 — QM reversal, session premium (C2),
opening-range breakout (C1), channel trend-follow (C4). **Gross edges span PF 1.0–1.21;
NONE clears the PF≥1.3 acceptance bar even frictionless, and gold's round-trip costs
(0.07–0.12R drag) turn all of them net-negative.** The pattern is consistent and
decision-relevant: standard technical edges on gold M15/H1 are real but too small to
clear retail costs.

**CONFIRMED at scale (2026-07-09):** the C4-basket test (option "breadth + lower cost")
was run — frozen trend-follow across 16 symbols, **N=5221 OOS, net −0.086R, PF 0.78,
t=−6.69**. Breadth and cheaper-cost symbols did NOT rescue it.

**ALL FIVE candidate families are now tested and killed (2026-07-09):** QM reversal,
C1 opening-range breakout, C2 session-premium, C4 channel trend-follow, C3 post-news
drift/fade. **Uniform result: gross edges span PF 1.0–1.21 (none clears the PF≥1.3 bar
even frictionless), and costs turn every one net-negative** — worst of all for C3, whose
edge lives in the widest-spread window (gross 1.15, cost drag 0.227R). The C4-basket
result makes this powered (t=−6.69), and the gross-ceiling logic shows more data/breadth
cannot rescue any of them. **Conclusion (high confidence): this liquid FX/metals/index/
crypto universe at M15–H1 is efficient relative to retail transaction costs; no standard
technical or event-driven strategy family clears them.** Only lower-prior scraps remain
(C4 on D1: lower cost but low N + heavily arbitraged). The reusable engine/infra is best
pointed at a fundamentally different approach — lower-frequency, structural-counterparty,
or new-data (all a G5 conversation) — or the technical search is concluded here.

## C4-basket — pre-registration (frozen BEFORE first backtest, 2026-07-09)
**Hypothesis:** the C4 trend-follow gross edge (gold H1 PF 1.208) net-clears on a
lower-cost, broader basket where it cannot on gold alone — breadth multiplies N and
several symbols have lower cost/ATR than gold (H1: BTC 0.09, US30 0.13 vs gold 0.15).
**Frozen params (from gold, NO per-symbol tuning):** L=55, pctile band (0.0,1.0)
[no vol gate — it was worse on gold], chandelier trail 3×ATR, ATR period 21. TF = H1.
**Symbol set (pre-registered):** metals+FX-majors/crosses {XAU,XAG,EURUSD,GBPUSD,
USDJPY,AUDUSD,USDCAD,NZDUSD,EURJPY,GBPJPY,USDCHF,EURGBP} + lower-cost trend set
{BTCUSD,US30,USTEC,USOIL}. Gold = in-sample reference; the other 15 are OOS-by-symbol
(params came from gold). Per-symbol COST calibration only (spread/slippage/swap +
scaled spread_cap). Development slice only; holdout (2024-01-09) sealed.
**Kill line (pre-registered):** pooled OOS (15 non-gold) net expR ≤ 0 OR net PF < 1.2
→ the trend-follow-on-this-universe line is closed (and with it, strong evidence that
no standard technical family clears costs on this universe). Report NET and GROSS
pooled, per-symbol table, cross-symbol monthly-R correlation, effective-N, acceptance
(net PF≥1.3, expR>0, no symbol >40% of PnL). **Status: registered.**

- **C3 post-news — KILLED 2026-07-09 (gold M15 dev, calendar 7660d8a96b3267e6).**
  Grid branch{drift,fade}×horizon{2h,6h}, 192 scheduled events 2018→2024-01. All 4
  net-negative: drift 2h −0.378R/PF0.43, drift 6h −0.307R/0.56, fade 2h −0.161R/0.75,
  fade 6h −0.209R/0.70. Best (fade 2h) valid (median hold 2.0h) — GROSS +0.066R/PF1.153
  but cost drag **0.227R** (the WORST of any candidate: news-window spreads are widest,
  exactly as the README/G4 warned) → net −0.161R. Gross ceiling 1.15 < 1.3, so more N
  (basket) cannot rescue it (per-trade economics fixed). Low single-symbol N but the
  kill is on the gross-ceiling + structural-cost logic, not the sample. KILL.

## C3 calendar wired (2026-07-09)
`doc/us_high_impact_calendar_2018_2026.csv` (278 US high-impact events 2018→2026:
102 NFP, 102 CPI, 74 FOMC), **sha256 `7660d8a96b3267e6`** — logged per C3 run via
`research_gate.file_sha256`. Loader (`calendar/news.py`) adapted to the file schema
(`event`→`title`, `scheduled` bool, `event_code`/`note` preserved); `calendar_csv`
wired in `forwardtest_iter3_config.yaml`. Historical evaluation loads with
`scheduled_only=True` (drops the 3 emergency 2020 FOMC) and `as_of=<eval end>`
(drops future rows). **Oct-2025 has no NFP/CPI report by design** (federal shutdown;
the file carries only the delayed Sep-2025 CPI on Oct-24 + the scheduled Oct FOMC —
no imputed first-Friday event); code must not impute them. Dev window (2018→2024-01,
scheduled) = 192 events → ~32/yr on gold alone, so C3 power is thin single-symbol.

- **C4-D1 — pooled KILLED, but a different animal (2026-07-10).** Frozen C4 on D1,
  16-symbol basket, 15 non-gold OOS. Pooled OOS **N=531, net −0.054R, PF 0.846,
  t=−1.45** → kill line hit (equal-weight universe), so the pre-registered test is
  closed and the technical search is CLOSED per the plan. BUT two honest differences
  from the H1 death: (1) **NOT powered** (t=−1.45, ~35 trades/symbol) — this is
  "not distinguishable from zero", not H1's decisive t=−6.69; (2) **cost wall is
  GONE** — on D1 gross≈net (drag ~0.01–0.06R), exactly as **G8 predicted** (nice
  confirmation the gate is real). The pooled negative is driven by an **asset-class
  split**: trend-follow is positive on the trending classes — USOIL +0.357/PF2.18,
  BTC +0.234/PF1.68, gold +0.225/PF1.88(IS), GBPJPY +0.104/PF1.31 (several clear the
  1.3 bar) — and negative on the range-bound FX majors (EURUSD −0.256, AUDUSD −0.199,
  USDCAD −0.209, EURGBP −0.226). **DISCIPLINE: do NOT declare "trend works on crypto/
  commodities."** Per-symbol N~27–42 is far too low; the winners may be the same
  small-sample tail that has burned this project repeatedly, and post-hoc asset-class
  selection is textbook snooping. It is a POINTER only: a trend-follow restricted to
  trending classes on D1+ is a legitimately NEW hypothesis needing its own
  pre-registration AND a D1 data extension for real N — not a rescue of C4-D1.

## G8 — cost-ceiling gate (paper, mandatory before any implementation)
Derived from the powered negative result (see `TECHNICAL_SEARCH_CONCLUSION.md`).
For the candidate's TF/symbol/stop: `cost_drag_R ≈ cost_per_ATR / s` (cost_per_ATR
from `output/scope_metrics.csv`: gold M15 0.29, H1 0.15, D1 ~0.03, news ×~2;
s = stop in ATR). PASS only if the mechanism can credibly deliver, ON PAPER:
`gross_expR ≥ 3 × cost_drag_R` AND implied `gross PF ≥ 1.5` (equivalently: expected
gross favorable excursion ≥ 3 × round-trip cost). Empirically nothing on this universe
at M15/H1 exceeded gross PF 1.21 / +0.076R, so any intraday-technical retail-spot idea
FAILS G8 on paper — don't build it. The only ways to pass: lower-cost regime (D1+, or
futures venue) or a materially larger gross edge (real structural counterparty).

## C4-D1 — pre-registration (closing experiment, 2026-07-10)
Passes G8 by construction (D1 cost_drag_R ~0.01R vs C4 gross +0.076R). **Frozen params
identical to C4-basket** (L=55, no vol gate, chandelier 3×ATR, ATR 21) — TF = **D1**,
same 16-symbol set, per-symbol cost calibration only, gold = IS ref / 15 non-gold =
OOS-by-symbol, development slice only, holdout sealed. **Kill line:** pooled OOS net
expR ≤ 0 OR net PF < 1.2 → the technical search is FULLY closed. Report NET+GROSS
pooled, per-symbol, correlation, effective-N, acceptance. **Status: registered.**

## Rules (carried from the QM post-mortem)
- No rescue filters on a failing in-sample result.
- One config basket-wide (or pre-registered groups metals vs majors); no per-symbol tuning.
- Walk-forward OOS judged per-window (≥30 OOS/window), never stitched-total vs the bar.
- Never touch the holdout early — not even "just to check."
- Label every in-sample number as in-sample.
- Convergent discoveries (e.g. C1-fade ≡ C3-fade on the same trades) are ONE registry hypothesis.
