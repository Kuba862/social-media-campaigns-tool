export const CONNECTOR_NAMES = ["fake", "postgres"] as const; // mirrors backend/sync/connectors

export type ScheduleInfo = { paused: boolean; next_run_at: string | null; runs: number };

export type ConnectorRow = {
  id: string;
  name: string;
  schedule_cron: string;
  enabled: boolean;
  config: Record<string, unknown>;
  schedule: ScheduleInfo | null; // null when Temporal is unreachable or nothing is scheduled
};

export type SyncRunRow = {
  id: string;
  connector_id: string;
  status: string;
  stats: Record<string, number>;
  error: string | null;
  started_at: string;
  ended_at: string | null;
  sync_connectors: { name: string } | null;
};

export type ConnectorSpec = {
  schedule_cron: string;
  enabled: boolean;
  config: Record<string, unknown>;
};

/** The register form as the API body; the config textarea must hold a JSON object. */
export function connectorFromForm(form: FormData): ConnectorSpec {
  const raw = String(form.get("config") ?? "").trim() || "{}";
  let config: unknown;
  try {
    config = JSON.parse(raw);
  } catch {
    throw new Error("config must be valid JSON");
  }
  if (!config || typeof config !== "object" || Array.isArray(config)) {
    throw new Error("config must be a JSON object");
  }
  return {
    schedule_cron: String(form.get("schedule_cron") ?? "").trim(),
    enabled: form.get("enabled") === "on",
    config: config as Record<string, unknown>,
  };
}

/** "extracted 4, inserted 3, invalid 1" with the zero counters left out. */
export function statsSummary(stats: Record<string, number> | null | undefined): string {
  const parts = Object.entries(stats ?? {})
    .filter(([, count]) => count > 0)
    .map(([key, count]) => `${key} ${count}`);
  return parts.length > 0 ? parts.join(", ") : "-";
}

/** "paused, next 2026-10-22 00:00", "next …", "not scheduled" or "Temporal unreachable". */
export function describeSchedule(schedule: ScheduleInfo | null): string {
  if (schedule === null) return "not scheduled";
  const next = schedule.next_run_at
    ? `next ${schedule.next_run_at.slice(0, 16).replace("T", " ")}`
    : "no next run";
  return schedule.paused ? `paused, ${next}` : next;
}
