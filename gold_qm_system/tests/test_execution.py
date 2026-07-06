"""Execution-sim, calendar and kill-switch tests. Includes the required cost
tests: costs reduce PnL; stop-fill slippage applies on stop exits; worst-case
intrabar sequencing (stop before target)."""
import pandas as pd
import pytest

from gold_qm_system.config import CostConfig, KillSwitchConfig
from gold_qm_system.calendar import NewsCalendar
from gold_qm_system.execution import KillSwitchMonitor, SimBroker, TradeRecord

T0 = pd.Timestamp("2024-01-02 10:00", tz="UTC")


def ts(hours):
    return T0 + pd.Timedelta(hours=hours)


def costs(**kw):
    base = dict(spread_asian=0.30, spread_london=0.30, spread_newyork=0.30,
                spread_overlap=0.30, spread_news_extra=0.50, base_slippage=0.05,
                stop_slippage_extra=0.15, news_slippage_extra=0.30,
                commission_per_unit=0.0, swap_long_per_unit_day=0.0,
                swap_short_per_unit_day=0.0)
    base.update(kw)
    return CostConfig(**base)


def open_long(broker, size=10.0, stop=1990.0, target=2020.0, risk=100.0):
    broker.submit_market("buy", size, stop, target, risk, {"tag": "t"})


# --------------------------------------------------------------- entry fills

def test_buy_entry_fills_at_open_plus_half_spread_plus_slippage():
    b = SimBroker(100_000, costs())
    open_long(b)
    b.process_bar(ts(0), open_=2000.0, high=2001.0, low=1999.0, close=2000.5,
                  spread=0.30, in_news=False)
    pos = b.open_positions()[0]
    assert pos.entry_price == pytest.approx(2000.0 + 0.15 + 0.05)


def test_news_window_adds_entry_slippage():
    b = SimBroker(100_000, costs())
    open_long(b)
    b.process_bar(ts(0), 2000.0, 2001.0, 1999.0, 2000.5, spread=0.80, in_news=True)
    pos = b.open_positions()[0]
    assert pos.entry_price == pytest.approx(2000.0 + 0.40 + 0.05 + 0.30)


# ----------------------------------------------------------------- cost tests

def test_costs_reduce_pnl_vs_frictionless():
    def run(cost_cfg):
        b = SimBroker(100_000, cost_cfg)
        open_long(b, size=10.0, stop=1990.0, target=2010.0)
        b.process_bar(ts(0), 2000.0, 2001.0, 1999.0, 2000.5, 0.30, False)
        # target bar: high must clear target + half spread
        recs = b.process_bar(ts(1), 2005.0, 2011.0, 2004.0, 2010.5, 0.30, False)
        assert len(recs) == 1 and recs[0].exit_reason == "target"
        return recs[0].net_pnl

    frictionless = costs(spread_asian=0.0, spread_london=0.0, spread_newyork=0.0,
                         spread_overlap=0.0, base_slippage=0.0, stop_slippage_extra=0.0)
    # note: frictionless run passes spread=0.30 to process_bar; use 0 instead
    b0 = SimBroker(100_000, frictionless)
    open_long(b0, size=10.0, stop=1990.0, target=2010.0)
    b0.process_bar(ts(0), 2000.0, 2001.0, 1999.0, 2000.5, 0.0, False)
    recs0 = b0.process_bar(ts(1), 2005.0, 2011.0, 2004.0, 2010.5, 0.0, False)
    pnl_free = recs0[0].net_pnl

    pnl_costly = run(costs(commission_per_unit=0.10))
    assert pnl_costly < pnl_free
    # entry paid half-spread + slippage (0.20) on 10 units + commission both sides
    assert pnl_free - pnl_costly == pytest.approx(0.20 * 10 + 0.10 * 10 * 2)


def test_stop_fill_slippage_applies_on_stop_exits():
    b = SimBroker(100_000, costs())
    open_long(b, size=10.0, stop=1990.0, target=2020.0)
    b.process_bar(ts(0), 2000.0, 2001.0, 1999.0, 2000.5, 0.30, False)
    # bid low = 1990.1 - 0.15 = 1989.95 <= 1990 -> stop triggers
    recs = b.process_bar(ts(1), 1995.0, 1996.0, 1990.1, 1991.0, 0.30, False)
    assert len(recs) == 1 and recs[0].exit_reason == "stop"
    assert recs[0].exit_price == pytest.approx(1990.0 - (0.05 + 0.15))  # worse than stop
    assert recs[0].net_pnl < 0
    stop_slips = [e for e in b.slippage_log if e["kind"] == "stop"]
    assert stop_slips and stop_slips[0]["modeled_slippage"] > 0


def test_worst_case_sequencing_stop_fills_when_both_in_range():
    b = SimBroker(100_000, costs())
    open_long(b, size=10.0, stop=1995.0, target=2005.0)
    b.process_bar(ts(0), 2000.0, 2001.0, 1999.0, 2000.5, 0.30, False)
    # one wide bar contains BOTH stop and target -> STOP must fill
    recs = b.process_bar(ts(1), 2000.0, 2010.0, 1990.0, 2008.0, 0.30, False)
    assert len(recs) == 1 and recs[0].exit_reason == "stop"


def test_gap_through_stop_fills_at_worse_open():
    b = SimBroker(100_000, costs())
    open_long(b, size=10.0, stop=1990.0, target=2020.0)
    b.process_bar(ts(0), 2000.0, 2001.0, 1999.0, 2000.5, 0.30, False)
    recs = b.process_bar(ts(1), 1980.0, 1982.0, 1978.0, 1981.0, 0.30, False)
    assert recs[0].exit_reason == "stop"
    assert recs[0].exit_price == pytest.approx(1980.0 - 0.15 - 0.20)  # open bid - stop slip
    assert recs[0].exit_price < 1990.0


def test_target_is_limit_fill_exact_price_and_needs_spread_clearance():
    b = SimBroker(100_000, costs())
    open_long(b, size=10.0, stop=1990.0, target=2010.0)
    b.process_bar(ts(0), 2000.0, 2001.0, 1999.0, 2000.5, 0.30, False)
    # high 2010.05: bid high = 2009.90 < 2010 -> NOT filled
    recs = b.process_bar(ts(1), 2005.0, 2010.05, 2004.0, 2009.0, 0.30, False)
    assert recs == []
    # high 2010.20: bid high = 2010.05 >= 2010 -> filled AT 2010 exactly
    recs = b.process_bar(ts(2), 2006.0, 2010.20, 2005.0, 2010.0, 0.30, False)
    assert recs[0].exit_reason == "target" and recs[0].exit_price == 2010.0


# --------------------------------------------------- stops, trims, swap

def test_modify_stop_tighten_only():
    b = SimBroker(100_000, costs())
    open_long(b, stop=1990.0)
    b.process_bar(ts(0), 2000.0, 2001.0, 1999.0, 2000.5, 0.30, False)
    pid = b.open_positions()[0].pos_id
    b.modify_stop(pid, 1995.0)                     # tighten: ok
    with pytest.raises(ValueError):
        b.modify_stop(pid, 1985.0)                 # loosen: forbidden (8.3)


def test_partial_close_fills_next_open_and_reduces_size():
    b = SimBroker(100_000, costs())
    open_long(b, size=10.0, stop=1990.0, target=2050.0, risk=100.0)
    b.process_bar(ts(0), 2000.0, 2001.0, 1999.0, 2000.5, 0.30, False)
    pid = b.open_positions()[0].pos_id
    b.request_close(pid, 4.0, "trim")
    recs = b.process_bar(ts(1), 2005.0, 2006.0, 2004.0, 2005.5, 0.30, False)
    assert recs[0].exit_reason == "trim" and recs[0].size == 4.0
    assert recs[0].exit_price == pytest.approx(2005.0 - 0.15 - 0.05)  # sell at bid - slip
    assert b.open_positions()[0].size == pytest.approx(6.0)
    # 1R attribution is pro-rata
    assert b.open_positions()[0].risk_amount == pytest.approx(60.0)


def test_swap_charged_on_day_rollover_and_tripled():
    c = costs(swap_long_per_unit_day=-0.50, swap_triple_weekday=2)  # Wed
    b = SimBroker(100_000, c)
    open_long(b, size=10.0, stop=1900.0, target=2100.0)
    b.process_bar(pd.Timestamp("2024-01-02 23:00", tz="UTC"), 2000, 2001, 1999, 2000, 0.0, False)
    cash_before = b.equity()
    # Tuesday -> Wednesday rollover: 3x swap
    b.process_bar(pd.Timestamp("2024-01-03 00:00", tz="UTC"), 2000, 2001, 1999, 2000, 0.0, False)
    assert b.equity() == pytest.approx(cash_before - 0.50 * 10 * 3)


# --------------------------------------------------------------- calendar

def test_calendar_blackout_window_and_impact_filter(tmp_path):
    p = tmp_path / "cal.csv"
    p.write_text("timestamp_utc,impact,currency,title\n"
                 "2024-01-05 13:30,high,USD,NFP\n"
                 "2024-01-06 10:00,medium,USD,minor\n", encoding="utf-8")
    cal = NewsCalendar.from_csv(p)
    nfp = pd.Timestamp("2024-01-05 13:30", tz="UTC")
    assert cal.in_blackout(nfp, 30)
    assert cal.in_blackout(nfp - pd.Timedelta(minutes=30), 30)      # inclusive edge
    assert not cal.in_blackout(nfp - pd.Timedelta(minutes=31), 30)
    assert not cal.in_blackout(pd.Timestamp("2024-01-06 10:00", tz="UTC"), 30, "high")
    assert cal.in_blackout(pd.Timestamp("2024-01-06 10:00", tz="UTC"), 30, "medium")
    assert not NewsCalendar.empty().in_blackout(nfp, 30)


# ------------------------------------------------------------- kill-switches

def kcfg(**kw):
    base = dict(daily_loss_r=2.0, daily_loss_pct=0.03, max_consec_losses=4,
                spread_cap=1.5, vol_cap_atr_mult=3.0, max_total_dd=0.15)
    base.update(kw)
    return KillSwitchConfig(**base)


def loss_trade(r=-1.1, pnl=-1100.0, reason="stop"):
    return TradeRecord(1, "buy", 10.0, 2000.0, 1990.0, ts(0), ts(1), 1990.0,
                       pnl, 0.0, pnl, r, reason, {})


def test_daily_loss_r_limit_halts_and_resets_next_day():
    m = KillSwitchMonitor(kcfg(), 100_000)
    m.on_bar(ts(0), 100_000, 100_000, 0.3, 1.0, 5.0)
    m.on_trade_closed(loss_trade(r=-1.1))
    assert m.allow_new_entries()[0]
    m.on_trade_closed(loss_trade(r=-1.0))
    ok, why = m.allow_new_entries()
    assert not ok and why == "daily_loss_r_limit"
    # next UTC day resets the daily counters
    m.on_bar(ts(24), 98_000, 98_000, 0.3, 1.0, 5.0)
    assert m.allow_new_entries()[0]


def test_daily_loss_pct_limit():
    m = KillSwitchMonitor(kcfg(), 100_000)
    m.on_bar(ts(0), 100_000, 100_000, 0.3, 1.0, 5.0)
    m.on_trade_closed(loss_trade(r=-1.0, pnl=-3100.0))
    ok, why = m.allow_new_entries()
    assert not ok and why == "daily_loss_pct_limit"


def test_consecutive_losses_pause_holds_then_auto_resumes():
    """DECISIONS #27: the pause holds for consec_pause_days (simulated manual
    review) then auto-resumes with the loss counter reset."""
    m = KillSwitchMonitor(kcfg(max_consec_losses=3, consec_pause_days=5), 100_000)
    m.on_bar(ts(0), 100_000, 100_000, 0.3, 1.0, 5.0)
    for i in range(3):
        m.on_bar(ts(i * 30), 100_000, 100_000, 0.3, 1.0, 5.0)  # spread days out
        m.on_trade_closed(loss_trade(r=-0.1, pnl=-100.0))
    pause_start = loss_trade().exit_time                        # ts(1)
    ok, why = m.allow_new_entries()
    assert not ok and why == "consecutive_losses_pause"
    # still paused within the window
    m.on_bar(pause_start + pd.Timedelta(days=4), 100_000, 100_000, 0.3, 1.0, 5.0)
    assert not m.allow_new_entries()[0]
    # auto-resumes after consec_pause_days; one new loss does NOT re-latch
    m.on_bar(pause_start + pd.Timedelta(days=5, hours=1), 100_000, 100_000, 0.3, 1.0, 5.0)
    assert m.allow_new_entries()[0]
    m.on_trade_closed(loss_trade(r=-0.1, pnl=-100.0))
    assert m.allow_new_entries()[0]


def test_consecutive_losses_manual_reset_still_works():
    m = KillSwitchMonitor(kcfg(max_consec_losses=2, consec_pause_days=5), 100_000)
    m.on_bar(ts(0), 100_000, 100_000, 0.3, 1.0, 5.0)
    m.on_trade_closed(loss_trade(r=-0.1, pnl=-100.0))
    m.on_trade_closed(loss_trade(r=-0.1, pnl=-100.0))
    assert m.allow_new_entries() == (False, "consecutive_losses_pause")
    m.reset_consecutive_pause()
    assert m.allow_new_entries()[0]


def test_entry_gap_through_target_or_stop_is_rejected():
    """DECISIONS #28: don't chase a runaway open past the order's own target,
    and don't enter straight into a stop-out."""
    b = SimBroker(100_000, costs())
    # buy queued with target 2010; next bar opens ABOVE the target -> reject
    open_long(b, size=10.0, stop=1990.0, target=2010.0)
    b.process_bar(ts(0), 2015.0, 2016.0, 2014.0, 2015.5, 0.30, False)
    assert b.open_positions() == [] and len(b.rejected_entries) == 1
    assert b.rejected_entries[0]["would_fill"] >= 2010.0
    # buy queued with stop 1990; next bar opens BELOW the stop -> reject
    open_long(b, size=10.0, stop=1990.0, target=2010.0)
    b.process_bar(ts(1), 1985.0, 1986.0, 1984.0, 1985.5, 0.30, False)
    assert b.open_positions() == [] and len(b.rejected_entries) == 2
    # normal open between stop and target -> fills
    open_long(b, size=10.0, stop=1990.0, target=2010.0)
    b.process_bar(ts(2), 2000.0, 2001.0, 1999.0, 2000.5, 0.30, False)
    assert len(b.open_positions()) == 1 and len(b.rejected_entries) == 2


def test_trim_exits_do_not_count_as_losses():
    m = KillSwitchMonitor(kcfg(max_consec_losses=2), 100_000)
    m.on_bar(ts(0), 100_000, 100_000, 0.3, 1.0, 5.0)
    for _ in range(5):
        m.on_trade_closed(loss_trade(r=-0.1, pnl=-10.0, reason="trim"))
    assert m.allow_new_entries()[0]


def test_spread_and_vol_circuit_breakers():
    m = KillSwitchMonitor(kcfg(), 100_000)
    m.on_bar(ts(0), 100_000, 100_000, spread=2.0, true_range=1.0, atr_value=5.0)
    assert m.allow_new_entries() == (False, "spread_circuit_breaker")
    m.on_bar(ts(1), 100_000, 100_000, spread=0.3, true_range=20.0, atr_value=5.0)
    assert m.allow_new_entries() == (False, "volatility_circuit_breaker")
    m.on_bar(ts(2), 100_000, 100_000, spread=0.3, true_range=4.0, atr_value=5.0)
    assert m.allow_new_entries()[0]


def test_equity_floor_hard_stop_is_permanent():
    m = KillSwitchMonitor(kcfg(max_total_dd=0.15), 100_000)
    m.on_bar(ts(0), 110_000, 110_000, 0.3, 1.0, 5.0)   # peak 110k
    m.on_bar(ts(1), 93_000, 93_000, 0.3, 1.0, 5.0)     # dd 15.45% -> hard stop
    assert m.hard_stopped
    assert m.allow_new_entries() == (False, "equity_floor_hard_stop")
    m.on_bar(ts(2), 120_000, 120_000, 0.3, 1.0, 5.0)   # recovery does NOT unlatch
    assert m.hard_stopped
