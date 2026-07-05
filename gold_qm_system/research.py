"""Research protocols: walk-forward (B.6), parameter sensitivity (B.7) and
layer ablation (B.8). All of them re-run the ONE backtest engine — no separate
vectorized shortcut that could disagree with live behavior."""
from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Any, Optional

import pandas as pd

from gold_qm_system.calendar import NewsCalendar
from gold_qm_system.config import SystemConfig
from gold_qm_system.engine import run_backtest
from gold_qm_system.execution import TradeRecord
from gold_qm_system.metrics import compute_stats


def override_config(cfg: SystemConfig, path: str, value: Any) -> SystemConfig:
    """Return a new config with dotted `path` (e.g. 'qm.qml_atr_mult') set."""
    d = cfg.model_dump()
    node = d
    keys = path.split(".")
    for k in keys[:-1]:
        node = node[k]
    node[keys[-1]] = value
    return SystemConfig.model_validate(d)


def override_many(cfg: SystemConfig, updates: dict[str, Any]) -> SystemConfig:
    for k, v in updates.items():
        cfg = override_config(cfg, k, v)
    return cfg


# ------------------------------------------------------------ walk-forward

#: compact default optimization grid — deliberately small; a big grid on a
#: layered discretionary system is an overfitting machine (Appendix B.7).
DEFAULT_GRID: dict[str, list[Any]] = {
    "swings.swing_strength": [2, 3, 4],
    "qm.qml_atr_mult": [0.05, 0.10, 0.15],
    "stops_targets.min_rr": [1.5, 2.0, 3.0],
}


@dataclass
class WalkForwardResult:
    windows: list[dict[str, Any]]          # per-window: chosen params, IS/OOS stats
    oos_trades: list[TradeRecord]
    oos_stats: dict[str, Any]              # the ONLY stats to be reported (B.6)


def _score(stats: dict[str, Any], min_trades: int = 5) -> float:
    """In-sample selection score: expectancy, but only with a minimal sample."""
    if stats.get("trades", 0) < min_trades:
        return float("-inf")
    return stats.get("expectancy_r", float("-inf"))


def walkforward(cfg: SystemConfig, bars: pd.DataFrame, windows: int, oos: float,
                grid: Optional[dict[str, list[Any]]] = None,
                calendar: Optional[NewsCalendar] = None) -> WalkForwardResult:
    """Blockwise walk-forward: split bars into `windows` contiguous segments;
    within each, optimize the grid on the first (1-oos) fraction and validate
    the winner on the trailing `oos` fraction. OOS runs are warm-started on
    the IS bars but only trades ENTERED inside the OOS range are counted."""
    if not 0 < oos < 1:
        raise ValueError("oos fraction must be in (0,1)")
    grid = grid if grid is not None else DEFAULT_GRID
    n = len(bars)
    seg = n // windows
    if seg < 50:
        raise ValueError(f"segments too small ({seg} bars) for {windows} windows")

    keys = list(grid.keys())
    combos = list(itertools.product(*(grid[k] for k in keys)))

    all_oos_trades: list[TradeRecord] = []
    oos_curves: list[pd.Series] = []
    window_reports: list[dict[str, Any]] = []

    for w in range(windows):
        lo, hi = w * seg, (w + 1) * seg if w < windows - 1 else n
        is_end = lo + int((hi - lo) * (1 - oos))
        is_bars, full_bars = bars.iloc[lo:is_end], bars.iloc[lo:hi]
        oos_start_time = bars.index[is_end]

        best: tuple[float, dict[str, Any]] | None = None
        for combo in combos:
            params = dict(zip(keys, combo))
            res = run_backtest(override_many(cfg, params), is_bars, calendar)
            st = compute_stats(res.trades, res.equity_curve, res.slippage_log,
                               cfg.account.initial_equity)
            score = _score(st)
            if best is None or score > best[0]:
                best = (score, params)

        chosen = best[1]
        res = run_backtest(override_many(cfg, chosen), full_bars, calendar)
        oos_trades = [t for t in res.trades if t.entry_time >= oos_start_time]
        oos_curve = res.equity_curve.loc[res.equity_curve.index >= oos_start_time]
        all_oos_trades.extend(oos_trades)
        if len(oos_curve):
            oos_curves.append(oos_curve)
        window_reports.append({
            "window": w, "is_score": best[0], "chosen_params": chosen,
            "oos_trades": len(oos_trades),
            "oos_net_pnl": sum(t.net_pnl for t in oos_trades),
        })

    stitched = (pd.concat(oos_curves) if oos_curves
                else pd.Series(dtype=float, index=pd.DatetimeIndex([], tz="UTC")))
    oos_stats = compute_stats(all_oos_trades, stitched, [], cfg.account.initial_equity)
    return WalkForwardResult(window_reports, all_oos_trades, oos_stats)


# ------------------------------------------------------------- sensitivity

#: numeric parameters perturbed by the sensitivity sweep (B.7)
SENSITIVITY_PARAMS = [
    "swings.swing_strength",
    "structure.range_atr_mult",
    "qm.qm_lookback",
    "qm.qml_atr_mult",
    "price_action.pin_wick_ratio",
    "stops_targets.stop_atr_mult",
    "stops_targets.min_rr",
]

_INT_PARAMS = {"swings.swing_strength", "qm.qm_lookback"}


def _get(cfg: SystemConfig, path: str) -> Any:
    node: Any = cfg
    for k in path.split("."):
        node = getattr(node, k)
    return node


def sensitivity(cfg: SystemConfig, bars: pd.DataFrame, perturb: float = 0.2,
                params: Optional[list[str]] = None,
                calendar: Optional[NewsCalendar] = None) -> pd.DataFrame:
    """Perturb each parameter +/- `perturb` (one at a time), re-run, and flag
    overfitting when performance collapses relative to the base run."""
    params = params if params is not None else SENSITIVITY_PARAMS
    rows = []

    base_res = run_backtest(cfg, bars, calendar)
    base = compute_stats(base_res.trades, base_res.equity_curve,
                         base_res.slippage_log, cfg.account.initial_equity)
    rows.append({"param": "(base)", "value": "", "trades": base["trades"],
                 "expectancy_r": base.get("expectancy_r"),
                 "profit_factor": base.get("profit_factor"),
                 "net_pnl": base.get("net_pnl", 0.0), "overfit_flag": ""})

    base_pf = base.get("profit_factor") or 0.0
    for p in params:
        cur = _get(cfg, p)
        for sign in (-1, 1):
            val = cur * (1 + sign * perturb)
            if p in _INT_PARAMS:
                val = round(val)
                if val == cur:
                    val = cur + sign
                val = max(1, val)
                if val == cur:          # clamped back onto the base value
                    rows.append({"param": p, "value": val, "trades": base["trades"],
                                 "expectancy_r": base.get("expectancy_r"),
                                 "profit_factor": base_pf,
                                 "net_pnl": base.get("net_pnl", 0.0),
                                 "overfit_flag": "(= base)"})
                    continue
            res = run_backtest(override_config(cfg, p, val), bars, calendar)
            st = compute_stats(res.trades, res.equity_curve, res.slippage_log,
                               cfg.account.initial_equity)
            pf = st.get("profit_factor") or 0.0
            collapsed = (base_pf >= 1.3 and (pf < 1.0 or pf < 0.5 * base_pf))
            rows.append({"param": p, "value": val, "trades": st["trades"],
                         "expectancy_r": st.get("expectancy_r"),
                         "profit_factor": pf,
                         "net_pnl": st.get("net_pnl", 0.0),
                         "overfit_flag": "COLLAPSED" if collapsed else ""})
    return pd.DataFrame(rows)


# --------------------------------------------------------------- ablation

#: cumulative layer stack per Appendix B.8
ABLATION_STACK: list[tuple[str, dict[str, Any]]] = [
    ("L1 structure-only (MSS)", {"layers.use_qm": False}),
    ("L2 +QM (band touch)", {"layers.use_qm": True, "layers.use_fib_zone": False,
                             "layers.use_price_action": False}),
    ("L3 +Fib zone", {"layers.use_qm": True, "layers.use_fib_zone": True,
                      "layers.use_price_action": False}),
    ("L4 +price action", {"layers.use_qm": True, "layers.use_fib_zone": True,
                          "layers.use_price_action": True}),
]


def ablation(cfg: SystemConfig, bars: pd.DataFrame,
             calendar: Optional[NewsCalendar] = None) -> pd.DataFrame:
    """Marginal contribution of each layer. The SFP booster does not gate
    entries (A.6), so its row splits the full stack's trades by the flag
    instead of re-running."""
    rows = []
    full_trades: list[TradeRecord] = []
    for name, updates in ABLATION_STACK:
        res = run_backtest(override_many(cfg, updates), bars, calendar)
        st = compute_stats(res.trades, res.equity_curve, res.slippage_log,
                           cfg.account.initial_equity)
        rows.append({"layer": name, "trades": st["trades"],
                     "expectancy_r": st.get("expectancy_r"),
                     "win_rate": st.get("win_rate"),
                     "profit_factor": st.get("profit_factor"),
                     "net_pnl": st.get("net_pnl", 0.0),
                     "max_drawdown": st.get("max_drawdown")})
        if name.startswith("L4"):
            full_trades = res.trades

    for flag, label in ((True, "L4 subset: SFP-flagged"),
                        (False, "L4 subset: no SFP")):
        sub = [t for t in full_trades if bool(t.meta.get("sfp")) is flag]
        if sub:
            import numpy as np
            r = np.array([t.r_multiple for t in sub])
            pnl = np.array([t.net_pnl for t in sub])
            gains, losses = pnl[pnl > 0].sum(), -pnl[pnl < 0].sum()
            rows.append({"layer": label, "trades": len(sub),
                         "expectancy_r": float(r.mean()),
                         "win_rate": float((pnl > 0).mean()),
                         "profit_factor": float(gains / losses) if losses > 0 else float("inf"),
                         "net_pnl": float(pnl.sum()), "max_drawdown": None})
        else:
            rows.append({"layer": label, "trades": 0, "expectancy_r": None,
                         "win_rate": None, "profit_factor": None,
                         "net_pnl": 0.0, "max_drawdown": None})
    return pd.DataFrame(rows)
