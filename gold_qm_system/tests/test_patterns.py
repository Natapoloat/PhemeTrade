"""Pattern tests with hand-crafted fixtures: valid sell/buy QM, invalid-order,
stale-QML, born-stale, invalidation; plus all A.5/A.6 trigger geometry."""
import pandas as pd
import pytest

from gold_qm_system.config import QMConfig
from gold_qm_system.indicators import SwingPoint
from gold_qm_system.patterns import (
    Bar,
    QMDetector,
    any_trigger,
    compression,
    cplq,
    engulfing,
    inside_bar_breakout,
    pin_bar,
    sfp,
)

T0 = pd.Timestamp("2024-01-02 00:00", tz="UTC")


def sw(kind, index, price, strength=3):
    t = T0 + pd.Timedelta(hours=index)
    return SwingPoint(kind, index, t, float(price),
                      index + strength, t + pd.Timedelta(hours=strength))


def feed_sell_qm(det, atr=2.0):
    """Valid SELL QM: LS 110 @10, neck 100 @15, head 115 @20 (Over),
    under 95 @25 (Under), confirmed at 28."""
    det.on_swing(sw("high", 10, 110), atr)
    det.on_swing(sw("low", 15, 100), atr)
    det.on_swing(sw("high", 20, 115), atr)
    return det.on_swing(sw("low", 25, 95), atr)


# ------------------------------------------------------------------ QM: valid

def test_valid_sell_qm_forms_with_correct_geometry():
    det = QMDetector(QMConfig())
    pat = feed_sell_qm(det)
    assert pat is not None and pat.direction == "sell"
    assert pat.qml == 110 and pat.status == "fresh"
    assert pat.qml_tol == pytest.approx(0.10 * 2.0)          # frozen ATR tol
    assert pat.tradeable_index == 28                          # pt5 confirmation
    # fib window prices: under 95 + [0.618, 0.786] * 20 = [107.36, 110.72]
    # zone = fib ∩ band[109.8, 110.2] = [109.8, 110.2]
    assert pat.zone_lo == pytest.approx(109.8)
    assert pat.zone_hi == pytest.approx(110.2)
    assert pat.stop_extreme == 115
    assert det.active_patterns(28) == [pat]
    assert det.active_patterns(27) == []                      # not visible earlier


def test_valid_buy_qm_mirror():
    det = QMDetector(QMConfig())
    det.on_swing(sw("low", 10, 90), 2.0)      # LS: QML = 90
    det.on_swing(sw("high", 15, 100), 2.0)    # neck
    det.on_swing(sw("low", 20, 85), 2.0)      # head breaks below 90 (Under)
    pat = det.on_swing(sw("high", 25, 105), 2.0)  # Over: breaks neck
    assert pat is not None and pat.direction == "buy"
    assert pat.qml == 90 and pat.stop_extreme == 85
    # fib: 105 - [0.786, 0.618]*20 = [89.28, 92.64]; band [89.8, 90.2]
    assert pat.zone_lo == pytest.approx(89.8)
    assert pat.zone_hi == pytest.approx(90.2)


# --------------------------------------------------------------- QM: invalid

def test_invalid_order_head_does_not_break_ls():
    det = QMDetector(QMConfig())
    det.on_swing(sw("high", 10, 110), 2.0)
    det.on_swing(sw("low", 15, 100), 2.0)
    det.on_swing(sw("high", 20, 109), 2.0)    # NO Over (109 < 110)
    assert det.on_swing(sw("low", 25, 95), 2.0) is None


def test_invalid_under_does_not_break_neck():
    det = QMDetector(QMConfig())
    det.on_swing(sw("high", 10, 110), 2.0)
    det.on_swing(sw("low", 15, 100), 2.0)
    det.on_swing(sw("high", 20, 115), 2.0)
    assert det.on_swing(sw("low", 25, 101), 2.0) is None      # 101 > neck 100


def test_lookback_exceeded_rejects_pattern():
    det = QMDetector(QMConfig(qm_lookback=10))                # pt5-pt2 = 15 > 10
    assert feed_sell_qm(det) is None


# ------------------------------------------------------- QM: freshness/stale

def test_first_touch_then_leave_marks_stale():
    det = QMDetector(QMConfig())
    pat = feed_sell_qm(det)
    # bar 30 rallies into the band [109.8, 110.2] -> first touch (still fresh)
    det.on_bar_close(30, high=110.0, low=107.0, close=108.0)
    assert pat.status == "fresh" and pat.in_first_touch and pat.touched
    assert pat.is_armed(110.0, 107.0, 108.0)                  # reached zone, closed below hi
    # bar 31 leaves the band entirely -> stale, no longer armable
    det.on_bar_close(31, high=108.0, low=105.0, close=106.0)
    assert pat.status == "stale"
    assert not pat.is_armed(110.0, 107.0, 108.0)
    assert det.active_patterns(31) == []


def test_born_stale_when_touched_before_confirmation():
    det = QMDetector(QMConfig())
    det.on_swing(sw("high", 10, 110), 2.0)
    det.on_swing(sw("low", 15, 100), 2.0)
    det.on_swing(sw("high", 20, 115), 2.0)
    # bars 26..28 happen between pt5 formation (25) and confirmation (28);
    # bar 27 rallies back into the QML band before we could ever act
    det.on_bar_close(26, high=104.0, low=96.0, close=103.0)
    det.on_bar_close(27, high=110.0, low=103.0, close=109.0)  # touches band
    det.on_bar_close(28, high=109.0, low=105.0, close=106.0)
    pat = det.on_swing(sw("low", 25, 95), 2.0)
    assert pat is not None and pat.status == "stale"
    assert det.active_patterns(28) == []


def test_close_beyond_head_invalidates():
    det = QMDetector(QMConfig())
    pat = feed_sell_qm(det)
    det.on_bar_close(30, high=116.0, low=110.0, close=115.5)  # close > head 115
    assert pat.status == "invalid"
    assert det.active_patterns(30) == []


def test_pass_through_band_during_formation_is_not_a_touch():
    """Bars BEFORE/AT the point-5 bar cross the QML on the way down; the
    pattern must still be born fresh (DECISIONS #23)."""
    det = QMDetector(QMConfig())
    det.on_swing(sw("high", 10, 110), 2.0)
    det.on_swing(sw("low", 15, 100), 2.0)
    det.on_swing(sw("high", 20, 115), 2.0)
    det.on_bar_close(22, high=113.0, low=108.0, close=109.0)  # through band, pre-pt5
    det.on_bar_close(25, high=101.0, low=95.0, close=96.0)    # the pt5 bar itself
    det.on_bar_close(28, high=99.0, low=96.0, close=98.0)
    pat = det.on_swing(sw("low", 25, 95), 2.0)
    assert pat is not None and pat.status == "fresh"


# ----------------------------------------------------------------- triggers

def test_pin_bar_geometry():
    sell_pin = Bar(open=101.5, high=110.0, low=100.0, close=100.8)
    assert pin_bar(sell_pin, "sell", 0.66)
    assert not pin_bar(sell_pin, "buy", 0.66)
    buy_pin = Bar(open=108.5, high=110.0, low=100.0, close=109.2)
    assert pin_bar(buy_pin, "buy", 0.66)
    small_wick = Bar(open=104.0, high=110.0, low=100.0, close=103.0)
    assert not pin_bar(small_wick, "sell", 0.66)


def test_engulfing_geometry():
    prev = Bar(open=105.0, high=106.0, low=103.0, close=104.0)   # down bar
    cur = Bar(open=103.5, high=107.0, low=103.0, close=106.5)    # engulfs, closes > prev.open
    assert engulfing(prev, cur, "buy")
    assert not engulfing(prev, cur, "sell")
    weak = Bar(open=103.5, high=107.0, low=103.0, close=104.5)   # covers? close < prev.open
    assert not engulfing(prev, weak, "buy")


def test_inside_bar_breakout_geometry():
    mother = Bar(open=105.0, high=110.0, low=100.0, close=104.0)
    inside = Bar(open=104.0, high=107.0, low=103.0, close=105.0)
    up = Bar(open=105.0, high=111.0, low=104.0, close=110.5)
    dn = Bar(open=105.0, high=106.0, low=98.0, close=99.0)
    assert inside_bar_breakout(mother, inside, up, "buy")
    assert inside_bar_breakout(mother, inside, dn, "sell")
    assert not inside_bar_breakout(mother, inside, up, "sell")
    not_inside = Bar(open=104.0, high=111.0, low=103.0, close=105.0)
    assert not inside_bar_breakout(mother, not_inside, up, "buy")


def test_any_trigger_returns_name():
    bars = [
        Bar(105.0, 110.0, 100.0, 104.0),
        Bar(104.0, 107.0, 103.0, 105.0),
        Bar(105.0, 111.0, 104.0, 110.5),
    ]
    assert any_trigger(bars, "buy") == "inside_bar_breakout"
    assert any_trigger([Bar(101.5, 110.0, 100.0, 100.8)], "sell") == "pin_bar"
    assert any_trigger([Bar(104.0, 106.0, 100.0, 105.0)], "sell") is None


def test_sfp_geometry():
    bar = Bar(open=109.0, high=111.0, low=108.0, close=108.5)
    assert sfp(bar, swing_level=110.0, direction="sell", wick_ratio=0.5)
    assert not sfp(bar, swing_level=112.0, direction="sell")   # never poked
    buy_bar = Bar(open=101.0, high=102.0, low=98.0, close=101.5)
    assert sfp(buy_bar, swing_level=100.0, direction="buy", wick_ratio=0.5)


def test_compression_and_cplq():
    def coil(rngs, center=100.0):
        return [Bar(center, center + r / 2, center - r / 2, center) for r in rngs]

    shrinking = coil([10, 8, 6.4, 5, 4])
    assert compression(shrinking, n_bars=4, shrink=0.8)
    expanding = coil([4, 5, 6.4, 8, 10])
    assert not compression(expanding, n_bars=4, shrink=0.8)
    # CPLQ: coil completes with close inside the band
    assert cplq(shrinking, band_lo=99.0, band_hi=101.0, n_bars=4, shrink=0.8)
    assert not cplq(shrinking, band_lo=110.0, band_hi=112.0, n_bars=4, shrink=0.8)
