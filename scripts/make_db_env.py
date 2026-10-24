"""Create a local .env.deploy with an encoded Supabase admin URL."""
import getpass
import os
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REF = "llexupubzkadeulusoaf"

host = input("Session pooler host (from Supabase Connect → Session pooler): ").strip()
if host.startswith("postgresql://") or "/" in host or " " in host:
    raise SystemExit("Paste only the host, e.g. aws-0-ap-south-1.pooler.supabase.com")

password = getpass.getpass("Database password (typing is hidden): ")
if not password:
    raise SystemExit("Password cannot be empty")

encoded = urllib.parse.quote(password, safe="")
url = f"postgresql://postgres.{REF}:{encoded}@{host}:5432/postgres?sslmode=require"
out = ROOT / ".env.deploy"
out.write_text(f"ADMIN_DATABASE_URL={url}\n")
os.chmod(out, 0o600)
print(f"Wrote {out}")
