-- Test sends from the panel belong to no journey run; node_id stays "test" for them.
alter table public.messages alter column run_id drop not null;
