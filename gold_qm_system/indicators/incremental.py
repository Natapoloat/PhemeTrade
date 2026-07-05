"""Incremental (streaming) forms of the causal indicators, used by the live
engine. Parity with the vectorized forms is enforced by tests."""
from __future__ import annotations

from collections import deque
from typing import Optional

import numpy as np


class IncATR:
    """EMA-form ATR, incremental. Matches indicators.core.atr exactly."""

    def __init__(self, period: int = 21):
        self.k = 2.0 / (period + 1)
        self.value: Optional[float] = None
        self._prev_close: Optional[float] = None

    def update(self, high: float, low: float, close: float) -> float:
        if self._prev_close is None:
            tr = high - low
        else:
            tr = max(high, self._prev_close) - min(low, self._prev_close)
        self.value = tr if self.value is None else self.value + self.k * (tr - self.value)
        self._prev_close = close
        return self.value


class IncRSI:
    """Wilder RSI, incremental. Matches indicators.core.rsi exactly."""

    def __init__(self, period: int = 14):
        self.alpha = 1.0 / period
        self.value: Optional[float] = None
        self._prev_close: Optional[float] = None
        self._avg_gain: Optional[float] = None
        self._avg_loss: Optional[float] = None

    def update(self, close: float) -> Optional[float]:
        if self._prev_close is None:
            self._prev_close = close
            return None
        delta = close - self._prev_close
        gain, loss = max(delta, 0.0), max(-delta, 0.0)
        if self._avg_gain is None:
            self._avg_gain, self._avg_loss = gain, loss
        else:
            self._avg_gain += self.alpha * (gain - self._avg_gain)
            self._avg_loss += self.alpha * (loss - self._avg_loss)
        self._prev_close = close
        self.value = 100.0 if self._avg_loss == 0 else 100.0 - 100.0 / (
            1.0 + self._avg_gain / self._avg_loss)
        return self.value


class IncPercentile:
    """Trailing percentile rank of the latest value within a rolling window.
    Matches indicators.core.atr_percentile ((window-1 predecessors) <= x)."""

    def __init__(self, window: int = 200, min_history: int = 20):
        self._buf: deque[float] = deque(maxlen=window)
        self.min_history = min_history

    def update(self, x: float) -> Optional[float]:
        history = np.fromiter(self._buf, dtype=float, count=len(self._buf))
        self._buf.append(x)
        if len(history) + 1 < self.min_history:
            return None                       # not enough history: filter inactive
        return float((history <= x).mean())
