"""Step 1 of the D1+ scope: swap-aware cost model + per-symbol G8 recompute.

Fixes the swap_mode bug (Exness reports mode 1 = POINTS; the old cost code applied
swaps only for mode 0 = DISABLED, i.e. it charged ZERO overnight financing in every
backtest, C4-D1 included). Here we cost a D1 trend trade honestly:

    cost_price(H) = round_trip_spread + swap_per_night * H          (H = hold nights)
    cost_drag_R(H) = cost_price(H) / R,   R = 3 * median_ATR(D1)   (C4 chandelier stop)

G8 viability: a candidate needs gross_expR >= 3 * cost_drag_R. Even an OPTIMISTIC D1
trend edge is ~0.30R gross, so a symbol is only viable if cost_drag_R(realistic H)
<= 0.10R. We report cost_drag_R at H = 5/10/20 nights (trend-realistic) and the
break-even hold (nights until cost_drag_R hits 0.10R). swap is DIRECTIONAL: for
gold/BTC/indices the penalty is on LONG (their trend bias), so we report the
penalized-direction cost (the honest case when the trend makes you hold the
carry-negative side) and the symmetric 50/50 case.

NO strategy code is built here — this is the cost gate that decides the universe (or
closes the Exness D1 lever). Objective inputs only (broker swaps + measured ATR).

Usage:  python scripts/swap_g8_scope.py
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import MetaTrader5 as mt5
import numpy as np
import pandas as pd

TERMINAL = r"C:\Program Files\MetaTrader 5 EXNESS\terminal64.exe"
CLASSES = {
    "metal":  ["XAUUSDm", "XAGUSDm"],
    "index":  ["US30m", "US500m", "USTECm", "UK100m", "JP225m"],
    "energy": ["USOILm", "UKOILm"],
    "crypto": ["BTCUSDm", "ETHUSDm"],
    "fx-major": ["EURUSDm", "GBPUSDm", "USDJPYm", "AUDUSDm", "USDCADm", "NZDUSDm", "USDCHFm"],
    "fx-cross": ["EURJPYm", "GBPJPYm", "EURGBPm"],
}
G8_MAX_DRAG = 0.10        # cost_drag_R ceiling (implies gross_expR >= 0.30R to pass 3x)
HOLDS = [5, 10, 20]


def atr_d1(symbol: str) -> float | None:
    mt5.symbol_select(symbol, True)
    end = datetime.now(timezone.utc); cur = end - timedelta(days=365.25 * 10)
    frames = []
    while cur < end:
        hi = min(cur + timedelta(days=1500), end)
        r = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_D1, cur, hi)
        if r is not None and len(r):
            frames.append(pd.DataFrame(r))
        cur = hi
    if not frames:
        return None
    df = pd.concat(frames).drop_duplicates("time").sort_values("time")
    h, l, c = df["high"], df["low"], df["close"]; pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return float(tr.ewm(alpha=1 / 21, adjust=False).mean().dropna().median())


def main() -> None:
    if not mt5.initialize(path=TERMINAL):
        raise SystemExit(f"MT5 init failed: {mt5.last_error()}")
    rows = []
    for cls, syms in CLASSES.items():
        for s in syms:
            info = mt5.symbol_info(s)
            if info is None:
                continue
            pt = info.point
            spread_px = max(info.spread, 1) * pt
            # swap_mode 1 = POINTS -> price = swap * point ; else disabled/other -> flag
            if info.swap_mode == 1:
                sl_px, ss_px = info.swap_long * pt, info.swap_short * pt
            else:
                sl_px = ss_px = float("nan")
            atr = atr_d1(s)
            if atr is None or atr <= 0:
                continue
            R = 3.0 * atr
            rt_spread = 3.0 * spread_px
            cost_long = max(0.0, -sl_px)     # paid per night to hold long
            cost_short = max(0.0, -ss_px)
            pen = max(cost_long, cost_short)          # penalized (worst) direction
            sym = 0.5 * (cost_long + cost_short)      # symmetric 50/50
            rec = {"class": cls, "symbol": s, "atr_d1": round(atr, 4),
                   "spread_R": round(rt_spread / R, 4),
                   "swap_pen/night_R": round(pen / R, 5),
                   "swap_sym/night_R": round(sym / R, 5)}
            for H in HOLDS:
                rec[f"drag_R@{H}n_pen"] = round((rt_spread + pen * H) / R, 4)
            # break-even hold: nights until penalized drag_R hits the G8 ceiling
            per = pen / R
            rec["breakeven_nights"] = round((G8_MAX_DRAG - rt_spread / R) / per, 1) if per > 0 else float("inf")
            rec["G8@10n"] = "PASS" if rec["drag_R@10n_pen"] <= G8_MAX_DRAG else "FAIL"
            rows.append(rec)
    mt5.shutdown()

    df = pd.DataFrame(rows)
    df.to_csv("output/swap_g8_scope.csv", index=False)
    cols = ["class", "symbol", "atr_d1", "spread_R", "swap_pen/night_R",
            "drag_R@5n_pen", "drag_R@10n_pen", "drag_R@20n_pen", "breakeven_nights", "G8@10n"]
    print(df[cols].to_string(index=False))
    print(f"\nG8 ceiling cost_drag_R <= {G8_MAX_DRAG} (needs gross_expR >= 0.30R at 3x).")
    print("penalized = you hold the carry-negative direction (the trend bias for metals/")
    print("crypto/indices is LONG = the penalized side). breakeven_nights = max hold before G8 fails.\n")
    print("=== survivors at 10-night hold (penalized direction) ===")
    surv = df[df["G8@10n"] == "PASS"]
    if len(surv):
        for cls in CLASSES:
            ss = surv[surv["class"] == cls]["symbol"].tolist()
            if ss:
                print(f"  {cls:<9}: {', '.join(ss)}")
    else:
        print("  NONE — swaps close the Exness D1 lever. Stop; next honest move is venue/vehicle change.")


if __name__ == "__main__":
    main()
