create or replace function list_institutes()
returns table (id uuid, name text, city text)
language sql
security definer
set search_path = public, pg_temp
as $$ select i.id, i.name, i.city from institute i order by i.name $$;
revoke execute on function list_institutes() from public;
grant execute on function list_institutes() to app_rw;
insert into schema_migration (version, checksum) values ('0005_directory', 'v1') on conflict do nothing;
