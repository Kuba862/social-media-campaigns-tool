import Link from "next/link";
import { redirect } from "next/navigation";
import { logout } from "@/app/login/actions";
import { Bars, Columns, DataTable, Legend, StatCard } from "@/components/charts";
import { Nav } from "@/components/nav";
import { ApiError, apiFetch } from "@/lib/api";
import type { JourneyRow } from "@/lib/journeys";
import type { MessageRow } from "@/lib/messages";
import type { RunRow } from "@/lib/runs";
import { journeyStats, messageStats, syncStats, templateStats } from "@/lib/stats";
import { createClient } from "@/lib/supabase/server";
import type { SyncRunRow } from "@/lib/sync";
import type { TemplateRow } from "@/lib/templates";

type Loaded<T> = { rows: T[]; problem: string | null };

async function load<T>(path: string): Promise<Loaded<T>> {
  try {
    return { rows: await apiFetch<T[]>(path), problem: null };
  } catch (error) {
    const problem = error instanceof ApiError ? error.message : "API is not reachable";
    return { rows: [], problem };
  }
}

const SYNC_SERIES = ["inserted", "updated"];

export default async function HomePage() {
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    redirect("/login");
  }

  const [messages, journeys, runs, templates, syncRuns] = await Promise.all([
    load<MessageRow>("/messages"),
    load<JourneyRow>("/journeys"),
    load<RunRow>("/runs"),
    load<TemplateRow>("/templates"),
    load<SyncRunRow>("/sync/runs"),
  ]);
  const m = messageStats(messages.rows);
  const j = journeyStats(journeys.rows, runs.rows);
  const t = templateStats(templates.rows);
  const s = syncStats(syncRuns.rows);
  const statusLine = (counts: { label: string; value: number }[], empty: string) =>
    counts.length > 0 ? counts.map((c) => `${c.label} ${c.value}`).join(" · ") : empty;

  return (
    <>
      <Nav current="/" email={user.email} />
      <main>
        <section className="hero">
          <p className="eyebrow">Proof of concept</p>
          <h1>WhatsApp campaigns</h1>
          <p className="lede">
            Templates go to Meta for approval, journeys run on Temporal and react to replies, and
            your own connectors keep contacts and consents in sync.
          </p>
          <p className="muted">Signed in as {user.email}</p>
        </section>
        <div className="grid">
          <Link href="/templates" className="tile">
            <strong>Manage templates</strong>
            <span>Drafts, submission to Meta, status from the webhook, test sends.</span>
          </Link>
          <Link href="/journeys" className="tile">
            <strong>Build journeys</strong>
            <span>The editor, published versions, runs for a list of numbers.</span>
          </Link>
          <Link href="/messages" className="tile">
            <strong>Read the message log</strong>
            <span>Every message with its delivery statuses and errors.</span>
          </Link>
          <Link href="/sync" className="tile">
            <strong>Sync contacts</strong>
            <span>Connectors on a schedule, their runs and statistics.</span>
          </Link>
        </div>
        <section className="stats" aria-label="Campaign data">
          <StatCard
            id="messages"
            title="Messages"
            value={m.total}
            note={statusLine(m.byStatus, "nothing sent yet")}
          >
            {messages.problem ? (
              <p role="alert">{messages.problem}</p>
            ) : (
              <>
                <Columns
                  title="Messages per day, last 14 days"
                  series={["messages"]}
                  points={m.perDay.map((p) => ({
                    label: p.label,
                    values: [p.value],
                    title: `${p.day}: ${p.value}`,
                  }))}
                />
                <DataTable
                  head={["Day", "Messages"]}
                  rows={m.perDay.map((p) => [p.day, p.value])}
                />
              </>
            )}
          </StatCard>
          <StatCard
            id="journeys"
            title="Journeys"
            value={j.runs}
            note={`runs across ${j.active} active of ${j.total} journeys`}
          >
            {(journeys.problem ?? runs.problem) ? (
              <p role="alert">{journeys.problem ?? runs.problem}</p>
            ) : (
              <>
                <Bars title="Runs by status" rows={j.byStatus} />
                <DataTable
                  head={["Status", "Runs"]}
                  rows={j.byStatus.map((c) => [c.label, c.value])}
                />
              </>
            )}
          </StatCard>
          <StatCard
            id="templates"
            title="Templates"
            value={t.approved}
            note={`approved of ${t.total}; ${statusLine(t.byStatus, "no templates yet")}`}
          >
            {templates.problem ? (
              <p role="alert">{templates.problem}</p>
            ) : (
              <>
                <Bars title="Templates by status" rows={t.byStatus} />
                <DataTable
                  head={["Status", "Templates"]}
                  rows={t.byStatus.map((c) => [c.label, c.value])}
                />
              </>
            )}
          </StatCard>
          <StatCard
            id="sync"
            title="Sync"
            value={s.inserted + s.updated}
            note={`contacts written in ${s.runs} runs${s.lastStatus ? `, last run ${s.lastStatus}` : ""}`}
          >
            {syncRuns.problem ? (
              <p role="alert">{syncRuns.problem}</p>
            ) : (
              <>
                <Columns
                  title="Contacts written per sync run, last 10 runs"
                  series={SYNC_SERIES}
                  points={s.points.map((p) => ({
                    label: p.label,
                    values: [p.inserted, p.updated],
                    title: `${p.label}: inserted ${p.inserted}, updated ${p.updated} (${p.status})`,
                  }))}
                />
                <Legend series={SYNC_SERIES} />
                <DataTable
                  head={["Run", "Inserted", "Updated", "Status"]}
                  rows={s.points.map((p) => [p.label, p.inserted, p.updated, p.status])}
                />
              </>
            )}
          </StatCard>
        </section>
        <form action={logout} style={{ marginTop: "var(--space-6)" }}>
          <button type="submit" className="secondary">
            Sign out
          </button>
        </form>
      </main>
    </>
  );
}
