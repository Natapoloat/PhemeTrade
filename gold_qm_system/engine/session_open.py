"""C1 — London/NY session-open breakout AND fade (one family, two branches).

Pre-registered (RESEARCH_REGISTRY.md, 2026-07-09). Mechanism: session opens
concentrate flow; Asian-range stop clusters sit just outside the range; fixing/
hedging execute at fixed times. Breakout = flow initiation beyond the range;
fade = stop-run exhaustion on the first failed break.

Anti-lookahead: the Asian range is completed only from bars strictly before 07:00
UTC; entries use the current CLOSED bar's OHLC + a closed-bar ATR; orders fill at
the NEXT bar open. No future data is referenced.

Frozen grid: branch {breakout, fade} x buffer_k {0.0,0.25,0.5} x exit_mode
{session_end, fixed_2R}. ATR period, session bounds and the 1x ATR stop are fixed
conventions (never tuned). One position at a time; one entry per session window/day.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from ..config import SystemConfig
from ..execution import BrokerAdapter
from ..indicators.incremental import IncATR
from ..risk.sizing import compute_size

# session hours (UTC), fixed conventions
ASIAN_END = 7      # Asian range = [0, 7)
LON_OPEN, LON_END = 7, 16
NY_OPEN, NY_END = 13, 21


class SessionOpenStrategy:
    def __init__(self, cfg: SystemConfig, broker: BrokerAdapter, ks: Any, calendar: Any,
                 branch: str = "breakout", buffer_k: float = 0.25,
                 exit_mode: str = "session_end", stop_atr_mult: float = 1.0):
        self.cfg = cfg
        self.broker = broker
        self.branch = branch            # 'breakout' | 'fade'
        self.buffer_k = buffer_k
        self.exit_mode = exit_mode       # 'session_end' | 'fixed_2R'
        self.stop_atr_mult = stop_atr_mult
        self.atr = IncATR(cfg.indicators.atr_period)
        self._entry_delta = pd.Timedelta(minutes=15)
        self.skip_log: list[dict] = []
        self.halted = False
        self._day = None
        self._a_high = self._a_low = None
        self._a_complete = False
        self._did_london = self._did_ny = False

    def _reset_day(self) -> None:
        self._a_high = self._a_low = None
        self._a_complete = False
        self._did_london = self._did_ny = False

    def on_bar_close(self, time: pd.Timestamp, o: float, h: float, l: float,
                     c: float, spread: float, fills: Any) -> None:
        atr = self.atr.update(h, l, c)
        ct = time + self._entry_delta      # bar-close instant
        hour, day = ct.hour, ct.date()
        if day != self._day:
            self._day = day
            self._reset_day()

        # accumulate the Asian range from bars strictly inside [0,7)
        if 0 <= hour < ASIAN_END:
            self._a_high = h if self._a_high is None else max(self._a_high, h)
            self._a_low = l if self._a_low is None else min(self._a_low, l)
            return
        if self._a_high is not None:
            self._a_complete = True

        # exits: close at/after the session-end hour recorded on the position
        for pos in self.broker.open_positions():
            if hour >= pos.meta.get("exit_hour", 99):
                self.broker.request_close(pos.pos_id, None, "time_exit")
        if self.broker.open_positions():
            return                          # one position at a time
        if not (self._a_complete and atr and atr > 0):
            return

        in_london = LON_OPEN <= hour < NY_OPEN and not self._did_london
        in_ny = NY_OPEN <= hour < NY_END and not self._did_ny
        if not (in_london or in_ny):
            return
        exit_hour = LON_END if in_london else NY_END

        buf = self.buffer_k * atr
        up, dn = self._a_high + buf, self._a_low - buf
        direction = None
        if self.branch == "breakout":
            if c > up:
                direction = "buy"
            elif c < dn:
                direction = "sell"
        else:  # fade the first failed break (poke beyond, close back inside)
            if h > up and c < self._a_high:
                direction = "sell"
            elif l < dn and c > self._a_low:
                direction = "buy"
        if direction is None:
            return

        if in_london:
            self._did_london = True
        else:
            self._did_ny = True

        # STRUCTURAL, session-scaled stop (corrected 2026-07-09 after the 1x-M15-ATR
        # convention proved degenerate: median hold 0.25-0.5h, ~80% noise-stopped in
        # ~2 bars — a micro-scalp, not a session hold). Breakout: stop at the far side
        # of the Asian range (you are wrong only if price fully reverses through it).
        # Fade: stop just beyond the failed-break extreme. R scales with the setup.
        sbuf = 0.1 * atr
        if direction == "buy":
            stop = (self._a_low - sbuf) if self.branch == "breakout" else (l - sbuf)
            r = c - stop
            target = c + (2.0 * r if self.exit_mode == "fixed_2R" else 1000.0 * atr)
        else:
            stop = (self._a_high + sbuf) if self.branch == "breakout" else (h + sbuf)
            r = stop - c
            target = c - (2.0 * r if self.exit_mode == "fixed_2R" else 1000.0 * atr)
        if r <= 0:
            return
        equity = self.broker.equity()
        sizing = compute_size(equity, c, stop, atr, self.cfg.sizing)
        if sizing.binding == "skipped" or sizing.size <= 0:
            self.skip_log.append({"time": time, "reason": "sizing_skipped"})
            return
        meta = {"strategy": "C1-session-open", "branch": self.branch,
                "session": "london" if in_london else "ny", "exit_hour": exit_hour,
                "init_stop": stop, "signal_close": c}
        self.broker.submit_market(direction, sizing.size, stop, target,
                                  sizing.risk_amount, meta)


def make_c1_factory(branch: str, buffer_k: float, exit_mode: str,
                    entry_delta: pd.Timedelta = pd.Timedelta(minutes=15)):
    def factory(cfg, broker, ks, calendar):
        s = SessionOpenStrategy(cfg, broker, ks, calendar, branch=branch,
                                buffer_k=buffer_k, exit_mode=exit_mode)
        s._entry_delta = entry_delta
        return s
    return factory
