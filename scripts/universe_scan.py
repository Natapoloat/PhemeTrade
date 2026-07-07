"""Universe scan: fetch M15 for a liquid multi-asset set from Exness MT5,
cost-calibrate per symbol, and backtest the QM strategy (fixed_rr, as
validated on gold) on each.

DISCIPLINE: scanning N symbols and picking the best is multiple-comparisons
data-snooping — some symbols WILL look good by chance. This ranks ALL symbols
with trade counts as HYPOTHESIS GENERATION. Any candidate must then survive an
out-of-sample walk-forward on its own before it means anything. Ranked on
expectancy-R / profit factor (scale-free); $PnL is omitted (contract sizes
differ across assets).

Usage:  python scripts/universe_scan.py [--years 6] [--out output/universe_scan.csv]
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

import MetaTrader5 as mt5
import pandas as pd

from gold_qm_system.config import SystemConfig
from gold_qm_system.data import normalize_ohlcv
from gold_qm_system.engine import run_backtest
from gold_qm_system.metrics import compute_stats

TERMINAL = r"C:\Program Files\MetaTrader 5 EXNESS\terminal64.exe"

UNIVERSE = {
    "FX-major": ["EURUSDm", "GBPUSDm", "USDJPYm", "USDCHFm", "AUDUSDm", "USDCADm", "NZDUSDm"],
    "FX-cross": ["EURJPYm", "GBPJPYm", "EURGBPm"],
    "Metal":    ["XAUUSDm", "XAGUSDm"],
    "Index":    ["US30m", "US500m", "USTECm", "UK100m", "JP225m"],
    "Energy":   ["USOILm", "UKOILm"],
    "Crypto":   ["BTCUSDm", "ETHUSDm"],
}


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
        "open_time": pd.to_datetime(raw["time"], unit="s", utc=True),  # server=UTC (offset 0, verified)
        "open": raw["open"], "high": raw["high"], "low": raw["low"],
        "close": raw["close"], "volume": raw["tick_volume"],
    }).iloc[:-1]  # drop still-forming bar
    return normalize_ohlcv(df, "M15")


def symbol_config(base: SystemConfig, symbol: str) -> SystemConfig:
    """Per-symbol cost model: spread from the broker's current spread in
    points; slippage scaled to that spread; swaps point-scaled. Sizing left
    granularity-free so R-multiples are unaffected."""
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
    return SystemConfig.model_validate(d)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--years", type=float, default=6.0)
    ap.add_argument("--out", default="output/universe_scan.csv")
    ap.add_argument("--config", default="backtest_m15_config.yaml")
    args = ap.parse_args()

    if not mt5.initialize(path=TERMINAL):
        raise SystemExit(f"MT5 init failed: {mt5.last_error()} — is the Exness terminal logged in?")
    base = SystemConfig.from_yaml(args.config)

    rows = []
    for asset_class, symbols in UNIVERSE.items():
        for sym in symbols:
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
                rows.append({
                    "asset_class": asset_class, "symbol": sym,
                    "bars": len(bars), "years": round(years, 1),
                    "trades": st["trades"],
                    "expectancy_r": round(st.get("expectancy_r") or 0, 3),
                    "win_rate": round(st.get("win_rate") or 0, 3),
                    "profit_factor": round(st.get("profit_factor") or 0, 3),
                    "max_dd": round(st.get("max_drawdown") or 0, 3),
                    "trades_per_year": round((st["trades"] / years) if years else 0, 1),
                })
                r = rows[-1]
                print(f"  {sym:<10} trades={r['trades']:>3}  expR={r['expectancy_r']:>6}  "
                      f"PF={r['profit_factor']:>5}  win={r['win_rate']:.0%}  yrs={r['years']}",
                      flush=True)
            except Exception as e:  # noqa: BLE001
                print(f"  {sym:<10} ERROR {e}", flush=True)
    mt5.shutdown()

    df = pd.DataFrame(rows)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out, index=False)
    print(f"\n=== RANKED (expectancy_r; ⚠ multiple-comparisons — validate winners OOS) ===")
    show = df.sort_values("expectancy_r", ascending=False)
    print(show.to_string(index=False))
    print(f"\nwrote {args.out}")
    pos = df[df.expectancy_r > 0]
    print(f"symbols with positive expectancy: {len(pos)}/{len(df)} "
          f"(by chance alone at 50/50 you'd expect ~{len(df)//2})")


if __name__ == "__main__":
    main()
