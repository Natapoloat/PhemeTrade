"""OHLCV data loading and normalization.

Conventions (used everywhere in this package):
- Bars are indexed by their OPEN timestamp, tz-aware UTC, ascending, unique.
- A bar of timeframe TF is CLOSED at open_time + TF period. Decisions made
  "at bar t" mean at that close time, using data through that close only.
- Required columns: open, high, low, close. Optional: volume.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from gold_qm_system.config import TIMEFRAME_MINUTES

REQUIRED_COLS = ["open", "high", "low", "close"]


def timeframe_delta(timeframe: str) -> pd.Timedelta:
    if timeframe not in TIMEFRAME_MINUTES:
        raise ValueError(f"unknown timeframe {timeframe!r}; expected one of {list(TIMEFRAME_MINUTES)}")
    return pd.Timedelta(minutes=TIMEFRAME_MINUTES[timeframe])


def normalize_ohlcv(df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    """Validate + normalize a raw OHLCV frame to package conventions."""
    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]

    # locate a timestamp column if the index isn't already datetime
    if not isinstance(df.index, pd.DatetimeIndex):
        ts_col = next((c for c in ("open_time", "timestamp", "time", "datetime", "date") if c in df.columns), None)
        if ts_col is None:
            raise ValueError("no datetime index and no timestamp/time/datetime/date column found")
        df[ts_col] = pd.to_datetime(df[ts_col], utc=True)
        df = df.set_index(ts_col)

    idx = pd.DatetimeIndex(df.index)
    idx = idx.tz_localize("UTC") if idx.tz is None else idx.tz_convert("UTC")
    df.index = idx
    df.index.name = "open_time"

    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"missing required OHLC columns: {missing}")

    keep = REQUIRED_COLS + (["volume"] if "volume" in df.columns else [])
    df = df[keep].astype(float).sort_index()
    df = df[~df.index.duplicated(keep="first")]

    bad = (df["high"] < df[["open", "close", "low"]].max(axis=1)) | (
        df["low"] > df[["open", "close", "high"]].min(axis=1)
    )
    if bad.any():
        raise ValueError(f"{int(bad.sum())} bars violate high>=max(o,c,l) / low<=min(o,c,h)")

    df.attrs["timeframe"] = timeframe
    return df


def load_ohlcv(path: str | Path, timeframe: str) -> pd.DataFrame:
    """Load one timeframe's OHLCV bars from CSV or Parquet."""
    path = Path(path)
    if path.suffix.lower() == ".parquet":
        raw = pd.read_parquet(path)
    elif path.suffix.lower() in (".csv", ".txt"):
        raw = pd.read_csv(path)
    else:
        raise ValueError(f"unsupported file type: {path.suffix}")
    return normalize_ohlcv(raw, timeframe)


def load_data_dir(data_dir: str | Path, symbol: str, timeframes: list[str]) -> dict[str, pd.DataFrame]:
    """Load `<data_dir>/<symbol>_<TF>.(csv|parquet)` for each requested TF.

    A missing timeframe file raises unless it can be resampled from a finer
    one that IS present (see resample_ohlcv).
    """
    data_dir = Path(data_dir)
    out: dict[str, pd.DataFrame] = {}
    for tf in timeframes:
        found = None
        for ext in (".parquet", ".csv"):
            cand = data_dir / f"{symbol}_{tf}{ext}"
            if cand.exists():
                found = cand
                break
        if found is not None:
            out[tf] = load_ohlcv(found, tf)

    # resample any missing TF from the finest available finer TF
    for tf in timeframes:
        if tf in out:
            continue
        finer = [
            (t, f) for t, f in out.items() if TIMEFRAME_MINUTES[t] < TIMEFRAME_MINUTES[tf]
        ]
        if not finer:
            raise FileNotFoundError(
                f"no data file for {symbol}_{tf} in {data_dir} and no finer timeframe to resample from"
            )
        src_tf, src = min(finer, key=lambda p: TIMEFRAME_MINUTES[p[0]])
        out[tf] = resample_ohlcv(src, tf)
    return out


def resample_ohlcv(df: pd.DataFrame, target_tf: str) -> pd.DataFrame:
    """Resample finer bars to a coarser timeframe.

    Labels are the OPEN time of the coarser bar (label='left'), so the
    close-time convention (open + period) holds for the result. Only fully
    formed buckets are meaningful for backtesting; the last (possibly partial)
    bucket is kept — the no-lookahead aligner makes it invisible until its
    close time has passed, so it can never leak.
    """
    src_tf = df.attrs.get("timeframe")
    if src_tf is not None and TIMEFRAME_MINUTES[src_tf] >= TIMEFRAME_MINUTES[target_tf]:
        raise ValueError(f"cannot resample {src_tf} -> {target_tf} (not coarser)")
    rule = timeframe_delta(target_tf)
    agg = {"open": "first", "high": "max", "low": "min", "close": "last"}
    if "volume" in df.columns:
        agg["volume"] = "sum"
    out = df.resample(rule, label="left", closed="left").agg(agg).dropna(subset=["open"])
    out.attrs["timeframe"] = target_tf
    out.index.name = "open_time"
    return out
