# Gold (XAUUSD) Trading Strategy — Master Reference

> Synthesized from: Liquidity_Rule.md, Market_Structure_Forex.md, Price_Action_Startrader.md, QM_Pattern.md, Qm Master.pdf, Quant Portfolio Management (Tom Basso), and Quantitative Investment Strategies thesis (Guo).
> Purpose: single reference document to design a rule-based (and eventually automatable) gold trading system. Review before building the system.

---

## 1. Trading Philosophy

1. **Price is the only truth.** Structure and price action lead; indicators (if any) are secondary confirmation only.
2. **You are either the smart money or you are the liquidity.** Every setup must answer: *"Whose stops am I trading with, and whose stops is the market trying to take?"*
3. **Trend + Structure + Liquidity + Price Action = Entry.** No single concept below is traded in isolation. A signal is only actionable when multiple layers align.
4. **Risk management is not optional bolt-on — it is 50% of the system.** A mediocre entry model with disciplined sizing beats a great entry model with undisciplined sizing.
5. **Gold-specific reality:** XAUUSD is a high-volatility, news-sensitive instrument (USD real yields, DXY, risk-on/risk-off flows, central bank policy, geopolitical shocks). It gaps, spikes, and runs stops more violently than most FX pairs. Treat every liquidity/stop-hunt concept below as *more* relevant to gold than to majors, not less. Widen expectations for wick length and false breaks accordingly.

---

## 2. Layer 1 — Market Structure (Directional Bias)

Market structure tells you what "normal" looks like, so that stop-hunts and fakeouts can be identified as abnormal.

### 2.1 Three Structure States
| State | Signature | Bias |
|---|---|---|
| **Bullish** | Higher Highs (HH) + Higher Lows (HL), each swing higher than the last | Look for **Buys** only |
| **Bearish** | Lower Highs (LH) + Lower Lows (LL), each swing lower than the last | Look for **Sells** only |
| **Ranging** | Swing highs/lows cluster at similar levels, no expansion | Range-trade: buy support, sell resistance — or stand aside |

### 2.2 Structure Shift Sequence
Structure breaks always evolve in this order — do not skip steps in your read:

1. **BOS (Break of Structure)** — price breaks the prior swing *in the direction of the existing trend*. Confirms trend continuation. Not a reversal signal.
2. **CHoCH (Change of Character)** — the first break *against* the prevailing trend structure (e.g., in an uptrend, price breaks below the most recent higher low). This is a warning, not a confirmed reversal.
3. **MSS (Market Structure Shift)** — a clean break of the prior *swing* low/high (not just a minor internal low), confirming the new trend direction. This is the trigger to start looking for entries in the new direction.

### 2.3 Multi-Timeframe Protocol (mandatory top-down flow)
1. **Daily/H4 (Directional TF):** Establish grand trend + mark Demand/Supply zones (Order Blocks) and the QM Level (see Layer 3).
2. **H1/M15 (Setup TF):** Confirm the smaller-TF structure agrees with the higher TF. Only trade with the higher TF unless you have an explicit, defined counter-trend/reversal setup (MSS-confirmed).
3. **M5/M1 (Entry TF):** Fine-tune entry using price action confirmation (Layer 4) inside the zone identified on H1.
4. **Common error to avoid:** Reading structure off insignificant micro-swings. Only use swings that actually mattered (i.e., that were followed by a real BOS) to define HH/HL/LH/LL — noise swings will scramble your bias.
5. Optional confirmation: RSI momentum agreement, or a simple candle pattern cluster (e.g., three same-colored bars) on the entry TF — supportive, never sufficient by itself.

---

## 3. Layer 2 — Smart Money / Liquidity Concepts

**Core idea:** Institutional players need liquidity (opposing orders) to fill large positions. They engineer price moves toward clusters of retail stop-losses (liquidity pools) before reversing in the intended direction.

### 3.1 Where Liquidity Sits
- **Buy-side liquidity:** above old highs / above resistance (where shorts' stops and breakout buy-stops cluster).
- **Sell-side liquidity:** below old lows / below support (where longs' stops and breakout sell-stops cluster).
- **Order Blocks:** the last opposite-colored candle(s) before a strong impulsive move — presumed zone of institutional order accumulation. Treat as a supply/demand zone for re-entry.

### 3.2 The Four Liquidity Traps to Recognize
1. **Stop-Hunt-then-Reverse:** Price spikes through a support/resistance level to trigger stops, then reverses hard in the original direction. Common right before genuine trend continuation.
2. **Fake Breakout:** Price appears to break a range boundary to pull in breakout traders, then snaps back inside the range with a long rejection wick.
3. **News Spike Fade:** A good/bad news print causes a sharp move that cannot hold — smart money uses the retail rush to offload into strength/weakness.
4. **Swing Failure Pattern (SFP):** Price makes a marginal new high/low but **fails to close beyond it**, leaving a long wick — a classic liquidity grab signature that precedes reversal. This is your highest-quality confirmation signal when it lines up with a QM level (Layer 3).

### 3.3 Warning Signs You're Watching the Trap Live
- Price moves too fast, with no supporting structure (no clean impulse-pullback rhythm).
- A sudden burst around a major news release that fails to sustain.
- A long-wicked candle appears right after a breakout — the market is rejecting the breakout level.

### 3.4 Practical Rule
**Never place a stop loss at the "obvious" round-number/swing level everyone can see.** Place it beyond the level with a buffer, or better, structure your entries (Layer 3/4) so your stop naturally sits *beyond* the liquidity pool rather than inside it.

---

## 4. Layer 3 — The QM (Quasimodo) Pattern — Core Setup Engine

QM is a reversal pattern (cousin of Head & Shoulders) distinguished by **asymmetric shoulders**: the structure is allowed to break the prior swing extreme (Lower Low in an uptrend / Higher High in a downtrend) — something classic H&S does not permit. This break is exactly the liquidity grab described in Layer 2.

### 4.1 Anatomy (Sell Setup — mirror for Buy)
1. Price rises to point **2** (Left Shoulder / "Bahu Kiri") → this level becomes the **QM Level (QML)**, valid only while "fresh" (untouched since formed).
2. Price pulls back to point **3** ("neck").
3. Price rallies again, breaking above point 2 to form a **Higher High** at point **4** (the "Head") → this is the **OVER**.
4. Price falls, breaking below point 3's low, forming a **Lower Low** at point **5** → this is the **UNDER**. (Over + Under = the defining QM signature.)
5. Price returns to retest the QML (same level as point 2) → this is the **entry zone**, point **6**.

> **Intermediate QM:** the same pattern but with a small internal double-top/bottom ("QMM" or **MPL — Maximum Pain Level**) sitting on the *same line* as the QML on a lower timeframe. When QML (higher TF) and MPL (lower TF) sit on the same price line, this is called a **"sharp entry"** — the highest-confidence version of the setup.
> **QM Shadow / CS Pattern:** on higher timeframes, simplify the pattern to just the candle bodies (ignore wicks) — the same Over/Under logic applies and is easier to spot on Daily/H4. A **Bullish/Bearish Engulfing candle** at the QML is a simplified, single-candle version of the whole QM structure (the engulfing candle's second candle = the "Over" or "Under").

### 4.2 Entry Technique
1. Identify Over (HH in downtrend context / — mirror for uptrend) and Under (LL) → confirms QM validity.
2. Wait for price to **retrace back toward the QML/MPL confluence zone**.
3. Use **Fibonacci retracement**, always drawn **left-to-right** (top of the relevant swing = 100, bottom = 0, or mirrored for sell setups).
4. **Entry zone = 61.8%–78.6% Fibonacci retracement**, ideally overlapping the QML/MPL level.
5. Only trade a QML that is still **"fresh"** (i.e., price has not already retested it once — a second retest is a materially lower-probability, higher-risk trade).

### 4.3 Stop Loss / Take Profit
- **Stop Loss:**
  - Sell: above the swing High (the "Over" / Head).
  - Buy: below the swing Low (the "Under").
- **Take Profit — three methods (use most conservative / most appropriate for context):**
  1. Target the origin of the opposite move — i.e., price returning to the next QML zone in the counter-direction.
  2. **Fixed Risk:Reward** — 1:2, 1:3, or 1:5 depending on conviction and structure quality.
  3. **Maximum TP** — the next major structural Resistance/Support (Layer 2 zone) before price made the QM pattern in the first place.

### 4.4 Advanced QM — Combine With Liquidity Confirmation
The highest-quality entries stack QM with Layer 2/3 confirmations:
- **Fakeout at/above the QM level** (price pokes through R1/R2/R3 test levels, then fails) — strongly increases entry conviction.
- **SR Flip** — an old resistance becomes new support (or vice versa) right at the QML.
- **Diamond pattern / Compression (CP)** — price coils into a shrinking range (compression) right before the retest — often precedes the sharpest move back through the QML.
- **CPLQ (Compression + Liquidity)** — compression forming directly beneath a supply zone / above a demand zone, right where buy-side or sell-side liquidity rests — the single best-documented "sharp entry" combination in the QM Master material.

**Remembrance checklist before every QM entry** (from source material, verbatim spirit):
> *"Wait for fakeout. Wait for Diamond/Compression. Wait for CPLQ. Look to the left (for the QML). Look for the MPL. Then you have an entry."*

---

## 5. Layer 4 — Price Action Confirmation Toolkit

Used to fine-tune entries at the QML/MPL/Fib zone identified in Layer 3, and to time entries around Order Blocks (Layer 2).

| Pattern | Signature | Use |
|---|---|---|
| **Pin Bar** | Long wick one side, small body, close on opposite end | Rejection at QML/zone → reversal signal |
| **Bullish/Bearish Engulfing (Outside Bar)** | Current candle's High/Low fully engulfs prior candle | Strong reversal confirmation at zone; also a simplified stand-alone QM signature |
| **Inside Bar (compression)** | Candle range fully inside prior candle's range | Consolidation/indecision; trade the breakout direction ("Follow Buy/Sell") once range is broken — pairs well with QM "Diamond/Compression" |
| **Up Bar / Down Bar** | Higher High+Higher Low (up) or Lower High+Lower Low (down) vs. prior candle | Simple momentum read, context only |

**Rule of thumb:** Reversal patterns (Pin Bar, Engulfing) are used *at the end of a trend leg*, i.e., exactly at the QML retest. Continuation/breakout patterns (Inside Bar sequences) are used when confirming a Compression/Diamond before the QM retest completes.

---

## 6. Putting It All Together — Entry Checklist (Top-Down Flow)

Run through in order. All must be satisfied before entry:

1. **[ ] Directional bias set** on Daily/H4 via Market Structure (Layer 1) — trading with the higher-TF trend unless explicit MSS reversal confirmed.
2. **[ ] QM pattern identified** on the setup TF (H1/M15): Over + Under confirmed, QML/MPL marked, level still fresh.
3. **[ ] Liquidity context confirmed:** Is the Over/Under a genuine stop-hunt into buy-side/sell-side liquidity? Any fakeout/SFP visible around the level?
4. **[ ] Price returns to the 61.8%–78.6% Fib zone**, ideally overlapping QML/MPL confluence.
5. **[ ] Price action confirmation** on entry TF (M5/M1): Pin Bar, Engulfing, or a completed Compression/Inside-Bar breakout in the expected direction.
6. **[ ] Stop loss defined** beyond the swing extreme (Over for sells, Under for buys) — never at the obvious round number itself; add a small buffer past the wick.
7. **[ ] Take profit defined** using one of the three TP methods (Layer 4.3), matched to a minimum 1:2 R:R.
8. **[ ] Position size calculated** per Section 7 before order is placed — never size intuitively.
9. **[ ] Macro/news filter checked** — no major USD/gold-moving release (FOMC, NFP, CPI) within the next candle or two unless the setup explicitly trades the news-spike-fade pattern (Layer 2.2 #3).

---

## 7. Risk & Money Management (Position Sizing)

> Adapted from Tom Basso's *Successful Traders Size Their Positions*. This governs **how much** to trade once Section 6 says **when/where** to trade.

### 7.1 Why This Matters
Entry signals only tell you direction and level. Profit = (exit price − entry price) × **position size**. A great entry with poor sizing still fails; disciplined sizing turns a mediocre edge into a survivable, compoundable one. Position sizing is what keeps you emotionally able to follow the system (oversized → panic/abandon strategy; undersized → boredom/sloppiness).

### 7.2 Three Independent Sizing Methods — Always Compute All Three, Trade the Smallest

**A. Risk-based sizing**
```
Position Size = (Equity × %Risk Allocated) / (Entry Price − Stop Loss Price, per unit)
```
- Novice: 0.5% of equity risked per trade.
- Experienced/medium-term: ~1%.
- Aggressive (high risk tolerance + experience only): up to 2% — note 20 simultaneous full-loss positions at 2% = 40% drawdown, rarely tolerable.
- **Gold-specific note:** because XAUUSD stops (Layer 3/4) are often wide (swing-based, not arbitrary), risk-based sizing will naturally produce smaller lot/contract sizes than in tighter FX pairs — this is correct, do not override it by shrinking the stop artificially.

**B. Volatility-based sizing** (controls how much day-to-day equity swing you're exposed to, independent of where your stop sits)
```
ATR(21) = Prior ATR + (2/(N+1)) × Today's True Range        [N = lookback, e.g. 21 days]
Position Size = (Equity × %Volatility Allocated) / ATR(21) per unit
```
- Novice: ≤0.5% of equity per position.
- Medium-term: ~0.6–0.75%.
- Aggressive: 1–2% (be aware ATR is an *average* — a single day can exceed it materially, especially in gold around news).

**C. Margin/Capital-based sizing** (protects against a low-volatility, low-risk instrument that still requires excessive margin — or a sudden exchange margin hike)
```
Position Size = (Equity × %Margin Allocated) / Margin Required per unit
```
- Typical cap: ~5% of equity margin per single position.

**Combine:** `Final Position Size = MIN(Size_Risk, Size_Volatility, Size_Margin)`. This always yields the most conservative, safest size across the three lenses.

### 7.3 Ongoing (In-Trade) Risk Management — Sizing Doesn't Stop at Entry
As a trade moves in your favor, its *effective* risk-to-equity ratio (using the now-larger open profit as part of what's "at stake" if reversed) grows. Rules:
- Set an **ongoing risk allocation ceiling** higher than the initial entry risk % (e.g., start at 1%, cap ongoing risk at ~2–2.5%) — if unrealized risk exceeds the ceiling, trim the position size (take partial profit) rather than let it ride unchecked. This is **"right-sizing," not "scaling out"** — you are managing risk exposure, not following a profit-target rule.
- Similarly cap **ongoing volatility exposure** (e.g., ~0.8% of equity) — if the position's ATR-based exposure grows past this because gold has become sharply more volatile, reduce size even if the risk-based measure hasn't yet triggered.
- Re-evaluate both whenever ATR or price gap materially (e.g., after major news).

### 7.4 Total Portfolio Risk Cap
If running multiple concurrent gold positions/setups (e.g., a QM setup on H1 plus a longer swing position), sum total open risk across all positions. Cap aggregate portfolio risk (e.g., ~10–15% of equity) — if a new signal would push you over the cap, either skip it or trim an existing position first (start with the position that is easiest/cheapest to trim).

### 7.5 Practical Starting Defaults for This System
| Parameter | Conservative default | Notes |
|---|---|---|
| Risk % per trade | 0.5%–1.0% | Start at 0.5% until system is validated live |
| Volatility % per trade | 0.5%–0.75% | ATR(21) daily basis |
| Margin % per trade | ≤5% | Relevant mainly if trading leveraged CFD/futures |
| Ongoing risk ceiling | ~2–2.5% | Trim, don't fully exit, when breached |
| Total portfolio risk cap | ~10–12.5% | Across all open gold positions |
| Minimum Reward:Risk | 1:2 | From Layer 3.3 TP rules |

### 7.6 What NOT to Do
- Do not use Kelly-criterion-style "maximize growth" sizing or push toward maximum theoretical leverage before blow-up — this passes every psychological breaking point (Basso's "shooting for the moon" warning) and one bad stretch (very plausible around gold news shocks) ends the account.
- Do not size so small that trades become irrelevant/boring — this leads to sloppy execution and rule violations because "it doesn't matter anyway."
- Do not average down into a losing QM setup — if the level fails (closes clearly beyond your stop), the setup is invalidated, not "cheaper."

---

## 8. Trade Management & Exit Discipline

1. Once in a trade, manage using Section 7.3 (ongoing risk/volatility limits) — not emotion.
2. If price stalls well before TP1 and structure starts printing a CHoCH against your position, consider closing early rather than waiting for the hard stop.
3. Never move a stop loss further away once placed. You may only move it in the direction of reduced risk (breakeven, trailing).
4. Re-mark QML/order-block levels after every completed swing — a level that has been retested once is no longer "fresh" and should not be re-traded with full size.

---

## 9. Trading Journal & Review (build this into the system from day one)

For every trade log:
- Timeframe(s) used for bias / setup / entry.
- Screenshot of QM structure with QML, Over, Under, Fib zone marked.
- Which liquidity concept applied (stop-hunt, fakeout, SFP, order block).
- Price action confirmation used.
- Position size and which of the 3 sizing methods was binding (risk/vol/margin).
- Outcome vs. planned R:R, and whether ongoing risk/volatility limits were triggered.
- Post-mortem: was the loss (if any) a "good loss" (system followed correctly, market just didn't cooperate) or a rule violation?

This journal is the raw material for eventually converting this discretionary framework into a backtestable/automatable rule set.

---

## 10. Summary — The One-Paragraph Version

Establish directional bias top-down using market structure (HH/HL vs LH/LL, BOS→CHoCH→MSS). Within that bias, hunt for a QM (Quasimodo) pattern — an Over/Under structure break that represents a genuine liquidity grab, ideally with QML and lower-timeframe MPL aligned for a "sharp entry," and ideally reinforced by a fakeout/compression/CPLQ setup. Enter on the 61.8–78.6% Fibonacci retracement into that zone, confirmed by price action (pin bar/engulfing/inside-bar breakout). Place the stop beyond the swing extreme, never at the obvious level. Target 1:2+ R:R using structure-based take-profit logic. Size every trade using the smallest of risk%/volatility%/margin% sizing, manage risk dynamically as the trade develops, and cap total portfolio risk — because the entry model only wins if the sizing survives long enough to let it work.

---

# PART II — SYSTEMATIZATION APPENDICES
> Added to make the discretionary framework above **codeable, backtestable, and forward-testable** without lookahead bias. Part I is the *intent*; Part II is the *specification*. Where the two ever conflict, Part II wins for automation purposes because it is unambiguous. Every threshold below is a **starting default** to be validated by walk-forward testing, not a sacred number.

## Appendix A — Operational (Quantitative) Definitions
The single biggest risk in automating this system is that terms like "swing," "fresh," and "compression" are defined *retrospectively*. Below, each is frozen to information available **at bar close only**. No definition may reference a future bar.

### A.1 Swing points (fractal, no repaint)
- A bar `i` is a **confirmed swing high** if `high[i]` is the maximum of the window `[i-L, i+R]`, where `L = R = swing_strength` (default `3`). Critically: the swing is only **emitted/known** at bar `i+R`, never at bar `i`. The engine must not "see" a swing until `R` bars later.
- **Confirmed swing low**: mirror with lows.
- Only swings with `swing_strength >= 3` count toward structure (HH/HL/LH/LL). This is the codified version of Part I §2.3.4 ("ignore insignificant micro-swings").
- `swing_strength` is a tunable parameter; larger = fewer, more significant swings.

### A.2 Market structure state (Layer 1)
- Maintain an ordered list of confirmed swing highs (SH) and lows (SL).
- **Bullish** if the last two SH are ascending AND the last two SL are ascending.
- **Bearish** if the last two SH are descending AND the last two SL are descending.
- **Ranging** otherwise (or if the last SH/SL differ by less than `range_atr_mult * ATR`, default `0.5`).
- **BOS**: close beyond the most recent confirmed swing in the trend direction.
- **CHoCH**: close beyond the most recent confirmed swing *against* trend (first counter-break).
- **MSS**: close beyond the prior *major* swing (a swing that itself produced a BOS) in the new direction → this flips `bias`.

### A.3 QM (Quasimodo) pattern detection (Layer 3, sell example; mirror for buy)
Given confirmed swings, label points 2→3→4→5 and derive the QML:
1. Point 2 = a confirmed SH → candidate `QML = high[point2]`.
2. Point 3 = the confirmed SL after point 2 (the "neck").
3. Point 4 ("OVER") = a confirmed SH with `high[point4] > high[point2]` (breaks point 2 → liquidity grab above).
4. Point 5 ("UNDER") = a confirmed SL with `low[point5] < low[point3]` (breaks the neck → confirms QM).
5. Pattern is **valid** once both Over and Under exist, in order, within `qm_lookback` bars (default `120`).
- **Freshness (§4.2.5 codified):** QML is `fresh` until price trades back into `[QML - qml_tol, QML + qml_tol]` once. `qml_tol = qml_atr_mult * ATR` (default `0.10`). After the first touch, mark `stale` → no full-size trade.
- **Shoulder asymmetry tolerance:** require `high[point4] >= high[point2] * (1 + break_frac)` and `low[point5] <= low[point3] * (1 - break_frac)`, `break_frac` default `0.0` (any clean break) — expose as a param.
- **Engulfing simplification (§4.1 "QM Shadow"):** on the directional TF, a single bearish/bullish engulfing bar at a supply/demand zone may substitute for the full 2→5 structure; treat its body as Over/Under.

### A.4 Entry zone (Fib confluence, Layer 3.2)
- Draw Fib on the impulse leg from Over→Under (sell) using **only bars up to the current bar** (no future extension).
- **Entry window = 61.8%–78.6% retracement** of that leg, intersected with `[QML - qml_tol, QML + qml_tol]`.
- Entry is armed only when price is inside the intersection AND the QML is still `fresh`.

### A.5 Price-action triggers (Layer 4, quantified)
- **Pin bar:** `wick_rejection / total_range >= pin_wick_ratio` (default `0.66`), body in opposite third, rejecting the zone.
- **Engulfing:** current body fully covers prior body; close beyond prior open in trigger direction.
- **Inside bar breakout:** bar fully inside prior range, then a close beyond the mother-bar range in bias direction.
- A trade triggers only when price is in the A.4 window **and** one A.5 pattern closes in the bias direction.

### A.6 Liquidity / SFP confirmation (Layer 2, optional booster)
- **SFP:** a bar makes a new extreme beyond a prior confirmed swing but **closes back inside** it, with rejection wick `>= sfp_wick_ratio` (default `0.5`). Flag `sfp=True` as a conviction booster (can raise R:R target or size tier).

### A.7 Stops & targets (Layer 3.3 codified)
- **Stop:** `swing_extreme ± stop_buffer`, `stop_buffer = stop_atr_mult * ATR` (default `0.25`), placed beyond the Over (sell) / Under (buy) — never at the round number.
- **Targets:** (T1) fixed `R:R = 2` minimum; (T2) next opposing structural zone; (T3) origin of opposite move. Configurable; default trade T1 with optional runner to T2.

## Appendix B — Backtesting Methodology (anti-lookahead is mandatory)
1. **Event-driven, bar-close decisions.** Loop bar by bar. At bar `t`, decisions may use data through the **close of `t`** only. Fills happen at `t+1` open or at limit/stop levels reached during `t+1..`, never at `t`'s close using `t`'s own future.
2. **No repainting.** Swings emit at `i+R` (Appendix A.1). Any indicator (ATR, RSI) uses closed bars only.
3. **Multi-timeframe alignment without leakage.** A higher-TF value may be used at a lower-TF bar only if that higher-TF bar has **already closed** at/before the lower-TF timestamp. Resample with explicit closed-bar timestamps; never forward-fill an unclosed HTF candle.
4. **Realistic cost model (see Appendix D).** Spread, slippage, commission, and swap applied to every fill. Backtests on mid-price with zero costs are invalid.
5. **Fill realism for wick trades.** If entry/stop sits inside a bar's range, assume worst-case intrabar sequencing (stop can be hit before target within the same bar unless tick data proves otherwise). For gold, add extra slippage on stop fills during high-volatility windows.
6. **Walk-forward, not single-shot optimization.** Optimize params on in-sample window `[a,b]`, validate on out-of-sample `[b,c]`, then roll forward. Report OOS results only.
7. **Parameter sensitivity.** Perturb each param ±20%; if performance collapses, the result is overfit.
8. **Ablation study.** Test the marginal contribution of each layer (structure-only, +QM, +Fib, +price action, +SFP) so you know which layers actually add edge vs. just reduce trade count.
9. **Regime tagging.** Tag each trade by regime (trend/range via ADX or structure; high/low vol via ATR percentile; session) and report per-regime stats — an edge that only exists in one regime needs a regime filter.

## Appendix C — Forward-Testing (Paper / Demo) Protocol
1. Run the **exact same code path** as live, on a real-time demo feed, for a fixed period (default: `>= 60 trading days` or `>= 30 qualifying trades`, whichever is later).
2. Log every signal, intended fill, actual (simulated broker) fill, and slippage.
3. **Divergence check:** compare forward-test expectancy, win rate, and average slippage to the backtest. A statistically significant gap (esp. worse fills) means the backtest's execution assumptions are wrong — fix before going live.
4. Forward-test is the primary defense against lookahead bugs that unit tests miss, because in real time the future genuinely does not exist.

## Appendix D — Data, Execution & Cost Modeling (gold-specific)
- **Data:** timezone-normalize to UTC; store broker + feed source (gold differs across venues). Prefer the broker's own historical feed for realism. Keep bid/ask if available.
- **Spread:** model as time-varying — tight in London/NY overlap, wide in Asian session and around news. Minimum a session-dependent spread table, ideally recorded historical spread.
- **Slippage:** base slippage + extra on stop fills + extra during news windows.
- **Commission & swap:** per-lot commission; overnight swap for positions held past broker rollover (triple swap on the broker's 3-day roll day).
- **News blackout:** integrate an economic-calendar source (FOMC, NFP, CPI, PPI, major geopolitical). Default: **no new entries within `news_blackout_min` (default 30) minutes before/after high-impact USD/gold events**, unless the setup is explicitly the news-spike-fade type (Part I §2.2.3) with its own tighter rules.
- **Weekend gap:** flag positions held over the weekend; optionally flat-by-Friday-close rule.

## Appendix E — Performance Metrics & Acceptance Criteria
Report all of these (win rate alone is meaningless):
- Expectancy per trade (in R), profit factor, total return.
- Max drawdown (%, and duration), Calmar/MAR, Sharpe, Sortino.
- Distribution of R-multiples (histogram), longest losing streak.
- Trade count and average trades/month (is the sample even large enough to trust?).
- Average modeled slippage vs. forward-test realized slippage.
- Per-regime and per-session breakdown.
**Suggested minimum acceptance (tune to taste) before micro-live:** OOS profit factor `>= 1.3`, OOS expectancy `> 0` after full costs, max DD within personal tolerance, `>= 30` OOS trades, and forward-test not materially worse than backtest.

## Appendix F — Session & Regime Filters
- **Sessions (UTC):** Asian ~00:00–07:00, London ~07:00–16:00, NY ~13:00–21:00, London/NY overlap ~13:00–16:00 (highest liquidity). Expose `allowed_sessions` param; gold setups generally cleanest in London/NY overlap.
- **Volatility regime:** ATR percentile over trailing window; optionally require `atr_pctile` in a band (skip dead and berserk conditions).
- **Trend regime:** only take counter-trend QM reversals when MSS-confirmed (Part I §2.3.2).

## Appendix G — Kill-Switches / Circuit Breakers (live safety)
- **Daily loss limit:** halt new entries after `-daily_loss_R` (default `-2R`) or `-daily_loss_pct` (default `-3%`).
- **Consecutive losses:** pause after `max_consec_losses` (default `4`) for manual review.
- **Spread/vol breaker:** skip entries when live spread `> spread_cap` or ATR spikes beyond `vol_cap`.
- **Equity floor:** hard stop the system at `-max_total_dd` (default `-15%`) pending review.

## Appendix H — Suggested System Architecture (for the build)
```
gold_qm_system/
  config/            # YAML params (all thresholds above), per-regime overrides
  data/              # loaders, resamplers (no-lookahead HTF alignment), spread tables
  indicators/        # ATR, RSI, swing detector (fractal, repaint-safe)
  structure/         # market-structure state machine (BOS/CHoCH/MSS)
  patterns/          # QM detector, price-action triggers, SFP, compression
  risk/              # 3-method position sizing (MIN of risk/vol/margin), ongoing risk mgr
  engine/            # event-driven backtester + live/paper runner (shared code path)
  execution/         # order sim (fills, slippage, costs), broker adapter interface
  calendar/          # economic-calendar news filter
  metrics/           # stats, R-distribution, per-regime/session reports
  journal/           # auto-logged trade journal (Part I §9 fields)
  reports/           # equity curve, walk-forward, sensitivity, ablation outputs
  tests/             # anti-lookahead tests, sizing tests, pattern-detection tests
  cli.py             # backtest | walkforward | forwardtest | live subcommands
```

## Appendix I — Improvements & Warnings Added to the Original System
1. **Freshness, compression, and "sharp entry" are now quantified** (Appendix A) so they can't silently repaint.
2. **Ablation study requirement** — because the layered filter stack risks tiny, unvalidatable samples; measure each layer's real contribution.
3. **Explicit anti-lookahead + HTF-alignment rules** — the failure mode most likely to make this system look great in backtest and lose live.
4. **Gold-specific cost/execution modeling elevated to a first-class requirement** — the strategy trades wicks/stop-hunts, the very moments of worst fills; ignoring this overstates edge.
5. **Regime & session tagging** — gold's character changes across macro regimes; an unconditional edge claim is suspect.
6. **Kill-switches** — the original doc manages per-trade risk well but had no portfolio-level circuit breaker for a bad day / broken market.
7. **Shared code path for backtest and live** — the only reliable way to keep forward-test honest.

---

# PART III — DESIGN ITERATION 2: EXIT GEOMETRY
> Added 2026-07-07 after Iteration 1 (fixed 2R target) failed validation on 21.6 years of gold M15 data (OOS expectancy −0.20R, PF 0.67 under walk-forward across band-width / Fib-veto / trigger-set variations). This part revises the *exit* design only; entry logic (Part I §§2–6, Appendix A.1–A.6) is unchanged. Part II's anti-lookahead, cost and validation requirements continue to apply in full.

## Appendix J — Why the fixed-target geometry failed, and the redesign

### J.1 The measured problem
On 21.6 years (127 trades), realized outcomes were: average losing trade **−1.12R**, average winning trade **+1.83R** (a fixed-2R target, minus costs/slippage), win rate **29–35%**. That geometry needs ≈ 38–40% winners to break even; the strategy delivers fewer. The fixed target also **caps the right tail**: gold trends persist well beyond 2R, and the CHoCH early-exit (Part I §8.2) closed 24 trades at an average of only **+0.36R**, cutting winners short. The edge, if any, must come from **letting winners run** and **cutting the reversal-to-full-stop losers**, not from a higher hit rate.

### J.2 Redesign — three configurable exit mechanics
All are parameters so they can be settled by walk-forward OOS results, never hand-picked in-sample.

1. **Exit mode (`stops_targets.exit_mode`)**
   - `fixed_rr` (Iteration 1 behavior; default so nothing silently changes): stop beyond the swing extreme (Appendix A.7), take-profit at `min_rr` × risk.
   - `trail_structure` (new): **no fixed take-profit** (target set to ±∞). The stop is trailed behind confirmed **setup-TF** structure — for a long, up to (most-recent confirmed swing low − `stop_atr_mult`×ATR); for a short, down to (most-recent confirmed swing high + `stop_atr_mult`×ATR). Trailing uses only **confirmed** swings (emitted at `i+R`, repaint-safe) and the current close, so it is fully causal. The stop may only tighten (already enforced by the broker). The position exits when the trailing stop is hit, or (optionally) on a counter-CHoCH, or at end-of-data.

2. **Breakeven rule (`stops_targets.be_trigger_r`, 0 = off)**
   Once unrealized profit reaches `be_trigger_r` × initial-risk-per-unit, move the stop to the entry price (once). Directly attacks the −1.12R losers: a trade that goes ≥ `be_trigger_r` R in favor and then reverses is scratched near breakeven instead of losing a full R. Applies in both exit modes.

3. **CHoCH-exit toggle (`stops_targets.use_choch_exit`, default true = Part I §8.2)**
   When `false`, a counter-CHoCH no longer force-closes the position; the trailing stop (or fixed target) does the work. Lets the walk-forward test whether §8.2 was protecting capital or amputating winners (the +0.36R evidence suggests the latter).

### J.3 What is deliberately *not* changed
Entry location, QM/Fib/PA gating, sizing (MIN of risk/vol/margin), session/news/regime filters, kill-switches, and the one-retest freshness rule are all unchanged. This isolates the exit variable so that any change in OOS performance is attributable to exit geometry alone (a controlled experiment, not a rewrite).

### J.4 Acceptance
Same bar as Part II Appendix E, judged on **walk-forward OOS only**: profit factor ≥ 1.3, expectancy > 0 after full costs, ≥ 30 OOS trades, sensitivity stable at ±20%. If `trail_structure` + breakeven does not clear this, the *concept* (not the tuning) is unproven on gold and the system does not proceed to Phase 3.

### J.5 Outcome — hypothesis FALSIFIED (2026-07-07)
Controlled full-sample comparison on 21.6 years (fixed_rr baseline vs trailing/breakeven variants, entry logic held constant):

| exit config | trades | exp. R | win% | PF | best trade |
|---|---|---|---|---|---|
| fixed_rr (Iter 1) | 127 | −0.12 | 35% | 0.84 | +2.0R |
| trail_structure | 123 | −0.25 | 25% | 0.28 | **+2.9R** |
| trail + BE@1R | 123 | −0.21 | 24% | 0.30 | +2.9R |
| fixed + BE@1R | 127 | −0.14 | 31% | 0.78 | +2.0R |

Two findings, both against the redesign:
1. **No fat right tail exists to harvest.** Letting every winner run with a structural trailing stop produced a best-ever trade of only **+2.9R** — the premise "gold trends persist well beyond 2R *from these entries*" is false. The QM retest does not locate the origin of large trends.
2. **Trailing destroys the win rate** (35% → 24%): the stop behind the last confirmed setup swing is hit on ordinary pullbacks before any trend develops, converting +2R winners into scratches/losses. Breakeven was neutral-to-slightly-negative.

**Conclusion:** the exit geometry was not the binding constraint; **the entry is.** Fixed 2R was, in fact, the best of the exit variants. Walk-forward was deliberately **not** run on the trailing variants — an in-sample PF of 0.28–0.30 cannot be rescued out-of-sample, so spending the compute would be validation theater. Iteration 2's specific hypothesis is rejected; the exit knobs remain in the codebase (defaulting to `fixed_rr`, i.e. inert) for future use, but the search now belongs at the entry, or the QM-on-gold concept should be retired. See VALIDATION.md.
