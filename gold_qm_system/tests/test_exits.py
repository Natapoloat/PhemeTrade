"""Exit-geometry (Appendix J.2) white-box tests: breakeven rule, structural
trailing stop, gated CHoCH exit. These drive QMStrategy._manage_positions
directly against a SimBroker with a hand-placed position, so the exit logic is
tested in isolation from the entry funnel."""
import math

import pandas as pd
import pytest

from gold_qm_system.calendar import NewsCalendar
from gold_qm_system.config import SystemConfig
from gold_qm_system.engine.strategy import QMStrategy
from gold_qm_system.execution import KillSwitchMonitor, SimBroker
from gold_qm_system.execution.broker import Position
from gold_qm_system.execution.sim import _CostLedger
from gold_qm_system.indicators import SwingPoint
from gold_qm_system.structure import StructureEngine

T0 = pd.Timestamp("2024-01-02 12:00", tz="UTC")


def make_strategy(**st_overrides):
    cfg = SystemConfig.model_validate({
        "timeframes": {"directional": "H1", "setup": "H1", "entry": "H1"},
        "stops_targets": st_overrides,
    })
    broker = SimBroker(cfg.account.initial_equity, cfg.costs)
    ks = KillSwitchMonitor(cfg.kill_switches, cfg.account.initial_equity)
    strat = QMStrategy(cfg, broker, ks, NewsCalendar.empty())
    return cfg, broker, strat


def place(broker, direction, size, entry, stop, target=None):
    if target is None:
        target = math.inf if direction == "buy" else -math.inf
    pos = Position(1, direction, size, entry, stop, target, T0,
                   risk_amount=size * abs(entry - stop),
                   meta={"init_stop": stop})
    broker._positions[1] = pos
    broker._ledgers[1] = _CostLedger()
    broker._next_pos_id = 2
    return pos


def inject_setup_swing(strat, kind, price, atr=2.0):
    """Register a confirmed setup-TF swing and set setup ATR for the buffer."""
    sp = SwingPoint(kind, 10, T0, float(price), 13, T0 + pd.Timedelta(hours=3))
    strat.setup.structure.on_swing(sp, atr)
    strat.setup.atr.value = atr


# ------------------------------------------------------------- breakeven

def test_breakeven_moves_stop_to_entry_after_trigger():
    _, broker, strat = make_strategy(be_trigger_r=1.0, exit_mode="fixed_rr")
    pos = place(broker, "buy", size=10, entry=100.0, stop=95.0)   # 1R = 5.0/unit
    # +0.9R: no breakeven yet
    strat._manage_positions(T0, close=104.4)
    assert pos.stop == 95.0 and not pos.meta.get("be_done")
    # +1.0R: stop jumps to entry, once
    strat._manage_positions(T0 + pd.Timedelta(hours=1), close=105.0)
    assert pos.stop == 100.0 and pos.meta["be_done"] is True


def test_breakeven_sell_side():
    _, broker, strat = make_strategy(be_trigger_r=1.0)
    pos = place(broker, "sell", size=10, entry=100.0, stop=105.0)  # 1R = 5.0
    strat._manage_positions(T0, close=95.0)                        # +1R
    assert pos.stop == 100.0 and pos.meta["be_done"]


def test_breakeven_disabled_when_zero():
    _, broker, strat = make_strategy(be_trigger_r=0.0)
    pos = place(broker, "buy", size=10, entry=100.0, stop=95.0)
    strat._manage_positions(T0, close=120.0)                      # deep profit
    assert pos.stop == 95.0                                        # never moved


# ------------------------------------------------ structural trailing stop

def test_trail_structure_ratchets_stop_up_behind_swing_low():
    _, broker, strat = make_strategy(exit_mode="trail_structure", stop_atr_mult=0.25)
    pos = place(broker, "buy", size=10, entry=100.0, stop=95.0)
    inject_setup_swing(strat, "low", 98.0, atr=2.0)               # swing low 98
    strat._manage_positions(T0, close=105.0)
    assert pos.stop == pytest.approx(98.0 - 0.25 * 2.0)           # 97.5, tightened up
    # a LOWER subsequent swing low must NOT loosen the stop
    strat.setup.structure._lows[-1].swing = SwingPoint(
        "low", 20, T0, 96.0, 23, T0)                              # (lower) newer low
    strat._manage_positions(T0 + pd.Timedelta(hours=1), close=106.0)
    assert pos.stop == pytest.approx(97.5)                         # unchanged (tighten-only)


def test_trail_structure_sell_side():
    _, broker, strat = make_strategy(exit_mode="trail_structure", stop_atr_mult=0.25)
    pos = place(broker, "sell", size=10, entry=100.0, stop=105.0)
    inject_setup_swing(strat, "high", 102.0, atr=2.0)
    strat._manage_positions(T0, close=95.0)
    assert pos.stop == pytest.approx(102.0 + 0.25 * 2.0)          # 102.5

def test_no_trailing_in_fixed_mode():
    _, broker, strat = make_strategy(exit_mode="fixed_rr")
    pos = place(broker, "buy", size=10, entry=100.0, stop=95.0, target=110.0)
    inject_setup_swing(strat, "low", 98.0, atr=2.0)
    strat._manage_positions(T0, close=105.0)
    assert pos.stop == 95.0                                        # fixed mode: no trail


# --------------------------------------------------- CHoCH exit toggle

def _emit_counter_choch(strat, direction_against):
    """Force a setup-TF CHoCH event into last_events for this bar."""
    from gold_qm_system.structure.state_machine import StructureEvent
    strat.setup.last_events = [
        StructureEvent("CHOCH", direction_against, 5, T0, 100.0, 4)]


def test_choch_exit_closes_when_enabled():
    _, broker, strat = make_strategy(use_choch_exit=True)
    place(broker, "buy", size=10, entry=100.0, stop=95.0, target=110.0)
    _emit_counter_choch(strat, "down")                            # against a long
    strat._manage_positions(T0, close=101.0)
    recs = broker.process_bar(T0 + pd.Timedelta(hours=1), 101, 102, 100, 101, 0.3, False)
    assert len(recs) == 1 and recs[0].exit_reason == "choch_exit"


def test_choch_exit_ignored_when_disabled():
    _, broker, strat = make_strategy(use_choch_exit=False, exit_mode="trail_structure")
    place(broker, "buy", size=10, entry=100.0, stop=95.0)
    _emit_counter_choch(strat, "down")
    strat._manage_positions(T0, close=101.0)
    recs = broker.process_bar(T0 + pd.Timedelta(hours=1), 101, 102, 100, 101, 0.3, False)
    assert recs == [] and len(broker.open_positions()) == 1       # stayed open
