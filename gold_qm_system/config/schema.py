"""Configuration schema.

Every tunable threshold from Gold_Trading_Strategy.md Part II (Appendices A-G)
lives here, loaded from YAML. Nothing in the signal/risk/execution code may
hard-code a strategy threshold.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel, Field, model_validator

Timeframe = Literal["M1", "M5", "M15", "H1", "H4", "D1"]

TIMEFRAME_MINUTES: dict[str, int] = {
    "M1": 1,
    "M5": 5,
    "M15": 15,
    "H1": 60,
    "H4": 240,
    "D1": 1440,
}


class SwingConfig(BaseModel):
    """Appendix A.1 — fractal swing detection (repaint-safe)."""

    swing_strength: int = Field(3, ge=1, description="L = R bars each side; swing emits at i+R")


class StructureConfig(BaseModel):
    """Appendix A.2 — market structure state machine."""

    range_atr_mult: float = Field(0.5, ge=0.0, description="SH/SL within this * ATR => Ranging")


class QMConfig(BaseModel):
    """Appendix A.3/A.4 — Quasimodo pattern + Fib entry zone."""

    qm_lookback: int = Field(120, ge=10, description="max bars for a valid 2->5 sequence")
    qml_atr_mult: float = Field(0.10, ge=0.0, description="qml_tol = qml_atr_mult * ATR")
    break_frac: float = Field(0.0, ge=0.0, description="required fractional break of pt2/pt3")
    fib_veto: bool = Field(
        True,
        description="True: discard patterns whose Fib window misses the QML band "
                    "(DECISIONS #6); False: keep them, zone = QML band, Fib logged "
                    "as a confluence flag (DECISIONS #29)",
    )
    fib_entry_low: float = Field(0.618, gt=0.0, lt=1.0)
    fib_entry_high: float = Field(0.786, gt=0.0, lt=1.0)

    @model_validator(mode="after")
    def _fib_order(self) -> "QMConfig":
        if self.fib_entry_low >= self.fib_entry_high:
            raise ValueError("fib_entry_low must be < fib_entry_high")
        return self


class PriceActionConfig(BaseModel):
    """Appendix A.5/A.6 — price-action triggers and SFP booster."""

    triggers: list[Literal["pin_bar", "engulfing", "inside_bar_breakout"]] = Field(
        default_factory=lambda: ["pin_bar", "engulfing", "inside_bar_breakout"],
        min_length=1, description="enabled A.5 entry triggers (DECISIONS #30)")
    pin_wick_ratio: float = Field(0.66, gt=0.0, lt=1.0)
    sfp_wick_ratio: float = Field(0.5, gt=0.0, lt=1.0)
    compression_bars: int = Field(4, ge=2, description="min consecutive contracting-range bars for compression")
    compression_shrink: float = Field(0.8, gt=0.0, lt=1.0, description="each bar range <= shrink * prior range")


class StopsTargetsConfig(BaseModel):
    """Appendix A.7 (stops/targets) + Appendix J (exit-geometry iteration 2)."""

    stop_atr_mult: float = Field(0.25, ge=0.0, description="stop buffer = stop_atr_mult * ATR beyond swing extreme")
    min_rr: float = Field(2.0, gt=0.0, description="fixed-mode take-profit at min_rr * risk (Appendix A.7 / J.2)")
    use_runner: bool = Field(False, description="optional runner to T2 (next opposing zone)")
    runner_fraction: float = Field(0.5, ge=0.0, le=1.0)
    # Appendix J.2 — configurable exit mechanics
    exit_mode: Literal["fixed_rr", "trail_structure"] = Field(
        "fixed_rr", description="J.2: fixed take-profit vs structural trailing stop (no target)")
    be_trigger_r: float = Field(
        0.0, ge=0.0,
        description="J.2: move stop to entry once +be_trigger_r*R reached (0 = off)")
    use_choch_exit: bool = Field(
        True, description="J.2: counter-CHoCH force-closes the position (Part I 8.2); "
                          "False lets the trail/target run")


class IndicatorConfig(BaseModel):
    atr_period: int = Field(21, ge=2, description="EMA-form ATR per Part I 7.2")
    rsi_period: int = Field(14, ge=2)


class SizingConfig(BaseModel):
    """Part I 7.2/7.5 — three-method sizing, final = MIN of the three."""

    risk_pct: float = Field(0.005, gt=0.0, le=0.02, description="fraction of equity risked to stop")
    vol_pct: float = Field(0.005, gt=0.0, le=0.02, description="fraction of equity per ATR unit")
    margin_pct: float = Field(0.05, gt=0.0, le=1.0, description="max margin fraction per position")
    margin_per_unit: float = Field(
        0.0,
        ge=0.0,
        description="margin required per 1 unit (e.g. 1 oz) of XAUUSD; 0 => margin method not binding",
    )
    min_size: float = Field(0.0, ge=0.0, description="broker minimum size; below this, skip trade")
    size_step: float = Field(0.0, ge=0.0, description="round size down to this step (0 = no rounding)")


class OngoingRiskConfig(BaseModel):
    """Part I 7.3/7.4 — in-trade ceilings and portfolio cap."""

    ongoing_risk_ceiling: float = Field(0.025, gt=0.0, description="trim when open risk exceeds this fraction of equity")
    ongoing_vol_ceiling: float = Field(0.008, gt=0.0, description="trim when position ATR exposure exceeds this")
    portfolio_risk_cap: float = Field(0.125, gt=0.0, description="max summed open risk across positions")


class SessionConfig(BaseModel):
    """Appendix F — session windows in UTC hours [start, end)."""

    asian: tuple[int, int] = (0, 7)
    london: tuple[int, int] = (7, 16)
    newyork: tuple[int, int] = (13, 21)
    overlap: tuple[int, int] = (13, 16)
    allowed_sessions: list[str] = Field(
        default_factory=lambda: ["london", "newyork"],
        description="sessions in which new entries are allowed",
    )


class RegimeConfig(BaseModel):
    """Appendix F — volatility regime filter."""

    atr_pctile_window: int = Field(200, ge=20)
    atr_pctile_min: float = Field(0.0, ge=0.0, le=1.0)
    atr_pctile_max: float = Field(1.0, ge=0.0, le=1.0)


class CostConfig(BaseModel):
    """Appendix D — gold-specific execution cost model."""

    # session-dependent spread (price units, e.g. USD per oz for XAUUSD)
    spread_asian: float = Field(0.45, ge=0.0)
    spread_london: float = Field(0.30, ge=0.0)
    spread_newyork: float = Field(0.30, ge=0.0)
    spread_overlap: float = Field(0.25, ge=0.0)
    spread_news_extra: float = Field(0.50, ge=0.0, description="added inside news window")
    base_slippage: float = Field(0.05, ge=0.0, description="price units per fill")
    stop_slippage_extra: float = Field(0.15, ge=0.0, description="extra slippage on stop fills")
    news_slippage_extra: float = Field(0.30, ge=0.0, description="extra slippage inside news window")
    commission_per_unit: float = Field(0.0, ge=0.0, description="per unit per side")
    swap_long_per_unit_day: float = Field(0.0, description="overnight swap, long (can be negative)")
    swap_short_per_unit_day: float = Field(0.0, description="overnight swap, short")
    swap_triple_weekday: int = Field(2, ge=0, le=6, description="0=Mon..6=Sun; day with 3x swap (default Wed)")
    flat_by_friday: bool = Field(False, description="close all positions before weekend")


class NewsConfig(BaseModel):
    """Appendix D — news blackout."""

    news_blackout_min: int = Field(30, ge=0, description="minutes before/after high-impact events")
    calendar_csv: Optional[str] = Field(None, description="path to economic calendar CSV")
    min_impact: Literal["low", "medium", "high"] = "high"


class KillSwitchConfig(BaseModel):
    """Appendix G — circuit breakers."""

    daily_loss_r: float = Field(2.0, gt=0.0, description="halt new entries after this many R lost in a day")
    daily_loss_pct: float = Field(0.03, gt=0.0, description="halt after this fraction of equity lost in a day")
    max_consec_losses: int = Field(4, ge=1)
    consec_pause_days: int = Field(5, ge=1, description="pause duration simulating manual review; auto-resumes after")
    spread_cap: float = Field(1.5, gt=0.0, description="skip entries when live spread exceeds this (price units)")
    vol_cap_atr_mult: float = Field(3.0, gt=0.0, description="skip entries when bar true range > mult * ATR")
    max_total_dd: float = Field(0.15, gt=0.0, description="hard stop the system at this peak-to-trough drawdown")


class TimeframesConfig(BaseModel):
    """Part I 2.3 — multi-timeframe protocol."""

    directional: Timeframe = "H4"
    setup: Timeframe = "H1"
    entry: Timeframe = "M5"

    @model_validator(mode="after")
    def _ordering(self) -> "TimeframesConfig":
        d = TIMEFRAME_MINUTES
        if not (d[self.entry] <= d[self.setup] <= d[self.directional]):
            raise ValueError("require entry TF <= setup TF <= directional TF")
        return self


class StrategyLayersConfig(BaseModel):
    """Which layers are active — used by the ablation study (Appendix B.8)."""

    use_structure_bias: bool = True
    use_qm: bool = True
    use_fib_zone: bool = True
    use_price_action: bool = True
    use_sfp_booster: bool = True
    require_htf_bias_alignment: bool = True
    allow_countertrend_on_mss: bool = True


class AccountConfig(BaseModel):
    initial_equity: float = Field(100_000.0, gt=0.0)
    currency: str = "USD"


class SystemConfig(BaseModel):
    """Root config — mirrors sample_config.yaml."""

    symbol: str = "XAUUSD"
    account: AccountConfig = AccountConfig()
    timeframes: TimeframesConfig = TimeframesConfig()
    swings: SwingConfig = SwingConfig()
    structure: StructureConfig = StructureConfig()
    qm: QMConfig = QMConfig()
    price_action: PriceActionConfig = PriceActionConfig()
    stops_targets: StopsTargetsConfig = StopsTargetsConfig()
    indicators: IndicatorConfig = IndicatorConfig()
    sizing: SizingConfig = SizingConfig()
    ongoing_risk: OngoingRiskConfig = OngoingRiskConfig()
    sessions: SessionConfig = SessionConfig()
    regime: RegimeConfig = RegimeConfig()
    costs: CostConfig = CostConfig()
    news: NewsConfig = NewsConfig()
    kill_switches: KillSwitchConfig = KillSwitchConfig()
    layers: StrategyLayersConfig = StrategyLayersConfig()

    @classmethod
    def from_yaml(cls, path: str | Path) -> "SystemConfig":
        with open(path, "r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        return cls.model_validate(raw)

    def to_yaml(self, path: str | Path) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            yaml.safe_dump(self.model_dump(mode="json"), fh, sort_keys=False)
