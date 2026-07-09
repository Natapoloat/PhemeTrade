"""Fan the gold-QM paper forward-test across a BASKET of instruments to reach a
decision-grade trade count faster (QM+FVG fires only ~3/yr per symbol, so gold
alone would take years to hit n>=30).

Each symbol runs the PROVEN single-symbol harness (scripts/forwardtest_exness.py)
in its own subprocess, sharing the one running Exness MT5 terminal (read-only
market data; orders go to each process's paper SimBroker -> ZERO capital risk).

Cost realism: gold's spread config would be nonsense on FX (0.28 price units on a
1.08 instrument). So the launcher CALIBRATES each symbol's real spread from recent
MT5 bars and writes a per-symbol config before launching.

Usage:
  # connectivity self-test: calibrate + warm-up each symbol, no live wait
  python scripts/forwardtest_basket.py --selftest --symbols XAUUSD,EURUSD

  # real basket forward-test (runs until Ctrl-C; aggregates live trades)
  python scripts/forwardtest_basket.py
"""
from __future__ import annotations

import argparse
import json
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from gold_qm_system.config import SystemConfig

DEFAULT_TERMINAL = r"C:\Program Files\MetaTrader 5 EXNESS\terminal64.exe"
# instruments that actually produced QM trades in the universe scan (metals + FX
# majors/crosses); combined ~30-40 setups/yr -> n>=30 in roughly a year.
DEFAULT_BASKET = ["XAUUSD", "XAGUSD", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD",
                  "USDCAD", "NZDUSD", "EURJPY", "GBPJPY", "USDCHF", "EURGBP"]
HERE = Path(__file__).resolve().parent
SINGLE = HERE / "forwardtest_exness.py"


# ----------------------------------------------------------- cost calibration
def calibrate_configs(symbols, base_cfg_path, outdir, terminal, warmup_probe=800):
    """For each symbol, read its real spread from recent MT5 bars and write a
    per-symbol config (Iter3 signal params kept; costs scaled to that symbol).
    Returns {symbol: (config_path, resolved_symbol)}. Runs in THIS process, then
    shuts MT5 down so the child processes get clean connections."""
    import MetaTrader5 as mt5
    import pandas as pd

    base = SystemConfig.from_yaml(base_cfg_path)
    ok = mt5.initialize(path=terminal) if terminal else mt5.initialize()
    if not ok:
        raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}. Open the "
                           "Exness terminal, log in, leave it running.")
    acct = mt5.account_info()
    print(f"[calib] connected server={acct.server!r} login={acct.login} "
          f"mode={'DEMO' if acct.trade_mode == 0 else 'REAL/OTHER'}", flush=True)

    cfgdir = Path(outdir) / "configs"
    cfgdir.mkdir(parents=True, exist_ok=True)
    result = {}
    for want in symbols:
        info = mt5.symbol_info(want)
        sym = want
        if info is None:
            cands = [s.name for s in (mt5.symbols_get(f"{want}*") or [])]
            if not cands:
                print(f"[calib] {want}: NOT FOUND, skipping", flush=True)
                continue
            sym = cands[0]
            info = mt5.symbol_info(sym)
        mt5.symbol_select(sym, True)
        point = info.point
        rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M15, 0, warmup_probe)
        if rates is not None and len(rates):
            spread_px = float(pd.DataFrame(rates)["spread"].median() * point)
        else:
            spread_px = float(info.spread * point)         # fallback: current spread
        if spread_px <= 0:
            spread_px = point * 10

        cfg = base.model_copy(deep=True)
        cfg.symbol = want
        if want == "XAUUSD":
            pass                                            # gold config already calibrated
        else:
            c = cfg.costs
            c.spread_asian = c.spread_london = c.spread_newyork = c.spread_overlap = round(spread_px, 8)
            c.spread_news_extra = round(spread_px, 8)
            c.base_slippage = round(0.25 * spread_px, 8)
            c.stop_slippage_extra = round(0.5 * spread_px, 8)
            c.news_slippage_extra = round(spread_px, 8)
            c.swap_long_per_unit_day = 0.0                  # unknown per-symbol; neutral
            c.swap_short_per_unit_day = 0.0
            # spread_cap (a kill-switch, in price units) must scale with the symbol
            cfg.kill_switches.spread_cap = round(max(5 * spread_px, 1e-4), 8)
        path = cfgdir / f"{want}_config.yaml"
        cfg.to_yaml(path)
        result[want] = (path, sym)
        print(f"[calib] {want:<8} -> {sym:<10} spread~{spread_px:.5f} px  cfg={path.name}", flush=True)

    mt5.shutdown()
    return result


# ----------------------------------------------------------- aggregation
def aggregate(outdir, symbols):
    """Read each symbol's journal, pool the LIVE exits, print per-symbol +
    combined expectancy/PF/win/n."""
    outdir = Path(outdir)
    print("\n" + "=" * 68)
    print("BASKET FORWARD-TEST — LIVE trades only (warm-up excluded)")
    print("=" * 68)
    print(f"{'symbol':<9}{'n':>4}{'expR':>8}{'win%':>7}{'PF':>7}{'sumR':>8}")
    all_r = []
    for sym in symbols:
        jpath = outdir / f"{sym}.jsonl"
        rs = []
        if jpath.exists():
            for line in jpath.read_text(encoding="utf-8").splitlines():
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("event") == "exit" and rec.get("phase") == "live":
                    rs.append(float(rec["r_multiple"]))
        all_r.extend(rs)
        if rs:
            _print_row(sym, rs)
        else:
            print(f"{sym:<9}{0:>4}{'—':>8}{'—':>7}{'—':>7}{'—':>8}")
    print("-" * 43)
    if all_r:
        _print_row("COMBINED", all_r)
    else:
        print("COMBINED  0   — no live trades yet (keep it running).")
    print("\nAcceptance: PF>=1.3, expectancy>0, n>=30. Backtest OOS expectation ~ -0.04R.")


def _print_row(label, rs):
    n = len(rs)
    exp = sum(rs) / n
    wins = [r for r in rs if r > 0]
    gw = sum(wins)
    gl = -sum(r for r in rs if r <= 0)
    pf = (gw / gl) if gl > 0 else float("inf")
    print(f"{label:<9}{n:>4}{exp:>+8.3f}{len(wins)/n*100:>6.0f}%{pf:>7.2f}{sum(rs):>+8.2f}")


# ----------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--symbols", default=",".join(DEFAULT_BASKET),
                    help="comma-separated basket")
    ap.add_argument("--config", default="forwardtest_iter3_config.yaml")
    ap.add_argument("--warmup-bars", type=int, default=3000)
    ap.add_argument("--terminal", default=DEFAULT_TERMINAL)
    ap.add_argument("--outdir", default="output/basket")
    ap.add_argument("--selftest", action="store_true",
                    help="calibrate + warm-up each symbol, no live wait")
    ap.add_argument("--status-every", type=float, default=120.0,
                    help="seconds between aggregated status prints")
    args = ap.parse_args()

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    cfgs = calibrate_configs(symbols, args.config, outdir, args.terminal,
                             warmup_probe=min(args.warmup_bars, 800))
    if not cfgs:
        print("No symbols resolved; aborting.")
        return

    procs = {}
    for sym, (cfgpath, _resolved) in cfgs.items():
        logf = open(outdir / f"{sym}.log", "a", encoding="utf-8")
        cmd = [sys.executable, str(SINGLE), "--symbol", sym,
               "--config", str(cfgpath), "--warmup-bars", str(args.warmup_bars),
               "--terminal", args.terminal, "--journal", str(outdir / f"{sym}.jsonl")]
        if args.selftest:
            cmd.append("--selftest")
        p = subprocess.Popen(cmd, stdout=logf, stderr=subprocess.STDOUT,
                             cwd=str(HERE.parent))
        procs[sym] = (p, logf)
        print(f"[launch] {sym} pid={p.pid} log={outdir / f'{sym}.log'}", flush=True)
        time.sleep(2.0)                       # stagger MT5 init

    stopping = {"flag": False}

    def handle_sigint(signum, frame):
        print("\n[stop] Ctrl-C — terminating children, then aggregating.", flush=True)
        stopping["flag"] = True
    signal.signal(signal.SIGINT, handle_sigint)

    print(f"\n[basket] {len(procs)} workers running. Per-symbol console -> "
          f"{outdir}/<SYM>.log ; trades -> {outdir}/<SYM>.jsonl", flush=True)
    try:
        last_status = 0.0
        while not stopping["flag"]:
            alive = [s for s, (p, _) in procs.items() if p.poll() is None]
            if not alive:
                print("[basket] all workers exited.", flush=True)
                break
            now = time.time()
            if now - last_status >= args.status_every or args.selftest:
                aggregate(outdir, list(cfgs.keys()))
                last_status = now
                if args.selftest and not alive:
                    break
            time.sleep(3.0)
    finally:
        for sym, (p, logf) in procs.items():
            if p.poll() is None:
                p.terminate()
        for sym, (p, logf) in procs.items():
            try:
                p.wait(timeout=15)
            except subprocess.TimeoutExpired:
                p.kill()
            logf.close()
        aggregate(outdir, list(cfgs.keys()))
        print(f"\n[basket] done {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC")


if __name__ == "__main__":
    main()
