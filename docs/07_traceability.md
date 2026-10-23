# Requirement traceability and submission checklist

## 1. Requirement map

| Area | Requirement | Status | Evidence |
|---|---|---|---|
| Tenancy | Multi-tenant institute isolation | Met | `db/migrations/0002_rls.sql`; pytest `test_tenant_rls_isolation`; no-context reads return 0 |
| Access | Role-based views (owner, teacher, admin, parent) | Met | `app/main.py`; signed session; teacher redaction test; parent token view |
| Ingestion | CSV import with validation | Met | `app/imports.py`; 1,205-row demo: 1,200 accepted / 4 quarantined / 1 duplicate |
| Ingestion | Google Forms | Partial | CSV export path works; native connector deferred |
| Ingestion | OMR | Deferred | Optional per brief; adapter point only; CSV is the working path |
| Assessment | Rasch / 1PL ability and item difficulty | Met | `app/analytics.py`; 181k responses; 41–76 iterations |
| Assessment | Topic mastery with uncertainty | Met | `mastery_snapshot`; shrinkage κ=8; 120-day half-life; low-evidence badges |
| Assessment | Anchor equating | Met | 10 common anchor items per test; concurrent calibration |
| Risk | 28-day disengagement | Met | Calibrated logistic; AUC/PR-AUC/Brier in model card |
| Risk | Falling behind | Met | Transparent `rule_v1`; percentile band + weakest mastery |
| Risk | Fee default | Met | Transparent `rule_v1`; overdue amount + late instalments |
| Explainability | Reasons for every score | Met | `risk_snapshot.reasons`, UI reason lists, model cards |
| Prediction | Internal percentile band | Met | Conformal-style 80% interval; coverage 74–90%; no exam rank |
| Reporting | English/Hindi parent report | Met | `app/reports.py`; 30 reports per institute; template-first |
| Reporting | Fact lock / no hallucinated numbers | Met | Facts object + template; LLM path off; validator design |
| Communication | WhatsApp report delivery | Partial | Queue + `message_log`; provider adapter stubbed |
| Communication | WhatsApp structured entry | Met | `/webhooks/whatsapp`; signed secret; response stored as `form` |
| Workflow | Intervention tracking | Met | `/students/{id}/interventions`; audited; UI list |
| Workflow | Study plan / RAG-lite | Met | `content_resource`; 3 weakest topics; curated concept + drill |
| Privacy | Consent gating | Met | `parent_communication` checked before report/link/WhatsApp |
| Privacy | PII separation and minimisation | Met | `student_pii`; guardian phone HMACed; tenant RLS |
| Privacy | Teacher fee redaction | Met | Role filter + template `reason_text`; verified in browser |
| Privacy | Parent no-risk/no-fee view | Met | Parent template; verified |
| Privacy | Audit trail | Met | `audit_event` on report/link/import/intervention/erasure |
| Privacy | Erasure request | Met (workflow stub) | `deletion_request`; owner/admin UI; 30-day note |
| Security | Auth, session, CSRF, headers | Met | scrypt; HMAC cookie; CSRF token; CSP/frame-deny/nosniff |
| AI | Optional LLM with guardrails | Partial | Template-first; LLM disabled; fact-lock design |
| AI | RAG | Met (narrow) | Curated retrieval; deterministic composition; no external student data |
| Business | Pricing and unit economics | Met | Financial model; ₹35/₹55; 65% contribution |
| GTM | Wedge and design-partner plan | Met | Business plan; 10 Patna design partners; 90-day pilot |
| Demo | Working end-to-end product | Met | Screenshots; 6/6 tests; page health; 7.7s rebuild |
| Submission | Deck and validation report | Met | `docs/03_pitch_deck.pdf`; `docs/02_validation_report.pdf` |

## 2. Scope decisions

### Must

- Multi-tenant, role-aware analytics platform.
- CSV ingestion with validation and quarantine.
- Rasch mastery, three risk targets, internal percentile band.
- Bilingual parent report with privacy controls.
- Explainable reasons and teacher interventions.
- DPDP-pilot controls: consent, RLS, audit, erasure workflow.
- A working demo, not a mock.

### Should

- Native Google Forms connector.
- WhatsApp provider delivery (not just queue).
- OMR adapter.
- Parent-link revocation UI and shorter TTL.
- Time-based model validation on real data.
- Benchmark network with consented aggregates.

### Defer

- Full OMR scanner.
- Student mobile app.
- Payments / fee collection.
- Content marketplace / LMS.
- Cross-institute benchmark in the UI.
- LLM generation on by default.

## 3. Rubric mapping

| Criterion | Weight | What we show | Where |
|---|---:|---|---|
| Architecture | 25 | Modular monolith, 36+ tables, forced RLS, job queue, audited roles | `db/migrations/`, `app/core.py`, `app/main.py` |
| DS / ML / AI | 25 | Rasch, shrinkage, calibration, rules, RAG-lite, honest validation | `app/analytics.py`, validation report |
| Feasibility + privacy/safety | 20 | Consent, PII split, teacher redaction, parent no-risk, erasure, audit | `app/main.py`, `db/migrations/0002_rls.sql`, validation report |
| Revenue | 20 | ₹35/₹55, 65% contribution, CAC payback, break-even, 3-year model | `docs/04_business_plan.md`, `docs/institute_intelligence_financial_model.xlsx` |
| GTM | 10 | Patna wedge, 10 design partners, paid pilot, referral/distributor | `docs/04_business_plan.md`, deck slides 13–14 |

## 4. Evidence files

| File | Purpose |
|---|---|
| `docs/01_solution_overview.md` | Problem, architecture, ML, privacy, scope |
| `docs/02_validation_report.pdf` | Validation report (7 pages) |
| `docs/03_pitch_deck.pdf` | 14-slide competition deck |
| `docs/04_business_plan.md` | Market, pricing, GTM, financials, risks |
| `docs/05_demo_script.md` | 7-minute and 3-minute demo |
| `docs/06_qna.md` | Objection handling |
| `docs/institute_intelligence_financial_model.xlsx` | Editable unit economics and 3-year P&L |
| `docs/assets/` | Product screenshots |
| `tests/` | 6 automated tests |
| `db/tests/rls_smoke.sql` | Original RLS/job-queue smoke test |

## 5. Final checks

```bash
python3 -m pytest -q                         # 6 passed
python3 -m compileall -q app                 # no syntax errors
python3 scripts/apply_migrations.py          # all migrations skipped
curl -s http://127.0.0.1:8000/healthz        # {"status":"ok"}
```

Manual checks:
- Owner dashboard: three risks, no missing cards.
- Teacher dashboard: no ₹ amounts, no fee-default target.
- Parent link: no risk/fee labels.
- Import: quarantined rows first.
- Report: “Template-generated”, not “template_fallback”.
- Study plan: three weakest topics with curated briefs.

## 6. Known gaps before production

1. Real, consented institute data and time-based validation.
2. Native Google Forms OAuth connector.
3. OMR scanning pipeline.
4. WhatsApp Business provider integration and delivery receipts.
5. Legal review of DPDP notice, consent language, DPA, retention and breach SLA.
6. Pen test and secrets management.
7. Parent-link revocation UI and shorter default expiry.
8. CI/CD, backups, observability and on-call.
9. Pricing validation with paid pilots.
10. Model monitoring and drift alerts.
