# DECISIONS.md — spec ambiguities resolved (most conservative, no-lookahead interpretation)

Each entry records a point where `Gold_Trading_Strategy.md` was ambiguous for
automation, and the interpretation chosen. Spec references in parentheses.

1. **Swing emission timestamp (A.1).** A swing at bar `i` becomes *known* at the
   close of bar `i+R`. All downstream consumers (structure, QM) receive the swing
   event stamped with `confirmed_at = i+R`, and may only act from bar `i+R+…`
   onward. Ties (equal highs inside the window) do NOT confirm a swing — we
   require a strict maximum/minimum, the conservative reading of "is the maximum".

2. **"Last two SH/SL" for bias (A.2).** Bias needs at least 2 confirmed SH *and*
   2 confirmed SL. Before that, bias = Ranging (no trades that require bias).
   The Ranging tie-break uses ATR as of the moment the later swing was
   *confirmed*, not formed — no future ATR. "Last SH/SL differ by less than
   `range_atr_mult*ATR`" is read as: Ranging when BOTH `|ΔSH| < tol` AND
   `|ΔSL| < tol` (both sides flat = a range; a one-sided flat with the other
   side expanding is still resolved by the ascending/descending rule, which
   already requires BOTH sides to agree for a trend).

3. **"Major swing" for MSS (A.2).** "A swing that itself produced a BOS" is read
   as the ORIGIN swing of the breaking impulse: when a BOS occurs in an uptrend
   (close > last confirmed SH), the most recent confirmed SL before that break
   becomes the *major low* (the impulse that broke the high originated from it).
   MSS = close beyond the current major swing against the old trend; this flips
   `bias` on that bar close. Mirror for downtrends. CHoCH = first close beyond
   the most recent confirmed counter-side swing since the last BOS; the CHoCH
   flag re-arms after each new BOS.

4. **QM point ordering (A.3).** Points 2/3/4/5 must be strictly time-ordered by
   their swing bar index (not confirmation index), but the pattern only becomes
   *tradeable* at max(confirmed_at) of its constituent swings — i.e., only when
   point 5 (Under) is itself a confirmed swing. `qm_lookback` is measured from
   point-2 bar to point-5 bar on the setup TF.

5. **Freshness (A.3).** The freshness clock starts at the bar where the pattern
   became tradeable (point-5 confirmation). Bars between point-5 *formation* and
   its *confirmation* are inspected retroactively at confirmation time: if price
   already re-entered the QML band in that gap, the level is born stale (we could
   not have traded it anyway — conservative).
   `qml_tol` uses ATR at pattern-confirmation time and is then FROZEN for the
   life of that pattern, so the band cannot repaint as ATR changes.

6. **Fib leg (A.4).** For a sell QM, the Fib leg is Over-high → Under-low; the
   entry window prices are `under_low + fib * (over_high - under_low)` for
   fib ∈ [0.618, 0.786]. Entry zone = intersection of that price band with the
   frozen QML band; if the intersection is empty the setup is discarded.

7. **Bar-close decisions, next-bar fills (B.1).** Signals are evaluated strictly
   on the close of entry-TF bar `t`; market entries fill at the open of `t+1`
   (plus spread/slippage). No same-bar signal+fill.

8. **Worst-case intrabar sequencing (B.5).** If both stop and target lie inside
   one bar's range, the STOP is assumed to be hit first, always (we have no tick
   data). If entry-bar open gaps beyond the stop, fill at the (worse) open price.

9. **HTF visibility (B.3).** An HTF bar stamped `T` (bar-open convention) with
   period `P` is visible at LTF timestamp `t` only if `T + P <= t_close`, where
   `t_close` is the close time of the LTF bar being processed. Implemented via
   `merge_asof` on HTF *close* timestamps.

10. **Sizing edge cases (Part I §7.2).** If the margin method is not configured
    (`margin_per_unit == 0`), it is treated as non-binding (infinite). If the
    computed final size < `min_size`, the trade is SKIPPED (never rounded up).
    `size_step` rounds DOWN only.

11. **Ongoing risk ceiling (§7.3).** "Open risk" of a position = size × distance
    from current close to current stop (≥0), as a fraction of current equity.
    When it exceeds `ongoing_risk_ceiling`, trim exactly enough size to return to
    the ceiling. Same mechanic for the ATR-based volatility ceiling. Checked on
    entry-TF bar closes.

12. **Daily loss in R (App. G).** 1R = the per-trade risk in currency at entry
    (size × stop distance). Daily realized R is summed over trades *closed* that
    UTC day. Both R- and %-based daily limits halt NEW entries only; existing
    positions keep their stops/targets.

13. **Counter-trend trades (Part I §2.3.2 / App. F).** A QM whose direction
    opposes the directional-TF bias is only taken if the *setup-TF* structure has
    printed an MSS in the trade direction, and `allow_countertrend_on_mss: true`.

14. **Sessions (App. F).** Session filter applies to NEW entries only, evaluated
    at the signal bar's close time (UTC hour). Exits are always allowed.

15. **News blackout (App. D).** Blackout = [event − N min, event + N min]. Both
    the *signal* bar close and the *expected fill* time (next bar open) must be
    outside the blackout. The news-spike-fade exception (Part I §2.2.3) is NOT
    implemented as an automated setup — deliberately out of scope v1 (it lacks
    an unambiguous Appendix A definition; noted as future work).

16. **Compression / CPLQ (A.5, Part I §4.4).** Compression = `compression_bars`
    consecutive bars each with true range ≤ `compression_shrink` × prior bar's
    true range. CPLQ is flagged when compression completes while price is inside
    the QML band. Both are conviction *boosters* (journal/analysis flags), not
    entry gates, in v1 — mirroring SFP's role in A.6.

17. **Engulfing simplification of QM on the directional TF (A.3 last bullet)**
    is implemented as a booster/annotation only, not a substitute setup, in v1.
    The full 2→5 structure is required for entries. Conservative: fewer setups,
    no ambiguity about what "a supply/demand zone" means numerically.

18. **RSI (Part I §2.3.5)** is computed and journaled but is NOT an entry gate
    (spec: "supportive, never sufficient"). Exposed for future filters.

19. **Equity for sizing** = account cash + realized PnL (closed-trade equity).
    Unrealized PnL is excluded from the sizing base (conservative; avoids
    pyramiding on open profits) but IS included in the drawdown/kill-switch
    equity curve (conservative in the other direction: breakers see the worst).

20. **CHoCH early-exit (Part I §8.2)** — "consider closing early" is
    discretionary language; v1 implements it as a config-less always-on rule:
    if the setup-TF prints a CHoCH against an open position, the position is
    closed at the next bar open. Simple, testable, and traceable to §8.2.

21. **ATR formula (Part I §7.2).** The spec's literal text — "ATR = Yesterday's
    ATR + (Expo. Avg Factor × Today's True Range)" — omits the EMA decay term
    and would grow without bound. Implemented as the standard EMA recursion the
    source (Basso) clearly intends: `ATR_t = ATR_{t-1} + k·(TR_t − ATR_{t-1})`,
    `k = 2/(N+1)`, seeded with `ATR_0 = TR_0`. Causal; prefix-consistency is
    enforced by test.
