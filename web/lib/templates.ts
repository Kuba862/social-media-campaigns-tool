/** Rows and API bodies of /templates: Meta templates and saved service messages share the table. */

export type TemplateButton =
  { type: "quick_reply"; text: string } | { type: "url"; text: string; url: string };

export type TemplateComponents = {
  header?: string | null;
  header_image_url?: string | null;
  body: string;
  footer?: string | null;
  buttons?: TemplateButton[];
  example_values?: string[];
  variables?: string[];
  image_url?: string | null; // service messages
  quick_replies?: string[]; // rows written before the creator
};

export type TemplateRow = {
  id: string;
  name: string;
  language: string;
  category: string;
  kind?: "template" | "service";
  status: string;
  meta_template_id: string | null;
  rejection_reason: string | null;
  components: TemplateComponents;
  created_at: string;
};

/** POST /templates */
export type TemplateSpec = {
  name: string;
  language: string;
  category: "UTILITY" | "MARKETING";
  header: string | null;
  header_image_url: string | null;
  body: string;
  footer: string | null;
  buttons: TemplateButton[];
  example_values: string[];
};

/** POST /templates/service */
export type ServiceMessageSpec = {
  name: string;
  language: string;
  body: string;
  image_url: string | null;
};

export function isService(row: Pick<TemplateRow, "kind">): boolean {
  return row.kind === "service";
}
