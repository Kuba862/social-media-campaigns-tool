import { Nav } from "@/components/nav";
import { Status } from "@/components/status";
import { ApiError, apiFetch } from "@/lib/api";
import { formatTime } from "@/lib/runs";
import {
  CONNECTOR_NAMES,
  describeSchedule,
  statsSummary,
  type ConnectorRow,
  type SyncRunRow,
} from "@/lib/sync";
import { applySchedule, registerConnector, runNow } from "./actions";

async function load(): Promise<{
  connectors: ConnectorRow[];
  runs: SyncRunRow[];
  problem: string | null;
}> {
  try {
    const [connectors, runs] = await Promise.all([
      apiFetch<ConnectorRow[]>("/sync/connectors"),
      apiFetch<SyncRunRow[]>("/sync/runs"),
    ]);
    return { connectors, runs, problem: null };
  } catch (error) {
    const problem = error instanceof ApiError ? error.message : "API is not reachable";
    return { connectors: [], runs: [], problem };
  }
}

export default async function SyncPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string; notice?: string }>;
}) {
  const { error, notice } = await searchParams;
  const { connectors, runs, problem } = await load();
  const message = error ?? problem;
  return (
    <>
      <Nav current="/sync" />
      <main>
        <div className="page-head">
          <div>
            <h1>Sync</h1>
            <p className="lede">
              Connectors are code in <code>backend/sync/connectors</code>; a row here gives one a
              schedule and a config without secrets. Apply schedule pushes the row to Temporal.
            </p>
          </div>
        </div>
        {message && <p role="alert">{message}</p>}
        {notice && <p role="status">{notice}</p>}

        <h2>Connectors</h2>
        <div className="card">
          <table aria-label="Connectors">
            <thead>
              <tr>
                <th>Name</th>
                <th>Cron</th>
                <th>Enabled</th>
                <th>Schedule in Temporal</th>
                <th>Config</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {connectors.map((row) => (
                <tr key={row.id}>
                  <td>{row.name}</td>
                  <td>
                    <code>{row.schedule_cron}</code>
                  </td>
                  <td>
                    <Status value={row.enabled ? "yes" : "no"} />
                  </td>
                  <td>
                    {describeSchedule(row.schedule)}
                    {row.schedule && row.schedule.runs > 0 && ` (${row.schedule.runs} runs)`}
                  </td>
                  <td>
                    <code className="wrap">{JSON.stringify(row.config)}</code>
                  </td>
                  <td>
                    <div className="toolbar">
                      <form action={runNow}>
                        <input type="hidden" name="name" value={row.name} />
                        <button type="submit">Run now</button>
                      </form>
                      <form action={applySchedule}>
                        <input type="hidden" name="name" value={row.name} />
                        <button type="submit">Apply schedule</button>
                      </form>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {connectors.length === 0 && <p className="empty">No connectors registered.</p>}
        </div>

        <h2>Register or update a connector</h2>
        <div className="card">
          <form action={registerConnector}>
            <label>
              Connector
              <select name="name" defaultValue="fake">
                {CONNECTOR_NAMES.map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Cron (five fields)
              <input name="schedule_cron" defaultValue="0 * * * *" required />
            </label>
            <label>
              Enabled
              <input name="enabled" type="checkbox" defaultChecked />
            </label>
            <label>
              Config (JSON, no secrets)
              <textarea name="config" rows={3} defaultValue="{}" />
            </label>
            <button type="submit">Save connector</button>
          </form>
        </div>

        <h2>Runs</h2>
        <div className="card">
          <table aria-label="Runs">
            <thead>
              <tr>
                <th>Connector</th>
                <th>Status</th>
                <th>Stats</th>
                <th>Error</th>
                <th>Started</th>
                <th>Ended</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr key={run.id}>
                  <td>{run.sync_connectors?.name ?? run.connector_id}</td>
                  <td>
                    <Status value={run.status} />
                  </td>
                  <td>{statsSummary(run.stats)}</td>
                  <td>{run.error ?? ""}</td>
                  <td>{formatTime(run.started_at)}</td>
                  <td>{formatTime(run.ended_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {runs.length === 0 && <p className="empty">No runs yet.</p>}
        </div>
      </main>
    </>
  );
}
