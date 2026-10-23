alter table student add column if not exists roll_no text;
create unique index if not exists student_roll_idx on student (institute_id, roll_no) where roll_no is not null;

create table if not exists item_difficulty (
  id uuid primary key default gen_random_uuid(),
  institute_id uuid not null,
  item_id uuid not null,
  as_of date not null,
  model_version_id uuid not null references model_version(id),
  difficulty numeric(6,3) not null,
  std_error numeric(5,3),
  response_count int not null check (response_count >= 0),
  status text not null check (status in ('calibrated','provisional','uncalibrated')),
  unique (institute_id, id),
  foreign key (institute_id, item_id) references item(institute_id, id) on delete cascade,
  unique (institute_id, item_id, as_of, model_version_id)
);

alter table item_difficulty enable row level security;
alter table item_difficulty force row level security;
create policy tenant_isolation on item_difficulty
  for all using (institute_id = current_tenant()) with check (institute_id = current_tenant());
grant select, insert, update, delete on item_difficulty to app_rw;

create or replace function resolve_parent_token(p_token_hash text)
returns table (institute_id uuid, student_id uuid, guardian_id uuid, expires_at timestamptz, revoked_at timestamptz)
language sql
security definer
set search_path = public, pg_temp
as $$
  select l.institute_id, l.student_id, l.guardian_id, l.expires_at, l.revoked_at
  from parent_link l
  where l.token_hash = p_token_hash
  limit 1
$$;
revoke execute on function resolve_parent_token(text) from public;
grant execute on function resolve_parent_token(text) to app_rw;

alter role app_rw login password 'devpass';

insert into schema_migration (version, checksum) values ('0003_dev', 'v1');
