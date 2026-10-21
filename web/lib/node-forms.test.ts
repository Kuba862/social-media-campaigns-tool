import { describe, expect, it } from "vitest";
import {
  branchApply,
  branchDefaults,
  fromIso,
  placeholderCount,
  sendTemplateApply,
  sendTemplateDefaults,
  toIso,
  updateContactApply,
  variableRows,
  waitForReplyApply,
} from "./node-forms";

describe("durations", () => {
  it("round-trip the engine's ISO 8601 forms through amount and unit", () => {
    for (const iso of ["P2D", "PT3H", "PT45M"]) expect(toIso(fromIso(iso))).toBe(iso);
    expect(fromIso("PT1H30M")).toEqual({ amount: "90", unit: "minutes" });
    expect(fromIso("P1DT12H")).toEqual({ amount: "36", unit: "hours" });
    expect(fromIso("garbage")).toEqual({ amount: "1", unit: "hours" });
  });
});

describe("send_template", () => {
  const templates = [{ id: "t-2", name: "offer", language: "pl", placeholders: 2 }];
  const node = {
    id: "send_1",
    type: "send_template" as const,
    template_id: "t-2",
    variables: { "1": "contact.first_name" },
  };

  it("counts placeholders and pads the variable rows to the template", () => {
    expect(placeholderCount("Cześć {{1}}, oferta {{2}} do {{1}}")).toBe(2);
    expect(placeholderCount("no variables")).toBe(0);
    expect(sendTemplateDefaults(node, { next: "end" }, templates)).toEqual({
      template_id: "t-2",
      variables: [{ path: "contact.first_name" }, { path: "" }],
      next: "end",
    });
    expect(variableRows(1, [{ path: "a" }, { path: "b" }])).toEqual([{ path: "a" }]);
  });

  it("writes the rows back as a 1-based map and the next handle", () => {
    const applied = sendTemplateApply(node, {
      template_id: "t-2",
      variables: [{ path: "contact.first_name" }, { path: "contact.country" }],
      next: "wait_1",
    });
    expect(applied.node).toEqual({
      ...node,
      variables: { "1": "contact.first_name", "2": "contact.country" },
    });
    expect(applied.targets).toEqual({ next: "wait_1" });
  });
});

describe("branch", () => {
  const node = {
    id: "branch_1",
    type: "branch" as const,
    conditions: [{ if: { "reply.button_payload": "YES" }, next: "send_2" }],
    else: "end",
  };

  it("shows one row per condition, preferring the canvas edges as targets", () => {
    expect(branchDefaults(node, { "cond-0": "wait_1" })).toEqual({
      conditions: [{ path: "reply.button_payload", value: "YES", next: "wait_1" }],
      else: "end",
    });
  });

  it("rebuilds the conditions, the else and every handle target", () => {
    const applied = branchApply(node, {
      conditions: [
        { path: "reply.button_payload", value: "YES", next: "send_2" },
        { path: "contact.country", value: "PL", next: "" },
      ],
      else: "end",
    });
    expect(applied.node).toEqual({
      ...node,
      conditions: [
        { if: { "reply.button_payload": "YES" }, next: "send_2" },
        { if: { "contact.country": "PL" }, next: "" },
      ],
    });
    expect(applied.targets).toEqual({ "cond-0": "send_2", "cond-1": "", else: "end" });
  });
});

describe("other nodes", () => {
  it("map wait_for_reply ports and update_contact pairs", () => {
    const reply = waitForReplyApply(
      { id: "w", type: "wait_for_reply", timeout: "PT24H" },
      { timeout: { amount: "2", unit: "days" }, onReply: "branch_1", onTimeout: "end" },
    );
    expect(reply).toEqual({
      node: { id: "w", type: "wait_for_reply", timeout: "P2D" },
      targets: { replied: "branch_1", timeout: "end" },
    });
    const update = updateContactApply(
      { id: "u", type: "update_contact", set: {} },
      { set: [{ key: "attributes.interested", value: "yes" }], next: "end" },
    );
    expect(update.node).toEqual({
      id: "u",
      type: "update_contact",
      set: { "attributes.interested": "yes" },
    });
  });
});
