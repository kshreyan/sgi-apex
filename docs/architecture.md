# G. Architecture

```text
SOURCES                BRONZE                 SILVER                    GOLD                        DECISION LAYER
ERP / fee system ─┐    immutable snapshots    canonical, validated      metrics, forecasts,         control tower
Admissions CRM ───┤──▶ (parquet, append-only)─▶ keyed by entity_id ────▶ alerts, scenarios ───────▶ daily brief / board pack
Tally / bank ─────┤    source, ingestion_time  programme/year/week      data-quality score          decision register
HRMS, LMS, HIS ───┘                            DQ checks gate output     frozen forecasts (lockbox)  overrides → evaluation
                                   ▲
                       ENTITY REGISTRY (master): every row must resolve to a verified entity
```

## Components (milestone 1)

| Layer | Module | Notes |
|---|---|---|
| Master data | `entities/registry.py` | Validation, parent integrity, reconciliation gate |
| Ingest | `data/pipeline.py` | `ingest()` is the only source-specific code. Swap the synthetic call for an ERP/CSV reader |
| Quality | `data/quality.py` | Completeness, freshness, validity, uniqueness, consistency. Below 0.80 → `DQ-HOLD`, never an alert |
| Forecast | `forecasting/admissions/` | Models, engine (correlated MC + roll-ups), backtest |
| Scoring | `forecasting/scoring.py` | CRPS, coverage, Brier, log loss, reliability |
| Lockbox | `forecasting/lockbox.py` | Immutable prospective forecasts |
| Exceptions | `metrics/alerts.py` | GREEN/AMBER/RED with materiality. BLACK reserved |
| Decisions | `decisions/options.py`, `register.py` | Simulated options, robustness, append-only register, overrides |
| Reporting | `reporting/build.py`, `brief.py` | One build feeds the brief and the site JSON |
| UI | `site/` | Static GitHub Pages control tower. No server, no PII |

## Target stack (later phases)

- **Storage:** PostgreSQL holds the operational store and RBAC. DuckDB/Parquet holds analytics.
- **API:** FastAPI behind SSO/MFA.
- **Models:** statsmodels/PyMC for hierarchical Bayesian models, LightGBM where features justify it, OR-Tools/HiGHS for allocation.
- **Tracking and validation:** MLflow (or the JSON lockbox) for experiments, Pandera for schemas.
- **Ops:** Docker deploys, GitHub Actions CI.

Each technology must earn its place. Milestone 1 needs only numpy, pandas and pyarrow.

## Deployment boundary

The public GitHub Pages site may only ever show **synthetic or aggregated, non-sensitive** data. Real operational data runs on a private deployment (see `privacy_security.md`).
