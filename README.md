# Institute Intelligence — Case B “The Data Moat”

A working, privacy-first analytics prototype for Tier-2/3 NEET/JEE coaching institutes. It turns CSV test exports, attendance and fee data into topic mastery, three explainable risk scores, intervention tracking and bilingual parent reports.

Built for **Nextute × Finance Club IIT Patna — Case B: The Data Moat (2026)**.

## What is implemented

- Multi-tenant FastAPI + PostgreSQL app with row-level security and role-based views.
- CSV import with required-column checks, topic-code validation, quarantine rows, duplicate detection, idempotent job creation and an explicit commit step.
- Rasch/1PL ability and topic mastery with empirical-Bayes shrinkage, 120-day recency weighting and anchor-item equating.
- Three risk targets: 28-day disengagement (calibrated logistic model), falling behind and fee default (transparent rules where outcome history is thin).
- Internal percentile band with conformal-style 80% interval — never a JEE/NEET rank.
- Bilingual (English/Hindi) parent reports generated from a locked facts object; optional LLM path is disabled by default, deterministic template is the fallback.
- Retrieval-grounded study plan from a curated topic library (RAG-lite, no student data sent to an external model).
- Consent-aware report generation, teacher fee redaction, parent view with no risk/fee labels, audit events and a DPDP erasure-request workflow.
- WhatsApp webhook for structured score entry and a queued utility-template message log for report delivery.
- pytest regression suite plus a passing RLS/isolation test.

## Quick start

```bash
python3 -m pip install -r requirements.txt
# for tests/playwright:
# python3 -m pip install -r requirements-dev.txt

# Postgres 16 (already running in the development environment)
docker run --name dm-pg -e POSTGRES_PASSWORD=postgres -p 55432:5432 -d postgres:16

# Apply schema once; safe to re-run
python3 scripts/apply_migrations.py

# Synthetic pilot data: 3 institutes, 1,000 students, 180k responses
python3 -m app.synth

# Rebuild mastery, risk, performance snapshots and parent reports
python3 -m app.analytics

# Run the app
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Open <http://127.0.0.1:8000/login>.

## Live demo

**https://nextute-data-moat.vercel.app**

The app runs on Vercel with a Supabase Postgres database. The data is the synthetic pilot dataset (1,000 students, 181k responses); no real student data is present.

## Demo accounts

| Role | Email | Password | What to show |
|---|---|---|---|
| Owner | `owner@demo.test` | `demo1234` | Full dashboard, fees, consent, erasure |
| Teacher | `teacher@demo.test` | `demo1234` | Fee fields redacted, interventions |
| Admin | `admin@demo.test` | `demo1234` | Imports, model/data health |

## Tests

```bash
python3 -m pytest -q
```

The suite covers Rasch recovery, topic mastery, tenant isolation, the 1,205-row demo import, consent enforcement and API auth/role redaction.

## Demo import

`app/static/demo_import.csv` — 40 students × 30 questions + 5 deliberately bad rows:

- 1,205 total
- 1,200 accepted
- 4 quarantined
- 1 duplicate

Upload from **Data imports → Upload results**, review quarantined rows, then commit.

## Repository map

```text
app/
  main.py          FastAPI routes, auth/CSRF, role-aware pages
  core.py          DB connection, tenant context, scrypt, signed session
  synth.py         synthetic data generator
  taxonomy.py      NEET taxonomy
  analytics.py     Rasch, mastery, risk, performance, rule risks
  imports.py       CSV validation, quarantine, idempotent commit
  reports.py       fact-locked bilingual report generation
  templates/       server-rendered UI
  static/          CSS, demo CSV, favicon
db/migrations/     schema, RLS, grants, content library
db/tests/          RLS smoke SQL
scripts/           migrations, demo CSV, financial model
tests/             pytest suite
notebooks/         early-model notebook on synthetic data
docs/              validation report, deck, business plan, Q&A
```

## Known limits (deliberate)

- Metrics are on **synthetic data** with a designed signal; AUC 1.0 is not a real-world claim.
- Fee-default and falling-behind scores are transparent rules, not trained models.
- OMR is an adapter point, not implemented; CSV is the working ingestion path.
- WhatsApp provider delivery is a queued stub; the inbound structured-entry webhook is implemented.
- Single-node pilot architecture; no real institute data has been used.
- The optional LLM path is off; reports use the reviewed template and fact-lock validator.

## Deploy on Vercel

Live deployment: <https://nextute-data-moat.vercel.app>

See `docs/08_vercel_deploy.md`. Vercel runs the FastAPI app, but you must supply a hosted Postgres URL and `SESSION_SECRET`. The local Docker database is not available inside Vercel.

## Submission pack

- `docs/01_solution_overview.md` — problem, architecture, ML, privacy
- `docs/02_validation_report.pdf` — validation report
- `docs/03_pitch_deck.pdf` — 14-slide deck
- `docs/04_business_plan.md` — market, pricing, GTM, financials
- `docs/05_demo_script.md` — 7-minute and 3-minute demos
- `docs/06_qna.md` — objection handling
- `docs/07_traceability.md` — requirement and rubric map
- `docs/08_vercel_deploy.md` — Vercel deployment runbook
- `docs/early_model_results.md` — reproducible early-model artefact
- `docs/institute_intelligence_financial_model.xlsx` — editable financial model
