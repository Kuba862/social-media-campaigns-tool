"use server";

import { perform } from "@/lib/actions";
import { apiFetch } from "@/lib/api";

export async function deleteVersion(form: FormData) {
  const journeyId = String(form.get("journey_id") ?? "");
  const versionId = String(form.get("version_id") ?? "");
  await perform(
    () => apiFetch(`/journeys/${journeyId}/versions/${versionId}`, { method: "DELETE" }),
    `/journeys/${journeyId}`,
    `/journeys/${journeyId}`,
  );
}
