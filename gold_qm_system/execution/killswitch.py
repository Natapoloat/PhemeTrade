"""Kill-switches / circuit breakers (Appendix G) — wired into the engine.

- daily loss limit: halt NEW entries after -daily_loss_r (R) or -daily_loss_pct
  of day-start equity (realized, trades closed this UTC day);
- consecutive-loss pause after max_consec_losses;
- spread / volatility circuit breaker on the current bar;
- equity floor: HARD stop at max_total_dd peak-to-trough (mark-to-market view).

Existing positions keep their stops/targets; breakers gate entries only —
except the hard stop, which the engine treats as flatten-and-halt.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from gold_qm_system.config import KillSwitchConfig
from .broker import TradeRecord

_LOSS_COUNTED_REASONS = {"stop", "target", "choch_exit"}  # trims don't count


@dataclass
class KillSwitchMonitor:
    cfg: KillSwitchConfig
    initial_equity: float

    _day: Optional[pd.Timestamp] = field(default=None, init=False)
    _day_start_equity: float = field(default=0.0, init=False)
    _daily_r: float = field(default=0.0, init=False)
    _daily_pnl: float = field(default=0.0, init=False)
    _consec_losses: int = field(default=0, init=False)
    _peak_equity: float = field(default=0.0, init=False)
    _last_spread: float = field(default=0.0, init=False)
    _last_tr_over_atr: float = field(default=0.0, init=False)
    hard_stopped: bool = field(default=False, init=False)
    consec_paused: bool = field(default=False, init=False)

    def __post_init__(self):
        self._peak_equity = self.initial_equity
        self._day_start_equity = self.initial_equity

    # ------------------------------------------------------------- callbacks
    def on_bar(self, time: pd.Timestamp, mtm_equity: float, realized_equity: float,
               spread: float, true_range: float, atr_value: float) -> None:
        day = time.normalize()
        if self._day is None or day != self._day:
            self._day = day
            self._daily_r = 0.0
            self._daily_pnl = 0.0
            self._day_start_equity = realized_equity
        self._last_spread = spread
        self._last_tr_over_atr = (true_range / atr_value) if atr_value > 0 else 0.0
        self._peak_equity = max(self._peak_equity, mtm_equity)
        if self._peak_equity > 0:
            dd = 1.0 - mtm_equity / self._peak_equity
            if dd >= self.cfg.max_total_dd:
                self.hard_stopped = True

    def on_trade_closed(self, trade: TradeRecord) -> None:
        self._daily_r += trade.r_multiple if trade.exit_reason in _LOSS_COUNTED_REASONS else 0.0
        self._daily_pnl += trade.net_pnl
        if trade.exit_reason in _LOSS_COUNTED_REASONS:
            if trade.net_pnl < 0:
                self._consec_losses += 1
                if self._consec_losses >= self.cfg.max_consec_losses:
                    self.consec_paused = True   # sticky: needs manual reset/review
            elif trade.net_pnl > 0:
                self._consec_losses = 0

    def reset_consecutive_pause(self) -> None:
        """Manual-review acknowledgment (Appendix G)."""
        self.consec_paused = False
        self._consec_losses = 0

    # --------------------------------------------------------------- queries
    def allow_new_entries(self) -> tuple[bool, Optional[str]]:
        if self.hard_stopped:
            return False, "equity_floor_hard_stop"
        if self.consec_paused:
            return False, "consecutive_losses_pause"
        if self._daily_r <= -self.cfg.daily_loss_r:
            return False, "daily_loss_r_limit"
        if self._day_start_equity > 0 and (
                self._daily_pnl / self._day_start_equity) <= -self.cfg.daily_loss_pct:
            return False, "daily_loss_pct_limit"
        if self._last_spread > self.cfg.spread_cap:
            return False, "spread_circuit_breaker"
        if self._last_tr_over_atr > self.cfg.vol_cap_atr_mult:
            return False, "volatility_circuit_breaker"
        return True, None
