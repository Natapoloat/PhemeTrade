"""Broker abstraction + core order/position/trade types.

`BrokerAdapter` is the seam between the strategy engine and any venue:
the simulator implements it for backtest/paper; a real broker adapter can be
plugged in later WITHOUT touching signal code (the engine only ever talks to
this interface).
"""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any, Literal, Optional

import pandas as pd

Direction = Literal["buy", "sell"]
ExitReason = Literal["stop", "target", "choch_exit", "trim", "flat_friday",
                     "kill_switch", "end_of_data", "manual"]


@dataclass
class Position:
    pos_id: int
    direction: Direction
    size: float
    entry_price: float
    stop: float
    target: float
    entry_time: pd.Timestamp
    risk_amount: float                     # 1R in currency at entry, for R-multiples
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TradeRecord:
    """One (possibly partial) exit of a position."""
    pos_id: int
    direction: Direction
    size: float
    entry_price: float
    exit_price: float
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    stop_at_exit: float
    gross_pnl: float
    costs: float                            # commission + swap attributed to this exit
    net_pnl: float
    r_multiple: float                       # net pnl / (1R for the exited size)
    exit_reason: ExitReason
    meta: dict[str, Any]


class BrokerAdapter(abc.ABC):
    """Minimal venue interface used by the engine (signal code)."""

    @abc.abstractmethod
    def submit_market(self, direction: Direction, size: float, stop: float,
                      target: float, risk_amount: float, meta: dict[str, Any]) -> None:
        """Queue a market order; fills on the NEXT bar open (B.1)."""

    @abc.abstractmethod
    def request_close(self, pos_id: int, size: Optional[float], reason: ExitReason) -> None:
        """Queue a (partial) close; fills on the NEXT bar open."""

    @abc.abstractmethod
    def modify_stop(self, pos_id: int, new_stop: float) -> None:
        """Tighten a stop (never loosen — enforced by implementations, Part I 8.3)."""

    @abc.abstractmethod
    def open_positions(self) -> list[Position]:
        ...

    @abc.abstractmethod
    def equity(self) -> float:
        """Closed-trade equity (cash + realized PnL) — the sizing base
        (DECISIONS #19)."""

    @abc.abstractmethod
    def mark_to_market_equity(self, price: float) -> float:
        """Equity including unrealized PnL — the kill-switch/drawdown view."""

    @abc.abstractmethod
    def process_bar(self, time: pd.Timestamp, open_: float, high: float, low: float,
                    close: float, spread: float, in_news: bool) -> list["TradeRecord"]:
        """Per-bar sync point called by the engine BEFORE strategy decisions:
        the simulator fills queued orders / checks stops here; a REAL adapter
        implements it by polling the venue for fills since the last bar and
        returning them as TradeRecords. Implementations must also maintain
        `.trades: list[TradeRecord]` and `.slippage_log: list[dict]`."""


