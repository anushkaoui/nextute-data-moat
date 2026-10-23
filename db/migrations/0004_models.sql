create policy model_version_write on model_version
  for insert with check (institute_id = current_tenant());
create policy model_version_update on model_version
  for update using (institute_id = current_tenant()) with check (institute_id = current_tenant());
grant insert, update on model_version to app_rw;
insert into schema_migration (version, checksum) values ('0004_models', 'v1') on conflict do nothing;
