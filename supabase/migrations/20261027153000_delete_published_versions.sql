-- A published version stays immutable, but it may be deleted when nothing references it: the
-- foreign key from journey_runs keeps versions with runs, and the API refuses those first.
create or replace function public.forbid_published_version_change()
returns trigger
language plpgsql
as $$
begin
  if tg_op = 'DELETE' then
    return old;
  end if;
  if old.published_at is not null then
    raise exception 'journey version % is published and immutable', old.id
      using errcode = 'check_violation';
  end if;
  return new;
end;
$$;
