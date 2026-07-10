"""C4-basket — frozen-param channel-breakout across a lower-cost basket (H1, dev only).

Applies the E1 portfolio method to the best gross edge found (C4 trend-follow). Gold
params FROZEN (L=55, no vol gate); no per-symbol tuning, only cost calibration. The
15 non-gold symbols are OUT-OF-SYMBOL OOS. Reports NET and GROSS pooled stats,
per-symbol table, cross-symbol correlation, effective-N, acceptance. Development
slice only (holdout sealed). Pre-registered in RESEARCH_REGISTRY.md.

Usage:  python scripts/c4_basket.py
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

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
BASKET = ["XAUUSDm", "XAGUSDm", "EURUSDm", "GBPUSDm", "USDJPYm", "AUDUSDm",
          "USDCADm", "NZDUSDm", "EURJPYm", "GBPJPYm", "USDCHFm", "EURGBPm",
          "BTCUSDm", "US30m", "USTECm", "USOILm"]
IN_SAMPLE = {"XAUUSDm"}
L, BAND = 55, (0.0, 1.0)   # frozen from gold
TF_MAP = {"H1": (mt5.TIMEFRAME_H1, 400), "D1": (mt5.TIMEFRAME_D1, 1500)}


def fetch(symbol: str, tf_label: str) -> pd.DataFrame | None:
    tf_const, step = TF_MAP[tf_label]
    mt5.symbol_select(symbol, True)
    end = datetime.now(timezone.utc)
    cur = end - timedelta(days=365.25 * 15)
    frames = []
    while cur < end:
        hi = min(cur + timedelta(days=step), end)
        r = mt5.copy_rates_range(symbol, tf_const, cur, hi)
        if r is not None and len(r):
            frames.append(pd.DataFrame(r))
        cur = hi
    if not frames:
        return None
    raw = pd.concat(frames).drop_duplicates("time").sort_values("time")
    df = pd.DataFrame({
        "open_time": pd.to_datetime(raw["time"], unit="s", utc=True),
        "open": raw["open"], "high": raw["high"], "low": raw["low"],
        "close": raw["close"], "volume": raw["tick_volume"],
    }).iloc[:-1]
    return normalize_ohlcv(df, tf_label)


def symbol_config(base: SystemConfig, symbol: str, zero_cost: bool,
                  tf_label: str) -> SystemConfig:
    info = mt5.symbol_info(symbol)
    point = info.point
    spread_px = max(info.spread, 1) * point
    # swap_mode 1 = POINTS (Exness) -> price = swap * point; mode 0 = disabled -> 0.
    # (Earlier code used ==0 which is DISABLED, so it charged ZERO swaps everywhere.)
    swap_long = info.swap_long * point if info.swap_mode == 1 else 0.0
    swap_short = info.swap_short * point if info.swap_mode == 1 else 0.0
    d = base.model_dump()
    d["symbol"] = symbol
    # C4 uses only entry bars (its own ATR/Donchian) — collapse all TFs to the run TF
    # so the entry<=setup<=directional constraint holds for D1 too.
    d["timeframes"].update({"entry": tf_label, "setup": tf_label, "directional": tf_label})
    d["sizing"].update({"min_size": 0.0, "size_step": 0.0, "margin_per_unit": 0.0})
    d["news"]["calendar_csv"] = None
    if zero_cost:
        for k in d["costs"]:
            if isinstance(d["costs"][k], (int, float)):
                d["costs"][k] = 0.0
    else:
        d["costs"].update({
            "spread_asian": spread_px, "spread_london": spread_px,
            "spread_newyork": spread_px, "spread_overlap": spread_px,
            "spread_news_extra": spread_px, "base_slippage": 0.5 * spread_px,
            "stop_slippage_extra": 1.0 * spread_px, "news_slippage_extra": spread_px,
            "swap_long_per_unit_day": swap_long, "swap_short_per_unit_day": swap_short,
        })
        d["kill_switches"]["spread_cap"] = max(d["kill_switches"]["spread_cap"], 6.0 * spread_px)
    return SystemConfig.model_validate(d)


def pooled(rs: np.ndarray) -> dict:
    if len(rs) == 0:
        return {"n": 0}
    gl = -rs[rs < 0].sum()
    eq = np.cumsum(rs); dd = float((np.maximum.accumulate(eq) - eq).max())
    return {"n": int(len(rs)), "expR": float(rs.mean()),
            "win": float((rs > 0).mean()),
            "PF": float(rs[rs > 0].sum() / gl) if gl > 0 else float("inf"),
            "sumR": float(rs.sum()), "maxdd_r": dd,
            "t": float(rs.mean() / (rs.std(ddof=1) / np.sqrt(len(rs)))) if len(rs) > 1 and rs.std(ddof=1) > 0 else float("nan")}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf", default="H1", choices=list(TF_MAP))
    args = ap.parse_args()
    tf = args.tf
    min_bars = 400 if tf == "D1" else 3000
    candidate = f"C4-basket-{tf.lower()}"

    if not mt5.initialize(path=TERMINAL):
        raise SystemExit(f"MT5 init failed: {mt5.last_error()}")
    base = SystemConfig.from_yaml("forwardtest_iter3_config.yaml")
    log_run(candidate, {"L": L, "band": list(BAND), "tf": tf, "symbols": BASKET,
            "frozen_from": "gold"}, "pre-registration", {},
            note="Frozen BEFORE first backtest; OOS-by-symbol for 15 non-gold")

    rows, trades_net = [], {}
    for sym in BASKET:
        if mt5.symbol_info(sym) is None:
            print(f"  {sym:<9} SKIP", flush=True); continue
        bars = fetch(sym, tf)
        if bars is None or len(bars) < min_bars:
            print(f"  {sym:<9} SKIP (insufficient)", flush=True); continue
        bars = development_only(bars)
        out = {}
        for zero, tag in [(False, "net"), (True, "gross")]:
            res = run_backtest(symbol_config(base, sym, zero, tf), bars,
                               strategy_factory=make_c4_factory(L, BAND[0], BAND[1]))
            st = compute_stats(res.trades, res.equity_curve, res.slippage_log, 100000)
            out[tag] = (st["trades"], st.get("expectancy_r") or 0.0, st.get("profit_factor") or 0.0)
            if tag == "net":
                trades_net[sym] = pd.DataFrame([{"exit_time": t.exit_time, "r": t.r_multiple}
                                                for t in res.trades])
        yrs = (bars.index[-1] - bars.index[0]).days / 365.25
        istag = "IS" if sym in IN_SAMPLE else "OOS"
        rows.append({"symbol": sym, "tag": istag, "yrs": round(yrs, 1),
                     "n": out["net"][0], "net_expR": round(out["net"][1], 3),
                     "net_PF": round(out["net"][2], 2), "gross_PF": round(out["gross"][2], 2)})
        r = rows[-1]
        print(f"  {sym:<9} [{istag:<3}] n={r['n']:>4} net_expR={r['net_expR']:>+6} "
              f"net_PF={r['net_PF']:>5} gross_PF={r['gross_PF']:>5} yrs={r['yrs']}", flush=True)
    mt5.shutdown()

    df = pd.DataFrame(rows)
    outdir = Path(f"output/{candidate}")
    outdir.mkdir(parents=True, exist_ok=True)
    df.to_csv(outdir / "per_symbol.csv", index=False)

    oos = [s for s in trades_net if s not in IN_SAMPLE]
    allr = pd.concat([trades_net[s] for s in oos if len(trades_net[s])], ignore_index=True)
    ps = pooled(allr["r"].to_numpy() if len(allr) else np.array([]))
    # concentration + correlation
    sym_sum = {s: float(trades_net[s]["r"].sum()) for s in oos if len(trades_net[s])}
    pos_tot = sum(v for v in sym_sum.values() if v > 0) or float("nan")
    max_share = max((v / pos_tot for v in sym_sum.values() if v > 0), default=float("nan"))
    monthly = {}
    for s in oos:
        t = trades_net[s]
        if len(t):
            m = t.copy(); m["mo"] = pd.to_datetime(m["exit_time"]).dt.tz_localize(None).dt.to_period("M")
            monthly[s] = m.groupby("mo")["r"].sum()
    corr = float("nan")
    if len(monthly) >= 2:
        cm = pd.DataFrame(monthly).fillna(0.0).corr().values
        corr = float(np.nanmean(cm[np.triu_indices_from(cm, k=1)]))
    n_eff = ps.get("n", 0) / (1 + (len(oos) - 1) * max(corr, 0)) if ps.get("n", 0) else 0

    log_run(candidate, {"L": L, "band": list(BAND), "tf": tf}, "development-oos-pooled",
            {"trades": ps.get("n", 0), "expectancy_r": ps.get("expR"), "profit_factor": ps.get("PF"),
             "t": ps.get("t"), "max_share": max_share, "corr": corr}, note="15 non-gold OOS-by-symbol")

    print("\n" + "=" * 62)
    print("C4-BASKET POOLED OOS (15 non-gold; frozen gold params = out-of-symbol)")
    print("=" * 62)
    print(f"  aggregate N        : {ps.get('n', 0)}")
    print(f"  pooled NET expR    : {ps.get('expR', float('nan')):+.4f} R")
    print(f"  pooled NET PF      : {ps.get('PF', float('nan')):.3f}")
    print(f"  pooled win rate    : {ps.get('win', float('nan')):.1%}")
    print(f"  t-stat (H0 E[R]=0) : {ps.get('t', float('nan')):+.2f}")
    print(f"  pooled R max-DD    : {ps.get('maxdd_r', float('nan')):.1f} R")
    print(f"  max symbol PnL share: {max_share:.0%}")
    print(f"  mean monthly-R corr: {corr:+.3f}   effective-N ~= {n_eff:.0f}")
    accept = ps.get("n", 0) >= 120 and ps.get("expR", -1) > 0 and ps.get("PF", 0) >= 1.3 and (max_share != max_share or max_share <= 0.40)
    kill = ps.get("expR", -1) <= 0 or ps.get("PF", 0) < 1.2
    print(f"\n  ACCEPTANCE (N>=120, expR>0, PF>=1.3, no symbol>40%): {'PASS' if accept else 'FAIL'}")
    print(f"  KILL LINE (expR<=0 or PF<1.2): {'HIT -> trend-follow-on-universe closed' if kill else 'not hit'}")


if __name__ == "__main__":
    main()
