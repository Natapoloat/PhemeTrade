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

## D1+ lever, Step 1 — swap-aware cost model + G8 recompute (2026-07-10) → PASS (pruned)
**Bug found:** Exness reports `swap_mode == 1` (POINTS) for all symbols, but the cost
code applied swaps only for `swap_mode == 0` (DISABLED) → **every backtest, C4-D1
included, charged ZERO overnight financing.** Fixed (`==1`) in c4_basket + portfolio_backtest.
**Swaps are the dominant D1 cost** (spread ~0.01R; swap 0.03–0.16R over a hold).
`scripts/swap_g8_scope.py` (`output/swap_g8_scope.csv`): cost_drag_R(H) = [3·spread +
swap/night·H]/(3·ATR_D1); G8 ceiling 0.10R (needs gross ≥0.30R at 3×). Actual C4-D1
median holds = 15–20 nights (p75 25–28), direction ~52–68% long. Verdict at real holds:
- **Robust** (pass at median & p75): **BTC, ETH (crypto); USOIL, UKOIL (energy); JP225
  (index, zero swap).**
- **Marginal** (pass at median, FAIL beyond ~12n): **gold (be 12n vs 18n hold), US30
  (be 11n vs 16n)** — gold, a C4-D1 "winner", is demoted once financing is charged.
- **Fail at 10n:** silver, US500, USTEC, UK100 (high swap/ATR).
**Step 1 PASSES with a pruned universe** (~5 robust + 2 marginal). NOT killed — but the
robust core is small and within-class correlated (crypto, energy), a power caveat for
Steps 2–3. Recorded C4-D1 net (−0.054R) was swap-FREE and is therefore optimistic;
Step 3's pre-registered run will apply correct swaps.

## D1+ lever, Step 2 — depth + power math (2026-07-10)
D1/H4 reach 2018 without any Max-bars change (only M15 was capped). Dev depth (pre
2024-01-09): D1 ~1000–1840 bars/symbol; H4 ~4250–6440. **Power wall:** measured D1
trades ~25–38/symbol → robust core (5) ≈ 159 dev trades (~110 effective after
crypto/energy within-class correlation). Trend σ ≈ 1.7R ⇒ need n ≈ 447 (μ=0.20R) /
286 (0.25) / 198 (0.30) to separate the edge from zero. **D1-only is UNDERPOWERED**
(~110–160 « 200–450); holdout adds ~75, forward ~30/yr. H4 would give ~3–4× the N
(→ powerable) but needs its own Step-1 G8 with H4 costs — DEFERRED, not smuggled in.
Consequence for Step 3: dev cannot confirm; the verdict must rest on the sealed
holdout + forward test + cross-symbol consistency, and may honestly return
"insufficient power on Exness D1" → venue/vehicle change.

## D1+ lever, Step 3 — pre-registration: "D1 trend, asset-class basket" (2026-07-10)
**NEW hypothesis, frozen before any strategy code.** Mechanism/universe chosen by
**ex-ante rationale** (trend/time-series-momentum premium is documented in commodities,
equity indices, crypto — negative-skew risk-transfer; FX majors are carry/range, not
trend → **excluded**), intersected with the Step-1 swap-cost survivors:
- **Robust universe (primary):** BTCUSD, ETHUSD, USOIL, UKOIL, JP225.
- **Marginal group (reported separately, hold-monitored):** XAUUSD, US30 — swap-marginal
  (break-even ~11–12 nights vs 16–18 night holds); included only to watch, not to rescue.
- **Out:** all FX majors/crosses (literature) + silver/US500/USTEC/UK100 (failed G8).
**Frozen params (no re-tune):** Donchian L=55, no vol gate, chandelier 3×ATR trail,
ATR(21), TF = **D1**. **Sizing fixed ex-ante:** risk 0.5%/trade, stop = 3×ATR ⇒ size
∝ 1/ATR (vol-scaled, equal risk per trade). **Costs:** per-symbol spread + **correct
swaps (mode-1 fix)**, spread_cap scaled. H4 explicitly deferred to its own gate.
**Kill line:** pooled robust-core, swap-inclusive — net expR ≤ 0 OR PF < 1.2 → the
Exness D1 lever is closed. Given underpower, ALSO require majority of robust-core
symbols net-positive (no single-symbol fluke).
**CONTAMINATION NOTE (mandatory):** we have already seen the C4-D1 split (crypto/energy/
gold looked positive). Development/in-sample is therefore CONTAMINATED and is NOT
evidence. **The verdict rests solely on the sealed 2.5y holdout (evaluated once, last)
+ a forward test**, plus cross-symbol consistency. If those are inconclusive (likely,
given the power math), the honest verdict is "no demonstrable D1 edge reachable on
Exness" → next is venue (futures) or vehicle change. **Status: registered, not built.**

## D1+ lever, Levers 1+2 (2026-07-10) — swap regimes + H4 G8
`scripts/cost_regime_g8.py` (`output/cost_regime_g8.csv`). Cost model parameterized per
symbol/TF: swap regime ∈ {full | zero (swap-free) | fee_after(N_free, fee/night)}. Holds
MEASURED per TF via frozen C4 (gross, dev-only) — returns NOT inspected on H4, so H4 edge
stays sealed.

**Lever 1 (swap-free eligibility, D1):** decisive. Under FULL swap 18/21 pass (gold/US30
marginal at ~0.09R; US500/USTEC/UK100 fail). Under ZERO swap **21/21 pass** (D1 spread-only
= 0.007–0.056R). So if the account is swap-free on the instruments, the D1 cost constraint
essentially vanishes and the full universe re-enters. `max_fee_after3` column gives the
largest after-3-night daily fee each symbol can absorb and still pass — plug the account's
real terms in to decide. (A fee_after backtest would need a SimBroker cost extension;
deferred until a regime is chosen.)

**Lever 2 (H4 G8, correct swaps):** H4 holds are SHORT (2.1–4.5 nights) → swap/trade
collapses → **19/21 pass under full swap** (fail only XAG 0.130, UK100 0.127); robust core
all pass (BTC 0.020/ETH 0.026/USOIL 0.032/UKOIL 0.050/JP225 0.015), gold 0.053, US30 0.058.
H4 dev trades ~96–118/symbol → robust core **~539 dev trades** (vs D1 ~159), ~3.4× → the
power wall is SOLVED on H4. H4 returns were NOT inspected → uncontaminated.

## H4-trend — pre-registration DRAFT (2026-07-10; awaiting sign-off, not built)
A FRESH hypothesis (not a port of D1-trend): H4 channel-breakout trend, own params/kill line.
- **Mechanism:** intermediate-term (≈week) breakout/time-series-momentum on trend-bearing
  classes; same risk-transfer rationale, faster horizon than D1.
- **Frozen params (ex-ante, H4-native — NOT the D1 L55):** Donchian **L=30** H4 bars (~5
  trading days), chandelier trail 3×ATR(H4), ATR(21), no vol gate. **Single config, no grid**
  (avoid multiplicity on the powered data). [L=30 flagged for user sign-off.]
- **Universe:** PRIMARY (full-swap-safe) = **{BTCUSD, ETHUSD, USOIL, UKOIL, JP225}**;
  CONDITIONAL on swap-free confirmation (Lever 1) expand to {XAUUSD, US30, US500, USTEC}.
  OUT: XAG, UK100 (fail H4 G8), FX (literature).
- **Sizing (fixed ex-ante):** risk 0.5%/trade, stop 3×ATR ⇒ vol-scaled equal risk.
- **Costs:** per-symbol spread + correct swaps (mode-1) + parameterized regime (full for
  primary; zero for the swap-free-conditional arm).
- **Kill line (own):** pooled primary net expR ≤ 0 OR PF < 1.2 → H4-trend closed; also
  require majority of primary symbols net-positive.
- **Power:** robust core ~539 dev trades (~372 effective after within-class correlation) ≥
  the ~200–450 needed (trend σ≈1.7R) → **POWERED**.
- **Contamination:** D1 per-symbol PnL was seen (C4-D1 split) but **H4 per-symbol PnL has
  NOT** — only holds/counts. So H4 dev is legitimate primary evidence (walk-forward), with
  the sealed 2.5y holdout as final confirmation. This is H4's key edge over the D1 shot.
- **Status: RUN + KILLED 2026-07-10 (dev, powered).**

## H4-trend — VERDICT: KILLED, powered + clean (2026-07-10)
`scripts/h4_trend.py`, primary universe, dev only, correct full swaps. **Pooled N=736,
net +0.0038R, PF 1.011, t=+0.09** — indistinguishable from zero. Per-symbol: BTC
+0.218/PF1.63, ETH +0.02/1.05, USOIL −0.074/0.78, UKOIL −0.16/0.58, JP225 −0.006/0.98
→ **2/5 net-positive**; kill line HIT (PF<1.2) and majority-positive FAILED. Even GROSS
the basket is ~PF 1.1 (BTC gross 1.89, ETH 1.2, rest <1.05) → swaps are not the killer;
**there is no H4 trend edge.** This is the powered (N=736, not D1's ~110), uncontaminated
(H4 PnL never pre-seen) test — the most trustworthy trend result — and it is NULL. The
lone BTC positive mirrors the D1 BTC number, i.e. the D1 "trending-asset split" was the
small-sample tail (5× the data on the same assets → edge vanishes). **D1 holdout NOT run
(dev failed → sealed shot preserved).** Swap-free (Lever 1) cannot rescue it (gross already
~1.1). CONCLUSION: the trend lever on the Exness spot universe, at its best-powered/lowest-
relative-cost version, has no edge → the Exness D1+ trend lever is effectively closed.
Remaining honest moves: futures (venue, pending capital-granularity check) or a
non-trend/structural-counterparty vehicle change.

## H4-trend — pre-registration (frozen spec, executed above)

## PROJECT STOPPING RULE (2026-07-10)
Structural-thesis phase after the technical search + trend lever closed. **Budget: at
most THREE structural theses paper-scoped.** Full pre-registration (and later code) ONLY
for a paper-passer (clears cost/G8 + frequency + a credible power path + a real
counterparty). Dead-on-paper theses do not consume the budget's "pass" slots but ARE
logged. **If all three die, the project concludes as a powered negative result and we
write it up as the final deliverable.** Futures is a VENUE option to layer under any
paper-passer — never itself a thesis. Theses so far: [1] carry (DEAD), [2] turn-of-month
(conditional — power-marginal), [3] crypto calendar (PAPER-PASS — strongest lead).

## Structural thesis 3 — CRYPTO CALENDAR / liquidity-cycle (BTC+ETH): PAPER-PASS
Day-of-week + weekend structure. Counterparty (G2): weekend/off-hours institutional
absence → retail-flow-driven liquidity-cycle mispricing that normalizes when desks return.
1. **Cost/G8 (correct swaps + triple-swap-day, R=2·ATR_D1):** crypto's huge ATR dwarfs the
   swap → PASS comfortably at 1–3n even long+triple: BTC 3n=0.054R, ETH 0.023R; short side
   ~0.014–0.018R. The swap wall does NOT bind on crypto (unlike metals/indices). Not the kill.
2. **Sessions:** BTC & ETH are **24/7** (Mon=Sat=Sun bar counts) → weekend exposure is
   HOLDABLE/continuous, not a gap trade; swaps accrue every night incl. weekends.
3. **Power:** BTC-ETH daily corr 0.83; per day-of-week ~262 weekly obs each → raw pooled
   ~525, effective N ≈ **307 (in the 200–450 band → POWERED full-sample)**. Pre/post-2022
   split ~154/half → sign-consistency check (not per-half significance). Best power of the
   three theses (vs ToM's ~79–118 monthly).
4. **Contamination:** crypto AGGREGATE returns were seen in trend runs (BTC positive; dev is
   60% pre-2022 = the 2020–21 bull), but calendar SLICES were not. **Design MUST be
   drift-neutral** — day-of-week EXCESS vs each asset's unconditional daily mean (or a
   long-short across days) — else it just re-discovers the BTC bull. Slice PnL unseen;
   verdict on sealed holdout + forward.
**Verdict: PAPER-PASS on all four gates (with the drift-neutral design constraint).**
Strongest structural lead. Eligible for full pre-registration.

### Crypto-calendar — pre-registration DRAFT (awaiting sign-off; not built)
Universe {BTCUSD, ETHUSD}. Primary rule (ex-ante liquidity rationale, single — no day-sweep):
the low-liquidity **weekend window** (Fri-close → Mon-open, ~2–3 nights), measured
**drift-neutral** (excess over unconditional daily mean). Vol-scaled 0.5%/trade, stop
2·ATR_D1, correct swaps. Kill line: pooled drift-neutral excess net expR ≤ 0 OR not
sign-consistent across the pre/post-2022 split → closed. Sign to be confirmed on dev
(powered) and locked before the sealed holdout. [weekend-window + drift-neutral flagged
for sign-off.] **Status: DRAFT.**

## Structural thesis 1 — CARRY: PAPER-KILLED (2026-07-10)
For each FX pair, actual Exness swap yield (mode-1) vs the policy-rate differential
(rates = mid-2026 ESTIMATE): **every pair's best harvestable carry ≤ 0.00%/yr.** Exness
zeroes the swap on the carry-favorable side (e.g. USDJPY theoretical +3.5%/yr → earn
0.00%) and charges −1.8% to −4.3%/yr on the other; markup = 100% of the differential.
No pair pays you to hold the high-yielder → **no carry premium exists on this broker.
Family closed.** (Does not consume a pass slot.)

## Structural thesis 2 — TURN-OF-MONTH (indices): paper-scope → CONDITIONAL pass
Counterparty (G2): scheduled month-end institutional flows (index/pension rebalancing,
inflows, window-dressing) → documented turn-of-month return concentration. Long-only,
3-night hold (last trading day → ~3rd of next month).
- **Cost/G8 (R=2·ATR_D1, cost=3·spread+swap_long·H):** at 3n ALL pass — US30 0.054,
  US500 0.084, USTEC 0.073, UK100 0.087, JP225 0.013R; at 5n US500/USTEC/UK100 fail.
  Short hold sidesteps the 15–20-night swap wall. **PASS at 3n.**
- **Frequency:** 12/yr/index; dev ~79 turns/index (JP225 62). Raw ~395 dev trades.
- **Power (binding caveat):** indices are ~0.8 correlated at month-end → one equity-beta
  bet sampled monthly → **effective N ≈ months (~79–118), not months×indices.** Adequate
  ONLY if the per-turn effect ≥ ~0.25R; the effect is known to have SECULARLY DECAYED →
  likely underpowered. NOT a clean pass.
- **Verdict:** conditional paper-pass (cost+freq ✓, power marginal). Eligible for a DRAFT
  pre-registration, but the effect-size/decay is the real gate; the honest verdict would
  rest on the sealed holdout + forward given effective N is monthly-limited.

### Turn-of-month — pre-registration DRAFT (awaiting sign-off; not built)
Universe {US30, US500, USTEC, UK100, JP225}; long at last-trading-day close, exit 3rd
trading day of next month; vol-scaled 0.5%/trade, stop 2·ATR_D1; correct swaps. Single
rule, no grid. Kill line: pooled net expR ≤ 0 OR PF < 1.3 → closed; require majority of
indices net-positive. Power caveat above front-and-center. Turn-of-month returns NOT yet
inspected → clean. **Status: DRAFT.**

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
