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
        <h1>WhatsApp campaigns</h1>
        <p>Signed in as {user.email}</p>
        <ul>
          <li>
            <Link href="/templates">Manage templates</Link>: drafts, submission to Meta, test sends.
          </li>
          <li>
            <Link href="/journeys">Build journeys</Link>: the editor, versions and runs.
          </li>
          <li>
            <Link href="/messages">Read the message log</Link>: delivery statuses per message.
          </li>
        </ul>
        <form action={logout}>
          <button type="submit" className="secondary">
            Sign out
          </button>
        </form>
      </main>
    </>
  );
}
