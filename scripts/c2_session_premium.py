"""C2 first run — session-holding / overnight premium on gold H1 (DEVELOPMENT ONLY).

Triage step 2: cheapest candidate, one-afternoon cost verdict, doubles as a
rails shakedown for non-QM logic. Uses gold's deep local H1 (21.6y), sealed at
the frozen holdout (research_gate). Pre-registers a small set of session-hold
windows (long-only; the premium hypothesis is directional). Every window is
logged to the registry; multiplicity is acknowledged. Kill criterion: net
expectancy <= 0 after costs => stop (no rescue).

Usage:  python scripts/c2_session_premium.py
"""
from __future__ import annotations

import pandas as pd

from gold_qm_system.config import SystemConfig
from gold_qm_system.data import normalize_ohlcv
from gold_qm_system.engine import run_backtest
from gold_qm_system.engine.session_premium import make_c2_factory
from gold_qm_system.metrics import compute_stats
from gold_qm_system.research_gate import development_only, log_run, holdout_cutoff

# pre-registered windows (UTC): mechanism points to the illiquid/overnight hold.
WINDOWS = [
    ("overnight_21_7", 21, 7),   # NY close -> London open (primary: gap premium)
    ("asian_0_7", 0, 7),
    ("london_7_16", 7, 16),
    ("ny_13_21", 13, 21),
    ("day_7_21", 7, 21),
]
DIRECTION = "buy"


def main() -> None:
    df = pd.read_csv("market_data_long/XAUUSD_H1.csv")
    bars_all = normalize_ohlcv(df, "H1")
    bars = development_only(bars_all)  # seal the holdout
    print(f"gold H1: total={len(bars_all)} dev={len(bars)} "
          f"(dev {bars.index[0].date()}..{bars.index[-1].date()}; holdout>={holdout_cutoff().date()})\n")

    cfg = SystemConfig.from_yaml("forwardtest_iter3_config.yaml")
    d = cfg.model_dump()
    d["timeframes"]["entry"] = "H1"
    d["sizing"].update({"min_size": 0.0, "size_step": 0.0, "margin_per_unit": 0.0})
    d["news"]["calendar_csv"] = None
    cfg = SystemConfig.model_validate(d)

    print(f"{'window':<16} {'n':>5} {'expR':>8} {'win%':>6} {'PF':>6} {'sumR':>8}  verdict")
    print("-" * 66)
    for name, eh, ex in WINDOWS:
        factory = make_c2_factory(eh, ex, DIRECTION, entry_delta=pd.Timedelta(hours=1))
        res = run_backtest(cfg, bars, strategy_factory=factory)
        st = compute_stats(res.trades, res.equity_curve, res.slippage_log,
                           cfg.account.initial_equity)
        n = st["trades"]; exp = st.get("expectancy_r") or 0.0
        pf = st.get("profit_factor") or 0.0; win = st.get("win_rate") or 0.0
        sumr = sum(t.r_multiple for t in res.trades)
        verdict = "PASS(cont.)" if exp > 0 else "KILL"
        stats = {"trades": n, "expectancy_r": exp, "win_rate": win,
                 "profit_factor": pf, "sum_r": sumr, "max_dd": st.get("max_drawdown")}
        log_run("C2-session-premium",
                {"entry_hour": eh, "exit_hour": ex, "direction": DIRECTION,
                 "market": "XAUUSD", "tf": "H1"},
                "development", stats,
                note=f"{name}; {'KILL' if exp <= 0 else 'continue'}")
        print(f"{name:<16} {n:>5} {exp:>+8.4f} {win:>6.1%} {pf:>6.2f} {sumr:>+8.1f}  {verdict}")

    print("\nAll runs logged to research/registry.jsonl (development sample).")
    print("Multiplicity: 5 pre-registered windows tested; discount any single 'PASS' accordingly.")


if __name__ == "__main__":
    main()
