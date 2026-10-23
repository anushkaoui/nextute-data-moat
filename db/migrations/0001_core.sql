create extension if not exists citext;
create extension if not exists pg_trgm;
create extension if not exists pgcrypto;

create table schema_migration (
  version text primary key,
  checksum text,
  applied_at timestamptz not null default now()
);

create table institute (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  city text not null,
  state text not null,
  city_tier smallint not null check (city_tier between 1 and 3),
  exam_focus text not null check (exam_focus in ('NEET','JEE_MAIN','JEE_ADV','OTHER')),
  timezone text not null default 'Asia/Kolkata',
  plan text not null default 'starter' check (plan in ('starter','growth','enterprise')),
  student_capacity int check (student_capacity is null or student_capacity > 0),
  status text not null default 'active' check (status in ('active','suspended','closed')),
  settings jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  deleted_at timestamptz
);

create table batch (
  id uuid primary key default gen_random_uuid(),
  institute_id uuid not null references institute(id),
  name text not null,
  exam_focus text not null check (exam_focus in ('NEET','JEE_MAIN','JEE_ADV','OTHER')),
  class_level text not null check (class_level in ('11','12','dropper')),
  academic_year text not null,
  start_date date not null,
  end_date date,
  capacity int check (capacity is null or capacity > 0),
  status text not null default 'active' check (status in ('planned','active','completed','archived')),
  created_at timestamptz not null default now(),
  unique (institute_id, id),
  unique (institute_id, academic_year, name),
  check (end_date is null or end_date >= start_date)
);

create table app_user (
  id uuid primary key default gen_random_uuid(),
  institute_id uuid not null references institute(id),
  email citext not null,
  phone_hmac text,
  full_name text not null,
  password_hash text,
  status text not null default 'invited' check (status in ('invited','active','disabled')),
  mfa_secret_enc bytea,
  last_login_at timestamptz,
  created_at timestamptz not null default now(),
  deleted_at timestamptz,
  unique (institute_id, id),
  unique (institute_id, email)
);

create table role_binding (
  id uuid primary key default gen_random_uuid(),
  institute_id uuid not null,
  user_id uuid not null,
  role text not null check (role in ('owner','academic_head','teacher','admin')),
  batch_id uuid,
  created_at timestamptz not null default now(),
  unique (institute_id, id),
  foreign key (institute_id, user_id) references app_user(institute_id, id) on delete cascade,
  foreign key (institute_id, batch_id) references batch(institute_id, id) on delete cascade,
  unique (institute_id, user_id, role, batch_id)
);

create table student (
  id uuid primary key default gen_random_uuid(),
  institute_id uuid not null references institute(id),
  student_key text not null,
  join_date date not null,
  class_level text not null check (class_level in ('11','12','dropper')),
  status text not null default 'active' check (status in ('active','completed','withdrawn','transferred')),
  exit_date date,
  exit_reason text,
  created_at timestamptz not null default now(),
  deleted_at timestamptz,
  unique (institute_id, id),
  unique (institute_id, student_key),
  check (exit_date is null or exit_date >= join_date)
);
create index student_status_idx on student (institute_id, status);

create table student_pii (
  student_id uuid primary key,
  institute_id uuid not null,
  full_name text not null,
  name_normalized text not null,
  dob date,
  phone_hmac text,
  guardian_name text,
  guardian_phone_enc bytea,
  guardian_phone_hmac text,
  address_enc bytea,
  key_version smallint not null default 1,
  updated_at timestamptz not null default now(),
  foreign key (institute_id, student_id) references student(institute_id, id) on delete cascade
);
create index student_pii_name_trgm_idx on student_pii using gin (name_normalized gin_trgm_ops);
create index student_pii_guardian_phone_idx on student_pii (institute_id, guardian_phone_hmac);

create table student_alias (
  institute_id uuid not null,
  old_student_id uuid not null,
  canonical_student_id uuid not null,
  merged_at timestamptz not null default now(),
  merged_by uuid,
  primary key (institute_id, old_student_id),
  foreign key (institute_id, canonical_student_id) references student(institute_id, id)
);

create table guardian (
  id uuid primary key default gen_random_uuid(),
  institute_id uuid not null,
  student_id uuid not null,
  name text not null,
  phone_enc bytea,
  phone_hmac text,
  relationship text check (relationship in ('father','mother','guardian','other')),
  is_primary boolean not null default false,
  verification_method text check (verification_method in ('in_person_id','otp','digital_locker','institute_attestation')),
  verified_at timestamptz,
  created_at timestamptz not null default now(),
  unique (institute_id, id),
  foreign key (institute_id, student_id) references student(institute_id, id) on delete cascade
);
create unique index guardian_one_primary_idx on guardian (institute_id, student_id) where is_primary;

create table consent (
  id uuid primary key default gen_random_uuid(),
  institute_id uuid not null,
  student_id uuid not null,
  guardian_id uuid,
  purpose text not null check (purpose in ('core_analytics','parent_communication','ai_generation','aggregate_benchmark')),
  status text not null check (status in ('granted','withdrawn')),
  method text not null check (method in ('admission_form_otp','digital_locker','in_person_verified','institute_attestation')),
  evidence_ref text,
  notice_version text not null,
  granted_at timestamptz not null default now(),
  withdrawn_at timestamptz,
  recorded_by uuid,
  unique (institute_id, id),
  foreign key (institute_id, student_id) references student(institute_id, id) on delete cascade,
  foreign key (institute_id, guardian_id) references guardian(institute_id, id)
);
create unique index consent_one_active_idx on consent (institute_id, student_id, purpose) where status = 'granted';

create table notice (
  id uuid primary key default gen_random_uuid(),
  institute_id uuid references institute(id),
  version text not null,
  language text not null check (language in ('hi','en')),
  body text not null,
  published_at timestamptz,
  unique nulls not distinct (institute_id, version, language)
);

create table enrollment (
  id uuid primary key default gen_random_uuid(),
  institute_id uuid not null,
  student_id uuid not null,
  batch_id uuid not null,
  joined_at date not null,
  left_at date,
  left_reason text,
  unique (institute_id, id),
  foreign key (institute_id, student_id) references student(institute_id, id) on delete cascade,
  foreign key (institute_id, batch_id) references batch(institute_id, id) on delete cascade,
  check (left_at is null or left_at >= joined_at)
);
create unique index enrollment_one_active_idx on enrollment (institute_id, student_id, batch_id) where left_at is null;

create table taxonomy_version (
  id uuid primary key default gen_random_uuid(),
  exam text not null check (exam in ('NEET','JEE_MAIN','JEE_ADV')),
  label text not null,
  source_url text,
  effective_from date not null,
  checksum text,
  status text not null default 'active' check (status in ('draft','active','retired')),
  created_at timestamptz not null default now(),
  unique (exam, label)
);

create table subject (
  id uuid primary key default gen_random_uuid(),
  taxonomy_version_id uuid not null references taxonomy_version(id) on delete cascade,
  name text not null,
  code text not null,
  unique (taxonomy_version_id, code)
);

create table chapter (
  id uuid primary key default gen_random_uuid(),
  subject_id uuid not null references subject(id) on delete cascade,
  name text not null,
  code text not null,
  sequence int not null,
  unique (subject_id, code)
);

create table topic (
  id uuid primary key default gen_random_uuid(),
  chapter_id uuid not null references chapter(id) on delete cascade,
  name text not null,
  code text not null,
  definition text,
  sequence int not null,
  difficulty_prior numeric(4,3) check (difficulty_prior between 0 and 1),
  unique (chapter_id, code)
);
create index topic_name_trgm_idx on topic using gin (name gin_trgm_ops);

create table item (
  id uuid primary key default gen_random_uuid(),
  institute_id uuid not null references institute(id),
  subject_id uuid not null references subject(id),
  topic_id uuid not null references topic(id),
  stem text not null,
  item_type text not null check (item_type in ('single_correct','multi_correct','numeric')),
  options jsonb,
  correct_answer jsonb not null,
  source text,
  external_ref text,
  status text not null default 'draft' check (status in ('draft','approved','retired')),
  created_at timestamptz not null default now(),
  deleted_at timestamptz,
  unique (institute_id, id),
  unique (institute_id, external_ref)
);

create table item_topic (
  institute_id uuid not null,
  item_id uuid not null,
  topic_id uuid not null references topic(id),
  weight numeric(3,2) not null default 1 check (weight > 0 and weight <= 1),
  confidence numeric(3,2) not null default 1 check (confidence between 0 and 1),
  source text not null check (source in ('manual','rule','embedding','llm')),
  reviewed_by uuid,
  reviewed_at timestamptz,
  primary key (institute_id, item_id, topic_id),
  foreign key (institute_id, item_id) references item(institute_id, id) on delete cascade
);

create table scoring_policy (
  id uuid primary key default gen_random_uuid(),
  institute_id uuid not null references institute(id),
  name text not null,
  correct_marks numeric(5,2) not null,
  incorrect_marks numeric(5,2) not null,
  unattempted_marks numeric(5,2) not null default 0,
  multi_correct text not null default 'all_or_nothing' check (multi_correct in ('all_or_nothing','partial_proportional','partial_fixed')),
  partial_rule jsonb,
  unique (institute_id, id),
  unique (institute_id, name)
);

create table test (
  id uuid primary key default gen_random_uuid(),
  institute_id uuid not null,
  batch_id uuid not null,
  name text not null,
  test_date date not null,
  duration_min int check (duration_min is null or duration_min > 0),
  total_marks numeric(6,2) check (total_marks is null or total_marks >= 0),
  paper_version text not null default 'A',
  scoring_policy_id uuid not null,
  syllabus_note text,
  status text not null default 'scheduled' check (status in ('scheduled','completed','published','void')),
  published_at timestamptz,
  created_by uuid,
  created_at timestamptz not null default now(),
  unique (institute_id, id),
  foreign key (institute_id, batch_id) references batch(institute_id, id),
  foreign key (institute_id, scoring_policy_id) references scoring_policy(institute_id, id),
  unique (institute_id, batch_id, name, paper_version)
);
create index test_date_idx on test (institute_id, test_date);

create table test_item (
  id uuid primary key default gen_random_uuid(),
  institute_id uuid not null,
  test_id uuid not null,
  item_id uuid not null,
  position int not null check (position > 0),
  marks_override numeric(5,2),
  answer_key jsonb not null,
  answer_key_version int not null default 1 check (answer_key_version > 0),
  key_status text not null default 'draft' check (key_status in ('draft','approved')),
  approved_by uuid,
  approved_at timestamptz,
  unique (institute_id, id),
  foreign key (institute_id, test_id) references test(institute_id, id) on delete cascade,
  foreign key (institute_id, item_id) references item(institute_id, id),
  unique (institute_id, test_id, position)
);

create table import_job (
  id uuid primary key default gen_random_uuid(),
  institute_id uuid not null references institute(id),
  kind text not null check (kind in ('csv','xlsx','omr','forms','whatsapp')),
  source_filename text,
  content_hash text not null,
  storage_key text not null,
  status text not null default 'received' check (status in ('received','parsing','needs_review','committed','failed','rolled_back')),
  idempotency_key text not null,
  stats jsonb not null default '{}'::jsonb,
  error_summary jsonb,
  created_by uuid,
  created_at timestamptz not null default now(),
  completed_at timestamptz,
  unique (institute_id, id),
  unique (institute_id, idempotency_key)
);
create index import_job_hash_idx on import_job (institute_id, content_hash);

create table import_row (
  id uuid primary key default gen_random_uuid(),
  institute_id uuid not null,
  import_job_id uuid not null,
  row_no int not null check (row_no >= 0),
  raw jsonb not null,
  normalized jsonb,
  status text not null check (status in ('accepted','corrected','quarantined','rejected','duplicate')),
  errors jsonb,
  warnings jsonb,
  entity_type text,
  entity_id uuid,
  created_at timestamptz not null default now(),
  unique (institute_id, id),
  foreign key (institute_id, import_job_id) references import_job(institute_id, id) on delete cascade
);
create index import_row_status_idx on import_row (import_job_id, status);

create table response (
  id uuid primary key default gen_random_uuid(),
  institute_id uuid not null,
  test_id uuid not null,
  student_id uuid not null,
  test_item_id uuid not null,
  raw_response jsonb,
  is_correct boolean,
  marks_awarded numeric(5,2),
  attempt_no int not null default 1 check (attempt_no > 0),
  time_taken_sec int check (time_taken_sec is null or time_taken_sec >= 0),
  source text not null check (source in ('omr','csv','form','manual','api')),
  confidence numeric(3,2) check (confidence is null or confidence between 0 and 1),
  import_row_id uuid,
  created_at timestamptz not null default now(),
  foreign key (institute_id, test_id) references test(institute_id, id) on delete cascade,
  foreign key (institute_id, student_id) references student(institute_id, id) on delete cascade,
  foreign key (institute_id, test_item_id) references test_item(institute_id, id) on delete cascade,
  foreign key (institute_id, import_row_id) references import_row(institute_id, id),
  unique (institute_id, test_id, student_id, test_item_id, attempt_no)
);
create index response_student_idx on response (institute_id, student_id, test_id);
create index response_test_idx on response (institute_id, test_id);

create table attendance_session (
  id uuid primary key default gen_random_uuid(),
  institute_id uuid not null,
  batch_id uuid not null,
  session_date date not null,
  start_time time not null,
  duration_min int check (duration_min is null or duration_min > 0),
  session_type text not null default 'class' check (session_type in ('class','test','doubt')),
  subject_id uuid references subject(id),
  topic_id uuid references topic(id),
  created_by uuid,
  created_at timestamptz not null default now(),
  unique (institute_id, id),
  foreign key (institute_id, batch_id) references batch(institute_id, id) on delete cascade
);
create unique index attendance_session_slot_idx on attendance_session (institute_id, batch_id, session_date, start_time);

create table attendance_record (
  id uuid primary key default gen_random_uuid(),
  institute_id uuid not null,
  session_id uuid not null,
  student_id uuid not null,
  status text not null check (status in ('present','absent','late','excused')),
  source text not null check (source in ('manual','offline_sync','import')),
  recorded_by uuid,
  recorded_at timestamptz not null default now(),
  client_ts timestamptz,
  version int not null default 1 check (version > 0),
  foreign key (institute_id, session_id) references attendance_session(institute_id, id) on delete cascade,
  foreign key (institute_id, student_id) references student(institute_id, id) on delete cascade,
  unique (institute_id, session_id, student_id)
);
create index attendance_record_student_idx on attendance_record (institute_id, student_id, recorded_at);

create table fee_plan (
  id uuid primary key default gen_random_uuid(),
  institute_id uuid not null,
  student_id uuid not null,
  academic_year text not null,
  total_fee numeric(10,2) not null check (total_fee >= 0),
  scholarship_amount numeric(10,2) not null default 0 check (scholarship_amount >= 0),
  status text not null default 'active' check (status in ('active','completed','cancelled')),
  created_at timestamptz not null default now(),
  unique (institute_id, id),
  foreign key (institute_id, student_id) references student(institute_id, id) on delete cascade,
  unique (institute_id, student_id, academic_year),
  check (scholarship_amount <= total_fee)
);

create table fee_instalment (
  id uuid primary key default gen_random_uuid(),
  institute_id uuid not null,
  fee_plan_id uuid not null,
  instalment_no int not null check (instalment_no > 0),
  due_date date not null,
  amount_due numeric(10,2) not null check (amount_due >= 0),
  amount_paid numeric(10,2) not null default 0 check (amount_paid >= 0),
  paid_date date,
  grace_days int not null default 0 check (grace_days >= 0),
  payment_method text,
  receipt_ref text,
  status text not null default 'pending' check (status in ('pending','partial','paid','waived')),
  updated_at timestamptz not null default now(),
  unique (institute_id, id),
  foreign key (institute_id, fee_plan_id) references fee_plan(institute_id, id) on delete cascade,
  unique (fee_plan_id, instalment_no),
  check (amount_paid <= amount_due)
);
create index fee_instalment_due_idx on fee_instalment (institute_id, due_date, status);

create table omr_template (
  id uuid primary key default gen_random_uuid(),
  institute_id uuid not null references institute(id),
  name text not null,
  layout jsonb not null,
  version int not null default 1 check (version > 0),
  active boolean not null default true,
  created_at timestamptz not null default now(),
  unique (institute_id, id)
);

create table omr_sheet (
  id uuid primary key default gen_random_uuid(),
  institute_id uuid not null,
  import_job_id uuid not null,
  template_id uuid not null,
  test_id uuid,
  student_id uuid,
  image_key text not null,
  page_no int not null default 1 check (page_no > 0),
  decoded_sheet_code text,
  confidence numeric(3,2) check (confidence is null or confidence between 0 and 1),
  detected jsonb,
  corrected jsonb,
  status text not null check (status in ('auto_accepted','needs_review','reviewed','rejected')),
  reviewed_by uuid,
  reviewed_at timestamptz,
  created_at timestamptz not null default now(),
  unique (institute_id, id),
  foreign key (institute_id, import_job_id) references import_job(institute_id, id) on delete cascade,
  foreign key (institute_id, template_id) references omr_template(institute_id, id),
  foreign key (institute_id, test_id) references test(institute_id, id),
  foreign key (institute_id, student_id) references student(institute_id, id)
);

create table tag_suggestion (
  id uuid primary key default gen_random_uuid(),
  institute_id uuid not null,
  item_id uuid not null,
  topic_id uuid not null references topic(id),
  confidence numeric(3,2) not null check (confidence between 0 and 1),
  method text not null check (method in ('rule','embedding','llm')),
  model_version text,
  status text not null default 'pending' check (status in ('pending','accepted','rejected')),
  reviewed_by uuid,
  reviewed_at timestamptz,
  created_at timestamptz not null default now(),
  unique (institute_id, id),
  foreign key (institute_id, item_id) references item(institute_id, id) on delete cascade
);
create index tag_suggestion_pending_idx on tag_suggestion (institute_id, status);

create table model_version (
  id uuid primary key default gen_random_uuid(),
  institute_id uuid references institute(id),
  kind text not null check (kind in ('rasch','bkt','risk_disengagement','risk_fee_default','performance_percentile','tagger')),
  version text not null,
  trained_at timestamptz,
  data_window daterange,
  metrics jsonb not null default '{}'::jsonb,
  params_key text,
  status text not null default 'shadow' check (status in ('shadow','active','retired')),
  created_at timestamptz not null default now(),
  unique nulls not distinct (institute_id, kind, version)
);

create table mastery_snapshot (
  id uuid primary key default gen_random_uuid(),
  institute_id uuid not null,
  student_id uuid not null,
  topic_id uuid not null references topic(id),
  as_of date not null,
  model_version_id uuid not null references model_version(id),
  ability numeric(6,3),
  mastery_prob numeric(5,4) check (mastery_prob between 0 and 1),
  evidence_count int not null check (evidence_count >= 0),
  uncertainty numeric(5,4) check (uncertainty is null or uncertainty >= 0),
  last_response_at timestamptz,
  created_at timestamptz not null default now(),
  unique (institute_id, id),
  foreign key (institute_id, student_id) references student(institute_id, id) on delete cascade,
  unique (institute_id, student_id, topic_id, as_of, model_version_id)
);
create index mastery_student_idx on mastery_snapshot (institute_id, student_id, as_of desc);
create index mastery_topic_idx on mastery_snapshot (institute_id, topic_id, as_of desc);

create table risk_snapshot (
  id uuid primary key default gen_random_uuid(),
  institute_id uuid not null,
  student_id uuid not null,
  target text not null check (target in ('disengagement','fee_default')),
  as_of date not null,
  horizon_days int not null check (horizon_days > 0),
  score numeric(5,4) not null check (score between 0 and 1),
  band text not null check (band in ('low','medium','high')),
  reasons jsonb not null,
  features jsonb not null,
  data_sufficiency text not null check (data_sufficiency in ('insufficient','low','ok')),
  model_version_id uuid not null references model_version(id),
  created_at timestamptz not null default now(),
  unique (institute_id, id),
  foreign key (institute_id, student_id) references student(institute_id, id) on delete cascade,
  unique (institute_id, student_id, target, as_of, model_version_id)
);
create index risk_student_idx on risk_snapshot (institute_id, student_id, as_of desc);
create index risk_band_idx on risk_snapshot (institute_id, target, as_of, band);

create table prediction_snapshot (
  id uuid primary key default gen_random_uuid(),
  institute_id uuid not null,
  student_id uuid not null,
  kind text not null check (kind in ('internal_percentile','internal_score')),
  as_of date not null,
  point numeric(7,3),
  lower_bound numeric(7,3),
  upper_bound numeric(7,3),
  coverage numeric(4,3) check (coverage is null or coverage between 0 and 1),
  basis jsonb not null,
  data_sufficiency text not null check (data_sufficiency in ('insufficient','low','ok')),
  model_version_id uuid not null references model_version(id),
  created_at timestamptz not null default now(),
  unique (institute_id, id),
  foreign key (institute_id, student_id) references student(institute_id, id) on delete cascade,
  check (lower_bound is null or point is null or lower_bound <= point),
  check (upper_bound is null or point is null or point <= upper_bound),
  unique (institute_id, student_id, kind, as_of, model_version_id)
);

create table intervention (
  id uuid primary key default gen_random_uuid(),
  institute_id uuid not null,
  student_id uuid not null,
  risk_snapshot_id uuid,
  type text not null check (type in ('mentoring','remedial','parent_call','counselling','fee_plan_review','study_plan')),
  opened_by uuid not null,
  opened_at timestamptz not null default now(),
  due_date date,
  status text not null default 'open' check (status in ('open','in_progress','closed','cancelled')),
  notes text,
  outcome text check (outcome in ('improved','no_change','worsened','unknown')),
  closed_at timestamptz,
  closed_by uuid,
  unique (institute_id, id),
  foreign key (institute_id, student_id) references student(institute_id, id) on delete cascade,
  foreign key (institute_id, risk_snapshot_id) references risk_snapshot(institute_id, id)
);
create index intervention_open_idx on intervention (institute_id, status, due_date);

create table llm_call (
  id uuid primary key default gen_random_uuid(),
  institute_id uuid,
  feature text not null check (feature in ('parent_report','study_plan','tagging','doubt_answer','teacher_summary')),
  model text not null,
  prompt_hash text not null,
  input_tokens int,
  output_tokens int,
  cost_micros bigint check (cost_micros is null or cost_micros >= 0),
  latency_ms int,
  schema_valid boolean,
  fallback_used boolean not null default false,
  status text not null check (status in ('ok','invalid','error','blocked')),
  created_at timestamptz not null default now()
);
create index llm_call_feature_idx on llm_call (institute_id, feature, created_at desc);

create table report (
  id uuid primary key default gen_random_uuid(),
  institute_id uuid not null,
  student_id uuid not null,
  kind text not null default 'parent_monthly' check (kind in ('parent_monthly','teacher_summary')),
  language text not null check (language in ('hi','en')),
  period_start date not null,
  period_end date not null,
  facts jsonb not null,
  body text,
  storage_key text,
  status text not null check (status in ('generated','template_fallback','failed','delivered')),
  llm_call_id uuid references llm_call(id),
  created_at timestamptz not null default now(),
  unique (institute_id, id),
  foreign key (institute_id, student_id) references student(institute_id, id) on delete cascade,
  check (period_end >= period_start)
);

create table message_log (
  id uuid primary key default gen_random_uuid(),
  institute_id uuid not null,
  student_id uuid,
  guardian_id uuid,
  template_name text not null,
  category text not null check (category in ('utility','marketing','service')),
  provider_message_id text,
  status text not null check (status in ('queued','sent','delivered','failed','read')),
  cost_micros bigint,
  created_at timestamptz not null default now(),
  foreign key (institute_id, student_id) references student(institute_id, id),
  foreign key (institute_id, guardian_id) references guardian(institute_id, id)
);

create table parent_link (
  id uuid primary key default gen_random_uuid(),
  institute_id uuid not null,
  student_id uuid not null,
  guardian_id uuid,
  token_hash text not null,
  expires_at timestamptz not null,
  revoked_at timestamptz,
  last_used_at timestamptz,
  created_at timestamptz not null default now(),
  unique (token_hash),
  foreign key (institute_id, student_id) references student(institute_id, id) on delete cascade,
  foreign key (institute_id, guardian_id) references guardian(institute_id, id)
);

create table device (
  id uuid primary key default gen_random_uuid(),
  institute_id uuid not null,
  user_id uuid not null,
  name text,
  last_seen_at timestamptz,
  revoked_at timestamptz,
  created_at timestamptz not null default now(),
  unique (institute_id, id),
  foreign key (institute_id, user_id) references app_user(institute_id, id) on delete cascade
);

create table sync_operation (
  id uuid primary key default gen_random_uuid(),
  institute_id uuid not null,
  op_id uuid not null,
  device_id uuid not null,
  user_id uuid not null,
  entity_type text not null,
  entity_id uuid,
  status text not null check (status in ('applied','conflict','rejected')),
  result jsonb,
  created_at timestamptz not null default now(),
  unique (institute_id, op_id),
  foreign key (institute_id, device_id) references device(institute_id, id),
  foreign key (institute_id, user_id) references app_user(institute_id, id)
);

create table audit_event (
  id bigint generated always as identity primary key,
  institute_id uuid,
  actor_user_id uuid,
  action text not null,
  entity_type text,
  entity_id uuid,
  detail jsonb,
  ip inet,
  created_at timestamptz not null default now()
);
create index audit_event_tenant_idx on audit_event (institute_id, created_at desc);

create table deletion_request (
  id uuid primary key default gen_random_uuid(),
  institute_id uuid not null,
  subject_type text not null check (subject_type in ('student','guardian','staff')),
  subject_id uuid not null,
  requested_by uuid,
  verified_at timestamptz,
  status text not null default 'pending' check (status in ('pending','verified','executed','rejected')),
  scope jsonb not null default '{}'::jsonb,
  executed_at timestamptz,
  notes text,
  created_at timestamptz not null default now(),
  unique (institute_id, id)
);

create table job (
  id uuid primary key default gen_random_uuid(),
  institute_id uuid,
  kind text not null,
  payload jsonb not null default '{}'::jsonb,
  status text not null default 'queued' check (status in ('queued','running','succeeded','failed','dead')),
  attempts int not null default 0 check (attempts >= 0),
  max_attempts int not null default 5 check (max_attempts > 0),
  run_after timestamptz not null default now(),
  locked_by text,
  locked_at timestamptz,
  last_error text,
  created_at timestamptz not null default now(),
  completed_at timestamptz
);
create index job_claim_idx on job (run_after) where status = 'queued';

insert into schema_migration (version, checksum) values ('0001_core', 'v1');
