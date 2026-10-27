import "server-only";
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { ApiError } from "@/lib/api";

/**
 * Runs one API call from a server action. Success revalidates and redirects to `next` (a path,
 * or one computed from the result); failure sends the API's message to `back` as ?error=;
 * a 401 goes to the login page.
 */
export async function perform<T>(
  call: () => Promise<T>,
  next: string | ((result: T) => string),
  back: string,
): Promise<never> {
  let target: string | null = null;
  let failure: string | null = null;
  let status = 0;
  try {
    const result = await call();
    target = typeof next === "function" ? next(result) : next;
  } catch (error) {
    failure = error instanceof ApiError ? error.message : "unexpected error";
    status = error instanceof ApiError ? error.status : 0;
  }
  if (status === 401) {
    redirect("/login");
  }
  if (failure !== null || target === null) {
    redirect(`${back}?error=${encodeURIComponent(failure ?? "unexpected error")}`);
  }
  revalidatePath(target);
  redirect(target);
}

/** One API call whose failure the caller shows in place (a 401 still goes to the login page). */
export async function attempt<T>(
  call: () => Promise<T>,
): Promise<{ ok: true; result: T } | { ok: false; error: string }> {
  try {
    return { ok: true, result: await call() };
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) redirect("/login");
    return { ok: false, error: error instanceof ApiError ? error.message : "unexpected error" };
  }
}
