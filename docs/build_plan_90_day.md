# J. 90-day build plan

| Weeks | Deliverable | Exit criterion |
|---|---|---|
| 0 (done) | Repo, entity registry from public sources, synthetic end-to-end admissions loop, control tower on Pages | `make test` green; site live |
| 1–2 | Discovery interviews with the owners in `data_availability.md`. Collect approval letters; fix intakes; close registry open questions; verify hospital | All `programmes.csv` intakes sourced to a letter; registry confidence ≥ medium everywhere except items under investigation |
| 2–4 | **Real admissions ingest** (tooling done: `sgi ingest --file`, see `data_ingest.md`; awaiting export): CSV/Excel adapter for ≥5 past cycles (weekly cumulative enquiries/applications/enrolments). Schema + value checks. DQ report | Silver table reconciles to final enrolment per institution within ±1 |
| 4–5 | (tooling done: `sgi run --real --out`) Re-run backtest on real data. Freeze the first real prospective forecast. Set alert thresholds with the Head of Admissions | Champion chosen out of sample; lockbox scored once |
| 5–6 | Private deployment: Postgres + FastAPI + SSO. Site served behind login for real data; public site stays synthetic | Security checklist in `privacy_security.md` passed |
| 6–8 | Decision workflow live: DG/HoA propose, chairman decides, outcomes logged. First geo or channel experiment to measure counselling uplift | ≥1 real decision in register with owner and deadline |
| 8–10 | **M2 cash loop**: fee billing + collections + payroll + opex + capex → 13-week cash forecast, liquidity scenarios | Forecast reconciles to Tally opening balance |
| 10–12 | Compliance register v1 (regulator, approval, renewal, document, owner, deadline) from the document-evidence audit. Board-pack v1 | Every approval has a document and a renewal date |
| 13 | Review: forecast accuracy vs frozen, decision turnaround, data-quality trend. Decide M3 scope | Written postmortem in `research/` |

## K. Files created in milestone 1

See the repository tree in the README. Key files:
- `configs/entities/entity_registry.csv`
- `configs/entities/programmes.csv`
- `src/sgi_apex/**`
- `tests/**` (unit, leakage, forecasting)
- `site/**`
- `docs/*.md`

## L. First executable milestone

`make all` runs: ingest → silver → backtest (validation + lockbox) → champion → frozen week-10 forecast → alerts → options → decision register → outcome → loop evaluation → brief + site data.
