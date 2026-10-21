import { describe, expect, it } from "vitest";
import { connectorFromForm, describeSchedule, statsSummary } from "./sync";

function form(fields: Record<string, string>): FormData {
  const data = new FormData();
  for (const [key, value] of Object.entries(fields)) data.append(key, value);
  return data;
}

describe("connectorFromForm", () => {
  it("parses the config as a JSON object and reads the checkbox", () => {
    const spec = connectorFromForm(
      form({ schedule_cron: " 0 * * * * ", enabled: "on", config: '{"table": "legacy.contacts"}' }),
    );
    expect(spec).toEqual({
      schedule_cron: "0 * * * *",
      enabled: true,
      config: { table: "legacy.contacts" },
    });
    expect(connectorFromForm(form({ schedule_cron: "0 * * * *" })).config).toEqual({});
  });

  it("rejects text that is not a JSON object", () => {
    expect(() => connectorFromForm(form({ schedule_cron: "0 * * * *", config: "{" }))).toThrow(
      "valid JSON",
    );
    expect(() => connectorFromForm(form({ schedule_cron: "0 * * * *", config: "[1]" }))).toThrow(
      "JSON object",
    );
  });
});

describe("summaries", () => {
  it("lists only the non-zero counters", () => {
    expect(statsSummary({ extracted: 4, inserted: 0, invalid: 1 })).toBe("extracted 4, invalid 1");
    expect(statsSummary({})).toBe("-");
    expect(statsSummary(null)).toBe("-");
  });

  it("describes the live schedule", () => {
    expect(describeSchedule(null)).toBe("not scheduled");
    expect(
      describeSchedule({ paused: false, next_run_at: "2026-10-22T00:00:00+00:00", runs: 2 }),
    ).toBe("next 2026-10-22 00:00");
    expect(describeSchedule({ paused: true, next_run_at: null, runs: 0 })).toBe(
      "paused, no next run",
    );
  });
});
