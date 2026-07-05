"""gold-qm CLI — backtest | walkforward | sensitivity | ablation | forwardtest | live.

Research/testing software only. Not financial advice. A positive backtest does
NOT imply live profitability.
"""
from __future__ import annotations

import importlib
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
import typer
from rich.console import Console
from rich.table import Table

from gold_qm_system.config import SystemConfig
from gold_qm_system.data import load_data_dir
from gold_qm_system.engine import CSVReplayFeed, run_backtest, run_feed
from gold_qm_system.execution import BrokerAdapter
from gold_qm_system.journal import write_journal
from gold_qm_system.metrics import compute_stats
from gold_qm_system.reports import write_report
from gold_qm_system import research

app = typer.Typer(add_completion=False, no_args_is_help=True,
                  help=__doc__, rich_markup_mode="markdown")
console = Console()

_HEADLINE = ["trades", "expectancy_r", "win_rate", "profit_factor", "net_pnl",
             "total_return", "max_drawdown", "sharpe", "calmar_mar",
             "trades_per_month", "longest_losing_streak"]


def _load(config: Path, data: Path, from_date: Optional[str], to_date: Optional[str]
          ) -> tuple[SystemConfig, pd.DataFrame]:
    cfg = SystemConfig.from_yaml(config)
    frames = load_data_dir(data, cfg.symbol, [cfg.timeframes.entry])
    bars = frames[cfg.timeframes.entry]
    if from_date:
        bars = bars.loc[pd.Timestamp(from_date, tz="UTC"):]
    if to_date:
        bars = bars.loc[:pd.Timestamp(to_date, tz="UTC")]
    if bars.empty:
        raise typer.BadParameter("no bars in the selected date range")
    return cfg, bars


def _outdir(base: Optional[Path], kind: str) -> Path:
    d = base or Path("output") / f"{kind}_{datetime.utcnow():%Y%m%d_%H%M%S}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _print_stats(stats: dict, title: str) -> None:
    t = Table(title=title)
    t.add_column("metric")
    t.add_column("value", justify="right")
    for k in _HEADLINE:
        v = stats.get(k)
        t.add_row(k, f"{v:,.4f}" if isinstance(v, float) else str(v))
    console.print(t)


def _print_df(df: pd.DataFrame, title: str) -> None:
    t = Table(title=title)
    for col in df.columns:
        t.add_column(str(col))
    for _, row in df.iterrows():
        t.add_row(*(f"{v:,.4f}" if isinstance(v, float) else str(v) for v in row))
    console.print(t)


@app.command()
def backtest(config: Path = typer.Option(..., help="YAML config"),
             data: Path = typer.Option(..., help="data dir with <SYMBOL>_<TF>.csv/parquet"),
             from_date: Optional[str] = typer.Option(None, "--from"),
             to_date: Optional[str] = typer.Option(None, "--to"),
             output: Optional[Path] = typer.Option(None, help="report directory")):
    """Historical backtest with full costs; writes report + journal."""
    cfg, bars = _load(config, data, from_date, to_date)
    res = run_backtest(cfg, bars)
    stats = compute_stats(res.trades, res.equity_curve, res.slippage_log,
                          cfg.account.initial_equity)
    out = _outdir(output, "backtest")
    write_report(stats, res.equity_curve, out)
    write_journal(res.trades, out / "journal.csv")
    _print_stats(stats, f"Backtest {bars.index[0]:%Y-%m-%d} → {bars.index[-1]:%Y-%m-%d}")
    if res.halted:
        console.print("[red bold]RUN HALTED by equity-floor kill switch[/]")
    console.print(f"report: {out / 'report.md'}")


@app.command()
def walkforward(config: Path = typer.Option(...),
                data: Path = typer.Option(...),
                windows: int = typer.Option(4, min=1),
                oos: float = typer.Option(0.25, min=0.05, max=0.95,
                                          help="out-of-sample fraction per window"),
                from_date: Optional[str] = typer.Option(None, "--from"),
                to_date: Optional[str] = typer.Option(None, "--to"),
                output: Optional[Path] = typer.Option(None)):
    """Rolling optimize-in-sample / validate-out-of-sample. Reports OOS ONLY (B.6)."""
    cfg, bars = _load(config, data, from_date, to_date)
    wf = research.walkforward(cfg, bars, windows, oos)
    out = _outdir(output, "walkforward")
    pd.DataFrame(wf.windows).to_csv(out / "windows.csv", index=False)
    write_journal(wf.oos_trades, out / "oos_journal.csv")
    _print_df(pd.DataFrame(wf.windows).astype(str), "Per-window selection (IS metrics NOT for reporting)")
    _print_stats(wf.oos_stats, "OUT-OF-SAMPLE stats (the only reportable numbers)")
    console.print(f"outputs: {out}")


@app.command()
def sensitivity(config: Path = typer.Option(...),
                data: Path = typer.Option(...),
                perturb: float = typer.Option(0.2, min=0.01, max=0.9),
                from_date: Optional[str] = typer.Option(None, "--from"),
                to_date: Optional[str] = typer.Option(None, "--to"),
                output: Optional[Path] = typer.Option(None)):
    """±perturb parameter sweep; flags collapsed (overfit) parameters (B.7)."""
    cfg, bars = _load(config, data, from_date, to_date)
    df = research.sensitivity(cfg, bars, perturb)
    out = _outdir(output, "sensitivity")
    df.to_csv(out / "sensitivity.csv", index=False)
    _print_df(df, f"Sensitivity ±{perturb:.0%}")
    if (df["overfit_flag"] == "COLLAPSED").any():
        console.print("[red bold]WARNING: performance collapses under perturbation — likely overfit.[/]")
    console.print(f"outputs: {out}")


@app.command()
def ablation(config: Path = typer.Option(...),
             data: Path = typer.Option(...),
             from_date: Optional[str] = typer.Option(None, "--from"),
             to_date: Optional[str] = typer.Option(None, "--to"),
             output: Optional[Path] = typer.Option(None)):
    """Marginal contribution of each layer: structure→+QM→+Fib→+PA→SFP split (B.8)."""
    cfg, bars = _load(config, data, from_date, to_date)
    df = research.ablation(cfg, bars)
    out = _outdir(output, "ablation")
    df.to_csv(out / "ablation.csv", index=False)
    _print_df(df, "Layer ablation")
    console.print("[yellow]Watch trade counts: a layer that only shrinks the sample "
                  "proves nothing (Appendix I.2).[/]")
    console.print(f"outputs: {out}")


@app.command()
def forwardtest(config: Path = typer.Option(...),
                feed: str = typer.Option(..., help="CSV path to replay, or dotted "
                                         "'module:factory' returning a BarFeed"),
                speed: float = typer.Option(0.0, help="0 = as fast as possible; "
                                            "1 = real time (CSV replay only)"),
                output: Optional[Path] = typer.Option(None)):
    """Paper trading on a streaming feed — the EXACT same code path as live.
    Logs intended vs actual fills and slippage divergence (Appendix C)."""
    cfg = SystemConfig.from_yaml(config)
    if ":" in feed and not Path(feed).exists():
        mod, factory = feed.split(":", 1)
        bar_feed = getattr(importlib.import_module(mod), factory)(cfg)
    else:
        bar_feed = CSVReplayFeed(feed, cfg.timeframes.entry, speed=speed)
    res = run_feed(cfg, iter(bar_feed))
    out = _outdir(output, "forwardtest")
    write_journal(res.trades, out / "journal.csv")

    rows = []
    for t in res.trades:
        intended = t.meta.get("signal_close")
        if intended is None:
            continue
        sign = 1.0 if t.direction == "buy" else -1.0
        rows.append({"pos_id": t.pos_id, "direction": t.direction,
                     "intended_ref_price": intended, "actual_fill": t.entry_price,
                     "adverse_divergence": sign * (t.entry_price - intended)})
    div = pd.DataFrame(rows)
    div.to_csv(out / "fill_divergence.csv", index=False)
    stats = compute_stats(res.trades, res.equity_curve, res.slippage_log,
                          cfg.account.initial_equity)
    _print_stats(stats, "Forward test (paper)")
    if not div.empty:
        console.print(f"mean adverse fill divergence: {div['adverse_divergence'].mean():.4f} "
                      f"(compare with backtest's modeled slippage — Appendix C.3)")
    console.print(f"outputs: {out}")


@app.command()
def live(config: Path = typer.Option(...),
         broker: str = typer.Option(..., help="dotted 'module:Class' implementing BrokerAdapter"),
         feed: str = typer.Option(..., help="dotted 'module:factory' returning a BarFeed"),
         i_understand_the_risk: bool = typer.Option(
             False, "--i-understand-the-risk",
             help="required: real orders, real money, at your own risk")):
    """LIVE trading — OFF by default; same code path as forwardtest; honors all
    kill-switches. No broker adapter ships with this package: you must supply
    one (and a real-time feed) that you have tested against your venue."""
    if not i_understand_the_risk:
        console.print("[red bold]Refusing to run live: pass --i-understand-the-risk "
                      "only after a completed forward test (see VALIDATION.md).[/]")
        raise typer.Exit(code=2)
    cfg = SystemConfig.from_yaml(config)
    mod, cls_name = broker.split(":", 1)
    adapter_cls = getattr(importlib.import_module(mod), cls_name)
    if not (isinstance(adapter_cls, type) and issubclass(adapter_cls, BrokerAdapter)):
        console.print("[red]broker must subclass gold_qm_system.execution.BrokerAdapter[/]")
        raise typer.Exit(code=2)
    fmod, ffac = feed.split(":", 1)
    bar_feed = getattr(importlib.import_module(fmod), ffac)(cfg)
    adapter = adapter_cls(cfg)
    console.print("[yellow bold]LIVE session starting — kill-switches armed "
                  "(daily loss, consec-loss pause, spread/vol breaker, equity floor).[/]")
    res = run_feed(cfg, iter(bar_feed), broker=adapter)
    write_journal(res.trades, _outdir(None, "live") / "journal.csv")
    if res.halted:
        console.print("[red bold]LIVE session HALTED by equity-floor kill switch.[/]")


if __name__ == "__main__":
    app()
