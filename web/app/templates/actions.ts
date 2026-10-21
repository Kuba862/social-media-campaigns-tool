"use server";

import { perform } from "@/lib/actions";
import { apiFetch } from "@/lib/api";
import { specFromForm } from "@/lib/templates";
import { testSendFromForm } from "@/lib/messages";

export async function createTemplate(form: FormData) {
  await perform(
    () => apiFetch("/templates", { method: "POST", body: specFromForm(form) }),
    "/templates",
    "/templates",
  );
}

export async function submitTemplate(form: FormData) {
  const id = String(form.get("id") ?? "");
  await perform(
    () => apiFetch(`/templates/${id}/submit`, { method: "POST" }),
    "/templates",
    "/templates",
  );
}

export async function syncTemplate(form: FormData) {
  const id = String(form.get("id") ?? "");
  await perform(
    () => apiFetch(`/templates/${id}/sync`, { method: "POST" }),
    "/templates",
    "/templates",
  );
}

export async function sendTest(form: FormData) {
  await perform(
    () => apiFetch("/messages/test", { method: "POST", body: testSendFromForm(form) }),
    "/messages",
    "/templates",
  );
}
