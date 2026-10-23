do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'app_rw') then
    create role app_rw nologin;
  end if;
end
$$;

create or replace function current_tenant() returns uuid
language sql stable
as $$ select nullif(current_setting('app.institute_id', true), '')::uuid $$;

create or replace function auth_resolve_login(p_email citext)
returns table (user_id uuid, institute_id uuid, password_hash text, status text, mfa_secret_enc bytea)
language sql
security definer
set search_path = public, pg_temp
as $$
  select u.id, u.institute_id, u.password_hash, u.status, u.mfa_secret_enc
  from app_user u
  where u.email = p_email and u.deleted_at is null
  limit 1
$$;

create or replace function enqueue_job(
  p_institute_id uuid,
  p_kind text,
  p_payload jsonb,
  p_run_after timestamptz default now()
) returns uuid
language sql
security definer
set search_path = public, pg_temp
as $$
  insert into job (institute_id, kind, payload, run_after)
  values (p_institute_id, p_kind, coalesce(p_payload, '{}'::jsonb), coalesce(p_run_after, now()))
  returning id
$$;

create or replace function claim_job(p_worker text, p_kinds text[] default null)
returns setof job
language sql
security definer
set search_path = public, pg_temp
as $$
  with candidate as (
    select j.id
    from job j
    where j.status = 'queued'
      and j.run_after <= now()
      and (p_kinds is null or j.kind = any(p_kinds))
    order by j.run_after, j.created_at
    for update skip locked
    limit 1
  ), claimed as (
    update job j
    set status = 'running',
        locked_by = p_worker,
        locked_at = now(),
        attempts = j.attempts + 1
    from candidate c
    where j.id = c.id
    returning j.*
  )
  select * from claimed
$$;

create or replace function finish_job(p_id uuid, p_ok boolean, p_error text default null)
returns void
language plpgsql
security definer
set search_path = public, pg_temp
as $$
begin
  if p_ok then
    update job
    set status = 'succeeded', completed_at = now(), last_error = null,
        locked_by = null, locked_at = null
    where id = p_id;
  else
    update job
    set status = case when attempts >= max_attempts then 'dead' else 'queued' end,
        last_error = p_error,
        run_after = case when attempts >= max_attempts then run_after
                         else now() + make_interval(secs => least(3600, 30 * (2 ^ attempts))::int) end,
        completed_at = case when attempts >= max_attempts then now() else null end,
        locked_by = null, locked_at = null
    where id = p_id;
  end if;
end
$$;

create or replace function reap_stuck_jobs(p_timeout interval default interval '30 minutes')
returns int
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  n int;
begin
  update job
  set status = 'queued', locked_by = null, locked_at = null
  where status = 'running' and locked_at < now() - p_timeout;
  get diagnostics n = row_count;
  return n;
end
$$;

do $$
declare
  t text;
  tenant_tables text[] := array[
    'batch','app_user','student','student_pii','student_alias','guardian','consent','enrollment',
    'item','item_topic','scoring_policy','test','test_item','import_job','import_row','response',
    'attendance_session','attendance_record','fee_plan','fee_instalment','omr_template','omr_sheet',
    'tag_suggestion','mastery_snapshot','risk_snapshot','prediction_snapshot','intervention',
    'report','message_log','parent_link','device','sync_operation','deletion_request','llm_call',
    'audit_event'
  ];
begin
  foreach t in array tenant_tables loop
    execute format('alter table %I enable row level security', t);
    execute format('alter table %I force row level security', t);
    execute format(
      'create policy tenant_isolation on %I for all using (institute_id = current_tenant()) with check (institute_id = current_tenant())',
      t
    );
  end loop;
end
$$;

alter table institute enable row level security;
alter table institute force row level security;
create policy tenant_isolation on institute
  for all using (id = current_tenant()) with check (id = current_tenant());

alter table model_version enable row level security;
alter table model_version force row level security;
create policy model_version_read on model_version
  for select using (institute_id is null or institute_id = current_tenant());

alter table notice enable row level security;
alter table notice force row level security;
create policy notice_read on notice
  for select using (institute_id is null or institute_id = current_tenant());

alter table taxonomy_version enable row level security;
alter table taxonomy_version force row level security;
create policy taxonomy_read on taxonomy_version for select using (true);

alter table subject enable row level security;
alter table subject force row level security;
create policy subject_read on subject for select using (true);

alter table chapter enable row level security;
alter table chapter force row level security;
create policy chapter_read on chapter for select using (true);

alter table topic enable row level security;
alter table topic force row level security;
create policy topic_read on topic for select using (true);

alter table job enable row level security;
alter table job force row level security;

alter table schema_migration enable row level security;
alter table schema_migration force row level security;

grant usage on schema public to app_rw;

grant select, insert, update, delete on
  batch, app_user, student, student_pii, student_alias, guardian, enrollment,
  item, item_topic, scoring_policy, test, test_item, import_job, import_row,
  attendance_session, attendance_record, fee_plan, fee_instalment, omr_template, omr_sheet,
  tag_suggestion, intervention, report, message_log, parent_link, device, sync_operation,
  deletion_request, llm_call
to app_rw;

grant select, insert, update on institute, consent, response to app_rw;
grant select, insert on mastery_snapshot, risk_snapshot, prediction_snapshot, audit_event to app_rw;
grant select on taxonomy_version, subject, chapter, topic, model_version, notice to app_rw;

grant usage, select on sequence audit_event_id_seq to app_rw;

revoke all on job from public;
revoke all on job from app_rw;
revoke all on schema_migration from public;
revoke all on schema_migration from app_rw;

revoke execute on function claim_job(text, text[]) from public;
revoke execute on function finish_job(uuid, boolean, text) from public;
revoke execute on function enqueue_job(uuid, text, jsonb, timestamptz) from public;
revoke execute on function reap_stuck_jobs(interval) from public;
revoke execute on function auth_resolve_login(citext) from public;

grant execute on function claim_job(text, text[]) to app_rw;
grant execute on function finish_job(uuid, boolean, text) to app_rw;
grant execute on function enqueue_job(uuid, text, jsonb, timestamptz) to app_rw;
grant execute on function reap_stuck_jobs(interval) to app_rw;
grant execute on function auth_resolve_login(citext) to app_rw;
grant execute on function current_tenant() to app_rw;

insert into schema_migration (version, checksum) values ('0002_rls', 'v1');
