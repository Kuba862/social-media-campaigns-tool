/**
 * The creator's forms: Meta's rules for templates, mirrored from backend meta_client/models.py
 * so the user sees them while typing; the API stays authoritative.
 */
import { z } from "zod";
import type { ServiceMessageSpec, TemplateSpec } from "./templates";

const PLACEHOLDER = /\{\{\s*([A-Za-z0-9_]+)\s*\}\}/g;
const VARIABLE_NAME = /^[A-Za-z][A-Za-z0-9_]*$/;
export const NAME_PATTERN = /^[a-z0-9_]{1,512}$/;

export const LANGUAGES: { code: string; label: string }[] = [
  { code: "pl", label: "Polish" },
  { code: "en", label: "English" },
  { code: "en_US", label: "English (US)" },
  { code: "en_GB", label: "English (UK)" },
  { code: "de", label: "German" },
  { code: "es", label: "Spanish" },
  { code: "fr", label: "French" },
  { code: "it", label: "Italian" },
  { code: "pt_BR", label: "Portuguese (Brazil)" },
  { code: "pt_PT", label: "Portuguese (Portugal)" },
  { code: "nl", label: "Dutch" },
  { code: "cs", label: "Czech" },
  { code: "sk", label: "Slovak" },
  { code: "uk", label: "Ukrainian" },
  { code: "hu", label: "Hungarian" },
  { code: "ro", label: "Romanian" },
];

/** Variable names in order of first appearance, each once: {{first_name}} or {{1}}. */
export function variablesOf(body: string): string[] {
  const seen: string[] = [];
  for (const match of body.matchAll(PLACEHOLDER)) {
    const name = match[1] ?? "";
    if (!seen.includes(name)) seen.push(name);
  }
  return seen;
}

/** Meta's placement rules for variables, in the same words as the API. */
export function bodyProblems(body: string): string[] {
  const problems: string[] = [];
  const names = variablesOf(body);
  const numbers = names.filter((name) => /^\d+$/.test(name));
  if (numbers.length > 0 && numbers.length !== names.length) {
    problems.push("variables must be all named ({{first_name}}) or all positional ({{1}})");
  }
  if (numbers.length > 0 && numbers.some((name, index) => Number(name) !== index + 1)) {
    problems.push("placeholders must be numbered 1..n without gaps");
  }
  const bad = names.filter((name) => !/^\d+$/.test(name) && !VARIABLE_NAME.test(name));
  if (bad.length > 0) problems.push(`variable names must start with a letter: ${bad.join(", ")}`);
  const stripped = body.trim();
  if (stripped.startsWith("{{")) problems.push("the body must not start with a variable");
  if (stripped.endsWith("}}")) problems.push("the body must not end with a variable");
  if (/\}\}\s*\{\{/.test(body)) problems.push("two variables must be separated by text");
  return problems;
}

const https = (message: string) =>
  z
    .string()
    .trim()
    .refine((value) => /^https:\/\/\S+$/.test(value), message);

export const BUTTON_TYPES = ["quick_reply", "url"] as const;
export const HEADER_KINDS = ["none", "text", "image"] as const;

export const templateSchema = z
  .object({
    language: z.string().min(1),
    category: z.enum(["UTILITY", "MARKETING"]),
    header_kind: z.enum(HEADER_KINDS),
    header: z.string().max(60, "up to 60 characters"),
    header_image_url: z.string(),
    body: z.string().trim().min(1, "write the message").max(1024, "up to 1024 characters"),
    footer: z.string().max(60, "up to 60 characters"),
    buttons: z
      .array(
        z.object({
          type: z.enum(BUTTON_TYPES),
          text: z.string().trim().min(1, "required").max(25, "up to 25 characters"),
          url: z.string().trim(),
        }),
      )
      .max(5, "at most 5 buttons"),
    example_values: z.array(z.object({ value: z.string().trim().min(1, "required") })),
  })
  .superRefine((values, ctx) => {
    for (const problem of bodyProblems(values.body)) {
      ctx.addIssue({ code: "custom", path: ["body"], message: problem });
    }
    if (values.header_kind === "text" && values.header.trim() === "") {
      ctx.addIssue({ code: "custom", path: ["header"], message: "write the header" });
    }
    if (values.header_kind === "text" && PLACEHOLDER.test(values.header)) {
      ctx.addIssue({ code: "custom", path: ["header"], message: "no variables in the header" });
    }
    if (values.header_kind === "image" && !https("x").safeParse(values.header_image_url).success) {
      ctx.addIssue({
        code: "custom",
        path: ["header_image_url"],
        message: "an https address of a JPEG or PNG",
      });
    }
    values.buttons.forEach((button, index) => {
      if (button.type === "url" && !https("x").safeParse(button.url).success) {
        ctx.addIssue({
          code: "custom",
          path: ["buttons", index, "url"],
          message: "an https address",
        });
      }
    });
    if (values.buttons.filter((button) => button.type === "url").length > 2) {
      ctx.addIssue({ code: "custom", path: ["buttons"], message: "at most 2 URL buttons" });
    }
  });
export type TemplateValues = z.infer<typeof templateSchema>;

export const serviceSchema = z
  .object({
    language: z.string().min(1),
    image_url: z.string().trim(),
    body: z.string().trim().min(1, "write the message").max(4096, "up to 4096 characters"),
  })
  .superRefine((values, ctx) => {
    if (PLACEHOLDER.test(values.body)) {
      ctx.addIssue({
        code: "custom",
        path: ["body"],
        message: "a service message has no variables",
      });
    }
    if (values.image_url !== "" && !https("x").safeParse(values.image_url).success) {
      ctx.addIssue({
        code: "custom",
        path: ["image_url"],
        message: "an https address of an image",
      });
    }
    if (values.image_url !== "" && values.body.length > 1024) {
      ctx.addIssue({
        code: "custom",
        path: ["body"],
        message: "a caption has at most 1024 characters",
      });
    }
  });
export type ServiceValues = z.infer<typeof serviceSchema>;

/** The name step: Meta's pattern, and unique among the names already in the list. */
export function nameProblem(name: string, taken: Set<string>): string | null {
  if (!NAME_PATTERN.test(name)) return "lowercase letters, digits and underscores only";
  if (taken.has(name)) return "this name is already taken";
  return null;
}

export const templateDefaults: TemplateValues = {
  language: "pl",
  category: "UTILITY",
  header_kind: "none",
  header: "",
  header_image_url: "",
  body: "",
  footer: "",
  buttons: [],
  example_values: [],
};

export const serviceDefaults: ServiceValues = { language: "pl", image_url: "", body: "" };

/** Example inputs follow the variables typed in the body, keeping values already entered. */
export function exampleRows(body: string, current: { value: string }[]): { value: string }[] {
  return variablesOf(body).map((_, index) => ({ value: current[index]?.value ?? "" }));
}

export function toTemplateSpec(name: string, v: TemplateValues): TemplateSpec {
  return {
    name,
    language: v.language,
    category: v.category,
    header: v.header_kind === "text" ? v.header.trim() : null,
    header_image_url: v.header_kind === "image" ? v.header_image_url.trim() : null,
    body: v.body.trim(),
    footer: v.footer.trim() === "" ? null : v.footer.trim(),
    buttons: v.buttons.map((button) =>
      button.type === "url"
        ? { type: "url", text: button.text.trim(), url: button.url.trim() }
        : { type: "quick_reply", text: button.text.trim() },
    ),
    example_values: v.example_values.map((row) => row.value.trim()),
  };
}

export function toServiceSpec(name: string, v: ServiceValues): ServiceMessageSpec {
  return {
    name,
    language: v.language,
    body: v.body.trim(),
    image_url: v.image_url.trim() === "" ? null : v.image_url.trim(),
  };
}

export type PreviewSegment = { text: string; variable?: string };

/**
 * The body split for the preview: plain text, and each variable replaced by its example value
 * (or left as the placeholder when no example is typed yet) so the reader sees which part moves.
 */
export function previewSegments(body: string, examples: Record<string, string>): PreviewSegment[] {
  const segments: PreviewSegment[] = [];
  let last = 0;
  for (const match of body.matchAll(PLACEHOLDER)) {
    const start = match.index ?? 0;
    if (start > last) segments.push({ text: body.slice(last, start) });
    const name = match[1] ?? "";
    const example = examples[name]?.trim();
    segments.push({ text: example ? example : match[0], variable: name });
    last = start + match[0].length;
  }
  if (last < body.length) segments.push({ text: body.slice(last) });
  return segments;
}

/** Example values keyed by variable name, from the form's rows in variable order. */
export function examplesByName(body: string, rows: { value: string }[]): Record<string, string> {
  const names = variablesOf(body);
  return Object.fromEntries(names.map((name, index) => [name, rows[index]?.value ?? ""]));
}
