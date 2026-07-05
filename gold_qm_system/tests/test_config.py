"""Config schema tests: sample YAML loads, defaults match Appendix values,
round-trip is stable, invalid configs are rejected."""
from pathlib import Path

import pytest
from pydantic import ValidationError

from gold_qm_system.config import SystemConfig

REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLE = REPO_ROOT / "sample_config.yaml"


def test_sample_config_loads_with_appendix_defaults():
    cfg = SystemConfig.from_yaml(SAMPLE)
    # Appendix A defaults
    assert cfg.swings.swing_strength == 3
    assert cfg.structure.range_atr_mult == 0.5
    assert cfg.qm.qm_lookback == 120
    assert cfg.qm.qml_atr_mult == 0.10
    assert cfg.qm.fib_entry_low == 0.618
    assert cfg.qm.fib_entry_high == 0.786
    assert cfg.price_action.pin_wick_ratio == 0.66
    assert cfg.price_action.sfp_wick_ratio == 0.5
    assert cfg.stops_targets.stop_atr_mult == 0.25
    assert cfg.stops_targets.min_rr == 2.0
    # Part I §7 defaults
    assert cfg.indicators.atr_period == 21
    assert cfg.sizing.risk_pct == 0.005
    assert cfg.ongoing_risk.portfolio_risk_cap == 0.125
    # Appendix D/G defaults
    assert cfg.news.news_blackout_min == 30
    assert cfg.kill_switches.max_consec_losses == 4
    assert cfg.kill_switches.max_total_dd == 0.15


def test_config_yaml_round_trip(tmp_path):
    cfg = SystemConfig.from_yaml(SAMPLE)
    out = tmp_path / "roundtrip.yaml"
    cfg.to_yaml(out)
    cfg2 = SystemConfig.from_yaml(out)
    assert cfg == cfg2


def test_invalid_fib_order_rejected():
    with pytest.raises(ValidationError):
        SystemConfig.model_validate({"qm": {"fib_entry_low": 0.8, "fib_entry_high": 0.6}})


def test_invalid_timeframe_ordering_rejected():
    with pytest.raises(ValidationError):
        SystemConfig.model_validate({"timeframes": {"directional": "M5", "setup": "H1", "entry": "H4"}})


def test_defaults_construct_without_yaml():
    cfg = SystemConfig()
    assert cfg.symbol == "XAUUSD"
    assert cfg.timeframes.setup == "H1"
