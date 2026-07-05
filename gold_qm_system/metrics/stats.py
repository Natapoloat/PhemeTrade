"""Performance metrics (Appendix E) + per-session / per-regime breakdowns
(Appendix F / B.9). Win rate alone is meaningless — everything below is
reported together, and acceptance criteria live in VALIDATION.md."""
from __future__ import annotations

from typing import Any, Optional

import numpy as np
import pandas as pd

from gold_qm_system.execution import TradeRecord

# exits that represent a completed trade thesis (trims are risk management)
_FULL_EXITS = {"stop", "target", "choch_exit", "flat_friday", "kill_switch", "end_of_data"}


def _annualization_factor(equity: pd.Series) -> float:
    if len(equity) < 3:
        return 1.0
    spacing = pd.Series(equity.index).diff().dropna().median()
    periods_per_year = pd.Timedelta(days=365) / spacing
    return float(np.sqrt(periods_per_year))


def _max_drawdown(equity: pd.Series) -> tuple[float, float]:
    """Return (max drawdown fraction, longest drawdown duration in days)."""
    if len(equity) == 0:
        return 0.0, 0.0
    peak = equity.cummax()
    dd = 1.0 - equity / peak
    max_dd = float(dd.max())
    underwater = dd > 0
    longest = pd.Timedelta(0)
    start: Optional[pd.Timestamp] = None
    for t, uw in underwater.items():
        if uw and start is None:
            start = t
        elif not uw and start is not None:
            longest = max(longest, t - start)
            start = None
    if start is not None:
        longest = max(longest, equity.index[-1] - start)
    return max_dd, longest.total_seconds() / 86400.0


def _vol_bucket(pctile: Any) -> str:
    if pctile is None or (isinstance(pctile, float) and np.isnan(pctile)):
        return "unknown"
    return "low_vol" if pctile < 0.33 else "high_vol" if pctile > 0.66 else "mid_vol"


def _group_stats(trades: list[TradeRecord]) -> dict[str, Any]:
    if not trades:
        return {"trades": 0}
    r = np.array([t.r_multiple for t in trades])
    pnl = np.array([t.net_pnl for t in trades])
    gains, losses = pnl[pnl > 0].sum(), -pnl[pnl < 0].sum()
    return {
        "trades": len(trades),
        "expectancy_r": float(r.mean()),
        "win_rate": float((pnl > 0).mean()),
        "profit_factor": float(gains / losses) if losses > 0 else float("inf"),
        "net_pnl": float(pnl.sum()),
    }


def compute_stats(trades: list[TradeRecord], equity: pd.Series,
                  slippage_log: list[dict], initial_equity: float) -> dict[str, Any]:
    full = [t for t in trades if t.exit_reason in _FULL_EXITS]
    stats: dict[str, Any] = {"initial_equity": initial_equity}

    # ---- headline
    stats.update(_group_stats(full))
    stats["all_exits_count"] = len(trades)
    stats["total_return"] = (float(equity.iloc[-1] / initial_equity - 1.0)
                             if len(equity) else 0.0)

    # ---- risk-adjusted
    max_dd, dd_days = _max_drawdown(equity)
    stats["max_drawdown"] = max_dd
    stats["max_drawdown_days"] = dd_days
    if len(equity) > 2:
        years = max((equity.index[-1] - equity.index[0]).total_seconds() / (365 * 86400), 1e-9)
        cagr = (equity.iloc[-1] / initial_equity) ** (1 / years) - 1.0
        stats["cagr"] = float(cagr)
        stats["calmar_mar"] = float(cagr / max_dd) if max_dd > 0 else float("inf")
        rets = equity.pct_change().dropna()
        ann = _annualization_factor(equity)
        stats["sharpe"] = float(rets.mean() / rets.std() * ann) if rets.std() > 0 else 0.0
        downside = rets[rets < 0]
        stats["sortino"] = (float(rets.mean() / downside.std() * ann)
                            if len(downside) > 1 and downside.std() > 0 else float("inf"))
        stats["trades_per_month"] = len(full) / max(years * 12, 1e-9)

    # ---- R distribution & streaks
    r_mults = [t.r_multiple for t in full]
    stats["r_multiples"] = r_mults
    streak = longest = 0
    for t in full:
        streak = streak + 1 if t.net_pnl < 0 else 0
        longest = max(longest, streak)
    stats["longest_losing_streak"] = longest

    # ---- slippage
    slips = [e["modeled_slippage"] for e in slippage_log]
    stats["avg_modeled_slippage"] = float(np.mean(slips)) if slips else 0.0

    # ---- per-session / per-regime (Appendix F, B.9)
    def by(key_fn):
        groups: dict[str, list[TradeRecord]] = {}
        for t in full:
            groups.setdefault(key_fn(t), []).append(t)
        return {k: _group_stats(v) for k, v in sorted(groups.items())}

    stats["by_session"] = by(lambda t: str(t.meta.get("session", "unknown")))
    stats["by_trend_regime"] = by(lambda t: str(t.meta.get("bias_directional", "unknown")))
    stats["by_vol_regime"] = by(lambda t: _vol_bucket(t.meta.get("atr_pctile_entry")))
    stats["by_exit_reason"] = by(lambda t: t.exit_reason)
    return stats
