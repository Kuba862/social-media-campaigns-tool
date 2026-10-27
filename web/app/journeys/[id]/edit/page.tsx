import Link from "next/link";
import { notFound } from "next/navigation";
import { Nav } from "@/components/nav";
import { ApiError, apiFetch } from "@/lib/api";
import {
  EMPTY_DEFINITION,
  EMPTY_LAYOUT,
  type Definition,
  type Layout,
} from "@/lib/journey-definition";
import type { JourneyDetail } from "@/lib/journeys";
import { placeholderCount, type ServiceOption, type TemplateOption } from "@/lib/node-forms";
import { isService, type TemplateRow } from "@/lib/templates";
import { Editor } from "./editor";

/** The draft when there is one, else a copy of the latest published version, else start and end. */
function startingPoint(journey: JourneyDetail): {
  definition: Definition;
  layout: Layout;
  label: string;
} {
  const draft = journey.versions.find((version) => version.published_at === null);
  const latest = [...journey.versions].reverse().find((version) => version.published_at !== null);
  const version = draft ?? latest;
  if (!version)
    return { definition: EMPTY_DEFINITION, layout: EMPTY_LAYOUT, label: "a new journey" };
  return {
    definition: version.definition as Definition,
    layout: version.layout,
    label: draft ? `draft v${version.version}` : `a copy of published v${version.version}`,
  };
}

/**
 * Approved templates only: a send node may not pick anything else. Rows made outside the panel
 * (webhook, psql) can carry `[]` or Meta's component list instead of our object, so the body is
 * read defensively.
 */
function templateOptions(rows: TemplateRow[]): TemplateOption[] {
  return rows
    .filter((row) => row.status === "APPROVED" && !isService(row))
    .map((row) => {
      const components = row.components && !Array.isArray(row.components) ? row.components : null;
      const body = typeof components?.body === "string" ? components.body : "";
      const named = Array.isArray(components?.variables) ? components.variables : null;
      const count = named ? named.length : placeholderCount(body);
      return {
        id: row.id,
        name: row.name,
        language: row.language,
        placeholders: count,
        variables: named ?? Array.from({ length: count }, (_, i) => String(i + 1)),
      };
    });
}

/** Saved service messages a send_text node may send. */
function serviceOptions(rows: TemplateRow[]): ServiceOption[] {
  return rows
    .filter((row) => isService(row))
    .map((row) => ({ id: row.id, name: row.name, language: row.language }));
}

async function loadJourney(id: string): Promise<{
  journey: JourneyDetail | null;
  templates: TemplateOption[];
  services: ServiceOption[];
  problem: string | null;
}> {
  try {
    const [journey, rows] = await Promise.all([
      apiFetch<JourneyDetail>(`/journeys/${id}`),
      apiFetch<TemplateRow[]>("/templates"),
    ]);
    const options = { templates: templateOptions(rows), services: serviceOptions(rows) };
    return { journey, ...options, problem: null };
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
    const problem = error instanceof ApiError ? error.message : "API is not reachable";
    return { journey: null, templates: [], services: [], problem };
  }
}

export default async function EditJourneyPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const { journey, templates, services, problem } = await loadJourney(id);
  const start = journey ? startingPoint(journey) : null;
  return (
    <>
      <Nav current="/journeys" />
      <main>
        <p className="crumbs">
          <Link href="/journeys">Journeys</Link> /{" "}
          {journey ? <Link href={`/journeys/${id}`}>{journey.name}</Link> : "Journey"} / Edit
        </p>
        <div className="page-head">
          <h1>Edit: {journey?.name ?? "Journey"}</h1>
        </div>
        {problem && <p role="alert">{problem}</p>}
        {start && (
          <>
            <p>
              Editing {start.label}. Save draft keeps your work; Publish checks it and makes it the
              next version.
            </p>
            <Editor
              journeyId={id}
              definition={start.definition}
              layout={start.layout}
              templates={templates}
              services={services}
            />
          </>
        )}
      </main>
    </>
  );
}
