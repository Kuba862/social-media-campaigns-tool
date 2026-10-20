"use server";

import { redirect } from "next/navigation";
import { isAllowedEmail } from "@/lib/auth/domain";
import { createClient } from "@/lib/supabase/server";

export async function login(formData: FormData) {
  const email = String(formData.get("email") ?? "").trim();
  const password = String(formData.get("password") ?? "");

  if (!isAllowedEmail(email, process.env.PANEL_ALLOWED_EMAIL_DOMAIN ?? "")) {
    redirect("/login?error=domain");
  }

  const supabase = await createClient();
  const { error } = await supabase.auth.signInWithPassword({ email, password });
  if (error) {
    redirect("/login?error=credentials");
  }
  redirect("/");
}

export async function logout() {
  const supabase = await createClient();
  await supabase.auth.signOut({ scope: "local" });
  redirect("/login");
}
