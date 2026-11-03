# I. Privacy and security plan

Governing law: Digital Personal Data Protection Act 2023 and the DPDP Rules. Health data also follows clinical-establishment and ABDM norms, with NABH information-management standards where applicable.

## Data sensitivity classes

| Class | Examples | Controls |
|---|---|---|
| S4: health-identifiable | patient records, diagnoses | Never leaves the hospital information system. Analytics only on aggregated, de-identified extracts (k ≥ 10 per cell). Never sent to general-purpose LLM APIs |
| S3: personal | student and employee PII, fee ledgers, grievances | Encrypted at rest and in transit. Role-scoped access. Pseudonymised IDs in the analytics layer. Retention schedule |
| S2: confidential business | finance, contracts, forecasts, decisions | RBAC, audit log, private deployment only |
| S1: public | registry facts from public sources, synthetic demo | May be published (this site) |

## Controls

- **Access:** least privilege with RBAC (`configs/permissions/roles.json`) and SSO with MFA for every human user.
- **Secrets:** kept in a vault or GitHub encrypted secrets. Never in the repo (`.env.example` holds names only).
- **Audit:** append-only logs for data access, decisions and overrides.
- **Backups:** daily encrypted, offsite copy, restore tested quarterly. RPO 24 h, RTO 8 h for the control tower. Source systems remain the system of record, so APEX is never a single point of failure.
- **Supply chain:** dependency scanning (Dependabot) and pinned versions. SBOM before production.
- **Application security:** OWASP ASVS L2 for the future API.
- **DPDP duties:** notice and consent at admission (purpose: education administration and student support), data-principal rights workflow, breach notification within 72 h, Data Protection Officer named.

## AI safety boundaries

An LLM or model may **never** silently:
- change accounting, student or clinical records
- approve admissions
- move money
- hire or fire
- sign contracts
- commit capital

Student- and employee-level predictions are **support signals only**. They need explainability, human review and fairness monitoring: false-positive and false-negative rates and calibration across lawful cohorts.
