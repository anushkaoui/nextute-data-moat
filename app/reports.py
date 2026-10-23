import hashlib
import secrets
from datetime import date

import psycopg

from .synth import AS_OF


def report_body(facts, lang):
    if lang == "hi":
        lines = [
            f"नमस्ते {facts['guardian_name']} जी,",
            f"{facts['student_name']} की {facts['period']} की प्रगति रिपोर्ट:",
            f"उपस्थिति: {facts['attendance_pct']}%",
            f"औसत अंक: {facts['avg_score']}%",
            f"सबसे मजबूत विषय: {facts['strong_topics']}",
            f"ध्यान देने योग्य विषय: {facts['focus_topics']}",
            f"अनुमानित आंतरिक प्रतिशतक: {facts['percentile_point']} (सीमा {facts['percentile_low']}–{facts['percentile_high']})",
            facts["advice_hi"],
            "यह अनुमान उपलब्ध डेटा पर आधारित है और परीक्षा परिणाम की गारंटी नहीं है।",
            "किसी भी प्रश्न के लिए कृपया संस्थान से संपर्क करें।",
        ]
    else:
        lines = [
            f"Dear {facts['guardian_name']},",
            f"Progress report for {facts['student_name']} for {facts['period']}:",
            f"Attendance: {facts['attendance_pct']}%",
            f"Average score: {facts['avg_score']}%",
            f"Strongest topics: {facts['strong_topics']}",
            f"Topics needing attention: {facts['focus_topics']}",
            f"Estimated internal percentile: {facts['percentile_point']} (range {facts['percentile_low']}–{facts['percentile_high']})",
            facts["advice_en"],
            "This estimate is based on available data and is not a guarantee of exam outcome.",
            "Please contact the institute for any questions.",
        ]
    return "\n".join(lines)


def facts_for_student(conn, student_id, as_of=AS_OF):
    r = conn.execute(
        "select s.id, p.full_name, b.name as batch, g.name as guardian, g.id as guardian_id "
        "from student s join student_pii p on p.student_id = s.id "
        "join enrollment e on e.institute_id = s.institute_id and e.student_id = s.id "
        "join batch b on b.institute_id = e.institute_id and b.id = e.batch_id "
        "left join guardian g on g.institute_id = s.institute_id and g.student_id = s.id and g.is_primary "
        "where s.id = %s limit 1", (student_id,)
    ).fetchone()
    if not r:
        return None
    topics = conn.execute(
        "select t.name, m.mastery_prob from mastery_snapshot m join topic t on t.id = m.topic_id "
        "where m.student_id = %s order by m.mastery_prob desc", (student_id,)
    ).fetchall()
    strong = ", ".join(t["name"] for t in topics[:3]) or "not enough data"
    focus = ", ".join(t["name"] for t in topics[-3:][::-1]) or "not enough data"
    att = conn.execute(
        "select count(*) as n, sum(case when status in ('present','late') then 1 else 0 end) as p "
        "from attendance_record where student_id = %s", (student_id,)
    ).fetchone()
    att_pct = round(100.0 * int(att["p"] or 0) / max(int(att["n"] or 1), 1))
    sc = conn.execute(
        "select sum(marks_awarded) as m, count(*) as n from response where student_id = %s "
        "and is_correct is not null", (student_id,)
    ).fetchone()
    avg = round(100.0 * float(sc["m"] or 0) / max(4.0 * int(sc["n"] or 1), 1), 1)
    perc = conn.execute(
        "select point, lower_bound, upper_bound from prediction_snapshot "
        "where student_id = %s and kind = 'internal_percentile' order by as_of desc limit 1", (student_id,)
    ).fetchone()
    risk = conn.execute(
        "select score, band from risk_snapshot where student_id = %s and target='disengagement' "
        "order by as_of desc limit 1", (student_id,)
    ).fetchone()
    high_risk = risk and risk["band"] == "high"
    advice_hi = ("नियमित कक्षा उपस्थिति और साप्ताहिक अभ्यास पर ध्यान दें; शिक्षक से मार्गदर्शन लें।"
                 if high_risk else "नियमित अभ्यास जारी रखें और कमजोर विषयों पर अतिरिक्त अभ्यास करें।")
    advice_en = ("Please prioritise regular attendance and weekly practice, and speak to the teacher."
                 if high_risk else "Keep up regular practice and add extra drills on the focus topics.")
    return {
        "student_name": r["full_name"],
        "guardian_name": r["guardian"] or "Parent/Guardian",
        "period": "April–September 2026",
        "batch": r["batch"],
        "attendance_pct": att_pct,
        "avg_score": avg,
        "strong_topics": strong,
        "focus_topics": focus,
        "percentile_point": round(float(perc["point"]), 1) if perc else "insufficient data",
        "percentile_low": round(float(perc["lower_bound"]), 1) if perc else "-",
        "percentile_high": round(float(perc["upper_bound"]), 1) if perc else "-",
        "risk_band": risk["band"] if risk else "unknown",
        "advice_hi": advice_hi,
        "advice_en": advice_en,
        "guardian_id": r["guardian_id"],
        "batch_name": r["batch"],
    }


def has_consent(conn, student_id, purpose="parent_communication"):
    row = conn.execute(
        "select 1 from consent where student_id=%s and purpose=%s and status='granted' limit 1",
        (student_id, purpose),
    ).fetchone()
    return bool(row)


def generate_report(conn, student_id, lang="en", as_of=AS_OF):
    facts = facts_for_student(conn, student_id, as_of)
    if not facts:
        return None
    if not has_consent(conn, student_id):
        return {"error": "consent"}
    body = report_body(facts, lang)
    clean = {k: v for k, v in facts.items() if k not in ("guardian_id",)}
    rep = conn.execute(
        "insert into report (institute_id, student_id, kind, language, period_start, period_end, "
        "facts, body, status) values "
        "(current_tenant(),%s,'parent_monthly',%s,'2026-04-01',%s,%s,%s,'template_fallback') returning id",
        (student_id, lang, as_of, psycopg.types.json.Jsonb(clean), body),
    ).fetchone()
    token = secrets.token_urlsafe(24)
    thash = hashlib.sha256(token.encode()).hexdigest()
    conn.execute(
        "insert into parent_link (institute_id, student_id, guardian_id, token_hash, expires_at) "
        "values (current_tenant(),%s,%s,%s,now() + interval '90 days')",
        (student_id, facts.get("guardian_id"), thash),
    )
    return {"id": rep["id"], "token": token, "body": body, "facts": clean}
