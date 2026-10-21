"use server";

import { perform } from "@/lib/actions";
import { apiFetch } from "@/lib/api";
import { journeyFromForm, type JourneyRow } from "@/lib/journeys";

export async function createJourney(form: FormData) {
  await perform(
    () => apiFetch<JourneyRow>("/journeys", { method: "POST", body: journeyFromForm(form) }),
    (journey) => `/journeys/${journey.id}`,
    "/journeys",
  );
}
