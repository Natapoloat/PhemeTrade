"""G7 multiple-comparisons hygiene: a write-once holdout freeze + an append-only
hypothesis registry. Import this from every new-strategy experiment.

- freeze_holdout(): records the holdout cutoff ONCE (repo research/holdout.json).
  The most-recent slice (default 2.5y) is off-limits to ALL experiments until a
  candidate has passed walk-forward on the development remainder. split_bars()
  enforces it; touching the holdout requires read_holdout(confirm=True).
- log_run(): appends one record per config actually run against the data
  (candidate, params, sample, stats) to research/registry.jsonl. The gold set has
  already absorbed many QM iterations; its p-values are not innocent, so every
  run — including abandoned ones — must be logged for a multiplicity-aware read.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent
_RESEARCH = _ROOT / "research"
_HOLDOUT = _RESEARCH / "holdout.json"
_REGISTRY = _RESEARCH / "registry.jsonl"


def freeze_holdout(cutoff_utc: str, years: float = 2.5, note: str = "") -> dict:
    """Write the holdout boundary once. `cutoff_utc` (e.g. '2024-01-09'): data at
    or after this instant is the sealed holdout. Refuses to overwrite an existing
    freeze (raises) — the whole point is that it cannot be moved to fit a result."""
    _RESEARCH.mkdir(parents=True, exist_ok=True)
    if _HOLDOUT.exists():
        raise FileExistsError(
            f"holdout already frozen at {read_holdout()['cutoff_utc']} — it is "
            "write-once by design; do not move it to fit a result")
    rec = {
        "cutoff_utc": pd.Timestamp(cutoff_utc, tz="UTC").isoformat(),
        "holdout_years": years,
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "rule": "data >= cutoff_utc is sealed; evaluate ONCE, last, per strategy class",
        "note": note,
    }
    _HOLDOUT.write_text(json.dumps(rec, indent=2), encoding="utf-8")
    return rec


def read_holdout(confirm: bool = False) -> dict:
    if not _HOLDOUT.exists():
        raise FileNotFoundError("holdout not frozen — call freeze_holdout() first")
    rec = json.loads(_HOLDOUT.read_text(encoding="utf-8"))
    if not confirm:
        rec = {k: rec[k] for k in ("cutoff_utc", "holdout_years", "rule")}
    return rec


def holdout_cutoff() -> pd.Timestamp:
    return pd.Timestamp(read_holdout()["cutoff_utc"])


def split_bars(df: pd.DataFrame, time_col: Optional[str] = None):
    """Return (development, holdout) split at the frozen cutoff. `time_col` names
    the timestamp column; if None, uses the DatetimeIndex."""
    cutoff = holdout_cutoff()
    ts = df[time_col] if time_col else df.index
    ts = pd.to_datetime(ts, utc=True)
    dev = df[ts < cutoff]
    hold = df[ts >= cutoff]
    return dev, hold


def development_only(df: pd.DataFrame, time_col: Optional[str] = None) -> pd.DataFrame:
    """Development slice only — the safe default for all pre-holdout work."""
    return split_bars(df, time_col)[0]


def log_run(candidate: str, params: dict, sample: str, stats: dict,
            note: str = "") -> None:
    """Append one experiment record. `sample` in {development, walkforward-oos,
    holdout, forward-test, in-sample-full}. Log EVERY run, including abandoned."""
    _RESEARCH.mkdir(parents=True, exist_ok=True)
    rec = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "candidate": candidate,
        "sample": sample,
        "params": params,
        "stats": {k: (round(v, 4) if isinstance(v, float) else v) for k, v in stats.items()},
        "note": note,
    }
    with _REGISTRY.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")


def registry_df() -> pd.DataFrame:
    if not _REGISTRY.exists():
        return pd.DataFrame()
    return pd.DataFrame([json.loads(l) for l in _REGISTRY.read_text(encoding="utf-8").splitlines() if l.strip()])
