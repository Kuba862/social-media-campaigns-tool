import Link from "next/link";
import { notFound } from "next/navigation";
import { ApiError, apiFetch } from "@/lib/api";
import {
  EMPTY_DEFINITION,
  EMPTY_LAYOUT,
  type Definition,
  type Layout,
} from "@/lib/journey-definition";
import type { JourneyDetail } from "@/lib/journeys";
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

async function loadJourney(
  id: string,
): Promise<{ journey: JourneyDetail | null; problem: string | null }> {
  try {
    return { journey: await apiFetch<JourneyDetail>(`/journeys/${id}`), problem: null };
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
    const problem = error instanceof ApiError ? error.message : "API is not reachable";
    return { journey: null, problem };
  }
}

export default async function EditJourneyPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const { journey, problem } = await loadJourney(id);
  const start = journey ? startingPoint(journey) : null;
  return (
    <main>
      <p>
        <Link href="/">Home</Link> | <Link href="/journeys">Journeys</Link>
        {journey && (
          <>
            {" "}
            | <Link href={`/journeys/${id}`}>{journey.name}</Link>
          </>
        )}
      </p>
      <h1>Edit: {journey?.name ?? "Journey"}</h1>
      {problem && <p role="alert">{problem}</p>}
      {start && (
        <>
          <p>Editing {start.label}. Save creates or overwrites the draft; publish comes later.</p>
          <Editor journeyId={id} definition={start.definition} layout={start.layout} />
        </>
      )}
    </main>
  );
}
