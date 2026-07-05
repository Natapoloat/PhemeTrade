"""Simulated broker — realistic fills per Appendix D / B.5.

Price convention: OHLC bars are MID prices; bid = mid - spread/2, ask = mid + spread/2.

Fill model (long side; shorts mirror):
- Market entry: fills at NEXT bar open (B.1): ask = open + spread/2, plus
  slippage = base (+ news extra inside a blackout window).
- Stop (sell stop at S): triggers when bar's bid low reaches S
  (low - spread/2 <= S). Fill = S - stop_slippage, where stop_slippage =
  base + stop_extra (+ news extra). If the bar OPENS through the stop (gap),
  fill at the worse open bid minus stop_slippage.
- Target (sell limit at T): triggers when bid high reaches T
  (high - spread/2 >= T). Fills AT T (limit semantics, no slippage) —
  conservative trigger, exact price.
- Worst-case intrabar sequencing (DECISIONS #8): if both stop and target lie
  within one bar, the STOP fills. Always.
- Commission charged per unit per side; swap charged on UTC-day rollover
  (3x on the configured weekday); both attributed to trade records pro rata.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import pandas as pd

from gold_qm_system.config import CostConfig
from .broker import (
    BrokerAdapter,
    Direction,
    ExitReason,
    Position,
    TradeRecord,
)


@dataclass
class _PendingEntry:
    direction: Direction
    size: float
    stop: float
    target: float
    risk_amount: float
    meta: dict[str, Any]


@dataclass
class _PendingClose:
    pos_id: int
    size: Optional[float]        # None = full
    reason: ExitReason


@dataclass
class _CostLedger:
    total: float = 0.0           # commissions + swaps accrued on the position


class SimBroker(BrokerAdapter):
    def __init__(self, initial_equity: float, costs: CostConfig):
        self.costs = costs
        self._cash = initial_equity
        self._positions: dict[int, Position] = {}
        self._ledgers: dict[int, _CostLedger] = {}
        self._pending_entries: list[_PendingEntry] = []
        self._pending_closes: list[_PendingClose] = []
        self.trades: list[TradeRecord] = []
        self.slippage_log: list[dict[str, Any]] = []
        self._last_bar_time: Optional[pd.Timestamp] = None
        self._next_pos_id = 1

    # ------------------------------------------------ BrokerAdapter interface
    def submit_market(self, direction, size, stop, target, risk_amount, meta):
        self._pending_entries.append(_PendingEntry(direction, size, stop, target,
                                                   risk_amount, dict(meta)))

    def request_close(self, pos_id, size, reason):
        self._pending_closes.append(_PendingClose(pos_id, size, reason))

    def modify_stop(self, pos_id, new_stop):
        pos = self._positions[pos_id]
        loosening = (new_stop < pos.stop) if pos.direction == "buy" else (new_stop > pos.stop)
        if loosening:
            raise ValueError("stops may only be tightened (Part I 8.3)")
        pos.stop = new_stop

    def open_positions(self):
        return list(self._positions.values())

    def equity(self):
        return self._cash

    def mark_to_market_equity(self, price):
        unreal = 0.0
        for p in self._positions.values():
            sign = 1.0 if p.direction == "buy" else -1.0
            unreal += sign * (price - p.entry_price) * p.size
        return self._cash + unreal

    # ----------------------------------------------------------- bar handling
    def process_bar(self, time: pd.Timestamp, open_: float, high: float, low: float,
                    close: float, spread: float, in_news: bool) -> list[TradeRecord]:
        """Advance the sim by one bar. Order of operations:
        swap rollover -> pending entries at open -> pending closes at open ->
        intrabar stop/target (worst-case). Returns exits filled this bar."""
        fills: list[TradeRecord] = []
        self._apply_swap(time)
        half = spread / 2.0
        entry_slip = self.costs.base_slippage + (self.costs.news_slippage_extra if in_news else 0.0)
        stop_slip = entry_slip + self.costs.stop_slippage_extra

        # 1) pending market entries fill at this bar's open
        for pe in self._pending_entries:
            px = open_ + half + entry_slip if pe.direction == "buy" else open_ - half - entry_slip
            pos = Position(self._next_pos_id, pe.direction, pe.size, px, pe.stop,
                           pe.target, time, pe.risk_amount, pe.meta)
            self._next_pos_id += 1
            self._positions[pos.pos_id] = pos
            led = _CostLedger()
            self._charge(led, self.costs.commission_per_unit * pe.size)
            self._ledgers[pos.pos_id] = led
            self.slippage_log.append({"time": time, "kind": "entry",
                                      "modeled_slippage": entry_slip + half, "size": pe.size})
        self._pending_entries.clear()

        # 2) pending (partial) closes fill at this bar's open
        for pc in self._pending_closes:
            pos = self._positions.get(pc.pos_id)
            if pos is None:
                continue
            qty = pos.size if pc.size is None else min(pc.size, pos.size)
            px = open_ - half - entry_slip if pos.direction == "buy" else open_ + half + entry_slip
            fills.append(self._settle_exit(pos, qty, px, time, pc.reason,
                                           extra_slip=entry_slip + half))
        self._pending_closes.clear()

        # 3) intrabar stop/target — worst case: stop checked FIRST, always
        for pos in list(self._positions.values()):
            fill = self._check_stop_target(pos, time, open_, high, low, half, stop_slip)
            if fill is not None:
                fills.append(fill)
        return fills

    # -------------------------------------------------------------- internals
    def _charge(self, ledger: _CostLedger, amount: float) -> None:
        ledger.total += amount
        self._cash -= amount

    def _apply_swap(self, time: pd.Timestamp) -> None:
        if self._last_bar_time is not None and time.date() != self._last_bar_time.date():
            mult = 3.0 if time.weekday() == self.costs.swap_triple_weekday else 1.0
            days = max(1, (time.date() - self._last_bar_time.date()).days)
            for pos in self._positions.values():
                per_day = (self.costs.swap_long_per_unit_day if pos.direction == "buy"
                           else self.costs.swap_short_per_unit_day)
                # negative swap value = cost; ledger stores costs as positive
                self._charge(self._ledgers[pos.pos_id], -per_day * pos.size * mult * days)
        self._last_bar_time = time

    def _check_stop_target(self, pos: Position, time, open_, high, low,
                           half: float, stop_slip: float) -> Optional[TradeRecord]:
        if pos.direction == "buy":
            bid_open, bid_low, bid_high = open_ - half, low - half, high - half
            if bid_open <= pos.stop:                       # gap through stop
                return self._settle_exit(pos, pos.size, bid_open - stop_slip, time,
                                         "stop", extra_slip=stop_slip + half)
            if bid_low <= pos.stop:                        # stop first, always
                return self._settle_exit(pos, pos.size, pos.stop - stop_slip, time,
                                         "stop", extra_slip=stop_slip + half)
            if bid_high >= pos.target:
                return self._settle_exit(pos, pos.size, pos.target, time,
                                         "target", extra_slip=0.0)
        else:
            ask_open, ask_high, ask_low = open_ + half, high + half, low + half
            if ask_open >= pos.stop:
                return self._settle_exit(pos, pos.size, ask_open + stop_slip, time,
                                         "stop", extra_slip=stop_slip + half)
            if ask_high >= pos.stop:
                return self._settle_exit(pos, pos.size, pos.stop + stop_slip, time,
                                         "stop", extra_slip=stop_slip + half)
            if ask_low <= pos.target:
                return self._settle_exit(pos, pos.size, pos.target, time,
                                         "target", extra_slip=0.0)
        return None

    def _settle_exit(self, pos: Position, qty: float, px: float, time,
                     reason: ExitReason, extra_slip: float) -> TradeRecord:
        ledger = self._ledgers[pos.pos_id]
        exit_commission = self.costs.commission_per_unit * qty
        self._charge(ledger, exit_commission)

        frac = qty / pos.size if pos.size > 0 else 1.0
        attributed_costs = ledger.total * frac
        ledger.total -= attributed_costs

        sign = 1.0 if pos.direction == "buy" else -1.0
        gross = sign * (px - pos.entry_price) * qty
        self._cash += gross
        net = gross - attributed_costs
        one_r_for_qty = pos.risk_amount * frac
        r_mult = net / one_r_for_qty if one_r_for_qty > 0 else 0.0

        rec = TradeRecord(pos.pos_id, pos.direction, qty, pos.entry_price, px,
                          pos.entry_time, time, pos.stop, gross, attributed_costs,
                          net, r_mult, reason, dict(pos.meta))
        self.trades.append(rec)
        if extra_slip > 0:
            self.slippage_log.append({"time": time, "kind": reason,
                                      "modeled_slippage": extra_slip, "size": qty})

        pos.size -= qty
        pos.risk_amount -= one_r_for_qty
        if pos.size <= 1e-12:
            del self._positions[pos.pos_id]
            del self._ledgers[pos.pos_id]
        return rec
