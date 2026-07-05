"""Indicator tests — including the two core anti-lookahead guarantees:
(1) swings never emit before i+R and are immune to future data;
(2) causal prefix-consistency of ATR/RSI."""
import numpy as np
import pandas as pd
import pytest

from gold_qm_system.indicators import (
    SwingDetector,
    atr,
    detect_swings,
    rsi,
    true_range,
)


def make_bars(highs, lows, start="2024-01-02", freq="1h"):
    idx = pd.date_range(start, periods=len(highs), freq=freq, tz="UTC")
    highs = np.asarray(highs, dtype=float)
    lows = np.asarray(lows, dtype=float)
    mid = (highs + lows) / 2
    return pd.DataFrame({"open": mid, "high": highs, "low": lows, "close": mid}, index=idx)


# ------------------------------------------------------------------ ATR / RSI

def test_true_range_uses_prev_close_gap():
    df = make_bars([10, 20], [9, 19])
    df.loc[df.index[1], "close"] = 19.5
    tr = true_range(df)
    assert tr.iloc[0] == 1.0                       # first bar: high - low
    assert tr.iloc[1] == 20 - min(19, df["close"].iloc[0])  # gap vs prev close


def test_atr_matches_manual_ema_recursion():
    rng = np.random.default_rng(3)
    n, period = 60, 21
    highs = 100 + np.cumsum(rng.normal(0, 1, n)) + rng.uniform(0.5, 2, n)
    lows = highs - rng.uniform(1, 4, n)
    df = make_bars(highs, lows)
    tr = true_range(df).to_numpy()
    k = 2.0 / (period + 1)
    manual = np.empty(n)
    manual[0] = tr[0]
    for i in range(1, n):
        manual[i] = manual[i - 1] + k * (tr[i] - manual[i - 1])
    np.testing.assert_allclose(atr(df, period).to_numpy(), manual, rtol=1e-12)


@pytest.mark.parametrize("func,kwargs", [(atr, {"period": 21}), (rsi, {"period": 14})])
def test_indicator_prefix_consistency_no_lookahead(func, kwargs):
    """Value at bar t computed on full data == value computed on data[:t+1].
    This is the property that makes precomputing indicators lookahead-safe."""
    rng = np.random.default_rng(11)
    n = 80
    highs = 2000 + np.cumsum(rng.normal(0, 2, n)) + rng.uniform(0.5, 3, n)
    lows = highs - rng.uniform(1, 5, n)
    df = make_bars(highs, lows)
    full = func(df, **kwargs)
    for t in (30, 55, n - 1):
        prefix = func(df.iloc[: t + 1], **kwargs)
        assert prefix.iloc[-1] == pytest.approx(full.iloc[t], rel=1e-12, nan_ok=True)


def test_rsi_bounds_and_direction():
    up = make_bars(np.arange(100, 130.0), np.arange(99, 129.0))
    dn = make_bars(np.arange(130, 100, -1.0), np.arange(129, 99, -1.0))
    assert rsi(up).iloc[-1] > 70
    assert rsi(dn).iloc[-1] < 30
    assert rsi(up).dropna().between(0, 100).all()


# ------------------------------------------------------- swings (repaint-safe)

def spike_bars(n=40, spike_at=20, strength=3):
    """Flat-ish series with one clear swing high at `spike_at`."""
    highs = np.full(n, 100.0) + np.linspace(0, 0.1, n)  # tiny drift, no ties
    lows = highs - 1.0
    highs[spike_at] = 105.0
    lows[spike_at - 5] = 95.0  # and one clear swing low earlier
    return make_bars(highs, lows), spike_at


def test_swing_emitted_exactly_at_i_plus_R():
    strength = 3
    df, spike = spike_bars()
    det = SwingDetector(strength)
    emitted_at: dict[int, int] = {}
    for j, (t, row) in enumerate(zip(df.index, df[["high", "low"]].itertuples(index=False))):
        for sw in det.update(t, row.high, row.low):
            emitted_at[sw.index] = j
            assert sw.confirmed_index == sw.index + strength
    assert emitted_at[spike] == spike + strength          # not one bar earlier or later
    assert (spike - 5) in emitted_at                       # the swing low was found too


def test_swing_never_visible_before_confirmation():
    """Feed bars one at a time; at every step, the set of known swings must
    contain only swings with confirmed_index <= current bar."""
    df, _ = spike_bars()
    det = SwingDetector(3)
    known = []
    for j, (t, row) in enumerate(zip(df.index, df[["high", "low"]].itertuples(index=False))):
        known.extend(det.update(t, row.high, row.low))
        assert all(sw.confirmed_index <= j for sw in known)


def test_future_spike_does_not_change_past_swings():
    """Anti-lookahead: a huge spike appended AFTER confirmation cannot alter
    already-emitted swings."""
    strength = 3
    df, spike = spike_bars()
    upto = spike + strength  # bar at which the swing is confirmed
    base = detect_swings(df.iloc[: upto + 1], strength)

    df_mut = df.copy()
    df_mut.loc[df_mut.index[upto + 2], ["high"]] = 999.0   # future spike
    mut = detect_swings(df_mut, strength)
    mut_upto = [s for s in mut if s.confirmed_index <= upto]
    assert base == mut_upto


def test_tie_does_not_confirm_swing():
    highs = np.full(10, 100.0)
    highs[4] = 105.0
    highs[5] = 105.0  # tie with bar 4 inside its window
    lows = highs - 1
    df = make_bars(highs, lows)
    swings = detect_swings(df, 3)
    assert not any(s.kind == "high" and s.index in (4, 5) for s in swings)


def test_vectorized_matches_incremental():
    rng = np.random.default_rng(42)
    n = 200
    highs = 2000 + np.cumsum(rng.normal(0, 2, n)) + rng.uniform(0.5, 3, n)
    lows = highs - rng.uniform(1, 5, n)
    df = make_bars(highs, lows)
    det = SwingDetector(3)
    inc = []
    for t, row in zip(df.index, df[["high", "low"]].itertuples(index=False)):
        inc.extend(det.update(t, row.high, row.low))
    assert inc == detect_swings(df, 3)
    assert len(inc) > 0
