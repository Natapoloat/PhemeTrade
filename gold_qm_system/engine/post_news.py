"""C3 — post-news drift / fade (one family, two branches).

Mechanism (G2): after a high-impact US print (NFP/CPI/FOMC), slow-moving,
mandate-constrained capital adjusts over hours (drift), while the first spike
often overshoots (fade). The calendar supplies the trigger times; the DATA
decides which branch, if any, survives costs.

Anti-lookahead: the event time is known in advance, but the impulse DIRECTION is
measured only from bars between the event and the settle point (all closed); entry
is submitted at the settle bar's close and fills at the next open. Nothing future
of the entry is referenced. Uses the calendar passed into the strategy (filter it
to scheduled_only + as_of upstream so no unscheduled/future rows leak in).

Free params: branch {drift, fade}, exit_horizon_h. settle_min is a fixed
convention (30 min ~ covers the initial reaction; FOMC presser can extend it).
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from ..config import SystemConfig
from ..execution import BrokerAdapter
from ..indicators.incremental import IncATR
from ..risk.sizing import compute_size


class PostNewsStrategy:
    def __init__(self, cfg: SystemConfig, broker: BrokerAdapter, ks: Any, calendar: Any,
                 branch: str = "drift", exit_horizon_h: float = 2.0,
                 settle_min: int = 30):
        self.cfg = cfg
        self.broker = broker
        self.branch = branch
        self.exit_td = pd.Timedelta(hours=exit_horizon_h)
        self.settle_td = pd.Timedelta(minutes=settle_min)
        self.atr = IncATR(cfg.indicators.atr_period)
        self._entry_delta = pd.Timedelta(minutes=15)
        events = getattr(calendar, "events", None)
        self._events = (list(pd.to_datetime(events["timestamp_utc"], utc=True))
                        if events is not None and len(events) else [])
        self._pi = 0
        self._armed: list[dict] = []
        self._prev_close: float | None = None
        self.skip_log: list[dict] = []
        self.halted = False

    def on_bar_close(self, time: pd.Timestamp, o: float, h: float, l: float,
                     c: float, spread: float, fills: Any) -> None:
        atr = self.atr.update(h, l, c)
        ct = time + self._entry_delta

        # arm events whose release has passed on/at this bar (ref = pre-event close)
        while self._pi < len(self._events) and self._events[self._pi] <= ct:
            E = self._events[self._pi]
            self._pi += 1
            ref = self._prev_close if self._prev_close is not None else c
            self._armed.append({"settle": E + self.settle_td, "ref": ref})

        # exits: close held position at its horizon
        for pos in self.broker.open_positions():
            if ct >= pos.meta.get("exit_time", pd.Timestamp.max.tz_localize("UTC")):
                self.broker.request_close(pos.pos_id, None, "time_exit")

        # entries: fire armed events that have reached the settle point
        still = []
        for a in self._armed:
            if ct < a["settle"]:
                still.append(a)
                continue
            if self.broker.open_positions() or not (atr and atr > 0):
                continue  # missed (busy/warm-up); drop the event
            impulse = c - a["ref"]
            if impulse == 0:
                continue
            base = "buy" if impulse > 0 else "sell"
            direction = base if self.branch == "drift" else ("sell" if base == "buy" else "buy")
            r = 1.5 * max(abs(impulse), 0.5 * atr)     # event-scaled risk unit
            if direction == "buy":
                stop, target = c - r, c + 1000.0 * atr
            else:
                stop, target = c + r, c - 1000.0 * atr
            sizing = compute_size(self.broker.equity(), c, stop, atr, self.cfg.sizing)
            if sizing.binding == "skipped" or sizing.size <= 0:
                self.skip_log.append({"time": time, "reason": "sizing_skipped"})
                continue
            meta = {"strategy": "C3-post-news", "branch": self.branch,
                    "exit_time": ct + self.exit_td, "init_stop": stop, "signal_close": c}
            self.broker.submit_market(direction, sizing.size, stop, target,
                                      sizing.risk_amount, meta)
        self._armed = still
        self._prev_close = c


def make_c3_factory(branch: str, exit_horizon_h: float, settle_min: int = 30,
                    entry_delta: pd.Timedelta = pd.Timedelta(minutes=15)):
    def factory(cfg, broker, ks, calendar):
        s = PostNewsStrategy(cfg, broker, ks, calendar, branch=branch,
                             exit_horizon_h=exit_horizon_h, settle_min=settle_min)
        s._entry_delta = entry_delta
        return s
    return factory
