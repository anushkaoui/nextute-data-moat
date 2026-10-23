import hashlib
import math
import random
import uuid
from datetime import date, datetime, timedelta

import numpy as np
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .taxonomy import ADMIN_DATABASE_URL, seed_taxonomy, topic_map

FIRST = ["Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh", "Ayaan",
         "Krishna", "Ishaan", "Ananya", "Diya", "Aadhya", "Saanvi", "Pari", "Anika",
         "Riya", "Ira", "Myra", "Sara", "Rahul", "Amit", "Priya", "Neha", "Rohan",
         "Sneha", "Karan", "Pooja", "Vikram", "Shreya"]
ADULT_MALE = ["Rajesh", "Sunil", "Manoj", "Anil", "Sanjay", "Rakesh", "Dinesh", "Mukesh",
              "Ashok", "Umesh", "Pramod", "Vinod", "Arun", "Ajay", "Suresh", "Mahesh",
              "Naresh", "Ravi", "Santosh", "Dilip"]
LAST = ["Kumar", "Singh", "Sharma", "Verma", "Gupta", "Yadav", "Mishra", "Pandey",
        "Tiwari", "Raj", "Kumari", "Devi", "Prasad", "Chaudhary", "Jha", "Sinha",
        "Nair", "Reddy", "Patel", "Das"]

INSTITUTES = [
    ("11111111-1111-1111-1111-111111111111", "Patna NEET Academy", "Patna", "Bihar", 2, "NEET", 400),
    ("22222222-2222-2222-2222-222222222222", "Gaya Success Point", "Gaya", "Bihar", 2, "NEET", 350),
    ("33333333-3333-3333-3333-333333333333", "Patna JEE Circle", "Patna", "Bihar", 2, "JEE_MAIN", 250),
]
BATCHES = [("Class 11", "11"), ("Class 12", "12"), ("Dropper", "dropper")]
TEST_DATES = [date(2026, 4, 15), date(2026, 5, 15), date(2026, 6, 15),
              date(2026, 7, 15), date(2026, 8, 15), date(2026, 9, 20)]
AS_OF = date(2026, 9, 30)


def hmac_phone(phone: str, salt: str = "dev-pepper") -> str:
    return hashlib.sha256((salt + phone).encode()).hexdigest()


def connect_admin():
    return psycopg.connect(ADMIN_DATABASE_URL, row_factory=dict_row)


def generate(seed: int = 20260401, reset: bool = True, verbose: bool = True):
    rng = np.random.default_rng(seed)
    rnd = random.Random(seed)
    seed_taxonomy()
    admin = connect_admin()
    try:
        with admin.transaction():
            topics = list(topic_map(admin).values())
            if reset:
                admin.execute("truncate table institute cascade")
            counts = {"students": 0, "responses": 0, "attendance": 0}
            for inst_id, name, city, state, tier, exam, n_students in INSTITUTES:
                institute_id = uuid.UUID(inst_id)
                admin.execute(
                    "insert into institute (id, name, city, state, city_tier, exam_focus, plan, student_capacity) "
                    "values (%s,%s,%s,%s,%s,%s,'growth',%s)",
                    (institute_id, name, city, state, tier, exam, n_students),
                )
                seed_users(admin, institute_id)
                policy_id = admin.execute(
                    "insert into scoring_policy (institute_id, name, correct_marks, incorrect_marks) "
                    "values (%s,'NEET +4/-1',4,-1) returning id",
                    (institute_id,),
                ).fetchone()["id"]

                items = seed_items(admin, institute_id, topics, rng)
                item_by_id = {i["id"]: i for i in items}
                anchors = list(range(10))

                batches = []
                for b_idx, (bname, class_level) in enumerate(BATCHES):
                    batch_id = uuid.uuid4()
                    admin.execute(
                        "insert into batch (id, institute_id, name, exam_focus, class_level, academic_year, start_date, capacity) "
                        "values (%s,%s,%s,%s,%s,'2026-27','2026-04-01',%s)",
                        (batch_id, institute_id, bname, exam, class_level, n_students),
                    )
                    batches.append((batch_id, bname, class_level, b_idx))

                per_batch = distribute(n_students, len(batches))
                students = []
                sessions = {}
                for (batch_id, bname, class_level, b_idx), count in zip(batches, per_batch):
                    sessions[batch_id] = seed_sessions(admin, institute_id, batch_id)
                    for k in range(count):
                        s = seed_student(admin, institute_id, batch_id, b_idx, k, class_level, topics, rng, rnd)
                        students.append(s)
                counts["students"] += len(students)

                tests = []
                for t_idx, test_date in enumerate(TEST_DATES):
                    for (batch_id, bname, class_level, b_idx) in batches:
                        test_id = uuid.uuid4()
                        admin.execute(
                            "insert into test (id, institute_id, batch_id, name, test_date, duration_min, total_marks, "
                            "paper_version, scoring_policy_id, status, published_at) "
                            "values (%s,%s,%s,%s,%s,180,%s,'A',%s,'published',%s)",
                            (test_id, institute_id, batch_id, f"Test {t_idx + 1}",
                             test_date, 30 * 4, policy_id, datetime.combine(test_date, datetime.min.time())),
                        )
                        chosen = list(anchors) + [int(x) for x in rng.choice(
                            np.arange(10, len(items)), size=20, replace=False)]
                        chosen_items = [items[i] for i in chosen]
                        ti_rows = []
                        for pos, it in enumerate(chosen_items, start=1):
                            ti_id = uuid.uuid4()
                            admin.execute(
                                "insert into test_item (id, institute_id, test_id, item_id, position, answer_key, "
                                "key_status, approved_at) values (%s,%s,%s,%s,%s,%s,'approved',now())",
                                (ti_id, institute_id, test_id, it["id"], pos,
                                 Jsonb({"correct": it["key"]})),
                            )
                            ti_rows.append((ti_id, it))
                        tests.append((test_id, batch_id, test_date, ti_rows))

                batch_students = {}
                for s in students:
                    batch_students.setdefault(s["batch_id"], []).append(s)

                resp_rows = []
                for test_id, batch_id, test_date, ti_rows in tests:
                    for s in batch_students[batch_id]:
                        theta = s["theta"] + 0.06 * (test_date.month - 4)
                        for ti_id, it in ti_rows:
                            p = 0.2 + 0.8 / (1 + math.exp(-((theta + s["topic_affinity"].get(it["topic_id"], 0.0)) - it["b"])))
                            if rnd.random() < 0.05:
                                resp = None
                            elif rnd.random() < p:
                                resp = it["key"]
                            else:
                                resp = rnd.choice([x for x in "ABCD" if x != it["key"]])
                            resp_rows.append((institute_id, test_id, s["id"], ti_id, resp, it["key"]))
                counts["responses"] += insert_responses(admin, institute_id, resp_rows)
                counts["attendance"] += seed_attendance(admin, institute_id, students, sessions, rnd)
                seed_fees(admin, institute_id, students, rnd)
                seed_consents(admin, institute_id, students, rnd)
                seed_content(admin, institute_id, topics)
            if verbose:
                print(f"synthetic data ready: {counts}")
            return counts
    finally:
        admin.close()


def seed_users(admin, institute_id):
    from .core import hash_password
    rows = [
        ("owner@demo.test", "Owner Demo", "owner"),
        ("teacher@demo.test", "Teacher Demo", "teacher"),
        ("admin@demo.test", "Admin Demo", "admin"),
    ]
    for email, name, role in rows:
        existing = admin.execute(
            "select id from app_user where institute_id=%s and email=%s", (institute_id, email)
        ).fetchone()
        if existing:
            uid = existing["id"]
        else:
            uid = uuid.uuid4()
            admin.execute(
                "insert into app_user (id, institute_id, email, full_name, password_hash, status) "
                "values (%s,%s,%s,%s,%s,'active')",
                (uid, institute_id, email, name, hash_password("demo1234")),
            )
        admin.execute(
            "insert into role_binding (institute_id, user_id, role) values (%s,%s,%s) on conflict do nothing",
            (institute_id, uid, role),
        )


def seed_items(admin, institute_id, topics, rng):
    items = []
    for idx in range(150):
        topic = topics[idx % len(topics)]
        b = float(rng.normal(0, 1.1))
        key = "ABCD"[idx % 4]
        item_id = uuid.uuid4()
        admin.execute(
            "insert into item (id, institute_id, subject_id, topic_id, stem, item_type, options, correct_answer, "
            "external_ref, status) values (%s,%s,%s,%s,%s,'single_correct',%s,%s,%s,'approved')",
            (item_id, institute_id, topic["subject_id"], topic["id"],
             f"Practice item {idx + 1} on {topic['name']}", Jsonb({"A": "1", "B": "2", "C": "3", "D": "4"}),
             Jsonb({"correct": key}), f"ITM-{idx + 1:04d}"),
        )
        admin.execute(
            "insert into item_topic (institute_id, item_id, topic_id, weight, confidence, source, reviewed_at) "
            "values (%s,%s,%s,1,0.95,'manual',now())",
            (institute_id, item_id, topic["id"]),
        )
        items.append({"id": item_id, "b": b, "key": key, "topic_id": topic["id"]})
    return items


def seed_student(admin, institute_id, batch_id, b_idx, k, class_level, topics, rng, rnd):
    sid = uuid.uuid4()
    roll = f"{b_idx + 1}{k + 1:03d}"
    name = f"{rnd.choice(FIRST)} {rnd.choice(LAST)}"
    if rnd.random() < 0.02:
        name = name.replace("a", "aa", 1)
    dob_year = {"11": 2009, "12": 2008, "dropper": 2007}[class_level]
    theta = float(rng.normal(0, 0.9))
    withdrawal = rnd.random() < 0.15
    if withdrawal:
        exit_date = date(2026, 10, 1) + timedelta(days=rnd.randint(0, 75))
        status, exit_reason = "withdrawn", "withdrawn"
    else:
        exit_date, status, exit_reason = date(2026, 12, 31), "active", None
    affinity = {}
    if rnd.random() < 0.40:
        for t in rnd.sample(topics, k=rnd.randint(1, 2)):
            affinity[t["id"]] = -float(rng.uniform(0.6, 1.4))
    admin.execute(
        "insert into student (id, institute_id, student_key, join_date, class_level, status, exit_date, exit_reason, roll_no) "
        "values (%s,%s,%s,'2026-04-01',%s,%s,%s,%s,%s)",
        (sid, institute_id, "sk_" + uuid.uuid4().hex[:16], class_level, status, exit_date, exit_reason, roll),
    )
    phone = f"9{rnd.randint(100000000, 999999999)}"
    admin.execute(
        "insert into student_pii (student_id, institute_id, full_name, name_normalized, dob, guardian_phone_hmac, "
        "guardian_name, key_version) values (%s,%s,%s,%s,%s,%s,%s,1)",
        (sid, institute_id, name, name.lower(), date(dob_year, rnd.randint(1, 12), rnd.randint(1, 28)),
         hmac_phone(phone), f"{rnd.choice(ADULT_MALE)} {name.split()[-1]}"),
    )
    gid = uuid.uuid4()
    admin.execute(
        "insert into guardian (id, institute_id, student_id, name, phone_hmac, relationship, is_primary, "
        "verification_method, verified_at) values (%s,%s,%s,%s,%s,'father',true,'otp',now())",
        (gid, institute_id, sid, f"{rnd.choice(ADULT_MALE)} {name.split()[-1]}", hmac_phone(phone)),
    )
    admin.execute(
        "insert into enrollment (institute_id, student_id, batch_id, joined_at) values (%s,%s,%s,'2026-04-01')",
        (institute_id, sid, batch_id),
    )
    return {"id": sid, "batch_id": batch_id, "theta": theta, "exit_date": exit_date,
            "status": status, "roll": roll, "topic_affinity": affinity}


def seed_sessions(admin, institute_id, batch_id):
    sessions = []
    d = date(2026, 4, 6)
    while d <= date(2026, 9, 28):
        for slot in ("09:00", "17:00"):
            sid = uuid.uuid4()
            admin.execute(
                "insert into attendance_session (id, institute_id, batch_id, session_date, start_time, duration_min) "
                "values (%s,%s,%s,%s,%s,90)",
                (sid, institute_id, batch_id, d, slot),
            )
            sessions.append((sid, d))
        d += timedelta(days=7)
    return sessions


def seed_attendance(admin, institute_id, students, sessions, rnd):
    rows = []
    for s in students:
        for sid, sdate in sessions[s["batch_id"]]:
            if sdate > s["exit_date"]:
                continue
            p = 0.92
            if s["status"] == "withdrawn" and (s["exit_date"] - sdate).days <= 20:
                p = 0.45
            if sdate >= date(2026, 9, 15) and s["status"] == "withdrawn" and s["exit_date"] <= date(2026, 10, 30):
                p = 0.40
            status = "present" if rnd.random() < p else "absent"
            rows.append((institute_id, sid, s["id"], status))
    _executemany(admin, 
        "insert into attendance_record (institute_id, session_id, student_id, status, source) "
        "values (%s,%s,%s,%s,'import') on conflict do nothing",
        rows,
    )
    return len(rows)


def seed_fees(admin, institute_id, students, rnd):
    plans = []
    inst = []
    for s in students:
        plan_id = uuid.uuid4()
        plans.append((plan_id, institute_id, s["id"]))
        for n in range(1, 5):
            due = date(2026, 4 + n, 10)
            p_paid = 0.92 if s["status"] == "active" else 0.55
            paid = rnd.random() < p_paid
            paid_date = due + timedelta(days=rnd.randint(0, 12)) if paid else None
            inst.append((institute_id, plan_id, n, due, 15000, 15000 if paid else 0, paid_date,
                         "paid" if paid else "pending"))
    _executemany(admin, 
        "insert into fee_plan (id, institute_id, student_id, academic_year, total_fee) "
        "values (%s,%s,%s,'2026-27',60000)",
        plans,
    )
    _executemany(admin, 
        "insert into fee_instalment (institute_id, fee_plan_id, instalment_no, due_date, amount_due, "
        "amount_paid, paid_date, status) values (%s,%s,%s,%s,%s,%s,%s,%s)",
        inst,
    )


def seed_consents(admin, institute_id, students, rnd):
    consents = []
    for s in students:
        guardian = admin.execute(
            "select id from guardian where student_id=%s and is_primary limit 1", (s["id"],)
        ).fetchone()
        for purpose in ["core_analytics", "parent_communication"]:
            consents.append((institute_id, s["id"], guardian["id"], purpose))
        if rnd.random() < 0.8:
            consents.append((institute_id, s["id"], guardian["id"], "ai_generation"))
        if rnd.random() < 0.4:
            consents.append((institute_id, s["id"], guardian["id"], "aggregate_benchmark"))
    _executemany(admin, 
        "insert into consent (institute_id, student_id, guardian_id, purpose, status, method, notice_version) "
        "values (%s,%s,%s,%s,'granted','admission_form_otp','v1')",
        consents,
    )


def seed_content(admin, institute_id, topics):
    rows = []
    for t in topics:
        ctx = f"{t['chapter_name']} · {t['subject_code']}"
        rows.extend([
            (institute_id, t["id"], "concept", f"{t['name']} — concept brief",
             f"{ctx}. Define the core variable, sketch the setup, write the governing relation, "
             f"then check units and limiting cases before substituting numbers."),
            (institute_id, t["id"], "drill", f"{t['name']} — practice set",
             f"Start with two worked examples on {t['name']}, then 10 untimed questions, then a "
             f"15-minute timed set. Log every error by cause and reattempt after three days."),
            (institute_id, t["id"], "common_error", f"{t['name']} — common errors",
             f"Typical errors in {t['name']}: skipping the setup sketch, mixing units, and stopping "
             f"at the first algebraic form. Re-derive the result and test a limiting case."),
        ])
    _executemany(admin,
        "insert into content_resource (institute_id, topic_id, kind, title, body) "
        "values (%s,%s,%s,%s,%s) on conflict do nothing",
        rows,
    )
    return len(rows)


def insert_responses(admin, institute_id, rows):
    payload = []
    for inst, test_id, student_id, ti_id, resp, key in rows:
        if resp is None:
            payload.append((institute_id, test_id, student_id, ti_id, None, None, None, "omr", 1.0))
        else:
            correct = resp == key
            payload.append((institute_id, test_id, student_id, ti_id, Jsonb({"choice": resp}),
                            correct, 4 if correct else -1, "omr", 0.95))
    _executemany(admin, 
        "insert into response (institute_id, test_id, student_id, test_item_id, raw_response, is_correct, "
        "marks_awarded, source, confidence) values (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        payload,
    )
    return len(payload)


def _executemany(conn, sql, rows):
    with conn.cursor() as cur:
        cur.executemany(sql, rows)


def distribute(total, buckets):
    base = total // buckets
    out = [base] * buckets
    for i in range(total - base * buckets):
        out[i] += 1
    return out


if __name__ == "__main__":
    generate()
