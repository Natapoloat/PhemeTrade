"""Economic-calendar news filter (Appendix D).

Pluggable source; ships with a CSV backend the user populates:
    timestamp_utc,impact,currency,title
    2024-01-05 13:30,high,USD,Non-Farm Payrolls
Impact levels: low < medium < high. Blackout = [event - N min, event + N min].
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

_IMPACT_RANK = {"low": 0, "medium": 1, "high": 2}


def _as_bool(x: object) -> bool:
    if isinstance(x, bool):
        return x
    return str(x).strip().lower() in ("true", "1", "yes")


class NewsCalendar:
    def __init__(self, events: Optional[pd.DataFrame] = None):
        """`events` needs columns: timestamp_utc (tz-aware UTC), impact, title."""
        if events is None:
            events = pd.DataFrame(columns=["timestamp_utc", "impact", "currency", "title"])
        self.events = events.sort_values("timestamp_utc").reset_index(drop=True)
        self._epoch_cache: dict[str, np.ndarray] = {}   # min_impact -> sorted event epochs (ns)

    def _relevant_epochs(self, min_impact: str) -> np.ndarray:
        """Sorted ns-epoch array of events with impact >= min_impact (cached).
        Turns in_blackout into an O(log n) search instead of a per-call DataFrame
        filter — matters now the calendar is wired and hit on every bar."""
        cached = self._epoch_cache.get(min_impact)
        if cached is None:
            if self.events.empty:
                cached = np.empty(0, dtype="int64")
            else:
                rank = _IMPACT_RANK[min_impact]
                mask = self.events["impact"].map(_IMPACT_RANK) >= rank
                ts = self.events.loc[mask, "timestamp_utc"]
                cached = np.sort(ts.astype("int64").to_numpy())
            self._epoch_cache[min_impact] = cached
        return cached

    @classmethod
    def from_csv(cls, path: str | Path, scheduled_only: bool = False,
                 as_of: Optional[pd.Timestamp | str] = None) -> "NewsCalendar":
        """Load an event calendar. The loader adapts to the file's schema (does not
        require the file to match ours):
        - `event` is mapped to `title` when no `title` column is present;
        - a `scheduled` column (bool / "true"/"false") is honored — pass
          `scheduled_only=True` to keep only scheduled events (historical
          evaluation of scheduled-news behavior; unscheduled emergencies are still
          returned by default so the blackout filter can use them);
        - `as_of` drops any row at/after that instant (future rows are for the live
          forward test only, never a historical evaluation).
        Extra columns (event_code, note, source, ...) are preserved untouched.
        """
        df = pd.read_csv(path)
        df.columns = [c.strip().lower() for c in df.columns]
        if "timestamp_utc" not in df.columns:
            raise ValueError("calendar CSV needs a 'timestamp_utc' column")
        df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
        if "title" not in df.columns and "event" in df.columns:
            df["title"] = df["event"]
        df["impact"] = df.get("impact", "high").astype(str).str.strip().str.lower()
        bad = ~df["impact"].isin(_IMPACT_RANK)
        if bad.any():
            raise ValueError(f"unknown impact values: {sorted(df.loc[bad, 'impact'].unique())}")
        df["scheduled"] = (df["scheduled"].map(_as_bool) if "scheduled" in df.columns
                           else True)
        if scheduled_only:
            df = df[df["scheduled"]]
        if as_of is not None:
            cutoff = pd.Timestamp(as_of)
            cutoff = cutoff.tz_localize("UTC") if cutoff.tzinfo is None else cutoff.tz_convert("UTC")
            df = df[df["timestamp_utc"] < cutoff]
        return cls(df.reset_index(drop=True))

    @classmethod
    def empty(cls) -> "NewsCalendar":
        return cls(None)

    def in_blackout(self, ts: pd.Timestamp, blackout_min: int, min_impact: str = "high") -> bool:
        """True if `ts` falls within +/- blackout_min of any event with impact
        >= min_impact."""
        if self.events.empty or blackout_min <= 0:
            return False
        arr = self._relevant_epochs(min_impact)
        if arr.size == 0:
            return False
        delta = int(blackout_min) * 60 * 1_000_000_000        # minutes -> ns
        t = ts.value
        i = int(np.searchsorted(arr, t - delta, side="left"))  # first event >= t-delta
        return i < arr.size and arr[i] <= t + delta            # within +/- window?
