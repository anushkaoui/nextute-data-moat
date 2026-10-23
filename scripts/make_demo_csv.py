import csv
import random
import sys
from datetime import date

import psycopg
from psycopg.rows import dict_row

from app.core import DATABASE_URL, tenant
from app.taxonomy import topic_map

INSTITUTE = "11111111-1111-1111-1111-111111111111"
KEYS = ["A", "B", "C", "D"]


def main(out="app/static/demo_import.csv", seed=99):
    rnd = random.Random(seed)
    conn = psycopg.connect(DATABASE_URL, autocommit=True, row_factory=dict_row)
    rows = []
    with tenant(conn, INSTITUTE):
        topics = list(topic_map(conn).values())
        students = conn.execute(
            "select s.roll_no, p.full_name, "
            "(select 100.0*sum(r.marks_awarded)/(4.0*count(*)) from response r "
            " where r.student_id=s.id and r.is_correct is not null) as avg_pct "
            "from student s join student_pii p on p.student_id=s.id "
            "join enrollment e on e.student_id=s.id join batch b on b.id=e.batch_id "
            "where b.name='Class 12' and s.status='active' order by s.roll_no limit 40"
        ).fetchall()
    if not students:
        print("no Class 12 students found; run app.synth first", file=sys.stderr)
        return 1
    q_topics = [topics[i % len(topics)]["code"] for i in range(30)]
    keys = [KEYS[i % 4] for i in range(30)]
    for s in students:
        p = min(0.95, max(0.18, float(s["avg_pct"] or 45) / 100.0))
        for q in range(1, 31):
            if rnd.random() < 0.05:
                choice = ""
            elif rnd.random() < p:
                choice = keys[q - 1]
            else:
                choice = rnd.choice([k for k in KEYS if k != keys[q - 1]])
            rows.append({
                "test_name": "Weekly Test 7",
                "test_date": "2026-10-05",
                "batch_name": "Class 12",
                "roll_no": s["roll_no"],
                "student_name": s["full_name"],
                "q_no": q,
                "topic_code": q_topics[q - 1],
                "answer_key": keys[q - 1],
                "response": choice,
                "time_taken_sec": rnd.randint(35, 120),
            })
    base = dict(rows[0])
    bad = []
    r = dict(base); r["topic_code"] = "PHY-XXX"; bad.append(r)
    r = dict(base); r["answer_key"] = "E"; bad.append(r)
    r = dict(base); r["roll_no"] = ""; bad.append(r)
    bad.append(dict(rows[0]))
    r = dict(base); r["test_date"] = "05-10-2026"; bad.append(r)
    rows.extend(bad)
    with open(out, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} rows to {out} ({len(students)} students, 30 questions, 5 bad rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
