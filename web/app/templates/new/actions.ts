"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { attempt } from "@/lib/actions";
import { apiFetch } from "@/lib/api";
import type { ServiceMessageSpec, TemplateSpec } from "@/lib/templates";

/** Saves a Meta template draft; the API's message comes back so the form can keep its state. */
export async function saveTemplate(spec: TemplateSpec): Promise<string | null> {
  const outcome = await attempt(() => apiFetch("/templates", { method: "POST", body: spec }));
  if (!outcome.ok) return outcome.error;
  revalidatePath("/templates");
  redirect("/templates");
}

export async function saveServiceMessage(spec: ServiceMessageSpec): Promise<string | null> {
  const outcome = await attempt(() =>
    apiFetch("/templates/service", { method: "POST", body: spec }),
  );
  if (!outcome.ok) return outcome.error;
  revalidatePath("/templates");
  redirect("/templates");
}
