"""Engine tests: aggregator close-timing, incremental-indicator parity, a full
hand-crafted end-to-end QM trade, determinism, and engine-level anti-lookahead
(future data cannot change past decisions)."""
import numpy as np
import pandas as pd
import pytest

from gold_qm_system.config import SystemConfig
from gold_qm_system.data import resample_ohlcv
from gold_qm_system.engine import BarAggregator, run_backtest
from gold_qm_system.indicators import atr, rsi
from gold_qm_system.indicators.incremental import IncATR, IncRSI


# ------------------------------------------------------------- aggregator

def m5_times(start="2024-01-02 00:00", n=12):
    return pd.date_range(start, periods=n, freq="5min", tz="UTC")


def test_aggregator_emits_h1_exactly_when_final_m5_closes():
    agg = BarAggregator("M5", "H1")
    times = m5_times(n=12)
    emitted = []
    for j, t in enumerate(times):
        out = agg.add(t, 100.0 + j, 101.0 + j, 99.0 + j, 100.5 + j)
        if j < 11:
            assert out == []          # H1 not closed before the 00:55 bar
        emitted.extend(out)
    assert len(emitted) == 1
    bar = emitted[0]
    assert bar.time == times[0]       # labeled by bucket OPEN
    assert bar.open == 100.0 and bar.close == 111.5
    assert bar.high == 112.0 and bar.low == 99.0


def test_aggregator_flushes_partial_bucket_on_gap():
    agg = BarAggregator("M5", "H1")
    agg.add(pd.Timestamp("2024-01-02 00:00", tz="UTC"), 1, 2, 0.5, 1.5)
    out = agg.add(pd.Timestamp("2024-01-02 01:00", tz="UTC"), 5, 6, 4, 5.5)
    # the partial 00:00 bucket flushes when a 01:00-bucket bar arrives
    assert len(out) == 1 and out[0].time == pd.Timestamp("2024-01-02 00:00", tz="UTC")
    assert out[0].close == 1.5


def test_aggregator_passthrough_same_tf():
    agg = BarAggregator("H1", "H1")
    t = pd.Timestamp("2024-01-02 00:00", tz="UTC")
    out = agg.add(t, 1, 2, 0.5, 1.5)
    assert len(out) == 1 and out[0] == (t, 1, 2, 0.5, 1.5)


# ------------------------------------------------- incremental parity

def test_incremental_atr_rsi_match_vectorized():
    rng = np.random.default_rng(5)
    n = 120
    close = 2000 + np.cumsum(rng.normal(0, 2, n))
    high = close + rng.uniform(0.5, 3, n)
    low = close - rng.uniform(0.5, 3, n)
    df = pd.DataFrame({"open": close, "high": high, "low": low, "close": close},
                      index=pd.date_range("2024-01-02", periods=n, freq="1h", tz="UTC"))
    va, vr = atr(df, 21), rsi(df, 14)
    ia, ir = IncATR(21), IncRSI(14)
    for i in range(n):
        a = ia.update(high[i], low[i], close[i])
        r = ir.update(close[i])
        assert a == pytest.approx(va.iloc[i], rel=1e-12)
        if i >= 1:
            assert r == pytest.approx(vr.iloc[i], rel=1e-9)


# ------------------------------------------------- end-to-end integration

QM_BARS = [
    # (o, h, l, c) — hand-crafted H1 sequence forming a SELL QM
    (104.0, 105.0, 103.0, 104.0),   # b0  warmup
    (105.0, 110.0, 104.0, 106.0),   # b1  LS high 110 (QML)
    (106.0, 107.0, 105.0, 105.0),   # b2  confirms SH@110 (strength=1)
    (103.0, 104.0, 100.0, 101.0),   # b3  neck low 100
    (102.0, 105.0, 101.0, 104.0),   # b4  confirms SL@100
    (106.0, 115.0, 105.0, 112.0),   # b5  head 115 (Over)
    (110.0, 111.0, 106.0, 107.0),   # b6  confirms SH@115
    (100.0, 103.0, 95.0, 96.0),     # b7  under 95 (Under)
    (97.0, 99.0, 96.0, 98.0),       # b8  confirms SL@95 -> QM tradeable
    (99.0, 104.0, 98.0, 103.0),     # b9  rally toward zone
    (104.0, 110.2, 103.5, 104.5),   # b10 pin bar into zone -> SELL signal
    (105.0, 106.0, 104.0, 104.6),   # b11 entry fills at open
    (100.0, 101.0, 80.0, 82.0),     # b12 crash: target hit
]


def qm_config(**layer_overrides):
    cfg = SystemConfig.model_validate({
        "timeframes": {"directional": "H1", "setup": "H1", "entry": "H1"},
        "swings": {"swing_strength": 1},
        "sessions": {"allowed_sessions": ["asian", "london", "newyork", "overlap"]},
        # bias layer off: the crafted sequence is deliberately bias-ambiguous
        "layers": {"use_structure_bias": False, **layer_overrides},
    })
    return cfg


def qm_frame(bars=QM_BARS, start="2024-01-02 08:00"):
    idx = pd.date_range(start, periods=len(bars), freq="1h", tz="UTC")
    df = pd.DataFrame(bars, columns=["open", "high", "low", "close"], index=idx)
    df.index.name = "open_time"
    df.attrs["timeframe"] = "H1"
    return df


def test_end_to_end_sell_qm_trade():
    res = run_backtest(qm_config(), qm_frame())
    assert len(res.trades) == 1
    tr = res.trades[0]
    assert tr.direction == "sell"
    assert tr.exit_reason == "target"
    assert tr.meta["setup"] == "qm" and tr.meta["qml"] == 110.0
    assert tr.meta["trigger"] == "pin_bar"
    assert tr.meta["binding_method"] == "risk"
    # signal at b10 close -> fill at b11 open (B.1: no same-bar fill)
    assert tr.entry_time == qm_frame().index[11]
    assert tr.entry_price == pytest.approx(105.0 - 0.15 - 0.05)   # bid - slippage
    assert tr.r_multiple == pytest.approx(2.0, abs=0.15)          # min_rr target
    assert res.equity_curve.iloc[-1] > res.equity_curve.iloc[0]


def test_rr_to_structure_filter(monkeypatch):
    """Appendix K.1 #4: the fixture's room to the UNDER (95) is smaller than the
    stop distance (structural R:R < 1), so a threshold of 2 filters the trade;
    threshold 0 (default) trades it."""
    base = qm_config().model_dump()
    base["stops_targets"]["min_rr_to_structure"] = 2.0
    filtered = run_backtest(SystemConfig.model_validate(base), qm_frame())
    assert filtered.trades == []
    assert any(e["reason"] == "rr_to_structure" for e in filtered.skip_log)
    # default off -> trades as before
    assert len(run_backtest(qm_config(), qm_frame()).trades) == 1


def test_zone_stop_placement_tightens_stop_and_target(monkeypatch):
    """Appendix K.1 #3: anchoring the stop at the QML zone boundary (band top for
    a sell) instead of the head liquidity-grab yields a tighter stop, and the
    min_rr target therefore lands closer to entry. Same entry, still a target
    exit — only the geometry moves."""
    swing = run_backtest(qm_config(), qm_frame())
    base = qm_config().model_dump()
    base["stops_targets"]["stop_placement"] = "zone"
    zone = run_backtest(SystemConfig.model_validate(base), qm_frame())

    assert len(swing.trades) == 1 and len(zone.trades) == 1
    sw, zn = swing.trades[0], zone.trades[0]
    assert sw.direction == zn.direction == "sell"
    assert zn.entry_price == sw.entry_price                  # entry logic unchanged
    # stop anchored at band_hi(=110+tol) < head(115) -> strictly tighter
    assert zn.meta["init_stop"] < sw.meta["init_stop"]
    assert zn.meta["init_stop"] > zn.entry_price             # still a valid sell stop
    # tighter risk -> higher (closer) sell target price -> higher target exit
    assert sw.exit_reason == zn.exit_reason == "target"
    assert zn.exit_price > sw.exit_price


def test_no_trade_without_price_action_when_no_trigger():
    """Remove the pin bar (b10 becomes a bland zone-touch): with the PA layer
    ON there is no trigger -> no trade; with PA OFF the armed touch trades."""
    bars = list(QM_BARS)
    bars[10] = (104.0, 110.2, 103.5, 109.9)   # touch, but body top: not a sell pin
    with_pa = run_backtest(qm_config(), qm_frame(bars))
    assert all(t.meta.get("trigger") != "pin_bar" for t in with_pa.trades)
    no_pa = run_backtest(qm_config(use_price_action=False), qm_frame(bars))
    assert len(no_pa.trades) >= 1
    assert no_pa.trades[0].meta["trigger"] == "none"


def test_stale_qml_is_not_traded():
    """First retest happens WITHOUT a trigger and leaves the band; the second
    retest must not be traded (freshness rule A.3)."""
    bars = list(QM_BARS[:10])
    bars.append((104.0, 110.2, 103.5, 109.9))  # b10: touch, no pin (body at top)
    bars.append((104.0, 105.0, 103.0, 104.0))  # b11: leaves band -> stale
    bars.append((104.0, 110.2, 103.5, 104.5))  # b12: perfect pin, but too late
    bars.append((105.0, 106.0, 104.0, 104.6))
    res = run_backtest(qm_config(), qm_frame(bars))
    assert res.trades == []


def test_determinism_same_inputs_identical_results():
    r1 = run_backtest(qm_config(), qm_frame())
    r2 = run_backtest(qm_config(), qm_frame())
    assert r1.trades == r2.trades
    pd.testing.assert_series_equal(r1.equity_curve, r2.equity_curve)

    # also on noisy data with the full default layer stack
    rng = np.random.default_rng(9)
    n = 600
    close = 2000 + np.cumsum(rng.normal(0, 3, n))
    high = close + rng.uniform(0.5, 4, n)
    low = close - rng.uniform(0.5, 4, n)
    open_ = np.concatenate([[2000.0], close[:-1]])
    idx = pd.date_range("2024-01-02", periods=n, freq="5min", tz="UTC")
    noisy = pd.DataFrame({"open": open_, "high": np.maximum(high, open_),
                          "low": np.minimum(low, open_), "close": close}, index=idx)
    noisy.attrs["timeframe"] = "M5"
    cfg = SystemConfig.model_validate({
        "timeframes": {"directional": "H1", "setup": "M15", "entry": "M5"},
        "sessions": {"allowed_sessions": ["asian", "london", "newyork", "overlap"]},
    })
    a, b = run_backtest(cfg, noisy), run_backtest(cfg, noisy)
    assert a.trades == b.trades
    pd.testing.assert_series_equal(a.equity_curve, b.equity_curve)


def test_future_bars_cannot_change_past_decisions():
    """Engine-level anti-lookahead: run on a truncated history, then on the
    full history with a violent extra future bar — every decision up to the
    truncation point must be identical."""
    short = run_backtest(qm_config(), qm_frame(QM_BARS[:12]))     # through b11
    extended_bars = QM_BARS + [(82.0, 200.0, 81.0, 199.0)]        # insane future bar
    full = run_backtest(qm_config(), qm_frame(extended_bars))

    # the entry decision (made at b10 close, filled at b11 open) is unchanged
    assert len(short.trades) == 1 and len(full.trades) == 1
    s, f = short.trades[0], full.trades[0]
    assert (s.entry_time, s.entry_price, s.size, s.direction) == \
           (f.entry_time, f.entry_price, f.size, f.direction)
    # equity is bit-identical over the common (pre-divergence) window: bars
    # 0..10 close before any position exists
    common = short.equity_curve.index[:11]
    pd.testing.assert_series_equal(short.equity_curve.loc[common],
                                   full.equity_curve.loc[common])


def test_multi_tf_run_smoke_and_htf_bar_counts():
    """M5 entry / M15 setup / H1 directional on synthetic data: runs clean and
    the internal aggregation produced the expected HTF bar counts."""
    m5 = qm_frame([(100 + 0.01 * i, 101 + 0.01 * i, 99 + 0.01 * i, 100.5 + 0.01 * i)
                   for i in range(48)], start="2024-01-02 00:00")
    m5.index = pd.date_range("2024-01-02 00:00", periods=48, freq="5min", tz="UTC")
    m5.attrs["timeframe"] = "M5"
    h1 = resample_ohlcv(m5, "H1")
    assert len(h1) == 4
    cfg = SystemConfig.model_validate({
        "timeframes": {"directional": "H1", "setup": "M15", "entry": "M5"}})
    res = run_backtest(cfg, m5)
    assert res.trades == [] and not res.halted
