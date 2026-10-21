-- Meta retries webhooks; the same status for the same message must not create a second event.
alter table public.message_events
  add constraint message_events_wamid_type_key unique (wamid, type);
