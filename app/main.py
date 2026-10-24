import hashlib
import json
import os
import secrets
import time
from collections import defaultdict
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import imports as importer
from .analytics import run_for_institute
from .core import (SESSION_COOKIE, SESSION_HOURS, connect, login, make_session,
                   read_session, tenant)
from .reports import generate_report
from .synth import AS_OF

BASE = Path(__file__).resolve().parent
app = FastAPI(title="Institute Intelligence Platform", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
templates = Jinja2Templates(directory=BASE / "templates")
templates.env.filters["inr"] = lambda v: "₹{:,.0f}".format(float(v or 0))
templates.env.globals["AS_OF"] = AS_OF


def reason_text(reason, role):
    if not reason:
        return "—"
    if role not in ("owner", "academic_head", "admin") and reason.get("feature") in ("fees", "fee_overdue_k"):
        return "fee status restricted"
    return reason.get("text", "—")


templates.env.globals["reason_text"] = reason_text


def mcolor(v):
    if v is None:
        return "#eef2f7"
    if v < 0.35:
        return "#fee2e2"
    if v < 0.55:
        return "#fef3c7"
    if v < 0.75:
        return "#ecfccb"
    return "#dcfce7"


templates.env.filters["mcolor"] = mcolor

FAILED_LOGINS = defaultdict(list)


@contextmanager
def tenant_conn(payload):
    conn = connect()
    try:
        with tenant(conn, payload["iid"]):
            yield conn
    finally:
        conn.close()


def session_of(request: Request):
    return read_session(request.cookies.get(SESSION_COOKIE))


def require(request: Request):
    payload = session_of(request)
    if not payload:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    return payload


def page(request, name, **ctx):
    payload = session_of(request)
    return templates.TemplateResponse(request, name, {
        "user": payload,
        "csrf": payload["csrf"] if payload else "",
        **ctx,
    })


def check_csrf(payload, token):
    if not token or not secrets.compare_digest(token, payload.get("csrf", "")):
        raise HTTPException(status_code=403, detail="invalid CSRF token")


def forbid(role_ok):
    if not role_ok:
        raise HTTPException(status_code=403, detail="not permitted for this role")


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
        "form-action 'self'; frame-ancestors 'none'"
    )
    return response


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if session_of(request):
        return RedirectResponse("/dashboard", status_code=303)
    return page(request, "login.html", error=None)


@app.post("/login")
def login_submit(request: Request, email: str = Form(...), password: str = Form(...)):
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    FAILED_LOGINS[ip] = [t for t in FAILED_LOGINS[ip] if now - t < 600]
    if len(FAILED_LOGINS[ip]) >= 8:
        return page(request, "login.html", error="Too many attempts. Try again in 10 minutes.")
    conn = connect()
    try:
        user = login(conn, email.strip().lower(), password)
    finally:
        conn.close()
    if not user:
        FAILED_LOGINS[ip].append(now)
        return page(request, "login.html", error="Invalid email or password.")
    cookie = make_session(user["user_id"], user["institute_id"], user["role"], user["name"], user["institute_name"])
    resp = RedirectResponse("/dashboard", status_code=303)
    https = request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"
    resp.set_cookie(SESSION_COOKIE, cookie, httponly=True, samesite="lax",
                    secure=https, max_age=SESSION_HOURS * 3600)
    return resp


@app.post("/logout")
def logout(request: Request, csrf: str = Form("")):
    payload = require(request)
    check_csrf(payload, csrf)
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie(SESSION_COOKIE)
    return resp


@app.get("/", response_class=HTMLResponse)
def root(request: Request):
    return RedirectResponse("/dashboard" if session_of(request) else "/login", status_code=303)


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    payload = require(request)
    with tenant_conn(payload) as conn:
        stats = conn.execute(
            "select count(*) filter (where status='active') as active, count(*) as total from student "
            "where deleted_at is null"
        ).fetchone()
        att = conn.execute(
            "select count(*) as n, coalesce(sum(case when status in ('present','late') then 1 else 0 end),0) as p "
            "from attendance_record ar join attendance_session s on s.institute_id=ar.institute_id and s.id=ar.session_id "
            "where s.session_date > %s and s.session_date <= %s", (AS_OF - timedelta(days=28), AS_OF)
        ).fetchone()
        tests = conn.execute(
            "select count(*) as n, max(test_date) as last from test"
        ).fetchone()
        risk = conn.execute(
            "select target, band, count(*) as n from risk_snapshot "
            "where as_of = (select max(as_of) from risk_snapshot) group by target, band"
        ).fetchall()
        fees = None
        if payload["role"] in ("owner", "academic_head", "admin"):
            fees = conn.execute(
                "select coalesce(sum(amount_due - amount_paid),0) as due from fee_instalment "
                "where status <> 'paid' and due_date <= %s", (AS_OF,)
            ).fetchone()
        risky = conn.execute(
            "select s.id, p.full_name, s.roll_no, b.name as batch, r.score, r.band, r.reasons "
            "from risk_snapshot r join student s on s.id=r.student_id "
            "join student_pii p on p.student_id=s.id "
            "join lateral (select b.name from enrollment e join batch b on b.id=e.batch_id "
            "where e.student_id=s.id limit 1) b on true "
            "where r.target='disengagement' and r.as_of=(select max(as_of) from risk_snapshot) "
            "order by r.score desc limit 8"
        ).fetchall()
        weak = conn.execute(
            "select t.name, sub.name as subject, avg(m.mastery_prob) as avg_m, count(*) as n "
            "from mastery_snapshot m join topic t on t.id=m.topic_id "
            "join chapter c on c.id=t.chapter_id join subject sub on sub.id=c.subject_id "
            "where m.as_of=(select max(as_of) from mastery_snapshot) "
            "group by 1,2 having count(*) > 8 order by avg_m asc limit 8"
        ).fetchall()
        last_import = conn.execute(
            "select id, source_filename, status, created_at from import_job order by created_at desc limit 1"
        ).fetchone()
        models = conn.execute(
            "select kind, version, metrics, trained_at from model_version where status='active' order by kind"
        ).fetchall()
        if payload["role"] not in ("owner", "academic_head", "admin"):
            models = [m for m in models if m["kind"] != "risk_fee_default"]
    att_pct = round(100.0 * int(att["p"]) / max(int(att["n"]), 1))
    risk_latest = {}
    for r in risk:
        risk_latest.setdefault(r["target"], {})[r["band"]] = r["n"]
    return page(request, "dashboard.html", active="dashboard", stats=stats, att_pct=att_pct,
                tests=tests, risk=risk_latest, fees=fees, risky=risky, weak=weak,
                last_import=last_import, models=models)


@app.get("/students", response_class=HTMLResponse)
def students(request: Request, q: str = "", batch: str = "", status: str = "active"):
    payload = require(request)
    clauses = ["s.deleted_at is null"]
    params = []
    if q:
        clauses.append("(p.full_name ilike %s or s.roll_no ilike %s)")
        params += [f"%{q}%", f"%{q}%"]
    if batch:
        clauses.append("b.name = %s")
        params.append(batch)
    if status:
        clauses.append("s.status = %s")
        params.append(status)
    where = " and ".join(clauses)
    with tenant_conn(payload) as conn:
        rows = conn.execute(
            f"""
            select s.id, p.full_name, s.roll_no, s.status, b.name as batch,
              (select count(*) from attendance_record a where a.student_id=s.id) as att_n,
              (select coalesce(sum(case when a.status in ('present','late') then 1 else 0 end),0)
                 from attendance_record a where a.student_id=s.id) as att_p,
              (select 100.0*sum(r.marks_awarded)/(4.0*count(*)) from response r
                 where r.student_id=s.id and r.is_correct is not null) as last_score,
              (select band from risk_snapshot r where r.student_id=s.id and r.target='disengagement'
                 order by r.as_of desc limit 1) as band
            from student s join student_pii p on p.student_id=s.id
            join lateral (select b.name from enrollment e join batch b on b.id=e.batch_id
                          where e.student_id=s.id limit 1) b on true
            where {where}
            order by case (select band from risk_snapshot r where r.student_id=s.id and r.target='disengagement'
                           order by r.as_of desc limit 1)
                     when 'high' then 1 when 'medium' then 2 else 3 end, p.full_name
            limit 200
            """, params,
        ).fetchall()
        batches = conn.execute("select name from batch order by name").fetchall()
    return page(request, "students.html", active="students", rows=rows, batches=batches,
                q=q, batch=batch, status=status)


@app.get("/students/{student_id}", response_class=HTMLResponse)
def student_detail(request: Request, student_id: str):
    payload = require(request)
    with tenant_conn(payload) as conn:
        s = conn.execute(
            "select s.*, p.full_name, p.guardian_name, b.name as batch, b.class_level "
            "from student s join student_pii p on p.student_id=s.id "
            "join lateral (select b.* from enrollment e join batch b on b.id=e.batch_id "
            "where e.student_id=s.id limit 1) b on true where s.id=%s", (student_id,)
        ).fetchone()
        if not s:
            raise HTTPException(404, "student not found")
        mastery = conn.execute(
            "select t.name, c.name as chapter, sub.name as subject, m.mastery_prob, m.ability, "
            "m.evidence_count, m.uncertainty from mastery_snapshot m "
            "join topic t on t.id=m.topic_id join chapter c on c.id=t.chapter_id "
            "join subject sub on sub.id=c.subject_id "
            "where m.student_id=%s and m.as_of=(select max(as_of) from mastery_snapshot where student_id=%s) "
            "order by m.mastery_prob desc", (student_id, student_id)
        ).fetchall()
        trend = conn.execute(
            "select t.name, t.test_date, 100.0*sum(r.marks_awarded)/(4.0*count(*)) as pct "
            "from response r join test t on t.id=r.test_id where r.student_id=%s "
            "and r.is_correct is not null group by t.name, t.test_date order by t.test_date",
            (student_id,)
        ).fetchall()
        risks = conn.execute(
            "select target, score, band, reasons, as_of from risk_snapshot where student_id=%s "
            "and as_of=(select max(as_of) from risk_snapshot where student_id=%s) "
            "and (%s or target <> 'fee_default') order by target",
            (student_id, student_id, payload["role"] in ("owner", "academic_head", "admin"))
        ).fetchall()
        pred = conn.execute(
            "select point, lower_bound, upper_bound, coverage, basis from prediction_snapshot "
            "where student_id=%s order by as_of desc limit 1", (student_id,)
        ).fetchone()
        reports = conn.execute(
            "select id, language, status, created_at from report where student_id=%s order by created_at desc limit 6",
            (student_id,)
        ).fetchall()
        interventions = conn.execute(
            "select type, status, notes, opened_at from intervention where student_id=%s order by opened_at desc",
            (student_id,)
        ).fetchall()
        fees = []
        if payload["role"] in ("owner", "academic_head", "admin"):
            fees = conn.execute(
                "select fi.instalment_no, fi.due_date, fi.amount_due, fi.amount_paid, fi.status "
                "from fee_instalment fi join fee_plan fp on fp.id=fi.fee_plan_id "
                "where fp.student_id=%s order by fi.instalment_no", (student_id,)
            ).fetchall()
        consents = []
        if payload["role"] in ("owner", "admin"):
            consents = conn.execute(
                "select purpose, status, method, notice_version, granted_at from consent "
                "where student_id=%s order by purpose", (student_id,)
            ).fetchall()
        guardian = conn.execute(
            "select name, relationship, is_primary from guardian where student_id=%s", (student_id,)
        ).fetchall()
        deletions = []
        if payload["role"] in ("owner", "admin"):
            deletions = conn.execute(
                "select id, status, requested_by, verified_at, executed_at, created_at from deletion_request "
                "where subject_type='student' and subject_id=%s order by created_at desc limit 3", (student_id,)
            ).fetchall()
        study_plan = conn.execute(
            "select w.name, w.mastery_prob, w.evidence_count, "
            "(select body from content_resource where topic_id=w.id and kind='concept' limit 1) as concept, "
            "(select body from content_resource where topic_id=w.id and kind='drill' limit 1) as drill "
            "from (select t.id, t.name, m.mastery_prob, m.evidence_count from mastery_snapshot m "
            "join topic t on t.id=m.topic_id where m.student_id=%s "
            "and m.as_of=(select max(as_of) from mastery_snapshot where student_id=%s) "
            "order by m.mastery_prob asc limit 3) w", (student_id, student_id)
        ).fetchall()
    return page(request, "student.html", active="students", s=s, mastery=mastery, trend=trend,
                risks=risks, pred=pred, reports=reports, interventions=interventions,
                fees=fees, consents=consents, guardian=guardian, study_plan=study_plan,
                deletions=deletions)


@app.post("/students/{student_id}/reports")
def make_report(request: Request, student_id: str, lang: str = Form("en"),
                csrf: str = Form("")):
    payload = require(request)
    check_csrf(payload, csrf)
    if lang not in ("en", "hi"):
        raise HTTPException(400, "unsupported language")
    with tenant_conn(payload) as conn:
        out = generate_report(conn, student_id, lang, AS_OF)
        if not out:
            raise HTTPException(404, "student not found")
        if out.get("error"):
            return RedirectResponse(f"/students/{student_id}?err=consent", status_code=303)
        conn.execute(
            "insert into audit_event (institute_id, actor_user_id, action, entity_type, entity_id) "
            "values (%s,%s,'report.generate','report',%s)",
            (payload["iid"], payload["uid"], out["id"]),
        )
    return RedirectResponse(f"/reports/{out['id']}", status_code=303)


@app.post("/students/{student_id}/interventions")
def add_intervention(request: Request, student_id: str, type: str = Form(...),
                     notes: str = Form(""), csrf: str = Form("")):
    payload = require(request)
    check_csrf(payload, csrf)
    if type not in ("mentoring", "remedial", "parent_call", "counselling", "fee_plan_review", "study_plan"):
        raise HTTPException(400, "invalid intervention type")
    with tenant_conn(payload) as conn:
        conn.execute(
            "insert into intervention (institute_id, student_id, type, opened_by, notes, due_date) "
            "values (%s,%s,%s,%s,%s,%s)",
            (payload["iid"], student_id, type, payload["uid"], notes[:2000] or None,
             date(2026, 10, 31)),
        )
        conn.execute(
            "insert into audit_event (institute_id, actor_user_id, action, entity_type, entity_id, detail) "
            "values (%s,%s,'intervention.open','student',%s,%s)",
            (payload["iid"], payload["uid"], student_id, importer.Jsonb({"type": type})),
        )
    return RedirectResponse(f"/students/{student_id}", status_code=303)


@app.post("/students/{student_id}/deletion-request")
def request_deletion(request: Request, student_id: str, notes: str = Form(""), csrf: str = Form("")):
    payload = require(request)
    check_csrf(payload, csrf)
    if payload["role"] not in ("owner", "admin"):
        raise HTTPException(403, "owner or admin only")
    with tenant_conn(payload) as conn:
        sid = conn.execute("select id from student where id=%s", (student_id,)).fetchone()
        if not sid:
            raise HTTPException(404, "student not found")
        conn.execute(
            "insert into deletion_request (institute_id, subject_type, subject_id, requested_by, status, scope, notes) "
            "values (%s,'student',%s,%s,'pending',%s,%s)",
            (payload["iid"], student_id, payload["uid"],
             importer.Jsonb({"student": "all", "reports": True, "responses": True}),
             (notes[:1000] or "Erasure request logged. Verify guardian identity before execution.")),
        )
        conn.execute(
            "insert into audit_event (institute_id, actor_user_id, action, entity_type, entity_id, detail) "
            "values (%s,%s,'deletion.request','student',%s,%s)",
            (payload["iid"], payload["uid"], student_id, importer.Jsonb({"status": "pending"})),
        )
    return RedirectResponse(f"/students/{student_id}", status_code=303)


@app.get("/mastery", response_class=HTMLResponse)
def mastery_page(request: Request, batch: str = ""):
    payload = require(request)
    with tenant_conn(payload) as conn:
        batches = conn.execute("select id, name from batch order by name").fetchall()
        if not batches:
            return page(request, "heatmap.html", active="mastery", batches=[], batch=None,
                        topics=[], rows=[], legend=[])
        chosen = next((b for b in batches if str(b["id"]) == batch), batches[0])
        students = conn.execute(
            "select s.id, p.full_name, s.roll_no from student s join student_pii p on p.student_id=s.id "
            "join enrollment e on e.student_id=s.id where e.batch_id=%s and s.deleted_at is null "
            "order by s.roll_no limit 60", (chosen["id"],)
        ).fetchall()
        topics = conn.execute(
            "select t.id, t.name, t.code, sub.code as subject from topic t "
            "join chapter c on c.id=t.chapter_id join subject sub on sub.id=c.subject_id "
            "order by sub.code, t.code"
        ).fetchall()
        data = {}
        for r in conn.execute(
            "select student_id, topic_id, mastery_prob from mastery_snapshot "
            "where as_of=(select max(as_of) from mastery_snapshot)"
        ).fetchall():
            data[(str(r["student_id"]), str(r["topic_id"]))] = float(r["mastery_prob"])
    rows = []
    for s in students:
        cells = []
        for t in topics:
            v = data.get((str(s["id"]), str(t["id"])))
            cells.append(v)
        vals = [c for c in cells if c is not None]
        rows.append({"student": s, "cells": cells, "avg": (sum(vals) / len(vals)) if vals else None})
    return page(request, "heatmap.html", active="mastery", batches=batches, batch=chosen,
                topics=topics, rows=rows)


@app.get("/risk", response_class=HTMLResponse)
def risk_page(request: Request, target: str = "disengagement", band: str = ""):
    payload = require(request)
    if target not in ("disengagement", "falling_behind", "fee_default"):
        raise HTTPException(400, "invalid target")
    if target == "fee_default":
        forbid(payload["role"] in ("owner", "academic_head", "admin"))
    with tenant_conn(payload) as conn:
        rows = conn.execute(
            "select s.id, p.full_name, s.roll_no, b.name as batch, r.score, r.band, r.reasons, r.as_of, "
            "r.data_sufficiency from risk_snapshot r join student s on s.id=r.student_id "
            "join student_pii p on p.student_id=s.id "
            "join lateral (select b.name from enrollment e join batch b on b.id=e.batch_id where e.student_id=s.id limit 1) b on true "
            "where r.target=%s and r.as_of=(select max(as_of) from risk_snapshot where target=%s) "
            "and (%s = '' or r.band=%s) order by r.score desc limit 120",
            (target, target, band, band),
        ).fetchall()
        counts = conn.execute(
            "select band, count(*) as n from risk_snapshot where target=%s "
            "and as_of=(select max(as_of) from risk_snapshot where target=%s) group by band",
            (target, target),
        ).fetchall()
        model = conn.execute(
            "select kind, version, metrics, trained_at from model_version where kind=%s "
            "and institute_id=%s order by trained_at desc limit 1",
            ("risk_" + target if target != "falling_behind" else "risk_falling_behind", payload["iid"]),
        ).fetchone()
        if target == "disengagement":
            model = conn.execute(
                "select kind, version, metrics, trained_at from model_version "
                "where kind='risk_disengagement' order by trained_at desc limit 1"
            ).fetchone()
        elif target == "fee_default":
            model = conn.execute(
                "select kind, version, metrics, trained_at from model_version "
                "where kind='risk_fee_default' order by trained_at desc limit 1"
            ).fetchone()
    counts = {r["band"]: r["n"] for r in counts}
    return page(request, "risk.html", active="risk", rows=rows, target=target, band=band,
                counts=counts, model=model)


@app.get("/imports", response_class=HTMLResponse)
def imports_list(request: Request):
    payload = require(request)
    with tenant_conn(payload) as conn:
        jobs = conn.execute(
            "select j.*, u.full_name as created_by_name from import_job j "
            "left join app_user u on u.id=j.created_by order by j.created_at desc limit 40"
        ).fetchall()
    return page(request, "imports.html", active="imports", jobs=jobs)


@app.get("/imports/new", response_class=HTMLResponse)
def import_new(request: Request):
    payload = require(request)
    forbid(payload["role"] in ("owner", "academic_head", "admin"))
    return page(request, "import_new.html", active="imports")


@app.post("/imports")
async def import_upload(request: Request, file: UploadFile = File(...), csrf: str = Form("")):
    payload = require(request)
    forbid(payload["role"] in ("owner", "academic_head", "admin"))
    check_csrf(payload, csrf)
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "only .csv files are accepted")
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(413, "file exceeds 5 MB")
    with tenant_conn(payload) as conn:
        job_id, existed = importer.create_job(conn, payload["iid"], file.filename, content, payload["uid"])
        if not existed:
            importer.parse_and_store(conn, payload["iid"], job_id, content)
    return RedirectResponse(f"/imports/{job_id}", status_code=303)


@app.get("/imports/{job_id}", response_class=HTMLResponse)
def import_detail(request: Request, job_id: str):
    payload = require(request)
    with tenant_conn(payload) as conn:
        job = conn.execute("select * from import_job where id=%s", (job_id,)).fetchone()
        if not job:
            raise HTTPException(404, "import not found")
        rows = conn.execute(
            "select row_no, status, normalized, errors, warnings from import_row "
            "where import_job_id=%s order by case status when 'quarantined' then 0 when 'duplicate' then 1 else 2 end, "
            "row_no limit 300", (job_id,)
        ).fetchall()
    return page(request, "import_detail.html", active="imports", job=job, rows=rows)


@app.post("/imports/{job_id}/commit")
def import_commit(request: Request, job_id: str, csrf: str = Form("")):
    payload = require(request)
    forbid(payload["role"] in ("owner", "academic_head", "admin"))
    check_csrf(payload, csrf)
    with tenant_conn(payload) as conn:
        job = conn.execute("select status from import_job where id=%s", (job_id,)).fetchone()
        if not job:
            raise HTTPException(404, "import not found")
        if job["status"] != "needs_review":
            raise HTTPException(400, "import is not awaiting review")
        stats = importer.commit_job(conn, payload["iid"], job_id, payload["uid"])
    return RedirectResponse(f"/imports/{job_id}", status_code=303)


@app.get("/reports/{report_id}", response_class=HTMLResponse)
def report_view(request: Request, report_id: str):
    payload = require(request)
    with tenant_conn(payload) as conn:
        report = conn.execute(
            "select r.*, p.full_name from report r join student_pii p on p.student_id=r.student_id where r.id=%s",
            (report_id,)
        ).fetchone()
        if not report:
            raise HTTPException(404, "report not found")
    return page(request, "report.html", active="students", report=report)


@app.post("/reports/{report_id}/parent-link")
def parent_link(request: Request, report_id: str, csrf: str = Form("")):
    payload = require(request)
    check_csrf(payload, csrf)
    with tenant_conn(payload) as conn:
        report = conn.execute("select student_id from report where id=%s", (report_id,)).fetchone()
        if not report:
            raise HTTPException(404, "report not found")
        if not conn.execute(
            "select 1 from consent where student_id=%s and purpose='parent_communication' and status='granted'",
            (report["student_id"],)
        ).fetchone():
            raise HTTPException(403, "parent communication consent not on file")
        guardian = conn.execute(
            "select id from guardian where student_id=%s and is_primary limit 1", (report["student_id"],)
        ).fetchone()
        token = secrets.token_urlsafe(24)
        thash = hashlib.sha256(token.encode()).hexdigest()
        conn.execute(
            "insert into parent_link (institute_id, student_id, guardian_id, token_hash, expires_at) "
            "values (%s,%s,%s,%s,now() + interval '90 days')",
            (payload["iid"], report["student_id"], guardian["id"] if guardian else None, thash),
        )
        conn.execute(
            "insert into audit_event (institute_id, actor_user_id, action, entity_type, entity_id) "
            "values (%s,%s,'parent_link.create','report',%s)",
            (payload["iid"], payload["uid"], report_id),
        )
    return RedirectResponse(f"/parent/{token}", status_code=303)


@app.get("/parent/{token}", response_class=HTMLResponse)
def parent_view(request: Request, token: str, lang: str = "en"):
    conn = connect()
    try:
        thash = hashlib.sha256(token.encode()).hexdigest()
        link = conn.execute("select * from resolve_parent_token(%s)", (thash,)).fetchone()
        if not link or link["revoked_at"] or link["expires_at"] < datetime.now(link["expires_at"].tzinfo):
            raise HTTPException(404, "link not found or expired")
        with tenant(conn, link["institute_id"]):
            if not conn.execute(
                "select 1 from consent where student_id=%s and purpose='parent_communication' "
                "and status='granted' limit 1", (link["student_id"],)
            ).fetchone():
                raise HTTPException(404, "link not found or consent withdrawn")
            report = conn.execute(
                "select id, language, body, facts, created_at from report where student_id=%s "
                "and language=%s order by created_at desc limit 1",
                (link["student_id"], lang if lang in ("en", "hi") else "en"),
            ).fetchone()
            if not report:
                report = conn.execute(
                    "select id, language, body, facts, created_at from report where student_id=%s "
                    "order by created_at desc limit 1", (link["student_id"],)
                ).fetchone()
            conn.execute("update parent_link set last_used_at=now() where token_hash=%s", (thash,))
    finally:
        conn.close()
    if not report:
        raise HTTPException(404, "report not available yet")
    return templates.TemplateResponse(request, "parent.html", {
        "report": report, "lang": report["language"], "user": None,
        "csrf": "", "token": token,
    })


@app.post("/reports/{report_id}/whatsapp")
def whatsapp_queue(request: Request, report_id: str, csrf: str = Form("")):
    payload = require(request)
    check_csrf(payload, csrf)
    with tenant_conn(payload) as conn:
        report = conn.execute(
            "select r.student_id, r.language, r.body, g.id as guardian_id from report r "
            "left join guardian g on g.student_id=r.student_id and g.is_primary = true "
            "where r.id=%s", (report_id,)
        ).fetchone()
        if not report:
            raise HTTPException(404, "report not found")
        conn.execute(
            "insert into message_log (institute_id, student_id, guardian_id, template_name, category, status) "
            "values (%s,%s,%s,%s,'utility','queued')",
            (payload["iid"], report["student_id"], report["guardian_id"],
             "parent_report_" + report["language"]),
        )
        conn.execute(
            "insert into audit_event (institute_id, actor_user_id, action, entity_type, entity_id, detail) "
            "values (%s,%s,'whatsapp.queue','report',%s,%s)",
            (payload["iid"], payload["uid"], report_id, importer.Jsonb({"category": "utility"})),
        )
    return RedirectResponse(f"/reports/{report_id}?wa=1", status_code=303)


@app.post("/webhooks/whatsapp")
async def whatsapp_webhook(request: Request):
    secret = request.headers.get("x-webhook-secret", "")
    expected = os.environ.get("WHATSAPP_WEBHOOK_SECRET", "demo-whatsapp")
    if not secrets.compare_digest(secret, expected):
        raise HTTPException(401, "invalid webhook secret")
    body = await request.json()
    institute_id = body.get("institute_id")
    if not institute_id:
        raise HTTPException(400, "institute_id required")
    conn = connect()
    try:
        with tenant(conn, institute_id):
            if not conn.execute(
                "select 1 from institute where id=%s", (institute_id,)
            ).fetchone():
                raise HTTPException(404, "institute not found")
            student = conn.execute(
                "select id from student where roll_no=%s and deleted_at is null", (str(body.get("roll_no")),)
            ).fetchone()
            if not student:
                raise HTTPException(404, "roll number not found")
            if not conn.execute(
                "select 1 from consent where student_id=%s and purpose='core_analytics' and status='granted'",
                (student["id"],)
            ).fetchone():
                raise HTTPException(403, "no core analytics consent")
            test = conn.execute(
                "select id from test where name=%s order by test_date desc limit 1", (body.get("test_name"),)
            ).fetchone()
            if not test:
                raise HTTPException(404, "test not found")
            ti = conn.execute(
                "select ti.id, ti.answer_key, ti.answer_key->>'correct' as correct from test_item ti "
                "where ti.test_id=%s and ti.position=%s", (test["id"], int(body.get("q_no", 0)))
            ).fetchone()
            if not ti:
                raise HTTPException(404, "question not found")
            choice = str(body.get("response", "")).upper()
            if choice not in ("A", "B", "C", "D", ""):
                raise HTTPException(400, "response must be A-D or blank")
            key = ti["correct"]
            if choice:
                correct = choice == key
                marks = 4 if correct else -1
            else:
                correct = None
                marks = None
            conn.execute(
                "insert into response (institute_id, test_id, student_id, test_item_id, raw_response, "
                "is_correct, marks_awarded, source, confidence) values "
                "(%s,%s,%s,%s,%s,%s,%s,'form',0.8) "
                "on conflict (institute_id, test_id, student_id, test_item_id, attempt_no) do nothing",
                (institute_id, test["id"], student["id"], ti["id"],
                 importer.Jsonb({"choice": choice}) if choice else None, correct, marks),
            )
            conn.execute(
                "insert into message_log (institute_id, student_id, template_name, category, status) "
                "values (%s,%s,'whatsapp_score_entry','service','delivered')",
                (institute_id, student["id"]),
            )
    finally:
        conn.close()
    return {"status": "accepted", "student_id": str(student["id"]), "test_id": str(test["id"])}


@app.get("/status", response_class=HTMLResponse)
def status_page(request: Request):
    payload = require(request)
    with tenant_conn(payload) as conn:
        models = conn.execute(
            "select kind, version, trained_at, metrics, status from model_version order by trained_at desc"
        ).fetchall()
        counts = {}
        for table in ("student", "response", "mastery_snapshot", "risk_snapshot", "report", "import_job"):
            counts[table] = conn.execute(f"select count(*) as n from {table}").fetchone()["n"]
        last_import = conn.execute(
            "select created_at, status from import_job order by created_at desc limit 1"
        ).fetchone()
    return page(request, "status.html", active="status", models=models, counts=counts,
                last_import=last_import)


@app.get("/healthz")
def healthz():
    try:
        conn = connect()
        conn.execute("select 1")
        conn.close()
        return {"status": "ok", "time": datetime.now().isoformat()}
    except Exception:
        return {"status": "degraded"}
