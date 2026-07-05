"""Repaint-safe fractal swing detection (Appendix A.1).

A bar `i` is a confirmed swing high iff high[i] is the STRICT maximum of the
window [i-L, i+R] with L = R = swing_strength. The swing is only EMITTED at
bar i+R — the engine must never see it earlier. Ties do not confirm
(DECISIONS.md #1).

Two APIs with guaranteed identical output (tested):
- SwingDetector: incremental, one bar at a time (used by the live engine).
- detect_swings: vectorized over a closed history (used for analysis/tests).
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class SwingPoint:
    kind: Literal["high", "low"]
    index: int                # bar position of the swing extreme
    time: pd.Timestamp        # open time of the swing bar
    price: float
    confirmed_index: int      # index + swing_strength (R)
    confirmed_time: pd.Timestamp


class SwingDetector:
    """Feed bars in order; get back swings confirmed AT the fed bar."""

    def __init__(self, strength: int = 3):
        if strength < 1:
            raise ValueError("strength must be >= 1")
        self.s = strength
        self._win = 2 * strength + 1
        self._idx: deque[int] = deque(maxlen=self._win)
        self._time: deque[pd.Timestamp] = deque(maxlen=self._win)
        self._high: deque[float] = deque(maxlen=self._win)
        self._low: deque[float] = deque(maxlen=self._win)
        self._next_index = 0

    def update(self, time: pd.Timestamp, high: float, low: float) -> list[SwingPoint]:
        i = self._next_index
        self._next_index += 1
        self._idx.append(i)
        self._time.append(time)
        self._high.append(high)
        self._low.append(low)

        out: list[SwingPoint] = []
        if len(self._idx) < self._win:
            return out

        c = self.s  # candidate position: center of the full window
        h = np.asarray(self._high)
        l = np.asarray(self._low)
        cand_h, cand_l = h[c], l[c]
        others = np.arange(self._win) != c
        if cand_h > h[others].max():
            out.append(SwingPoint("high", self._idx[c], self._time[c], float(cand_h), i, time))
        if cand_l < l[others].min():
            out.append(SwingPoint("low", self._idx[c], self._time[c], float(cand_l), i, time))
        return out


def detect_swings(df: pd.DataFrame, strength: int = 3) -> list[SwingPoint]:
    """Vectorized equivalent of SwingDetector over a closed OHLC history."""
    det = SwingDetector(strength)
    swings: list[SwingPoint] = []
    for time, row in zip(df.index, df[["high", "low"]].itertuples(index=False)):
        swings.extend(det.update(time, row.high, row.low))
    return swings
