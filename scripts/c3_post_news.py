"""C3 first run — post-news drift/fade on gold M15 (DEVELOPMENT ONLY, primary).

Calendar: doc/us_high_impact_calendar_2018_2026.csv, loaded scheduled_only + as_of
= holdout cutoff (drops the 3 emergency FOMC and all future rows). The calendar
sha256 is logged with every run. Grid: branch {drift, fade} x exit_horizon {2h, 6h},
settle 30 min fixed. Low single-symbol N (~192 events 2018->2024-01) -> weak power;
the primary gate is the kill line (dev expR <= 0 after costs -> stop that branch).

Usage:  python scripts/c3_post_news.py
"""
from __future__ import annotations

import itertools

import pandas as pd

from gold_qm_system.calendar import NewsCalendar
from gold_qm_system.config import SystemConfig
from gold_qm_system.data import normalize_ohlcv
from gold_qm_system.engine import run_backtest
from gold_qm_system.engine.post_news import make_c3_factory
from gold_qm_system.metrics import compute_stats
from gold_qm_system.research_gate import development_only, log_run, holdout_cutoff, file_sha256

CAL = "doc/us_high_impact_calendar_2018_2026.csv"
BRANCHES = ["drift", "fade"]
HORIZONS = [2.0, 6.0]


def main() -> None:
    cutoff = holdout_cutoff()
    cal = NewsCalendar.from_csv(CAL, scheduled_only=True, as_of=cutoff)
    cal_hash = file_sha256(CAL)
    df = pd.read_csv("market_data_long/XAUUSD_M15.csv")
    bars = development_only(normalize_ohlcv(df, "M15"))
    print(f"gold M15 dev: {len(bars)} bars {bars.index[0].date()}..{bars.index[-1].date()}")
    print(f"calendar: {len(cal.events)} scheduled events <{cutoff.date()}  sha256={cal_hash}\n")

    cfg = SystemConfig.from_yaml("forwardtest_iter3_config.yaml")
    d = cfg.model_dump()
    d["timeframes"]["entry"] = "M15"
    d["sizing"].update({"min_size": 0.0, "size_step": 0.0, "margin_per_unit": 0.0})
    cfg = SystemConfig.model_validate(d)

    # pre-registration (with calendar hash) BEFORE the runs
    log_run("C3-post-news",
            {"family": "post-news", "branches": BRANCHES, "horizons_h": HORIZONS,
             "settle_min": 30, "market": "XAUUSD", "tf": "M15", "calendar_sha256": cal_hash,
             "kill_line": "dev expR<=0 after costs on gold -> stop branch"},
            "pre-registration", {}, note="Frozen before first C3 backtest")

    print(f"{'branch':<7}{'horizon':>9}{'n':>6}{'expR':>9}{'win%':>7}{'PF':>7}{'sumR':>9}  verdict")
    print("-" * 60)
    for branch, hz in itertools.product(BRANCHES, HORIZONS):
        res = run_backtest(cfg, bars, calendar=cal,
                           strategy_factory=make_c3_factory(branch, hz))
        st = compute_stats(res.trades, res.equity_curve, res.slippage_log,
                           cfg.account.initial_equity)
        n = st["trades"]; exp = st.get("expectancy_r") or 0.0
        pf = st.get("profit_factor") or 0.0; win = st.get("win_rate") or 0.0
        sumr = sum(t.r_multiple for t in res.trades)
        log_run("C3-post-news",
                {"branch": branch, "exit_horizon_h": hz, "settle_min": 30,
                 "market": "XAUUSD", "tf": "M15", "calendar_sha256": cal_hash},
                "development",
                {"trades": n, "expectancy_r": exp, "win_rate": win, "profit_factor": pf,
                 "sum_r": sumr, "max_dd": st.get("max_drawdown")},
                note=f"C3 primary grid; cal {cal_hash}")
        print(f"{branch:<7}{hz:>8}h{n:>6}{exp:>+9.4f}{win:>7.1%}{pf:>7.2f}{sumr:>+9.1f}"
              f"  {'PASS' if exp > 0 else 'KILL'}")

    print("\nLow N (~events/symbol); single-symbol gate. Basket (gold + USD pairs) would")
    print("multiply N but stays cost-hostile (news-window spreads are widest).")


if __name__ == "__main__":
    main()
