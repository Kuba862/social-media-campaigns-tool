"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { ApiError, apiFetch } from "@/lib/api";
import type { Definition, Layout } from "@/lib/journey-definition";
import type { JourneyVersionRow } from "@/lib/journeys";

export type SaveResult = { ok: true; version: number } | { ok: false; error: string };
export type PublishResult = { ok: true; version: number } | { ok: false; problems: string[] };

/** PUT the draft; the editor stays on the page and shows the outcome, so no redirect here. */
export async function saveDraft(
  journeyId: string,
  definition: Definition,
  layout: Layout,
): Promise<SaveResult> {
  try {
    const row = await apiFetch<JourneyVersionRow>(`/journeys/${journeyId}/draft`, {
      method: "PUT",
      body: { definition, layout },
    });
    revalidatePath(`/journeys/${journeyId}`);
    return { ok: true, version: row.version };
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) redirect("/login");
    return { ok: false, error: error instanceof ApiError ? error.message : "unexpected error" };
  }
}

/** Save the draft, then publish it; a 422 comes back as the server's list of problems. */
export async function publishDraft(
  journeyId: string,
  definition: Definition,
  layout: Layout,
): Promise<PublishResult> {
  const saved = await saveDraft(journeyId, definition, layout);
  if (!saved.ok) return { ok: false, problems: [saved.error] };
  try {
    const row = await apiFetch<JourneyVersionRow>(`/journeys/${journeyId}/publish`, {
      method: "POST",
    });
    revalidatePath(`/journeys/${journeyId}`);
    revalidatePath("/journeys");
    return { ok: true, version: row.version };
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) redirect("/login");
    const problems =
      error instanceof ApiError && error.details.length > 0
        ? error.details
        : [error instanceof ApiError ? error.message : "unexpected error"];
    return { ok: false, problems };
  }
}
