"""C4 — ATR-percentile-gated Donchian channel breakout (trend-follow BENCHMARK).

The brief's "boring benchmark": if nothing beats a 2-parameter channel break gated
by vol regime, that is itself decision-relevant. Weakest structural story of the
four candidates but the strongest empirical base across decades/assets. Not a
deployment candidate unless it wins outright — it is the reference every other
candidate's OOS must beat.

Signal: enter on a close beyond the prior-L-bar Donchian channel, only when the
ATR percentile is inside a pre-fixed band (skip dead/berserk vol). Exit via a
chandelier ATR-trailing stop (let winners run). Free params: L, pctile band. ATR
period, the trail multiple (3xATR) and percentile window are fixed conventions.

Anti-lookahead: the channel is the max-high/min-low of bars STRICTLY BEFORE the
current one (deque read, then appended); ATR/percentile use closed bars; the
trailing stop is tightened on closed info so it binds only on the next bar.
"""
from __future__ import annotations

from collections import deque
from typing import Any

import pandas as pd

from ..config import SystemConfig
from ..execution import BrokerAdapter
from ..indicators.incremental import IncATR, IncPercentile
from ..risk.sizing import compute_size


class ChannelBreakoutStrategy:
    def __init__(self, cfg: SystemConfig, broker: BrokerAdapter, ks: Any, calendar: Any,
                 lookback: int = 55, pctile_lo: float = 0.0, pctile_hi: float = 1.0,
                 trail_k: float = 3.0):
        self.cfg = cfg
        self.broker = broker
        self.L = lookback
        self.pctile_lo = pctile_lo
        self.pctile_hi = pctile_hi
        self.trail_k = trail_k
        self.atr = IncATR(cfg.indicators.atr_period)
        self.pctile = IncPercentile(cfg.regime.atr_pctile_window, min_history=20)
        self._highs: deque[float] = deque(maxlen=lookback)
        self._lows: deque[float] = deque(maxlen=lookback)
        self._ext: dict[int, dict] = {}     # pos_id -> extreme since entry
        self.skip_log: list[dict] = []
        self.halted = False

    def on_bar_close(self, time: pd.Timestamp, o: float, h: float, l: float,
                     c: float, spread: float, fills: Any) -> None:
        atr = self.atr.update(h, l, c)
        pct = self.pctile.update(atr) if atr else None

        # trail open positions (chandelier); tighten only
        for pos in self.broker.open_positions():
            ext = self._ext.setdefault(pos.pos_id, {"hi": h, "lo": l})
            ext["hi"], ext["lo"] = max(ext["hi"], h), min(ext["lo"], l)
            if atr and atr > 0:
                if pos.direction == "buy":
                    ns = ext["hi"] - self.trail_k * atr
                    if ns > pos.stop:
                        self.broker.modify_stop(pos.pos_id, ns)
                else:
                    ns = ext["lo"] + self.trail_k * atr
                    if ns < pos.stop:
                        self.broker.modify_stop(pos.pos_id, ns)
        open_ids = {p.pos_id for p in self.broker.open_positions()}
        for pid in [k for k in self._ext if k not in open_ids]:
            del self._ext[pid]

        # entry on prior-L-bar Donchian break, gated by ATR percentile band
        if (len(self._highs) >= self.L and not self.broker.open_positions()
                and atr and atr > 0 and pct is not None
                and self.pctile_lo <= pct <= self.pctile_hi):
            ch_hi, ch_lo = max(self._highs), min(self._lows)
            direction = "buy" if c > ch_hi else ("sell" if c < ch_lo else None)
            if direction is not None:
                stop_dist = self.trail_k * atr
                if direction == "buy":
                    stop, target = c - stop_dist, c + 1000.0 * atr
                else:
                    stop, target = c + stop_dist, c - 1000.0 * atr
                sizing = compute_size(self.broker.equity(), c, stop, atr, self.cfg.sizing)
                if sizing.binding != "skipped" and sizing.size > 0:
                    self.broker.submit_market(direction, sizing.size, stop, target,
                                              sizing.risk_amount,
                                              {"strategy": "C4-channel", "init_stop": stop})

        self._highs.append(h)
        self._lows.append(l)


def make_c4_factory(lookback: int, pctile_lo: float, pctile_hi: float):
    def factory(cfg, broker, ks, calendar):
        return ChannelBreakoutStrategy(cfg, broker, ks, calendar, lookback=lookback,
                                       pctile_lo=pctile_lo, pctile_hi=pctile_hi)
    return factory
