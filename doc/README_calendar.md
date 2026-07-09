# US High-Impact Event Calendar (FOMC / NFP / CPI), 2018 → Jul 2026

**File:** `us_high_impact_calendar_2018_2026.csv` — 278 events (102 NFP, 102 CPI, 74 FOMC).
**Purpose:** trigger/blackout input for `calendar/news.py` (C3 post-news candidate + existing news-blackout filter). Compiled 2026-07-09 from primary sources.

## Schema
| column | description |
|---|---|
| `timestamp_utc` | Release moment in UTC, `YYYY-MM-DD HH:MM:SS`. DST-correct (computed via `America/New_York` zoneinfo, so 08:30 ET → 13:30 UTC in winter / 12:30 UTC in summer). Match this against your UTC-normalized bar timestamps. |
| `date_et`, `time_et`, `weekday` | Release date/time in Eastern Time, for human audit. |
| `event`, `event_code` | Full name / short code: `fomc`, `nfp`, `cpi`. |
| `country`, `currency`, `impact` | `US`, `USD`, `high` (all rows). |
| `scheduled` | `false` only for the three 2020 emergency FOMC actions (Mar 3, Mar 15, Mar 23). A backtest of *scheduled*-news behavior should filter `scheduled == true`; unscheduled events are still needed for the blackout filter. |
| `note` | Irregularities (shutdown delays, holiday shifts, emergency meetings, provisional rows). |
| `source` | Where the date came from. |

## Provenance
- **FOMC 2021–2026 + future scheduled:** fetched from the Fed's official meeting calendar page (statement released 14:00 ET on day 2; press conference 14:30 ET). Remaining 2026 meetings included as `future scheduled`: Jul 29, Sep 16, Oct 28, Dec 9.
- **FOMC 2018–2020:** Federal Reserve historical record (the official calendar page now only renders 2021+). These dates are stable public facts, but they are the one block *not* re-verified against a fetched page this session — a 2-minute spot-check against the Fed's historical-materials pages is cheap insurance before first use.
- **NFP & CPI (all rows):** actual release dates extracted from the BLS archived-news-release indexes, where the release date is encoded in each archive URL (`empsit_MMDDYYYY`, `cpi_MMDDYYYY`). These are realized dates, not scheduled dates — so holiday shifts and delays are already correct.

## Caveats the strategy code must handle
1. **October 2025 does not exist.** Neither the Oct-2025 NFP nor Oct-2025 CPI was ever published (federal shutdown). Sep-2025 data came out late (NFP 2025-11-20, CPI 2025-10-24) and the schedule stayed shifted into early 2026 (Tue/Wed releases). Do not impute a "first Friday" event for Oct/Nov 2025.
2. **One provisional row:** NFP 2026-07-02 (Jun-2026 report, holiday-shifted to Thursday). Observed via the current BLS release page but the archive index had not yet listed it at compile time — verify before including it in any evaluated window.
3. **FOMC timing exceptions (2020):** Mar 3 10:00 ET, Mar 15 17:00 ET **Sunday** (markets closed — the tradable reaction is the Asia/futures open that evening), Mar 23 08:00 ET. All other FOMC rows are 14:00 ET.
4. **Some releases land on market holidays** (e.g., NFP on Good Friday 2021-04-02, 2015-style years): FX/gold liquidity is thin or venues closed; expect missing/thin bars around those timestamps rather than treating them as data errors.
5. **FOMC vol window is longer than the statement:** the 14:30 ET press conference typically extends the high-vol regime ~60–90 min past `timestamp_utc`. C3's post-event window should be defined relative to statement time but tested with awareness of the presser.
6. **Future rows** (`note` contains `future scheduled`, plus CPI 2026-07-14) are for the live forward test only — never part of a historical evaluation. Extend the live calendar going forward from the BLS release schedule and the Fed calendar page; don't hand-extrapolate.

## Integration note
`calendar/news.py` currently expects a CSV via the `calendar_csv` config key. If its expected column names differ, adapt the loader to this schema (or add a thin mapping) rather than editing this file — keeping the file schema stable preserves the provenance chain above. Registry hygiene: log the calendar file hash alongside any C3 run so results are reproducible against the exact event set used.
