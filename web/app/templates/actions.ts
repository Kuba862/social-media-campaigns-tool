"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { ApiError, apiFetch } from "@/lib/api";
import { specFromForm } from "@/lib/templates";
import { testSendFromForm } from "@/lib/messages";

/** Runs one API call; on failure the page shows the API's message, on success it reloads. */
async function perform(call: () => Promise<unknown>, next = "/templates"): Promise<never> {
  let failure: string | null = null;
  let status = 0;
  try {
    await call();
  } catch (error) {
    failure = error instanceof ApiError ? error.message : "unexpected error";
    status = error instanceof ApiError ? error.status : 0;
  }
  if (status === 401) {
    redirect("/login");
  }
  if (failure !== null) {
    redirect(`/templates?error=${encodeURIComponent(failure)}`);
  }
  revalidatePath(next);
  redirect(next);
}

export async function createTemplate(form: FormData) {
  await perform(() => apiFetch("/templates", { method: "POST", body: specFromForm(form) }));
}

export async function submitTemplate(form: FormData) {
  const id = String(form.get("id") ?? "");
  await perform(() => apiFetch(`/templates/${id}/submit`, { method: "POST" }));
}

export async function syncTemplate(form: FormData) {
  const id = String(form.get("id") ?? "");
  await perform(() => apiFetch(`/templates/${id}/sync`, { method: "POST" }));
}

export async function sendTest(form: FormData) {
  await perform(
    () => apiFetch("/messages/test", { method: "POST", body: testSendFromForm(form) }),
    "/messages",
  );
}
