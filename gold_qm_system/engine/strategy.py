"""QM strategy — the SINGLE signal-generation code path shared by backtest,
paper and live runners (Appendix C/H requirement).

The strategy consumes CLOSED entry-TF bars only and internally aggregates
setup-TF and directional-TF bars (engine.aggregator), so higher-TF leakage is
impossible by construction. All venue interaction goes through BrokerAdapter.

Decision timing (B.1): everything below happens at the CLOSE of an entry-TF
bar; resulting orders fill at the NEXT bar's open in the broker.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from gold_qm_system.calendar import NewsCalendar
from gold_qm_system.config import SystemConfig
from gold_qm_system.data import session_of, timeframe_delta
from gold_qm_system.execution import BrokerAdapter, KillSwitchMonitor, TradeRecord
from gold_qm_system.indicators import SwingDetector
from gold_qm_system.indicators.incremental import IncATR, IncPercentile, IncRSI
from gold_qm_system.patterns import Bar, QMDetector, QMPattern, any_trigger, cplq, sfp
from gold_qm_system.risk import (
    OpenPositionState,
    build_stop_and_target,
    compute_size,
    ongoing_trim_size,
    remaining_risk_budget_fraction,
)
from gold_qm_system.structure import StructureEngine
from .aggregator import BarAggregator, ClosedBar


@dataclass
class _TFState:
    """Per-timeframe incremental state driven by that TF's CLOSED bars."""
    swings: SwingDetector
    structure: StructureEngine
    atr: IncATR
    qm: Optional[QMDetector] = None
    bar_count: int = field(default=0, init=False)
    last_mss_direction: Optional[str] = field(default=None, init=False)

    def process(self, bar: ClosedBar) -> None:
        i = self.bar_count
        self.bar_count += 1
        atr_val = self.atr.update(bar.high, bar.low, bar.close)
        if self.qm is not None:
            self.qm.on_bar_close(i, bar.high, bar.low, bar.close)  # before swings (QMDetector order)
        for sw_pt in self.swings.update(bar.time, bar.high, bar.low):
            self.structure.on_swing(sw_pt, atr_val)
            if self.qm is not None:
                self.qm.on_swing(sw_pt, atr_val)
        for ev in self.structure.on_bar_close(i, bar.time, bar.close):
            if ev.kind == "MSS":
                self.last_mss_direction = "buy" if ev.direction == "up" else "sell"
            self.last_events.append(ev)

    def __post_init__(self):
        self.last_events: list = []   # events emitted by the most recent process()

    def begin_bar(self) -> None:
        self.last_events = []


class QMStrategy:
    def __init__(self, cfg: SystemConfig, broker: BrokerAdapter,
                 killswitch: KillSwitchMonitor, calendar: NewsCalendar):
        self.cfg = cfg
        self.broker = broker
        self.ks = killswitch
        self.calendar = calendar

        tfs = cfg.timeframes
        self.entry_delta = timeframe_delta(tfs.entry)
        self._agg_setup = BarAggregator(tfs.entry, tfs.setup)
        self._agg_dir = BarAggregator(tfs.entry, tfs.directional)

        def make_state(with_qm: bool) -> _TFState:
            return _TFState(
                swings=SwingDetector(cfg.swings.swing_strength),
                structure=StructureEngine(cfg.structure.range_atr_mult),
                atr=IncATR(cfg.indicators.atr_period),
                qm=QMDetector(cfg.qm) if with_qm else None,
            )

        self.setup = make_state(with_qm=True)
        self.directional = make_state(with_qm=False)
        self.entry_atr = IncATR(cfg.indicators.atr_period)
        self.entry_rsi = IncRSI(cfg.indicators.rsi_period)
        self.entry_pctile = IncPercentile(cfg.regime.atr_pctile_window)
        self._entry_bars: deque[Bar] = deque(maxlen=8)
        self._prev_close: Optional[float] = None
        self.skip_log: list[dict] = []          # why entries were vetoed (journal)
        self.halted: bool = False               # equity-floor hard stop latched

    # ------------------------------------------------------------- main hook
    def on_bar_close(self, time: pd.Timestamp, o: float, h: float, l: float,
                     c: float, spread: float, fills: list[TradeRecord]) -> None:
        """Called once per CLOSED entry-TF bar, AFTER the broker has processed
        this bar's fills (which the runner passes in for kill-switch updates)."""
        # 1) roll up higher-TF state that closed at/with this bar
        self.setup.begin_bar()
        self.directional.begin_bar()
        for closed in self._agg_dir.add(time, o, h, l, c):
            self.directional.process(closed)
        for closed in self._agg_setup.add(time, o, h, l, c):
            self.setup.process(closed)

        # 2) entry-TF state
        tr = (h - l) if self._prev_close is None else (
            max(h, self._prev_close) - min(l, self._prev_close))
        atr_entry = self.entry_atr.update(h, l, c)
        rsi_val = self.entry_rsi.update(c)
        pct = self.entry_pctile.update(atr_entry)
        self._entry_bars.append(Bar(o, h, l, c))
        self._prev_close = c

        # 3) kill-switch bookkeeping
        for f in fills:
            self.ks.on_trade_closed(f)
        self.ks.on_bar(time, self.broker.mark_to_market_equity(c),
                       self.broker.equity(), spread, tr, atr_entry)
        if self.ks.hard_stopped and not self.halted:
            self.halted = True
            for pos in self.broker.open_positions():
                self.broker.request_close(pos.pos_id, None, "kill_switch")
        if self.halted:
            return

        # 4) trade management (exits before entries)
        self._manage_positions(time, c)

        # 5) new entries
        self._maybe_enter(time, c, pct, rsi_val)

    # ------------------------------------------------------- trade management
    def _manage_positions(self, time: pd.Timestamp, close: float) -> None:
        positions = self.broker.open_positions()
        if not positions:
            return

        # flat-by-Friday (Appendix D): close everything late Friday UTC
        bar_close_time = time + self.entry_delta
        if self.cfg.costs.flat_by_friday and bar_close_time.weekday() == 4 \
                and bar_close_time.hour >= 21:
            for pos in positions:
                self.broker.request_close(pos.pos_id, None, "flat_friday")
            return

        st = self.cfg.stops_targets
        # CHoCH/MSS against an open position -> close at next open (DECISIONS #20;
        # gated by use_choch_exit per Appendix J.2)
        against = {("buy", "down"), ("sell", "up")}
        counter_events = [ev for ev in self.setup.last_events
                          if ev.kind in ("CHOCH", "MSS")]
        for pos in positions:
            if st.use_choch_exit and any(
                    (pos.direction, ev.direction) in against for ev in counter_events):
                self.broker.request_close(pos.pos_id, None, "choch_exit")
                continue

            # breakeven rule (Appendix J.2) — both exit modes
            if st.be_trigger_r > 0 and not pos.meta.get("be_done"):
                rpu = abs(pos.entry_price - pos.meta.get("init_stop", pos.stop))
                fav = (close - pos.entry_price) if pos.direction == "buy" \
                    else (pos.entry_price - close)
                if rpu > 0 and fav >= st.be_trigger_r * rpu:
                    self._tighten(pos, pos.entry_price)
                    pos.meta["be_done"] = True

            # structural trailing stop (Appendix J.2) — trail_structure mode only
            if st.exit_mode == "trail_structure":
                self._trail_structure(pos, st.stop_atr_mult)

            # ongoing risk / volatility ceilings (Part I 7.3) — trim, don't exit
            state = OpenPositionState(pos.direction, pos.size, pos.stop)
            trim = ongoing_trim_size(state, close, self._vol_atr(),
                                     self.broker.equity(), self.cfg.ongoing_risk)
            if trim > 0:
                self.broker.request_close(pos.pos_id, trim, "trim")

    def _tighten(self, pos, new_stop: float) -> None:
        """Move a stop only in the risk-reducing direction (broker also enforces
        this; we guard to avoid the ValueError on a no-op/loosening call)."""
        tighter = (new_stop > pos.stop) if pos.direction == "buy" else (new_stop < pos.stop)
        if tighter:
            self.broker.modify_stop(pos.pos_id, new_stop)

    def _trail_structure(self, pos, stop_atr_mult: float) -> None:
        """Trail behind the most recent CONFIRMED setup-TF swing in favor
        (repaint-safe; causal). Buffer = stop_atr_mult * setup-TF ATR."""
        buffer = stop_atr_mult * (self.setup.atr.value or 0.0)
        if pos.direction == "buy":
            lows = self.setup.structure.swing_lows
            if lows:
                self._tighten(pos, lows[-1].price - buffer)
        else:
            highs = self.setup.structure.swing_highs
            if highs:
                self._tighten(pos, highs[-1].price + buffer)

    def _vol_atr(self) -> float:
        """ATR used for volatility sizing / ceilings: directional-TF ATR
        (DECISIONS #25 — the closest causal stand-in for 'daily ATR')."""
        return self.directional.atr.value or 0.0

    # --------------------------------------------------------------- entries
    def _maybe_enter(self, time: pd.Timestamp, close: float,
                     atr_pctile: Optional[float], rsi_val: Optional[float]) -> None:
        lay = self.cfg.layers
        bar_close_time = time + self.entry_delta

        ok, why = self.ks.allow_new_entries()
        if not ok:
            return self._skip(time, why)
        sess = session_of(bar_close_time, self.cfg.sessions)
        allowed = set(self.cfg.sessions.allowed_sessions)
        sess_ok = sess in allowed or (
            sess == "overlap" and ({"london", "newyork"} & allowed))
        if not sess_ok:
            return self._skip(time, f"session:{sess}")
        blackout = self.calendar.in_blackout(bar_close_time, self.cfg.news.news_blackout_min,
                                             self.cfg.news.min_impact) or \
            self.calendar.in_blackout(bar_close_time + self.entry_delta,
                                      self.cfg.news.news_blackout_min, self.cfg.news.min_impact)
        if blackout:
            return self._skip(time, "news_blackout")
        if atr_pctile is not None and not (
                self.cfg.regime.atr_pctile_min <= atr_pctile <= self.cfg.regime.atr_pctile_max):
            return self._skip(time, "regime:atr_pctile")

        if lay.use_qm:
            self._enter_qm(time, close, sess, rsi_val, atr_pctile)
        else:
            self._enter_structure_only(time, close, sess)   # ablation baseline (B.8)

    def _bias_allows(self, direction: str) -> bool:
        lay = self.cfg.layers
        if not (lay.use_structure_bias and lay.require_htf_bias_alignment):
            return True
        bias = self.directional.structure.bias
        aligned = (bias == "bullish" and direction == "buy") or \
                  (bias == "bearish" and direction == "sell")
        if aligned:
            return True
        if lay.allow_countertrend_on_mss:
            # Part I 2.3.2 / DECISIONS #13: setup-TF MSS in the trade direction,
            # still reflected in the current setup bias
            setup_bias = self.setup.structure.bias
            return (self.setup.last_mss_direction == direction
                    and ((setup_bias == "bullish" and direction == "buy")
                         or (setup_bias == "bearish" and direction == "sell")))
        return False

    def _enter_qm(self, time: pd.Timestamp, close: float, sess: str,
                  rsi_val: Optional[float], atr_pctile: Optional[float]) -> None:
        cur = self._entry_bars[-1]
        setup_idx = self.setup.bar_count - 1
        candidates = self.setup.qm.active_patterns(setup_idx)
        for pat in reversed(candidates):                      # most recent first
            if not self._bias_allows(pat.direction):
                continue
            if self.cfg.layers.use_fib_zone:
                armed = pat.is_armed(cur.high, cur.low, cur.close)
            else:                                              # ablation: QML band only
                armed = pat.status == "fresh" and pat.bar_touches_band(cur.high, cur.low)
            if not armed:
                continue
            trigger = "none"
            if self.cfg.layers.use_price_action:
                trigger = any_trigger(list(self._entry_bars), pat.direction,
                                      self.cfg.price_action.pin_wick_ratio,
                                      enabled=self.cfg.price_action.triggers)
                if trigger is None:
                    continue
            self._submit(time, close, pat, trigger, sess, rsi_val, atr_pctile)
            pat.status = "stale"                               # the retest is being traded
            return                                             # one entry per bar

    def _enter_structure_only(self, time: pd.Timestamp, close: float, sess: str) -> None:
        """Ablation baseline: trade setup-TF MSS flips (no QM/zone/trigger)."""
        for ev in self.setup.last_events:
            if ev.kind != "MSS":
                continue
            direction = "buy" if ev.direction == "up" else "sell"
            if not self._bias_allows(direction):
                continue
            atr_setup = self.setup.atr.value or 0.0
            stop, target = build_stop_and_target(
                direction, close, ev.level, atr_setup,
                self.cfg.stops_targets.stop_atr_mult, self.cfg.stops_targets.min_rr,
                self.cfg.stops_targets.exit_mode)
            self._submit_order(time, close, direction, stop, target,
                               meta={"setup": "mss_structure_only", "session": sess})
            return

    def _submit(self, time: pd.Timestamp, close: float, pat: QMPattern,
                trigger: Optional[str], sess: str, rsi_val: Optional[float],
                atr_pctile: Optional[float]) -> None:
        atr_setup = self.setup.atr.value or 0.0
        stop, target = build_stop_and_target(
            pat.direction, close, pat.stop_extreme, atr_setup,
            self.cfg.stops_targets.stop_atr_mult, self.cfg.stops_targets.min_rr,
            self.cfg.stops_targets.exit_mode)
        bars = list(self._entry_bars)
        meta = {
            "setup": "qm",
            "qml": pat.qml,
            "qm_direction": pat.direction,
            "qm_points": {"ls": pat.ls.index, "neck": pat.neck.index,
                          "head": pat.head.index, "under": pat.under.index},
            "zone": (pat.zone_lo, pat.zone_hi),
            "fib_confluence": pat.fib_confluence,
            "has_departure_fvg": pat.has_departure_fvg,
            "departure_fvg_size": pat.departure_fvg_size,
            "trigger": trigger,
            "sfp": (self.cfg.layers.use_sfp_booster
                    and sfp(bars[-1], pat.qml, pat.direction,
                            self.cfg.price_action.sfp_wick_ratio)),
            "cplq": cplq(bars, pat.band_lo, pat.band_hi,
                         self.cfg.price_action.compression_bars,
                         self.cfg.price_action.compression_shrink),
            "session": sess,
            "bias_directional": self.directional.structure.bias,
            "bias_setup": self.setup.structure.bias,
            "rsi_entry_tf": rsi_val,
            "atr_pctile_entry": atr_pctile,
            "atr_setup_tf": atr_setup,
            "tf_bias": self.cfg.timeframes.directional,
            "tf_setup": self.cfg.timeframes.setup,
            "tf_entry": self.cfg.timeframes.entry,
        }
        self._submit_order(time, close, pat.direction, stop, target, meta)

    def _submit_order(self, time, close, direction, stop, target, meta) -> None:
        equity = self.broker.equity()
        positions = self.broker.open_positions()
        states = [OpenPositionState(p.direction, p.size, p.stop) for p in positions]
        budget = remaining_risk_budget_fraction(states, [close] * len(states),
                                                equity, self.cfg.ongoing_risk)
        sizing = compute_size(equity, close, stop, self._vol_atr(),
                              self.cfg.sizing, risk_budget_frac=budget)
        if sizing.binding == "skipped":
            return self._skip(time, "sizing_skipped")
        meta = dict(meta)
        meta["signal_close"] = close
        meta["init_stop"] = stop          # frozen initial stop for R math (Appendix J.2)
        meta["binding_method"] = sizing.binding
        meta["sizing"] = {"risk": sizing.size_risk, "vol": sizing.size_vol,
                          "margin": sizing.size_margin}
        self.broker.submit_market(direction, sizing.size, stop, target,
                                  sizing.risk_amount, meta)

    def _skip(self, time: pd.Timestamp, reason: Optional[str]) -> None:
        if reason:
            self.skip_log.append({"time": time, "reason": reason})
