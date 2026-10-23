import csv
import hashlib
import io
import re
import uuid
from datetime import date, datetime

import psycopg
from psycopg.types.json import Jsonb

REQUIRED = ["test_name", "test_date", "batch_name", "roll_no", "student_name",
            "q_no", "topic_code", "answer_key", "response"]
ALLOWED_ANSWER = {"A", "B", "C", "D", ""}
MAX_ROWS = 20000


def norm_name(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def parse_date(s: str):
    try:
        return datetime.strptime((s or "").strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def create_job(conn, institute_id, filename, content: bytes, user_id):
    digest = hashlib.sha256(content).hexdigest()
    existing = conn.execute(
        "select id, status from import_job where institute_id=%s and content_hash=%s limit 1",
        (institute_id, digest),
    ).fetchone()
    if existing:
        return existing["id"], True
    job = conn.execute(
        "insert into import_job (institute_id, kind, source_filename, content_hash, storage_key, "
        "status, idempotency_key, created_by) values "
        "(%s,'csv',%s,%s,%s,'parsing',%s,%s) returning id",
        (institute_id, filename[:200], digest, f"imports/{digest}.csv", digest, user_id),
    ).fetchone()
    return job["id"], False


def parse_and_store(conn, institute_id, job_id, content: bytes):
    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    topics = {
        r["code"]: r for r in conn.execute(
            "select t.id, t.code, t.name, t.chapter_id, c.subject_id from topic t join chapter c on c.id=t.chapter_id"
        ).fetchall()
    }
    rows = []
    seen = set()
    stats = {"total": 0, "accepted": 0, "quarantined": 0, "duplicate": 0}
    for idx, raw in enumerate(reader, start=1):
        if idx > MAX_ROWS:
            break
        stats["total"] += 1
        raw = {k: (v if v is not None else "") for k, v in raw.items() if k}
        errors, warnings = [], []
        missing = [c for c in REQUIRED if c not in raw]
        if missing:
            errors.append(f"missing columns: {', '.join(missing)}")
        test_name = (raw.get("test_name") or "").strip()
        batch_name = (raw.get("batch_name") or "").strip()
        roll = (raw.get("roll_no") or "").strip()
        name = (raw.get("student_name") or "").strip()
        topic_code = (raw.get("topic_code") or "").strip().upper()
        key = (raw.get("answer_key") or "").strip().upper()
        response = (raw.get("response") or "").strip().upper()
        d = parse_date(raw.get("test_date", ""))
        try:
            q_no = int((raw.get("q_no") or "").strip())
        except ValueError:
            q_no = None
        if not test_name:
            errors.append("test_name is empty")
        if not batch_name:
            errors.append("batch_name is empty")
        if not roll:
            errors.append("roll_no is empty")
        if not name:
            errors.append("student_name is empty")
        if d is None:
            errors.append("test_date must be YYYY-MM-DD")
        if q_no is None or q_no < 1 or q_no > 200:
            errors.append("q_no must be an integer between 1 and 200")
        if topic_code not in topics:
            errors.append(f"unknown topic_code '{topic_code}'")
        if key not in {"A", "B", "C", "D"}:
            errors.append("answer_key must be A, B, C or D")
        if response not in ALLOWED_ANSWER:
            errors.append("response must be A-D or blank")
        dedupe = (test_name.lower(), d, batch_name.lower(), roll, q_no)
        duplicate = dedupe in seen
        seen.add(dedupe)
        if errors:
            status = "quarantined"
            stats["quarantined"] += 1
        elif duplicate:
            errors.append("duplicate row in file (same roll and question)")
            status = "duplicate"
            stats["duplicate"] += 1
        else:
            status = "accepted"
            stats["accepted"] += 1
        normalized = {
            "test_name": test_name, "test_date": d.isoformat() if d else None,
            "batch_name": batch_name, "roll_no": roll, "student_name": name,
            "q_no": q_no, "topic_code": topic_code, "answer_key": key,
            "response": response or None,
            "time_taken_sec": raw.get("time_taken_sec") or None,
        }
        rows.append((institute_id, job_id, idx, Jsonb(raw), Jsonb(normalized),
                     status, Jsonb(errors), Jsonb(warnings), "response"))
    with conn.cursor() as cur:
        cur.executemany(
            "insert into import_row (institute_id, import_job_id, row_no, raw, normalized, status, "
            "errors, warnings, entity_type) values (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            rows,
        )
    conn.execute(
        "update import_job set status='needs_review', stats=%s where id=%s",
        (Jsonb(stats), job_id),
    )
    return stats


def _batch(conn, institute_id, name, test_date):
    row = conn.execute(
        "select id, class_level from batch where name=%s and academic_year='2026-27' limit 1", (name,)
    ).fetchone()
    if row:
        return row["id"], row["class_level"]
    level = "11" if "11" in name else ("12" if "12" in name else "dropper")
    exam = conn.execute("select exam_focus from institute where id=%s", (institute_id,)).fetchone()["exam_focus"] or "NEET"
    row = conn.execute(
        "insert into batch (institute_id, name, exam_focus, class_level, academic_year, start_date) "
        "values (%s,%s,%s,%s,'2026-27',%s) returning id",
        (institute_id, name, exam, level, test_date),
    ).fetchone()
    return row["id"], level


def _policy(conn, institute_id):
    row = conn.execute("select id from scoring_policy order by name limit 1").fetchone()
    if row:
        return row["id"]
    return conn.execute(
        "insert into scoring_policy (institute_id, name, correct_marks, incorrect_marks) "
        "values (%s,'NEET +4/-1',4,-1) returning id", (institute_id,)
    ).fetchone()["id"]


def _student(conn, institute_id, roll, name, batch_id, level, test_date, user_id, job_id):
    row = conn.execute("select id from student where roll_no=%s limit 1", (roll,)).fetchone()
    if row:
        return row["id"], False, []
    sid = uuid.uuid4()
    conn.execute(
        "insert into student (id, institute_id, student_key, join_date, class_level, status, roll_no) "
        "values (%s,%s,%s,%s,%s,'active',%s)",
        (sid, institute_id, "imp-" + uuid.uuid4().hex[:12], test_date, level, roll),
    )
    conn.execute(
        "insert into student_pii (student_id, institute_id, full_name, name_normalized, key_version) "
        "values (%s,%s,%s,%s,1)",
        (sid, institute_id, name or f"Student {roll}", norm_name(name)),
    )
    conn.execute(
        "insert into enrollment (institute_id, student_id, batch_id, joined_at) values (%s,%s,%s,%s)",
        (institute_id, sid, batch_id, test_date),
    )
    conn.execute(
        "insert into consent (institute_id, student_id, purpose, status, method, evidence_ref, "
        "notice_version, recorded_by) values (%s,%s,'core_analytics','granted','institute_attestation',%s,'v1',%s) "
        "on conflict do nothing",
        (institute_id, sid, f"import:{job_id}", user_id),
    )
    return sid, True, ["student created from import; consent recorded as institute attestation"]


def commit_job(conn, institute_id, job_id, user_id):
    job = conn.execute("select * from import_job where id=%s", (job_id,)).fetchone()
    if not job:
        return None
    rows = conn.execute(
        "select * from import_row where import_job_id=%s and status='accepted' order by row_no",
        (job_id,),
    ).fetchall()
    topics = {r["code"]: r for r in conn.execute("select t.id, t.code, t.name, t.chapter_id, c.subject_id from topic t join chapter c on c.id=t.chapter_id").fetchall()}
    stats = {"inserted": 0, "duplicate": 0, "students_created": 0, "tests_created": 0}
    tests = {}
    items = {}
    for row in rows:
        n = row["normalized"]
        if not n:
            continue
        test_key = (n["test_name"], n["test_date"], n["batch_name"])
        if test_key not in tests:
            batch_id, level = _batch(conn, institute_id, n["batch_name"], date.fromisoformat(n["test_date"]))
            policy_id = _policy(conn, institute_id)
            test_date = date.fromisoformat(n["test_date"])
            test = conn.execute(
                "select id from test where batch_id=%s and name=%s and paper_version='A'", (batch_id, n["test_name"])
            ).fetchone()
            if test:
                test_id = test["id"]
            else:
                test_id = conn.execute(
                    "insert into test (institute_id, batch_id, name, test_date, duration_min, total_marks, "
                    "paper_version, scoring_policy_id, status, published_at) "
                    "values (%s,%s,%s,%s,180,120,'A',%s,'published',now()) returning id",
                    (institute_id, batch_id, n["test_name"], test_date, policy_id),
                ).fetchone()["id"]
                stats["tests_created"] += 1
            tests[test_key] = (test_id, batch_id, level, policy_id, test_date)
        test_id, batch_id, level, policy_id, test_date = tests[test_key]
        topic = topics[n["topic_code"]]
        item_key = (test_id, n["q_no"])
        if item_key not in items:
            ti = conn.execute(
                "select ti.id from test_item ti where ti.test_id=%s and ti.position=%s", (test_id, n["q_no"])
            ).fetchone()
            if ti:
                ti_id = ti["id"]
            else:
                item_id = uuid.uuid4()
                conn.execute(
                    "insert into item (id, institute_id, subject_id, topic_id, stem, item_type, options, "
                    "correct_answer, external_ref, status) values (%s,%s,%s,%s,%s,'single_correct',%s,%s,%s,'approved')",
                    (item_id, institute_id, topic["subject_id"], topic["id"], f"Imported Q{n['q_no']} — {topic['name']}",
                     Jsonb({"A": "1", "B": "2", "C": "3", "D": "4"}),
                     Jsonb({"correct": n["answer_key"]}), f"IMP-{job_id}-{n['q_no']}"),
                )
                conn.execute(
                    "insert into item_topic (institute_id, item_id, topic_id, weight, confidence, source, reviewed_at) "
                    "values (%s,%s,%s,1,0.9,'rule',now())",
                    (institute_id, item_id, topic["id"]),
                )
                ti_id = conn.execute(
                    "insert into test_item (institute_id, test_id, item_id, position, answer_key, key_status, approved_at) "
                    "values (%s,%s,%s,%s,%s,'approved',now()) returning id",
                    (institute_id, test_id, item_id, n["q_no"], Jsonb({"correct": n["answer_key"]})),
                ).fetchone()["id"]
            items[item_key] = (ti_id, n["answer_key"])
        ti_id, key = items[item_key]
        sid, created, warnings = _student(
            conn, institute_id, n["roll_no"], n["student_name"], batch_id, level, test_date, user_id, job_id
        )
        if created:
            stats["students_created"] += 1
        response = n["response"]
        if response is None:
            correct = None
            marks = None
        else:
            correct = response == key
            marks = 4 if correct else -1
        cur = conn.execute(
            "insert into response (institute_id, test_id, student_id, test_item_id, raw_response, is_correct, "
            "marks_awarded, source, confidence, import_row_id) values "
            "(%s,%s,%s,%s,%s,%s,%s,'csv',1.0,%s) "
            "on conflict (institute_id, test_id, student_id, test_item_id, attempt_no) do nothing returning id",
            (institute_id, test_id, sid, ti_id,
             Jsonb({"choice": response}) if response else None, correct, marks, row["id"]),
        ).fetchone()
        if cur:
            stats["inserted"] += 1
            conn.execute("update import_row set status='accepted', entity_id=%s where id=%s",
                         (test_id, row["id"]))
        else:
            stats["duplicate"] += 1
            conn.execute("update import_row set status='duplicate', entity_id=%s where id=%s",
                         (test_id, row["id"]))
    conn.execute(
        "update import_job set status='committed', completed_at=now(), stats=%s where id=%s",
        (Jsonb({**job["stats"], "commit": stats}), job_id),
    )
    conn.execute(
        "insert into audit_event (institute_id, actor_user_id, action, entity_type, entity_id, detail) "
        "values (%s,%s,'import.commit','import_job',%s,%s)",
        (institute_id, user_id, job_id, Jsonb(stats)),
    )
    return stats
