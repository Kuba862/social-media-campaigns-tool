import { z } from "zod";
import type { IfClosed, NodeDef, NodeType } from "./journey-definition";
import { conditionHandle, ELSE, NEXT } from "./journey-graph";

/** Handle -> target node id; "" means not connected. */
export type Targets = Record<string, string>;
export type Applied = { node: NodeDef; targets: Targets };
type Of<T extends NodeType> = Extract<NodeDef, { type: T }>;

export type TemplateOption = { id: string; name: string; language: string; placeholders: number };

/** Highest {{n}} in a template body: how many variables a send node has to map. */
export function placeholderCount(body: string): number {
  let max = 0;
  for (const match of body.matchAll(/\{\{(\d+)\}\}/g)) max = Math.max(max, Number(match[1]));
  return max;
}

export const UNITS = ["minutes", "hours", "days"] as const;
export type Unit = (typeof UNITS)[number];
export type Duration = { amount: string; unit: Unit };
const SECONDS: Record<Unit, number> = { minutes: 60, hours: 3600, days: 86400 };

/** ISO 8601 duration as the engine wants it: P2D, PT3H, PT45M. */
export function toIso({ amount, unit }: Duration): string {
  const n = Number(amount);
  return unit === "days" ? `P${n}D` : unit === "hours" ? `PT${n}H` : `PT${n}M`;
}

/** The largest unit that divides the duration; anything odd (PT1H30M) shows as minutes. */
export function fromIso(iso: string): Duration {
  const m = /^P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?$/.exec(iso);
  if (!m) return { amount: "1", unit: "hours" };
  const total =
    Number(m[1] ?? 0) * 86400 +
    Number(m[2] ?? 0) * 3600 +
    Number(m[3] ?? 0) * 60 +
    Number(m[4] ?? 0);
  for (const unit of ["days", "hours", "minutes"] as const) {
    if (total > 0 && total % SECONDS[unit] === 0) {
      return { amount: String(total / SECONDS[unit]), unit };
    }
  }
  return { amount: String(Math.max(1, Math.ceil(total / 60))), unit: "minutes" };
}

const target = z.string();
const duration = z.object({
  amount: z.string().regex(/^[1-9]\d*$/, "a whole number above 0"),
  unit: z.enum(UNITS),
});
const required = z.string().min(1, "required");

export const startSchema = z.object({ next: target });
export type StartValues = z.infer<typeof startSchema>;
export const startDefaults = (targets: Targets): StartValues => ({ next: targets[NEXT] ?? "" });
export const startApply = (node: Of<"start">, v: StartValues): Applied => ({
  node,
  targets: { [NEXT]: v.next },
});

export const sendTemplateSchema = z.object({
  template_id: z.string().min(1, "choose a template"),
  variables: z.array(z.object({ path: required })),
  next: target,
});
export type SendTemplateValues = z.infer<typeof sendTemplateSchema>;
export function variableRows(
  count: number,
  current: { path: string }[] | Record<string, string>,
): { path: string }[] {
  const paths = Array.isArray(current) ? current.map((row) => row.path) : [];
  if (!Array.isArray(current))
    for (let i = 1; i <= count; i += 1) paths.push(current[String(i)] ?? "");
  return Array.from({ length: count }, (_, i) => ({ path: paths[i] ?? "" }));
}
export function sendTemplateDefaults(
  node: Of<"send_template">,
  targets: Targets,
  templates: TemplateOption[],
): SendTemplateValues {
  const known = templates.find((template) => template.id === node.template_id);
  const count = known?.placeholders ?? Object.keys(node.variables).length;
  return {
    template_id: node.template_id,
    variables: variableRows(count, node.variables),
    next: targets[NEXT] ?? "",
  };
}
export const sendTemplateApply = (node: Of<"send_template">, v: SendTemplateValues): Applied => ({
  node: {
    ...node,
    template_id: v.template_id,
    variables: Object.fromEntries(v.variables.map((row, i) => [String(i + 1), row.path])),
  },
  targets: { [NEXT]: v.next },
});

export const IF_CLOSED: IfClosed[] = ["skip", "fail"];
export const sendTextSchema = z.object({
  text: z.string().trim().min(1, "write the text"),
  if_closed: z.enum(["skip", "fail"]),
  next: target,
});
export type SendTextValues = z.infer<typeof sendTextSchema>;
export const sendTextDefaults = (node: Of<"send_text">, targets: Targets): SendTextValues => ({
  text: node.text,
  if_closed: node.if_closed,
  next: targets[NEXT] ?? "",
});
export const sendTextApply = (node: Of<"send_text">, v: SendTextValues): Applied => ({
  node: { ...node, text: v.text, if_closed: v.if_closed },
  targets: { [NEXT]: v.next },
});

export const waitSchema = z.object({ duration, next: target });
export type WaitValues = z.infer<typeof waitSchema>;
export const waitDefaults = (node: Of<"wait">, targets: Targets): WaitValues => ({
  duration: fromIso(node.duration),
  next: targets[NEXT] ?? "",
});
export const waitApply = (node: Of<"wait">, v: WaitValues): Applied => ({
  node: { ...node, duration: toIso(v.duration) },
  targets: { [NEXT]: v.next },
});

export const waitForReplySchema = z.object({
  timeout: duration,
  onReply: target,
  onTimeout: target,
});
export type WaitForReplyValues = z.infer<typeof waitForReplySchema>;
export const waitForReplyDefaults = (
  node: Of<"wait_for_reply">,
  targets: Targets,
): WaitForReplyValues => ({
  timeout: fromIso(node.timeout),
  onReply: targets.replied ?? "",
  onTimeout: targets.timeout ?? "",
});
export const waitForReplyApply = (node: Of<"wait_for_reply">, v: WaitForReplyValues): Applied => ({
  node: { ...node, timeout: toIso(v.timeout) },
  targets: { replied: v.onReply, timeout: v.onTimeout },
});

export const branchSchema = z.object({
  conditions: z.array(z.object({ path: required, value: z.string(), next: target })),
  else: target,
});
export type BranchValues = z.infer<typeof branchSchema>;
/** One (path, value) pair per condition; a condition with several keys keeps only the first. */
export const branchDefaults = (node: Of<"branch">, targets: Targets): BranchValues => ({
  conditions: node.conditions.map((condition, i) => {
    const [path = "", value = ""] = Object.entries(condition.if)[0] ?? [];
    return { path, value, next: targets[conditionHandle(i)] ?? condition.next };
  }),
  else: targets[ELSE] ?? node.else,
});
export const branchApply = (node: Of<"branch">, v: BranchValues): Applied => ({
  node: {
    ...node,
    conditions: v.conditions.map((row) => ({ if: { [row.path]: row.value }, next: row.next })),
    else: v.else,
  },
  targets: {
    ...Object.fromEntries(v.conditions.map((row, i) => [conditionHandle(i), row.next])),
    [ELSE]: v.else,
  },
});

export const updateContactSchema = z.object({
  set: z.array(z.object({ key: required, value: z.string() })),
  next: target,
});
export type UpdateContactValues = z.infer<typeof updateContactSchema>;
export const updateContactDefaults = (
  node: Of<"update_contact">,
  targets: Targets,
): UpdateContactValues => ({
  set: Object.entries(node.set).map(([key, value]) => ({ key, value: String(value ?? "") })),
  next: targets[NEXT] ?? "",
});
export const updateContactApply = (
  node: Of<"update_contact">,
  v: UpdateContactValues,
): Applied => ({
  node: { ...node, set: Object.fromEntries(v.set.map((row) => [row.key, row.value])) },
  targets: { [NEXT]: v.next },
});
