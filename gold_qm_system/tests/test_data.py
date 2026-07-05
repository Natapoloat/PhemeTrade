"""Data-layer tests. The HTF-alignment tests are anti-lookahead tests: an
unclosed higher-TF bar must be invisible at the lower TF, and changing FUTURE
data must never change PAST aligned values."""
import numpy as np
import pandas as pd
import pytest

from gold_qm_system.config import CostConfig, SessionConfig
from gold_qm_system.data import (
    assert_no_htf_leak,
    htf_view,
    load_ohlcv,
    normalize_ohlcv,
    resample_ohlcv,
    session_of,
    spread_at,
    timeframe_delta,
)


def make_m5(start="2024-01-02 00:00", periods=288, seed=7):
    """One day of synthetic M5 bars (UTC)."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range(start, periods=periods, freq="5min", tz="UTC")
    close = 2000 + np.cumsum(rng.normal(0, 1.0, periods))
    open_ = np.concatenate([[2000.0], close[:-1]])
    high = np.maximum(open_, close) + rng.uniform(0.1, 1.5, periods)
    low = np.minimum(open_, close) - rng.uniform(0.1, 1.5, periods)
    df = pd.DataFrame({"open": open_, "high": high, "low": low, "close": close}, index=idx)
    df.index.name = "open_time"
    df.attrs["timeframe"] = "M5"
    return df


# ---------------------------------------------------------------- loaders

def test_normalize_rejects_missing_columns():
    df = pd.DataFrame({"open": [1.0], "high": [2.0], "low": [0.5]},
                      index=pd.date_range("2024-01-01", periods=1, freq="5min", tz="UTC"))
    with pytest.raises(ValueError, match="missing required"):
        normalize_ohlcv(df, "M5")


def test_normalize_localizes_naive_timestamps_and_sorts():
    idx = pd.to_datetime(["2024-01-01 00:10", "2024-01-01 00:00", "2024-01-01 00:05"])
    df = pd.DataFrame({"open": [1, 1, 1], "high": [2, 2, 2], "low": [0.5] * 3, "close": [1.5] * 3},
                      index=idx, dtype=float)
    out = normalize_ohlcv(df, "M5")
    assert str(out.index.tz) == "UTC"
    assert out.index.is_monotonic_increasing


def test_load_csv_roundtrip(tmp_path):
    df = make_m5(periods=12)
    p = tmp_path / "XAUUSD_M5.csv"
    df.reset_index().to_csv(p, index=False)
    loaded = load_ohlcv(p, "M5")
    pd.testing.assert_frame_equal(loaded, df, check_freq=False)


def test_resample_label_is_open_time_and_ohlc_correct():
    m5 = make_m5(periods=24)  # 2 hours
    h1 = resample_ohlcv(m5, "H1")
    assert len(h1) == 2
    assert h1.index[0] == m5.index[0]  # left label = bucket open time
    first_bucket = m5.iloc[:12]
    assert h1["open"].iloc[0] == first_bucket["open"].iloc[0]
    assert h1["close"].iloc[0] == first_bucket["close"].iloc[-1]
    assert h1["high"].iloc[0] == first_bucket["high"].max()
    assert h1["low"].iloc[0] == first_bucket["low"].min()


# ------------------------------------------------- HTF alignment (anti-lookahead)

def test_htf_bar_invisible_until_it_closes():
    m5 = make_m5(periods=36)  # 3 hours: H1 bars at 00:00, 01:00, 02:00
    h1 = resample_ohlcv(m5, "H1")
    view = htf_view(m5, h1, "M5", "H1")

    # All M5 bars whose close is <= 01:00 must see NO H1 bar (first H1 closes at 01:00,
    # visible from the M5 bar closing at exactly 01:00, i.e. bar opening 00:55).
    ts_0000 = m5.index[0]                      # closes 00:05 -> nothing visible
    ts_0055 = m5.index[11]                     # closes 01:00 -> H1@00:00 visible (exact match)
    ts_0100 = m5.index[12]                     # closes 01:05 -> H1@00:00 visible, H1@01:00 NOT
    assert np.isnan(view.loc[ts_0000, "h1_close"])
    assert view.loc[ts_0055, "h1_close"] == h1["close"].iloc[0]
    assert view.loc[ts_0100, "h1_close"] == h1["close"].iloc[0]

    # The M5 bar opening 01:55 closes at 02:00 -> H1@01:00 (closes 02:00) becomes visible.
    ts_0155 = m5.index[23]
    assert view.loc[ts_0155, "h1_close"] == h1["close"].iloc[1]

    assert_no_htf_leak(m5, view, "M5", "h1_")


def test_future_htf_change_does_not_alter_past_view():
    """Anti-lookahead: mutate the FUTURE (last H1 bar) massively; every aligned
    value at earlier LTF timestamps must be bit-identical."""
    m5 = make_m5(periods=48)  # 4 hours
    h1 = resample_ohlcv(m5, "H1")
    view_before = htf_view(m5, h1, "M5", "H1")

    h1_mut = h1.copy()
    h1_mut.loc[h1_mut.index[-1], ["open", "high", "low", "close"]] = [9999.0, 10000.0, 9998.0, 9999.5]
    view_after = htf_view(m5, h1_mut, "M5", "H1")

    last_h1_close = h1.index[-1] + timeframe_delta("H1")
    unaffected = m5.index[(m5.index + timeframe_delta("M5")) < last_h1_close]
    pd.testing.assert_frame_equal(view_before.loc[unaffected], view_after.loc[unaffected])


def test_unclosed_partial_htf_bucket_never_leaks():
    """A partial (still-forming) HTF bucket produced by resampling must be
    invisible at every LTF bar inside it."""
    m5 = make_m5(periods=30)  # 2.5 hours -> 3rd H1 bucket (02:00) is partial
    h1 = resample_ohlcv(m5, "H1")
    assert len(h1) == 3
    view = htf_view(m5, h1, "M5", "H1")
    inside_partial = m5.index[m5.index >= h1.index[2]]
    for ts in inside_partial:
        # the partial bucket (open 02:00, nominal close 03:00) must not be referenced
        assert view.loc[ts, "h1_bar_close_time"] <= ts + timeframe_delta("M5")
        assert view.loc[ts, "h1_close"] == h1["close"].iloc[1]  # still sees 01:00 bar


def test_htf_view_rejects_wrong_direction():
    m5 = make_m5(periods=24)
    h1 = resample_ohlcv(m5, "H1")
    with pytest.raises(ValueError):
        htf_view(h1, m5, "H1", "M5")


# ------------------------------------------------------------ sessions & spread

def test_session_classification():
    s = SessionConfig()
    assert session_of(pd.Timestamp("2024-01-02 03:00", tz="UTC"), s) == "asian"
    assert session_of(pd.Timestamp("2024-01-02 08:00", tz="UTC"), s) == "london"
    assert session_of(pd.Timestamp("2024-01-02 14:00", tz="UTC"), s) == "overlap"
    assert session_of(pd.Timestamp("2024-01-02 18:00", tz="UTC"), s) == "newyork"
    assert session_of(pd.Timestamp("2024-01-02 22:00", tz="UTC"), s) == "off"


def test_spread_table_and_news_addon():
    s, c = SessionConfig(), CostConfig()
    t_overlap = pd.Timestamp("2024-01-02 14:00", tz="UTC")
    t_asian = pd.Timestamp("2024-01-02 03:00", tz="UTC")
    assert spread_at(t_overlap, s, c) == c.spread_overlap
    assert spread_at(t_asian, s, c) == c.spread_asian
    assert spread_at(t_overlap, s, c, in_news_window=True) == c.spread_overlap + c.spread_news_extra
    # off-session assumes the worst configured spread
    t_off = pd.Timestamp("2024-01-02 22:00", tz="UTC")
    assert spread_at(t_off, s, c) == max(c.spread_asian, c.spread_london, c.spread_newyork, c.spread_overlap)
