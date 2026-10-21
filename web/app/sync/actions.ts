"use server";

import { redirect } from "next/navigation";
import { perform } from "@/lib/actions";
import { apiFetch } from "@/lib/api";
import { connectorFromForm, type ConnectorSpec } from "@/lib/sync";

const PAGE = "/sync";

function parsed(form: FormData): ConnectorSpec | { error: string } {
  try {
    return connectorFromForm(form);
  } catch (error) {
    return { error: error instanceof Error ? error.message : "invalid form" };
  }
}

export async function registerConnector(form: FormData) {
  const name = String(form.get("name") ?? "");
  const body = parsed(form);
  if ("error" in body) redirect(`${PAGE}?error=${encodeURIComponent(body.error)}`);
  await perform(
    () => apiFetch(`/sync/connectors/${name}`, { method: "PUT", body }),
    `${PAGE}?notice=${encodeURIComponent(`${name} saved`)}`,
    PAGE,
  );
}

export async function runNow(form: FormData) {
  const name = String(form.get("name") ?? "");
  await perform(
    () => apiFetch<{ workflow_id: string }>(`/sync/connectors/${name}/run`, { method: "POST" }),
    (result) => `${PAGE}?notice=${encodeURIComponent(`started ${result.workflow_id}`)}`,
    PAGE,
  );
}

export async function applySchedule(form: FormData) {
  const name = String(form.get("name") ?? "");
  await perform(
    () =>
      apiFetch<{ schedule_id: string; paused?: boolean }>(`/sync/connectors/${name}/schedule`, {
        method: "POST",
      }),
    (result) =>
      `${PAGE}?notice=${encodeURIComponent(
        `${result.schedule_id} ${result.paused ? "paused" : "active"}`,
      )}`,
    PAGE,
  );
}
