create table public.panel_allowed_domains (
  domain      text primary key,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);
alter table public.panel_allowed_domains enable row level security;
create trigger set_updated_at before update on public.panel_allowed_domains
  for each row execute function public.set_updated_at();

create or replace function public.is_panel_user()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select auth.role() = 'authenticated'
     and exists (
       select 1
       from public.panel_allowed_domains d
       where d.domain = lower(split_part(auth.jwt() ->> 'email', '@', 2))
     );
$$;

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
    execute format(
      'create policy panel_read on public.%I
       for select to authenticated using ((select public.is_panel_user()))', t);
  end loop;

  foreach t in array array['templates', 'journeys', 'journey_versions']
  loop
    execute format(
      'create policy panel_insert on public.%I
       for insert to authenticated with check ((select public.is_panel_user()))', t);
    execute format(
      'create policy panel_update on public.%I
       for update to authenticated
       using ((select public.is_panel_user())) with check ((select public.is_panel_user()))', t);
  end loop;
end;
$$;

create or replace function public.forbid_change()
returns trigger
language plpgsql
as $$
begin
  raise exception '% is append-only', tg_table_name using errcode = 'check_violation';
end;
$$;

create trigger consents_append_only
  before update or delete on public.consents
  for each row execute function public.forbid_change();

create trigger message_events_append_only
  before update or delete on public.message_events
  for each row execute function public.forbid_change();

create or replace function public.forbid_published_version_change()
returns trigger
language plpgsql
as $$
begin
  if old.published_at is not null then
    raise exception 'journey version % is published and immutable', old.id
      using errcode = 'check_violation';
  end if;
  if tg_op = 'DELETE' then
    return old;
  end if;
  return new;
end;
$$;

create trigger journey_versions_immutable_after_publish
  before update or delete on public.journey_versions
  for each row execute function public.forbid_published_version_change();