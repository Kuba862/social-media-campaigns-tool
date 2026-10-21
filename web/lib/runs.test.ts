import { describe, expect, it } from "vitest";
import { formatTime, phonesFromForm, startSummary } from "./runs";

describe("phonesFromForm", () => {
  it("splits on commas, spaces and newlines and drops duplicates", () => {
    const form = new FormData();
    form.append("phones", "+48600000001, +48600000002\n+48600000001 ;+48600000003");
    expect(phonesFromForm(form)).toEqual(["+48600000001", "+48600000002", "+48600000003"]);
  });
});

describe("startSummary", () => {
  it("mentions only what happened", () => {
    expect(startSummary({ started: ["r1", "r2"], skipped: [], unknown: [] })).toBe("started 2");
    expect(startSummary({ started: [], skipped: ["c1"], unknown: ["+48700000000"] })).toBe(
      "started 0, skipped 1 (already running), unknown numbers: +48700000000",
    );
  });
});

describe("formatTime", () => {
  it("shows minutes and a dash for nothing", () => {
    expect(formatTime("2026-10-21T14:05:33.123+00:00")).toBe("2026-10-21 14:05");
    expect(formatTime(null)).toBe("-");
  });
});
