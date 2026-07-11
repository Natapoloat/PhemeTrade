"""Track A safety guards. The demo-account guard is BLOCKING: it must be called at
every live-session start and hard-exits the process if the connected MT5 account is
not a DEMO account. Phase 4 Track A may never touch real money.

MT5 account_info().trade_mode: 0 = ACCOUNT_TRADE_MODE_DEMO, 1 = CONTEST, 2 = REAL.
Only mode 0 is permitted here.
"""
from __future__ import annotations

import sys
from typing import Any, Optional

DEMO = 0  # ACCOUNT_TRADE_MODE_DEMO


class NotDemoError(SystemExit):
    """Raised (as SystemExit) when the connected account is not a demo account."""


def assert_demo(mt5: Any, expected_login: Optional[int] = None,
                expected_server: Optional[str] = None, logger: Any = None) -> dict:
    """Verify the live MT5 connection is a DEMO account. Hard-exit otherwise.

    Optionally pin the expected login/server (from config) so we also refuse to run
    against the wrong demo account. Returns a small dict describing the account for
    the session log.
    """
    acct = mt5.account_info()
    if acct is None:
        _die(logger, f"no MT5 account_info (terminal not logged in?): {mt5.last_error()}")
    info = {"login": int(acct.login), "server": str(acct.server),
            "trade_mode": int(acct.trade_mode), "currency": str(acct.currency),
            "balance": float(acct.balance), "leverage": int(acct.leverage)}
    if acct.trade_mode != DEMO:
        _die(logger, f"REFUSING TO RUN: account {acct.login} on {acct.server} is "
                     f"trade_mode={acct.trade_mode} (not DEMO=0). Track A is demo-only.")
    if expected_login is not None and int(acct.login) != int(expected_login):
        _die(logger, f"REFUSING TO RUN: connected login {acct.login} != expected "
                     f"{expected_login} (wrong demo account).")
    if expected_server is not None and str(acct.server) != str(expected_server):
        _die(logger, f"REFUSING TO RUN: connected server {acct.server!r} != expected "
                     f"{expected_server!r}.")
    _say(logger, f"demo guard OK: login={acct.login} server={acct.server} "
                 f"DEMO balance={acct.balance:.2f} {acct.currency}")
    return info


def _die(logger, msg: str) -> None:
    banner = "=" * 70
    text = f"\n{banner}\n[DEMO GUARD] {msg}\n{banner}\n"
    if logger is not None:
        try:
            logger.error(text)
        except Exception:  # noqa: BLE001
            pass
    print(text, file=sys.stderr, flush=True)
    raise NotDemoError(2)


def _say(logger, msg: str) -> None:
    if logger is not None:
        try:
            logger.info(msg)
        except Exception:  # noqa: BLE001
            pass
    print(f"[DEMO GUARD] {msg}", flush=True)
