"""C2 — session-holding / overnight premium strategy (next-strategy brief).

Hypothesis (G2): a disproportionate share of an asset's return accrues while
holding across a specific session/overnight window — a gap-risk premium paid to
whoever bears news/gap risk that intraday traders refuse. Test: hold a fixed
direction across a fixed [entry_hour, exit_hour) UTC window, every day; measure
net expectancy after full costs. Daily positioning => ~250 round-trips/yr/symbol.

Free parameters (G3): entry_hour, exit_hour, direction — 3. ATR period is a
fixed convention (used only to normalize R and cap tail risk; exit is time-based,
so the ATR stop rarely binds).

Plugs into the shared engine via the same interface as QMStrategy: __init__,
on_bar_close, .skip_log, .halted. Use make_c2_factory(...) with run_backtest's
strategy_factory hook. Kill-switches are intentionally NOT wired for the first
expectancy read (they would only reduce trade count, not per-trade R).
"""
from __future__ import annotations

from typing import Any, Optional

import pandas as pd

from ..config import SystemConfig
from ..execution import BrokerAdapter
from ..indicators.incremental import IncATR
from ..risk.sizing import compute_size


class SessionPremiumStrategy:
    def __init__(self, cfg: SystemConfig, broker: BrokerAdapter, ks: Any,
                 calendar: Any, entry_hour: int = 21, exit_hour: int = 7,
                 direction: str = "buy", stop_atr_mult: float = 1.5):
        self.cfg = cfg
        self.broker = broker
        self.entry_hour = entry_hour
        self.exit_hour = exit_hour
        self.direction = direction
        self.stop_atr_mult = stop_atr_mult
        self.atr = IncATR(cfg.indicators.atr_period)
        self._entry_delta = pd.Timedelta(hours=1)  # set by factory to match entry TF
        self.skip_log: list[dict] = []
        self.halted = False

    def on_bar_close(self, time: pd.Timestamp, o: float, h: float, l: float,
                     c: float, spread: float, fills: Any) -> None:
        atr = self.atr.update(h, l, c)
        close_hour = (time + self._entry_delta).hour
        positions = self.broker.open_positions()

        # exit: close the held position when the window ends
        if positions and close_hour == self.exit_hour:
            for pos in positions:
                self.broker.request_close(pos.pos_id, None, "time_exit")
            return

        # entry: open one position at the window start, only if flat and ATR warm
        if not positions and close_hour == self.entry_hour and atr and atr > 0:
            stop_dist = self.stop_atr_mult * atr
            if self.direction == "buy":
                stop, target = c - stop_dist, c + 1000.0 * atr   # target far => time/stop exit only
            else:
                stop, target = c + stop_dist, c - 1000.0 * atr
            equity = self.broker.equity()
            sizing = compute_size(equity, c, stop, atr, self.cfg.sizing)
            if sizing.binding == "skipped" or sizing.size <= 0:
                self.skip_log.append({"time": time, "reason": "sizing_skipped"})
                return
            meta = {"strategy": "C2-session-premium", "signal_close": c,
                    "init_stop": stop, "entry_hour": self.entry_hour,
                    "exit_hour": self.exit_hour}
            self.broker.submit_market(self.direction, sizing.size, stop, target,
                                      sizing.risk_amount, meta)


def make_c2_factory(entry_hour: int, exit_hour: int, direction: str = "buy",
                    entry_delta: pd.Timedelta = pd.Timedelta(hours=1)):
    """Build a strategy_factory closure capturing the C2 params (keeps them out of
    the shared config schema and explicit in the experiment)."""
    def factory(cfg, broker, ks, calendar):
        s = SessionPremiumStrategy(cfg, broker, ks, calendar,
                                   entry_hour=entry_hour, exit_hour=exit_hour,
                                   direction=direction)
        s._entry_delta = entry_delta
        return s
    return factory
