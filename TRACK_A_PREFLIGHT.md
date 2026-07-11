# Phase 4 Track A — Demo-Live Deployment of C4-Trend: Pre-flight (A1)

*Engineering phase. Runs the **registry-frozen C4-trend config verbatim** on an Exness MT5
**DEMO** account, basket {BTC, ETH, USOIL, UKOIL, JP225}, D1, ≥90 days unattended.
Success = execution fidelity, NOT profit (the registry already gave the expectancy).*

## Frozen artifact + guards (done)
- **Config:** `live/c4_trend_frozen.yaml`, sha256 **`b8bb3f7d99a86356`** — hashed at every
  session start, logged. The `signal:` block (L=55, no vol gate, 3×ATR trail, ATR 21) is
  frozen; only execution plumbing may change.
- **Demo guard:** `gold_qm_system/live/guard.py::assert_demo` — asserts `trade_mode==0`
  (DEMO) at every session start and hard-exits otherwise; optional login/server pin. Tested:
  demo allowed, real account refused (hard-exit).
- **Plumbing fix logged:** `run_feed` now accepts `strategy_factory` so the live path runs
  the C4 factory verbatim (previously defaulted to QMStrategy). Signal untouched; 138 tests green.

## Backtest → live reality mapping (the fidelity contract)
| dimension | backtest assumption | live reality | divergence to log |
|---|---|---|---|
| **bar close** | processes each CLOSED D1 bar | `MT5LiveFeed` reads CLOSED D1 bars from the terminal at the broker's daily rollover (Exness demo server = UTC+0, verified) | server-time vs UTC drift; late bars |
| **order type** | market on **next D1 bar open** (SimBroker fills at t+1 open) | market order submitted after D1 close; fills at next daily open | **fill price vs modeled open + 0.5×spread → the headline slippage metric** |
| **sizing** | vol-scaled 0.5% risk / 3×ATR stop on a fixed 100k | 0.5% of **live demo balance** / 3×ATR; rounded to broker `min_lot`/`lot_step` | rounding gap (granularity-free backtest vs lot steps) |
| **swap** | per-symbol swap (mode-1 corrected) | real demo swap accrues nightly | modeled vs actual swap (validates the cost model) |
| **spread** | per-symbol calibrated (median) | live spread at the fill instant | spread-at-execution vs modeled |
| **session** | daily bars | crypto 24/7 (daily roll) vs oil/index weekday sessions (weekend gaps) | missed/rolled bars |

## Session lifecycle & restart/recovery model
Every session start, in order — **nothing trades until all pass**:
1. **Demo guard** (`assert_demo`) — hard-exit if not demo.
2. **Hash-verify** the frozen config; log hash + data source.
3. **Warm-up** the strategy's ATR/Donchian state from history (stateless across restarts —
   `MT5LiveFeed` re-warms), so a restart reproduces the same signal state.
4. **Reconcile** own append-only **state file** (per symbol: open position, last-acted D1 bar
   time) against **broker state** (open positions + pending orders):
   - match → resume;
   - **mismatch → HALT** (kill switch iii): stop new entries, alert loudly, flatten NOTHING
     automatically (human decides).
5. **Idempotency:** an entry is submitted for a signal only if that symbol's `last_acted_bar`
   < the current signal bar — never duplicate an entry after a crash/reboot mid-signal.

## A2/A3 build plan (next, once inputs arrive)
- **Scheduler:** per-symbol trigger at each symbol's D1 close (24/7 crypto vs weekday
  oil/index handled by the feed's closed-bar detection, not a wall-clock cron).
- **Execution module:** signal → order → fill confirm → state update → append-only log.
  Partial fill / rejection / requote / symbol-disabled → **log and skip** (never blind retry-loop).
- **Kill switches (all three, each triggered once in week 1 to prove them):** (i) manual
  `live/HALT` flag file; (ii) daily basket loss > 3R; (iii) reconciliation mismatch. Halt =
  stop new entries + alert; no auto-flatten.
- **Alerting:** on every fill / error / halt. Proposed default = **Telegram bot** (free,
  reliable, trivial API, phone push) — swap for email if preferred.
- **A3 monitoring:** daily HTML/markdown dashboard (open positions, R, realized/unrealized
  PnL, equity, swap paid, **per-fill slippage: live vs backtest-model fill**, errors, uptime);
  **weekly reconciliation report** = live vs what the backtest engine says should have happened
  on the same bars/config, divergences itemized (slippage/spread/swap/timing). This is the
  live forward-test data, accruing to the record regardless of any capital decision.

## Acceptance (Track A "done" = operational)
- 30 consecutive unattended days, zero unexplained state divergences, zero missed signals.
- All three kill switches proven by deliberate trigger (week 1).
- Weekly slippage/divergence report auto-produced.
- **Profitability is explicitly NOT a criterion.**

## Blocking inputs needed (from user)
- Demo account connection (via config, never in chat): terminal path / login / server. The
  guard pins these once provided.
- Alert channel choice (default: Telegram bot token + chat id, via config/env).
