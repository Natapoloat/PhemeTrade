"""Position sizing — Part I 7.2/7.5.

Three independent methods, ALWAYS all computed, final = MIN of the three:
  A. risk-based:       equity * risk_pct   / |entry - stop|
  B. volatility-based: equity * vol_pct    / ATR
  C. margin-based:     equity * margin_pct / margin_per_unit

Edge cases per DECISIONS.md #10: unconfigured margin => non-binding;
below min_size => SKIP (never round up); size_step rounds DOWN only.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from gold_qm_system.config import SizingConfig

BindingMethod = Literal["risk", "volatility", "margin", "skipped"]


@dataclass(frozen=True)
class SizingResult:
    size: float
    binding: BindingMethod
    size_risk: float
    size_vol: float
    size_margin: float          # inf if margin method not configured
    risk_amount: float          # currency at risk at entry (= 1R), 0 if skipped


def compute_size(
    equity: float,
    entry: float,
    stop: float,
    atr_value: float,
    cfg: SizingConfig,
    risk_budget_frac: float | None = None,
) -> SizingResult:
    """Compute the final position size.

    `risk_budget_frac` optionally caps the risk fraction below cfg.risk_pct —
    used by the portfolio-cap trim (Part I 7.4): the NEW trade is trimmed to
    the remaining portfolio risk budget.
    """
    stop_dist = abs(entry - stop)
    if equity <= 0 or stop_dist <= 0 or atr_value <= 0:
        return SizingResult(0.0, "skipped", 0.0, 0.0, math.inf, 0.0)

    risk_frac = cfg.risk_pct if risk_budget_frac is None else min(cfg.risk_pct, risk_budget_frac)
    if risk_frac <= 0:
        return SizingResult(0.0, "skipped", 0.0, 0.0, math.inf, 0.0)

    size_risk = equity * risk_frac / stop_dist
    size_vol = equity * cfg.vol_pct / atr_value
    size_margin = (equity * cfg.margin_pct / cfg.margin_per_unit
                   if cfg.margin_per_unit > 0 else math.inf)

    final = min(size_risk, size_vol, size_margin)
    binding: BindingMethod = ("risk" if final == size_risk
                              else "volatility" if final == size_vol
                              else "margin")

    if cfg.size_step > 0:
        final = math.floor(final / cfg.size_step) * cfg.size_step  # round DOWN only
    if final <= 0 or final < cfg.min_size:
        return SizingResult(0.0, "skipped", size_risk, size_vol, size_margin, 0.0)

    return SizingResult(final, binding, size_risk, size_vol, size_margin,
                        risk_amount=final * stop_dist)


def build_stop_and_target(
    direction: Literal["sell", "buy"],
    entry: float,
    swing_extreme: float,
    atr_value: float,
    stop_atr_mult: float,
    min_rr: float,
    exit_mode: Literal["fixed_rr", "trail_structure"] = "fixed_rr",
) -> tuple[float, float]:
    """Appendix A.7 / J.2: stop beyond the swing extreme with an ATR buffer.
    fixed_rr -> take-profit at min_rr * risk. trail_structure -> no fixed
    target (returns +/-inf; exits come from the trailing stop, Appendix J.2)."""
    buffer = stop_atr_mult * atr_value
    if direction == "sell":
        stop = swing_extreme + buffer
        risk = stop - entry
        target = -math.inf if exit_mode == "trail_structure" else entry - min_rr * risk
    else:
        stop = swing_extreme - buffer
        risk = entry - stop
        target = math.inf if exit_mode == "trail_structure" else entry + min_rr * risk
    return stop, target
