# Institute Intelligence — solution overview

**Case B · The Data Moat · Nextute × Finance Club IIT Patna 2026**

## 1. The problem

A Tier-2 coaching institute already records the signals that predict dropout: attendance, weekly test scores, topic-level errors and fee behaviour. The data sits in OMR sheets, Excel exports and WhatsApp groups. Owners see it too late, teachers cannot act per topic, and parents receive a rank rather than an explanation.

The product is not another LMS. It is an analytics and communication layer that sits on top of the tools an institute already uses.

**Primary user:** owner/academic head of a 150–1,000-student NEET/JEE institute in Patna or a similar Tier-2 city.

**Jobs to be done:**
1. “Which students are slipping, and why?”
2. “Which topics should I reteach this week?”
3. “Give me a defensible, bilingual update I can send to a parent.”
4. “Keep our data private and do not create a student-facing rank.”

## 2. Product pillars

| Pillar | What the prototype does |
|---|---|
| Ingest | CSV/Google Forms export → validate → quarantine bad rows → commit; idempotent jobs |
| Measure | Rasch/1PL ability, topic mastery with shrinkage and recency, anchor equating |
| Predict | Disengagement (28d), falling behind, fee default — each with reasons |
| Explain | Internal percentile band, not an exam rank; parent report from locked facts |
| Act | Teacher-owned interventions, retrieval-grounded study plan, WhatsApp report queue |
| Protect | Tenant RLS, consent gates, teacher fee redaction, audit, erasure workflow |

## 3. Architecture

```text
┌──────────────────────────────────────────────────────────────────┐
│ Browser                                                          │
│ Owner / Teacher / Admin / Parent (token link)                    │
└───────────────┬──────────────────────────────────────────────────┘
                │ HTTPS, signed session, CSRF
┌───────────────▼──────────────────────────────────────────────────┐
│ FastAPI modular monolith                                          │
│ auth · imports · dashboard · mastery · risk · reports · webhooks  │
│ server-rendered Jinja templates                                   │
└───────┬───────────────────────────────┬──────────────────────────┘
        │ SQL (tenant context)          │ job queue
┌───────▼───────────────────────┐  ┌────▼─────────────────────────┐
│ PostgreSQL 16                 │  │ Worker / scheduler           │
│ tenant RLS · PII side table   │  │ parse → analytics → reports  │
│ responses · snapshots · audit │  └──────────────────────────────┘
└───────┬───────────────────────┘
        │
┌───────▼───────────────────────┐
│ Object storage (design point) │
│ raw CSV, future OMR images    │
└───────────────────────────────┘
```

**Why a modular monolith:** the pilot has one deployment, one database and a small team. Separating ingestion, analytics and rendering into services would add operational cost without improving the first 10 customers. The job table and snapshot tables preserve a clean split if a worker is extracted later.

## 4. Data flow

1. Institute uploads a CSV (or Google Forms export).
2. Parser validates required columns, test metadata, topic codes, answer keys, duplicates and response ranges.
3. Valid rows are quarantined/accepted at row level; a separate commit writes students, tests, items and responses.
4. Analytics job fits Rasch, writes item difficulty and topic mastery, trains the disengagement model, builds percentile bands and rule-based risks, and seeds parent reports.
5. Teacher sees risk lists, reasons, mastery and a study plan; opens an intervention.
6. Owner generates a bilingual report, creates a 90-day parent link, or queues a WhatsApp utility message.
7. Parent sees only attendance, scores, topics and percentile band — never risk labels or fees.

## 5. ML design

### 5.1 Rasch / 1PL

For student ability θ and item difficulty b:

`P(correct) = logistic(θ − b)`

- Alternating updates with damping, recentering each run.
- Empirical-Bayes shrinkage on topic ability (`κ = 8`) so a topic with two questions does not swing wildly.
- 120-day half-life recency weight.
- Concurrent calibration with 10 common anchor items per test; no separate equating step is needed for the pilot, but the schema stores anchor identity for a future bridge.
- Output: topic mastery probability, uncertainty and evidence count. Low evidence is labelled, not hidden.

### 5.2 Disengagement

- Features: 28-day attendance, previous 28-day attendance, trend, days since present, last score, two-test mean, score delta, weakest/mean mastery, fee overdue.
- 60/20/20 train/calibration/test split; Platt scaling on the calibration split; L2 logistic regression in numpy.
- Metrics: AUC, PR-AUC, Brier, recall/precision at the top 10%.
- Bands are triage aids. The report never shows a risk label to a parent.

### 5.3 Falling behind and fee default

With fewer than 12 months of outcome history, a trained model would be false precision. These are transparent rules:

- Falling behind uses the lower bound of the 80% internal percentile band and the weakest topic mastery.
- Fee default uses overdue amount and late instalments, with explicit thresholds.
- Both are labelled “rule_v1” in the model card and in the UI.

### 5.4 LLM and RAG

- Report generation is **template-first**. Facts are locked in a JSON object; a validator rejects numbers not present in the facts. The LLM path is disabled by default.
- Study plans use **retrieval-grounded composition**: the three weakest topics retrieve curated concept and practice briefs from the institute library. No student data is sent to an external model.
- This is intentionally narrow: the pilot should not invent advice or hallucinate a score.

## 6. Privacy and security

| Control | Implementation |
|---|---|
| Tenant isolation | RLS forced on tenant tables; `current_tenant()` from transaction-local setting |
| PII separation | Names/DOB/guardian phone in `student_pii`; phone HMACed |
| Auth | scrypt password hashes; HMAC-signed session cookie; 12-hour expiry |
| CSRF | Session-bound token on every state-changing form |
| Role redaction | Teacher cannot see fee amounts or fee-default risk; parent sees no risk/fees |
| Consent | `parent_communication` must be granted before report/link/WhatsApp |
| Audit | Report generation, parent link, imports, interventions, erasure requests |
| Erasure | Owner/admin logs a verified request; 30-day execution workflow |
| Headers | CSP, frame-deny, nosniff, same-origin referrer |
| Data minimisation | Parent link is token-hashed, expiring and revocable |

## 7. Scope decisions

| Requirement area | Status | Note |
|---|---|---|
| Multi-tenant platform, roles | Implemented | RLS + owner/teacher/admin |
| CSV / Google Forms ingestion | Implemented via CSV export | Native Forms connector is a follow-up |
| OMR ingestion | Deferred | Optional in the brief; CSV is the working path |
| Rasch mastery | Implemented | 181k responses across 3 institutes |
| Three risk targets | Implemented | One trained, two rules |
| Percentile band | Implemented | Internal only, explicit interval |
| Bilingual parent reports | Implemented | EN/HI template, fact lock |
| Interventions | Implemented | Teacher-owned, audited |
| WhatsApp | Partial | Inbound webhook + queued outbound stub |
| RAG | Implemented (narrow) | Curated retrieval, deterministic composition |
| DPDP controls | Implemented at pilot level | Not legal advice; DPA/notice review pending |

## 8. What is deliberately not built

- A native mobile app.
- A full LMS, content marketplace or live class stack.
- A student-facing chatbot.
- Real payment collection.
- A production OMR scanner.
- Cross-institute benchmarking in the UI (schema supports consented aggregates).
