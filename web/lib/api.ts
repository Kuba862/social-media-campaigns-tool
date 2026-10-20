import "server-only";
import { createClient } from "@/lib/supabase/server";

/** Error from our API: `status` is the HTTP code, `message` is the API's `detail`. */
export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

type Options = { method?: "GET" | "POST"; body?: unknown };

function detailOf(payload: unknown): string | null {
  if (payload && typeof payload === "object" && "detail" in payload) {
    const detail = (payload as { detail: unknown }).detail;
    return typeof detail === "string" ? detail : null;
  }
  return null;
}

/** Calls our FastAPI as the signed-in user. Server side only: API_URL never reaches the browser. */
export async function apiFetch<T>(path: string, options: Options = {}): Promise<T> {
  const supabase = await createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  if (!session) {
    throw new ApiError(401, "not signed in");
  }
  const response = await fetch(`${process.env.API_URL}${path}`, {
    method: options.method ?? "GET",
    headers: {
      Authorization: `Bearer ${session.access_token}`,
      "Content-Type": "application/json",
    },
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
    cache: "no-store",
  });
  if (!response.ok) {
    const payload: unknown = await response.json().catch(() => null);
    throw new ApiError(response.status, detailOf(payload) ?? `API responded ${response.status}`);
  }
  return (await response.json()) as T;
}
