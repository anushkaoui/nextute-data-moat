# Case brief — question-by-question answers

**Case B · The Data Moat**  
This is the answer key for the eight questions in the participant guide, and where each answer appears in the 14-slide deck.

## 1. Data capture — paper OMR, Excel, Google Forms, WhatsApp

**Answer.** The institute keeps its existing test workflow. We do not ask teachers to re-enter marks.

| Source | Capture path | Staff effort |
|---|---|---|
| Paper OMR | Existing OMR vendor CSV export, or front-desk scan. Schema supports `omr_template`, `omr_sheet`, item keys and confidence. Raw images are an adapter point; low-confidence scans go to human review. | One CSV drop or scan batch per test |
| Excel | Standard template; bulk upload; required columns, topic code, answer key, question range and duplicate checks. | Weekly upload; only red rows need attention |
| Google Forms | Today: Forms response CSV export. Next: native Forms API connector with OAuth and field mapping into the same import pipeline. | One-click export today; native sync later |
| WhatsApp | Inbound signed webhook accepts structured score entry (`roll`, `test`, `question`, `A–D`). Outbound parent reports are queued as utility templates with a provider adapter. | Teacher sends one structured message; no dashboard work |

**Minimum-effort design**
- Row-level quarantine: 1,205 demo rows → 1,200 accepted, 4 quarantined, 1 duplicate.
- Idempotent upload: the same file returns the same job; no duplicate imports.
- Commit is separate from review: staff see exceptions first, then commit valid rows.
- The teacher only reviews quarantined rows, not every mark.
- Every import is audited; raw data is retained for dispute resolution.

**Low bandwidth / offline**
- Server-rendered HTML, not a heavy SPA. Dashboard is ~16 KB; mastery grid is ~300 KB.
- Static CSS/JS is cacheable; no WebSocket or always-on connection is required.
- Data capture can happen offline in Excel/OMR; the CSV is uploaded when connectivity returns.
- Imports are queued and retried; WhatsApp/SMS is the fallback for a parent update.
- Honest boundary: this is low-bandwidth-first, not a fully offline PWA. A future offline capture sheet with background sync is a Should.

**Deck:** slides 3–5.

## 2. Data model — students, batches, tests, topics, attendance, fees, doubts

**Answer.** A tenant-scoped relational model with composite keys and RLS.

```text
institute
  ├── batch ── enrollment ── student ── student_pii
  ├── subject ── chapter ── topic
  ├── item ── item_topic ── topic
  ├── test ── test_item ── item
  ├── response ── student × test_item
  ├── attendance_session ── attendance_record
  ├── fee_plan ── fee_instalment
  ├── guardian ── consent ── parent_link
  ├── mastery_snapshot / prediction_snapshot / risk_snapshot
  ├── intervention ── report ── message_log
  └── import_job ── import_row / audit_event / job / model_version
```

**Why it enables insight**
- `response` is item-level, so Rasch and topic mastery are possible.
- `enrollment` links student to batch; `attendance_record` links to session.
- `fee_plan` / `fee_instalment` supports fee-default features.
- `mastery_snapshot`, `prediction_snapshot` and `risk_snapshot` are versioned, so every report is reproducible.
- `model_version` stores metrics and the model card; rules are labelled `rule_v1`.
- `consent` is purpose-bound; `audit_event` records who did what.

**Question tagging at scale**
1. CSV carries `topic_code`; the parser validates it against the taxonomy.
2. `item_topic` supports primary/secondary topic weights and confidence.
3. `tag_suggestion` stores model/LLM suggestions for human review.
4. A future embedding/LLM tagger proposes topics; low-confidence items go to an academic reviewer.
5. The taxonomy is versioned (`taxonomy_version`), so historical tags do not move under old reports.
6. Fallback is always manual: an unmapped question is quarantined, never silently labelled.

**Doubts.** The current pilot captures doubts indirectly through interventions and study plans. The designed table is `doubt(student_id, topic_id, source, text/media, status, resolved_by, linked_intervention_id)`, captured via WhatsApp/teacher and linked to topic mastery. This is a Should, not claimed as live.

**Deck:** slides 3, 6, 8, 10.

## 3. Learning analytics — mastery and difficulty calibration

**Answer.** Rasch/1PL is the backbone.

`P(correct) = logistic(θ_student − b_item)`

- Alternating damped updates; recenter θ each run; convergence in 41–76 iterations.
- Item difficulty `b` with a weak prior (`prior_b = 2`) and standard errors.
- Topic mastery: student ability θ plus topic item difficulties, with empirical-Bayes shrinkage (`κ = 8`) and a 120-day half-life recency weight.
- Uncertainty is stored (`uncertainty`, `evidence_count`); topics with `<3` responses are marked low evidence.
- 10 common anchor items per test support concurrent calibration; the schema can store a future bridge.
- We chose IRT over BKT because the pilot has item-level responses and small per-topic samples. BKT is a future option when there is a dense sequence of skills.

**Evidence:** θ sd 0.716–0.732; b sd 0.829–0.899; 181k responses. The synthetic Rasch recovery run reports θ correlation 0.922 and b correlation 0.995.

**Deck:** slides 3, 6, 8, 9.

## 4. Early-warning system

**Answer.** Three separate targets, separate thresholds, reasons attached.

| Target | Method | Horizon | Why |
|---|---|---|---|
| Disengagement | Calibrated logistic regression | 28 days | Learned from attendance/score/mastery/fee features |
| Falling behind | Transparent rule v1 | Next mock | Band lower bound + weakest mastery; insufficient outcome labels |
| Fee default | Transparent rule v1 | 30 days | Overdue amount + late instalments; 12+ months of default history needed to train |

**Features:** 28-day attendance, previous 28-day attendance, attendance trend, days since present, last score, two-mock mean, score delta, weakest/mean mastery, fee overdue.

**Guardrails**
- 60/20/20 train/calibration/test split; Platt scaling on calibration; top-10% review.
- Bands are triage aids, not decisions.
- Every score has a reason list; no black-box label.
- Fee amounts and fee-default risk are hidden from teachers; parent view never shows risk.
- Metrics are synthetic and labelled as such. The pilot uses a time-based holdout and a pre-registered bar.

**Deck:** slides 2–3, 6, 9.

## 5. Performance prediction — percentile range and uncertainty

**Answer.** We do not predict a JEE/NEET rank. We predict an **internal cohort percentile band**.

- Features: last mock score, two-mock mean, Rasch ability.
- Linear regression on historical mocks; hold-out 80% absolute-error quantile gives an interval.
- Output: point estimate + lower/upper bound + measured coverage.
- Observed 80% coverage: 74.3% / 84.0% / 90.0% across the three synthetic institutes; MAE 8.1–8.5 marks.
- The report says “internal percentile” and “not a JEE/NEET rank”; it shows the range, not a false point.
- The band is a communication device, not an admission guarantee.

**Deck:** slides 6–7, 9.

## 6. Generative AI layer — reports, plans, questions, doubts

**Answer.** Template-first, fact-locked, with an optional LLM behind guardrails.

- Parent report: facts object (attendance, score, strong/focus topics, band, advice) → reviewed English/Hindi template.
- Fact-lock validator rejects numbers not present in the facts object; the report carries a “Fact-locked” badge.
- LLM path is disabled by default; the deterministic template is the fallback. When enabled, the LLM receives the facts object, not raw student PII.
- Study plans: RAG-lite over a curated topic library; three weakest topics retrieve concept + drill briefs; composed deterministically. No external student data.
- Practice questions / doubt answers: designed as a future, teacher-reviewed workflow; not claimed as live. Content must be tagged to topic and reviewed before release.
- Cost control: cache by facts hash; batch/cached provider calls; token caps; no generation on page load; LLM cost budget per report. The pilot uses zero LLM calls.
- Hindi/English: reviewed templates and a Hindi QA pass; no machine translation at runtime.
- Safety: no student-facing chatbot, no invented numbers, no exam rank, no high-stakes automated decision.

**Deck:** slides 7–8.

## 7. Architecture — multi-tenant, secure, low-cost

**Answer.** A modular monolith: FastAPI + PostgreSQL + worker + object storage.

```text
Browser (owner/teacher/admin/parent token)
        │ signed session + CSRF
FastAPI (Vercel) ── server-rendered Jinja
        │ tenant context
PostgreSQL 16/17 (Supabase) ── RLS forced, PII split, audit
        │
Worker / offline analytics job ── snapshots + model versions
        │
Object storage ── raw CSV, future OMR images
```

- Tenant isolation: `app.institute_id` set transaction-local; RLS forced; no-context reads return zero.
- Roles: owner, academic head, admin, teacher, parent token.
- PII: names/DOB/guardian phone in `student_pii`; phone HMACed.
- Cost: one Postgres, one serverless web app, no GPU, no vector database, no per-institute cluster.
- Live deployment: Vercel + Supabase; `DATABASE_URL` uses the transaction pooler and prepared statements are disabled.

**Infrastructure + AI cost per student per month**

| Tier | Students | Service cost / year | Total / student / month | Infra + AI / student / month |
|---|---:|---:|---:|---:|
| Starter | 200 | ₹25,000 | ₹10.4 | ₹3–4 |
| Growth | 350 | ₹66,730 | ₹15.9 | ₹4–6 |

Infra + AI includes cloud/DB, storage, messaging, content retrieval and a small LLM budget. It excludes support/onboarding and sales. LLM is near zero in template mode; budget ₹1–2/student/month only if generation is enabled.

**Deck:** slides 8, 10, 12.

## 8. Privacy and safety — minors, consent, ownership, wellbeing

**Answer.** Privacy controls ship in the pilot.

| Control | How it works |
|---|---|
| Consent | Purpose-bound consent; `parent_communication` must be granted before report/link/WhatsApp |
| Data ownership | Institute is controller; we are processor; export/delete on request; no sale |
| Access | Tenant RLS; owner/teacher/admin roles; parent link is SHA-256 token, expiring and revocable |
| Teacher redaction | No fee amounts or fee-default risk; fee mentions in reasons redacted |
| Parent view | Attendance, scores, topics, internal band only; no risk labels or fees |
| Audit | Report, link, import, intervention and erasure events logged |
| Erasure | Verified request, 30-day workflow, audit trail |
| Retention | Raw import retained for dispute window; snapshots versioned; policy configurable |
| Wellbeing | No student-facing risk label; supportive report language; human-in-loop; escalation to counsellor |
| DPDP | Consent, minimisation, purpose limitation, DPA and legal review; not legal advice |

**Safety boundary:** risk scores support outreach; they are not automatic decisions, not shared with students, and not a rank. The parent report explicitly avoids exam-rank claims and states uncertainty.

**Deck:** slides 6–8, 10.

## What was actually stuck during deployment

1. The first remote seed used one large transaction and per-row `executemany` over the Supabase pooler. It looked stuck because there was no progress output; interrupting it rolled the transaction back.
2. We switched bulk rows to PostgreSQL `COPY` and loaded the already-seeded local dataset into Supabase. That produced the live 1,000-student / 181k-response database.
3. The first Vercel build had the wrong framework preset; setting `fastapi` fixed the function config.
4. The first live request returned 500 because Vercel installed a newer Starlette that requires `TemplateResponse(request, name, ...)`. We updated both template calls and redeployed.

**Live:** https://nextute-data-moat.vercel.app  
**Login:** `owner@demo.test` / `demo1234`
