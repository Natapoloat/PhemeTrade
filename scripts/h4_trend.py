"""H4-trend — the pre-registered test (DEVELOPMENT ONLY; holdout sealed).

Frozen spec (RESEARCH_REGISTRY.md -> H4-trend): channel-breakout trend on H4, Donchian
L=30, chandelier 3xATR, ATR(21), no vol gate, single config (no grid). Primary universe
= {BTCUSD, ETHUSD, USOIL, UKOIL, JP225}. Per-symbol cost calibration incl. CORRECT swaps
(swap_mode==1 -> points). Vol-scaled sizing (0.5%/trade, 3xATR stop) is the engine default.

Params were fixed ex-ante and never optimized on this data, so the full dev window is a
valid frozen-param (all-OOS) test; the sealed 2.5y holdout is the final confirmation and
is NOT run here. Kill line: pooled net expR <= 0 OR PF < 1.2 -> H4-trend closed; also
require a majority of symbols net-positive.

Usage:  python scripts/h4_trend.py
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
from gold_qm_system.metrics import compute_stats
from gold_qm_system.research_gate import development_only, log_run

TERMINAL = r"C:\Program Files\MetaTrader 5 EXNESS\terminal64.exe"
UNIVERSE = ["BTCUSDm", "ETHUSDm", "USOILm", "UKOILm", "JP225m"]
L = 30                      # H4-native (NOT the D1 L55); frozen


def fetch_h4(s):
    mt5.symbol_select(s, True)
    end = datetime.now(timezone.utc); cur = end - timedelta(days=365.25 * 12); fr = []
    while cur < end:
        hi = min(cur + timedelta(days=800), end)
        r = mt5.copy_rates_range(s, mt5.TIMEFRAME_H4, cur, hi)
        if r is not None and len(r):
            fr.append(pd.DataFrame(r))
        cur = hi
    if not fr:
        return None
    raw = pd.concat(fr).drop_duplicates("time").sort_values("time")
    return normalize_ohlcv(pd.DataFrame({
        "open_time": pd.to_datetime(raw["time"], unit="s", utc=True),
        "open": raw["open"], "high": raw["high"], "low": raw["low"],
        "close": raw["close"], "volume": raw["tick_volume"]}).iloc[:-1], "H4")


def cfg_for(base, sym, zero_cost):
    info = mt5.symbol_info(sym); pt = info.point
    spread_px = max(info.spread, 1) * pt
    sl = info.swap_long * pt if info.swap_mode == 1 else 0.0      # mode 1 = POINTS
    ss = info.swap_short * pt if info.swap_mode == 1 else 0.0
    d = base.model_dump(); d["symbol"] = sym
    d["timeframes"].update({"entry": "H4", "setup": "H4", "directional": "H4"})
    d["sizing"].update({"min_size": 0.0, "size_step": 0.0, "margin_per_unit": 0.0})
    d["news"]["calendar_csv"] = None
    if zero_cost:
        for k in d["costs"]:
            if isinstance(d["costs"][k], (int, float)):
                d["costs"][k] = 0.0
    else:
        d["costs"].update({
            "spread_asian": spread_px, "spread_london": spread_px, "spread_newyork": spread_px,
            "spread_overlap": spread_px, "spread_news_extra": spread_px,
            "base_slippage": 0.5 * spread_px, "stop_slippage_extra": 1.0 * spread_px,
            "news_slippage_extra": spread_px,
            "swap_long_per_unit_day": sl, "swap_short_per_unit_day": ss})
        d["kill_switches"]["spread_cap"] = max(d["kill_switches"]["spread_cap"], 6.0 * spread_px)
    return SystemConfig.model_validate(d)


def main():
    if not mt5.initialize(path=TERMINAL):
        raise SystemExit(mt5.last_error())
    base = SystemConfig.from_yaml("forwardtest_iter3_config.yaml")
    log_run("H4-trend", {"tf": "H4", "L": L, "universe": UNIVERSE, "swaps": "correct(mode1)"},
            "development", {}, note="Pre-registered H4-trend test; dev; holdout sealed")

    rows, trades = [], {}
    for s in UNIVERSE:
        bars = fetch_h4(s)
        if bars is None:
            print(f"  {s} SKIP"); continue
        bars = development_only(bars)
        out = {}
        for zero, tag in [(False, "net"), (True, "gross")]:
            res = run_backtest(cfg_for(base, s, zero), bars, strategy_factory=make_c4_factory(L, 0.0, 1.0))
            st = compute_stats(res.trades, res.equity_curve, res.slippage_log, 100000)
            out[tag] = (st["trades"], st.get("expectancy_r") or 0.0, st.get("profit_factor") or 0.0)
            if tag == "net":
                trades[s] = pd.DataFrame([{"exit_time": t.exit_time, "r": t.r_multiple} for t in res.trades])
        rows.append({"symbol": s, "n": out["net"][0], "net_expR": round(out["net"][1], 3),
                     "net_PF": round(out["net"][2], 2), "gross_PF": round(out["gross"][2], 2)})
        r = rows[-1]
        print(f"  {s:<9} n={r['n']:>4} net_expR={r['net_expR']:>+6} net_PF={r['net_PF']:>5} gross_PF={r['gross_PF']:>5}", flush=True)
    mt5.shutdown()

    allr = pd.concat([trades[s] for s in trades if len(trades[s])], ignore_index=True).sort_values("exit_time")
    rs = allr["r"].to_numpy()
    exp = float(rs.mean()); gl = -rs[rs < 0].sum()
    pf = float(rs[rs > 0].sum() / gl) if gl > 0 else float("inf")
    t = float(exp / (rs.std(ddof=1) / np.sqrt(len(rs)))) if len(rs) > 1 else float("nan")
    n_pos = sum(1 for r in rows if r["net_expR"] > 0)
    df = pd.DataFrame(rows); df.to_csv("output/h4_trend_dev.csv", index=False)
    log_run("H4-trend", {"tf": "H4", "L": L}, "development-pooled",
            {"trades": len(rs), "expectancy_r": exp, "profit_factor": pf, "t": t,
             "symbols_pos": n_pos}, note="dev pooled; holdout NOT run")

    print("\n" + "=" * 54)
    print(f"H4-TREND POOLED (DEV; holdout sealed)  N={len(rs)}")
    print(f"  net expR = {exp:+.4f} R   PF = {pf:.3f}   t = {t:+.2f}")
    print(f"  symbols net-positive: {n_pos}/{len(rows)}")
    kill = exp <= 0 or pf < 1.2
    passed = (not kill) and n_pos > len(rows) / 2
    print(f"  KILL LINE (expR<=0 or PF<1.2): {'HIT -> H4-trend closed' if kill else 'not hit'}")
    print(f"  -> {'DEV PASS: advance to sealed holdout (with sign-off)' if passed else 'DEV FAIL: no holdout; done'}")
    print("=" * 54)


if __name__ == "__main__":
    main()
