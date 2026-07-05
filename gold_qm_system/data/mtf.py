"""No-lookahead multi-timeframe alignment (Appendix B.3).

Rule: at a lower-TF bar whose CLOSE time is `t_close`, a higher-TF bar is
visible only if that HTF bar has ALREADY CLOSED, i.e. htf_open + htf_period
<= t_close. An unclosed HTF candle must never be forward-filled into LTF rows.
"""
from __future__ import annotations

import pandas as pd

from .loaders import timeframe_delta


def htf_view(
    ltf: pd.DataFrame,
    htf: pd.DataFrame,
    ltf_tf: str,
    htf_tf: str,
    columns: list[str] | None = None,
    prefix: str | None = None,
) -> pd.DataFrame:
    """Return, for each LTF bar, the values of the LAST CLOSED HTF bar.

    Output is indexed like `ltf`. Rows before the first HTF close are NaN.
    """
    ltf_delta = timeframe_delta(ltf_tf)
    htf_delta = timeframe_delta(htf_tf)
    if htf_delta <= ltf_delta:
        raise ValueError(f"htf {htf_tf} must be coarser than ltf {ltf_tf}")

    cols = columns if columns is not None else list(htf.columns)
    prefix = prefix if prefix is not None else f"{htf_tf.lower()}_"

    ltf_close = pd.Series(ltf.index + ltf_delta, index=ltf.index, name="ltf_close")
    htf_closed = htf[cols].copy()
    htf_closed.index = htf.index + htf_delta  # index by HTF CLOSE time
    htf_closed = htf_closed.sort_index()

    left = pd.DataFrame({"ltf_close": pd.DatetimeIndex(ltf.index + ltf_delta)}, index=ltf.index).reset_index()
    right = htf_closed.reset_index()
    right = right.rename(columns={right.columns[0]: "htf_close"})

    merged = pd.merge_asof(
        left.sort_values("ltf_close"),
        right.sort_values("htf_close"),
        left_on="ltf_close",
        right_on="htf_close",
        direction="backward",
        allow_exact_matches=True,  # HTF bar closing exactly at LTF close IS visible
    )
    merged = merged.set_index("open_time").sort_index()
    out = merged[cols].rename(columns={c: f"{prefix}{c}" for c in cols})
    out[f"{prefix}bar_close_time"] = merged["htf_close"]
    return out


def assert_no_htf_leak(ltf: pd.DataFrame, view: pd.DataFrame, ltf_tf: str, prefix: str) -> None:
    """Sanity assertion: every referenced HTF bar closed at/before the LTF close."""
    col = f"{prefix}bar_close_time"
    ref = view[col].dropna()
    ltf_close = pd.Series(pd.DatetimeIndex(ltf.index + timeframe_delta(ltf_tf)), index=ltf.index)
    leaked = ref.index[ref > ltf_close.loc[ref.index]]
    if len(leaked) > 0:
        raise AssertionError(f"HTF leak: {len(leaked)} LTF rows reference an unclosed HTF bar (first: {leaked[0]})")
