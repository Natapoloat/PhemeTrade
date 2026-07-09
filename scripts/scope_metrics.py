"""Paper-scoping metrics for the next-strategy brief (G1/G4/G6 inputs).

For each symbol: fetch M15 (terminal-capped) + H1 (deep) history, report bar
counts / span (G6), median ATR(21) per TF as the move-size scale, and the
round-trip cost implied by the existing per-symbol cost calibration, expressed
BOTH in price and as a fraction of ATR (the G4 ratio: edge must be >= 3x cost).

No strategy code is run — this is the before-implementation number sheet.

Usage:  python scripts/scope_metrics.py [--symbols ...] [--out output/scope_metrics.csv]
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

import MetaTrader5 as mt5
import numpy as np
import pandas as pd

TERMINAL = r"C:\Program Files\MetaTrader 5 EXNESS\terminal64.exe"
DEFAULT = ["XAUUSDm", "XAGUSDm", "EURUSDm", "GBPUSDm", "USDJPYm", "AUDUSDm",
           "USDCADm", "NZDUSDm", "USDCHFm", "EURJPYm", "GBPJPYm", "EURGBPm",
           "BTCUSDm", "US30m", "USTECm", "USOILm"]


def fetch(symbol: str, tf, years: float, step_days: int) -> pd.DataFrame | None:
    mt5.symbol_select(symbol, True)
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=365.25 * years)
    frames, cur = [], start
    while cur < end:
        hi = min(cur + timedelta(days=step_days), end)
        r = mt5.copy_rates_range(symbol, tf, cur, hi)
        if r is not None and len(r):
            frames.append(pd.DataFrame(r))
        cur = hi
    if not frames:
        return None
    raw = pd.concat(frames).drop_duplicates("time").sort_values("time")
    return raw


def atr(df: pd.DataFrame, n: int = 21) -> pd.Series:
    h, l, c = df["high"], df["low"], df["close"]
    pc = c.shift(1)
    tr = pd.concat([(h - l), (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / n, adjust=False).mean()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default="")
    ap.add_argument("--out", default="output/scope_metrics.csv")
    args = ap.parse_args()
    syms = [s.strip() for s in args.symbols.split(",") if s.strip()] or DEFAULT

    if not mt5.initialize(path=TERMINAL):
        raise SystemExit(f"MT5 init failed: {mt5.last_error()}")

    rows = []
    for s in syms:
        info = mt5.symbol_info(s)
        if info is None:
            print(f"  {s:<9} SKIP (not offered)", flush=True)
            continue
        point = info.point
        spread_px = max(info.spread, 1) * point
        # cost model as in portfolio_backtest.symbol_config:
        #   entry: spread + 0.5*spread slippage ; target exit: same ; stop exit: +1.0*spread
        rt_target = (spread_px + 0.5 * spread_px) * 2          # entry + non-stop exit
        rt_stop = (spread_px + 0.5 * spread_px) + (spread_px + 1.5 * spread_px)  # entry + stop exit
        rt_cost = 0.5 * (rt_target + rt_stop)                  # blended round trip (price)

        m15 = fetch(s, mt5.TIMEFRAME_M15, 15, 45)
        h1 = fetch(s, mt5.TIMEFRAME_H1, 15, 400)
        rec = {"symbol": s, "spread_px": round(spread_px, 6), "rt_cost_px": round(rt_cost, 6)}
        for tag, df in [("m15", m15), ("h1", h1)]:
            if df is None or len(df) < 500:
                rec[f"{tag}_bars"] = 0
                continue
            t0 = datetime.fromtimestamp(int(df["time"].iloc[0]), tz=timezone.utc)
            t1 = datetime.fromtimestamp(int(df["time"].iloc[-1]), tz=timezone.utc)
            yrs = (t1 - t0).days / 365.25
            med_atr = float(atr(df).dropna().median())
            rec[f"{tag}_bars"] = len(df)
            rec[f"{tag}_yrs"] = round(yrs, 1)
            rec[f"{tag}_from"] = t0.date().isoformat()
            rec[f"{tag}_med_atr"] = round(med_atr, 6)
            rec[f"{tag}_cost_per_atr"] = round(rt_cost / med_atr, 3) if med_atr else None
        rows.append(rec)
        print(f"  {s:<9} spread={rec['spread_px']:<10} rt_cost={rec['rt_cost_px']:<10} "
              f"M15:{rec.get('m15_yrs','-')}y cost/ATR={rec.get('m15_cost_per_atr','-')}  "
              f"H1:{rec.get('h1_yrs','-')}y cost/ATR={rec.get('h1_cost_per_atr','-')}", flush=True)
    mt5.shutdown()

    df = pd.DataFrame(rows)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out, index=False)
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
