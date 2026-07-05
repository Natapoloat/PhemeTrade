"""Market-structure state machine (Appendix A.2).

Pure function of CLOSED bars and CONFIRMED swings:
- feed confirmed swings (from the repaint-safe SwingDetector) via on_swing();
- feed bar closes via on_bar_close();
- read `bias` and receive BOS / CHOCH / MSS events.

Nothing here ever inspects an unconfirmed swing or an unclosed bar.
See DECISIONS.md #2 (Ranging tie-break) and #3 (major swing for MSS).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

import pandas as pd

from gold_qm_system.indicators import SwingPoint

Bias = Literal["bullish", "bearish", "ranging"]
EventKind = Literal["BOS", "CHOCH", "MSS"]
Direction = Literal["up", "down"]


@dataclass(frozen=True)
class StructureEvent:
    kind: EventKind
    direction: Direction
    bar_index: int
    time: pd.Timestamp
    level: float          # the swing price that was broken
    swing_index: int      # bar index of the broken swing


@dataclass
class _TrackedSwing:
    swing: SwingPoint
    broken: bool = False


@dataclass
class StructureEngine:
    range_atr_mult: float = 0.5

    bias: Bias = field(default="ranging", init=False)
    _highs: list[_TrackedSwing] = field(default_factory=list, init=False)
    _lows: list[_TrackedSwing] = field(default_factory=list, init=False)
    _major_low: Optional[_TrackedSwing] = field(default=None, init=False)   # for bullish trend
    _major_high: Optional[_TrackedSwing] = field(default=None, init=False)  # for bearish trend
    _choch_seen: bool = field(default=False, init=False)

    # ------------------------------------------------------------- swings
    def on_swing(self, swing: SwingPoint, atr_at_confirm: float) -> None:
        """Register a newly CONFIRMED swing; recompute pattern bias."""
        tracked = _TrackedSwing(swing)
        if swing.kind == "high":
            self._highs.append(tracked)
        else:
            self._lows.append(tracked)
        self._recompute_pattern_bias(atr_at_confirm)

    def _recompute_pattern_bias(self, atr_val: float) -> None:
        if len(self._highs) < 2 or len(self._lows) < 2:
            return  # keep whatever bias we have (initially ranging)
        sh1, sh2 = self._highs[-2].swing.price, self._highs[-1].swing.price
        sl1, sl2 = self._lows[-2].swing.price, self._lows[-1].swing.price
        tol = self.range_atr_mult * atr_val
        if abs(sh2 - sh1) < tol and abs(sl2 - sl1) < tol:
            new_bias: Bias = "ranging"
        elif sh2 > sh1 and sl2 > sl1:
            new_bias = "bullish"
        elif sh2 < sh1 and sl2 < sl1:
            new_bias = "bearish"
        else:
            new_bias = "ranging"
        if new_bias != self.bias:
            self.bias = new_bias
            self._choch_seen = False

    # ---------------------------------------------------------- bar closes
    def on_bar_close(self, bar_index: int, time: pd.Timestamp, close: float) -> list[StructureEvent]:
        """Check BOS / CHoCH / MSS against the close of a finished bar."""
        events: list[StructureEvent] = []
        if self.bias == "bullish":
            events += self._check_bullish(bar_index, time, close)
        elif self.bias == "bearish":
            events += self._check_bearish(bar_index, time, close)
        return events

    # -- helpers
    def _latest_breakable(self, swings: list[_TrackedSwing]) -> Optional[_TrackedSwing]:
        """The MOST RECENT confirmed swing (spec A.2), if not yet broken.
        Once broken, no further break events fire until a NEW swing confirms —
        older swings are never revisited."""
        if not swings or swings[-1].broken:
            return None
        return swings[-1]

    def _latest_confirmed(self, swings: list[_TrackedSwing]) -> Optional[_TrackedSwing]:
        return swings[-1] if swings else None

    def _check_bullish(self, i: int, t: pd.Timestamp, close: float) -> list[StructureEvent]:
        ev: list[StructureEvent] = []
        # BOS: close above the most recent unbroken confirmed SH
        sh = self._latest_breakable(self._highs)
        if sh is not None and close > sh.swing.price:
            sh.broken = True
            ev.append(StructureEvent("BOS", "up", i, t, sh.swing.price, sh.swing.index))
            # origin low of the breaking impulse becomes the major low (DECISIONS #3)
            self._major_low = self._latest_confirmed(self._lows)
            self._choch_seen = False
        # CHoCH: first close below the most recent unbroken confirmed SL
        sl = self._latest_breakable(self._lows)
        if not self._choch_seen and sl is not None and close < sl.swing.price:
            sl.broken = True
            self._choch_seen = True
            ev.append(StructureEvent("CHOCH", "down", i, t, sl.swing.price, sl.swing.index))
        # MSS: close below the major low -> flip to bearish
        if self._major_low is not None and close < self._major_low.swing.price:
            ml = self._major_low
            ev.append(StructureEvent("MSS", "down", i, t, ml.swing.price, ml.swing.index))
            self.bias = "bearish"
            self._major_low = None
            self._major_high = None
            self._choch_seen = False
        return ev

    def _check_bearish(self, i: int, t: pd.Timestamp, close: float) -> list[StructureEvent]:
        ev: list[StructureEvent] = []
        sl = self._latest_breakable(self._lows)
        if sl is not None and close < sl.swing.price:
            sl.broken = True
            ev.append(StructureEvent("BOS", "down", i, t, sl.swing.price, sl.swing.index))
            self._major_high = self._latest_confirmed(self._highs)
            self._choch_seen = False
        sh = self._latest_breakable(self._highs)
        if not self._choch_seen and sh is not None and close > sh.swing.price:
            sh.broken = True
            self._choch_seen = True
            ev.append(StructureEvent("CHOCH", "up", i, t, sh.swing.price, sh.swing.index))
        if self._major_high is not None and close > self._major_high.swing.price:
            mh = self._major_high
            ev.append(StructureEvent("MSS", "up", i, t, mh.swing.price, mh.swing.index))
            self.bias = "bullish"
            self._major_low = None
            self._major_high = None
            self._choch_seen = False
        return ev

    # ------------------------------------------------------------ introspection
    @property
    def swing_highs(self) -> list[SwingPoint]:
        return [tr.swing for tr in self._highs]

    @property
    def swing_lows(self) -> list[SwingPoint]:
        return [tr.swing for tr in self._lows]
