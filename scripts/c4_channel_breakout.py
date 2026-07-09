"""C4 benchmark — Donchian channel breakout on gold H1 (DEVELOPMENT ONLY).

Run on H1 (not M15): gold's H1 cost/ATR (~0.15) is roughly half M15's (~0.29), so
a trend-follow edge has a fighting chance against costs. This is the BENCHMARK the
other candidates' OOS must beat; it is only a deployment candidate if it clears
acceptance (net PF >= 1.3) outright. Every config logged to the registry.

Usage:  python scripts/c4_channel_breakout.py
"""
from __future__ import annotations

import itertools

import pandas as pd

from gold_qm_system.config import SystemConfig
from gold_qm_system.data import normalize_ohlcv
from gold_qm_system.engine import run_backtest
from gold_qm_system.engine.channel_breakout import make_c4_factory
from gold_qm_system.metrics import compute_stats
from gold_qm_system.research_gate import development_only, log_run, holdout_cutoff

LOOKBACKS = [20, 55]
BANDS = [(0.0, 1.0), (0.5, 1.0)]   # no gate; high-vol only


def main() -> None:
    df = pd.read_csv("market_data_long/XAUUSD_H1.csv")
    bars = development_only(normalize_ohlcv(df, "H1"))
    print(f"gold H1 dev: {len(bars)} bars {bars.index[0].date()}..{bars.index[-1].date()} "
          f"(holdout>={holdout_cutoff().date()})\n")

    cfg = SystemConfig.from_yaml("forwardtest_iter3_config.yaml")
    d = cfg.model_dump()
    d["timeframes"]["entry"] = "H1"
    d["sizing"].update({"min_size": 0.0, "size_step": 0.0, "margin_per_unit": 0.0})
    d["news"]["calendar_csv"] = None
    cfg = SystemConfig.model_validate(d)

    print(f"{'L':>4}{'band':>12}{'n':>7}{'expR':>9}{'win%':>7}{'PF':>7}{'sumR':>9}  net-accept?")
    print("-" * 66)
    for L, (lo, hi) in itertools.product(LOOKBACKS, BANDS):
        res = run_backtest(cfg, bars, strategy_factory=make_c4_factory(L, lo, hi))
        st = compute_stats(res.trades, res.equity_curve, res.slippage_log,
                           cfg.account.initial_equity)
        n = st["trades"]; exp = st.get("expectancy_r") or 0.0
        pf = st.get("profit_factor") or 0.0; win = st.get("win_rate") or 0.0
        sumr = sum(t.r_multiple for t in res.trades)
        accept = "YES" if (pf >= 1.3 and exp > 0) else "no"
        log_run("C4-channel-breakout",
                {"lookback": L, "pctile_band": [lo, hi], "market": "XAUUSD", "tf": "H1"},
                "development",
                {"trades": n, "expectancy_r": exp, "win_rate": win,
                 "profit_factor": pf, "sum_r": sumr, "max_dd": st.get("max_drawdown")},
                note="C4 benchmark (gold H1 dev)")
        print(f"{L:>4}{str((lo, hi)):>12}{n:>7}{exp:>+9.4f}{win:>7.1%}{pf:>7.2f}{sumr:>+9.1f}{accept:>13}")

    print("\nBenchmark reference. It becomes a candidate only if a config clears net PF>=1.3.")


if __name__ == "__main__":
    main()
