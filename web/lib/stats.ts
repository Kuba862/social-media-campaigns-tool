/** Pure aggregations behind the home page charts. Rows come from the API; nothing here fetches. */
import type { JourneyRow } from "./journeys";
import type { MessageRow } from "./messages";
import type { RunRow } from "./runs";
import type { SyncRunRow } from "./sync";
import type { TemplateRow } from "./templates";

export type Count = { label: string; value: number };
export type DayPoint = { day: string; label: string; value: number };
export type SyncPoint = { label: string; inserted: number; updated: number; status: string };

const DAY_MS = 86_400_000;

/** Counts per key in a fixed order; keys outside the order follow, alphabetically. */
export function countBy<T>(rows: T[], key: (row: T) => string, order: string[] = []): Count[] {
  const counts = new Map<string, number>();
  for (const row of rows) counts.set(key(row), (counts.get(key(row)) ?? 0) + 1);
  const known = order.filter((label) => counts.has(label));
  const rest = [...counts.keys()].filter((label) => !order.includes(label)).sort();
  return [...known, ...rest].map((label) => ({ label, value: counts.get(label) ?? 0 }));
}

/** Timestamps bucketed per UTC day over the last `days` days ending today; empty days stay 0. */
export function perDay(stamps: string[], days: number, today = new Date()): DayPoint[] {
  const end = Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate());
  const points: DayPoint[] = [];
  for (let i = days - 1; i >= 0; i -= 1) {
    const day = new Date(end - i * DAY_MS).toISOString().slice(0, 10);
    points.push({ day, label: day.slice(5), value: 0 });
  }
  const index = new Map(points.map((point, i) => [point.day, i]));
  for (const stamp of stamps) {
    const at = index.get(stamp.slice(0, 10));
    const point = at === undefined ? undefined : points[at];
    if (point) point.value += 1;
  }
  return points;
}

export const MESSAGE_STATUSES = ["pending", "sent", "delivered", "read", "failed", "skipped"];
export const RUN_STATUSES = [
  "queued",
  "running",
  "completed",
  "failed",
  "cancelled",
  "opted_out",
  "skipped_no_consent",
];
export const TEMPLATE_STATUSES = ["DRAFT", "PENDING", "APPROVED", "REJECTED"];

export function messageStats(rows: MessageRow[], today = new Date()) {
  return {
    total: rows.length,
    byStatus: countBy(rows, (row) => row.status, MESSAGE_STATUSES),
    perDay: perDay(
      rows.map((row) => row.created_at),
      14,
      today,
    ),
  };
}

export function journeyStats(journeys: JourneyRow[], runs: RunRow[]) {
  return {
    total: journeys.length,
    active: journeys.filter((journey) => journey.status === "active").length,
    runs: runs.length,
    byStatus: countBy(runs, (run) => run.status, RUN_STATUSES),
  };
}

export function templateStats(rows: TemplateRow[]) {
  return {
    total: rows.length,
    approved: rows.filter((row) => row.status === "APPROVED").length,
    byStatus: countBy(rows, (row) => row.status, TEMPLATE_STATUSES),
  };
}

/** The last `last` sync runs in time order with what they wrote, plus totals over all runs. */
export function syncStats(rows: SyncRunRow[], last = 10) {
  const sorted = [...rows].sort((a, b) => a.started_at.localeCompare(b.started_at));
  const toPoint = (run: SyncRunRow): SyncPoint => ({
    label: run.started_at.slice(5, 16).replace("T", " "),
    inserted: run.stats?.inserted ?? 0,
    updated: run.stats?.updated ?? 0,
    status: run.status,
  });
  const all = sorted.map(toPoint);
  return {
    runs: rows.length,
    inserted: all.reduce((sum, point) => sum + point.inserted, 0),
    updated: all.reduce((sum, point) => sum + point.updated, 0),
    lastStatus: all.at(-1)?.status ?? null,
    points: all.slice(-last),
  };
}
