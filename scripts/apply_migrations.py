import os
import pathlib
import sys

import psycopg

ROOT = pathlib.Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "db" / "migrations"
ADMIN_URL = os.environ.get(
    "ADMIN_DATABASE_URL", "postgresql://postgres:postgres@localhost:55432/postgres"
)


def main():
    conn = psycopg.connect(ADMIN_URL)
    try:
        exists = conn.execute("select to_regclass('public.schema_migration')").fetchone()[0]
        applied = set()
        if exists:
            applied = {r[0] for r in conn.execute("select version from schema_migration").fetchall()}
        for path in sorted(MIGRATIONS.glob("*.sql")):
            version = path.stem
            if version in applied:
                print(f"skip {version}")
                continue
            with conn.transaction():
                conn.execute(path.read_text())
            print(f"apply {version}")
    finally:
        conn.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"migration failed: {exc}", file=sys.stderr)
        raise
