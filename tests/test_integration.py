import psycopg
import pytest
from fastapi.testclient import TestClient

from app.core import DATABASE_URL, connect, tenant
from app.imports import create_job, parse_and_store
from app.main import app
from app.reports import generate_report, has_consent

ADMIN_URL = "postgresql://postgres:postgres@localhost:55432/postgres"


def admin_conn():
    return psycopg.connect(ADMIN_URL, autocommit=True, row_factory=psycopg.rows.dict_row)


def test_tenant_rls_isolation():
    conn = connect()
    try:
        institutes = conn.execute("select id, name from list_institutes() order by name").fetchall()
        counts = []
        for inst in institutes:
            with tenant(conn, inst["id"]):
                counts.append(conn.execute("select count(*) as n from student").fetchone()["n"])
        assert counts == [350, 250, 400]
        bare = conn.execute("select count(*) as n from student").fetchone()["n"]
        assert bare == 0
        with tenant(conn, institutes[0]["id"]):
            assert conn.execute(
                "select count(*) as n from student where institute_id <> %s", (institutes[0]["id"],)
            ).fetchone()["n"] == 0
    finally:
        conn.close()


def test_demo_csv_quarantine_and_cleanup():
    body = open("app/static/demo_import.csv", "rb").read() + b"\n"
    admin = admin_conn()
    conn = connect()
    try:
        iid = conn.execute("select id from list_institutes() where name='Patna NEET Academy'").fetchone()["id"]
        with tenant(conn, iid):
            user = conn.execute("select id from app_user where email='owner@demo.test'").fetchone()
            job_id, existing = create_job(conn, iid, "pytest_import.csv", body, user["id"])
            assert not existing
            stats = parse_and_store(conn, iid, job_id, body)
        assert stats == {"total": 1205, "accepted": 1200, "quarantined": 4, "duplicate": 1}
    finally:
        if "job_id" in locals():
            admin.execute("delete from import_job where id=%s", (job_id,))
        conn.close()
        admin.close()


def test_report_respects_parent_consent():
    admin = admin_conn()
    conn = connect()
    try:
        row = admin.execute(
            "select s.id, s.institute_id from student s where s.roll_no='2001'"
        ).fetchone()
        with tenant(conn, row["institute_id"]):
            assert has_consent(conn, row["id"])
            conn.execute(
                "update consent set status='withdrawn' where student_id=%s and purpose='parent_communication'",
                (row["id"],),
            )
            out = generate_report(conn, row["id"], "en")
            assert out == {"error": "consent"}
    finally:
        if "row" in locals() and row:
            admin.execute(
                "update consent set status='granted' where student_id=%s and purpose='parent_communication'",
                (row["id"],),
            )
        conn.close()
        admin.close()


def test_api_auth_and_role_redaction():
    with TestClient(app, follow_redirects=False) as client:
        assert client.get("/dashboard").status_code == 303
        bad = client.post("/login", data={"email": "owner@demo.test", "password": "wrong"})
        assert bad.status_code == 200 and "Invalid email or password" in bad.text
        good = client.post("/login", data={"email": "owner@demo.test", "password": "demo1234"})
        assert good.status_code == 303 and good.headers["location"] == "/dashboard"
        page = client.get("/dashboard")
        assert page.status_code == 200 and "Know who is slipping" in page.text
    with TestClient(app, follow_redirects=False) as client:
        client.post("/login", data={"email": "teacher@demo.test", "password": "demo1234"})
        body = client.get("/dashboard").text
        assert "Restricted" in body
        assert "₹" not in body
