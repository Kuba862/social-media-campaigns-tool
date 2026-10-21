-- The editor keeps node positions next to the definition; the definition stays pure engine input.
alter table public.journey_versions
  add column layout jsonb not null default '{}'::jsonb;

-- At most one unpublished version (the draft) per journey.
create unique index journey_versions_one_draft_idx
  on public.journey_versions (journey_id)
  where published_at is null;
