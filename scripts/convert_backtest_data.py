"""Convert MT4-style vendor exports (Date;O;H;L;C;V, server time) to the repo
data format (<SYMBOL>_<TF>.csv, UTC open_time).

Timezone: this vendor uses the common 'New-York-close' MT4 convention —
GMT+2 during US winter, GMT+3 during US daylight saving — detected from the
weekly open/close pattern (opens Mon 01:00, closes Fri 23:45 server time,
season-invariant). We therefore subtract 2h, +1h more when US Eastern is in
DST at that instant. Residual error is confined to the few hours around each
DST transition, which fall on inactive Sunday sessions.

Usage:
  python scripts/convert_backtest_data.py BacktestData/XAU_15m_data.csv M15 \
      --out market_data_long --symbol XAUUSD
"""
from __future__ import annotations

import argparse
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

NY = ZoneInfo("America/New_York")


def server_to_utc(ts: pd.Series) -> pd.Series:
    """GMT+2/GMT+3 (NY-close convention) naive server time -> tz-aware UTC."""
    approx_utc = ts - pd.Timedelta(hours=2)
    # DST flag evaluated at the approximate instant; transition-edge error is
    # bounded to those hours (weekend, market closed)
    ny = approx_utc.dt.tz_localize("UTC").dt.tz_convert(NY)
    is_dst = ny.map(lambda t: bool(t.dst()))
    return (approx_utc - pd.to_timedelta(is_dst.astype(int), unit="h")
            ).dt.tz_localize("UTC")


def convert(src: Path, timeframe: str, out_dir: Path, symbol: str) -> Path:
    df = pd.read_csv(src, sep=";")
    df.columns = [c.strip().lower() for c in df.columns]
    df["date"] = pd.to_datetime(df["date"], format="%Y.%m.%d %H:%M")
    df = df.sort_values("date").drop_duplicates("date").reset_index(drop=True)

    out = pd.DataFrame({
        "open_time": server_to_utc(df["date"]),
        "open": df["open"], "high": df["high"],
        "low": df["low"], "close": df["close"],
    })
    if "volume" in df.columns:
        out["volume"] = df["volume"]
    out = out.sort_values("open_time").drop_duplicates("open_time")

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{symbol}_{timeframe}.csv"
    out.to_csv(path, index=False)
    print(f"wrote {len(out):,} bars ({out.open_time.iloc[0]} .. "
          f"{out.open_time.iloc[-1]}) -> {path}")
    return path


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("src", type=Path)
    ap.add_argument("timeframe", choices=["M1", "M5", "M15", "H1", "H4", "D1"])
    ap.add_argument("--out", type=Path, default=Path("market_data_long"))
    ap.add_argument("--symbol", default="XAUUSD")
    a = ap.parse_args()
    convert(a.src, a.timeframe, a.out, a.symbol)
