export type VersionSummary = {
  id: string;
  version: number;
  published_at: string | null;
};

export type JourneyRow = {
  id: string;
  name: string;
  status: "draft" | "active" | "archived";
  created_at: string;
  journey_versions?: VersionSummary[]; // embedded by GET /journeys
};

export type JourneyVersionRow = VersionSummary & {
  definition: { nodes?: unknown };
  layout: Record<string, { x: number; y: number }>;
};

export type JourneyDetail = Omit<JourneyRow, "journey_versions"> & {
  versions: JourneyVersionRow[];
};

/** The create form as the API body; the API rejects an empty name too, this only trims. */
export function journeyFromForm(form: FormData): { name: string } {
  return { name: String(form.get("name") ?? "").trim() };
}

/** One cell for the list: "v2 published, draft v3", "draft v1" or "no versions". */
export function describeVersions(versions: VersionSummary[] = []): string {
  const published = versions.filter((v) => v.published_at !== null).map((v) => v.version);
  const draft = versions.find((v) => v.published_at === null);
  const parts = [
    published.length > 0 ? `v${Math.max(...published)} published` : null,
    draft ? `draft v${draft.version}` : null,
  ].filter((part): part is string => part !== null);
  return parts.length > 0 ? parts.join(", ") : "no versions";
}

export function nodeCount(version: JourneyVersionRow): number {
  return Array.isArray(version.definition.nodes) ? version.definition.nodes.length : 0;
}
