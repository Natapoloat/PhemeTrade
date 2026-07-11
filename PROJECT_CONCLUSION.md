# PhemeTrade — Final Project Conclusion (Powered Negative Result)

*2026-07-10. The definitive deliverable. Companions: `RESEARCH_REGISTRY.md` (per-run log),
`TECHNICAL_SEARCH_CONCLUSION.md` (technical-family detail), `Gold_Trading_Strategy.md`
Part VI (QM retirement). Every figure is tagged in-sample (IS) / OOS / dev / holdout.*

## Verdict

**No strategy tested — across reversal, breakout, session, trend, post-news, carry, and two
calendar anomalies — produces an edge that survives out-of-sample after realistic Exness
retail costs.** Several deaths are *statistically powered*, not small-sample shrugs. The
project concludes as a **powered negative result**: on this broker, at these timeframes and
asset classes, retail-cost systematic trading of the ideas in scope is not viable. The
engine, data pipeline, cost model, validation harness, and the G8 framework are the durable
output.

## 1. Headline — the powered nulls

| test | design | result |
|---|---|---|
| **C4 trend, 15-symbol frozen basket** | out-of-symbol OOS, N=5,221 | net −0.086R, **t = −6.69** |
| **H4 trend, robust crypto/energy/index basket** | powered + uncontaminated, N=736 | net +0.004R, PF 1.01, **t = +0.09** |
| **Crypto weekend calendar** | pre-registered, drift-neutral, N=132 | excess **t = −1.80**, sign **flipped** pre/post-2022 |
| **Turn-of-month, 5-index basket** | pre-registered, drift-neutral, N=81 | excess **t = +0.63**, all 3 gates fail |

These are not "we didn't look hard enough." At N=736–5,221 the trend nulls are decisive; the
calendar nulls fail their pre-registered sign-consistency gates because the effects **decayed
or reversed** post-2020. The remaining families died on cost ceilings or paper logic.

## 2. The full narrative

1. **QM (Quasimodo reversal)** — the original system. In-sample +0.115R looked promising;
   walk-forward OOS −0.04R, and a frozen-config 20-symbol out-of-symbol basket confirmed no
   edge. Retired (Part VI).
2. **Four technical families**, each pre-registered, holdout sealed: **C1** opening-range
   breakout+fade, **C2** session premium, **C4** channel trend-follow, **C3** post-news
   drift/fade. Gross profit factors spanned **1.00–1.21 — none clears 1.3 even frictionless**;
   costs turned every one net-negative. C4's frozen 16-symbol basket made it powered (t=−6.69).
3. **Trend lever, best-powered version.** Chased to H4 (short holds → low swap, ~3.4× the
   trades → N=736, powered) and it was **null (t=+0.09)**. Swap-free (Lever 1) couldn't rescue
   it — gross was already only ~1.1.
4. **Three structural theses** (stopping rule: max three, pre-register only paper-passers):
   - **Carry** — paper-killed. Every FX pair's best harvestable carry ≤ 0.00%/yr; the broker
     zeroes the favorable swap side and charges −1.8…−4.3%/yr the other. Markup = 100% of the
     rate differential.
   - **Crypto weekend calendar** — paper-passed all four gates (cost/session/power/clean), then
     **dev-failed**: weekend excess reversed sign pre→post-2022.
   - **Turn-of-month (indices)** — the last shot; **dev-failed on all three gates**, effect
     essentially absent 2018–2024 (secular decay).

## 3. The G8 cost-ceiling framework (durable methodological output)

The single most reusable result. Before any implementation, a candidate must clear, **on
paper**, using the measured cost model:

```
cost_drag_R = ( round_trip_spread + swap_per_night × hold_nights ) / ( s × ATR(TF) )
PASS only if  gross_expR ≥ 3 × cost_drag_R   AND   implied gross PF ≥ 1.5
```

- `cost_per_ATR` (spread only): gold M15 0.29, H1 0.15, **D1 ~0.03**; news-window ×~2.
- **Overnight financing is the dominant cost for multi-night holds**, not spread — and it is
  strongly hold-length- and direction-dependent (see §4). G8 must include it.
- Empirically nothing on this universe at M15/H1 exceeded gross PF 1.21, so **any
  intraday-technical retail-spot idea fails G8 on paper.** The two escape levers are a
  lower-cost regime (D1+, or a cheaper venue) or a materially larger gross edge (a real
  structural counterparty). Both were pursued; neither delivered.

## 4. Venue / microstructure findings (Exness retail)

- **Swap-mode bug (material).** Exness reports `swap_mode == 1` (POINTS); the cost code applied
  swaps only for `== 0` (DISABLED). So **every backtest, including the promising C4-D1 run,
  charged ZERO overnight financing.** Fixed. Correct swaps demote gold and US30 from the
  D1-trend universe and were essential to an honest verdict.
- **Carry side is zeroed.** Exness pays 0.00%/night on the carry-favorable direction of every
  FX pair and charges punitively on the other — the retail markup consumes 100% of the policy-
  rate differential. There is no carry premium to harvest on this broker.
- **The D1 swap wall.** At 15–20-night trend holds, financing (gold −0.49/nt, BTC −12.5, US30
  −9.5 on the long side) is 0.03–0.16R of drag. Short-hold strategies (H4 ~3nt, turn-of-month
  ~3nt) sidestep it; multi-night trend holds do not.
- **Crypto is 24/7** on Exness (BTC/ETH weekend bars present) → weekend exposure is holdable,
  and crypto's large ATR dwarfs the swap (so cost is *not* crypto's binding constraint — the
  edge is).

## 5. Methodology & integrity

- **One shared signal path** for backtest/forward/live; no vectorized shortcut that could
  disagree with live behavior. 138 anti-lookahead/unit tests green throughout.
- **Write-once holdout** (2024-01-09, most-recent 2.5y sealed) enforced in code.
- **Append-only hypothesis registry** with per-run logging and file-hash pinning (calendar).
- **Pre-registration** of every structural thesis: fixed window, two-sided direction with
  pre/post sign-consistency gates, economic *and* statistical kill lines, pooled-basket
  verdicts with per-symbol salvage pre-declared invalid, and pre-committed outcome handling.
- **Contamination discipline:** drift-neutral (excess-over-baseline) designs so a known bull
  (crypto) could not masquerade as a calendar edge; verdicts on sealed data.
- **The D1-trend holdout was NEVER spent** — its dev/underpowered version was superseded by the
  powered H4 null, so the sealed shot was preserved rather than wasted on an underpowered
  confirmation. It remains sealed permanently, barring genuinely new information.

## 6. Boundary conditions — what this result does and does NOT cover

Explicitly **out of scope**; a negative here is not a claim about these:
- **Venues other than Exness retail spot.** Futures (GC/ES/NQ/CL) have tighter spreads, no
  punitive retail swap, and deeper history — G8 could reopen ideas there. Futures was held as
  a *venue to layer under a paper-passer*, never itself a thesis; no paper-passer survived, so
  it was never scoped.
- **Sub-M15 / intrabar / tick / order-book strategies.** All testing was M15 and coarser; HFT/
  microstructure is a different data and latency regime, untested.
- **Non-price data.** Fundamentals, flow/positioning, on-chain, options surface, alternative
  data — none used. Every thesis here was price/calendar/swap only.
- **Discretionary trading.** This concerns *systematic, codeable* rules exclusively.

## 7. Reusable assets (the engine outlives the strategies)

Strategy-agnostic and proven: event-driven no-lookahead backtester + shared live/forward feed;
no-lookahead HTF resampling; per-symbol calibrated cost model (spread + correct swaps + triple-
swap convention); walk-forward / sensitivity / ablation harness; MT5 data pipeline; write-once
holdout + registry; the G8 paper gate; metrics/journal/reporting. Only `patterns/` +
`strategy.py`-equivalents are idea-specific. Any future thesis (new venue, new data class)
plugs into all of the above.

## 8. Final verdict

The disciplined, powered conclusion is that **the space of price-, calendar-, and carry-based
systematic strategies reachable on Exness retail at M15–D1 has been searched and is
efficient relative to retail costs.** Reopening the search requires a deliberate, out-of-scope
change — a different **venue** (futures) or a different **information source** (non-price data)
— scoped fresh through the G8 gate and the pre-registration protocol. Until such a change, the
project stands complete: a rigorous, reproducible, powered negative result, with the holdout
sealed and the infrastructure ready for the next genuinely different idea.

## 9. Addendum — the two reopenings were tried and closed (2026-07-11)

Both G8 exits named in §8 were pursued under full discipline. Both closed.

- **Exit (a) — venue change to futures.** Blocked at the **capital-granularity gate (Phase 0)**:
  running the frozen basket at ≤1% risk with 1-contract granularity across ≥4 uncorrelated
  markets needs ≈ **$284k** (binding = micro gold at current levels); available capital falls
  short. And even if funded, the prior was weak — the swap-mode bug meant the trend backtests
  were *already* zero-financing, and the closest analog (H4 trend, no-FX subset) was a powered
  null (t=+0.09) with gross PF ≤ 1.21. Venue change removes cost it had already (accidentally)
  removed; it does not create an absent gross edge.
- **Exit (b) — non-price information (Phase 3, 3-slot budget).** **Closed 2 dead + 1 reserved:**
  *Carry* — paper-killed (broker zeroes the favorable swap side; 100% markup). *Brent–WTI RV* —
  paper-killed (two-leg cost ≫ G8 on a low-vol spread). *COT positioning* — passed cost/lookahead/
  data (real CFTC 2006–2026 acquired, hashed) but **failed the honest power gate**: only **100
  non-overlapping crude+gold trades over 17y**, well below the 200–450 band. *VRP* — venue-blocked
  (no options on Exness). Slot 3 is **RESERVED, not spent**, behind gate **G9** (daily-or-better
  non-overlapping cadence with effective-N in-band **first**, non-price counterparty, G8-passing).

**Standing posture: screen-and-wait, not search.** The default allocation is **passive**. Nothing
is traded, and no further scoping is opened, unless a candidate clears G9 up front and then a full
pre-registration → sealed holdout → forward test. Correction on record: an earlier claim of a
2025 CFTC/COT publication gap was **wrong and retracted** — that shutdown affected BLS releases,
not the COT series, which is unbroken 2006–2026.
