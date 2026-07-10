"""Two in-scope levers: (1) parameterized swap-regime G8 (full / zero / fee-after-N),
and (2) the deferred H4 G8 with correct swaps — full universe.

Parameterized cost model (per symbol, per timeframe):
    swap_cost_price(H) =
        full           : swap_per_night * H
        zero           : 0                               (swap-free account)
        fee_after(N,f) : 0 for H<=N, else f * (H - N)    (grace nights then a daily fee)
    cost_price(H) = 3*spread + swap_cost_price(H)
    cost_drag_R   = cost_price(H) / (3 * median_ATR(TF))
G8 viability: cost_drag_R(actual hold) <= 0.10R  (needs gross_expR >= 0.30R at 3x).

Holds are MEASURED per timeframe by running the frozen C4 (gross, dev-only) and taking
the median hold in nights + long fraction (swap is direction-weighted by observed long%).
No new strategy code — C4 is used only to measure holds; the D1 holdout is not touched.

Usage:  python scripts/cost_regime_g8.py
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import MetaTrader5 as mt5
import numpy as np
import pandas as pd

from gold_qm_system.config import SystemConfig
from gold_qm_system.data import normalize_ohlcv
from gold_qm_system.engine import run_backtest
from gold_qm_system.engine.channel_breakout import make_c4_factory
from gold_qm_system.research_gate import development_only

TERMINAL = r"C:\Program Files\MetaTrader 5 EXNESS\terminal64.exe"
UNIVERSE = {
    "metal": ["XAUUSDm", "XAGUSDm"], "index": ["US30m", "US500m", "USTECm", "UK100m", "JP225m"],
    "energy": ["USOILm", "UKOILm"], "crypto": ["BTCUSDm", "ETHUSDm"],
    "fx": ["EURUSDm", "GBPUSDm", "USDJPYm", "AUDUSDm", "USDCADm", "NZDUSDm", "USDCHFm",
           "EURJPYm", "GBPJPYm", "EURGBPm"],
}
ROBUST = {"BTCUSDm", "ETHUSDm", "USOILm", "UKOILm", "JP225m"}
TF = {"D1": (mt5.TIMEFRAME_D1, 1500, 12), "H4": (mt5.TIMEFRAME_H4, 800, 12)}
G8_MAX = 0.10


def fetch(s, tf_const, step, yrs):
    mt5.symbol_select(s, True)
    end = datetime.now(timezone.utc); cur = end - timedelta(days=365.25 * yrs); fr = []
    while cur < end:
        hi = min(cur + timedelta(days=step), end)
        r = mt5.copy_rates_range(s, tf_const, cur, hi)
        if r is not None and len(r):
            fr.append(pd.DataFrame(r))
        cur = hi
    if not fr:
        return None
    raw = pd.concat(fr).drop_duplicates("time").sort_values("time")
    return pd.DataFrame({"open_time": pd.to_datetime(raw["time"], unit="s", utc=True),
                         "open": raw["open"], "high": raw["high"], "low": raw["low"],
                         "close": raw["close"], "volume": raw["tick_volume"]}).iloc[:-1]


def swap_cost(H, regime, swap_night, N=3, fee=None):
    if regime == "zero":
        return 0.0
    if regime == "full":
        return swap_night * H
    if regime == "fee_after":                       # grace N nights, then `fee`/night
        f = fee if fee is not None else swap_night
        return 0.0 if H <= N else f * max(0.0, H - N)
    raise ValueError(regime)


def main():
    if not mt5.initialize(path=TERMINAL):
        raise SystemExit(mt5.last_error())
    base = SystemConfig.from_yaml("forwardtest_iter3_config.yaml")
    rows = []
    for cls, syms in UNIVERSE.items():
        for s in syms:
            info = mt5.symbol_info(s)
            if info is None:
                continue
            pt = info.point
            spread_px = max(info.spread, 1) * pt
            sl = info.swap_long * pt if info.swap_mode == 1 else 0.0
            ss = info.swap_short * pt if info.swap_mode == 1 else 0.0
            for tf_label, (tfc, step, yrs) in TF.items():
                df = fetch(s, tfc, step, yrs)
                if df is None or len(df) < 500:
                    continue
                bars = development_only(normalize_ohlcv(df, tf_label))
                d = base.model_dump(); d["symbol"] = s
                d["timeframes"].update({"entry": tf_label, "setup": tf_label, "directional": tf_label})
                d["sizing"].update({"min_size": 0.0, "size_step": 0.0})
                d["news"]["calendar_csv"] = None
                res = run_backtest(SystemConfig.model_validate(d), bars,
                                   strategy_factory=make_c4_factory(55, 0.0, 1.0))
                if not res.trades:
                    continue
                holds = np.array([(t.exit_time - t.entry_time).total_seconds() / 86400 for t in res.trades])
                long_frac = np.mean([str(t.direction) == "buy" for t in res.trades])
                atr = float((pd.concat([df["high"] - df["low"],
                                        (df["high"] - df["close"].shift()).abs(),
                                        (df["low"] - df["close"].shift()).abs()], axis=1).max(axis=1)
                             ).ewm(alpha=1 / 21, adjust=False).mean().dropna().median())
                R = 3 * atr
                eff_swap = long_frac * max(0.0, -sl) + (1 - long_frac) * max(0.0, -ss)
                Hn = float(np.median(holds))
                rt = 3 * spread_px
                drag_full = (rt + swap_cost(Hn, "full", eff_swap)) / R
                drag_zero = rt / R
                rows.append({"class": cls, "symbol": s, "tf": tf_label, "n": len(res.trades),
                             "hold_nt": round(Hn, 1), "long%": round(long_frac, 2),
                             "drag_full": round(drag_full, 4), "drag_zero": round(drag_zero, 4),
                             "G8_full": "PASS" if drag_full <= G8_MAX else "FAIL",
                             "G8_zero": "PASS" if drag_zero <= G8_MAX else "FAIL",
                             # max after-3-night fee/night (price) keeping it under G8:
                             "max_fee_after3": round(max(0.0, (G8_MAX * R - rt)) / max(Hn - 3, 1e-9), 4)})
    mt5.shutdown()
    df = pd.DataFrame(rows)
    df.to_csv("output/cost_regime_g8.csv", index=False)
    for tf_label in ["D1", "H4"]:
        t = df[df.tf == tf_label]
        print(f"\n=== {tf_label} — G8 under full vs zero swap ===")
        print(t[["class", "symbol", "n", "hold_nt", "long%", "drag_full", "G8_full",
                 "drag_zero", "G8_zero"]].to_string(index=False))
    print("\n=== robust core: G8 by TF x regime ===")
    for s in ["BTCUSDm", "ETHUSDm", "USOILm", "UKOILm", "JP225m"]:
        for tf_label in ["D1", "H4"]:
            r = df[(df.symbol == s) & (df.tf == tf_label)]
            if len(r):
                r = r.iloc[0]
                print(f"  {s:<9} {tf_label}: full={r.G8_full} (drag {r.drag_full}) zero={r.G8_zero} "
                      f"hold={r.hold_nt}nt n={r.n}")
    print(f"\nG8 ceiling {G8_MAX}R. 'zero' = swap-free account; 'full' = current swaps;")
    print("max_fee_after3 = largest daily fee (price) after a 3-night grace that still passes G8.")


if __name__ == "__main__":
    main()
