import { describe, expect, it } from "vitest";
import type { MessageRow } from "./messages";
import type { SyncRunRow } from "./sync";
import { countBy, messageStats, perDay, syncStats, templateStats } from "./stats";
import type { TemplateRow } from "./templates";

const TODAY = new Date("2026-10-27T15:00:00Z");

describe("countBy", () => {
  it("keeps the given order first and sorts unknown keys after it", () => {
    const rows = [{ s: "b" }, { s: "zz" }, { s: "a" }, { s: "b" }, { s: "aa" }];
    expect(countBy(rows, (row) => row.s, ["a", "b", "c"])).toEqual([
      { label: "a", value: 1 },
      { label: "b", value: 2 },
      { label: "aa", value: 1 },
      { label: "zz", value: 1 },
    ]);
  });
});

describe("perDay", () => {
  it("buckets by UTC day over the window and keeps empty days", () => {
    const stamps = [
      "2026-10-27T00:10:00+00:00",
      "2026-10-26T23:59:00+00:00",
      "2026-10-01T10:00:00+00:00",
    ];
    const points = perDay(stamps, 3, TODAY);
    expect(points.map((p) => p.day)).toEqual(["2026-10-25", "2026-10-26", "2026-10-27"]);
    expect(points.map((p) => p.value)).toEqual([0, 1, 1]);
    expect(points[0]?.label).toBe("10-25");
  });
});

describe("messageStats", () => {
  it("counts statuses in delivery order and messages per day", () => {
    const message = (status: string, created_at: string): MessageRow =>
      ({ id: created_at, status, created_at }) as MessageRow;
    const rows = [
      message("read", "2026-10-27T10:00:00+00:00"),
      message("sent", "2026-10-27T11:00:00+00:00"),
      message("failed", "2026-10-20T11:00:00+00:00"),
    ];
    const stats = messageStats(rows, TODAY);
    expect(stats.total).toBe(3);
    expect(stats.byStatus).toEqual([
      { label: "sent", value: 1 },
      { label: "read", value: 1 },
      { label: "failed", value: 1 },
    ]);
    expect(stats.perDay).toHaveLength(14);
    expect(stats.perDay.at(-1)?.value).toBe(2);
  });
});

describe("templateStats", () => {
  it("counts approved templates and the status breakdown", () => {
    const rows = ["APPROVED", "DRAFT", "APPROVED", "REJECTED"].map(
      (status, i) => ({ id: String(i), status }) as TemplateRow,
    );
    const stats = templateStats(rows);
    expect([stats.total, stats.approved]).toEqual([4, 2]);
    expect(stats.byStatus.map((c) => c.label)).toEqual(["DRAFT", "APPROVED", "REJECTED"]);
  });
});

describe("syncStats", () => {
  const run = (started_at: string, stats: Record<string, number>, status = "succeeded") =>
    ({ id: started_at, started_at, stats, status }) as SyncRunRow;

  it("orders runs by start time, keeps the last ten and sums over all of them", () => {
    const rows = [
      run("2026-10-27T10:00:00+00:00", { inserted: 2 }),
      run("2026-10-26T10:00:00+00:00", { inserted: 3, updated: 1 }, "failed"),
    ];
    const stats = syncStats(rows, 1);
    expect([stats.runs, stats.inserted, stats.updated]).toEqual([2, 5, 1]);
    expect(stats.lastStatus).toBe("succeeded");
    expect(stats.points).toEqual([
      { label: "10-27 10:00", inserted: 2, updated: 0, status: "succeeded" },
    ]);
  });

  it("is empty-safe", () => {
    expect(syncStats([])).toEqual({
      runs: 0,
      inserted: 0,
      updated: 0,
      lastStatus: null,
      points: [],
    });
  });
});
