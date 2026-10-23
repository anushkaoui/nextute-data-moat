# Q&A and objection handling

## Model

**Q: Your AUC is 1.0. Is that credible?**  
No. Withdrawal is generated from attendance and fee behaviour, so the model partly learns the generator. We show it to prove the pipeline and calibration, not to claim real-world performance. The pilot uses a time-based holdout on real withdrawals and a pre-registered success bar.

**Q: Why Rasch instead of a simple percentage?**  
A percentage confounds student ability with paper difficulty. Rasch separates θ and b, so a hard test does not make every student look weak. We add shrinkage and recency because a topic with two questions is noisy.

**Q: Why rules for fee default and falling behind?**  
We do not have 12 months of labelled outcomes. A trained model would be false precision. Rules are transparent, tunable and labelled as rules. We will train when the labels exist.

**Q: What is the cold-start problem?**  
A new institute can run on historical CSV data immediately. Mastery needs item-level responses; risk needs attendance and fee history. If data is thin, the UI says “low evidence” and the report gives no false precision.

**Q: How do you handle a new test with no item history?**  
Concurrent calibration with anchor items. The schema stores anchors per test; the pilot uses 10 common items. A new institute starts with its own calibration and can adopt shared priors later.

**Q: Is the percentile band a rank?**  
No. It is an internal cohort percentile with an 80% interval. We explicitly prohibit JEE/NEET rank claims in the report and the UI.

## Data and product

**Q: Why not just use Excel?**  
Excel does not join student-level attendance, fees, item responses, interventions and parent communication with role-based privacy and an audit trail. The value is the weekly workflow and the trust boundary, not the chart.

**Q: How do you ingest data?**  
CSV and Google Forms exports today. Row-level validation, quarantine and idempotent commit. OMR is an adapter point; we did not build a scanner for the pilot.

**Q: What about dirty data?**  
Bad rows are visible exceptions, not silent drops. The demo has 4 quarantined rows and 1 duplicate out of 1,205. Commit is a separate step.

**Q: Is this an LMS?**  
No. It sits on top of the institute’s existing tests and classes. We do not sell content, live classes or a student app.

**Q: What does the teacher actually do on Monday?**  
Open the top-20 list, read the reason, open a mentoring/remedial action, and send a parent update where consent exists. The loop is designed for 20 minutes, not a new workflow.

**Q: Why will teachers adopt it?**  
One short list, reasons attached, one action button, no new LMS. The owner buys it; the teacher gets relief, not more admin.

## Privacy and regulation

**Q: How do you comply with DPDP?**  
Purpose-bound consent, data minimisation, PII separation, role-based access, audit, erasure request workflow, retention policy and a DPA with the institute. We are not giving legal advice; the pilot includes a legal review.

**Q: Can a parent see risk scores?**  
No. Parent view shows attendance, scores, topics and an internal band. No risk labels, no fees.

**Q: Can a teacher see fees?**  
No. Fee fields and the fee-default target are restricted to owner/academic head/admin. Fee mentions inside disengagement reasons are redacted.

**Q: What if consent is withdrawn?**  
Report generation, parent-link creation and WhatsApp queue are blocked. Existing links are revocable and expire.

**Q: Where is the data stored?**  
India-region Postgres/object storage in production. The pilot runs locally. PII is separated from operational tables; guardian phone is HMACed.

**Q: What happens on a breach?**  
Audit trail, tenant scoping, key rotation and an incident runbook. The exact notification timeline is a legal review item, not a claim we make today.

## Business

**Q: Why ₹35–₹55 per student per month?**  
It is a small share of a coaching fee and scales with the institute’s size. The 150-student floor keeps onboarding viable. We will test willingness to pay in the paid pilot.

**Q: What is the CAC and payback?**  
₹38k blended CAC; 3.6-month payback on Growth, 6.6 months blended. Founder-led sales keeps CAC low; it will rise with a sales team.

**Q: What is the churn assumption?**  
The model uses a 30-month conservative life for LTV, not a 5-year SaaS life. We will measure renewal after the first annual cycle.

**Q: Break-even?**  
About 110 institutes at the Year-1 fixed cost base. The 3-year plan reaches 140 by Year 2 and 320 by Year 3; EBITDA turns positive in Year 3.

**Q: Why raise ₹1.0Cr?**  
Peak cumulative burn is ~₹95L. The ask funds 18 months to 110+ institutes, with a small buffer. Use of funds: product 35%, pilots 20%, sales 20%, content/compliance 15%, buffer 10%.

**Q: What is the valuation?**  
We are not anchoring a valuation in this submission. The ask is milestone-based; the pilot de-risks the next round.

## Competition and moat

**Q: Why won’t an LMS or OMR vendor copy this?**  
They can add charts. The hard parts are the local workflow, the parent trust layer and the consented benchmark network. We start where they are not: Tier-2 owner-operated institutes.

**Q: What is the moat?**  
Weekly workflow lock-in, historical mastery and intervention data, parent communication templates, and a consented cross-institute benchmark. The data flywheel improves calibration as cohorts accumulate.

**Q: Why Patna?**  
Dense Tier-2 coaching cluster, owner-led buying, Hindi/English parent communication, and a short feedback loop for design partners. It is a wedge, not the whole market.

**Q: What is the biggest risk?**  
That real institutes do not change their weekly workflow. The pilot tests this directly: 70% of top-20 flags rated actionable, 60% parent report open rate, 3-point attendance lift.

## AI

**Q: Where is the LLM?**  
Template-first. The LLM is optional and disabled by default. Facts are locked and validated; the deterministic template is the fallback. We will add an LLM only after an evaluation set and a red-team review.

**Q: Where is the RAG?**  
Study plans retrieve curated concept and drill briefs for the three weakest topics and compose deterministically. No student data is sent to an external model. It is narrow on purpose.

**Q: How do you prevent hallucinated numbers?**  
The report is generated from a facts object. A validator rejects numbers not present in the facts. The parent report carries a fact-locked badge.

**Q: Is this “AI-washed”?**  
No. We use Rasch and a calibrated logistic model where they are appropriate, rules where data is thin, and templates for communication. The AI is a means, not the pitch.

## Team and execution

**Q: Why are you the team to build this?**  
We built the full vertical slice: schema, RLS, ingestion, Rasch, risk, reports, roles, tests and a working UI. We are honest about synthetic limits. That is the posture a trust product needs.

**Q: What is the next milestone?**  
10 design partners and 2 paid pilots in 90 days, with a time-based validation and a parent report study. Then 40 institutes in Year 1.

**Q: What would make you kill the idea?**  
If fewer than 70% of flags are judged actionable, if parents do not open reports, or if institutes will not pay ₹35 after a paid pilot. We pre-register those gates.
