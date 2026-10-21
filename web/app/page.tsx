import { redirect } from "next/navigation";
import { logout } from "@/app/login/actions";
import { createClient } from "@/lib/supabase/server";
import Link from "next/link";

export default async function HomePage() {
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    redirect("/login");
  }

  return (
    <main>
      <h1>Social Media campaigns tool</h1>
      <p>Signed in as {user.email}</p>
      <p>
        <Link href="/templates">Templates</Link>
      </p>
      <p>
        <Link href="/messages">Messages</Link>
      </p>
      <p>
        <Link href="/journeys">Journeys</Link>
      </p>
      <form action={logout}>
        <button type="submit">Sign out</button>
      </form>
    </main>
  );
}
