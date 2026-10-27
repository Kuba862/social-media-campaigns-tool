import Link from "next/link";
import { ConfirmButton } from "@/components/confirm-button";
import { Nav } from "@/components/nav";
import { Status } from "@/components/status";
import { ApiError, apiFetch } from "@/lib/api";
import { isService, type TemplateRow } from "@/lib/templates";
import { deleteTemplate, sendTest, submitTemplate, syncTemplate } from "./actions";

async function loadTemplates(): Promise<{ rows: TemplateRow[]; problem: string | null }> {
  try {
    return { rows: await apiFetch<TemplateRow[]>("/templates"), problem: null };
  } catch (error) {
    const problem = error instanceof ApiError ? error.message : "API is not reachable";
    return { rows: [], problem };
  }
}

export default async function TemplatesPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string }>;
}) {
  const { error } = await searchParams;
  const { rows, problem } = await loadTemplates();
  const message = error ?? problem;
  return (
    <>
      <Nav current="/templates" />
      <main>
        <div className="page-head">
          <div>
            <h1>Templates</h1>
            <p className="lede">
              Meta templates wait here as drafts until you submit them; saved service messages are
              ready at once.
            </p>
          </div>
          <div className="toolbar">
            <Link href="/templates/new" className="button">
              New message
            </Link>
          </div>
        </div>
        {message && <p role="alert">{message}</p>}
        <div className="card">
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Type</th>
                <th>Language</th>
                <th>Category</th>
                <th>Status</th>
                <th>Meta id</th>
                <th>Action</th>
                <th>Test send</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td>{row.name}</td>
                  <td>{isService(row) ? "service message" : "template"}</td>
                  <td>{row.language}</td>
                  <td>{row.category}</td>
                  <td>
                    <Status value={row.status} />
                    {row.rejection_reason && <div className="muted">{row.rejection_reason}</div>}
                  </td>
                  <td>{row.meta_template_id ?? "-"}</td>
                  <td>
                    <div className="row-actions">
                      {!isService(row) && (
                        <form action={row.status === "DRAFT" ? submitTemplate : syncTemplate}>
                          <input type="hidden" name="id" value={row.id} />
                          <button type="submit">
                            {row.status === "DRAFT" ? "Submit" : "Sync"}
                          </button>
                        </form>
                      )}
                      <form action={deleteTemplate}>
                        <input type="hidden" name="id" value={row.id} />
                        <ConfirmButton
                          message={`Delete template ${row.name} (${row.language})? Meta blocks a deleted name for 30 days.`}
                          className="secondary danger"
                        >
                          Delete
                        </ConfirmButton>
                      </form>
                    </div>
                  </td>
                  <td>
                    {row.status === "APPROVED" && (
                      <form action={sendTest}>
                        <input type="hidden" name="template_id" value={row.id} />
                        <input
                          name="to_e164"
                          placeholder="+48..."
                          required
                          pattern="\+[1-9][0-9]{6,14}"
                        />
                        <input name="body_values" placeholder="values, comma-separated" />
                        <button type="submit">Send test</button>
                      </form>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </main>
    </>
  );
}
