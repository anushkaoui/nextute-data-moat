# Validation report

**Product:** Institute Intelligence — Case B “The Data Moat”  
**Version:** pilot-1.0  
**Date:** 23 October 2026  
**Status:** prototype validated on synthetic data; ready for a controlled design-partner pilot

## Executive summary

The prototype works end to end: 3 synthetic institutes, 1,000 students, 181,201 responses and 52,000 attendance records flow through CSV ingestion, Rasch mastery, three risk targets, intervention tracking, bilingual reports and parent links.

- **Functional:** 6/6 automated tests pass; all primary pages return 200; import, commit, report and parent-link flows completed.
- **Model:** Rasch converges in 41–76 iterations. Disengagement AUC is 0.92–1.00 on held-out synthetic splits. Internal percentile coverage is 74–90% against a nominal 80%; MAE is 8.1–8.5 marks.
- **Privacy:** tenant isolation, consent gating, teacher fee redaction and parent no-risk/no-fee views were verified.
- **Performance:** dashboard p50 99 ms and p95 257 ms under 100 requests at 10-way concurrency; full analytics rebuild for 181k responses takes 7.7 s.
- **Caveat:** this is synthetic data with a designed dropout signal. The AUC is not a real-world claim. The next step is a time-based, two-institute pilot.

## 1. Scope of validation

| In scope | Out of scope |
|---|---|
| CSV import, validation, quarantine, commit | Native Google Forms connector |
| Rasch and topic mastery | Production OMR scanner |
| Disengagement, falling-behind, fee-default scores | Real payment collection |
| Internal percentile band | JEE/NEET rank prediction |
| English/Hindi report, parent link | Live WhatsApp provider integration |
| RLS, roles, consent, audit, erasure request | Legal sign-off under DPDP |
| Synthetic pilot at 3 institutes | Real institute outcomes |

## 2. Environment and data

| Item | Value |
|---|---|
| Application | FastAPI + Jinja, Python 3.14 |
| Database | PostgreSQL 16.15, Docker, port 55432 |
| Tenants | 3: Patna NEET Academy (400), Gaya Success Point (350), Patna JEE Circle (250) |
| Students | 1,000 |
| Tests | 55 (54 seeded + 1 imported) |
| Items | 510 |
| Responses | 181,201 |
| Attendance records | 52,000 |
| Reports | 30 per institute, English + Hindi |
| As-of date | 30 September 2026 |
| Raw import | 1,205 rows: 1,200 accepted, 4 quarantined, 1 duplicate |

The synthetic generator creates ability, topic affinity, attendance decline and withdrawal. That makes the data useful for testing plumbing and failure modes, but it also makes the risk metrics optimistic.

## 3. Functional validation

| ID | Test | Method | Result |
|---|---|---|---|
| V1 | Tenant isolation | pytest: count students per tenant; bare connection | Pass: 350 / 250 / 400; bare connection 0 |
| V2 | Cross-tenant visibility | tenant A query filtered by tenant B | Pass: 0 foreign rows |
| V3 | Auth and redirects | pytest + TestClient | Pass: unauth 303; bad login 200; good login 303 |
| V4 | Teacher fee redaction | Playwright text scan of dashboard/student | Pass: no ₹ amounts; fee-default target hidden |
| V5 | Parent privacy | Playwright parent link | Pass: report visible; no risk label or fee amount |
| V6 | Consent enforcement | revoke `parent_communication`, generate report | Pass: `{"error": "consent"}` |
| V7 | CSV validation | 1,205-row demo file | Pass: 1,200 accepted / 4 quarantined / 1 duplicate |
| V8 | Idempotent upload | same content hash twice | Pass: same job id, `existing=True` |
| V9 | Commit | import job commit | Pass: 1,200 responses, 1 test, 0 new students |
| V10 | WhatsApp entry | signed webhook, roll/test/question/answer | Pass: response stored as `form`, confidence 0.80, marks 4 |
| V11 | WhatsApp report queue | report page action | Pass: `message_log` row queued with utility template |
| V12 | Erasure request | owner action on student | Pass: pending request + audit event |
| V13 | Page health | owner session, 6 pages | Pass: 200 for dashboard, students, mastery, risk, import, report, status |
| V14 | Automated suite | `python3 -m pytest -q` | Pass: 6/6 |

### Import evidence

```text
total: 1,205
accepted: 1,200
quarantined: 4
duplicate: 1
commit: inserted 1,200; duplicate 0; tests_created 1; students_created 0
```

The four quarantine rows exercise unknown topic code, malformed date, missing answer key and out-of-range question number. These are visible first in the review screen.

## 4. Model validation

### 4.1 Rasch / mastery

| Institute | Students | Items | Responses | θ sd | b sd | Iterations |
|---|---:|---:|---:|---:|---:|---:|
| Patna NEET Academy | 400 | 169 | 69,599 | 0.718 | 0.829 | 46 |
| Gaya Success Point | 350 | 140 | 59,818 | 0.732 | 0.899 | 76 |
| Patna JEE Circle | 250 | 146 | 42,781 | 0.716 | 0.887 | 41 |

θ sd near 0.7 is plausible for a mixed Class 11/12/dropper cohort. The item spread (b sd 0.83–0.90) means the tests contain a usable range of difficulty. Convergence is stable; no divergence was observed after damping and recentering.

### 4.2 Disengagement (28-day)

| Institute | Positives | Base rate | AUC | PR-AUC | Brier | Recall @10% | Precision @10% |
|---|---:|---:|---:|---:|---:|---:|---:|
| Patna NEET Academy | 24 | 6.0% | 0.992 | 0.925 | 0.035 | 1.00 | 0.63 |
| Gaya Success Point | 19 | 5.4% | 1.000 | 1.000 | 0.016 | 1.00 | 0.57 |
| Patna JEE Circle | 15 | 6.0% | 0.922 | 0.738 | 0.025 | 0.67 | 0.40 |

**Interpretation.** The model ranks synthetic withdrawals well, especially in Patna NEET. Gaya’s perfect AUC reflects a clean synthetic separation, not model superiority. JEE Circle is the most honest stress case: 15 positives, AUC 0.922, top-10% recall 0.67. The pilot must replace this with time-based validation on real withdrawals.

### 4.3 Internal percentile band

| Institute | n | MAE (marks) | 80% interval coverage | q80 absolute error |
|---|---:|---:|---:|---:|
| Patna NEET Academy | 400 | 8.07 | 90.0% | 15.6 |
| Gaya Success Point | 350 | 8.38 | 74.3% | 12.3 |
| Patna JEE Circle | 250 | 8.47 | 84.0% | 14.6 |

Nominal coverage is 80%. The observed range (74–90%) is acceptable for a pilot but shows that the interval is not perfectly calibrated across cohorts. Reports label the interval as a range and explicitly say it is not a JEE/NEET rank.

### 4.4 Rule-based targets

| Institute | Falling behind high/medium | Fee default high/medium |
|---|---:|---:|
| Patna NEET Academy | 48 / 122 | 20 / 136 |
| Gaya Success Point | 9 / 88 | 12 / 123 |
| Patna JEE Circle | 19 / 64 | 4 / 92 |

These are deliberately rules, not models. They are explainable and tunable, but they are not validated predictors. Fee amounts are visible only to owner/academic head/admin.

## 5. Privacy and security validation

| Control | Evidence | Verdict |
|---|---|---|
| RLS | per-tenant counts; no-context returns 0; cross-tenant 0 | Pass |
| Session | HMAC-signed cookie; 12-hour expiry | Pass |
| Passwords | scrypt, constant-time verification | Pass |
| CSRF | state-changing forms include session token | Pass |
| CSP/headers | frame-deny, nosniff, same-origin | Pass |
| Parent token | SHA-256 stored; raw token only in link; 90-day expiry | Pass |
| Consent gate | report and parent link blocked after withdrawal | Pass |
| Teacher redaction | no ₹ on teacher dashboard/student; fee-default hidden | Pass |
| Parent content | no risk labels or fee amounts | Pass |
| Audit | report, link, import, intervention, erasure events | Pass |
| Erasure | pending request with 30-day workflow | Pass (workflow stub) |

**Residual risks.** The WhatsApp provider is stubbed. The parent link is bearer-token based; anyone with the link can view it until expiry. Production needs rate limiting, link revocation UI and a shorter default lifetime. The dev database uses a known password and should never be deployed as-is.

## 6. Performance and reliability

| Metric | Result | Method |
|---|---|---|
| Dashboard latency | 74 ms | single authenticated request |
| Students page | 58 ms | 200 rows |
| Mastery grid | 88 ms | 300 KB HTML |
| Risk page | 34 ms | top 120 rows |
| Status page | 27 ms | model cards |
| Dashboard p50 / p95 | 99 / 257 ms | 100 requests, 10 workers |
| Analytics rebuild | 7.7 s | 3 institutes, 181k responses |
| Database size | 156 MB | `pg_database_size` |

The current build is comfortable for a 3-institute pilot. The mastery page is the heaviest; at 10× students it needs pagination or a materialised grid.

## 7. Failure modes and mitigations

| Failure | Current behaviour | Next step |
|---|---|---|
| Bad CSV | row-level quarantine; commit blocked until reviewed | Add downloadable error CSV |
| Duplicate upload | same job returned by content hash | Show prior commit status clearly |
| Analytics crash | job transaction rolls back; prior snapshots remain | Add job retry/alerting |
| Wrong tenant | RLS returns zero rows | Keep tests in CI |
| Consent withdrawn | report/link generation refused | Add consent expiry reminders |
| Parent link leaked | bearer token valid until expiry | Add revoke button + shorter TTL |
| Model drift | versioned snapshots | Monthly backtest + drift alert |
| Fee data leaked to teacher | role filter + template redaction | Add API-level test |
| LLM hallucination | template path; fact validator | Keep LLM off until eval set exists |

## 8. Limitations

1. **Synthetic outcomes.** Withdrawal is generated from attendance and fee behaviour, so the model partly learns the generator. AUC 1.0 is not evidence of real-world performance.
2. **Random split, not time split.** The pilot must validate on future cohorts to avoid leakage.
3. **Small positive count.** 15–24 positives per institute gives wide confidence intervals.
4. **Rules are not predictors.** Fee-default and falling-behind scores are triage heuristics.
5. **No real institute data.** No DPDP notice, DPA or parent consent text has been legally reviewed.
6. **No native Forms/OMR.** CSV export is the working path; OMR is an adapter point.
7. **WhatsApp is partial.** Inbound structured entry works; outbound delivery is queued, not sent.
8. **Single region.** Patna/Bihar pricing and language assumptions are untested.

## 9. Pilot plan

**Design:** 2 institutes, 8 weeks, 300–600 students, one control batch per institute where feasible.

| Hypothesis | Measure | Success bar |
|---|---|---|
| H1: flags are actionable | teacher-rated usefulness of top-20 flags | ≥70% “actionable” |
| H2: onboarding is light | upload → first insight | <30 minutes |
| H3: parents engage | report open / reply rate | >60% open, >15% reply |
| H4: retention improves | 28-day attendance vs control | +3 percentage points |
| H5: willingness to pay | signed LOI / paid pilot | ≥₹35/student/month |

**Guardrails:** no student-facing risk labels; no exam-rank claims; no fee data to teachers; consent before parent communication; weekly model review; kill switch for reports.

**Decision gate:** proceed to paid rollout only if H1, H2 and H5 pass and no privacy incident occurs.

## 10. Recommendation

Proceed to a controlled design-partner pilot. The prototype is strong enough to test workflow, trust and willingness to pay. It is not yet evidence that the risk model predicts real dropout. The next validation must be temporal, on real consented data, with a pre-registered success bar.

## Appendix A — Reproduce

```bash
python3 scripts/apply_migrations.py
python3 -m app.synth
python3 -m app.analytics
python3 -m pytest -q
uvicorn app.main:app --port 8000
```

## Appendix B — Evidence index

- `tests/test_model.py`: Rasch recovery, mastery bounds.
- `tests/test_integration.py`: RLS, import quarantine, consent, API roles.
- `db/tests/rls_smoke.sql`: original RLS/job-queue smoke test.
- `docs/assets/`: dashboard, student, report, risk, import and status screenshots.
- `docs/institute_intelligence_financial_model.xlsx`: unit economics and 3-year plan.
