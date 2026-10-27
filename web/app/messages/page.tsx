import { Nav } from "@/components/nav";
import { Status } from "@/components/status";
import { ApiError, apiFetch } from "@/lib/api";
import { eventLabels, messageLabel, type MessageRow } from "@/lib/messages";

async function loadMessages(): Promise<{ rows: MessageRow[]; problem: string | null }> {
  try {
    return { rows: await apiFetch<MessageRow[]>("/messages"), problem: null };
  } catch (error) {
    const problem = error instanceof ApiError ? error.message : "API is not reachable";
    return { rows: [], problem };
  }
}

export default async function MessagesPage() {
  const { rows, problem } = await loadMessages();
  return (
    <>
      <Nav current="/messages" />
      <main>
        <div className="page-head">
          <div>
            <h1>Messages</h1>
            <p className="lede">Every message the system sent, with the statuses Meta reported.</p>
          </div>
        </div>
        {problem && <p role="alert">{problem}</p>}
        <div className="card">
          <table>
            <thead>
              <tr>
                <th>Created</th>
                <th>Message</th>
                <th>To</th>
                <th>Status</th>
                <th>Events</th>
                <th>Error</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td>{row.created_at.slice(0, 19).replace("T", " ")}</td>
                  <td>{messageLabel(row)}</td>
                  <td>{row.contacts?.phone_e164 ?? "-"}</td>
                  <td>
                    <Status value={row.status} />
                  </td>
                  <td>{eventLabels(row.message_events).join(", ") || "-"}</td>
                  <td>{row.error?.message ?? ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {rows.length === 0 && <p className="empty">No messages yet.</p>}
        </div>
      </main>
    </>
  );
}
