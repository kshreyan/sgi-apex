# Loading real admissions data

`sgi ingest --file` turns the admissions office's export into the canonical weekly funnel. Every forecast reads that funnel.

```bash
sgi ingest --file admissions_2017_2026.csv --dry-run                        # validate, write report only
sgi ingest --file admissions_2017_2026.csv --finals registrar_finals.csv    # validate, reconcile, write silver
```

## What the export must contain

There is one row per programme per snapshot, and the counts are **cumulative for that admission cycle**. Header spellings are matched loosely; the accepted aliases are in `configs/data/admissions_export.json`. A blank template is at `configs/data/admissions_export_template.csv`.

| Field | Accepted as | Notes |
|---|---|---|
| Programme | `programme_id`, or `programme` (+ `campus` when the name exists on both campuses) | Add other spellings under `programme_aliases` |
| Timing | `admission_year` + `cycle_week` (0 = 1 April), **or** `as_of_date` | With dates, the week is derived and the latest snapshot in a week wins. Dates are read day-first (`16/04/2025`) |
| Counts | `enquiries_cum`, `applications_cum`, `enrolled_cum` | Whole numbers ≥ 0; thousands separators allowed |

Excel files need `pip install -e '.[excel]'`.

## Rules

**ERROR: blocks ingest, nothing is written to silver**
- missing columns
- unknown programme
- blank, negative or fractional count
- week outside 0–26
- unparseable date
- the same week reported twice with different counts
- with `--finals`: an institution-year whose funnel final differs from the registrar's final by more than ±1 (`--tol`)

**WARN: passes, but is shown in the report and lowers the data-quality score**
- **gap_filled:** a missing week takes the previous week's value and is marked `imputed`. Values are only ever carried forward, never backward, so nothing leaks from the future.
- **leading_gap:** weeks before the first snapshot are set to 0.
- **incomplete_cycle:** a closed cycle ends before week 26, so the last value is taken as final.
- **non_monotone:** a cumulative count falls. Check for withdrawals or re-keying.
- **funnel_inverted:** enrolled is greater than applications.
- **over_intake:** enrolled is greater than the sanctioned intake. Fix `programmes.csv`, or treat it as a compliance flag.
- **short_history:** fewer than 5 closed cycles, which is too few for a meaningful backtest.

**INFO**
- **programme_absent:** the programme is not in the file.
- **finals_reconciled:** the funnel finals match the registrar's finals.

Filled-in weeks do not count as observations in the data-quality completeness check. A programme that is mostly filled in therefore drops towards DQ-HOLD instead of producing a confident forecast.

## Where things go

| Output | Path | Committed? |
|---|---|---|
| Exact copy of the file as read, keyed by sha256, never rewritten | `data/bronze/admissions_export_<sha>.parquet` | no |
| Canonical funnel | `data/silver/admissions_funnel.parquet` | no |
| Ingest report | `data/reports/ingest_<sha>.md` | no |

All of `data/` is git-ignored. Real figures must never be committed to this public repository or published on the public Pages site (see `privacy_security.md`).

## Not yet wired

`sgi run` still rebuilds the public demo from synthetic data. Running the forecast loop on a real silver table is weeks 4–5 of the 90-day plan. That step needs a private output location for the site data and the lockbox, so that real forecasts are never pushed to Pages.
