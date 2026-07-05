"""Quasimodo (QM) pattern detection — Appendix A.3/A.4.

Consumes CONFIRMED swings (repaint-safe) and CLOSED bars only. A pattern:

  SELL:  pt2 = SH (left shoulder, QML = its high)
         pt3 = SL (neck)
         pt4 = SH breaking pt2's high        ("OVER"  — liquidity grab above)
         pt5 = SL breaking pt3's low         ("UNDER" — confirms the QM)
  BUY:   exact mirror.

Lifecycle: forming -> tradeable(fresh) -> [touch] -> stale | invalid.
The QML tolerance band is FROZEN using ATR at pattern-confirmation time
(DECISIONS.md #5). Freshness starts strictly after the point-5 bar
(DECISIONS.md #23). A close beyond the head invalidates (DECISIONS.md #24).
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Literal, Optional

import pandas as pd

from gold_qm_system.config import QMConfig
from gold_qm_system.indicators import SwingPoint

QMDirection = Literal["sell", "buy"]
QMStatus = Literal["fresh", "stale", "invalid"]


@dataclass
class QMPattern:
    direction: QMDirection
    ls: SwingPoint        # point 2 (left shoulder) — QML source
    neck: SwingPoint      # point 3
    head: SwingPoint      # point 4 (Over for sell / Under for buy)
    under: SwingPoint     # point 5 (confirms pattern)
    qml: float
    qml_tol: float        # frozen at confirmation (ATR-based)
    tradeable_index: int  # bar index at which the pattern became tradeable
    zone_lo: float        # entry zone = fib window ∩ QML band (price low)
    zone_hi: float        # (price high)
    status: QMStatus = "fresh"
    in_first_touch: bool = field(default=False, init=False)
    touched: bool = field(default=False, init=False)

    # -- bands ------------------------------------------------------------
    @property
    def band_lo(self) -> float:
        return self.qml - self.qml_tol

    @property
    def band_hi(self) -> float:
        return self.qml + self.qml_tol

    @property
    def stop_extreme(self) -> float:
        """Swing extreme the stop sits beyond (A.7): head high (sell) / low (buy)."""
        return self.head.price

    def bar_touches_band(self, high: float, low: float) -> bool:
        return high >= self.band_lo and low <= self.band_hi

    def is_armed(self, high: float, low: float, close: float) -> bool:
        """DECISIONS #22: the bar reached the entry zone without closing through it."""
        if self.status != "fresh":
            return False
        if self.direction == "sell":
            return high >= self.zone_lo and close <= self.zone_hi
        return low <= self.zone_hi and close >= self.zone_lo


def _fib_zone(direction: QMDirection, head_price: float, under_price: float,
              fib_lo: float, fib_hi: float) -> tuple[float, float]:
    """A.4 / DECISIONS #6 — retracement window of the head->under impulse leg."""
    if direction == "sell":
        over_high, under_low = head_price, under_price
        rng = over_high - under_low
        return under_low + fib_lo * rng, under_low + fib_hi * rng
    under_low, over_high = head_price, under_price  # buy: head is the LOW extreme
    rng = over_high - under_low
    return over_high - fib_hi * rng, over_high - fib_lo * rng


class QMDetector:
    """Stateful detector. Call order per closed setup-TF bar:
    1) on_bar_close() with that bar's OHLC — so the born-stale retro check
       can see every bar up to and including the confirmation bar;
    2) on_swing() for each swing confirmed AT that bar (with ATR then).
    Then read `active_patterns()`.
    """

    def __init__(self, cfg: QMConfig, max_patterns: int = 20):
        self.cfg = cfg
        self._highs: list[SwingPoint] = []
        self._lows: list[SwingPoint] = []
        self._patterns: list[QMPattern] = []
        self._max_patterns = max_patterns
        # recent closed bars for the born-stale retro check (index, high, low)
        self._recent: deque[tuple[int, float, float]] = deque(maxlen=cfg.qm_lookback + 16)

    # ---------------------------------------------------------------- swings
    def on_swing(self, swing: SwingPoint, atr_at_confirm: float) -> Optional[QMPattern]:
        if swing.kind == "high":
            self._highs.append(swing)
            return self._try_form("buy", swing, atr_at_confirm)
        self._lows.append(swing)
        return self._try_form("sell", swing, atr_at_confirm)

    def _last_before(self, swings: list[SwingPoint], before_index: int) -> Optional[SwingPoint]:
        for s in reversed(swings):
            if s.index < before_index:
                return s
        return None

    def _try_form(self, direction: QMDirection, pt5: SwingPoint, atr_val: float) -> Optional[QMPattern]:
        """pt5 just confirmed; walk back alternating swings (DECISIONS #23)."""
        bf = self.cfg.break_frac
        if direction == "sell":
            pt4 = self._last_before(self._highs, pt5.index)
            if pt4 is None:
                return None
            pt3 = self._last_before(self._lows, pt4.index)
            if pt3 is None:
                return None
            pt2 = self._last_before(self._highs, pt3.index)
            if pt2 is None:
                return None
            if not (pt4.price >= pt2.price * (1 + bf) and pt4.price > pt2.price):
                return None                      # no Over: head must break LS high
            if not (pt5.price <= pt3.price * (1 - bf) and pt5.price < pt3.price):
                return None                      # no Under: must break the neck
        else:
            pt4 = self._last_before(self._lows, pt5.index)
            if pt4 is None:
                return None
            pt3 = self._last_before(self._highs, pt4.index)
            if pt3 is None:
                return None
            pt2 = self._last_before(self._lows, pt3.index)
            if pt2 is None:
                return None
            if not (pt4.price <= pt2.price * (1 - bf) and pt4.price < pt2.price):
                return None
            if not (pt5.price >= pt3.price * (1 + bf) and pt5.price > pt3.price):
                return None

        if pt5.index - pt2.index > self.cfg.qm_lookback:
            return None

        qml = pt2.price
        qml_tol = self.cfg.qml_atr_mult * atr_val   # FROZEN now (DECISIONS #5)
        fib_lo_p, fib_hi_p = _fib_zone(direction, pt4.price, pt5.price,
                                       self.cfg.fib_entry_low, self.cfg.fib_entry_high)
        zone_lo = max(fib_lo_p, qml - qml_tol)
        zone_hi = min(fib_hi_p, qml + qml_tol)
        if zone_lo > zone_hi:
            return None                             # empty intersection (DECISIONS #6)

        pat = QMPattern(direction, pt2, pt3, pt4, pt5, qml, qml_tol,
                        tradeable_index=pt5.confirmed_index,
                        zone_lo=zone_lo, zone_hi=zone_hi)

        # born-stale retro check: bars strictly after the point-5 bar,
        # up to and including the confirmation bar (DECISIONS #5)
        for (bi, bh, bl) in self._recent:
            if pt5.index < bi <= pt5.confirmed_index and pat.bar_touches_band(bh, bl):
                pat.status = "stale"
                pat.touched = True
                break

        self._patterns.append(pat)
        if len(self._patterns) > self._max_patterns:
            self._patterns = self._patterns[-self._max_patterns:]
        return pat

    # ------------------------------------------------------------- bar close
    def on_bar_close(self, bar_index: int, high: float, low: float, close: float) -> None:
        self._recent.append((bar_index, high, low))
        for pat in self._patterns:
            if pat.status != "fresh" or bar_index <= pat.tradeable_index:
                continue
            # invalidation: close beyond the head (DECISIONS #24)
            if pat.direction == "sell" and close > pat.head.price:
                pat.status = "invalid"
                continue
            if pat.direction == "buy" and close < pat.head.price:
                pat.status = "invalid"
                continue
            # freshness / first-touch episode tracking
            touching = pat.bar_touches_band(high, low)
            if touching:
                pat.in_first_touch = True
                pat.touched = True
            elif pat.touched:
                pat.in_first_touch = False
                pat.status = "stale"               # first retest over, untraded

    # ---------------------------------------------------------------- access
    def active_patterns(self, at_index: int) -> list[QMPattern]:
        """Patterns tradeable at (i.e. confirmed strictly before or at) `at_index`,
        still fresh."""
        return [p for p in self._patterns
                if p.status == "fresh" and p.tradeable_index <= at_index]
