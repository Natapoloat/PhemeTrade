"""Economic-calendar news filter (Appendix D).

Pluggable source; ships with a CSV backend the user populates:
    timestamp_utc,impact,currency,title
    2024-01-05 13:30,high,USD,Non-Farm Payrolls
Impact levels: low < medium < high. Blackout = [event - N min, event + N min].
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

_IMPACT_RANK = {"low": 0, "medium": 1, "high": 2}


class NewsCalendar:
    def __init__(self, events: Optional[pd.DataFrame] = None):
        """`events` needs columns: timestamp_utc (tz-aware UTC), impact, title."""
        if events is None:
            events = pd.DataFrame(columns=["timestamp_utc", "impact", "currency", "title"])
        self.events = events.sort_values("timestamp_utc").reset_index(drop=True)

    @classmethod
    def from_csv(cls, path: str | Path) -> "NewsCalendar":
        df = pd.read_csv(path)
        df.columns = [c.strip().lower() for c in df.columns]
        if "timestamp_utc" not in df.columns:
            raise ValueError("calendar CSV needs a 'timestamp_utc' column")
        df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
        df["impact"] = df.get("impact", "high")
        df["impact"] = df["impact"].astype(str).str.strip().str.lower()
        bad = ~df["impact"].isin(_IMPACT_RANK)
        if bad.any():
            raise ValueError(f"unknown impact values: {sorted(df.loc[bad, 'impact'].unique())}")
        return cls(df)

    @classmethod
    def empty(cls) -> "NewsCalendar":
        return cls(None)

    def in_blackout(self, ts: pd.Timestamp, blackout_min: int, min_impact: str = "high") -> bool:
        """True if `ts` falls within +/- blackout_min of any event with impact
        >= min_impact."""
        if self.events.empty or blackout_min <= 0:
            return False
        rank = _IMPACT_RANK[min_impact]
        relevant = self.events[self.events["impact"].map(_IMPACT_RANK) >= rank]
        if relevant.empty:
            return False
        delta = pd.Timedelta(minutes=blackout_min)
        times = relevant["timestamp_utc"]
        return bool(((times >= ts - delta) & (times <= ts + delta)).any())
