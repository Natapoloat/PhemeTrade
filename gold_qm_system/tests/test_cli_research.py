"""CLI + research-protocol tests: every subcommand runs end-to-end on the QM
fixture; walkforward reports OOS only; live refuses without the risk flag."""
import pandas as pd
import pytest
from typer.testing import CliRunner

from gold_qm_system import research
from gold_qm_system.cli import app
from gold_qm_system.tests.test_engine import QM_BARS, qm_config, qm_frame

runner = CliRunner()


def tiled_frame(reps=20):
    """Tile the QM fixture end-to-end so multiple patterns/trades occur."""
    bars = []
    for r in range(reps):
        off = (r % 3) * 5.0                     # small offsets, no monotonic drift
        bars += [(o + off, h + off, l + off, c + off) for o, h, l, c in QM_BARS]
    return qm_frame(bars, start="2024-01-01 00:00")


@pytest.fixture()
def workspace(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    df = qm_frame()
    df.reset_index().to_csv(data_dir / "XAUUSD_H1.csv", index=False)
    cfg_path = tmp_path / "config.yaml"
    qm_config().to_yaml(cfg_path)
    return tmp_path, data_dir, cfg_path


def test_cli_backtest_writes_report_and_journal(workspace):
    tmp, data_dir, cfg = workspace
    out = tmp / "bt"
    r = runner.invoke(app, ["backtest", "--config", str(cfg), "--data", str(data_dir),
                            "--output", str(out)])
    assert r.exit_code == 0, r.output
    assert (out / "report.md").exists()
    assert (out / "journal.csv").exists()
    assert (out / "equity_curve.png").exists()
    assert "trades" in r.output


def test_cli_backtest_date_slicing(workspace):
    tmp, data_dir, cfg = workspace
    r = runner.invoke(app, ["backtest", "--config", str(cfg), "--data", str(data_dir),
                            "--from", "2024-01-02", "--to", "2024-01-02 12:00",
                            "--output", str(tmp / "bt2")])
    assert r.exit_code == 0, r.output


def test_cli_sensitivity_runs_and_flags_column(workspace):
    tmp, data_dir, cfg = workspace
    out = tmp / "sens"
    r = runner.invoke(app, ["sensitivity", "--config", str(cfg), "--data", str(data_dir),
                            "--perturb", "0.2", "--output", str(out)])
    assert r.exit_code == 0, r.output
    df = pd.read_csv(out / "sensitivity.csv")
    assert "overfit_flag" in df.columns
    assert (df["param"] == "(base)").any()
    # each param appears twice (+/-)
    assert (df["param"] == "qm.qml_atr_mult").sum() == 2


def test_cli_ablation_reports_layer_stack(workspace):
    tmp, data_dir, cfg = workspace
    out = tmp / "abl"
    r = runner.invoke(app, ["ablation", "--config", str(cfg), "--data", str(data_dir),
                            "--output", str(out)])
    assert r.exit_code == 0, r.output
    df = pd.read_csv(out / "ablation.csv")
    layers = df["layer"].tolist()
    assert layers[0].startswith("L1") and any(s.startswith("L4 subset") for s in layers)
    # the full stack (L4) finds the fixture's one QM trade
    l4 = df[df["layer"].str.startswith("L4 +")].iloc[0]
    assert l4["trades"] >= 1


def test_cli_forwardtest_replay_shares_code_path(workspace, tmp_path):
    tmp, data_dir, cfg = workspace
    out = tmp / "ft"
    r = runner.invoke(app, ["forwardtest", "--config", str(cfg),
                            "--feed", str(data_dir / "XAUUSD_H1.csv"),
                            "--speed", "0", "--output", str(out)])
    assert r.exit_code == 0, r.output
    assert (out / "journal.csv").exists()
    div = pd.read_csv(out / "fill_divergence.csv")
    assert {"intended_ref_price", "actual_fill", "adverse_divergence"} <= set(div.columns)
    assert len(div) == 1                       # the fixture's single entry
    assert div["adverse_divergence"].iloc[0] != 0.0


def test_cli_live_refuses_without_risk_flag(workspace):
    _, data_dir, cfg = workspace
    r = runner.invoke(app, ["live", "--config", str(cfg),
                            "--broker", "nonexistent:Adapter",
                            "--feed", "nonexistent:feed"])
    assert r.exit_code == 2
    assert "Refusing" in r.output


def test_walkforward_reports_oos_only():
    cfg = qm_config()
    bars = tiled_frame(reps=20)                # 260 bars, 2 windows of 130
    wf = research.walkforward(cfg, bars, windows=2, oos=0.25,
                              grid={"stops_targets.min_rr": [1.5, 2.0]})
    assert len(wf.windows) == 2
    for w in wf.windows:
        assert "chosen_params" in w and "oos_trades" in w
    # every OOS trade was entered inside an OOS range — never in-sample
    seg = len(bars) // 2
    oos_starts = [bars.index[int(seg * 0.75)], bars.index[seg + int(seg * 0.75)]]
    seg_bounds = [bars.index[seg - 1], bars.index[-1]]
    for t in wf.oos_trades:
        assert any(s <= t.entry_time <= e for s, e in zip(oos_starts, seg_bounds))
    assert "trades" in wf.oos_stats


def test_walkforward_rejects_tiny_segments():
    with pytest.raises(ValueError, match="segments too small"):
        research.walkforward(qm_config(), qm_frame(), windows=2, oos=0.25)
