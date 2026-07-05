"""Report generation: equity-curve PNG + Markdown report (Appendix E)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

_DISCLAIMER = (
    "> **Disclaimer:** research/testing software, not financial advice. "
    "A positive backtest does **not** imply live profitability; costs, "
    "slippage and regime change can erase any modeled edge.\n"
)


def _fmt(v: Any) -> str:
    if isinstance(v, float):
        return f"{v:,.4f}" if abs(v) < 100 else f"{v:,.2f}"
    return str(v)


def _table(d: dict[str, Any], keys: list[str]) -> str:
    rows = ["| metric | value |", "|---|---|"]
    rows += [f"| {k} | {_fmt(d.get(k, 'n/a'))} |" for k in keys]
    return "\n".join(rows)


def _group_table(groups: dict[str, dict[str, Any]]) -> str:
    rows = ["| group | trades | expectancy (R) | win rate | profit factor | net pnl |",
            "|---|---|---|---|---|---|"]
    for name, g in groups.items():
        rows.append("| {} | {} | {} | {} | {} | {} |".format(
            name, g.get("trades", 0), _fmt(g.get("expectancy_r", "n/a")),
            _fmt(g.get("win_rate", "n/a")), _fmt(g.get("profit_factor", "n/a")),
            _fmt(g.get("net_pnl", "n/a"))))
    return "\n".join(rows)


def plot_equity(equity: pd.Series, out_png: Path) -> None:
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(equity.index, equity.values, lw=1.2)
    ax.set_title("Mark-to-market equity")
    ax.set_ylabel("Equity")
    ax.grid(alpha=0.3)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(out_png, dpi=130)
    plt.close(fig)


def plot_r_histogram(r_multiples: list[float], out_png: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 4))
    if r_multiples:
        ax.hist(r_multiples, bins=25, edgecolor="black", alpha=0.8)
    ax.set_title("R-multiple distribution")
    ax.set_xlabel("R")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_png, dpi=130)
    plt.close(fig)


def write_report(stats: dict[str, Any], equity: pd.Series, outdir: str | Path,
                 title: str = "Backtest report") -> Path:
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    plot_equity(equity, outdir / "equity_curve.png")
    plot_r_histogram(stats.get("r_multiples", []), outdir / "r_histogram.png")

    headline = ["trades", "expectancy_r", "win_rate", "profit_factor", "net_pnl",
                "total_return", "cagr", "max_drawdown", "max_drawdown_days",
                "calmar_mar", "sharpe", "sortino", "trades_per_month",
                "longest_losing_streak", "avg_modeled_slippage"]

    md = [f"# {title}", "", _DISCLAIMER, "",
          "![equity](equity_curve.png)", "",
          "## Headline metrics", _table(stats, headline), "",
          "![r-dist](r_histogram.png)", "",
          "## By session", _group_table(stats.get("by_session", {})), "",
          "## By trend regime (directional bias at entry)",
          _group_table(stats.get("by_trend_regime", {})), "",
          "## By volatility regime (ATR percentile at entry)",
          _group_table(stats.get("by_vol_regime", {})), "",
          "## By exit reason", _group_table(stats.get("by_exit_reason", {})), ""]
    path = outdir / "report.md"
    path.write_text("\n".join(md), encoding="utf-8")
    return path
