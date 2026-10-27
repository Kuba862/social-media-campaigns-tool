import { Nav } from "@/components/nav";
import { ApiError, apiFetch } from "@/lib/api";
import type { MessageRow } from "@/lib/messages";
import { MessageRows } from "./message-rows";

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
            <p className="lede">
              Every message the system sent, with the statuses Meta reported. Click a row for
              Meta&apos;s raw JSON.
            </p>
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
            <MessageRows rows={rows} />
          </table>
          {rows.length === 0 && <p className="empty">No messages yet.</p>}
        </div>
      </main>
    </>
  );
}
