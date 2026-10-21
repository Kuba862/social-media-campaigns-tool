import Link from "next/link";
import { notFound } from "next/navigation";
import { Nav } from "@/components/nav";
import { ApiError, apiFetch } from "@/lib/api";
import type { JourneyDetail } from "@/lib/journeys";
import { formatTime, type RunRow } from "@/lib/runs";
import { cancelRun, startRuns } from "./actions";

async function load(
  id: string,
): Promise<{ journey: JourneyDetail | null; runs: RunRow[]; problem: string | null }> {
  try {
    const [journey, runs] = await Promise.all([
      apiFetch<JourneyDetail>(`/journeys/${id}`),
      apiFetch<RunRow[]>(`/journeys/${id}/runs`),
    ]);
    return { journey, runs, problem: null };
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
    const problem = error instanceof ApiError ? error.message : "API is not reachable";
    return { journey: null, runs: [], problem };
  }
}

export default async function RunsPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ error?: string; notice?: string }>;
}) {
  const { id } = await params;
  const { error, notice } = await searchParams;
  const { journey, runs, problem } = await load(id);
  const message = error ?? problem;
  return (
    <>
      <Nav current="/journeys" />
      <main>
        <p className="crumbs">
          <Link href="/journeys">Journeys</Link> /{" "}
          {journey ? <Link href={`/journeys/${id}`}>{journey.name}</Link> : "Journey"} / Runs
        </p>
        <h1>Runs: {journey?.name ?? "Journey"}</h1>
        {message && <p role="alert">{message}</p>}
        {notice && <p role="status">{notice}</p>}
        <table>
          <thead>
            <tr>
              <th>Contact</th>
              <th>Status</th>
              <th>Current node</th>
              <th>Started</th>
              <th>Ended</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {runs.map((run) => (
              <tr key={run.id}>
                <td>{run.contacts?.phone_e164 ?? run.contact_id}</td>
                <td>{run.status}</td>
                <td>{run.current_node_id ?? "-"}</td>
                <td>{formatTime(run.started_at)}</td>
                <td>{formatTime(run.ended_at)}</td>
                <td>
                  {run.status === "running" && (
                    <form action={cancelRun}>
                      <input type="hidden" name="journey_id" value={id} />
                      <input type="hidden" name="run_id" value={run.id} />
                      <button type="submit" className="danger">
                        Cancel
                      </button>
                    </form>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {runs.length === 0 && <p className="empty">No runs yet.</p>}

        <h2>Start for contacts</h2>
        <p className="muted">
          One run per contact on the latest published version; a contact already running in this
          journey is skipped.
        </p>
        <form action={startRuns}>
          <input type="hidden" name="journey_id" value={id} />
          <label>
            Phone numbers (E.164, one per line or comma-separated)
            <textarea name="phones" rows={3} required placeholder="+48600000001" />
          </label>
          <button type="submit">Start</button>
        </form>
      </main>
    </>
  );
}
