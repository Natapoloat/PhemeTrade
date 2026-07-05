"""Auto-logged trade journal — Part I §9 fields, machine-readable.

The 'screenshot' requirement is satisfied numerically: QM point bar-indices,
QML, zone and stop levels are logged so any charting tool can reconstruct the
annotated picture. The 'good loss vs rule violation' post-mortem column is
left blank for the human — the system cannot grade its own discipline.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from gold_qm_system.execution import TradeRecord


def trades_to_journal(trades: list[TradeRecord]) -> pd.DataFrame:
    rows = []
    for t in trades:
        m = t.meta
        sizing = m.get("sizing", {})
        rows.append({
            # what & when
            "pos_id": t.pos_id,
            "setup": m.get("setup"),
            "direction": t.direction,
            "entry_time": t.entry_time,
            "exit_time": t.exit_time,
            "exit_reason": t.exit_reason,
            # timeframes used (Part I §9.1)
            "tf_bias": m.get("tf_bias"),
            "tf_setup": m.get("tf_setup"),
            "tf_entry": m.get("tf_entry"),
            # QM structure coordinates (§9.2 'screenshot', numeric form)
            "qml": m.get("qml"),
            "qm_points": str(m.get("qm_points", "")),
            "zone_lo": (m.get("zone") or (None, None))[0],
            "zone_hi": (m.get("zone") or (None, None))[1],
            # liquidity concept applied (§9.3)
            "sfp": m.get("sfp"),
            "cplq": m.get("cplq"),
            # price-action confirmation (§9.4)
            "trigger": m.get("trigger"),
            # sizing & which method was binding (§9.5)
            "size": t.size,
            "binding_method": m.get("binding_method"),
            "size_by_risk": sizing.get("risk"),
            "size_by_vol": sizing.get("vol"),
            "size_by_margin": sizing.get("margin"),
            # outcome vs plan (§9.6)
            "entry_price": t.entry_price,
            "exit_price": t.exit_price,
            "stop_at_exit": t.stop_at_exit,
            "gross_pnl": t.gross_pnl,
            "costs": t.costs,
            "net_pnl": t.net_pnl,
            "r_multiple": t.r_multiple,
            "ongoing_limit_trim": t.exit_reason == "trim",
            # context
            "session": m.get("session"),
            "bias_directional": m.get("bias_directional"),
            "bias_setup": m.get("bias_setup"),
            "rsi_entry_tf": m.get("rsi_entry_tf"),
            "atr_pctile_entry": m.get("atr_pctile_entry"),
            # post-mortem (§9.7) — for the human reviewer
            "good_loss_or_rule_violation": "",
        })
    return pd.DataFrame(rows)


def write_journal(trades: list[TradeRecord], path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    trades_to_journal(trades).to_csv(path, index=False)
    return path
