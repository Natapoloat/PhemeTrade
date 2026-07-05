"""Causal indicators: ATR (EMA form), RSI, ATR percentile.

All functions are pure and causal: value at row t uses rows <= t only.
Prefix-consistency (indicator(data[:t]) == indicator(data)[:t]) is enforced
by tests — that property is what makes precomputing them lookahead-safe.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def true_range(df: pd.DataFrame) -> pd.Series:
    """TR = max(prev_close, high) - min(prev_close, low). First bar: high-low."""
    prev_close = df["close"].shift(1)
    hi = pd.concat([df["high"], prev_close], axis=1).max(axis=1)
    lo = pd.concat([df["low"], prev_close], axis=1).min(axis=1)
    tr = hi - lo
    tr.iloc[0] = df["high"].iloc[0] - df["low"].iloc[0]
    return tr.rename("tr")


def atr(df: pd.DataFrame, period: int = 21) -> pd.Series:
    """EMA-form ATR (Part I 7.2): ATR_t = ATR_{t-1} + k*(TR_t - ATR_{t-1}),
    k = 2/(period+1). See DECISIONS.md #21 on the spec's literal formula."""
    k = 2.0 / (period + 1)
    return true_range(df).ewm(alpha=k, adjust=False).mean().rename("atr")


def rsi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Wilder's RSI (causal; smoothing alpha = 1/period)."""
    delta = df["close"].diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.ewm(alpha=1.0 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    out = 100.0 - 100.0 / (1.0 + rs)
    return out.fillna(100.0).where(delta.notna(), np.nan).rename("rsi")


def atr_percentile(atr_series: pd.Series, window: int = 200) -> pd.Series:
    """Rolling percentile rank (0..1) of current ATR within the trailing window
    (window includes the current bar; strictly trailing => causal)."""

    def pct_rank(x: np.ndarray) -> float:
        return float((x[:-1] <= x[-1]).mean()) if len(x) > 1 else np.nan

    return atr_series.rolling(window, min_periods=2).apply(pct_rank, raw=True).rename("atr_pctile")
