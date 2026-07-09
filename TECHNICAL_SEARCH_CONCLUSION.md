# Technical-Strategy Search — Powered Negative Result & the G8 Cost-Ceiling Gate

*2026-07-10. Companion to `RESEARCH_REGISTRY.md` (per-run log) and the QM retirement
(`Gold_Trading_Strategy.md` Part VI). All figures tagged in-sample (IS) / OOS.*

## 1. What was tested

After the QM (Quasimodo reversal) concept was retired, the strategy-agnostic engine
was pointed at four further standard families, each **pre-registered** (frozen grid,
symbol set, numeric kill line) before its first backtest, each judged on
development data with the 2.5-year holdout (≥ 2024-01-09) sealed throughout:

| family | mechanism | where run |
|---|---|---|
| QM | liquidity-grab reversal | gold M15 (21.6y) + 20-symbol scan |
| C1 | London/NY opening-range **breakout + fade** | gold M15 (primary) |
| C2 | overnight / session-holding premium | gold H1 |
| C4 | ATR-gated Donchian **trend-follow** (benchmark) | gold H1 + **16-symbol basket** |
| C3 | **post-news** drift/fade (FOMC/NFP/CPI) | gold M15 (event-triggered) |

## 2. The result — uniform, and powered

Every family, measured gross (zero-cost) and net (full modeled costs) on the same
discipline:

| family | best GROSS PF | GROSS expR | NET expR | verdict |
|---|---|---|---|---|
| QM (Iter3) | — | — | +0.115 **IS** → −0.04 **OOS** | died OOS |
| C2 session-premium | ~1.00 | +0.05 | −0.056 | killed |
| C1 opening-range | 1.07 | +0.028 | −0.044 | killed |
| C4 trend-follow (gold H1) | **1.21** | +0.076 | −0.039 | killed |
| C4 trend-follow (**basket, N=5,221**) | — | — | **−0.086, t = −6.69** | killed (powered) |
| C3 post-news (fade/2h) | 1.15 | +0.066 | −0.161 | killed (worst cost) |

**Three facts hold across all five families:**
1. **Gross edges are real but small** — profit factor spans **1.00–1.21**. None clears
   the Appendix-E acceptance bar (PF ≥ 1.3) *even frictionless*.
2. **Costs turn every one net-negative.** Measured round-trip cost drag: 0.07R (C1
   M15 structural stop) → 0.115R (C4 H1) → **0.227R (C3, news-window — the widest
   spreads)**. In every case the drag exceeds the gross edge.
3. **It is not a small-sample artifact.** The C4 frozen-param basket pooled **5,221
   out-of-symbol OOS trades** (effective-N ~2,000) at **t = −6.69**; and the
   gross-ceiling argument (below) shows that more data or breadth cannot rescue a
   family whose *frictionless* PF is already < 1.3.

**Conclusion (high confidence):** on this liquid FX / metals / index / crypto universe
at M15–H1 timeframes, **no standard technical or event-driven strategy family produces
an edge large enough to clear retail transaction costs.** The universe is efficient
*relative to these costs*. This is the project's second powered retirement (QM was the
first; this is the broader intraday-technical family).

## 3. G8 — the cost-ceiling gate (derived from the above)

The five deaths share one cause: the **round-trip cost is large relative to the gross
edge**. That relationship is measurable *on paper*, so it becomes a pre-implementation
gate. **All future candidates must pass G8 before any code is written.**

### 3.1 The cost model, in R-units
From `scripts/scope_metrics.py` (`output/scope_metrics.csv`), for a symbol/timeframe:

```
cost_per_ATR = round_trip_cost_price / median_ATR(TF)         # measured
round_trip_cost_price ≈ 3 × spread_px  (entry 1.5×spread + blended exit ~1.5×spread)
```
A strategy risks `R = s × ATR` per trade (s = stop distance in ATR). Therefore the
**cost drag in R-multiples** is:
```
cost_drag_R  ≈  cost_per_ATR / s
```
Measured anchors (gold): **M15 cost_per_ATR ≈ 0.29, H1 ≈ 0.15, D1 ≈ 0.03**
(D1 ATR ≈ 5× H1 ATR); **news-window ≈ 2× base**. These reproduce the observed drags
(C1 0.07R, C4 0.115R, C3 0.23R).

### 3.2 The gate
Net expR = gross expR − cost_drag_R, and IS overstates OOS. So a candidate PASSES G8
only if its mechanism can credibly produce, **on paper**:

> **G8.a**  `gross_expR ≥ 3 × cost_drag_R`   (net ≥ ~2× drag → OOS margin), **and**
> **G8.b**  implied `gross PF ≥ 1.5`   (empirically nothing here exceeded 1.21; the
> 1.3 *net* bar needs gross well above it), **and**
> **G8.c**  equivalently in price: expected gross favorable excursion per trade
> `≥ 3 × round_trip_cost_price`.

### 3.3 What G8 implies (and the only two ways to pass it)
Because `cost_drag_R = cost_per_ATR / s` and the captured move grows with holding
horizon while cost is fixed per round trip, **G8 is a minimum-holding-period / maximum-
frequency constraint.** On this universe at M15–H1, cost_drag_R ∈ [0.07, 0.23], so G8.a
demands **gross_expR ≥ ~0.21–0.45R** — and the best any tested family reached was
+0.076R. That gap is *why they all died*, and it is the bar. There are exactly two
levers to clear it:

- **Lower-cost regime** — push cost_per_ATR down. Higher timeframe (gold **D1 ≈ 0.03**,
  ~10× cheaper than M15) or a **cheaper venue** (futures: XAU=GC, indices=ES/NQ, tighter
  spreads + no retail markup). On D1 the gate falls to gross_expR ≥ ~0.03–0.09R —
  achievable by a real edge.
- **Larger gross edge** — a mechanism with a genuine *structural counterparty*
  (carry, rebalancing/fixing flow, risk-transfer premia), not a price-pattern that any
  chartist can see and arbitrage to PF ~1.1.

Anything that is intraday-technical on retail spot **fails G8 on paper** — do not build it.

## 4. Closing experiment — C4 on D1 (run 2026-07-10)
C4 trend-follow on D1 was the one pre-registered test that **passes G8 by construction**
(cost_drag_R ≈ 0.01–0.06R). Result on the 16-symbol basket, 15 non-gold OOS:
**pooled N=531, net −0.054R, PF 0.846, t=−1.45 → kill line hit; the equal-weight
universe test is closed and the technical search with it.**

Two findings from it, both important:
- **G8 is confirmed.** On D1 gross ≈ net (cost drag collapsed exactly as the gate
  predicts); the M15/H1 deaths really were cost-driven, and D1 removes that wall.
- **The D1 death is not powered and not uniform.** t=−1.45 (vs H1's −6.69), and the
  pooled negative is an **asset-class split**: trend-follow is *positive* on the
  trending classes (USOIL +0.357/PF2.18, BTC +0.234/PF1.68, gold +0.225/PF1.88 IS,
  GBPJPY +0.104/PF1.31 — several clear the 1.3 bar) and negative on range-bound FX
  majors, which drag the equal-weight pool under water.

**Discipline:** this is a POINTER, not an edge. Per-symbol N is ~27–42 — far too low to
trust the winners, and selecting "the trending subset" post-hoc is textbook data
snooping (the exact failure mode retired QM's early "positives"). A trend-follow
restricted to trending asset classes on D1+ would be a **new, separately pre-registered
hypothesis** requiring a D1 history extension for real N — not a rescue of C4-D1.

## 5. Where the search stands
The technical search is **closed**: five families, all pre-registered, all killed on
their pre-registered lines. The next scope decision is a deliberate **G5-level** change,
chosen not casually:
- **Venue economics** — re-run the *same* engine on **futures** data/costs (GC/ES/NQ/CL):
  tighter spreads lower cost_per_ATR, which G8 says is one of the only two levers. The D1
  trending-asset signal would be the first thing to test there, properly pre-registered.
- **A daily-plus macro/carry thesis** — a mechanism with a real structural counterparty
  (the other G8 lever), which typically needs new data (rates, curve, positioning).
All future candidates must clear **G8 on paper first**.
