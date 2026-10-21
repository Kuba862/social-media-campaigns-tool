-- Commands from the API to the worker (decision 41): the API never talks to Temporal itself.
create table public.dispatch_queue (
  id          uuid primary key default gen_random_uuid(),
  kind        text not null check (kind in ('start_run', 'cancel_run', 'signal', 'start_sync', 'apply_schedule')),
  payload     jsonb not null default '{}'::jsonb,
  attempts    integer not null default 0,
  error       text,
  done_at     timestamptz,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);
create index dispatch_queue_pending_idx on public.dispatch_queue (created_at) where done_at is null;
alter table public.dispatch_queue enable row level security;  -- service role only, no panel policies
create trigger set_updated_at before update on public.dispatch_queue
  for each row execute function public.set_updated_at();

-- A run is queued until the worker starts its workflow; still one active run per journey and contact.
alter table public.journey_runs drop constraint journey_runs_status_check;
alter table public.journey_runs add constraint journey_runs_status_check check (
  status in ('queued', 'running', 'completed', 'failed', 'cancelled', 'skipped_no_consent', 'opted_out')
);
drop index public.journey_runs_one_active_idx;
create unique index journey_runs_one_active_idx
  on public.journey_runs (journey_id, contact_id)
  where status in ('queued', 'running');

-- The worker reports the Temporal schedule it applied; the panel reads it from here.
alter table public.sync_connectors add column schedule_state jsonb;
