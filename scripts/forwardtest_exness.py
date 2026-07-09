"""Paper/forward-test the gold QM strategy live against an Exness MT5 demo.

READ-ONLY on the broker: bars are pulled from the running MetaTrader 5 terminal
and fed through the SAME QMStrategy signal path as the backtest; orders go to an
internal paper SimBroker, so NO live orders are ever placed and NO capital is at
risk. This is the honest out-of-sample test: the strategy sees only closed bars,
one at a time, exactly as in live trading.

The feed first replays recent history to WARM UP the strategy state (swings,
structure, QM patterns, ATR). Those warm-up trades are labelled [warmup] and do
NOT count — only trades whose signal lands after warm-up are the forward test.

Prereqs: Exness MT5 terminal installed + logged into your demo account, left
running. (Same setup as scripts/fetch_exness_mt5.py.)

Usage:
  # connectivity + pipeline self-test (replays ~3000 recent closed bars, no wait)
  python scripts/forwardtest_exness.py --selftest

  # real forward test (runs until Ctrl-C; one live M15 bar every 15 min)
  python scripts/forwardtest_exness.py --config forwardtest_iter3_config.yaml
"""
from __future__ import annotations

import argparse
import json
import signal
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from gold_qm_system.config import SystemConfig
from gold_qm_system.engine import run_feed
from gold_qm_system.engine.feed import MT5LiveFeed

DEFAULT_TERMINAL = r"C:\Program Files\MetaTrader 5 EXNESS\terminal64.exe"


class Journal:
    """on_event callback: prints a per-bar heartbeat, logs new entries/exits to a
    JSONL file, and tracks LIVE (post-warm-up) trades separately from warm-up."""

    def __init__(self, feed: MT5LiveFeed, path: Path, initial_equity: float):
        self.feed = feed
        self.path = path
        self.initial_equity = initial_equity
        self._seen_open: set = set()
        self._trade_count = 0
        self._bar = 0
        self.live_trades: list = []
        self._fh = open(path, "a", encoding="utf-8")

    def _is_live(self, t: pd.Timestamp) -> bool:
        w = self.feed.warmup_end_time
        return w is not None and t is not None and t > w

    def _write(self, rec: dict) -> None:
        self._fh.write(json.dumps(rec, default=str) + "\n")
        self._fh.flush()

    def __call__(self, time: pd.Timestamp, fills, strategy) -> None:
        self._bar += 1
        broker = strategy.broker
        phase = "live" if self._is_live(time) else "warmup"

        # new entries: positions we haven't seen open before
        for pos in broker.open_positions():
            if pos.pos_id not in self._seen_open:
                self._seen_open.add(pos.pos_id)
                tag = "live" if self._is_live(pos.meta.get("signal_time", time)) else "warmup"
                fvg = pos.meta.get("departure_fvg_size") or 0.0
                print(f"  [{tag}] ENTER {pos.direction} @ {pos.entry_price:.2f} "
                      f"stop {pos.stop:.2f} size {pos.size:g} "
                      f"trig={pos.meta.get('trigger')} fvg={fvg:.2f}",
                      flush=True)
                self._write({"event": "enter", "phase": tag, "time": time,
                             "pos_id": pos.pos_id, "direction": pos.direction,
                             "entry": pos.entry_price, "stop": pos.stop, "size": pos.size,
                             "trigger": pos.meta.get("trigger")})

        # new closed trades
        if len(broker.trades) > self._trade_count:
            for tr in broker.trades[self._trade_count:]:
                is_live = self._is_live(tr.entry_time)
                tag = "live" if is_live else "warmup"
                if is_live:
                    self.live_trades.append(tr)
                print(f"  [{tag}] EXIT  {tr.direction} {tr.exit_reason} "
                      f"R={tr.r_multiple:+.2f} pnl={tr.net_pnl:+.2f}", flush=True)
                self._write({"event": "exit", "phase": tag, "time": time,
                             "entry_time": tr.entry_time, "exit_time": tr.exit_time,
                             "direction": tr.direction, "exit_reason": tr.exit_reason,
                             "r_multiple": tr.r_multiple, "net_pnl": tr.net_pnl})
            self._trade_count = len(broker.trades)

        # heartbeat every bar
        eq = broker.equity()
        print(f"[{self._bar:>5}] {time} UTC {phase:<6} eq={eq:,.0f} "
              f"open={len(broker.open_positions())} live_trades={len(self.live_trades)}",
              flush=True)

    def summary(self) -> None:
        n = len(self.live_trades)
        print("\n" + "=" * 60)
        print(f"FORWARD-TEST SUMMARY (LIVE trades only, warm-up excluded)")
        print("=" * 60)
        if n == 0:
            print("No live trades yet. Keep it running — QM setups are rare "
                  "(~3-6 trades/year on M15). Journal:", self.path)
            self._fh.close()
            return
        rs = [t.r_multiple for t in self.live_trades]
        wins = [r for r in rs if r > 0]
        exp = sum(rs) / n
        gross_w = sum(wins)
        gross_l = -sum(r for r in rs if r <= 0)
        pf = (gross_w / gross_l) if gross_l > 0 else float("inf")
        print(f"  live trades:   {n}")
        print(f"  expectancy_R:  {exp:+.3f}")
        print(f"  win rate:      {len(wins)/n:.0%}")
        print(f"  profit factor: {pf:.2f}")
        print(f"  sum R:         {sum(rs):+.2f}")
        print(f"  journal:       {self.path}")
        print(f"  (acceptance bar: PF>=1.3, expectancy>0, >=30 trades; "
              f"backtest OOS expectation ~ -0.04R)")
        self._fh.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="forwardtest_iter3_config.yaml")
    ap.add_argument("--symbol", default="XAUUSD")
    ap.add_argument("--timeframe", default="M15")
    ap.add_argument("--warmup-bars", type=int, default=3000)
    ap.add_argument("--terminal", default=DEFAULT_TERMINAL)
    ap.add_argument("--server-utc-offset", type=int, default=None)
    ap.add_argument("--poll-seconds", type=float, default=None)
    ap.add_argument("--max-live-bars", type=int, default=None,
                    help="stop after N live bars (default: run until Ctrl-C)")
    ap.add_argument("--selftest", action="store_true",
                    help="replay recent history only (max_live_bars=0), no live wait")
    ap.add_argument("--journal", default=None,
                    help="JSONL output path (default: output/forwardtest_<ts>.jsonl)")
    args = ap.parse_args()

    cfg = SystemConfig.from_yaml(args.config)
    print(f"[cfg] {args.config}: FVG={cfg.qm.require_departure_fvg}"
          f"/{cfg.qm.min_departure_fvg_atr} stop={cfg.stops_targets.stop_placement} "
          f"TFs {cfg.timeframes.entry}/{cfg.timeframes.setup}/{cfg.timeframes.directional}")

    max_live = 0 if args.selftest else args.max_live_bars
    feed = MT5LiveFeed(symbol=args.symbol, timeframe=args.timeframe,
                       warmup_bars=args.warmup_bars, terminal=args.terminal,
                       server_utc_offset=args.server_utc_offset,
                       poll_seconds=args.poll_seconds, max_live_bars=max_live)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    jpath = Path(args.journal) if args.journal else Path("output") / f"forwardtest_{ts}.jsonl"
    jpath.parent.mkdir(parents=True, exist_ok=True)
    journal = Journal(feed, jpath, cfg.account.initial_equity)

    def handle_sigint(signum, frame):
        print("\n[stop] Ctrl-C — finishing current bar, then summarizing.")
        feed.stop()
    signal.signal(signal.SIGINT, handle_sigint)

    try:
        run_feed(cfg, feed, on_event=journal)
    finally:
        journal.summary()


if __name__ == "__main__":
    main()
