import { describe, expect, it } from "vitest";
import { eventLabels, metaJson, testSendFromForm } from "./messages";

describe("testSendFromForm", () => {
  it("builds the API body and splits values", () => {
    const form = new FormData();
    form.append("template_id", "t-1");
    form.append("to_e164", " +48600000001 ");
    form.append("body_values", "Ala, 20%");
    expect(testSendFromForm(form)).toEqual({
      template_id: "t-1",
      to_e164: "+48600000001",
      body_values: ["Ala", "20%"],
    });
  });

  it("sends an empty list when there are no values", () => {
    const form = new FormData();
    form.append("template_id", "t-1");
    form.append("to_e164", "+48600000001");
    expect(testSendFromForm(form).body_values).toEqual([]);
  });
});

describe("eventLabels", () => {
  it("orders events by time and shortens the timestamp", () => {
    const labels = eventLabels([
      { type: "read", occurred_at: "2025-06-18T16:23:30+00:00" },
      { type: "sent", occurred_at: "2025-06-18T16:22:53+00:00" },
      { type: "delivered", occurred_at: "2025-06-18T16:23:00+00:00" },
    ]);
    expect(labels).toEqual(["sent 16:22:53", "delivered 16:23:00", "read 16:23:30"]);
  });
});

describe("metaJson", () => {
  it("bundles the send response, the error and the raw events for the detail view", () => {
    const text = metaJson({
      meta_response: { messages: [{ id: "wamid.1" }] },
      error: null,
      message_events: [
        {
          type: "delivered",
          occurred_at: "2026-10-27T10:00:00+00:00",
          payload: { status: "delivered" },
        },
        { type: "read", occurred_at: "2026-10-27T10:01:00+00:00" },
      ],
    });
    expect(JSON.parse(text)).toEqual({
      send_response: { messages: [{ id: "wamid.1" }] },
      error: null,
      events: [{ status: "delivered" }, { type: "read" }],
    });
  });
});
