"""FVG (Fair Value Gap / imbalance) detection tests — Appendix K.1 #2.
Includes a no-lookahead check: an FVG at middle bar i depends only on bars
i-1..i+1, so appending future bars never changes already-found FVGs."""
from gold_qm_system.patterns import FVG, find_fvgs, leg_has_fvg


def test_bullish_fvg_detected():
    # bar0 high=10, bar1 (impulse) high=15 low=12, bar2 low=11 -> gap [10,11]
    highs = [10.0, 15.0, 13.0]
    lows = [8.0, 12.0, 11.0]
    fvgs = find_fvgs(highs, lows)
    assert len(fvgs) == 1
    assert fvgs[0].direction == "buy" and fvgs[0].mid_index == 1
    assert (fvgs[0].gap_lo, fvgs[0].gap_hi) == (10.0, 11.0)
    assert fvgs[0].size == 1.0


def test_bearish_fvg_detected():
    # bar0 low=20, bar1 impulse down, bar2 high=18 -> low[0]=20 > high[2]=18 -> gap [18,20]
    highs = [22.0, 21.0, 18.0]
    lows = [20.0, 16.0, 17.0]
    fvgs = find_fvgs(highs, lows)
    assert len(fvgs) == 1 and fvgs[0].direction == "sell"
    assert (fvgs[0].gap_lo, fvgs[0].gap_hi) == (18.0, 20.0)


def test_no_fvg_when_bars_overlap():
    # gentle overlapping drift -> no gap either direction
    highs = [10.0, 10.5, 11.0, 11.5]
    lows = [9.0, 9.5, 10.0, 10.5]
    assert find_fvgs(highs, lows) == []


def test_direction_filter_and_offset():
    highs = [10.0, 15.0, 13.0]
    lows = [8.0, 12.0, 11.0]
    assert find_fvgs(highs, lows, direction="sell") == []
    buy = find_fvgs(highs, lows, direction="buy", index_offset=100)
    assert buy[0].mid_index == 101


def test_leg_has_fvg_size_threshold():
    highs = [10.0, 15.0, 13.0]
    lows = [8.0, 12.0, 11.0]
    ok, size = leg_has_fvg(highs, lows, "buy", min_size=0.5)
    assert ok and size == 1.0
    ok2, _ = leg_has_fvg(highs, lows, "buy", min_size=2.0)   # gap 1.0 < 2.0
    assert not ok2
    ok3, _ = leg_has_fvg(highs, lows, "sell", min_size=0.0)  # wrong direction
    assert not ok3


def test_future_bars_do_not_change_past_fvgs():
    highs = [10.0, 15.0, 13.0, 20.0, 14.0]
    lows = [8.0, 12.0, 11.0, 18.0, 9.0]
    base = find_fvgs(highs[:3], lows[:3])
    extended = find_fvgs(highs, lows)
    # the FVG at mid_index 1 is identical whether or not later bars exist
    assert base[0] == next(f for f in extended if f.mid_index == 1)


def test_multiple_fvgs_returns_largest_in_leg():
    # bullish gaps: i=1 [10,11]=1, i=2 [15,18]=3, i=3 [13,20]=7 -> largest 7
    highs = [10.0, 15.0, 13.0, 20.0, 25.0, 22.0]
    lows = [8.0, 12.0, 11.0, 18.0, 20.0, 16.0]
    ok, size = leg_has_fvg(highs, lows, "buy")
    assert ok and size == 7.0
