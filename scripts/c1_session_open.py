"""C1 first run — session-open breakout/fade on gold M15 (DEVELOPMENT ONLY, primary).

Runs the pre-registered 12-config grid (branch x buffer_k x exit_mode) on gold's
deep M15 (dev slice, holdout sealed). Gold is the pre-registered PRIMARY; the kill
line is evaluated here. Secondary symbols (USDJPY/US30/USOIL) + cross-symbol
correlation / effective-N follow once the Max-bars backfill gives them real dev
depth. Every config logged to the registry.

Kill line (pre-registered): dev expR <= 0 after full costs on XAUUSD with zero
added filters -> that branch is killed. No filter-stacking.

Usage:  python scripts/c1_session_open.py
"""
from __future__ import annotations

import itertools

import pandas as pd

from gold_qm_system.config import SystemConfig
from gold_qm_system.data import normalize_ohlcv
from gold_qm_system.engine import run_backtest
from gold_qm_system.engine.session_open import make_c1_factory
from gold_qm_system.metrics import compute_stats
from gold_qm_system.research_gate import development_only, log_run, holdout_cutoff

BRANCHES = ["breakout", "fade"]
BUFFERS = [0.0, 0.25, 0.5]
EXITS = ["session_end", "fixed_2R"]


def main() -> None:
    df = pd.read_csv("market_data_long/XAUUSD_M15.csv")
    bars = development_only(normalize_ohlcv(df, "M15"))
    print(f"gold M15 dev: {len(bars)} bars {bars.index[0].date()}..{bars.index[-1].date()} "
          f"(holdout>={holdout_cutoff().date()})\n")

    cfg = SystemConfig.from_yaml("forwardtest_iter3_config.yaml")
    d = cfg.model_dump()
    d["timeframes"]["entry"] = "M15"
    d["sizing"].update({"min_size": 0.0, "size_step": 0.0, "margin_per_unit": 0.0})
    d["news"]["calendar_csv"] = None
    cfg = SystemConfig.model_validate(d)

    rows = []
    print(f"{'branch':<9}{'buf':>5}{'exit':>13}{'n':>7}{'expR':>9}{'win%':>7}{'PF':>7}{'sumR':>9}")
    print("-" * 66)
    for branch, buf, exit_mode in itertools.product(BRANCHES, BUFFERS, EXITS):
        factory = make_c1_factory(branch, buf, exit_mode)
        res = run_backtest(cfg, bars, strategy_factory=factory)
        st = compute_stats(res.trades, res.equity_curve, res.slippage_log,
                           cfg.account.initial_equity)
        n = st["trades"]; exp = st.get("expectancy_r") or 0.0
        pf = st.get("profit_factor") or 0.0; win = st.get("win_rate") or 0.0
        sumr = sum(t.r_multiple for t in res.trades)
        rows.append({"branch": branch, "buffer_k": buf, "exit_mode": exit_mode,
                     "n": n, "expR": exp, "win": win, "pf": pf, "sumR": sumr})
        log_run("C1-session-open",
                {"branch": branch, "buffer_k": buf, "exit_mode": exit_mode,
                 "market": "XAUUSD", "tf": "M15"},
                "development",
                {"trades": n, "expectancy_r": exp, "win_rate": win,
                 "profit_factor": pf, "sum_r": sumr, "max_dd": st.get("max_drawdown")},
                note="C1 primary grid (gold M15 dev)")
        print(f"{branch:<9}{buf:>5}{exit_mode:>13}{n:>7}{exp:>+9.4f}{win:>7.1%}{pf:>7.2f}{sumr:>+9.1f}")

    print("\n--- kill-line evaluation (pre-registered: dev expR>0 on gold primary, zero filters) ---")
    r = pd.DataFrame(rows)
    for branch in BRANCHES:
        b = r[r.branch == branch]
        best = b.loc[b.expR.idxmax()]
        alive = best.expR > 0
        print(f"  {branch:<9} best expR = {best.expR:+.4f} "
              f"(buf={best.buffer_k}, {best.exit_mode}, n={best.n}) -> "
              f"{'ALIVE (continue to secondary/OOS)' if alive else 'KILL'}")
    print("\nEffective-N: single-symbol run, so ~= raw N (no cross-symbol deflation yet);")
    print("full effective-N + cross-symbol daily-PnL correlation come with the secondary basket.")


if __name__ == "__main__":
    main()
