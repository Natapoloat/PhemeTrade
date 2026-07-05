"""Ongoing (in-trade) risk management and portfolio risk cap.

Part I 7.3: right-sizing, not scaling out — when a position's open risk or
ATR exposure exceeds its ceiling, trim exactly enough size to return to the
ceiling (DECISIONS.md #11).
Part I 7.4: total open risk across positions is capped; a new trade is trimmed
to the REMAINING budget (and skipped if the trimmed size is too small).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from gold_qm_system.config import OngoingRiskConfig


@dataclass(frozen=True)
class OpenPositionState:
    """Minimal view of an open position the risk manager needs."""
    direction: Literal["sell", "buy"]
    size: float
    stop: float


def open_risk_amount(pos: OpenPositionState, close: float) -> float:
    """Currency lost if price goes straight to the stop from `close` (>= 0).
    A stop beyond breakeven in profit direction => zero open risk."""
    dist = (close - pos.stop) if pos.direction == "buy" else (pos.stop - close)
    return pos.size * max(0.0, dist)


def open_risk_fraction(pos: OpenPositionState, close: float, equity: float) -> float:
    return open_risk_amount(pos, close) / equity if equity > 0 else 0.0


def vol_exposure_fraction(pos: OpenPositionState, atr_value: float, equity: float) -> float:
    return pos.size * atr_value / equity if equity > 0 else 0.0


def ongoing_trim_size(
    pos: OpenPositionState,
    close: float,
    atr_value: float,
    equity: float,
    cfg: OngoingRiskConfig,
) -> float:
    """Size to TRIM (0 if within both ceilings). Takes the larger of the two
    trims (most conservative) so both ceilings hold afterwards."""
    if pos.size <= 0 or equity <= 0:
        return 0.0

    trims: list[float] = []

    risk_frac = open_risk_fraction(pos, close, equity)
    if risk_frac > cfg.ongoing_risk_ceiling:
        dist = (close - pos.stop) if pos.direction == "buy" else (pos.stop - close)
        allowed = cfg.ongoing_risk_ceiling * equity / dist
        trims.append(pos.size - allowed)

    vol_frac = vol_exposure_fraction(pos, atr_value, equity)
    if atr_value > 0 and vol_frac > cfg.ongoing_vol_ceiling:
        allowed = cfg.ongoing_vol_ceiling * equity / atr_value
        trims.append(pos.size - allowed)

    return max(trims) if trims else 0.0


def portfolio_open_risk_fraction(
    positions: list[OpenPositionState], closes: list[float], equity: float
) -> float:
    if equity <= 0:
        return 0.0
    return sum(open_risk_amount(p, c) for p, c in zip(positions, closes)) / equity


def remaining_risk_budget_fraction(
    positions: list[OpenPositionState], closes: list[float], equity: float,
    cfg: OngoingRiskConfig,
) -> float:
    """Risk fraction still available for a NEW trade under the portfolio cap
    (Part I 7.4). The new trade's sizing is capped to this (>= 0)."""
    used = portfolio_open_risk_fraction(positions, closes, equity)
    return max(0.0, cfg.portfolio_risk_cap - used)
