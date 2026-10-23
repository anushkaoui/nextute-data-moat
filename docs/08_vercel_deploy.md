# Deploying on Vercel

Vercel can run this FastAPI app as a Python Function, but it **cannot** host the Postgres database. The current `localhost:55432` Docker database is development-only. For Vercel you need a hosted Postgres (Neon, Supabase, Railway, etc.) and two environment variables.

## What Vercel runs

- Entrypoint: `app/main.py` → FastAPI `app` (zero-config Python framework detection).
- Static files: FastAPI mounts `/static`; Vercel promotes it or serves it from the function bundle.
- Templates: `app/templates` is included in the function bundle.
- `vercel.json` only raises `maxDuration` to 60 s.
- No `uvicorn` process, no background worker, no local database.

## 1. Create a hosted Postgres

Use Neon or Supabase free tier. Create a database and copy:

- **Admin URL** — for migrations and seeding only.
- **App URL** — pooled connection string for `app_rw`.

For Neon, prefer the `-pooler` host for the app URL. For Supabase, use the **transaction pooler** on port `6543` for the app URL, and the **direct connection** (or session pooler if your local network is IPv4-only) for `ADMIN_DATABASE_URL`.

Supabase shared-pooler usernames include the project ref: `postgres.[PROJECT-REF]` for admin and `app_rw.[PROJECT-REF]` for the app role. Copy the host and port from the dashboard rather than composing them.

## 2. Apply migrations and seed from your machine

```bash
cd /Users/anushkagupta/data-moat
export ADMIN_DATABASE_URL='postgresql://ADMIN_USER:ADMIN_PASSWORD@HOST/DB?sslmode=require'

python3 scripts/apply_migrations.py
```

The dev migration creates `app_rw` with the local password `devpass`. Change it before using the app URL:

```bash
python3 - <<'PY'
import os, psycopg
conn = psycopg.connect(os.environ["ADMIN_DATABASE_URL"], autocommit=True)
conn.execute("alter role app_rw password 'REPLACE_WITH_A_LONG_RANDOM_PASSWORD'")
print("app_rw password updated")
PY
```

Supabase transaction mode does not support prepared statements or session state. The app disables prepared statements (`prepare_threshold=None`) and sets time zone inside the tenant transaction, so the transaction pooler is safe.

Seed the synthetic pilot and build snapshots:

```bash
export DATABASE_URL='postgresql://app_rw:REPLACE_WITH_A_LONG_RANDOM_PASSWORD@HOST/DB?sslmode=require'
python3 -m app.synth
python3 -m app.analytics
```

`app.synth` uses `ADMIN_DATABASE_URL`; `app.analytics` uses `DATABASE_URL` under RLS. The seed is synthetic — do not put real student data into a public demo.

## 3. Import the GitHub repo into Vercel

1. Vercel dashboard → **Add New → Project**.
2. Import `anushkaoui/nextute-data-moat-public`.
3. Framework preset: **FastAPI** (should auto-detect).
4. Root directory: `./`.
5. Build command: leave default.
6. Add environment variables:

| Variable | Value | Notes |
|---|---|---|
| `DATABASE_URL` | pooled app URL for `app_rw` | Required |
| `SESSION_SECRET` | 48+ random bytes | Required; app fails closed on Vercel if missing |
| `WHATSAPP_WEBHOOK_SECRET` | random string | Optional |

Do **not** add `ADMIN_DATABASE_URL` to Vercel. Migrations are run from your machine or CI, not by the web app.

7. Deploy.

## 4. Smoke test

```bash
curl -s https://YOUR-PROJECT.vercel.app/healthz
# {"status":"ok","time":"..."}
```

Then open `/login` and use the demo accounts. If the dashboard is empty, the database was not seeded or `DATABASE_URL` points to a different database.

## 5. Operational notes

- **Serverless connections:** every request opens a connection. Use a pooled URL; do not point Vercel at a low-connection-limit direct Postgres.
- **Analytics is offline:** the app reads snapshots. Run `python3 -m app.analytics` locally/CI, or add a protected cron endpoint later. Vercel does not run the worker.
- **Static assets:** `app.mount("/static", StaticFiles(...))` is handled by Vercel's FastAPI integration. If a future deployment drops the mount, use a `public/` directory or `[tool.vercel.fastapi.static]`.
- **Hobby plan:** Vercel's free tier is intended for personal/non-commercial use. For a commercial pilot, use Pro.
- **Secrets:** the repo contains only dev defaults. Set `SESSION_SECRET`, rotate the `app_rw` password, and never commit `.env`.
- **Data:** the public demo should stay synthetic. Real student data needs the DPDP review, DPA and consent flow described in the validation report.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `RuntimeError: Set SESSION_SECRET` | Add `SESSION_SECRET` in Vercel and redeploy |
| 500 on `/login` | Check `DATABASE_URL`, SSL mode, and app role password |
| `/healthz` works but pages 500 | Migrations not applied or `app_rw` lacks grants |
| Empty dashboard | Run `app.synth` and `app.analytics` against the same DB |
| `relation "student" does not exist` | Run `scripts/apply_migrations.py` with `ADMIN_DATABASE_URL` |
| Static CSS 404 | Confirm `app/static` is present in the deployment bundle |
| Function timeout | Seed/analytics should not run in a request; they are offline jobs |
