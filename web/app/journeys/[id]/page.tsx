import Link from "next/link";
import { notFound } from "next/navigation";
import { ConfirmButton } from "@/components/confirm-button";
import { Nav } from "@/components/nav";
import { Status } from "@/components/status";
import { ApiError, apiFetch } from "@/lib/api";
import { nodeCount, type JourneyDetail } from "@/lib/journeys";
import { deleteVersion } from "./actions";

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

export default async function JourneyPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ error?: string }>;
}) {
  const { id } = await params;
  const { error } = await searchParams;
  const { journey, problem } = await loadJourney(id);
  return (
    <>
      <Nav current="/journeys" />
      <main>
        <p className="crumbs">
          <Link href="/journeys">Journeys</Link> / {journey?.name ?? "Journey"}
        </p>
        <h1>{journey?.name ?? "Journey"}</h1>
        {(error ?? problem) && <p role="alert">{error ?? problem}</p>}
        {journey && (
          <>
            <div className="page-head">
              <p className="muted">
                <Status value={journey.status} />
              </p>
              <div className="toolbar">
                <Link href={`/journeys/${journey.id}/edit`} className="button">
                  Edit
                </Link>
                <Link href={`/journeys/${journey.id}/runs`} className="button secondary">
                  Runs
                </Link>
              </div>
            </div>
            <h2>Versions</h2>
            <div className="card">
              <table>
                <thead>
                  <tr>
                    <th>Version</th>
                    <th>State</th>
                    <th>Nodes</th>
                    <th>Published</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {journey.versions.map((version) => (
                    <tr key={version.id}>
                      <td>{version.version}</td>
                      <td>
                        <Status value={version.published_at === null ? "draft" : "published"} />
                      </td>
                      <td>{nodeCount(version)}</td>
                      <td>{version.published_at?.slice(0, 19).replace("T", " ") ?? "-"}</td>
                      <td>
                        <form action={deleteVersion}>
                          <input type="hidden" name="journey_id" value={journey.id} />
                          <input type="hidden" name="version_id" value={version.id} />
                          <ConfirmButton
                            message={`Delete version ${version.version}? Versions with runs are kept by the API.`}
                            className="secondary danger"
                          >
                            Delete
                          </ConfirmButton>
                        </form>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {journey.versions.length === 0 && <p className="empty">No versions yet.</p>}
            </div>
          </>
        )}
      </main>
    </>
  );
}
