export type RunRow = {
  id: string;
  journey_id: string;
  contact_id: string;
  workflow_id: string;
  status: string;
  current_node_id: string | null;
  started_at: string;
  ended_at: string | null;
  contacts: { phone_e164: string } | null; // embedded by GET /journeys/{id}/runs
};

export type StartResult = { started: string[]; skipped: string[]; unknown: string[] };

/** Phone numbers from the start form: split on commas, whitespace and newlines, de-duplicated. */
export function phonesFromForm(form: FormData): string[] {
  const raw = String(form.get("phones") ?? "");
  return [
    ...new Set(
      raw
        .split(/[\s,;]+/)
        .map((item) => item.trim())
        .filter(Boolean),
    ),
  ];
}

/** One sentence for the notice after a start. */
export function startSummary(result: StartResult): string {
  const parts = [`started ${result.started.length}`];
  if (result.skipped.length > 0) parts.push(`skipped ${result.skipped.length} (already running)`);
  if (result.unknown.length > 0) parts.push(`unknown numbers: ${result.unknown.join(", ")}`);
  return parts.join(", ");
}

export function formatTime(iso: string | null): string {
  return iso ? iso.slice(0, 16).replace("T", " ") : "-";
}
