"""Fair Value Gap (Imbalance) detection — Appendix K.1 #2.

An FVG is the 3-candle imbalance that marks a strong impulsive departure (the
course's measure of Supply/Demand zone quality). It is defined from bar
HIGH/LOW only and is known at the close of the third bar, so it is fully causal
(no lookahead): the FVG "at" the middle bar i is confirmed at bar i+1.

  Bullish FVG (up-impulse): high[i-1] < low[i+1]   -> gap [high[i-1], low[i+1]]
  Bearish FVG (down-impulse): low[i-1] > high[i+1] -> gap [high[i+1], low[i-1]]

`size` is the gap height in price units; callers compare it to an ATR multiple.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence

Direction = Literal["buy", "sell"]


@dataclass(frozen=True)
class FVG:
    direction: Direction        # "buy" = bullish gap, "sell" = bearish gap
    mid_index: int              # index of the middle bar (relative to the input sequence)
    gap_lo: float
    gap_hi: float

    @property
    def size(self) -> float:
        return self.gap_hi - self.gap_lo


def find_fvgs(highs: Sequence[float], lows: Sequence[float],
              direction: Direction | None = None,
              index_offset: int = 0) -> list[FVG]:
    """All FVGs in a sequence of aligned (high, low). `index_offset` is added to
    every emitted mid_index so callers can map back to absolute bar indices.
    If `direction` is given, only that polarity is returned."""
    out: list[FVG] = []
    n = len(highs)
    for i in range(1, n - 1):
        if direction in (None, "buy") and highs[i - 1] < lows[i + 1]:
            out.append(FVG("buy", index_offset + i, highs[i - 1], lows[i + 1]))
        if direction in (None, "sell") and lows[i - 1] > highs[i + 1]:
            out.append(FVG("sell", index_offset + i, highs[i + 1], lows[i - 1]))
    return out


def leg_has_fvg(highs: Sequence[float], lows: Sequence[float], direction: Direction,
                min_size: float = 0.0) -> tuple[bool, float]:
    """Does an impulsive leg contain a same-direction FVG >= min_size?

    Returns (has_fvg, largest_qualifying_size). Used as the zone-quality gate:
    a strong departure leaves an imbalance; a weak overlapping leg does not.
    """
    best = 0.0
    for fvg in find_fvgs(highs, lows, direction):
        if fvg.size >= min_size and fvg.size > best:
            best = fvg.size
    return (best > 0.0, best)
