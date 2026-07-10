"""Crypto weekend-liquidity — pre-registered DEV test (holdout >= 2024-01-09 SEALED).

Window: Fri 21:00 UTC -> Mon 00:00 UTC (~51h). Drift-neutral excess = raw window log-return
minus the unconditional per-hour drift x 51h. Pooled BTC+ETH basket (excess averaged per
weekend to respect the 0.83 correlation). Two-sided on dev; report sign + t + pre/post-2022
consistency, and the economic net after round-trip spread + 3 nightly swaps (conservative;
no Wed triple in a Fri->Mon window). R unit = 2*ATR_D1. Kill line: economic net >= +0.05R
AND |t| >= 2 AND same excess sign pre/post-2022.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import MetaTrader5 as mt5
import numpy as np
import pandas as pd

from gold_qm_system.research_gate import log_run

TERMINAL = r"C:\Program Files\MetaTrader 5 EXNESS\terminal64.exe"
CUT = pd.Timestamp("2024-01-09", tz="UTC")
SPLIT = pd.Timestamp("2022-01-01", tz="UTC")
NIGHTS = 3
HOURS = 51


def h1(s):
    mt5.symbol_select(s, True)
    end = datetime.now(timezone.utc); cur = end - timedelta(days=365.25 * 10); fr = []
    while cur < end:
        hi = min(cur + timedelta(days=400), end)
        r = mt5.copy_rates_range(s, mt5.TIMEFRAME_H1, cur, hi)
        if r is not None and len(r):
            fr.append(pd.DataFrame(r))
        cur = hi
    raw = pd.concat(fr).drop_duplicates("time").sort_values("time")
    raw["t"] = pd.to_datetime(raw["time"], unit="s", utc=True)
    return raw[raw["t"] < CUT].set_index("t")


def weekend_excess(s):
    """Return DataFrame indexed by weekend (Fri date) with excess log-return + R unit + cost_R."""
    info = mt5.symbol_info(s); pt = info.point
    spread_px = max(info.spread, 1) * pt
    swap_long = info.swap_long * pt if info.swap_mode == 1 else 0.0    # negative = pay
    df = h1(s)
    close = df["close"]
    lr = np.log(close / close.shift()).dropna()
    drift_per_hr = lr.mean()                                          # unconditional per-hour drift
    # daily ATR (from H1 -> resample) for R unit
    d = close.resample("1D").ohlc().dropna()
    tr = pd.concat([d["high"] - d["low"], (d["high"] - d["close"].shift()).abs(),
                    (d["low"] - d["close"].shift()).abs()], axis=1).max(axis=1)
    atr = float(tr.ewm(alpha=1 / 21, adjust=False).mean().dropna().median())
    px = float(close.median())
    R_ret = 2 * atr / px                                             # risk unit as a return
    rows = []
    fri = close[(close.index.dayofweek == 4) & (close.index.hour == 21)]
    for ts, entry in fri.items():
        exit_ts = ts + pd.Timedelta(hours=HOURS)                     # Mon 00:00
        if exit_ts not in close.index:
            near = close.index[(close.index >= exit_ts) & (close.index < exit_ts + pd.Timedelta(hours=3))]
            if len(near) == 0:
                continue
            exit_ts = near[0]
        raw = float(np.log(close.loc[exit_ts] / entry))
        excess = raw - drift_per_hr * HOURS
        rows.append({"weekend": ts.normalize(), "raw": raw, "excess": excess})
    out = pd.DataFrame(rows).set_index("weekend")
    # cost as a return, in the (later-chosen) direction: long pays swap_long, short pays 0
    out.attrs.update(spread_px=spread_px, swap_long_px=swap_long, px=px, R_ret=R_ret)
    return out


def main():
    if not mt5.initialize(path=TERMINAL):
        raise SystemExit(mt5.last_error())
    btc, eth = weekend_excess("BTCUSDm"), weekend_excess("ETHUSDm")
    mt5.shutdown()

    j = pd.concat([btc["excess"].rename("btc"), eth["excess"].rename("eth")], axis=1).dropna()
    j["avg"] = j[["btc", "eth"]].mean(axis=1)                        # basket per-weekend excess
    N = len(j); mean = j["avg"].mean(); sd = j["avg"].std(ddof=1)
    t = mean / (sd / np.sqrt(N))
    direction = 1 if mean > 0 else -1
    idx = pd.DatetimeIndex(j.index)
    if idx.tz is None:
        idx = idx.tz_localize("UTC")
    pre = j["avg"][idx < SPLIT].mean()
    post = j["avg"][idx >= SPLIT].mean()
    sign_ok = np.sign(pre) == np.sign(post) == np.sign(mean)

    # economic net (drift-neutral excess) in R, per asset then pooled, in the dev direction
    def net_R(d):
        cost_ret = (2 * d.attrs["spread_px"]
                    + (max(0.0, -d.attrs["swap_long_px"]) if direction > 0 else 0.0) * NIGHTS) / d.attrs["px"]
        return (direction * d["excess"] - cost_ret) / d.attrs["R_ret"]
    net = pd.concat([net_R(btc), net_R(eth)])
    econ = float(net.mean())

    print("=" * 60)
    print("CRYPTO WEEKEND — DEV (holdout sealed)   Fri21:00->Mon00:00 UTC")
    print("=" * 60)
    print(f"  weekends (basket)   : {N}")
    print(f"  mean excess         : {mean:+.5f}  (raw window return, drift-removed)")
    print(f"  excess t-stat       : {t:+.2f}   [need |t|>=2]")
    print(f"  dev direction       : {'LONG' if direction>0 else 'SHORT'} weekends")
    print(f"  pre-2022 / post-2022 excess mean: {pre:+.5f} / {post:+.5f}  sign-consistent={sign_ok}")
    print(f"  economic net (drift-neutral, after spread+{NIGHTS}x swap): {econ:+.4f} R  [need >= +0.05]")
    e_ok, t_ok = econ >= 0.05, abs(t) >= 2.0
    verdict = e_ok and t_ok and sign_ok
    print(f"  KILL LINE: economic {'PASS' if e_ok else 'FAIL'} | statistical {'PASS' if t_ok else 'FAIL'} "
          f"| sign-consistency {'PASS' if sign_ok else 'FAIL'}")
    print(f"  -> DEV {'PASS: advance dev-direction to sealed holdout' if verdict else 'FAIL: thesis closed, holdout NOT run'}")
    log_run("crypto-calendar", {"window": "Fri21-Mon00 UTC", "nights": NIGHTS}, "development",
            {"weekends": N, "excess_mean": round(mean, 5), "excess_t": round(t, 2),
             "econ_net_R": round(econ, 4), "sign_consistent": bool(sign_ok),
             "verdict": "PASS" if verdict else "FAIL"}, note="Dev weekend test; holdout sealed")


if __name__ == "__main__":
    main()
