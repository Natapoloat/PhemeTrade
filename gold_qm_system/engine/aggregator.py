"""Incremental bar aggregation: entry-TF bars in, CLOSED higher-TF bars out.

Because the strategy only ever consumes entry-TF bars and builds its own HTF
bars, an unclosed HTF candle can never leak into a decision by construction —
the aggregator emits a bucket only once its close time has been reached (or a
bar from a later bucket arrives, i.e. after a data gap).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import NamedTuple, Optional

import pandas as pd

from gold_qm_system.data import timeframe_delta


class ClosedBar(NamedTuple):
    time: pd.Timestamp    # bucket OPEN time
    open: float
    high: float
    low: float
    close: float


@dataclass
class _Bucket:
    open_time: pd.Timestamp
    open: float
    high: float
    low: float
    close: float


class BarAggregator:
    def __init__(self, source_tf: str, target_tf: str):
        self.src_delta = timeframe_delta(source_tf)
        self.tgt_delta = timeframe_delta(target_tf)
        if self.tgt_delta < self.src_delta:
            raise ValueError(f"target {target_tf} finer than source {source_tf}")
        self.passthrough = self.tgt_delta == self.src_delta
        self._freq = f"{int(self.tgt_delta.total_seconds() // 60)}min"
        self._bucket: Optional[_Bucket] = None

    def add(self, time: pd.Timestamp, o: float, h: float, l: float, c: float) -> list[ClosedBar]:
        """Feed one CLOSED source bar (open time = `time`); return any target
        bars that are now closed."""
        if self.passthrough:
            return [ClosedBar(time, o, h, l, c)]

        emitted: list[ClosedBar] = []
        bucket_open = time.floor(self._freq)

        if self._bucket is not None and self._bucket.open_time != bucket_open:
            # a bar from a LATER bucket arrived (data gap): flush the old bucket
            emitted.append(self._emit())

        if self._bucket is None:
            self._bucket = _Bucket(bucket_open, o, h, l, c)
        else:
            b = self._bucket
            b.high = max(b.high, h)
            b.low = min(b.low, l)
            b.close = c

        # bucket complete once the source bar's close reaches the bucket close
        if time + self.src_delta >= self._bucket.open_time + self.tgt_delta:
            emitted.append(self._emit())
        return emitted

    def _emit(self) -> ClosedBar:
        b = self._bucket
        self._bucket = None
        return ClosedBar(b.open_time, b.open, b.high, b.low, b.close)
