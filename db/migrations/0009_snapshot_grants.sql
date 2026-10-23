grant delete on mastery_snapshot, risk_snapshot, prediction_snapshot to app_rw;
insert into schema_migration (version, checksum) values ('0009_snapshot_grants', 'v1') on conflict do nothing;
