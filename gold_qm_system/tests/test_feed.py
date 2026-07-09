"""Feed tests. The MT5 live feed's connection is exercised by the live self-test
(scripts/forwardtest_exness.py --selftest); here we cover its pure, MT5-free
logic: timeframe validation and the polling cadence derived per timeframe."""
import pytest

from gold_qm_system.engine.feed import MT5LiveFeed


def test_mt5_feed_poll_seconds_default_scales_with_timeframe():
    assert MT5LiveFeed(timeframe="M15").poll_seconds == 30.0     # 15*60/30
    assert MT5LiveFeed(timeframe="M5").poll_seconds == 10.0      # 5*60/30
    assert MT5LiveFeed(timeframe="M1").poll_seconds == 2.0       # floored at 2s
    assert MT5LiveFeed(timeframe="M5", poll_seconds=1.0).poll_seconds == 1.0  # explicit wins


def test_mt5_feed_rejects_unknown_timeframe():
    with pytest.raises(ValueError):
        MT5LiveFeed(timeframe="M7")


def test_mt5_feed_construction_is_inert_until_iterated():
    f = MT5LiveFeed(symbol="XAUUSD", timeframe="M15", warmup_bars=500, max_live_bars=0)
    # nothing connects at construction time
    assert f.symbol is None and f._mt5 is None
    assert f.warmup_end_time is None
    assert f.max_live_bars == 0 and f.warmup_bars == 500
    f.stop()
    assert f._stopped is True
