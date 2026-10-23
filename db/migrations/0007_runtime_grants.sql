grant select on role_binding to app_rw;
insert into schema_migration (version, checksum) values ('0007_runtime_grants', 'v1') on conflict do nothing;
