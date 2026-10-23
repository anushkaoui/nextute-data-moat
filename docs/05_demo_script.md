# Demo script

**Target length:** 7 minutes (plus 3 minutes Q&A)  
**App:** `http://127.0.0.1:8000`  
**Password for all demo accounts:** `demo1234`

## Before you start

```bash
python3 -m pytest -q                 # 6 passed
curl -s http://127.0.0.1:8000/healthz
```

Open two browser windows:
- Owner: `owner@demo.test`
- Teacher: `teacher@demo.test`

Keep a third tab on `/status`.

## 7-minute walkthrough

### 0:00–0:35 — Frame the problem

“A Tier-2 coaching institute already has the data that predicts dropout: attendance, weekly test scores, topic-level errors and fee behaviour. It is trapped in OMR sheets, Excel and WhatsApp. We turn that into one weekly loop: measure, explain, act.”

### 0:35–1:35 — Owner dashboard

Log in as **owner**.

Point to:
1. Active students, attendance, tests, fees overdue.
2. Three risk cards: disengagement, falling behind, fee default.
3. Highest disengagement risk table with **primary reason**.
4. Weakest topics.

One line: “This is not a rank. It is a list of who needs help and why.”

### 1:35–3:00 — Student view

Click a student in the risk table (or **Students → any student**).

Show:
- Topic mastery with evidence count; low-evidence topics carry a “low” badge.
- Mock trend.
- Three risk snapshots with reasons. As owner, fee default is visible; as teacher it will be redacted.
- **Study plan**: three weakest topics retrieve curated concept and drill briefs.
- **Interventions**: open a mentoring/remedial action.

Say: “The score is decision support. The teacher owns the action. We audit it.”

### 3:00–4:15 — Parent report

Click **Generate English** (or open an existing report).

Show:
- Fact-locked badge; template-generated; no LLM call.
- Attendance, average score, strong topics, focus topics, internal percentile band.
- “This is an internal cohort percentile, not a JEE/NEET rank.”
- Click **Queue WhatsApp**; show the queued utility-message notice.
- Click **Create parent link**; the parent view opens.

Parent view: “No risk labels. No fees. Expiring token. Consent required.”

### 4:15–5:00 — Teacher redaction

Sign out, log in as **teacher**.

Show:
- Fee card says **Restricted**.
- No rupee amounts anywhere on the dashboard or student page.
- Fee-default risk tab is blocked.
- Risk reasons that mention fees are redacted to “fee status restricted”.

Say: “Role separation is server-side, not just CSS.”

### 5:00–6:00 — Import

Sign out, log in as **admin**.

Go to **Data imports → demo_import.csv → review**.

Show:
- 1,205 total; 1,200 accepted; 4 quarantined; 1 duplicate.
- Quarantined rows appear first: unknown topic code, malformed date, missing key, out-of-range question.
- “Bad rows are visible exceptions. We never silently drop data.”
- Point to **Commit** status: 1,200 inserted, 1 test, 0 new students.

### 6:00–6:45 — Model and data health

Open **Model & data** (`/status`).

Show:
- Rasch model version, θ sd, b sd, iterations.
- Disengagement AUC/PR-AUC/Brier and the model card note.
- Rule models labelled `rule_v1`.
- Reports generated, response counts, risk snapshots.
- “The metrics are on synthetic data. AUC 1.0 is not a real-world claim.”

### 6:45–7:00 — Close

“The pitch is not another LMS. It is the trust layer that turns existing data into a weekly action loop. We have the prototype, the privacy model and the unit economics. The next step is 10 Patna design partners.”

## 3-minute version

1. Dashboard: three risks with reasons (30s).
2. Student: mastery + study plan + intervention (50s).
3. Parent report: fact-locked, bilingual, no rank; queue WhatsApp (40s).
4. Teacher: fee redaction (25s).
5. Import: 1,205 → 1,200 / 4 / 1 (30s).
6. Caveat: synthetic data, next is time-based pilot (15s).

## If something breaks

| Symptom | Recovery |
|---|---|
| Login fails | Check `owner@demo.test` / `demo1234`; rate limit clears after 10 min |
| 500 on page | Check `uvicorn` terminal; run `python3 scripts/apply_migrations.py` |
| No reports | Run `python3 -m app.analytics`; it reseeds 30 per institute |
| Import duplicate | Re-upload returns the same job; open the existing job |
| Parent link 404 | Link expired or consent withdrawn; create a new link |
| Chart empty | Analytics snapshots missing; run the analytics job |
| WhatsApp queue fails | Consent missing; check the student’s consent ledger |

## Do not claim

- “Validated on real students.” It is synthetic.
- “Predicts NEET rank.” It does not.
- “AUC 0.99 in production.” It is a synthetic split.
- “OMR is live.” CSV is the working path; OMR is an adapter.
- “WhatsApp delivery is live.” The webhook and queue are; provider delivery is stubbed.
