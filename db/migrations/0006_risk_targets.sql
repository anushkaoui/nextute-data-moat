alter table risk_snapshot drop constraint risk_snapshot_target_check;
alter table risk_snapshot add constraint risk_snapshot_target_check
  check (target in ('disengagement', 'fee_default', 'falling_behind'));
alter table model_version drop constraint model_version_kind_check;
alter table model_version add constraint model_version_kind_check
  check (kind in ('rasch','bkt','risk_disengagement','risk_fee_default','risk_falling_behind','performance_percentile','tagger'));
insert into schema_migration (version, checksum) values ('0006_risk_targets', 'v1') on conflict do nothing;
