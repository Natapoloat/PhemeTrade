"""Structure state-machine tests (Appendix A.2) with hand-crafted swing
sequences: bias detection, BOS -> CHoCH -> MSS ordering, ranging tie-break."""
import pandas as pd

from gold_qm_system.indicators import SwingPoint
from gold_qm_system.structure import StructureEngine

T0 = pd.Timestamp("2024-01-02 00:00", tz="UTC")


def sw(kind, index, price, strength=3):
    t = T0 + pd.Timedelta(hours=index)
    return SwingPoint(kind, index, t, float(price),
                      index + strength, t + pd.Timedelta(hours=strength))


def close_bar(eng, index, price):
    return eng.on_bar_close(index, T0 + pd.Timedelta(hours=index), float(price))


def build_uptrend(eng, atr=1.0):
    """SL@100, SH@110, SL@105, SH@115 -> bullish."""
    eng.on_swing(sw("low", 0, 100), atr)
    eng.on_swing(sw("high", 5, 110), atr)
    eng.on_swing(sw("low", 10, 105), atr)
    eng.on_swing(sw("high", 15, 115), atr)


def test_bias_needs_two_of_each_and_detects_bullish():
    eng = StructureEngine(range_atr_mult=0.5)
    eng.on_swing(sw("low", 0, 100), 1.0)
    eng.on_swing(sw("high", 5, 110), 1.0)
    assert eng.bias == "ranging"          # only 1 SH + 1 SL so far
    eng.on_swing(sw("low", 10, 105), 1.0)
    assert eng.bias == "ranging"
    eng.on_swing(sw("high", 15, 115), 1.0)
    assert eng.bias == "bullish"


def test_bearish_bias():
    eng = StructureEngine()
    eng.on_swing(sw("high", 0, 120), 1.0)
    eng.on_swing(sw("low", 5, 110), 1.0)
    eng.on_swing(sw("high", 10, 115), 1.0)
    eng.on_swing(sw("low", 15, 105), 1.0)
    assert eng.bias == "bearish"


def test_ranging_tiebreak_both_sides_flat():
    eng = StructureEngine(range_atr_mult=0.5)  # tol = 0.5 * ATR
    eng.on_swing(sw("low", 0, 100.00), 1.0)
    eng.on_swing(sw("high", 5, 110.00), 1.0)
    eng.on_swing(sw("low", 10, 100.05), 1.0)   # ΔSL = 0.05 < 0.5
    eng.on_swing(sw("high", 15, 110.10), 1.0)  # ΔSH = 0.10 < 0.5
    assert eng.bias == "ranging"               # ascending, but both flat vs tol


def test_mixed_swings_are_ranging():
    eng = StructureEngine()
    eng.on_swing(sw("low", 0, 100), 1.0)
    eng.on_swing(sw("high", 5, 110), 1.0)
    eng.on_swing(sw("low", 10, 95), 1.0)       # SL descending
    eng.on_swing(sw("high", 15, 115), 1.0)     # SH ascending
    assert eng.bias == "ranging"


def test_bos_choch_mss_sequence_flips_bias():
    eng = StructureEngine()
    build_uptrend(eng)
    assert eng.bias == "bullish"

    # BOS: close above SH@115; major low becomes SL@105
    ev = close_bar(eng, 20, 116)
    assert [e.kind for e in ev] == ["BOS"]
    assert ev[0].direction == "up" and ev[0].level == 115

    # a new higher low confirms, then gets broken -> CHoCH (warning only)
    eng.on_swing(sw("low", 22, 108), 1.0)
    ev = close_bar(eng, 26, 107)
    assert [e.kind for e in ev] == ["CHOCH"]
    assert ev[0].direction == "down" and ev[0].level == 108
    assert eng.bias == "bullish"               # CHoCH does NOT flip bias

    # MSS: close below the major low (105) -> bias flips bearish
    ev = close_bar(eng, 28, 104)
    assert "MSS" in [e.kind for e in ev]
    mss = next(e for e in ev if e.kind == "MSS")
    assert mss.direction == "down" and mss.level == 105
    assert eng.bias == "bearish"


def test_choch_fires_once_until_next_bos():
    eng = StructureEngine()
    build_uptrend(eng)
    close_bar(eng, 20, 116)                    # BOS
    eng.on_swing(sw("low", 22, 108), 1.0)
    ev1 = close_bar(eng, 26, 107.5)            # CHoCH
    assert [e.kind for e in ev1] == ["CHOCH"]
    eng.on_swing(sw("low", 27, 107), 1.0)      # another counter-side swing
    ev2 = close_bar(eng, 31, 106.5)            # breaks it, but CHoCH already seen
    assert "CHOCH" not in [e.kind for e in ev2]


def test_no_events_while_ranging():
    eng = StructureEngine()
    eng.on_swing(sw("low", 0, 100), 1.0)
    eng.on_swing(sw("high", 5, 110), 1.0)
    assert close_bar(eng, 8, 120) == []        # huge close, but no bias yet


def test_bos_requires_new_swing_after_break():
    eng = StructureEngine()
    build_uptrend(eng)
    ev = close_bar(eng, 20, 116)
    assert [e.kind for e in ev] == ["BOS"]
    ev = close_bar(eng, 21, 117)               # even higher close, same swing
    assert ev == []                            # already broken; no re-fire


def test_mss_up_from_bearish():
    eng = StructureEngine()
    eng.on_swing(sw("high", 0, 120), 1.0)
    eng.on_swing(sw("low", 5, 110), 1.0)
    eng.on_swing(sw("high", 10, 115), 1.0)
    eng.on_swing(sw("low", 15, 105), 1.0)
    assert eng.bias == "bearish"
    ev = close_bar(eng, 20, 104)               # BOS down; major high = SH@115
    assert [e.kind for e in ev] == ["BOS"]
    ev = close_bar(eng, 25, 116)               # breaks major high -> MSS up
    kinds = [e.kind for e in ev]
    assert "MSS" in kinds
    assert eng.bias == "bullish"
