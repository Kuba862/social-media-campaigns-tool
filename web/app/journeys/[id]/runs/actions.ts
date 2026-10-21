"use server";

import { perform } from "@/lib/actions";
import { apiFetch } from "@/lib/api";
import { phonesFromForm, startSummary, type StartResult } from "@/lib/runs";

export async function startRuns(form: FormData) {
  const journeyId = String(form.get("journey_id") ?? "");
  const back = `/journeys/${journeyId}/runs`;
  await perform(
    () =>
      apiFetch<StartResult>(`/journeys/${journeyId}/runs`, {
        method: "POST",
        body: { phones: phonesFromForm(form) },
      }),
    (result) => `${back}?notice=${encodeURIComponent(startSummary(result))}`,
    back,
  );
}

export async function cancelRun(form: FormData) {
  const journeyId = String(form.get("journey_id") ?? "");
  const runId = String(form.get("run_id") ?? "");
  const back = `/journeys/${journeyId}/runs`;
  await perform(() => apiFetch(`/runs/${runId}/cancel`, { method: "POST" }), back, back);
}
