"""Risk-module tests: final_size == MIN(risk, vol, margin) across cases;
portfolio cap trims the new trade correctly; ongoing ceilings trim right."""
import math

import pytest

from gold_qm_system.config import OngoingRiskConfig, SizingConfig
from gold_qm_system.risk import (
    OpenPositionState,
    build_stop_and_target,
    compute_size,
    ongoing_trim_size,
    portfolio_open_risk_fraction,
    remaining_risk_budget_fraction,
)

EQ = 100_000.0


def cfg(**kw):
    base = dict(risk_pct=0.01, vol_pct=0.005, margin_pct=0.05,
                margin_per_unit=0.0, min_size=0.0, size_step=0.0)
    base.update(kw)
    return SizingConfig(**base)


# ------------------------------------------------------- MIN-of-three sizing

def test_risk_method_binds_when_stop_is_wide():
    # risk: 1000/20 = 50 ; vol: 500/5 = 100 ; margin off
    r = compute_size(EQ, entry=2000.0, stop=1980.0, atr_value=5.0, cfg=cfg())
    assert r.binding == "risk" and r.size == 50
    assert r.size == min(r.size_risk, r.size_vol, r.size_margin)
    assert r.risk_amount == pytest.approx(50 * 20)          # = equity * risk_pct


def test_volatility_method_binds_when_atr_is_large():
    # risk: 1000/5 = 200 ; vol: 500/25 = 20
    r = compute_size(EQ, entry=2000.0, stop=1995.0, atr_value=25.0, cfg=cfg())
    assert r.binding == "volatility" and r.size == 20
    assert r.size == min(r.size_risk, r.size_vol, r.size_margin)


def test_margin_method_binds_when_configured_tightly():
    # margin: 5000/500 = 10 ; risk: 200 ; vol: 100
    r = compute_size(EQ, entry=2000.0, stop=1995.0, atr_value=5.0,
                     cfg=cfg(margin_per_unit=500.0))
    assert r.binding == "margin" and r.size == 10


def test_unconfigured_margin_is_nonbinding():
    r = compute_size(EQ, entry=2000.0, stop=1995.0, atr_value=5.0, cfg=cfg())
    assert math.isinf(r.size_margin)


@pytest.mark.parametrize("entry,stop,atr,margin", [
    (2000, 1980, 5, 0), (2000, 1995, 25, 0), (2000, 1995, 5, 500),
    (2650, 2641.5, 12.3, 300), (1900, 1911, 8, 0),
])
def test_final_always_equals_min_of_three(entry, stop, atr, margin):
    r = compute_size(EQ, entry, stop, atr, cfg(margin_per_unit=margin))
    assert r.size == pytest.approx(min(r.size_risk, r.size_vol, r.size_margin))


def test_min_size_skips_never_rounds_up():
    r = compute_size(EQ, entry=2000.0, stop=1980.0, atr_value=5.0,
                     cfg=cfg(min_size=60.0))                 # computed 50 < 60
    assert r.binding == "skipped" and r.size == 0.0 and r.risk_amount == 0.0


def test_size_step_rounds_down_only():
    r = compute_size(EQ, entry=2000.0, stop=1987.0, atr_value=5.0, cfg=cfg())
    assert r.size == pytest.approx(1000 / 13)                # unrounded
    r2 = compute_size(EQ, entry=2000.0, stop=1987.0, atr_value=5.0,
                      cfg=cfg(size_step=10.0))
    assert r2.size == 70.0                                   # 76.9 -> 70, never 80


def test_degenerate_inputs_skip():
    assert compute_size(EQ, 2000, 2000, 5.0, cfg()).binding == "skipped"   # zero stop dist
    assert compute_size(0.0, 2000, 1990, 5.0, cfg()).binding == "skipped"  # no equity


# ------------------------------------------------------------ stops & targets

def test_stop_and_target_sell():
    stop, target = build_stop_and_target("sell", entry=110.0, swing_extreme=115.0,
                                         atr_value=2.0, stop_atr_mult=0.25, min_rr=2.0)
    assert stop == 115.5                                     # head + 0.25*ATR
    assert target == 110.0 - 2.0 * 5.5                       # entry - 2R


def test_stop_and_target_buy():
    stop, target = build_stop_and_target("buy", entry=90.0, swing_extreme=85.0,
                                         atr_value=2.0, stop_atr_mult=0.25, min_rr=2.0)
    assert stop == 84.5
    assert target == 90.0 + 2.0 * 5.5


def test_trail_structure_mode_has_no_fixed_target():
    """Appendix J.2: trail_structure returns an infinite target (exits come
    from the trailing stop), while the stop is identical to fixed mode."""
    import math
    s_stop, s_tgt = build_stop_and_target("sell", 110.0, 115.0, 2.0, 0.25, 2.0,
                                          exit_mode="trail_structure")
    assert s_stop == 115.5 and s_tgt == -math.inf
    b_stop, b_tgt = build_stop_and_target("buy", 90.0, 85.0, 2.0, 0.25, 2.0,
                                          exit_mode="trail_structure")
    assert b_stop == 84.5 and b_tgt == math.inf


# ------------------------------------------------- ongoing ceilings (7.3)

def test_ongoing_risk_ceiling_trims_to_exact_ceiling():
    ocfg = OngoingRiskConfig(ongoing_risk_ceiling=0.025, ongoing_vol_ceiling=1.0,
                             portfolio_risk_cap=0.125)
    pos = OpenPositionState("buy", size=100.0, stop=1950.0)
    # close 2000 -> dist 50 -> open risk 5000 = 5% > 2.5%
    trim = ongoing_trim_size(pos, close=2000.0, atr_value=1.0, equity=EQ, cfg=ocfg)
    assert trim == pytest.approx(50.0)                       # 100 -> 50 => exactly 2.5%
    kept = OpenPositionState("buy", size=100.0 - trim, stop=1950.0)
    assert (kept.size * 50.0) / EQ == pytest.approx(0.025)


def test_ongoing_vol_ceiling_trims():
    ocfg = OngoingRiskConfig(ongoing_risk_ceiling=1.0, ongoing_vol_ceiling=0.008,
                             portfolio_risk_cap=0.125)
    pos = OpenPositionState("buy", size=100.0, stop=1990.0)
    # ATR 10 -> exposure 1000 = 1% > 0.8% -> allowed 80
    trim = ongoing_trim_size(pos, close=2000.0, atr_value=10.0, equity=EQ, cfg=ocfg)
    assert trim == pytest.approx(20.0)


def test_no_trim_when_within_ceilings_or_stop_beyond_breakeven():
    ocfg = OngoingRiskConfig()
    ok = OpenPositionState("buy", size=10.0, stop=1990.0)
    assert ongoing_trim_size(ok, 2000.0, 5.0, EQ, ocfg) == 0.0
    locked = OpenPositionState("buy", size=10.0, stop=2010.0)  # stop in profit
    assert ongoing_trim_size(locked, 2000.0, 5.0, EQ, ocfg) == 0.0


# ------------------------------------------------- portfolio cap (7.4)

def test_portfolio_cap_trims_new_trade_to_remaining_budget():
    ocfg = OngoingRiskConfig(portfolio_risk_cap=0.125)
    positions = [OpenPositionState("buy", size=100.0, stop=1900.0),   # risk 10000 = 10%
                 OpenPositionState("sell", size=50.0, stop=2010.0)]   # risk 500  = 0.5%
    closes = [2000.0, 2000.0]
    used = portfolio_open_risk_fraction(positions, closes, EQ)
    assert used == pytest.approx(0.105)
    budget = remaining_risk_budget_fraction(positions, closes, EQ, ocfg)
    assert budget == pytest.approx(0.02)

    # a new trade wanting 1% risk fits untouched; the sizing budget only caps
    scfg = cfg(risk_pct=0.01)
    r = compute_size(EQ, 2000.0, 1980.0, 5.0, scfg, risk_budget_frac=budget)
    assert r.risk_amount == pytest.approx(EQ * 0.01)

    # with only 0.4% budget left, the new trade is TRIMMED to 0.4%
    r2 = compute_size(EQ, 2000.0, 1980.0, 5.0, scfg, risk_budget_frac=0.004)
    assert r2.risk_amount == pytest.approx(EQ * 0.004)
    assert r2.size == pytest.approx(400 / 20)

    # zero budget -> skipped
    r3 = compute_size(EQ, 2000.0, 1980.0, 5.0, scfg, risk_budget_frac=0.0)
    assert r3.binding == "skipped"
