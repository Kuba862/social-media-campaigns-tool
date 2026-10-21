import Link from "next/link";
import { Nav } from "@/components/nav";
import { Status } from "@/components/status";
import { ApiError, apiFetch } from "@/lib/api";
import { describeVersions, type JourneyRow } from "@/lib/journeys";
import { createJourney } from "./actions";

async function loadJourneys(): Promise<{ rows: JourneyRow[]; problem: string | null }> {
  try {
    return { rows: await apiFetch<JourneyRow[]>("/journeys"), problem: null };
  } catch (error) {
    const problem = error instanceof ApiError ? error.message : "API is not reachable";
    return { rows: [], problem };
  }
}

export default async function JourneysPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string }>;
}) {
  const { error } = await searchParams;
  const { rows, problem } = await loadJourneys();
  const message = error ?? problem;
  return (
    <>
      <Nav current="/journeys" />
      <main>
        <div className="page-head">
          <div>
            <h1>Journeys</h1>
            <p className="lede">
              A journey is a published graph of messages, waits and branches; runs follow its latest
              version.
            </p>
          </div>
        </div>
        {message && <p role="alert">{message}</p>}
        <div className="card">
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Status</th>
                <th>Versions</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td>
                    <Link href={`/journeys/${row.id}`}>{row.name}</Link>
                  </td>
                  <td>
                    <Status value={row.status} />
                  </td>
                  <td>{describeVersions(row.journey_versions)}</td>
                  <td>{row.created_at.slice(0, 19).replace("T", " ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {rows.length === 0 && <p className="empty">No journeys yet.</p>}
        </div>

        <h2>New journey</h2>
        <form action={createJourney}>
          <label>
            Name
            <input name="name" required maxLength={200} />
          </label>
          <button type="submit">Create</button>
        </form>
      </main>
    </>
  );
}
