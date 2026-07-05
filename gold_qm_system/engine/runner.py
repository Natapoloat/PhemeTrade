"""Runners: backtest (historical DataFrame) and forward/paper (real-time feed).

Both call the SAME `_run_core` loop with the SAME QMStrategy — the shared
code path required by Appendix C/H. The only difference is where entry-TF
bars come from.

Per-bar order of operations (B.1):
  1. broker.process_bar(bar)   -> fills for orders queued at the PREVIOUS close
                                  + intrabar stop/target checks;
  2. strategy.on_bar_close(bar, fills) -> decisions; orders fill NEXT bar.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Iterator, Optional

import pandas as pd

from gold_qm_system.calendar import NewsCalendar
from gold_qm_system.config import SystemConfig
from gold_qm_system.data import spread_at, timeframe_delta
from gold_qm_system.execution import KillSwitchMonitor, SimBroker, TradeRecord
from .strategy import QMStrategy


@dataclass
class RunResult:
    config: SystemConfig
    trades: list[TradeRecord]
    equity_curve: pd.Series               # mark-to-market, indexed by bar close time
    realized_equity_curve: pd.Series
    slippage_log: list[dict[str, Any]]
    skip_log: list[dict[str, Any]]
    halted: bool
    meta: dict[str, Any] = field(default_factory=dict)


def _make_calendar(cfg: SystemConfig) -> NewsCalendar:
    if cfg.news.calendar_csv:
        return NewsCalendar.from_csv(cfg.news.calendar_csv)
    return NewsCalendar.empty()


def _run_core(cfg: SystemConfig,
              bars: Iterable[tuple[pd.Timestamp, float, float, float, float]],
              broker: SimBroker,
              calendar: Optional[NewsCalendar] = None,
              on_event: Optional[Any] = None) -> RunResult:
    """The one and only event loop. `bars` yields CLOSED entry-TF bars as
    (open_time_utc, open, high, low, close), strictly ascending."""
    calendar = calendar if calendar is not None else _make_calendar(cfg)
    ks = KillSwitchMonitor(cfg.kill_switches, cfg.account.initial_equity)
    strategy = QMStrategy(cfg, broker, ks, calendar)
    entry_delta = timeframe_delta(cfg.timeframes.entry)

    eq_times: list[pd.Timestamp] = []
    eq_mtm: list[float] = []
    eq_real: list[float] = []
    prev_time: Optional[pd.Timestamp] = None

    for time, o, h, l, c in bars:
        if prev_time is not None and time <= prev_time:
            raise ValueError(f"bars not strictly ascending at {time}")
        prev_time = time

        in_news_open = calendar.in_blackout(time, cfg.news.news_blackout_min,
                                            cfg.news.min_impact)
        spread_open = spread_at(time, cfg.sessions, cfg.costs, in_news_open)

        fills = broker.process_bar(time, o, h, l, c, spread_open, in_news_open)
        strategy.on_bar_close(time, o, h, l, c, spread_open, fills)

        bar_close = time + entry_delta
        eq_times.append(bar_close)
        eq_mtm.append(broker.mark_to_market_equity(c))
        eq_real.append(broker.equity())
        if on_event is not None:
            on_event(time, fills, strategy)

    return RunResult(
        config=cfg,
        trades=list(broker.trades),
        equity_curve=pd.Series(eq_mtm, index=pd.DatetimeIndex(eq_times), name="equity_mtm"),
        realized_equity_curve=pd.Series(eq_real, index=pd.DatetimeIndex(eq_times),
                                        name="equity_realized"),
        slippage_log=list(broker.slippage_log),
        skip_log=list(strategy.skip_log),
        halted=strategy.halted,
    )


def run_backtest(cfg: SystemConfig, entry_bars: pd.DataFrame,
                 calendar: Optional[NewsCalendar] = None) -> RunResult:
    """Backtest over a normalized entry-TF OHLC DataFrame (see data.loaders)."""
    broker = SimBroker(cfg.account.initial_equity, cfg.costs)

    def gen() -> Iterator[tuple]:
        for t, row in zip(entry_bars.index,
                          entry_bars[["open", "high", "low", "close"]].itertuples(index=False)):
            yield t, row.open, row.high, row.low, row.close

    result = _run_core(cfg, gen(), broker, calendar)
    _settle_end_of_data(cfg, broker, entry_bars, result)
    return result


def run_feed(cfg: SystemConfig, feed: Iterable[tuple[pd.Timestamp, float, float, float, float]],
             calendar: Optional[NewsCalendar] = None,
             on_event: Optional[Any] = None,
             broker: Optional[Any] = None) -> RunResult:
    """Paper/forward-test (default SimBroker) or LIVE (inject a real
    BrokerAdapter): identical loop, bars arrive from a real-time feed.
    The feed must yield CLOSED entry-TF bars (open_time, o, h, l, c)."""
    if broker is None:
        broker = SimBroker(cfg.account.initial_equity, cfg.costs)
    return _run_core(cfg, feed, broker, calendar, on_event=on_event)


def _settle_end_of_data(cfg: SystemConfig, broker: SimBroker,
                        entry_bars: pd.DataFrame, result: RunResult) -> None:
    """Close any still-open positions at the final close price (backtest
    bookkeeping only — a forward test honestly leaves positions open)."""
    if not broker.open_positions():
        return
    for pos in list(broker.open_positions()):
        broker.request_close(pos.pos_id, None, "end_of_data")
    t = entry_bars.index[-1] + timeframe_delta(cfg.timeframes.entry)
    c = float(entry_bars["close"].iloc[-1])
    broker.process_bar(t, c, c, c, c, spread=0.0, in_news=False)
    result.trades = list(broker.trades)
    if len(result.equity_curve) > 0:
        result.equity_curve.iloc[-1] = broker.mark_to_market_equity(c)
        result.realized_equity_curve.iloc[-1] = broker.equity()
