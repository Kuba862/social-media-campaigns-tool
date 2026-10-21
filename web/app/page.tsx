import Link from "next/link";
import { redirect } from "next/navigation";
import { logout } from "@/app/login/actions";
import { Nav } from "@/components/nav";
import { createClient } from "@/lib/supabase/server";

export default async function HomePage() {
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    redirect("/login");
  }

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
        <form action={logout} style={{ marginTop: "var(--space-6)" }}>
          <button type="submit" className="secondary">
            Sign out
          </button>
        </form>
      </main>
    </>
  );
}
