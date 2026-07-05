"""Session identification and session-dependent spread model (Appendices D, F)."""
from __future__ import annotations

import pandas as pd

from gold_qm_system.config import CostConfig, SessionConfig


def _in_window(hour: int, window: tuple[int, int]) -> bool:
    start, end = window
    if start <= end:
        return start <= hour < end
    return hour >= start or hour < end  # overnight window


def session_of(ts: pd.Timestamp, sessions: SessionConfig) -> str:
    """Return the session name for a UTC timestamp.

    Overlap is checked first (it is a subset of both London and NY); then
    London, NY, Asian; anything else is 'off'.
    """
    if ts.tzinfo is None:
        raise ValueError("timestamp must be tz-aware UTC")
    hour = ts.tz_convert("UTC").hour
    if _in_window(hour, sessions.overlap):
        return "overlap"
    if _in_window(hour, sessions.london):
        return "london"
    if _in_window(hour, sessions.newyork):
        return "newyork"
    if _in_window(hour, sessions.asian):
        return "asian"
    return "off"


def spread_at(ts: pd.Timestamp, sessions: SessionConfig, costs: CostConfig, in_news_window: bool = False) -> float:
    """Session-dependent spread in price units, plus news add-on."""
    name = session_of(ts, sessions)
    base = {
        "overlap": costs.spread_overlap,
        "london": costs.spread_london,
        "newyork": costs.spread_newyork,
        "asian": costs.spread_asian,
        # outside all defined sessions: assume the worst configured spread
        "off": max(costs.spread_asian, costs.spread_london, costs.spread_newyork, costs.spread_overlap),
    }[name]
    return base + (costs.spread_news_extra if in_news_window else 0.0)
