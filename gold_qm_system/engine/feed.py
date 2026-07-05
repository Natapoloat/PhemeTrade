"""Bar feeds for the forward-test/live runner.

A feed yields CLOSED entry-TF bars as (open_time_utc, open, high, low, close).
Real-time feeds are user-supplied (implement BarFeed against your broker's
streaming API); CSVReplayFeed replays a file in real or accelerated time so
the forwardtest wiring can be exercised end-to-end without a live connection.
"""
from __future__ import annotations

import abc
import time as _time
from pathlib import Path
from typing import Iterator

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
