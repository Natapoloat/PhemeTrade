"""E1 — Frozen-config 12-symbol portfolio backtest (full available history).

Runs the FROZEN gold Iteration-3 config (FVG>=0.5 + swing SL) on each basket
symbol with NO per-symbol re-tuning (only per-symbol cost calibration + sizing
granularity, exactly as universe_scan). Purpose:

  (1) N-multiplication toward statistical power, and
  (2) a genuine OUT-OF-SYMBOL out-of-sample test: params came from gold, so the
      11 non-gold symbols are OOS-by-symbol. Gold itself is IN-SAMPLE (labelled).

Reports: per-symbol table, POOLED OOS basket stats (aggregate N, pooled
expectancy/PF, pooled R-equity max-DD, single-symbol PnL concentration), and the
cross-symbol correlation of monthly trade outcomes (diversification only helps if
correlations are low).

DISCIPLINE: freezing the gold config is the whole point — re-optimizing the FVG
threshold per symbol would convert this OOS-by-symbol test into in-sample.

Usage:  python scripts/portfolio_backtest.py [--years 25] [--out output/e1_portfolio]
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
from gold_qm_system.metrics import compute_stats

TERMINAL = r"C:\Program Files\MetaTrader 5 EXNESS\terminal64.exe"

# 12-symbol basket (metals + FX majors/crosses). Gold first = IN-SAMPLE reference.
BASKET = ["XAUUSDm", "XAGUSDm", "EURUSDm", "GBPUSDm", "USDJPYm", "AUDUSDm",
          "USDCADm", "NZDUSDm", "EURJPYm", "GBPJPYm", "USDCHFm", "EURGBPm"]
IN_SAMPLE = {"XAUUSDm"}  # params were derived on gold


def fetch_m15(symbol: str, years: float) -> pd.DataFrame | None:
    mt5.symbol_select(symbol, True)
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=365.25 * years)
    frames, cur = [], start
    while cur < end:
        hi = min(cur + timedelta(days=45), end)
        r = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M15, cur, hi)
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
    return normalize_ohlcv(df, "M15")


def symbol_config(base: SystemConfig, symbol: str) -> SystemConfig:
    """Per-symbol COST calibration only (spread/slippage/swap from the broker);
    all signal/risk params stay frozen at the gold values."""
    info = mt5.symbol_info(symbol)
    point = info.point
    spread_px = max(info.spread, 1) * point
    swap_long = info.swap_long * point if info.swap_mode == 0 else 0.0
    swap_short = info.swap_short * point if info.swap_mode == 0 else 0.0
    d = base.model_dump()
    d["symbol"] = symbol
    d["costs"].update({
        "spread_asian": spread_px, "spread_london": spread_px,
        "spread_newyork": spread_px, "spread_overlap": spread_px,
        "spread_news_extra": spread_px, "base_slippage": 0.5 * spread_px,
        "stop_slippage_extra": 1.0 * spread_px, "news_slippage_extra": spread_px,
        "swap_long_per_unit_day": swap_long, "swap_short_per_unit_day": swap_short,
    })
    d["sizing"].update({"min_size": 0.0, "size_step": 0.0, "margin_per_unit": 0.0})
    d["news"]["calendar_csv"] = None
    # spread_cap is an ABSOLUTE-price kill switch (gold-tuned 1.5); without scaling
    # it vetoes every entry on high-nominal-spread instruments (BTC spread_px~10,
    # indices ~3) → 0 trades. Scale it to the symbol's own spread (preserve gold's
    # ~6x headroom); max() so it only ever RAISES the cap → never newly-vetoes a
    # symbol that already traded (FX/metals results unchanged).
    d["kill_switches"]["spread_cap"] = max(d["kill_switches"]["spread_cap"], 6.0 * spread_px)
    return SystemConfig.model_validate(d)


def pooled_stats(rs: np.ndarray) -> dict:
    """Scale-free pooled stats from an array of per-trade R-multiples."""
    if len(rs) == 0:
        return {"n": 0}
    wins, losses = rs[rs > 0], rs[rs < 0]
    gross_win, gross_loss = wins.sum(), -losses.sum()
    eq = np.cumsum(rs)                       # R-space equity curve
    peak = np.maximum.accumulate(eq)
    max_dd_r = float((peak - eq).max())
    return {
        "n": int(len(rs)),
        "expectancy_r": float(rs.mean()),
        "win_rate": float((rs > 0).mean()),
        "profit_factor": float(gross_win / gross_loss) if gross_loss > 0 else float("inf"),
        "sum_r": float(rs.sum()),
        "std_r": float(rs.std(ddof=1)) if len(rs) > 1 else float("nan"),
        "max_dd_r": max_dd_r,
        "t_stat": float(rs.mean() / (rs.std(ddof=1) / np.sqrt(len(rs)))) if len(rs) > 1 and rs.std(ddof=1) > 0 else float("nan"),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--years", type=float, default=25.0, help="fetch depth; MT5 caps M15 at what it has")
    ap.add_argument("--out", default="output/e1_portfolio")
    ap.add_argument("--config", default="forwardtest_iter3_config.yaml")
    ap.add_argument("--symbols", default="", help="comma-separated symbol list; overrides the default basket")
    args = ap.parse_args()

    basket = [s.strip() for s in args.symbols.split(",") if s.strip()] or BASKET

    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)

    if not mt5.initialize(path=TERMINAL):
        raise SystemExit(f"MT5 init failed: {mt5.last_error()} — is the Exness terminal logged in?")
    base = SystemConfig.from_yaml(args.config)
    assert base.qm.require_departure_fvg and base.qm.min_departure_fvg_atr == 0.5, \
        "config is not the frozen Iter3 gold config (FVG>=0.5)"

    rows, per_symbol_trades = [], {}
    for sym in basket:
        if mt5.symbol_info(sym) is None:
            print(f"  {sym:<10} SKIP (not offered)", flush=True)
            continue
        try:
            bars = fetch_m15(sym, args.years)
            if bars is None or len(bars) < 5000:
                print(f"  {sym:<10} SKIP (insufficient history)", flush=True)
                continue
            cfg = symbol_config(base, sym)
            res = run_backtest(cfg, bars)
            st = compute_stats(res.trades, res.equity_curve, res.slippage_log,
                               cfg.account.initial_equity)
            years = (bars.index[-1] - bars.index[0]).days / 365.25
            trades_df = pd.DataFrame([
                {"exit_time": t.exit_time, "r": t.r_multiple,
                 "dir": getattr(t.direction, "name", str(t.direction))}
                for t in res.trades
            ])
            per_symbol_trades[sym] = trades_df
            tag = "IS" if sym in IN_SAMPLE else "OOS"
            rows.append({
                "symbol": sym, "tag": tag, "yrs": round(years, 1), "bars": len(bars),
                "trades": st["trades"],
                "expectancy_r": round(st.get("expectancy_r") or 0, 3),
                "win_rate": round(st.get("win_rate") or 0, 3),
                "profit_factor": round(st.get("profit_factor") or 0, 3),
                "max_dd": round(st.get("max_drawdown") or 0, 3),
                "sum_r": round(float(trades_df["r"].sum()) if len(trades_df) else 0, 2),
                "tr_per_yr": round((st["trades"] / years) if years else 0, 1),
            })
            r = rows[-1]
            print(f"  {sym:<10} [{tag:<3}] tr={r['trades']:>3} expR={r['expectancy_r']:>6} "
                  f"PF={r['profit_factor']:>5} win={r['win_rate']:.0%} yrs={r['yrs']} sumR={r['sum_r']:>6}",
                  flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"  {sym:<10} ERROR {e}", flush=True)
    mt5.shutdown()

    df = pd.DataFrame(rows)
    df.to_csv(outdir / "per_symbol.csv", index=False)

    # ---- POOLED OOS basket (the generalization test; gold excluded) ----
    oos_syms = [s for s in per_symbol_trades if s not in IN_SAMPLE]
    oos_frames = [per_symbol_trades[s] for s in oos_syms if len(per_symbol_trades[s])]
    oos_all = pd.concat(oos_frames, ignore_index=True) if oos_frames else pd.DataFrame(columns=["exit_time", "r"])
    oos_all = oos_all.sort_values("exit_time")
    ps = pooled_stats(oos_all["r"].to_numpy())

    # single-symbol PnL concentration (share of positive sumR among OOS)
    sym_sumr = {s: float(per_symbol_trades[s]["r"].sum()) for s in oos_syms if len(per_symbol_trades[s])}
    total_pos = sum(v for v in sym_sumr.values() if v > 0) or float("nan")
    max_share = max((v / total_pos for v in sym_sumr.values() if v > 0), default=float("nan"))

    # ---- cross-symbol correlation of MONTHLY summed-R ----
    monthly = {}
    for s in oos_syms:
        t = per_symbol_trades[s]
        if not len(t):
            continue
        m = t.copy()
        m["month"] = pd.to_datetime(m["exit_time"]).dt.tz_localize(None).dt.to_period("M")
        monthly[s] = m.groupby("month")["r"].sum()
    corr_mean = float("nan")
    if len(monthly) >= 2:
        mdf = pd.DataFrame(monthly).fillna(0.0)
        cm = mdf.corr()
        iu = np.triu_indices_from(cm.values, k=1)
        corr_mean = float(np.nanmean(cm.values[iu]))
        cm.to_csv(outdir / "corr_monthly_R.csv")

    # ---- acceptance check (E1 pre-registered bar) ----
    passed = (ps.get("n", 0) >= 200 and ps.get("expectancy_r", -1) > 0
              and ps.get("profit_factor", 0) >= 1.3
              and (max_share != max_share or max_share <= 0.40))

    lines = []
    lines.append("=" * 68)
    lines.append("E1 — FROZEN-CONFIG 12-SYMBOL PORTFOLIO BACKTEST")
    lines.append("=" * 68)
    lines.append(df.to_string(index=False))
    lines.append("")
    lines.append("--- POOLED OOS BASKET (gold excluded; params frozen from gold = out-of-symbol) ---")
    lines.append(f"  symbols (OOS)     : {len(oos_syms)}  {oos_syms}")
    lines.append(f"  aggregate N       : {ps.get('n', 0)}")
    lines.append(f"  pooled expectancy : {ps.get('expectancy_r', float('nan')):+.4f} R")
    lines.append(f"  pooled PF         : {ps.get('profit_factor', float('nan')):.3f}")
    lines.append(f"  pooled win rate   : {ps.get('win_rate', float('nan')):.1%}")
    lines.append(f"  pooled sum / std R: {ps.get('sum_r', float('nan')):+.1f} / {ps.get('std_r', float('nan')):.3f}")
    lines.append(f"  pooled R max-DD   : {ps.get('max_dd_r', float('nan')):.1f} R")
    lines.append(f"  t-stat (H0: E[R]=0): {ps.get('t_stat', float('nan')):+.2f}")
    lines.append(f"  max single-symbol PnL share : {max_share:.0%}")
    lines.append(f"  mean pairwise monthly-R corr: {corr_mean:+.3f}")
    lines.append("")
    lines.append(f"  ACCEPTANCE (N>=200, expR>0, PF>=1.3, no symbol>40%): "
                 f"{'PASS' if passed else 'FAIL'}")
    report = "\n".join(lines)
    (outdir / "report.txt").write_text(report, encoding="utf-8")
    print("\n" + report)
    print(f"\nwrote {outdir}/report.txt, per_symbol.csv, corr_monthly_R.csv")


if __name__ == "__main__":
    main()
