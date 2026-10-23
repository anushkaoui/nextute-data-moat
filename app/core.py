import base64
import hashlib
import hmac
import json
import os
import secrets
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import psycopg
from psycopg.rows import dict_row

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://app_rw:devpass@localhost:55432/postgres"
)
SESSION_SECRET = os.environ.get("SESSION_SECRET", "dev-secret-change-me").encode()
SESSION_COOKIE = "dm_session"
SESSION_HOURS = 12
SCRYPT_N = 2**14


def connect():
    conn = psycopg.connect(DATABASE_URL, row_factory=dict_row, autocommit=True)
    conn.execute("set time zone 'Asia/Kolkata'")
    return conn


@contextmanager
def tenant(conn, institute_id):
    with conn.transaction():
        conn.execute("select set_config('app.institute_id', %s, true)", (str(institute_id),))
        yield conn


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=SCRYPT_N, r=8, p=1, dklen=32)
    return "scrypt${}${}${}${}${}".format(
        SCRYPT_N, 8, 1, salt.hex(), digest.hex()
    )


def verify_password(password: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        scheme, n, r, p, salt_hex, digest_hex = stored.split("$")
        if scheme != "scrypt":
            return False
        digest = hashlib.scrypt(
            password.encode(),
            salt=bytes.fromhex(salt_hex),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(bytes.fromhex(digest_hex)),
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except Exception:
        return False


def sign_session(payload: dict) -> str:
    body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode()
    sig = hmac.new(SESSION_SECRET, body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def read_session(raw: str | None) -> dict | None:
    if not raw or "." not in raw:
        return None
    body, sig = raw.rsplit(".", 1)
    expected = hmac.new(SESSION_SECRET, body.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return None
    try:
        payload = json.loads(base64.urlsafe_b64decode(body.encode()))
    except Exception:
        return None
    if payload.get("exp", 0) < datetime.now(timezone.utc).timestamp():
        return None
    return payload


def make_session(user_id, institute_id, role, name, institute_name=""):
    return sign_session(
        {
            "uid": str(user_id),
            "iid": str(institute_id),
            "role": role,
            "name": name,
            "institute": institute_name,
            "csrf": secrets.token_urlsafe(18),
            "exp": (datetime.now(timezone.utc) + timedelta(hours=SESSION_HOURS)).timestamp(),
        }
    )


def login(conn, email: str, password: str):
    row = conn.execute(
        "select * from auth_resolve_login(%s)", (email,)
    ).fetchone()
    if not row or row["status"] != "active" or not verify_password(password, row["password_hash"]):
        return None
    with tenant(conn, row["institute_id"]):
        user = conn.execute(
            "select u.id, u.full_name, u.institute_id, i.name as institute_name "
            "from app_user u join institute i on i.id = u.institute_id where u.id = %s",
            (row["user_id"],),
        ).fetchone()
        binding = conn.execute(
            "select role from role_binding where user_id = %s order by "
            "case role when 'owner' then 1 when 'academic_head' then 2 when 'admin' then 3 else 4 end limit 1",
            (row["user_id"],),
        ).fetchone()
    if not user:
        return None
    return {
        "user_id": user["id"],
        "institute_id": user["institute_id"],
        "name": user["full_name"],
        "institute_name": user["institute_name"],
        "role": (binding or {}).get("role", "teacher"),
    }


def role_home(role: str) -> str:
    return "/dashboard" if role in ("owner", "academic_head", "teacher") else "/imports"
