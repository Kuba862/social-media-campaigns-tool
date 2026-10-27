export type MessageEvent = { type: string; occurred_at: string; payload?: unknown };

export type MessageRow = {
  id: string;
  status: string;
  node_id: string;
  wamid: string | null;
  error: { message?: string; code?: number } | null;
  meta_response?: unknown;
  created_at: string;
  kind: "template" | "text";
  text: string | null;
  templates: { name: string; language: string } | null;
  contacts: { phone_e164: string } | null;
  message_events: MessageEvent[];
};

export type TestSendBody = { template_id: string; to_e164: string; body_values: string[] };

/** Turns the "Send test" form into the API body; values are comma- or newline-separated. */
export function testSendFromForm(form: FormData): TestSendBody {
  const text = (key: string) => String(form.get(key) ?? "").trim();
  return {
    template_id: text("template_id"),
    to_e164: text("to_e164"),
    body_values: text("body_values")
      .split(/[,\n]/)
      .map((item) => item.trim())
      .filter((item) => item.length > 0),
  };
}

/** Delivery events in time order, as "delivered 16:23:00" labels. */
export function eventLabels(events: MessageEvent[]): string[] {
  return [...events]
    .sort((a, b) => a.occurred_at.localeCompare(b.occurred_at))
    .map((event) => `${event.type} ${event.occurred_at.slice(11, 19)}`);
}

/** What the log shows in its "Message" column: the template, or the start of a service text. */
export function messageLabel(row: Pick<MessageRow, "kind" | "text" | "templates">): string {
  if (row.kind === "text") {
    const text = row.text ?? "";
    return `text: ${text.slice(0, 40)}${text.length > 40 ? "…" : ""}`;
  }
  return row.templates ? `${row.templates.name} (${row.templates.language})` : "-";
}

/** Everything Meta said about a message, for the log's detail view: send response and events. */
export function metaJson(
  row: Pick<MessageRow, "meta_response" | "error" | "message_events">,
): string {
  return JSON.stringify(
    {
      send_response: row.meta_response ?? null,
      error: row.error,
      events: row.message_events.map((event) => event.payload ?? { type: event.type }),
    },
    null,
    2,
  );
}
