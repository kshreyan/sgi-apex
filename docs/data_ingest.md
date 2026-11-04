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

## Forecasting on real data

```bash
sgi run --real --out ~/sgi-private            # or --out data/private_run (git-ignored)
sgi run --real --out ~/sgi-private --as-of-week 8   # replay an earlier week
python -m http.server -d ~/sgi-private/site 8000    # view the private control tower
```

A real run reads the silver table written by `sgi ingest --file` and works out its settings from the data:

| Setting | Rule |
|---|---|
| Live cycle | The latest `admission_year` in the data |
| As-of week | The last week actually observed in that cycle, not a filled-in one. `--as-of-week` overrides it |
| Lockbox year | The last closed cycle. It is scored once and never used to choose a model |
| Validation years | Up to 5 closed cycles before the lockbox year. Each needs at least 2 earlier cycles behind it |
| Minimum history | 4 closed cycles, otherwise the run stops |
| Excluded programmes | Programmes with no rows in the live cycle, or no history. They are listed in the output, not forecast |

Everything is written under `--out`:
- the lockbox
- the decision register
- backtests
- the chairman's brief
- a copy of the control tower with a "confidential" banner

**Guards**
- `--real` without `--out` is refused.
- An `--out` inside the repo is refused, except under the git-ignored `data/`.
- A silver table that still holds synthetic rows is refused.

The public `site/` and `artifacts/` are never touched. The lockbox applies inside the private folder too: re-running the same week on the same data reproduces the frozen forecast, but a changed forecast for an already-frozen week is refused.

Serving the private site to the chairman's office needs a login in front of it. That is weeks 5–6 of the plan (see `privacy_security.md`).
