create policy model_version_delete on model_version
  for delete using (institute_id = current_tenant());
grant delete on model_version to app_rw;
insert into schema_migration (version, checksum) values ('0008_model_cleanup', 'v1') on conflict do nothing;
