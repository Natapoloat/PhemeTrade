"""Turn-of-month — pre-registered DEV test, last shot (holdout >= 2024-01-09 SEALED).

Window per index: enter at the D1 close of the last trading day of the calendar month,
exit at the D1 close of the 3rd trading day of the next month (~3 sessions). Drift-neutral
excess = raw 3-day return - unconditional daily drift x 3. Pooled 5-index basket (excess
averaged per month to respect ~0.8 cross-index correlation). Two-sided; sign consistency
across pre/post-2021-01. Economic net after round-trip spread + 3 nightly swaps, R=2*ATR_D1.
Kill line: econ >= +0.05R AND |t| >= 2 AND same excess sign pre/post-2021.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import MetaTrader5 as mt5
import numpy as np
import pandas as pd

from gold_qm_system.research_gate import log_run

TERMINAL = r"C:\Program Files\MetaTrader 5 EXNESS\terminal64.exe"
INDICES = ["US30m", "US500m", "USTECm", "UK100m", "JP225m"]
CUT = pd.Timestamp("2024-01-09", tz="UTC")
SPLIT = pd.Timestamp("2021-01-01", tz="UTC")
NIGHTS = 3


def d1(s):
    mt5.symbol_select(s, True)
    end = datetime.now(timezone.utc); cur = end - timedelta(days=365.25 * 10); fr = []
    while cur < end:
        hi = min(cur + timedelta(days=1500), end)
        r = mt5.copy_rates_range(s, mt5.TIMEFRAME_D1, cur, hi)
        if r is not None and len(r):
            fr.append(pd.DataFrame(r))
        cur = hi
    raw = pd.concat(fr).drop_duplicates("time").sort_values("time")
    raw["t"] = pd.to_datetime(raw["time"], unit="s", utc=True)
    return raw[raw["t"] < CUT].set_index("t")


def excess_by_month(s):
    info = mt5.symbol_info(s); pt = info.point
    spread_px = max(info.spread, 1) * pt
    swap_long = info.swap_long * pt if info.swap_mode == 1 else 0.0
    df = d1(s); c = df["close"]
    lr = np.log(c / c.shift()).dropna()
    drift = lr.mean()
    h, l = df["high"], df["low"]; pc = c.shift()
    atr = float(pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
                .ewm(alpha=1 / 21, adjust=False).mean().dropna().median())
    px = float(c.median()); R_ret = 2 * atr / px
    # per calendar month: last trading day -> 3rd trading day of next month
    g = list(df.groupby([df.index.year, df.index.month]))
    rows = []
    for i in range(len(g) - 1):
        (_, cur_bars), (_, nxt_bars) = g[i], g[i + 1]
        if len(nxt_bars) < 3:
            continue
        entry_t = cur_bars.index[-1]; entry = cur_bars["close"].iloc[-1]
        exit = nxt_bars["close"].iloc[2]           # 3rd trading day
        raw = float(np.log(exit / entry))
        rows.append({"month": entry_t.normalize(), "excess": raw - drift * NIGHTS})
    out = pd.DataFrame(rows).set_index("month")
    out.attrs.update(spread_px=spread_px, swap_long_px=swap_long, px=px, R_ret=R_ret)
    return out


def main():
    if not mt5.initialize(path=TERMINAL):
        raise SystemExit(mt5.last_error())
    data = {s: excess_by_month(s) for s in INDICES}
    mt5.shutdown()

    ex = pd.concat([data[s]["excess"].rename(s) for s in INDICES], axis=1)
    ex["avg"] = ex.mean(axis=1)                      # basket per-month excess
    j = ex.dropna(subset=["avg"])
    N = len(j); mean = j["avg"].mean(); sd = j["avg"].std(ddof=1)
    t = mean / (sd / np.sqrt(N)); direction = 1 if mean > 0 else -1
    idx = pd.DatetimeIndex(j.index)
    idx = idx.tz_localize("UTC") if idx.tz is None else idx
    pre, post = j["avg"][idx < SPLIT].mean(), j["avg"][idx >= SPLIT].mean()
    sign_ok = np.sign(pre) == np.sign(post) == np.sign(mean)

    def net_R(d):
        cost = (2 * d.attrs["spread_px"]
                + (max(0.0, -d.attrs["swap_long_px"]) if direction > 0 else 0.0) * NIGHTS) / d.attrs["px"]
        return (direction * d["excess"] - cost) / d.attrs["R_ret"]
    econ = float(pd.concat([net_R(data[s]) for s in INDICES]).mean())

    e_ok, t_ok = econ >= 0.05, abs(t) >= 2.0
    passed = e_ok and t_ok and sign_ok
    print("=" * 60)
    print("TURN-OF-MONTH — DEV (holdout sealed)   last-day -> 3rd, 5-index basket")
    print("=" * 60)
    print(f"  months (basket)     : {N}")
    print(f"  mean excess         : {mean:+.5f}")
    print(f"  excess t-stat       : {t:+.2f}   [need |t|>=2]")
    print(f"  dev direction       : {'LONG' if direction>0 else 'SHORT'}")
    print(f"  pre/post-2021 excess: {pre:+.5f} / {post:+.5f}  sign-consistent={sign_ok}")
    print(f"  economic net (after spread+{NIGHTS}x swap): {econ:+.4f} R  [need >= +0.05]")
    print(f"  KILL LINE: economic {'PASS' if e_ok else 'FAIL'} | statistical {'PASS' if t_ok else 'FAIL'} "
          f"| sign {'PASS' if sign_ok else 'FAIL'}")
    if passed:
        print("  -> CLEAN 3-GATE PASS: opens a holdout discussion")
    elif direction > 0 and (e_ok or t_ok):
        print("  -> INCONCLUSIVE (marginal/underpowered): recorded, conclude anyway")
    else:
        print("  -> DEV FAIL: conclude")
    log_run("turn-of-month", {"window": "lastday->3rd D1", "nights": NIGHTS}, "development",
            {"months": N, "excess_mean": round(mean, 5), "excess_t": round(t, 2),
             "econ_net_R": round(econ, 4), "sign_consistent": bool(sign_ok),
             "verdict": "PASS" if passed else ("INCONCLUSIVE" if (e_ok or t_ok) else "FAIL")},
            note="Dev turn-of-month test, last shot; holdout sealed")


if __name__ == "__main__":
    main()
