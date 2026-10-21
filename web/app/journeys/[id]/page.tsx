import Link from "next/link";
import { notFound } from "next/navigation";
import { Nav } from "@/components/nav";
import { Status } from "@/components/status";
import { ApiError, apiFetch } from "@/lib/api";
import { nodeCount, type JourneyDetail } from "@/lib/journeys";

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

export default async function JourneyPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const { journey, problem } = await loadJourney(id);
  return (
    <>
      <Nav current="/journeys" />
      <main>
        <p className="crumbs">
          <Link href="/journeys">Journeys</Link> / {journey?.name ?? "Journey"}
        </p>
        <h1>{journey?.name ?? "Journey"}</h1>
        {problem && <p role="alert">{problem}</p>}
        {journey && (
          <>
            <p>
              Status: {journey.status} | <Link href={`/journeys/${journey.id}/edit`}>Edit</Link> |{" "}
              <Link href={`/journeys/${journey.id}/runs`}>Runs</Link>
            </p>
            <h2>Versions</h2>
            <div className="card">
              <table>
                <thead>
                  <tr>
                    <th>Version</th>
                    <th>State</th>
                    <th>Nodes</th>
                    <th>Published</th>
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
