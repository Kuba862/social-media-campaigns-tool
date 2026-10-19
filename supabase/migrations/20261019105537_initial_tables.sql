create or replace function public.set_updated_at()
returns trigger 
language plpgsql
as $$ 
begin
    new.updated_at = now();
    return new;
end;
$$;

create table public.contacts (
    id            uuid primary key default gen_random_uuid(),
    phone_e164    text not null unique,
    first_name    text,
    locale        text,
    country       text,
    attributes    jsonb not null default '{}'::jsonb,
    external_ref  text,
    created_at    timestamptz not null default now(),
    updated_at    timestamptz not null default now()
);


create table public.consents (
    id          uuid primary key default gen_random_uuid(),
    contact_id  uuid not null references public.contacts (id) on delete cascade,
    channel     text not null default 'whatsapp' check (channel = 'whatsapp'),
    status      text not null check (status in ('opted_in', 'opted_out')),
    source      text,
    captured_at timestamptz not null default now(),
    created_at  timestamptz not null default now(),
    updated_at  timestamptz not null default now()
);
create index consents_contact_captured_idx on public.consents (contact_id, captured_at desc);

create table public.wa_phone_numbers (
    id uuid         primary key default gen_random_uuid(),
    waba_id         text not null,
    phone_number_id text not null unique,
    display_phone   text,
    quality_rating  text,
    messaging_limit text,
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now()
);

create table public.templates (
    id uuid             primary key default gen_random_uuid(),
    waba_id             text not null,
    name                text not null,
    language            text not null,
    category            text not null,
    components jsonb    not null default '[]'::jsonb,
    meta_template_id    text,
    status              text not null default 'DRAFT' check (status in ('DRAFT', 'PENDING', 'APPROVED', 'REJECTED')),
    rejection_reason    text,
    created_at          timestamptz not null default now(),
    updated_at          timestamptz not null default now(),
    unique (waba_id, name, language)
);

create table public.journeys (
    id          uuid primary key default gen_random_uuid(),
    name        text not null,
    status text not null default 'draft' check (status in ('draft', 'active', 'archived')),
    created_at  timestamptz not null default now(),
    updated_at  timestamptz not null default now()
);


create table public.journey_versions (
    id              uuid primary key default gen_random_uuid(),
    journey_id      uuid not null references public.journeys (id) on delete cascade,
    version         integer not null,
    definition      jsonb not null,
    published_at    timestamptz,
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now(),
    unique (journey_id, version)
);


create table public.journey_runs (
    id                  uuid primary key default gen_random_uuid(),
    journey_id uuid     not null references public.journeys (id),
    journey_version_id  uuid not null references public.journey_versions (id),
    contact_id          uuid not null references public.contacts (id),
    workflow_id         text not null unique,
    status              text not null default 'running' check (status in ('running', 'completed', 'failed', 'cancelled')),
    current_node_id     text,
    started_at          timestamptz not null default now(),
    ended_at            timestamptz,
    created_at          timestamptz not null default now(),
    updated_at          timestamptz not null default now()
);


create unique index journey_runs_one_active_idx
  on public.journey_runs (journey_id, contact_id)
  where status = 'running';

create table public.messages (
  id               uuid primary key default gen_random_uuid(),
  run_id           uuid not null references public.journey_runs (id) on delete cascade,
  node_id          text not null,
  contact_id       uuid not null references public.contacts (id),
  template_id      uuid not null references public.templates (id),
  idempotency_key  text not null unique,
  wamid            text unique,
  status           text not null default 'pending'
                   check (status in ('pending', 'sent', 'delivered', 'read', 'failed')),
  error            jsonb,
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now()
);

create table public.message_events (
  id           uuid primary key default gen_random_uuid(),
  message_id   uuid references public.messages (id) on delete cascade,
  wamid        text,
  type         text not null check (type in ('sent', 'delivered', 'read', 'failed')),
  payload      jsonb not null default '{}'::jsonb,
  occurred_at  timestamptz not null,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);

create table public.inbound_messages (
  id              uuid primary key default gen_random_uuid(),
  contact_id      uuid not null references public.contacts (id),
  wamid           text not null unique,
  type            text not null,
  text            text,
  button_payload  text,
  context_wamid   text,
  received_at     timestamptz not null,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now()
);

create table public.sync_connectors (
  id             uuid primary key default gen_random_uuid(),
  name           text not null unique,
  schedule_cron  text,
  enabled        boolean not null default false,
  config         jsonb not null default '{}'::jsonb,
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now()
);

create table public.sync_runs (
  id            uuid primary key default gen_random_uuid(),
  connector_id  uuid not null references public.sync_connectors (id) on delete cascade,
  status        text not null default 'running'
                check (status in ('running', 'succeeded', 'failed')),
  stats         jsonb not null default '{}'::jsonb,
  error         text,
  started_at    timestamptz not null default now(),
  ended_at      timestamptz,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);

do $$
declare
  t text;
begin
  foreach t in array array[
    'contacts', 'consents', 'wa_phone_numbers', 'templates', 'journeys',
    'journey_versions', 'journey_runs', 'messages', 'message_events',
    'inbound_messages', 'sync_connectors', 'sync_runs'
  ]
  loop
    execute format('alter table public.%I enable row level security', t);
    execute format(
      'create trigger set_updated_at before update on public.%I
       for each row execute function public.set_updated_at()', t);
  end loop;
end;
$$;
