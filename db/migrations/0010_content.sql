-- Curated study resources for retrieval-grounded study plans (RAG-lite).
create table content_resource (
  id uuid primary key default gen_random_uuid(),
  institute_id uuid not null references institute(id) on delete cascade,
  topic_id uuid not null references topic(id) on delete cascade,
  language text not null default 'en' check (language in ('en','hi')),
  kind text not null check (kind in ('concept','drill','common_error')),
  title text not null,
  body text not null,
  source text not null default 'institute_curated',
  created_at timestamptz not null default now(),
  unique (institute_id, topic_id, kind, language)
);
create index content_resource_topic_idx on content_resource (institute_id, topic_id);

alter table content_resource enable row level security;
alter table content_resource force row level security;
create policy content_resource_tenant on content_resource
  using (institute_id = current_tenant())
  with check (institute_id = current_tenant());
grant select, insert, update, delete on content_resource to app_rw;
insert into schema_migration (version, checksum) values ('0010_content', 'v1') on conflict do nothing;
