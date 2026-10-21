import Link from "next/link";
import { ApiError, apiFetch } from "@/lib/api";
import type { TemplateRow } from "@/lib/templates";
import { createTemplate, sendTest, submitTemplate, syncTemplate } from "./actions";

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
    <main>
      <p>
        <Link href="/">Home</Link> | <Link href="/messages">Messages</Link>
      </p>
      <h1>Templates</h1>
      {message && <p role="alert">{message}</p>}
      <table>
        <thead>
          <tr>
            <th>Name</th>
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
              <td>{row.language}</td>
              <td>{row.category}</td>
              <td>
                {row.status}
                {row.rejection_reason && ` (${row.rejection_reason})`}
              </td>
              <td>{row.meta_template_id ?? "-"}</td>
              <td>
                <form action={row.status === "DRAFT" ? submitTemplate : syncTemplate}>
                  <input type="hidden" name="id" value={row.id} />
                  <button type="submit">{row.status === "DRAFT" ? "Submit" : "Sync"}</button>
                </form>
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

      <h2>New draft</h2>
      <form action={createTemplate}>
        <label>
          Name
          <input name="name" required pattern="[a-z0-9_]+" />
        </label>
        <label>
          Language
          <input name="language" required defaultValue="pl" />
        </label>
        <label>
          Category
          <select name="category" defaultValue="MARKETING">
            <option>MARKETING</option>
            <option>UTILITY</option>
            <option>AUTHENTICATION</option>
          </select>
        </label>
        <label>
          Body
          <textarea name="body" required rows={4} />
        </label>
        <label>
          Example values, one per variable, comma-separated
          <input name="example_values" />
        </label>
        <label>
          Quick replies, comma-separated, up to three
          <input name="quick_replies" />
        </label>
        <button type="submit">Save draft</button>
      </form>
    </main>
  );
}
