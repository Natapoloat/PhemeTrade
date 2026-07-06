"""Fetch XAUUSD history from an Exness MT5 terminal into the repo data format.

Prereqs: Exness MetaTrader 5 terminal installed and logged into your (demo)
account at least once. The terminal is started headlessly by this script.

- Bars are written as <SYMBOL>_<TF>.csv with UTC open_time (the repo
  convention). MT5 reports bar times in SERVER time; the offset is
  auto-detected from the live tick clock (override with --server-utc-offset).
- Also prints a per-session spread calibration table (from the per-bar
  'spread' column, converted to price units) so you can set the Appendix D
  spread values in your YAML config from YOUR broker's actual numbers.

Usage:
  python scripts/fetch_exness_mt5.py --symbol XAUUSD --timeframe M5 --years 3 \
      --out market_data
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import MetaTrader5 as mt5
import pandas as pd

DEFAULT_TERMINAL = r"C:\Program Files\MetaTrader 5 EXNESS\terminal64.exe"

TF_MAP = {
    "M1": mt5.TIMEFRAME_M1,
    "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "H1": mt5.TIMEFRAME_H1,
    "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1,
}


def die(msg: str) -> None:
    print(f"ERROR: {msg}\nlast_error: {mt5.last_error()}", file=sys.stderr)
    mt5.shutdown()
    sys.exit(1)


def resolve_symbol(want: str) -> str:
    """Exness may suffix symbols by account type (e.g. XAUUSDm on mini)."""
    info = mt5.symbol_info(want)
    if info is not None:
        return want
    cands = [s.name for s in (mt5.symbols_get(f"{want}*") or [])]
    if not cands:
        die(f"symbol {want!r} not found; no candidates matching '{want}*'")
    print(f"note: {want!r} not found; using {cands[0]!r} (candidates: {cands})")
    return cands[0]


def detect_server_offset_hours() -> int:
    """Server clock vs UTC, rounded to the nearest hour (tick time is 'now')."""
    tick = mt5.symbol_info_tick(SYMBOL)
    if tick is None or tick.time == 0:
        print("warning: no live tick (market closed?); assuming offset 0 — "
              "verify with --server-utc-offset if bars look shifted")
        return 0
    server_now = datetime.fromtimestamp(tick.time, tz=timezone.utc)
    real_now = datetime.now(timezone.utc)
    return round((server_now - real_now).total_seconds() / 3600)


def fetch_chunked(symbol: str, tf, start: datetime, end: datetime,
                  chunk_days: int = 30) -> pd.DataFrame:
    frames = []
    cur = start
    while cur < end:
        hi = min(cur + timedelta(days=chunk_days), end)
        rates = mt5.copy_rates_range(symbol, tf, cur, hi)
        if rates is not None and len(rates):
            frames.append(pd.DataFrame(rates))
        cur = hi
    if not frames:
        die(f"no bars returned for {symbol} in {start:%Y-%m-%d}..{end:%Y-%m-%d} "
            "(history depth may be limited — try fewer --years)")
    df = pd.concat(frames).drop_duplicates(subset="time").sort_values("time")
    return df.reset_index(drop=True)


def session_of_hour(h: int) -> str:
    if 13 <= h < 16:
        return "overlap"
    if 7 <= h < 16:
        return "london"
    if 13 <= h < 21:
        return "newyork"
    if 0 <= h < 7:
        return "asian"
    return "off"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--symbol", default="XAUUSD")
    ap.add_argument("--timeframe", default="M5", choices=list(TF_MAP))
    ap.add_argument("--years", type=float, default=3.0)
    ap.add_argument("--out", default="market_data")
    ap.add_argument("--terminal", default=DEFAULT_TERMINAL)
    ap.add_argument("--server-utc-offset", type=int, default=None,
                    help="server clock minus UTC in hours; default: auto-detect")
    ap.add_argument("--login", type=int, default=None,
                    help="MT5 account number (only needed if the terminal has "
                         "no saved login); password is prompted, never stored")
    ap.add_argument("--server", default=None,
                    help="MT5 server name, e.g. 'Exness-MT5Trial9' (shown in "
                         "your Exness account email / terminal login dialog)")
    args = ap.parse_args()

    if args.login is not None:
        import getpass
        pwd = getpass.getpass(f"MT5 password for account {args.login}: ")
        ok = mt5.initialize(path=args.terminal, login=args.login,
                            password=pwd, server=args.server)
    else:
        ok = mt5.initialize(path=args.terminal)
    if not ok:
        die(f"cannot initialize/authorize MT5 terminal at {args.terminal}.\n"
            "Fix: open the Exness MT5 terminal, log into your trial account "
            "(File > Login to Trade Account, tick 'Save password'), leave it "
            "running, then re-run this script. Or pass --login <account> "
            "--server <ExnessServerName> to authenticate here.")
    acct = mt5.account_info()
    print(f"connected: server={acct.server!r} login={acct.login} "
          f"trade_mode={'DEMO' if acct.trade_mode == 0 else 'REAL/OTHER'}")

    global SYMBOL
    SYMBOL = resolve_symbol(args.symbol)
    mt5.symbol_select(SYMBOL, True)
    sym = mt5.symbol_info(SYMBOL)
    offset = (args.server_utc_offset if args.server_utc_offset is not None
              else detect_server_offset_hours())
    print(f"symbol={SYMBOL} point={sym.point} digits={sym.digits} "
          f"server_utc_offset={offset:+d}h")

    end = datetime.now(timezone.utc) + timedelta(hours=offset)   # server 'now'
    start = end - timedelta(days=365.25 * args.years)
    raw = fetch_chunked(SYMBOL, TF_MAP[args.timeframe], start, end)

    df = pd.DataFrame({
        "open_time": pd.to_datetime(raw["time"], unit="s", utc=True)
                       - pd.Timedelta(hours=offset),             # server -> UTC
        "open": raw["open"], "high": raw["high"],
        "low": raw["low"], "close": raw["close"],
        "volume": raw["tick_volume"],
    })
    # drop the still-forming last bar: the repo consumes CLOSED bars only
    df = df.iloc[:-1]

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{args.symbol}_{args.timeframe}.csv"
    df.to_csv(out_path, index=False)
    print(f"wrote {len(df):,} closed {args.timeframe} bars "
          f"({df['open_time'].iloc[0]} .. {df['open_time'].iloc[-1]}) -> {out_path}")

    # ---- spread calibration for the YAML cost model (Appendix D)
    spread_px = raw["spread"].iloc[:-1] * sym.point                # points -> price
    hours = df["open_time"].dt.hour
    print("\nSpread calibration (price units, from broker bar data) — put these "
          "in your config's costs section:")
    for name in ("asian", "london", "newyork", "overlap"):
        m = hours.map(session_of_hour) == name
        if m.any():
            s = spread_px[m.values]
            print(f"  spread_{name}: median={s.median():.3f}  "
                  f"p90={s.quantile(0.9):.3f}  max={s.max():.3f}")
    mt5.shutdown()


if __name__ == "__main__":
    main()
