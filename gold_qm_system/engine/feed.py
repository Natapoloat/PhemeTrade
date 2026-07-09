"""Bar feeds for the forward-test/live runner.

A feed yields CLOSED entry-TF bars as (open_time_utc, open, high, low, close).
Real-time feeds are user-supplied (implement BarFeed against your broker's
streaming API); CSVReplayFeed replays a file in real or accelerated time so
the forwardtest wiring can be exercised end-to-end without a live connection.
MT5LiveFeed streams CLOSED bars from a running MetaTrader 5 terminal (read-only
market data — orders still go to whatever broker run_feed is given, e.g. the
paper SimBroker).
"""
from __future__ import annotations

import abc
import time as _time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator, Optional

import pandas as pd

from gold_qm_system.data import load_ohlcv


class BarFeed(abc.ABC):
    @abc.abstractmethod
    def __iter__(self) -> Iterator[tuple[pd.Timestamp, float, float, float, float]]:
        ...


class CSVReplayFeed(BarFeed):
    """Replays a historical CSV as if it were streaming. `speed=0` replays as
    fast as possible; `speed=1` sleeps the real inter-bar interval, etc."""

    def __init__(self, path: str | Path, timeframe: str, speed: float = 0.0):
        self.df = load_ohlcv(path, timeframe)
        self.speed = speed

    def __iter__(self):
        prev = None
        for t, row in zip(self.df.index,
                          self.df[["open", "high", "low", "close"]].itertuples(index=False)):
            if self.speed > 0 and prev is not None:
                _time.sleep((t - prev).total_seconds() / self.speed)
            prev = t
            yield t, row.open, row.high, row.low, row.close


_MT5_TF = {"M1": "TIMEFRAME_M1", "M5": "TIMEFRAME_M5", "M15": "TIMEFRAME_M15",
           "H1": "TIMEFRAME_H1", "H4": "TIMEFRAME_H4", "D1": "TIMEFRAME_D1"}
_TF_MINUTES = {"M1": 1, "M5": 5, "M15": 15, "H1": 60, "H4": 240, "D1": 1440}


class MT5LiveFeed(BarFeed):
    """Stream CLOSED entry-TF bars from a running/headless MetaTrader 5 terminal.

    Read-only: it only pulls market data. It first replays the most recent
    `warmup_bars` CLOSED bars so the strategy's swing/structure/QM/ATR state is
    warm (these are NOT the forward test — `warmup_end_time` marks the boundary),
    then polls for each newly-CLOSED bar and yields it as it appears. The still-
    forming current bar is never yielded. Bar times are converted SERVER->UTC via
    an auto-detected offset (override with `server_utc_offset`).

    Set `max_live_bars` to stop after N live bars (wiring self-test); leave it
    None for an open-ended forward test (stop with Ctrl-C).
    """

    def __init__(self, symbol: str = "XAUUSD", timeframe: str = "M15",
                 warmup_bars: int = 1500, terminal: Optional[str] = None,
                 server_utc_offset: Optional[int] = None,
                 poll_seconds: Optional[float] = None,
                 max_live_bars: Optional[int] = None):
        if timeframe not in _MT5_TF:
            raise ValueError(f"unsupported timeframe {timeframe!r}")
        self.symbol_req = symbol
        self.timeframe = timeframe
        self.warmup_bars = warmup_bars
        self.terminal = terminal
        self._offset_override = server_utc_offset
        self.poll_seconds = poll_seconds if poll_seconds is not None \
            else max(2.0, _TF_MINUTES[timeframe] * 60 / 30)
        self.max_live_bars = max_live_bars
        # populated on connect / during iteration
        self._mt5 = None
        self._tf_const = None
        self.symbol: Optional[str] = None
        self.point: Optional[float] = None
        self.offset_hours: int = 0
        self.warmup_end_time: Optional[pd.Timestamp] = None
        self._stopped = False

    # --------------------------------------------------------------- connect
    def _connect(self) -> None:
        import MetaTrader5 as mt5           # lazy: keeps the module importable off-Windows
        self._mt5 = mt5
        self._tf_const = getattr(mt5, _MT5_TF[self.timeframe])
        ok = mt5.initialize(path=self.terminal) if self.terminal else mt5.initialize()
        if not ok:
            raise RuntimeError(
                f"MT5 initialize failed: {mt5.last_error()}. Open the Exness "
                "terminal, log into your demo account (tick 'Save password'), "
                "leave it running, then retry.")
        self.symbol = self._resolve_symbol(self.symbol_req)
        mt5.symbol_select(self.symbol, True)
        info = mt5.symbol_info(self.symbol)
        self.point = info.point
        self.offset_hours = (self._offset_override if self._offset_override is not None
                             else self._detect_offset())
        acct = mt5.account_info()
        mode = "DEMO" if acct and acct.trade_mode == 0 else "REAL/OTHER"
        print(f"[feed] connected server={acct.server!r} login={acct.login} "
              f"mode={mode} symbol={self.symbol} offset={self.offset_hours:+d}h "
              f"poll={self.poll_seconds:.0f}s", flush=True)
        if mode != "DEMO":
            print("[feed] WARNING: account is not DEMO — this feed only READS "
                  "data, but double-check you intended this account.", flush=True)

    def _resolve_symbol(self, want: str) -> str:
        mt5 = self._mt5
        if mt5.symbol_info(want) is not None:
            return want
        cands = [s.name for s in (mt5.symbols_get(f"{want}*") or [])]
        if not cands:
            raise RuntimeError(f"symbol {want!r} not found (no '{want}*' candidates)")
        print(f"[feed] {want!r} not found; using {cands[0]!r}", flush=True)
        return cands[0]

    def _detect_offset(self) -> int:
        tick = self._mt5.symbol_info_tick(self.symbol)
        if tick is None or tick.time == 0:
            print("[feed] no live tick (market closed?); assuming offset 0", flush=True)
            return 0
        server_now = datetime.fromtimestamp(tick.time, tz=timezone.utc)
        return round((server_now - datetime.now(timezone.utc)).total_seconds() / 3600)

    # ------------------------------------------------------------ bar pulls
    def _closed_bars(self, count: int) -> pd.DataFrame:
        """Most recent `count` CLOSED bars (drops the still-forming bar), UTC."""
        rates = self._mt5.copy_rates_from_pos(self.symbol, self._tf_const, 0, count + 1)
        if rates is None or len(rates) == 0:
            return pd.DataFrame(columns=["open_time", "open", "high", "low", "close"])
        df = pd.DataFrame(rates).iloc[:-1]          # drop forming last bar
        df["open_time"] = (pd.to_datetime(df["time"], unit="s", utc=True)
                           - pd.Timedelta(hours=self.offset_hours))
        return df[["open_time", "open", "high", "low", "close"]]

    def stop(self) -> None:
        self._stopped = True

    def __iter__(self):
        self._connect()
        warm = self._closed_bars(self.warmup_bars)
        last_time: Optional[pd.Timestamp] = None
        for row in warm.itertuples(index=False):
            last_time = row.open_time
            yield row.open_time, row.open, row.high, row.low, row.close
        self.warmup_end_time = last_time
        if self.max_live_bars == 0:                 # connectivity self-test: warm-up only
            print(f"[feed] warm-up done: {len(warm):,} bars through {last_time} UTC. "
                  f"max_live_bars=0 -> stopping (self-test).", flush=True)
            return
        print(f"[feed] warm-up done: {len(warm):,} bars through {last_time} UTC. "
              f"Forward test starts now — live bars below.", flush=True)

        live = 0
        while not self._stopped:
            recent = self._closed_bars(3)
            for row in recent.itertuples(index=False):
                if last_time is not None and row.open_time <= last_time:
                    continue
                last_time = row.open_time
                live += 1
                yield row.open_time, row.open, row.high, row.low, row.close
                if self.max_live_bars is not None and live >= self.max_live_bars:
                    print(f"[feed] reached max_live_bars={self.max_live_bars}; "
                          "stopping.", flush=True)
                    return
            _time.sleep(self.poll_seconds)
