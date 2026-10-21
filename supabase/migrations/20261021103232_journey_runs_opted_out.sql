-- opt_out ends a run on its own status, distinct from a cancel from the panel (guide section 4.2).
alter table public.journey_runs drop constraint journey_runs_status_check;
alter table public.journey_runs add constraint journey_runs_status_check check (
  status in ('running', 'completed', 'failed', 'cancelled', 'skipped_no_consent', 'opted_out')
);
