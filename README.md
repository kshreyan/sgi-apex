# SGI APEX

**Chairman's Intelligence and Prediction Operating System** for the Subhwanti Sudama Rai Foundation and the Subhwanti Group of Institutions (Siwan and Bettiah, Bihar).

**Live control tower:** https://kshreyan.github.io/sgi-apex/

> ⚠️ **All operational numbers in this repository and on the site are synthetic.** They come from a seeded simulator so the full decision loop can be demonstrated. The entity registry is the only part built from real public research. Do not use any figure for a real decision.

## What milestone 1 delivers

One complete closed loop (spec PART LXXVII):

```text
historical admissions → clean (silver) → programme forecast → seat-fill probability
→ chairman alert → action options → decision log → actual result → forecast + decision evaluation
```

| Capability | Where |
|---|---|
| Entity registry with sources and confidence. Group roll-ups blocked on unresolved entities | `configs/entities/`, `src/sgi_apex/entities/`, [`docs/entity_registry.md`](docs/entity_registry.md) |
| Bronze/silver/gold pipeline with a data-quality score on every forecast. Real-export adapter with a validation report | `src/sgi_apex/data/`, [`docs/data_ingest.md`](docs/data_ingest.md) |
| Four models (`seasonal_naive`, `pace_own`, `pace_pooled`, `bayes_blend`) with champion/challenger roles | `src/sgi_apex/forecasting/admissions/models.py` |
| Correlated Monte Carlo draws (group, campus, programme). Hierarchy agrees by construction | `engine.py` |
| Rolling-origin backtest, 2025 lockbox, CRPS/coverage/Brier/reliability | `backtest.py`, `scoring.py` |
| Prediction lockbox: frozen, hash-checked, refuses overwrite | `src/sgi_apex/forecasting/lockbox.py`, `artifacts/forecasts/` |
| GREEN/AMBER/RED exceptions with materiality rules | `src/sgi_apex/metrics/alerts.py` |
| Options simulated with ROBUST/MODERATE/FRAGILE grading | `src/sgi_apex/decisions/options.py` |
| Append-only decision register and override log | `src/sgi_apex/decisions/register.py`, `artifacts/decisions/` |
| Chairman daily brief and static control tower | `src/sgi_apex/reporting/`, `site/` |

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
make setup
make test          # 33 tests: unit, leakage, forecasting
make all           # full loop → artifacts/ + site/data/
make serve         # http://localhost:8000
```

CLI:

```bash
sgi run | chairman-brief | registry | ingest | forecast admissions | risks | decisions | backtest
sgi ingest --file export.csv [--finals finals.csv] [--dry-run]   # real admissions export → validated silver
```

`sgi institution-health | simulate | benchmark | expansion-screen` are registered but intentionally exit with "planned".

## Answers to the spec's required first response

| Section | Document |
|---|---|
| A–C. Organisation map, public footprint, hospital verification | [`docs/entity_registry.md`](docs/entity_registry.md) |
| D–E. Technology audit, data availability matrix · H. Prediction targets | [`docs/data_availability.md`](docs/data_availability.md) |
| F. Strategic gap analysis | [`docs/strategic_gap_analysis.md`](docs/strategic_gap_analysis.md) |
| G. Architecture | [`docs/architecture.md`](docs/architecture.md) |
| I. Security and privacy | [`docs/privacy_security.md`](docs/privacy_security.md) |
| J–L. 90-day plan, first files, first milestone | [`docs/build_plan_90_day.md`](docs/build_plan_90_day.md) |
| Protocol, governance, limitations | [`docs/forecasting_protocol.md`](docs/forecasting_protocol.md), [`docs/governance.md`](docs/governance.md), [`docs/limitations.md`](docs/limitations.md) |

## Key findings so far

- **Hospital in Chakia: not verified.** No public record links the Foundation to a Chakia hospital. It is registered with confidence `none`, and no healthcare engine will be built until internal documents confirm it.
- **Most sanctioned intakes are placeholders.** These must come from approval letters before real use.
- **The prototype caught its own flaw.** Independent programme draws made group intervals too narrow, and the 2026 actual fell outside them. Correlated draws fixed this. The fix is documented in the forecasting protocol.

## Switching to real data

1. Update intakes in `configs/entities/programmes.csv` from the approval letters.
2. Run `sgi ingest --file <export> --finals <registrar finals> --dry-run`. Fix every ERROR, review the WARNs, then run again without `--dry-run`. Accepted formats and rules are in [`docs/data_ingest.md`](docs/data_ingest.md).
3. Forecasting on that silver table is the next build step. Real outputs go to a private deployment, never to public Pages (see [`docs/privacy_security.md`](docs/privacy_security.md)).

## Repository layout

```text
configs/   entities · metrics · models · alerts · permissions
docs/      operating model, registry, architecture, protocol, governance, privacy, plans, limitations
src/sgi_apex/  data · entities · forecasting · metrics · decisions · reporting · api (stub) · cli
tests/     unit · leakage · forecasting
artifacts/ forecasts (lockbox) · decisions (register) · reports (briefs)
site/      GitHub Pages control tower
```
