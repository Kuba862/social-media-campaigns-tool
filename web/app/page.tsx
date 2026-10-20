import { redirect } from "next/navigation";
import { logout } from "@/app/login/actions";
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
    <main>
      <h1>Social Media campaigns tool</h1>
      <p>Signed in as {user.email}</p>
      <form action={logout}>
        <button type="submit">Sign out</button>
      </form>
    </main>
  );
}
