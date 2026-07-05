"""Price-action triggers (Appendix A.5), SFP booster (A.6) and compression /
CPLQ (Part I 4.4, DECISIONS #16). Pure functions of CLOSED bars only."""
from __future__ import annotations

from typing import Literal, NamedTuple, Sequence

Direction = Literal["buy", "sell"]


class Bar(NamedTuple):
    open: float
    high: float
    low: float
    close: float


def pin_bar(bar: Bar, direction: Direction, wick_ratio: float = 0.66) -> bool:
    """A.5: rejection wick >= wick_ratio of range, body in the opposite third."""
    rng = bar.high - bar.low
    if rng <= 0:
        return False
    body_hi, body_lo = max(bar.open, bar.close), min(bar.open, bar.close)
    if direction == "buy":                       # long lower wick, body in top third
        wick = body_lo - bar.low
        return wick / rng >= wick_ratio and body_lo >= bar.high - rng / 3.0
    wick = bar.high - body_hi                    # sell: long upper wick, body bottom third
    return wick / rng >= wick_ratio and body_hi <= bar.low + rng / 3.0


def engulfing(prev: Bar, cur: Bar, direction: Direction) -> bool:
    """A.5: current body fully covers prior body; close beyond prior open."""
    cover = (min(cur.open, cur.close) <= min(prev.open, prev.close)
             and max(cur.open, cur.close) >= max(prev.open, prev.close))
    if not cover:
        return False
    if direction == "buy":
        return cur.close > cur.open and cur.close > prev.open
    return cur.close < cur.open and cur.close < prev.open


def inside_bar_breakout(mother: Bar, inside: Bar, cur: Bar, direction: Direction) -> bool:
    """A.5: `inside` fully within `mother`'s range; `cur` closes beyond it."""
    is_inside = inside.high <= mother.high and inside.low >= mother.low
    if not is_inside:
        return False
    if direction == "buy":
        return cur.close > mother.high
    return cur.close < mother.low


def any_trigger(bars: Sequence[Bar], direction: Direction,
                pin_wick_ratio: float = 0.66) -> str | None:
    """Evaluate all A.5 triggers on the LAST closed bar of `bars`.
    Returns the trigger name or None. Needs >= 3 bars for the inside-bar case."""
    cur = bars[-1]
    if pin_bar(cur, direction, pin_wick_ratio):
        return "pin_bar"
    if len(bars) >= 2 and engulfing(bars[-2], cur, direction):
        return "engulfing"
    if len(bars) >= 3 and inside_bar_breakout(bars[-3], bars[-2], cur, direction):
        return "inside_bar_breakout"
    return None


def sfp(bar: Bar, swing_level: float, direction: Direction, wick_ratio: float = 0.5) -> bool:
    """A.6 Swing Failure Pattern: new extreme beyond a prior confirmed swing,
    close back inside, rejection wick >= wick_ratio of range.
    `direction` is the TRADE direction the SFP supports (sell = failed high)."""
    rng = bar.high - bar.low
    if rng <= 0:
        return False
    if direction == "sell":
        poked = bar.high > swing_level and bar.close < swing_level
        wick = bar.high - max(bar.open, bar.close)
    else:
        poked = bar.low < swing_level and bar.close > swing_level
        wick = min(bar.open, bar.close) - bar.low
    return poked and (wick / rng) >= wick_ratio


def compression(bars: Sequence[Bar], n_bars: int = 4, shrink: float = 0.8) -> bool:
    """DECISIONS #16: last `n_bars` bars each have true range <= shrink * prior
    bar's true range (contracting coil). Uses simple high-low range per bar
    within the sequence (close-to-close gaps negligible inside a coil)."""
    if len(bars) < n_bars + 1:
        return False
    window = bars[-(n_bars + 1):]
    ranges = [b.high - b.low for b in window]
    eps = 1e-9  # relative tolerance for float noise in range arithmetic
    return all(ranges[i + 1] <= shrink * ranges[i] * (1 + eps) and ranges[i] > 0
               for i in range(n_bars))


def cplq(bars: Sequence[Bar], band_lo: float, band_hi: float,
         n_bars: int = 4, shrink: float = 0.8) -> bool:
    """CPLQ (Part I 4.4): compression completing while price sits inside the
    QML band — compression + liquidity confluence flag."""
    if not compression(bars, n_bars, shrink):
        return False
    last = bars[-1]
    return band_lo <= last.close <= band_hi
