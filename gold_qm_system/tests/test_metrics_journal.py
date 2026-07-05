"""Metrics, report and journal tests, driven by the end-to-end QM fixture."""
import numpy as np
import pandas as pd

from gold_qm_system.engine import run_backtest
from gold_qm_system.journal import trades_to_journal, write_journal
from gold_qm_system.metrics import compute_stats
from gold_qm_system.reports import write_report
from gold_qm_system.tests.test_engine import QM_BARS, qm_config, qm_frame


def run_fixture():
    cfg = qm_config()
    res = run_backtest(cfg, qm_frame())
    stats = compute_stats(res.trades, res.equity_curve, res.slippage_log,
                          cfg.account.initial_equity)
    return res, stats


def test_stats_headline_values():
    res, stats = run_fixture()
    assert stats["trades"] == 1
    assert stats["win_rate"] == 1.0
    assert stats["expectancy_r"] > 1.5
    assert stats["profit_factor"] == float("inf")            # no losers
    assert stats["total_return"] > 0
    assert 0.0 <= stats["max_drawdown"] < 1.0
    assert stats["avg_modeled_slippage"] > 0
    assert stats["by_session"]                                # breakdowns exist
    assert stats["by_exit_reason"]["target"]["trades"] == 1


def test_stats_empty_run_is_graceful():
    idx = pd.date_range("2024-01-02", periods=10, freq="1h", tz="UTC")
    eq = pd.Series(np.full(10, 100_000.0), index=idx)
    stats = compute_stats([], eq, [], 100_000.0)
    assert stats["trades"] == 0 and stats["total_return"] == 0.0
    assert stats["max_drawdown"] == 0.0


def test_max_drawdown_and_duration():
    idx = pd.date_range("2024-01-01", periods=5, freq="1D", tz="UTC")
    eq = pd.Series([100.0, 120.0, 90.0, 95.0, 130.0], index=idx)
    stats = compute_stats([], eq, [], 100.0)
    assert stats["max_drawdown"] == 0.25                     # 120 -> 90
    assert stats["max_drawdown_days"] >= 2.0                 # underwater 2 days


def test_report_written_with_pngs(tmp_path):
    res, stats = run_fixture()
    path = write_report(stats, res.equity_curve, tmp_path)
    assert path.exists()
    assert (tmp_path / "equity_curve.png").exists()
    assert (tmp_path / "r_histogram.png").exists()
    text = path.read_text(encoding="utf-8")
    assert "Disclaimer" in text and "By session" in text


def test_journal_fields(tmp_path):
    res, _ = run_fixture()
    df = trades_to_journal(res.trades)
    assert len(df) == 1
    row = df.iloc[0]
    assert row["setup"] == "qm" and row["trigger"] == "pin_bar"
    assert row["binding_method"] == "risk"
    assert row["qml"] == 110.0 and row["tf_setup"] == "H1"
    assert row["good_loss_or_rule_violation"] == ""          # human column
    out = write_journal(res.trades, tmp_path / "journal.csv")
    assert out.exists() and "binding_method" in out.read_text(encoding="utf-8")
