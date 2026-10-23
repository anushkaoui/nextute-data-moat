begin;

insert into institute (id, name, city, state, city_tier, exam_focus) values
  ('11111111-1111-1111-1111-111111111111', 'Institute A', 'Patna', 'Bihar', 2, 'NEET'),
  ('22222222-2222-2222-2222-222222222222', 'Institute B', 'Patna', 'Bihar', 2, 'NEET');

insert into batch (id, institute_id, name, exam_focus, class_level, academic_year, start_date) values
  ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', '11111111-1111-1111-1111-111111111111', 'A-12-1', 'NEET', '12', '2026-27', '2026-04-01'),
  ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', '22222222-2222-2222-2222-222222222222', 'B-12-1', 'NEET', '12', '2026-27', '2026-04-01');

insert into student (id, institute_id, student_key, join_date, class_level) values
  ('a1111111-1111-1111-1111-111111111111', '11111111-1111-1111-1111-111111111111', 'sk_a1', '2026-04-01', '12'),
  ('b1111111-1111-1111-1111-111111111111', '22222222-2222-2222-2222-222222222222', 'sk_b1', '2026-04-01', '12');

insert into student_pii (student_id, institute_id, full_name, name_normalized) values
  ('a1111111-1111-1111-1111-111111111111', '11111111-1111-1111-1111-111111111111', 'Rahul Kumar', 'rahul kumar'),
  ('b1111111-1111-1111-1111-111111111111', '22222222-2222-2222-2222-222222222222', 'Amit Singh', 'amit singh');

insert into enrollment (institute_id, student_id, batch_id, joined_at) values
  ('11111111-1111-1111-1111-111111111111', 'a1111111-1111-1111-1111-111111111111', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', '2026-04-01'),
  ('22222222-2222-2222-2222-222222222222', 'b1111111-1111-1111-1111-111111111111', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', '2026-04-01');

insert into app_user (id, institute_id, email, full_name, password_hash, status) values
  ('cccccccc-cccc-cccc-cccc-cccccccccccc', '11111111-1111-1111-1111-111111111111', 'owner@a.test', 'Owner A', 'x', 'active');

insert into taxonomy_version (id, exam, label, effective_from) values
  ('dddddddd-dddd-dddd-dddd-dddddddddddd', 'NEET', '2026', '2026-04-01');

set role app_rw;
set app.institute_id = '11111111-1111-1111-1111-111111111111';

do $$
declare n int;
begin
  select count(*) into n from student;
  if n <> 1 then raise exception 'tenant A sees % students, expected 1', n; end if;
  select count(*) into n from student_pii;
  if n <> 1 then raise exception 'tenant A sees % pii rows, expected 1', n; end if;
  select count(*) into n from institute;
  if n <> 1 then raise exception 'tenant A sees % institutes, expected 1', n; end if;

  begin
    insert into student (institute_id, student_key, join_date, class_level)
    values ('22222222-2222-2222-2222-222222222222', 'sk_evil', current_date, '12');
    raise exception 'cross-tenant insert was allowed';
  exception when insufficient_privilege then null;
  end;

  begin
    insert into enrollment (institute_id, student_id, batch_id, joined_at)
    values ('11111111-1111-1111-1111-111111111111', 'a1111111-1111-1111-1111-111111111111', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', current_date);
    raise exception 'cross-tenant foreign key was allowed';
  exception when foreign_key_violation then null;
  end;

  begin
    select count(*) into n from job;
    raise exception 'job table was readable (rows=%)', n;
  exception when insufficient_privilege then null;
  end;

  begin
    update mastery_snapshot set ability = 1;
    raise exception 'snapshot update was allowed';
  exception when insufficient_privilege then null;
  end;

  insert into audit_event (institute_id, action, entity_type) values (current_tenant(), 'smoke.test', 'test');
end
$$;

do $$
declare
  v uuid;
  r record;
begin
  v := enqueue_job(current_tenant(), 'smoke', '{"hello":"world"}'::jsonb);
  if v is null then raise exception 'enqueue_job returned null'; end if;
  select * into r from claim_job('smoke-worker', array['smoke']);
  if r.id is null then raise exception 'claim_job returned nothing'; end if;
  if r.id <> v then raise exception 'claim_job returned the wrong job'; end if;
  if r.institute_id <> current_tenant() then raise exception 'job tenant mismatch'; end if;
  if r.attempts <> 1 then raise exception 'claim_job did not increment attempts'; end if;
  perform finish_job(v, true, null);
end
$$;

do $$
begin
  if (select count(*) from taxonomy_version) <> 1 then raise exception 'taxonomy not readable'; end if;
  if (select count(*) from auth_resolve_login('owner@a.test')) <> 1 then raise exception 'login resolution failed'; end if;
  if (select count(*) from auth_resolve_login('nobody@a.test')) <> 0 then raise exception 'login leaked'; end if;
end
$$;

set app.institute_id = '22222222-2222-2222-2222-222222222222';

do $$
declare n int;
begin
  select count(*) into n from student;
  if n <> 1 then raise exception 'tenant B sees % students, expected 1', n; end if;
  if exists (select 1 from student where student_key = 'sk_a1') then raise exception 'tenant B sees tenant A student'; end if;
end
$$;

reset app.institute_id;

do $$
declare n int;
begin
  select count(*) into n from student;
  if n <> 0 then raise exception 'no-tenant context leaked % rows', n; end if;
  select count(*) into n from student_pii;
  if n <> 0 then raise exception 'no-tenant context leaked % pii rows', n; end if;
end
$$;

reset role;

do $$
begin
  if (select status from job where kind = 'smoke') <> 'succeeded' then
    raise exception 'job did not reach succeeded state';
  end if;
  if (select completed_at from job where kind = 'smoke') is null then
    raise exception 'job completed_at not set';
  end if;
end
$$;

rollback;
