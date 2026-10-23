# Business plan

**Institute Intelligence · Case B “The Data Moat” · 2026**

## 1. Thesis

Tier-2 coaching institutes already have the data that predicts retention. They do not have the workflow to turn it into weekly action. We sell that workflow: a privacy-first analytics layer on top of the OMR/Excel/WhatsApp stack they already use.

The wedge is not “AI for education.” It is a narrow, measurable promise:

> “Know which students are slipping, why, and what to do this week — before they leave.”

## 2. Customer

**Beachhead:** NEET/JEE coaching institutes in Patna with 150–1,000 students, owner-operated, 10–40 teachers, using OMR or Google Forms for tests.

**Buyer:** owner or academic head. The owner feels fee leakage and batch shrinkage directly. Teachers need a short weekly list, not another dashboard.

**Users:** owner, academic head, teacher, front desk/admin, parent (read-only via expiring link).

**Why now:**
- Parents expect WhatsApp updates, but institutes send ranks without explanation.
- Margin pressure makes retention the cheapest growth lever.
- DPDP raises the bar for handling student data; privacy becomes a buying criterion.
- Cloud + OMR/Forms exports make ingestion possible without changing the institute’s test workflow.

## 3. Product

| Layer | What it does |
|---|---|
| Ingest | CSV/Forms export, validation, quarantine, idempotent commit |
| Measure | Rasch/1PL ability, topic mastery with uncertainty, anchor equating |
| Predict | 28-day disengagement (calibrated), falling behind (rule), fee default (rule) |
| Explain | Reasons for every score; internal percentile band, never an exam rank |
| Act | Teacher interventions, retrieval-grounded study plan, EN/HI parent report |
| Protect | Tenant RLS, consent gates, teacher fee redaction, audit, erasure workflow |

**Deliberate non-goals:** LMS, live classes, content marketplace, student chatbot, payment collection, full OMR scanner.

## 4. Market

Bottom-up, assumption-led:

| Layer | Assumption | Institutes |
|---|---|---:|
| Total coaching institutes | Industry planning assumption | 1,20,000 |
| NEET/JEE-focused | 25% | 30,000 |
| Tier-2/3, 150+ students | 40% of focused | 12,000 |
| Year-3 target | 2.7% of addressable | 320 |

At a blended ACV of ₹1.0–1.1L, the addressable SAM is roughly ₹1,200–1,300 Cr. These are planning assumptions, not verified market research. The pilot exists to test institute count, willingness to pay and churn.

## 5. Pricing

| Tier | Price / student / month | Average students | ACV | Service cost | Contribution |
|---|---:|---:|---:|---:|---:|
| Starter | ₹35 | 200 | ₹70,000 | ₹25,000 | ₹45,000 (64.3%) |
| Growth | ₹55 | 350 | ₹1,92,500 | ₹66,730 | ₹1,25,770 (65.3%) |

- 10 billed months; February–March free.
- 150-student minimum.
- Annual pre-paid after a 4-week historical-data pilot.
- No per-report or per-teacher fee; complexity hurts adoption.

## 6. Unit economics

| Metric | Starter | Growth | Blended |
|---|---:|---:|---:|
| ACV | ₹70,000 | ₹1,92,500 | ₹1,06,750 |
| Contribution | ₹45,000 | ₹1,25,770 | ₹69,231 |
| CAC | ₹38,000 | ₹38,000 | ₹38,000 |
| CAC payback | 10.1 months | 3.6 months | 6.6 months |
| LTV / CAC (30 months) | 3.0× | 8.3× | 4.6× |

Service cost includes cloud, support, onboarding amortisation, WhatsApp/SMS, payments and content ops. CAC assumes founder-led sales plus onboarding; it will rise with a sales team.

## 7. Go-to-market

**Phase 0 — design partners (next 90 days)**
- 10 Patna institutes; 2 paid pilots.
- Offer: free 4-week historical-data audit; paid 8-week pilot at ₹25,000; convert to annual.
- Success bar: 70% of top-20 flags rated actionable; parent report open rate >60%; 3-point attendance lift vs control.

**Phase 1 — Patna wedge (Year 1)**
- 40 institutes; owner referrals; local coaching associations; one distributor per district.
- Case studies by exam and batch type.
- Native Google Forms connector and OMR adapter.

**Phase 2 — Bihar/UP/Jharkhand (Year 2–3)**
- 140 → 320 institutes.
- Partner-led implementation; Hindi-first content ops; benchmark network with consented aggregates.

**Sales motion:** owner demo → historical data audit → 8-week pilot → annual contract. The audit is the wedge; it proves value before asking for workflow change.

## 8. Competition and moat

| Alternative | Gap |
|---|---|
| Excel + WhatsApp | No student-level join, no reasons, no audit, no parent-safe output |
| Generic LMS/BI | Requires replacing the institute’s workflow; weak assessment psychometrics |
| OMR vendors | Answer-sheet processing, not retention or parent communication |
| In-house dashboard | Expensive to build; no benchmark network or privacy controls |

**Moat over time:**
1. **Workflow lock-in:** imports, interventions and parent communication become weekly habits.
2. **Data flywheel:** consented cross-institute benchmarks improve calibration and topic priors.
3. **Trust brand:** explainability and privacy in a category built on rank anxiety.
4. **Switching cost:** historical mastery, intervention history and parent templates live in the platform.

## 9. Financial summary

| ₹ lakh | Year 1 | Year 2 | Year 3 |
|---|---:|---:|---:|
| Average institutes | 18 | 88 | 225 |
| Revenue | 18.1 | 93.9 | 254.0 |
| Contribution | 11.7 | 60.9 | 164.9 |
| Fixed cost | 76.0 | 92.0 | 120.0 |
| EBITDA | -64.3 | -31.1 | +44.9 |
| Cumulative EBITDA | -64.3 | -95.3 | -50.5 |
| Year-end ARR | 40.3 | 149.5 | 361.2 |

- Break-even at the Year-1 fixed cost base: ~110 institutes.
- Peak funding need: ~₹95L; ask ₹1.0Cr for 18 months with a small buffer.
- Year-end students: ~9,500 → 34,300 → 80,800.

## 10. Use of funds (₹1.0Cr)

| Category | ₹ lakh | Share |
|---|---:|---:|
| Product & engineering | 35.0 | 35% |
| Pilot delivery & onboarding | 20.0 | 20% |
| Sales & channel | 20.0 | 20% |
| Content & assessment ops | 10.0 | 10% |
| Compliance, legal, security | 5.0 | 5% |
| Working capital & buffer | 10.0 | 10% |

## 11. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Model does not predict real dropout | Time-based pilot; pre-registered success bar; keep rules transparent |
| Institutes will not change workflow | Start with a historical audit; integrate with existing CSV/Forms; 20-minute weekly loop |
| Parent consent / DPDP | Consent gate; purpose limitation; DPA; erasure workflow; legal review |
| Data quality | Row-level quarantine; visible exceptions; no silent fixes |
| Teacher adoption | One short list, reasons, intervention button; no new LMS |
| Price resistance | Starter tier; 150-student floor; value framed as retained fees |
| WhatsApp dependency | Provider-agnostic message log; SMS/email fallback |
| Founder bandwidth | Narrow wedge; design partners; no custom builds |

## 12. Milestones

| When | Milestone | Gate |
|---|---|---|
| Now | Working prototype on 3 synthetic institutes | 6/6 tests; privacy checks |
| 90 days | 10 design partners, 2 paid pilots | 70% flags actionable; 60% report open |
| 12 months | 40 institutes, ~9,500 students | CAC payback <9 months |
| 24 months | 140 institutes, ~34k students | Positive contribution after support |
| 36 months | 320 institutes, ~80k students | EBITDA positive; benchmark network live |

## 13. Why this team can win

- We built the full vertical slice, not a mock: ingestion, Rasch, calibrated risk, roles, RLS, reports, tests.
- We are honest about what is synthetic and what is not. That is the trust posture the category needs.
- The wedge is operationally narrow enough to sell founder-led and defensible enough to compound.
