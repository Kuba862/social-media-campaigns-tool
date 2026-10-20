export type TemplateComponents = {
  body: string;
  example_values: string[];
  quick_replies: string[];
};

export type TemplateRow = {
  id: string;
  name: string;
  language: string;
  category: string;
  status: string;
  meta_template_id: string | null;
  rejection_reason: string | null;
  components: TemplateComponents;
  created_at: string;
};

export type TemplateSpec = TemplateComponents & {
  name: string;
  language: string;
  category: string;
};

/** Turns the draft form into the API body. Lists are comma- or newline-separated in the form. */
export function specFromForm(form: FormData): TemplateSpec {
  const text = (key: string) => String(form.get(key) ?? "").trim();
  const list = (key: string) =>
    text(key)
      .split(/[,\n]/)
      .map((item) => item.trim())
      .filter((item) => item.length > 0);
  return {
    name: text("name"),
    language: text("language"),
    category: text("category") || "MARKETING",
    body: String(form.get("body") ?? ""),
    example_values: list("example_values"),
    quick_replies: list("quick_replies"),
  };
}
