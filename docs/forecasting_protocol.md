# Forecasting protocol

## Data periods

| Period | Years | Use |
|---|---|---|
| Training | every completed cycle before the origin year | model fitting, snapshot-gated |
| Validation | 2020–2024 | rolling-origin backtest, champion selection |
| Lockbox | 2025 | scored once, reported, **never** used for selection or tuning |
| Prospective | 2026 onward | frozen before the outcome in `artifacts/forecasts/` |

## Leakage control

Forecasting code reads data only through `pipeline.snapshot(df, year, week)`. `tests/leakage/` corrupts every future row and asserts the forecasts are bit-identical.

## Models (admissions final enrolment)

Listed simplest first:

| Model | Idea |
|---|---|
| `seasonal_naive` | Last year's final × lognormal noise at the historical YoY volatility |
| `pace_own` | Enrolled-to-date ÷ the programme's historical share complete at this week |
| `pace_pooled` | Same, with the share curve shrunk toward the campus curve (k = 3 pseudo-years) |
| `bayes_blend` | Precision-weighted log-scale combination of the seasonal prior and the pooled pace likelihood |

All samples are floored at confirmed enrolments and capped at sanctioned intake.

**Correlation:** draws use a three-level Gaussian factor (group, campus, programme). Its correlations are estimated from historical YoY co-movement. Without this, group intervals were too narrow: the first prototype's 90% group interval missed the 2026 outcome.

**Hierarchy:** campus and group totals are sums of programme draws, so all levels agree by construction.

## Champion selection

- Mean CRPS ÷ intake on validation, at the backtest week nearest the live as-of week.
- A simpler model is kept if it is within 2% of the best.
- Roles: CHAMPION, then CHALLENGER A/B/C by score.
- Promotion happens only on out-of-sample wins.

## Metrics

- **Distribution:** CRPS ÷ intake, MAE of median ÷ intake, 50% and 90% interval coverage.
- **Events (meet target fill):** Brier score, log loss, reliability bins.

## Freezing

`lockbox.freeze` writes `<target>_<year>_w<week>.json` with:
- the forecast and model name
- a UTC timestamp
- a data-snapshot SHA-256
- a content hash

A different payload for an existing key raises `LockboxError`. Outcomes go in a sibling `.outcome.json`. `load()` checks the content hash to detect tampering.

## Failure registry

When a frozen forecast misses, classify it as one of: data error, model error, assumption error, execution failure, external shock, random variance. Do not change a good model because a 1-in-20 event happened once.

## Overrides

`register.override()` records the person, timestamp, reason, evidence, original forecast and new assumption. Overrides are scored like models, so the system learns where humans beat models.
